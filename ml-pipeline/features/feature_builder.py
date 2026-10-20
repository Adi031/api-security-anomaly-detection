"""
Feature Builder — Per-Window Feature Extraction from API Request Logs

Extracts behavioral features from raw request logs, grouped by user/session
within sliding time windows. These features capture the "fingerprint" of 
normal vs anomalous API usage patterns.

Usage:
    python features/feature_builder.py [--window 60] [--stride 30] [--output ../data/processed/]
"""

import os

import random
import numpy as np
import torch
random.seed(999)
np.random.seed(999)
torch.manual_seed(999)
import sys
import argparse
import pandas as pd
import sqlite3
from tqdm import tqdm
from datetime import timedelta
import pickle
from sklearn.preprocessing import StandardScaler
from feature_utils import extract_features_from_records, FEATURE_NAMES, NUM_FEATURES

def fetch_logs(start_time=None, end_time=None, limit=None):
    """Fetch request logs from SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database.sqlite')
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM request_logs"
    conditions = []
    params = []

    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY timestamp ASC"
    
    if limit:
        query += f" LIMIT {limit}"

    df = pd.read_sql(query, conn, params=params or None)
    conn.close()
    return df


def load_logs_from_csv(filepath):
    """Load request logs from a CSV file (alternative to DB)."""
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    return df


def extract_features_for_window(window_df):
    """
    Extract feature vector for a single time window of requests.
    
    Args:
        window_df: DataFrame of requests within the time window
        
    Returns:
        numpy array of shape (NUM_FEATURES,) or None if window is empty
    """
    if len(window_df) == 0:
        return None
    return extract_features_from_records(window_df.to_dict('records'))


def build_feature_matrix(df, window_seconds=60, stride_seconds=30, group_by='session_id', min_requests=None, step=2):
    """
    Build feature matrix from raw request logs using trailing windows.
    
    Extracts trailing 60s windows ending at sampled requests (every `step` requests),
    matching the trailing evaluation window of the live scoring engine.
    Only windows with at least `min_requests` (MIN_WINDOW_REQUESTS, default 10) are kept.
    
    Args:
        df: DataFrame of request logs
        window_seconds: Window size in seconds (default: 60)
        stride_seconds: Retained for CLI compatibility
        group_by: Column to group by ('session_id' or 'user_id' or 'ip_address')
        min_requests: Minimum requests in a window (default: 10 or MIN_WINDOW_REQUESTS env)
        step: Stride in number of requests between sampled trailing windows (default: 2)
        
    Returns:
        features: numpy array of shape (N, NUM_FEATURES)
        metadata: list of dicts with window info (group_id, start_time, end_time)
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    if min_requests is None:
        min_requests = int(os.getenv("MIN_WINDOW_REQUESTS", "10"))
        
    all_features = []
    all_metadata = []
    
    groups = df.groupby(group_by)
    
    for group_id, group_df in tqdm(groups, desc=f"Extracting features (by {group_by})"):
        group_df = group_df.sort_values('timestamp').reset_index(drop=True)
        
        if len(group_df) < min_requests:
            continue
        
        # Trailing 60s window ending at each sampled request
        for i in range(0, len(group_df), step):
            current_end = group_df['timestamp'].iloc[i]
            current_start = current_end - timedelta(seconds=window_seconds)
            
            window_mask = (
                (group_df['timestamp'] >= current_start) & 
                (group_df['timestamp'] <= current_end)
            )
            window_df = group_df[window_mask]
            
            if len(window_df) >= min_requests:
                features = extract_features_for_window(window_df)
                if features is not None:
                    traffic_type = window_df['traffic_type'].iloc[0] if 'traffic_type' in window_df.columns else 'normal'
                    all_features.append(features)
                    all_metadata.append({
                        'group_id': group_id,
                        'group_by': group_by,
                        'start_time': current_start,
                        'end_time': current_end,
                        'request_count': len(window_df),
                        'traffic_type': traffic_type,
                    })
    
    if not all_features:
        print("WARNING: No features extracted! Check your data.")
        return np.array([]).reshape(0, NUM_FEATURES), []
    
    return np.array(all_features), all_metadata


