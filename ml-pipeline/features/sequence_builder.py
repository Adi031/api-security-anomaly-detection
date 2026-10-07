"""
Sequence Builder — Per-Session API Call Sequence Extraction

Converts raw request logs into ordered sequences of API calls per session,
suitable for the LSTM autoencoder (Stage 2).

Each timestep in a sequence represents one API call with features:
  - Endpoint embedding ID
  - HTTP method (one-hot)
  - Status code bucket
  - Inter-request time (log-scaled)
  - Response time (normalized)

Usage:
    python features/sequence_builder.py [--seq-len 30] [--output ../data/processed/]
"""

import os
import argparse
import numpy as np
import pandas as pd
import sqlite3
import pickle
import re
from tqdm import tqdm

# Endpoint vocabulary — maps endpoint patterns to IDs
# We normalize endpoints by replacing numeric IDs with <ID>
ENDPOINT_PATTERNS = {}  # Built dynamically from data


def normalize_endpoint(endpoint):
    """
    Normalize endpoint by replacing numeric path segments with <ID>.
    E.g., /api/products/42 → /api/products/<ID>
    """
    return re.sub(r'/\d+', '/<ID>', endpoint)


def build_endpoint_vocab(endpoints):
    """Build endpoint vocabulary from all seen endpoints."""
    normalized = [normalize_endpoint(ep) for ep in endpoints]
    unique = sorted(set(normalized))
    vocab = {ep: idx + 1 for idx, ep in enumerate(unique)}  # 0 reserved for padding
    vocab['<PAD>'] = 0
    vocab['<UNK>'] = len(vocab)
    return vocab


def encode_method(method):
    """One-hot encode HTTP method → 4-dim vector."""
    methods = {'GET': 0, 'POST': 1, 'PUT': 2, 'DELETE': 3}
    vec = np.zeros(4, dtype=np.float32)
    idx = methods.get(method.upper(), 0)
    vec[idx] = 1.0
    return vec


def encode_status(status_code):
    """Encode status code into bucket → scalar."""
    if 200 <= status_code < 300:
        return 0.0
    elif 300 <= status_code < 400:
        return 0.25
    elif status_code == 401 or status_code == 403:
        return 0.75  # Auth failures specifically
    elif 400 <= status_code < 500:
        return 0.5  # Client errors
    else:
        return 1.0  # Server errors


