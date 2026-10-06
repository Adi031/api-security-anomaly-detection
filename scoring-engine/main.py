import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Set, Dict
from datetime import datetime
import json
import time

from config import config
from db import db
from scorer import scorer
from alerting import alert_manager
from feature_extractor import extract_features

app = FastAPI(title="API Security Scoring Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections: Set[WebSocket] = set()

start_time = time.time()
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
                    
                
                last_id = max(log['id'] for log in logs)

                for sid, session_logs in sessions.items():
                    features = extract_features(session_logs)
                    score, severity, feature_contributions = scorer.score_features(features)
                    
                    stats["total_scored"] += len(session_logs)
                    
                    scored_batch = []
                    for log in session_logs:
                        scored_batch.append((log['id'], score, severity))
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

@app.on_event("startup")
async def startup_event():
    await db.connect()
    scorer.load()
    asyncio.create_task(poll_database())

@app.on_event("shutdown")
async def shutdown_event():
    await db.disconnect()

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
