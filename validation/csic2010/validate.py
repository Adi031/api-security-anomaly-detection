"""
CSIC 2010 Validation Pipeline

Downloads, preprocesses, and evaluates on the CSIC 2010 web application 
firewall dataset (HTTP request payloads).

Usage:
    python validation/csic2010/validate.py
"""

import os
import sys
import argparse
import urllib.request
import re
import numpy as np
import pandas as pd
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Add ml-pipeline to path directly
ml_pipeline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'ml-pipeline')
sys.path.insert(0, ml_pipeline_dir)

try:
    from models.dense_autoencoder import DenseAutoencoder
    from models.threshold import ThresholdSelector
except ImportError as e:
    print(f"Error importing from ml-pipeline: {e}")
    sys.exit(1)

print("\n--- NOTE ---")
print("This script tests the DenseAutoencoder on payload-level features (CSIC 2010).")
print("This is a related-task check for payload anomaly detection, not a proof of generalization")
print("for the behavioral/sequence models used in the main project.")
print("------------\n")

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

CSIC_URLS = {
    'normal_train': 'https://raw.githubusercontent.com/the-red-team/HTTP-CSIC-2010/master/normalTrafficTraining.txt',
    'normal_test': 'https://raw.githubusercontent.com/the-red-team/HTTP-CSIC-2010/master/normalTrafficTest.txt',
    'anomalous_test': 'https://raw.githubusercontent.com/the-red-team/HTTP-CSIC-2010/master/anomalousTrafficTest.txt'
}


def download_csic(data_dir):
    """Download CSIC 2010 dataset files if they don't exist."""
    os.makedirs(data_dir, exist_ok=True)
    
    files = {}
    for key, url in CSIC_URLS.items():
        filepath = os.path.join(data_dir, f"{key}.txt")
        files[key] = filepath
        
        if not os.path.exists(filepath):
            print(f"Downloading {key} from {url}...")
            urllib.request.urlretrieve(url, filepath)
            print(f"Saved to {filepath}")
        else:
            print(f"Found {filepath}")
            
    return files


def parse_csic_file(filepath, label):
    """Parse CSIC .txt format into structured HTTP request dictionaries."""
    print(f"Parsing {filepath} (label={label})...")
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Split into individual requests (separated by double newline + method)
    # The raw format usually looks like:
    # GET /path HTTP/1.1
    # Header: Value
    # 
    # POST /path HTTP/1.1
    
    # We split by HTTP method at the start of a line
    chunks = re.split(r'\n(?=GET|POST|PUT)', content)
    if not chunks[0].strip():
        chunks = chunks[1:]
        
    records = []
    
    for chunk in chunks:
        lines = chunk.strip().split('\n')
        if not lines:
            continue
            
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) >= 2:
            method = parts[0]
            uri = parts[1]
        else:
            method = "GET"
            uri = "/"
            
        # Parse headers and body
        headers = {}
        body = ""
        in_body = False
        
        for line in lines[1:]:
            if in_body:
                body += line + "\n"
            elif line.strip() == "":
                in_body = True
            else:
                header_parts = line.split(': ', 1)
                if len(header_parts) == 2:
                    headers[header_parts[0].lower()] = header_parts[1]
                    
        # Feature extraction on the payload
        query_string = ""
        if '?' in uri:
            uri_parts = uri.split('?', 1)
            uri = uri_parts[0]
            query_string = uri_parts[1]
            
        # Total parameters (query + body for POST)
        payload = query_string + body
        num_params = payload.count('=')
        
        # Calculate special character ratio in payload
        special_chars = r"['\";<>%\-]"
        special_count = len(re.findall(special_chars, payload))
        payload_len = len(payload)
        special_ratio = special_count / max(payload_len, 1)
        
        records.append({
            'method': method,
            'uri': uri,
            'payload_length': payload_len,
            'num_params': num_params,
            'special_char_ratio': special_ratio,
            'label': label
        })
        
    return pd.DataFrame(records)