def fetch_logs():
    """Fetch request logs from SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database.sqlite')
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT * FROM request_logs ORDER BY timestamp ASC",
        conn
    )
    conn.close()
    return df


def load_logs_from_csv(filepath):
    """Load from CSV file."""
    return pd.read_csv(filepath, parse_dates=['timestamp'])


def build_sequences(df, seq_len=30, group_by='session_id'):
    """
    Build API call sequences from raw logs.
    
    Args:
        df: DataFrame of request logs
        seq_len: Fixed sequence length (pad/truncate)
        group_by: Column to group by
        
    Returns:
        sequences: numpy array of shape (N, seq_len, feature_dim)
        metadata: list of dicts with sequence info
        vocab: endpoint vocabulary
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Build endpoint vocabulary on normal data only
    if 'traffic_type' in df.columns:
        normal_endpoints = df[df['traffic_type'] == 'normal']['endpoint'].tolist()
    else:
        normal_endpoints = df['endpoint'].tolist()
    
    vocab = build_endpoint_vocab(normal_endpoints)
    vocab_size = len(vocab)
    print(f"  Endpoint vocabulary size: {vocab_size}")
    
    # Feature dimension per timestep:
    # endpoint_id (1) + method_onehot (4) + status_bucket (1) + 
    # inter_time (1) + response_time (1) + request_body_size (1) + is_auth (1)
    feature_dim = 10
    
    all_sequences = []
    all_metadata = []
    
    groups = df.groupby(group_by)
    
    for group_id, group_df in tqdm(groups, desc=f"Building sequences (by {group_by})"):
        group_df = group_df.sort_values('timestamp')
        
        if len(group_df) < 3:  # Need at least 3 calls for a meaningful sequence
            continue
            
        traffic_type = group_df['traffic_type'].iloc[0] if 'traffic_type' in group_df.columns else 'normal'
        
        # Build feature vectors for each API call
        call_features = []
        timestamps = group_df['timestamp'].values
        
        for i, (_, row) in enumerate(group_df.iterrows()):
            # Endpoint ID (NOT normalized, for Embedding)
            norm_ep = normalize_endpoint(row['endpoint'])
            ep_id = vocab.get(norm_ep, vocab.get('<UNK>', 0))
            
            # Method one-hot
            method_vec = encode_method(row.get('method', 'GET'))
            
            # Status code bucket
            status = encode_status(row.get('status_code', 200))
            
            # Inter-request time (log-scaled)
            if i > 0:
                dt = (timestamps[i] - timestamps[i-1])
                # Handle numpy timedelta
                if hasattr(dt, 'total_seconds'):
                    inter_time = dt.total_seconds()
                else:
                    inter_time = dt / np.timedelta64(1, 's')
                inter_time = np.log1p(max(inter_time, 0))  # log(1 + t) for stability
            else:
                inter_time = 0.0
            
            # Response time (normalized, in seconds)
            resp_time = row.get('response_time_ms', 0) or 0
            resp_time = resp_time / 1000.0  # Convert to seconds
            
            # Request body size (log-scaled)
            body_size = np.log1p(row.get('request_body_size', 0) or 0)
            
            # Is authenticated
            is_auth = float(row.get('is_authenticated', False))
            
            # Combine all features
            features = np.concatenate([
                [ep_id],               # 1 (NOT normalized)
                method_vec,            # 4
                [status],              # 1
                [inter_time],          # 1
                [resp_time],           # 1
                [body_size],           # 1
                [is_auth],             # 1
            ])  # Total: 10
            
            call_features.append(features)
        
        call_features = np.array(call_features, dtype=np.float32)
        
        # If sequence is longer than seq_len, split into chunks
        # If shorter, pad with zeros
        if len(call_features) <= seq_len:
            # Pad
            padded = np.zeros((seq_len, feature_dim), dtype=np.float32)
            padded[:len(call_features)] = call_features
            all_sequences.append(padded)
            all_metadata.append({
                'group_id': group_id,
                'group_by': group_by,
                'original_length': len(call_features),
                'n_requests': len(group_df),
                'traffic_type': traffic_type,
            })
        else:
            # Sliding window over long sessions
            stride = seq_len // 2  # 50% overlap
            for start in range(0, len(call_features) - seq_len + 1, stride):
                chunk = call_features[start:start + seq_len]
                all_sequences.append(chunk)
                all_metadata.append({
                    'group_id': group_id,
                    'group_by': group_by,
                    'original_length': len(call_features),
                    'chunk_start': start,
                    'n_requests': len(group_df),
                    'traffic_type': traffic_type,
                })
    
    if not all_sequences:
        print("WARNING: No sequences built! Check your data.")
        return np.array([]).reshape(0, seq_len, feature_dim), [], vocab
    
    return np.array(all_sequences), all_metadata, vocab


