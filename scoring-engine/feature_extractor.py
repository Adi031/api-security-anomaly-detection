import sys
import os
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), '../ml-pipeline'))

from config import config

if config.MODEL_TYPE == "lstm":
    from features.sequence_builder import build_sequence_features
    from scorer import scorer
    def extract_features(logs: list):
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return build_sequence_features(df, scorer.vocab, max_len=30)
else:
    from features.feature_utils import extract_features_from_records
    def extract_features(logs: list):
        return extract_features_from_records(logs)
