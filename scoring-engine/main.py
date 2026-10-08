import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Set
from fastapi.middleware.cors import CORSMiddleware
import json
import time

from config import config
from db import db
from scorer import scorer
from alerting import alert_manager
from feature_extractor import extract_features

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect()
    scorer.load()
    poll_task = asyncio.create_task(poll_database())
    yield
    # Shutdown
    poll_task.cancel()
    await db.disconnect()

app = FastAPI(title="API Security Scoring Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections: Set[WebSocket] = set()

start_time = time.time()
session_flags = {}

stats = {
    "total_scored": 0,
    "alerts_by_severity": {"info": 0, "warning": 0, "critical": 0}
}

async def broadcast_message(message: dict):
    if not active_connections:
        return
    msg_str = json.dumps(message, default=str)
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_text(msg_str)
        except Exception:
            disconnected.add(connection)
    
    for connection in disconnected:
        active_connections.discard(connection)

async def poll_database():
    last_id = 0
    while True:
        try:
            logs = await db.fetch_new_logs(last_id)
            if logs:
                # Group by session
                sessions: Dict[str, list] = {}
                for log in logs:
                    sid = log['session_id']
                    if sid not in sessions:
                        sessions[sid] = []
                    sessions[sid].append(log)
                    
                global_scored_batch = []
                
                for sid, session_logs in sessions.items():
                    try:
                        latest_ts = session_logs[-1]['timestamp']
                        full_session_logs = await db.fetch_recent_session(sid, latest_ts, seconds=60)
                        
                        if not full_session_logs or len(full_session_logs) < 5:
                            continue
                            
                        features = extract_features(full_session_logs)
                        score, severity, feature_contributions = scorer.score_features(features)
                        
                        if severity != "normal":
                            session_flags[sid] = session_flags.get(sid, 0) + 1
                        else:
                            session_flags[sid] = 0
                            
                        # Persistence rule: only flag if it's the 3rd consecutive anomaly
                        if session_flags[sid] < 3:
                            severity = "normal"
                            
                        stats["total_scored"] += len(session_logs)
                        
                        for log in session_logs:
                            global_scored_batch.append((log['id'], score, severity))
                            scored_req = {
                                "id": log['id'],
                                "timestamp": log['timestamp'],
                                "user_id": log['user_id'],
                                "session_id": sid,
                                "ip_address": log['ip_address'],
                                "endpoint": log['endpoint'],
                                "anomaly_score": score,
                                "is_anomaly": severity != "normal"
                            }
                            await broadcast_message({"type": "scored_request", "data": scored_req})
                            
                        if severity != "normal":
                            stats["alerts_by_severity"][severity] += 1
                            alert = await alert_manager.create_alert_if_needed(sid, session_logs, score, severity, feature_contributions)
                            if alert:
                                await broadcast_message({"type": "alert", "data": alert})
                    except Exception as e:
                        print(f"Error processing session {sid}: {e}")
                        continue
                
                if global_scored_batch:
                    await db.insert_scored_requests(global_scored_batch)
                    
                # Advance last_id only after successful processing
                last_id = max(log['id'] for log in logs)
                            
                await broadcast_message({
                    "type": "stats_update", 
                    "data": {
                        "total_scored": stats["total_scored"],
                        "alerts_by_severity": stats["alerts_by_severity"],
                        "uptime": time.time() - start_time
                    }
                })
                            
        except Exception as e:
            import traceback
            print(f"Error in polling task: {e}")
            traceback.print_exc()
            
        await asyncio.sleep(config.POLLING_INTERVAL)



@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": scorer.model is not None,
        "db_connected": db.conn is not None
    }

@app.get("/api/stats")
async def get_stats():
    return {
        "total_scored": stats["total_scored"],
        "alerts_by_severity": stats["alerts_by_severity"],
        "model_info": {
            "type": scorer.model_type,
            "threshold": scorer.tau
        },
        "uptime": time.time() - start_time
    }

@app.get("/api/alerts")
async def get_alerts(page: int = 1, per_page: int = 20, severity: str = None):
    offset = (page - 1) * per_page
    alerts = await db.fetch_alerts(limit=per_page, offset=offset, severity=severity)
    return alerts

@app.get("/api/sessions")
async def get_sessions():
    sessions = await db.fetch_active_sessions()
    formatted = []
    for s in sessions:
        logs = await db.fetch_session(s['session_id'])
        score = 0.0
        ip = "Unknown"
        if logs:
            features = extract_features(logs)
            score, _, _ = scorer.score_features(features)
            ip = logs[0].get('ip_address', 'Unknown')
            
        formatted.append({
            "session_id": s['session_id'],
            "requests": s['request_count'],
            "score": score,
            "ip": ip
        })
    return formatted

@app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str):
    logs = await db.fetch_session(session_id)
    return logs

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception as e:
        import traceback
        print(f"WS error: {e}")
        traceback.print_exc()
        active_connections.discard(websocket)


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=config.PORT)