def split_and_save(sequences, metadata, vocab, output_dir, train_ratio=0.8, normal_only_train=True):
    """Split sequences by session_id and save to disk. Normal traffic only in train if requested."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract unique group_ids (session_ids)
    all_group_ids = np.array([m['group_id'] for m in metadata])
    labels = np.array([m.get('traffic_type', 'normal') for m in metadata])
    
    if normal_only_train:
        # Separate normal and attack sessions
        normal_mask = labels == 'normal'
        attack_mask = ~normal_mask
        
        normal_group_ids = np.unique(all_group_ids[normal_mask])
        attack_group_ids = np.unique(all_group_ids[attack_mask])
        
        # Shuffle and split normal sessions
        np.random.shuffle(normal_group_ids)
        n_normal_groups = len(normal_group_ids)
        n_train_groups = int(n_normal_groups * train_ratio)
        
        train_groups = set(normal_group_ids[:n_train_groups])
        val_groups = set(normal_group_ids[n_train_groups:])
        
        # Test groups include val normal and ALL attacks
        # (Though we might want test to be separate, let's keep val for threshold tuning and use it + attacks for test)
        # Actually, let's keep train, val, and test disjoint.
        # So val is val_groups, and test is attack_groups + some normal groups?
        # Let's just follow feature_builder logic: val is for tuning, test includes val normals + all attacks
        
        train_idx = [i for i, gid in enumerate(all_group_ids) if gid in train_groups]
        val_idx = [i for i, gid in enumerate(all_group_ids) if gid in val_groups]
        attack_idx = [i for i, gid in enumerate(all_group_ids) if gid in attack_group_ids]
        
        train_seq = sequences[train_idx]
        val_seq = sequences[val_idx]
        
        test_seq = np.concatenate([sequences[val_idx], sequences[attack_idx]]) if attack_idx else sequences[val_idx]
        test_labels = np.concatenate([np.zeros(len(val_idx)), np.ones(len(attack_idx))]) if attack_idx else np.zeros(len(val_idx))
    else:
        # Simple session split without labels
        unique_groups = np.unique(all_group_ids)
        np.random.shuffle(unique_groups)
        
        n_groups = len(unique_groups)
        n_train = int(n_groups * train_ratio)
        n_val = int(n_groups * 0.1)
        
        train_groups = set(unique_groups[:n_train])
        val_groups = set(unique_groups[n_train:n_train + n_val])
        test_groups = set(unique_groups[n_train + n_val:])
        
        train_idx = [i for i, gid in enumerate(all_group_ids) if gid in train_groups]
        val_idx = [i for i, gid in enumerate(all_group_ids) if gid in val_groups]
        test_idx = [i for i, gid in enumerate(all_group_ids) if gid in test_groups]
        
        train_seq = sequences[train_idx]
        val_seq = sequences[val_idx]
        test_seq = sequences[test_idx]
        test_labels = None
    
    np.save(os.path.join(output_dir, 'train_sequences.npy'), train_seq)
    np.save(os.path.join(output_dir, 'val_sequences.npy'), val_seq)
    np.save(os.path.join(output_dir, 'test_sequences.npy'), test_seq)
    if test_labels is not None:
        np.save(os.path.join(output_dir, 'test_seq_labels.npy'), test_labels)
    
    with open(os.path.join(output_dir, 'endpoint_vocab.pkl'), 'wb') as f:
        pickle.dump(vocab, f)
    
    with open(os.path.join(output_dir, 'sequence_metadata.pkl'), 'wb') as f:
        pickle.dump(metadata, f)
    
    print(f"\n✅ Sequences saved to {output_dir}")
    print(f"   Train: {train_seq.shape}")
    print(f"   Val:   {val_seq.shape}")
    print(f"   Test:  {test_seq.shape}")
    if test_labels is not None:
        print(f"   Test attacks: {int(test_labels.sum())} / {len(test_labels)}")
    print(f"   Seq length: {sequences.shape[1]}, Feature dim: {sequences.shape[2]}")
    print(f"   Vocab size: {len(vocab)}")


def main():
    parser = argparse.ArgumentParser(description='Build API call sequences')
    parser.add_argument('--source', choices=['db', 'csv'], default='db')
    parser.add_argument('--csv-path', type=str, default=None)
    parser.add_argument('--seq-len', type=int, default=30, help='Sequence length')
    parser.add_argument('--group-by', type=str, default='session_id',
                        choices=['session_id', 'user_id', 'ip_address'])
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--train-ratio', type=float, default=0.8)
    
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output is None:
        args.output = os.path.join(script_dir, '..', 'data', 'processed')
    
    print("=" * 60)
    print("Sequence Builder — LSTM Autoencoder Input")
    print("=" * 60)
    
    # Load data
    print("\n📥 Loading request logs...")
    if args.source == 'csv':
        df = load_logs_from_csv(args.csv_path)
    else:
        df = fetch_logs()
    print(f"   Loaded {len(df)} records")
    
    # Build sequences
    print("\n🔧 Building sequences...")
    sequences, metadata, vocab = build_sequences(
        df, seq_len=args.seq_len, group_by=args.group_by
    )
    print(f"   Built {len(sequences)} sequences")
    
    # Save
    print("\n💾 Saving...")
    split_and_save(sequences, metadata, vocab, args.output, args.train_ratio)


if __name__ == '__main__':
    main()

def build_sequence_features(df_group, vocab, max_len=30):
    """Builds a single sequence tensor for inference from a DataFrame of logs."""
    import numpy as np
    
    # Sort by timestamp
    df_group = df_group.sort_values('timestamp')
    
    feature_dim = 10
    call_features = []
    
    for i, (_, row) in enumerate(df_group.iterrows()):
        endpoint = row.get('endpoint', '')
        norm_ep = normalize_endpoint(endpoint)
        ep_id = vocab.get(norm_ep, vocab.get('<UNK>', 0))
        
        method_vec = encode_method(row.get('method', 'GET'))
        status = encode_status(row.get('status_code', 200))
        
        if i > 0:
            prev_time = df_group.iloc[i-1]['timestamp']
            curr_time = row['timestamp']
            inter_time = (curr_time - prev_time).total_seconds()
            inter_time = np.log1p(inter_time)
        else:
            inter_time = 0.0
            
        resp_time = row.get('response_time_ms', 0) or 0
        resp_time = resp_time / 1000.0
        
        body_size = np.log1p(row.get('request_body_size', 0) or 0)
        is_auth = float(row.get('is_authenticated', False))
        
        features = np.concatenate([
            [ep_id], method_vec, [status], [inter_time], [resp_time], [body_size], [is_auth]
        ])
        call_features.append(features)
        
    call_features = np.array(call_features, dtype=np.float32)
    
    # Trim to max_len from the END (most recent requests)
    if len(call_features) > max_len:
        call_features = call_features[-max_len:]
        
    padded = np.zeros((max_len, feature_dim), dtype=np.float32)
    padded[:len(call_features)] = call_features
    return padded
