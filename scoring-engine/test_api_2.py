import os
os.environ['MODEL_TYPE']='lstm'
import asyncio
from db import db
from scorer import scorer
from feature_extractor import extract_features

async def test():
    await db.connect()
    scorer.load()
    sessions = await db.fetch_active_sessions()
    print(f"Found {len(sessions)} sessions")
    for s in sessions:
        logs = await db.fetch_session(s['session_id'])
        if logs:
            try:
                features = extract_features(logs)
                score, _, _ = scorer.score_features(features)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error on session {s['session_id']}")
                break
                
asyncio.run(test())
