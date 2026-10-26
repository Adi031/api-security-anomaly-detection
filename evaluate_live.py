import asyncio
import os
import sys
import json
import argparse
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoring-engine"))

MIN_WINDOW_REQUESTS = int(os.getenv("MIN_WINDOW_REQUESTS", "10"))

async def evaluate_live(db_path=None):
    if db_path:
        os.environ["DB_PATH"] = db_path

    from db import db
    from scorer import scorer
    from feature_extractor import extract_features

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
    legit_feature_vectors = []
    
    print("\nSimulating real-time 60s sliding window scoring engine with persistence rule...")
    for i, (sid, session_logs) in enumerate(sessions.items()):
        if (i+1) % 50 == 0:
            print(f"Processed {i+1}/{len(sessions)} sessions...")
            
        traffic_type = session_logs[0].get('traffic_type', 'normal')
        
        # Sort logs by timestamp just in case
        session_logs.sort(key=lambda x: x['timestamp'])
        
        consecutive_flags = 0
        flagged = False
        windows_evaluated = 0
        
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
            
            if len(window_logs) < MIN_WINDOW_REQUESTS:
                consecutive_flags = 0
                continue
                
            windows_evaluated += 1
            features = extract_features(window_logs)
            if features is not None and len(features) > 0:
                if traffic_type in ["normal", "power"]:
                    legit_feature_vectors.append(features)
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
            "flagged": flagged,
            "total_requests": len(session_logs),
            "reached_gate": len(session_logs) >= MIN_WINDOW_REQUESTS,
            "windows_evaluated": windows_evaluated
        })
        
    await db.disconnect()

    # Drift Check on Legitimate Traffic
    if legit_feature_vectors and hasattr(scorer, 'scaler') and scorer.scaler is not None:
        import numpy as np
        from features.feature_utils import FEATURE_NAMES
        legit_mat = np.array(legit_feature_vectors)
        print("\n" + "="*75)
        print("FEATURE DRIFT DIAGNOSTIC (LEGITIMATE TRAFFIC VS TRAINING DISTRIBUTION)")
        print("="*75)
        print(f"{'Feature':<26} | {'Live Median':<11} | {'Train Mean':<11} | {'Scale':<8} | {'z-score':<8} | {'Status'}")
        print("-" * 75)
        scaler = scorer.scaler
        has_drift_warning = False
        for idx, feat_name in enumerate(FEATURE_NAMES):
            live_med = float(np.median(legit_mat[:, idx]))
            tr_mean = float(scaler.mean_[idx])
            tr_scale = float(scaler.scale_[idx])
            z = (live_med - tr_mean) / tr_scale
            status = "OK" if abs(z) <= 3.0 else "WARN (|z|>3)"
            if abs(z) > 3.0:
                has_drift_warning = True
            print(f"{feat_name:<26} | {live_med:>11.4f} | {tr_mean:>11.4f} | {tr_scale:>8.4f} | {z:>+7.2f}  | {status}")
        print("="*75)
        if has_drift_warning:
            print("[WARN] Timing or behavioral drift detected between live simulator and training set.")
        else:
            print("[OK] No significant distribution drift detected (all legitimate feature |z| <= 3.0).")
    
    # Timing Gap Percentile Diagnostic
    legit_gaps = []
    for sid, s_logs in sessions.items():
        tt = s_logs[0].get('traffic_type', 'normal')
        if tt in ['normal', 'power']:
            for k in range(1, len(s_logs)):
                t1 = datetime.fromisoformat(s_logs[k-1]['timestamp'])
                t2 = datetime.fromisoformat(s_logs[k]['timestamp'])
                gap = (t2 - t1).total_seconds()
                if gap >= 0:
                    legit_gaps.append(gap)

    if legit_gaps and os.path.exists('data_manifest.json'):
        with open('data_manifest.json', 'r') as f:
            manifest = json.load(f)
        live_med_gap = float(np.median(legit_gaps))
        live_p1_gap = float(np.percentile(legit_gaps, 1))
        live_p95_gap = float(np.percentile(legit_gaps, 95))
        tr_med_gap = manifest.get('median_gap', 5.0)
        tr_p1_gap = manifest.get('p1_gap', 2.0)
        tr_p95_gap = manifest.get('p95_gap', 12.0)
        print("\n" + "="*75)
        print("TIMING GAP DISTRIBUTION (LIVE SIMULATION VS TRAINING BASELINE)")
        print("="*75)
        print(f"{'Metric':<24} | {'Live Traffic':<15} | {'Training Baseline':<18} | {'Difference'}")
        print("-" * 75)
        med_diff = abs(live_med_gap - tr_med_gap)/tr_med_gap*100
        p1_diff = abs(live_p1_gap - tr_p1_gap)/tr_p1_gap*100
        print(f"{'Median Gap':<24} | {live_med_gap:>13.2f}s | {tr_med_gap:>16.2f}s | {med_diff:>9.1f}%")
        print(f"{'P1 (Fastest Gap)':<24} | {live_p1_gap:>13.2f}s | {tr_p1_gap:>16.2f}s | {p1_diff:>9.1f}%")
        print(f"{'P95 (Slowest Gap)':<24} | {live_p95_gap:>13.2f}s | {tr_p95_gap:>16.2f}s | {abs(live_p95_gap - tr_p95_gap)/tr_p95_gap*100:>9.1f}%")
        print("="*75)
        if med_diff > 50.0:
            print("[WARN] Live traffic pacing differs significantly from training baseline.")
        else:
            print("[OK] Live traffic pacing aligns with training distribution.")

    # Aggregate results
    stats = defaultdict(lambda: {"total": 0, "reached_gate": 0, "flagged": 0})
    
    for res in session_results:
        tt = res["traffic_type"]
        stats[tt]["total"] += 1
        if res["reached_gate"]:
            stats[tt]["reached_gate"] += 1
        if res["flagged"]:
            stats[tt]["flagged"] += 1
            
    print("\n" + "="*75)
    print("LIVE REPLAY EVALUATION RESULTS (SESSION-LEVEL)")
    print("="*75)
    print(f"{'Traffic Type':<22} | {'Flagged / Gate (>=10)':<22} | {'Gate Rate':<10} | {'Total Flagged'}")
    print("-" * 75)
    
    for tt, data in sorted(stats.items()):
        total = data["total"]
        gate = data["reached_gate"]
        flagged = data["flagged"]
        gate_rate = (flagged / gate * 100) if gate > 0 else 0
        total_rate = (flagged / total * 100) if total > 0 else 0
        print(f"{tt:<22} | {flagged:>3} / {gate:<4} ({gate:>3}/{total:<3} reached) | {gate_rate:>6.1f}%   | {flagged}/{total} ({total_rate:.1f}%)")
        
    print("="*75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate live session replay")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite database")
    args = parser.parse_args()
    asyncio.run(evaluate_live(db_path=args.db))
