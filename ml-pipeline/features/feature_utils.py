"""
Shared Feature Extraction — Single Source of Truth

This module is the ONLY place where the 14 behavioral features are computed.
Both the training pipeline (feature_builder.py) and the scoring engine
(feature_extractor.py) import from here to guarantee identical computation.

Fixes issue #8: feature drift between training and serving.
"""

import re
import numpy as np
from datetime import datetime

# Feature names — authoritative list
FEATURE_NAMES = [
    'request_count',
    'unique_endpoints',
    'endpoint_diversity_ratio',
    'mean_inter_request_time',
    'std_inter_request_time',
    'min_inter_request_time',
    'failed_auth_ratio',
    'error_ratio',
    'method_post_ratio',
    'avg_response_time',
    'std_response_time',
    'sequential_id_score',
    'session_duration',
    'unique_user_agents',
]

NUM_FEATURES = len(FEATURE_NAMES)


def _parse_timestamp(ts):
    """Parse a timestamp to a float (seconds since epoch).
    
    Handles: datetime objects, strings (ISO format), floats, and numpy datetime64.
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, datetime):
        return ts.timestamp()
    if isinstance(ts, str):
        # Try ISO format variants
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', 
                     '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                     '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
            try:
                return datetime.strptime(ts, fmt).timestamp()
            except ValueError:
                continue
        # Fallback: try fromisoformat
        try:
            return datetime.fromisoformat(ts).timestamp()
        except (ValueError, TypeError):
            pass
    # numpy datetime64
    if hasattr(ts, 'astype'):
        try:
            return float(ts.astype('datetime64[s]').astype('float64'))
        except (ValueError, TypeError):
            pass
    return 0.0


def compute_sequential_id_score(endpoints):
    """
    Measure how sequential the resource IDs in endpoint URLs are.
    
    High score = systematic enumeration (e.g., /api/products/1, /api/products/2, /api/products/3)
    Low score = random/natural browsing
    
    Returns a score between 0 and 1.
    """
    # Extract numeric IDs from endpoint URLs
    ids = []
    for ep in endpoints:
        match = re.search(r'/(\d+)(?:/|$)', str(ep))
        if match:
            ids.append(int(match.group(1)))
    
    if len(ids) < 2:
        return 0.0
    
    # Calculate how many consecutive pairs differ by exactly 1
    sequential_pairs = sum(
        1 for i in range(len(ids) - 1) 
        if abs(ids[i + 1] - ids[i]) == 1
    )
    
    return sequential_pairs / (len(ids) - 1)


def extract_features_from_records(records):
    """
    Extract the 14-dimensional feature vector from a list of request records.
    
    Each record must be a dict (or dict-like) with keys:
        timestamp, endpoint, method, status_code, response_time_ms, user_agent
    
    This function is used by BOTH:
      - ml-pipeline/features/feature_builder.py (training)
      - scoring-engine/feature_extractor.py (serving)
    
    Args:
        records: list of dicts with request log fields
        
    Returns:
        numpy array of shape (NUM_FEATURES,) = (14,)
    """
    if not records:
        return np.zeros(NUM_FEATURES, dtype=np.float32)
    
    request_count = len(records)
    
    # Collect fields
    endpoints = [r.get('endpoint', '/') if isinstance(r, dict) else r['endpoint'] for r in records]
    methods = [r.get('method', 'GET') if isinstance(r, dict) else r['method'] for r in records]
    status_codes = [r.get('status_code', 200) if isinstance(r, dict) else r['status_code'] for r in records]
    response_times = [r.get('response_time_ms', 0) or 0 if isinstance(r, dict) else (r['response_time_ms'] or 0) for r in records]
    user_agents = [r.get('user_agent', '') if isinstance(r, dict) else r['user_agent'] for r in records]
    
    # Parse timestamps to floats
    raw_timestamps = [r.get('timestamp', 0) if isinstance(r, dict) else r['timestamp'] for r in records]
    timestamps = sorted([_parse_timestamp(ts) for ts in raw_timestamps])
    
    # 1. Request count
    # (already computed)
    
    # 2. Unique endpoints
    unique_endpoints = len(set(endpoints))
    
    # 3. Endpoint diversity ratio
    endpoint_diversity_ratio = unique_endpoints / request_count if request_count > 0 else 0
    
    # 4-6. Inter-request timing stats
    if len(timestamps) > 1:
        inter_times = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
        inter_times = [max(t, 0) for t in inter_times]  # Clamp negatives
        mean_inter_request_time = float(np.mean(inter_times))
        # Use ddof=1 (sample std) consistently — matches pandas default
        std_inter_request_time = float(np.std(inter_times, ddof=1)) if len(inter_times) > 1 else 0.0
        min_inter_request_time = float(np.min(inter_times))
    else:
        mean_inter_request_time = 0.0
        std_inter_request_time = 0.0
        min_inter_request_time = 0.0
    
    # 7. Failed auth ratio (401, 403 responses)
    auth_fail_count = sum(1 for sc in status_codes if sc in (401, 403))
    failed_auth_ratio = auth_fail_count / request_count
    
    # 8. Error ratio (all 4xx and 5xx)
    error_count = sum(1 for sc in status_codes if sc >= 400)
    error_ratio = error_count / request_count
    
    # 9. POST method ratio
    post_count = sum(1 for m in methods if m == 'POST')
    method_post_ratio = post_count / request_count
    
    # 10-11. Response time stats
    valid_rt = [rt for rt in response_times if rt is not None]
    if valid_rt:
        avg_response_time = float(np.mean(valid_rt))
        std_response_time = float(np.std(valid_rt, ddof=1)) if len(valid_rt) > 1 else 0.0
    else:
        avg_response_time = 0.0
        std_response_time = 0.0
    
    # 12. Sequential ID score
    sequential_id_score = compute_sequential_id_score(endpoints)
    
    # 13. Session duration (seconds)
    if len(timestamps) > 1:
        session_duration = timestamps[-1] - timestamps[0]
    else:
        session_duration = 0.0
    
    # 14. Unique user agents
    unique_user_agents = len(set(ua for ua in user_agents if ua))
    if unique_user_agents == 0:
        unique_user_agents = 1
    
    features = np.array([
        request_count,
        unique_endpoints,
        endpoint_diversity_ratio,
        mean_inter_request_time,
        std_inter_request_time,
        min_inter_request_time,
        failed_auth_ratio,
        error_ratio,
        method_post_ratio,
        avg_response_time,
        std_response_time,
        sequential_id_score,
        session_duration,
        unique_user_agents,
    ], dtype=np.float32)
    
    return features


def extract_per_feature_errors(original, reconstructed):
    """
    Compute per-feature squared reconstruction error for explainability.
    
    Args:
        original: numpy array of shape (NUM_FEATURES,)
        reconstructed: numpy array of shape (NUM_FEATURES,)
    
    Returns:
        dict mapping feature_name -> squared_error
    """
    errors = (original - reconstructed) ** 2
    return {name: float(errors[i]) for i, name in enumerate(FEATURE_NAMES)}
