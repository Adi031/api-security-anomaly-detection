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
    if sessions:
        s = sessions[0]
        logs = await db.fetch_session(s['session_id'])
        f = extract_features(logs)
        score, sev, _ = scorer.score_features(f)
        print(f"Success! Score: {score}")
    else:
        print("No sessions")

asyncio.run(test())
