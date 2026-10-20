import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Set
from fastapi.middleware.cors import CORSMiddleware
import json
import time
import traceback

from config import config
from db import db
from scorer import scorer
from alerting import alert_manager
from feature_extractor import extract_features

@asynccontextmanager
async def lifespan(app: FastAPI):
    global last_id
    # Startup
    await db.connect()
    # Resume from last scored position to avoid duplicate scoring on restart
    async with db.conn.execute("SELECT COALESCE(MAX(request_log_id), 0) FROM scored_requests") as cursor:
        row = await cursor.fetchone()
        last_id = row[0] if row else 0
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
last_id = 0
session_flags = {}
session_flag_times = {}
alert_cooldowns = {}

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
    global last_id
    while True:
        try:
            logs = await db.fetch_new_logs(last_id, limit=5000)
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
                        
                        if not full_session_logs:
                            continue
                        
                        full_session_logs.sort(key=lambda x: x['timestamp'])
                        
                        overall_score = 0.0
                        raw_overall_severity = "normal"
                        overall_contributions = {}
                        
                        if len(full_session_logs) >= config.MIN_WINDOW_REQUESTS:
                            features = extract_features(full_session_logs)
                            overall_score, raw_overall_severity, overall_contributions = scorer.score_features(features)
                        else:
                            # Fast-path check for short burst attacks (e.g. failed login spray or rapid probe)
                            err_logs = [l for l in full_session_logs if l.get('status_code', 200) >= 400]
                            if len(full_session_logs) >= 3 and len(err_logs) / len(full_session_logs) >= 0.75:
                                overall_score = scorer.tau * 1.5
                                raw_overall_severity = "warning"
                                overall_contributions = {"rapid_error_burst": 1.0}
                        
                        if raw_overall_severity != "normal":
                            session_flags[sid] = session_flags.get(sid, 0) + 1
                        else:
                            session_flags[sid] = 0
                        session_flag_times[sid] = time.time()
                            
                        stats["total_scored"] += len(session_logs)
                        
                        # Score individual requests with their trailing window
                        for log in session_logs:
                            req_ts = log['timestamp']
                            trailing_reqs = [l for l in full_session_logs if l['timestamp'] <= req_ts]
                            req_score = 0.0
                            raw_req_sev = "normal"
                            
                            if len(trailing_reqs) >= config.MIN_WINDOW_REQUESTS:
                                req_feats = extract_features(trailing_reqs)
                                req_score, raw_req_sev, _ = scorer.score_features(req_feats)
                            elif len(trailing_reqs) >= 3:
                                err_count = sum(1 for r in trailing_reqs if r.get('status_code', 200) >= 400)
                                if err_count / len(trailing_reqs) >= 0.75:
                                    req_score = scorer.tau * 1.5
                                    raw_req_sev = "warning"
                            
                            # Store raw model severity to preserve raw decisions in DB
                            global_scored_batch.append((log['id'], req_score, raw_req_sev))
                            
                            scored_req = {
                                "id": log['id'],
                                "timestamp": log['timestamp'],
                                "user_id": log['user_id'],
                                "session_id": sid,
                                "ip_address": log['ip_address'],
                                "endpoint": log['endpoint'],
                                "anomaly_score": req_score,
                                "is_anomaly": raw_req_sev != "normal"
                            }
                            await broadcast_message({"type": "scored_request", "data": scored_req})
                            
                        # Persistence rule: only trigger alerts on 3rd consecutive anomaly
                        if session_flags[sid] >= 3 and raw_overall_severity != "normal":
                            stats["alerts_by_severity"][raw_overall_severity] += 1
                            # Only alert if not in cooldown (60 seconds between alerts per session)
                            if sid not in alert_cooldowns or time.time() - alert_cooldowns[sid] > 60:
                                alert = await alert_manager.create_alert_if_needed(sid, session_logs, overall_score, raw_overall_severity, overall_contributions)
                                if alert:
                                    alert_cooldowns[sid] = time.time()
                                    await broadcast_message({"type": "alert", "data": alert})
                    except Exception as e:
                        print(f"Error processing session {sid}: {e}")
                        continue
                
                # Clean up stale session flags and alert cooldowns (sessions idle for 10+ minutes)
                current_time = time.time()
                stale_sessions = [s for s, t in session_flag_times.items() if current_time - t > 600]
                for s in stale_sessions:
                    session_flags.pop(s, None)
                    session_flag_times.pop(s, None)
                    
                stale_cooldowns = [s for s, t in alert_cooldowns.items() if current_time - t > 600]
                for s in stale_cooldowns:
                    alert_cooldowns.pop(s, None)
                
                if global_scored_batch:
                    await db.insert_scored_requests(global_scored_batch)
                    
                # Advance last_id only after successful processing
                last_id = max(log['id'] for log in logs)
                            
                await broadcast_message({
                    "type": "stats_update", 
                    "data": {
                        "total_scored": stats["total_scored"],
                        "alerts_by_severity": stats["alerts_by_severity"],
                        "model_info": {
                            "type": scorer.model_type,
                            "threshold": scorer.tau
                        },
                        "uptime": time.time() - start_time
                    }
                })
                            
        except Exception as e:
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
            ip = logs[0].get('ip_address', 'Unknown')
        if logs and len(logs) >= config.MIN_WINDOW_REQUESTS:
            features = extract_features(logs)
            score, _, _ = scorer.score_features(features)
            
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
    if not logs:
        return None
        
    score = 0.0
    severity = "normal"
    top_features = []
    
    if len(logs) >= config.MIN_WINDOW_REQUESTS:
        features = extract_features(logs)
        score, severity, contributions = scorer.score_features(features)
        if contributions:
            sorted_feats = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
            top_features = [f"{k} ({v:.2f})" for k, v in sorted_feats[:4] if v > 0.01]

    # Calculate session duration
    try:
        from datetime import datetime
        t0 = datetime.fromisoformat(logs[0]['timestamp'].replace('Z', '+00:00'))
        t1 = datetime.fromisoformat(logs[-1]['timestamp'].replace('Z', '+00:00'))
        duration = max(0, int((t1 - t0).total_seconds()))
    except Exception:
        duration = 0

    return {
        "session_id": session_id,
        "score": score,
        "severity": severity,
        "ip": logs[0].get('ip_address', 'Unknown'),
        "user_id": logs[0].get('user_id'),
        "duration": duration,
        "features": top_features,
        "requests": [
            {
                "timestamp": l["timestamp"],
                "score": float(l["anomaly_score"]) if l.get("anomaly_score") is not None else (
                    score if len(logs) >= config.MIN_WINDOW_REQUESTS and idx >= config.MIN_WINDOW_REQUESTS - 1 else 0.0
                ),
                "method": l["method"],
                "path": l["endpoint"],
                "status_code": l.get("status_code", 200)
            }
            for idx, l in enumerate(logs[-50:])
        ]
    }

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
        print(f"WS error: {e}")
        traceback.print_exc()
        active_connections.discard(websocket)


if __name__ == '__main__':
    uvicorn.run('main:app', host='127.0.0.1', port=config.PORT)
