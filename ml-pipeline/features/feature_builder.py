"""
Feature Builder — Per-Window Feature Extraction from API Request Logs

Extracts behavioral features from raw request logs, grouped by user/session
within sliding time windows. These features capture the "fingerprint" of 
normal vs anomalous API usage patterns.

Usage:
    python features/feature_builder.py [--window 60] [--stride 30] [--output ../data/processed/]
"""

import os
import sys
import argparse
import numpy as np
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


def compute_sequential_id_score(endpoints):
    """
    Measure how sequential the resource IDs in endpoint URLs are.
    
    High score = systematic enumeration (e.g., /api/products/1, /api/products/2, /api/products/3)
    Low score = random/natural browsing
    
    Returns a score between 0 and 1.
    """
    import re
    
    # Extract numeric IDs from endpoint URLs
    ids = []
    for ep in endpoints:
        match = re.search(r'/(\d+)(?:/|$)', ep)
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


def build_feature_matrix(df, window_seconds=60, stride_seconds=30, group_by='session_id'):
    """
    Build feature matrix from raw request logs.
    
    Groups requests by session/user and extracts features for each time window.
    
    Args:
        df: DataFrame of request logs
        window_seconds: Window size in seconds
        stride_seconds: Stride between windows
        group_by: Column to group by ('session_id' or 'user_id' or 'ip_address')
        
    Returns:
        features: numpy array of shape (N, NUM_FEATURES)
        metadata: list of dicts with window info (group_id, start_time, end_time)
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    all_features = []
    all_metadata = []
    
    groups = df.groupby(group_by)
    
    for group_id, group_df in tqdm(groups, desc=f"Extracting features (by {group_by})"):
        group_df = group_df.sort_values('timestamp')
        
        if len(group_df) < 2:
            continue
        
        start_time = group_df['timestamp'].min()
        end_time = group_df['timestamp'].max()
        
        # Sliding window
        current_start = start_time
        while current_start < end_time:
            current_end = current_start + timedelta(seconds=window_seconds)
            
            window_mask = (
                (group_df['timestamp'] >= current_start) & 
                (group_df['timestamp'] < current_end)
            )
            window_df = group_df[window_mask]
            
            if len(window_df) >= 2:  # Need at least 2 requests for meaningful features
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
            
            current_start += timedelta(seconds=stride_seconds)
    
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
        normal_mask = labels == 'normal'
        attack_mask = ~normal_mask
        
        normal_features = features[normal_mask]
        attack_features = features[attack_mask]
        
        # Split normal into train/val
        n_normal = len(normal_features)
        n_train = int(n_normal * train_ratio)
        
        indices = np.random.permutation(n_normal)
        train_features = normal_features[indices[:n_train]]
        val_features = normal_features[indices[n_train:]]
        
        # Test set includes both normal val and all attacks
        test_features = np.concatenate([val_features, attack_features])
        test_labels = np.concatenate([
            np.zeros(len(val_features)),  # 0 = normal
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
        group_by=args.group_by
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
