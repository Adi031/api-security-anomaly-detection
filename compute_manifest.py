"""
Compute Timing Baseline Manifest & Fast Attack Sanity Check

Extracts inter-request timing percentiles from database.sqlite and saves
baseline parameters to data_manifest.json for live drift diagnostics.

Usage:
    python compute_manifest.py
"""

import os
import sqlite3
import json
import numpy as np
from datetime import datetime
from collections import defaultdict

def compute_manifest(db_path=None, output_path='data_manifest.json'):
    if db_path is None:
        db_path = os.getenv('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sqlite'))
        
    print(f"Connecting to database at {db_path}...")
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return None

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT session_id, timestamp, traffic_type FROM request_logs ORDER BY session_id, timestamp ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("Error: No request logs found in database. Run traffic simulator first.")
        return None

    sessions = defaultdict(list)
    for sid, ts, tt in rows:
        sessions[sid].append((datetime.fromisoformat(ts), tt))

    legit_gaps = []
    fast_attack_gaps = []
    fast_types = {'credential_stuffing', 'scraping', 'enumeration', 'privilege_probe'}

    for sid, logs in sessions.items():
        tt = logs[0][1]
        for i in range(1, len(logs)):
            gap = (logs[i][0] - logs[i-1][0]).total_seconds()
            if gap >= 0:
                if tt in ('normal', 'power'):
                    legit_gaps.append(gap)
                elif tt in fast_types:
                    fast_attack_gaps.append(gap)

    if not legit_gaps:
        print("Error: No legitimate inter-request gaps found.")
        return None

    fast_median = float(np.median(fast_attack_gaps)) if fast_attack_gaps else 0.0
    passed = fast_median < 0.5 and len(fast_attack_gaps) > 0

    manifest = {
        'total_gaps_analyzed': len(legit_gaps),
        'median_gap': round(float(np.median(legit_gaps)), 4),
        'mean_gap': round(float(np.mean(legit_gaps)), 4),
        'p1_gap': round(float(np.percentile(legit_gaps, 1)), 4),
        'p5_gap': round(float(np.percentile(legit_gaps, 5)), 4),
        'p25_gap': round(float(np.percentile(legit_gaps, 25)), 4),
        'p75_gap': round(float(np.percentile(legit_gaps, 75)), 4),
        'p95_gap': round(float(np.percentile(legit_gaps, 95)), 4),
        'fast_attack_median_gap': round(fast_median, 4),
        'fast_attack_sanity_check': 'PASSED (< 0.5s)' if passed else 'FAILED'
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 60)
    print("TIMING MANIFEST & SANITY CHECK RESULTS")
    print("=" * 60)
    print(json.dumps(manifest, indent=2))
    print(f"\nSaved manifest to {output_path}")
    print("=" * 60)
    return manifest

if __name__ == '__main__':
    compute_manifest()
