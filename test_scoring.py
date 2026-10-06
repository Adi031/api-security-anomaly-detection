import asyncio
import sys
import os
sys.path.append(os.path.abspath('scoring-engine'))
sys.path.append(os.path.abspath('ml-pipeline'))
from db import db
from feature_extractor import extract_features
from scorer import scorer

async def test():
    await db.connect()
    scorer.load()
    logs = await db.fetch_new_logs(0)
    print(f"Fetched {len(logs)} logs")
    if logs:
        try:
            features = extract_features(logs)
            print("Features extracted successfully:", features.shape)
            score, sev, contribs = scorer.score_features(features)
            print("Score:", score, sev)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(test())
