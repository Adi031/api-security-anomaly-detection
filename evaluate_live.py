import asyncio
import os
import sys
import json
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoring-engine"))

from db import db
from scorer import scorer
from feature_extractor import extract_features

async def evaluate_live():
    print("Loading models and database...")
    await db.connect()
    scorer.load()
    
    print("Fetching all request logs...")
    logs = await db.fetch_new_logs(0)
    
    if not logs:
        print("No logs in database.")
        await db.disconnect()
        return
        
    # Group by session
    sessions = {}
    for log in logs:
        sid = log['session_id']
        if sid not in sessions:
            sessions[sid] = []
        sessions[sid].append(log)
        
    print(f"Loaded {len(logs)} requests across {len(sessions)} sessions.")
    
    session_results = []
    
    print("\nSimulating real-time 60s sliding window scoring engine with persistence rule...")
    for i, (sid, session_logs) in enumerate(sessions.items()):
        if (i+1) % 50 == 0:
            print(f"Processed {i+1}/{len(sessions)} sessions...")
            
        traffic_type = session_logs[0].get('traffic_type', 'normal')
        
        # Sort logs by timestamp just in case
        session_logs.sort(key=lambda x: x['timestamp'])
        
        consecutive_flags = 0
        flagged = False
        
        # Walk through logs and simulate the 60s window at each step
        for j in range(len(session_logs)):
            current_log = session_logs[j]
            current_ts = datetime.fromisoformat(current_log['timestamp'])
            
            # Get logs in the 60 seconds before this log
            window_logs = []
            for k in range(j, -1, -1):
                past_log = session_logs[k]
                past_ts = datetime.fromisoformat(past_log['timestamp'])
                if (current_ts - past_ts).total_seconds() <= 60:
                    window_logs.append(past_log)
                else:
                    break
            
            window_logs.reverse() # chronological order
            
            if len(window_logs) < 5:
                consecutive_flags = 0
                continue
                
            features = extract_features(window_logs)
            if features is not None and len(features) > 0:
                score, severity, _ = scorer.score_features(features)
                if severity != "normal":
                    consecutive_flags += 1
                else:
                    consecutive_flags = 0
            else:
                consecutive_flags = 0
                
            # Persistence rule: flag only if 3 consecutive windows are anomalous
            if consecutive_flags >= 3:
                flagged = True
                break # We caught them, no need to keep scoring the rest of the session
            
        session_results.append({
            "session_id": sid,
            "traffic_type": traffic_type,
            "flagged": flagged
        })
        
    await db.disconnect()
    
    # Aggregate results
    stats = defaultdict(lambda: {"total": 0, "flagged": 0})
    
    for res in session_results:
        tt = res["traffic_type"]
        stats[tt]["total"] += 1
        if res["flagged"]:
            stats[tt]["flagged"] += 1
            
    print("\n" + "="*50)
    print("LIVE REPLAY EVALUATION RESULTS (SESSION-LEVEL)")
    print("="*50)
    print(f"{'Traffic Type':<25} | {'Sessions Flagged':<15} | {'Rate'}")
    print("-" * 50)
    
    for tt, data in sorted(stats.items()):
        total = data["total"]
        flagged = data["flagged"]
        rate = (flagged / total * 100) if total > 0 else 0
        print(f"{tt:<25} | {flagged:>5} / {total:<7} | {rate:.1f}%")
        
    print("="*50)

if __name__ == "__main__":
    asyncio.run(evaluate_live())