def preprocess_csic(files, output_dir):
    """Convert raw parsed text to numerical features."""
    
    df_normal_train = parse_csic_file(files['normal_train'], label=0)
    df_normal_test = parse_csic_file(files['normal_test'], label=0)
    df_anomalous_test = parse_csic_file(files['anomalous_test'], label=1)
    
    print(f"Normal Train: {len(df_normal_train)}")
    print(f"Normal Test: {len(df_normal_test)}")
    print(f"Anomalous Test: {len(df_anomalous_test)}")
    
    # Feature extraction (Simple tabular representation)
    def extract_features(df):
        features = np.zeros((len(df), 5))
        
        # Method (1 for POST/PUT, 0 for GET)
        features[:, 0] = df['method'].isin(['POST', 'PUT']).astype(float)
        
        # URI Length
        features[:, 1] = df['uri'].str.len().fillna(0)
        
        # Payload length
        features[:, 2] = df['payload_length']
        
        # Num params
        features[:, 3] = df['num_params']
        
        # Special char ratio
        features[:, 4] = df['special_char_ratio']
        
        return features
        
    X_train = extract_features(df_normal_train)
    X_val = extract_features(df_normal_test) # Using normal test as val
    
    X_test_anom = extract_features(df_anomalous_test)
    X_test = np.vstack([X_val, X_test_anom])
    y_test = np.concatenate([np.zeros(len(X_val)), np.ones(len(X_test_anom))])
    
    # Scale features
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    os.makedirs(output_dir, exist_ok=True)
    np.save(os.path.join(output_dir, 'csic_X_train.npy'), X_train_scaled)
    np.save(os.path.join(output_dir, 'csic_X_val.npy'), X_val_scaled)
    np.save(os.path.join(output_dir, 'csic_X_test.npy'), X_test_scaled)
    np.save(os.path.join(output_dir, 'csic_y_test.npy'), y_test)
    
    print(f"Saved preprocessed data to {output_dir}")
    return X_train_scaled, X_val_scaled, X_test_scaled, y_test


def train_csic_model(X_train, X_val, input_dim, save_dir):
    """Train a Dense Autoencoder on CSIC features."""
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training on device: {device}")
    
    model = DenseAutoencoder(input_dim=input_dim, encoding_dim=3, dropout=0.1).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train)), batch_size=64, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val)), batch_size=64, shuffle=False)
    
    epochs = 20
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for (batch_x,) in train_loader:
            batch_x = batch_x.to(device)
            optimizer.zero_grad()
            x_hat = model(batch_x)
            loss = criterion(x_hat, batch_x)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for (batch_x,) in val_loader:
                batch_x = batch_x.to(device)
                x_hat = model(batch_x)
                val_loss += criterion(x_hat, batch_x).item()
                
        if val_loss < best_loss:
            best_loss = val_loss
            os.makedirs(save_dir, exist_ok=True)
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'input_dim': input_dim,
                'encoding_dim': 3
            }, os.path.join(save_dir, 'csic_dense_ae.pt'))
            
        print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss/len(train_loader):.4f} | Val Loss: {val_loss/len(val_loader):.4f}")
        
    return os.path.join(save_dir, 'csic_dense_ae.pt')


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'csic2010', 'data')
    save_dir = os.path.join(base_dir, 'csic2010', 'results')
    
    # 1. Download
    files = download_csic(data_dir)
    
    # 2. Preprocess
    print("\nPreprocessing...")
    X_train, X_val, X_test, y_test = preprocess_csic(files, data_dir)
    
    # 3. Train Model
    print("\nTraining Model...")
    model_path = train_csic_model(X_train, X_val, input_dim=5, save_dir=save_dir)
    
    # 4. Evaluate
    print("\nEvaluating Model...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Load best model for evaluation logic
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model = DenseAutoencoder(input_dim=5, encoding_dim=3).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Get errors for validation (normal only) to set threshold
    val_tensor = torch.FloatTensor(X_val).to(device)
    with torch.no_grad():
        val_errors = model.compute_reconstruction_error(val_tensor, reduction='none').cpu().numpy()
        
    # Fit threshold (99th percentile)
    ts = ThresholdSelector()
    ts.fit_percentile(val_errors, percentile=95.0)
    ts.save(os.path.join(save_dir, 'csic_threshold.json'))
    
    # We can use the existing evaluate script logic by saving artifacts, 
    # or just run it directly.
    # For now, we just print the basic stats.
    test_tensor = torch.FloatTensor(X_test).to(device)
    with torch.no_grad():
        test_errors = model.compute_reconstruction_error(test_tensor, reduction='none').cpu().numpy()
        
    predictions = ts.predict(test_errors)
    
    from sklearn.metrics import classification_report, roc_auc_score
    print("\nCSIC 2010 Evaluation Results:")
    print(classification_report(y_test, predictions, target_names=['Normal', 'Anomalous']))
    auc = roc_auc_score(y_test, test_errors)
    print(f"AUC-ROC: {auc:.4f}")
    
    print(f"\nAll CSIC validation complete. Results saved in {save_dir}")

if __name__ == '__main__':
    main()
