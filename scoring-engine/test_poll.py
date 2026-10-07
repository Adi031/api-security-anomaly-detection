import os
os.environ['MODEL_TYPE']='lstm'
import asyncio
from db import db
from scorer import scorer
from feature_extractor import extract_features
from alerting import alert_manager

async def test():
    await db.connect()
    scorer.load()
    
    last_id = 0
    logs = await db.fetch_new_logs(last_id)
    print(f"Found {len(logs)} new logs")
    
    sessions = {}
    for log in logs:
        sid = log['session_id']
        if sid not in sessions:
            sessions[sid] = []
        sessions[sid].append(log)
        
    for sid, session_logs in sessions.items():
        full_session_logs = await db.fetch_session(sid)
        features = extract_features(full_session_logs)
        score, severity, feature_contributions = scorer.score_features(features)
        
        if severity != "normal":
            try:
                alert = await alert_manager.create_alert_if_needed(sid, session_logs, score, severity, feature_contributions)
                print(f"Created alert: {alert}")
            except Exception as e:
                print(f"Error creating alert: {e}")
            break

asyncio.run(test())
