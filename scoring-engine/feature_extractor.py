import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../ml-pipeline'))
from features.feature_utils import extract_features_from_records

def extract_features(logs: list):
    return extract_features_from_records(logs)