def split_and_save(features, metadata, output_dir, train_ratio=0.8, normal_only_train=True, label_col=None):
    """
    Split features into train/val/test sets and save.
    
    If normal_only_train is True, the training set contains only normal traffic.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    n = len(features)
    
    if normal_only_train and label_col:
        # Separate normal and anomalous
        labels = np.array([m.get(label_col, 'normal') for m in metadata])
        normal_mask = np.isin(labels, ['normal', 'power'])
        attack_mask = ~normal_mask
        
        normal_features = features[normal_mask]
        normal_metadata = [metadata[i] for i in range(len(metadata)) if normal_mask[i]]
        attack_features = features[attack_mask]
        
        # Split by session_id to prevent data leakage
        normal_session_ids = list(set(m.get('group_id', i) for i, m in enumerate(normal_metadata)))
        np.random.shuffle(normal_session_ids)
        
        n_sessions = len(normal_session_ids)
        n_train_sessions = int(n_sessions * train_ratio)
        n_val_sessions = int(n_sessions * 0.15)
        
        train_sessions = set(normal_session_ids[:n_train_sessions])
        val_sessions = set(normal_session_ids[n_train_sessions:n_train_sessions + n_val_sessions])
        test_sessions = set(normal_session_ids[n_train_sessions + n_val_sessions:])
        
        train_mask = np.array([m.get('group_id') in train_sessions for m in normal_metadata])
        val_mask = np.array([m.get('group_id') in val_sessions for m in normal_metadata])
        test_mask = np.array([m.get('group_id') in test_sessions for m in normal_metadata])
        
        train_features = normal_features[train_mask]
        val_features = normal_features[val_mask]
        test_normal_features = normal_features[test_mask]
        
        # Test set includes separate normal test and all attacks
        test_features = np.concatenate([test_normal_features, attack_features])
        test_labels = np.concatenate([
            np.zeros(len(test_normal_features)),  # 0 = normal
            np.ones(len(attack_features))  # 1 = attack
        ])
    else:
        # Simple random split (no labels)
        indices = np.random.permutation(n)
        n_train = int(n * train_ratio)
        n_val = int(n * 0.1)
        
        train_features = features[indices[:n_train]]
        val_features = features[indices[n_train:n_train + n_val]]
        test_features = features[indices[n_train + n_val:]]
        test_labels = None
    
    # Fit scaler on training data only
    scaler = StandardScaler()
    train_features_scaled = scaler.fit_transform(train_features)
    val_features_scaled = scaler.transform(val_features)
    test_features_scaled = scaler.transform(test_features)
    
    # Save everything
    np.save(os.path.join(output_dir, 'train_features.npy'), train_features_scaled)
    np.save(os.path.join(output_dir, 'val_features.npy'), val_features_scaled)
    np.save(os.path.join(output_dir, 'test_features.npy'), test_features_scaled)
    
    if test_labels is not None:
        np.save(os.path.join(output_dir, 'test_labels.npy'), test_labels)
    
    with open(os.path.join(output_dir, 'scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)
    
    with open(os.path.join(output_dir, 'feature_names.pkl'), 'wb') as f:
        pickle.dump(FEATURE_NAMES, f)
    
    with open(os.path.join(output_dir, 'metadata.pkl'), 'wb') as f:
        pickle.dump(metadata, f)
    
    print(f"\n✅ Features saved to {output_dir}")
    print(f"   Train: {len(train_features_scaled)} samples")
    print(f"   Val:   {len(val_features_scaled)} samples")
    print(f"   Test:  {len(test_features_scaled)} samples")
    if test_labels is not None:
        print(f"   Test attacks: {int(test_labels.sum())} / {len(test_labels)}")
    print(f"   Feature dim: {NUM_FEATURES}")
    print(f"   Scaler: StandardScaler fitted on training data")
    
    return scaler


def main():
    parser = argparse.ArgumentParser(description='Extract features from API request logs')
    parser.add_argument('--source', choices=['db', 'csv'], default='db',
                        help='Data source: "db" for PostgreSQL, "csv" for CSV file')
    parser.add_argument('--csv-path', type=str, default=None,
                        help='Path to CSV file (when --source csv)')
    parser.add_argument('--window', type=int, default=60,
                        help='Window size in seconds (default: 60)')
    parser.add_argument('--stride', type=int, default=30,
                        help='Stride between windows in seconds (default: 30)')
    parser.add_argument('--group-by', type=str, default='session_id',
                        choices=['session_id', 'user_id', 'ip_address'],
                        help='Group requests by this column (default: session_id)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory (default: data/processed/)')
    parser.add_argument('--train-ratio', type=float, default=0.8,
                        help='Fraction of data for training (default: 0.8)')
    parser.add_argument('--min-requests', type=int, default=int(os.getenv("MIN_WINDOW_REQUESTS", "10")),
                        help='Minimum requests in a window (default: 10)')
    parser.add_argument('--step', type=int, default=2,
                        help='Step size between trailing window samples (default: 2)')
    
    args = parser.parse_args()
    
    # Set default output path
    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(script_dir, '..', 'data', 'processed')
    
    print("=" * 60)
    print("Feature Builder — Behavioral Anomaly Detection")
    print("=" * 60)
    print(f"  Source:    {args.source}")
    print(f"  Window:    {args.window}s")
    print(f"  Stride:    {args.stride}s")
    print(f"  Group by:  {args.group_by}")
    print(f"  Output:    {args.output}")
    print("=" * 60)
    
    # Load data
    print("\n📥 Loading request logs...")
    if args.source == 'csv':
        if not args.csv_path:
            print("ERROR: --csv-path required when --source is csv")
            sys.exit(1)
        df = load_logs_from_csv(args.csv_path)
    else:
        df = fetch_logs()
    
    print(f"   Loaded {len(df)} request logs")
    
    if len(df) == 0:
        print("ERROR: No data found. Run the traffic simulator first.")
        sys.exit(1)
    
    # Extract features
    print("\n🔧 Extracting features...")
    features, metadata = build_feature_matrix(
        df, 
        window_seconds=args.window, 
        stride_seconds=args.stride,
        group_by=args.group_by,
        min_requests=args.min_requests,
        step=args.step
    )
    
    print(f"   Extracted {len(features)} feature vectors")
    
    # Save
    print("\n💾 Saving features...")
    split_and_save(features, metadata, args.output, train_ratio=args.train_ratio, label_col='traffic_type')
    
    # Print feature statistics
    print("\n📊 Feature Statistics (raw, before scaling):")
    for i, name in enumerate(FEATURE_NAMES):
        col = features[:, i]
        print(f"   {name:30s}  mean={col.mean():.4f}  std={col.std():.4f}  "
              f"min={col.min():.4f}  max={col.max():.4f}")


if __name__ == '__main__':
    main()
