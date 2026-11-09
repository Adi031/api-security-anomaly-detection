"""
Baseline Models Evaluation Benchmark

Trains Isolation Forest, One-Class SVM, and Rate Limiter strictly on normal
training data and benchmarks them against the trained Dense Autoencoder
on the exact same held-out test split.
"""

import os
import sys
import time
import json
import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from models.dense_autoencoder import DenseAutoencoder

DATA_DIR = os.path.join(BASE_DIR, 'data', 'processed')
SAVED_DIR = os.path.join(BASE_DIR, 'saved_models')

# 1. Load Data (Features are already standardized and clipped in feature_builder.py)
print("Loading data...")
X_train = np.load(os.path.join(DATA_DIR, 'train_features.npy'))
X_val = np.load(os.path.join(DATA_DIR, 'val_features.npy'))
X_test = np.load(os.path.join(DATA_DIR, 'test_features.npy'))
y_test = np.load(os.path.join(DATA_DIR, 'test_labels.npy')).astype(int)

print(f"Train (normal): {X_train.shape[0]} sessions")
print(f"Val (normal):   {X_val.shape[0]} sessions")
print(f"Test:           {X_test.shape[0]} sessions ({np.sum(y_test == 0)} normal, {np.sum(y_test == 1)} attacks)\n")

results = []

def evaluate_predictions(name, model_type, scores, preds, y_true, latency_ms):
    tn, fp, fn, tp = confusion_matrix(y_true, preds).ravel()
    prec = precision_score(y_true, preds, zero_division=0)
    rec = recall_score(y_true, preds, zero_division=0)
    f1 = f1_score(y_true, preds, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    auc = roc_auc_score(y_true, scores)
    
    return {
        "model": name,
        "type": model_type,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "fpr": fpr,
        "roc_auc": auc,
        "latency_ms": latency_ms
    }

# ============================================================
# Baseline 1: Heuristic Rate Limiter
# ============================================================
print("Evaluating Baseline 1: Static Rate Limiter...")
t0 = time.perf_counter()
# Standard Gateway rule on scaled features: feature 0 (request_count) or feature 6 (failed_auth_ratio) or feature 7 (error_ratio)
# In standardized space, > 1.5 standard deviations indicates extreme burst / error
rl_scores = (X_test[:, 0] + X_test[:, 6] * 2.0 + X_test[:, 7] * 2.0)
rl_preds = ((X_test[:, 6] > 1.0) | (X_test[:, 7] > 1.0) | (X_test[:, 0] > 1.5)).astype(int)
rl_latency = ((time.perf_counter() - t0) / len(X_test)) * 1000

res_rl = evaluate_predictions("Static Rate Limiter", "Heuristic Rules", rl_scores, rl_preds, y_test, rl_latency)
results.append(res_rl)

# ============================================================
# Baseline 2: Isolation Forest
# ============================================================
print("Training Baseline 2: Isolation Forest...")
iso = IsolationForest(n_estimators=100, random_state=42, contamination='auto', n_jobs=-1)
iso.fit(X_train)

t0 = time.perf_counter()
iso_val_scores = -iso.score_samples(X_val)
iso_test_scores = -iso.score_samples(X_test)
iso_latency = ((time.perf_counter() - t0) / len(X_test)) * 1000

# 95th percentile threshold on normal validation data
iso_threshold = np.percentile(iso_val_scores, 95)
iso_preds = (iso_test_scores >= iso_threshold).astype(int)

res_iso = evaluate_predictions("Isolation Forest", "Tree-based ML", iso_test_scores, iso_preds, y_test, iso_latency)
results.append(res_iso)

# ============================================================
# Baseline 3: One-Class SVM
# ============================================================
print("Training Baseline 3: One-Class SVM...")
ocsvm = OneClassSVM(kernel='rbf', gamma='scale', nu=0.05)
ocsvm.fit(X_train)

t0 = time.perf_counter()
ocsvm_val_scores = -ocsvm.decision_function(X_val)
ocsvm_test_scores = -ocsvm.decision_function(X_test)
ocsvm_latency = ((time.perf_counter() - t0) / len(X_test)) * 1000

ocsvm_threshold = np.percentile(ocsvm_val_scores, 95)
ocsvm_preds = (ocsvm_test_scores >= ocsvm_threshold).astype(int)

res_ocsvm = evaluate_predictions("One-Class SVM", "Kernel ML", ocsvm_test_scores, ocsvm_preds, y_test, ocsvm_latency)
results.append(res_ocsvm)

# ============================================================
# Proposed Model: Dense Autoencoder (Sentinel-v2)
# ============================================================
print("Evaluating Proposed Model: Dense Autoencoder...")
ckpt = torch.load(os.path.join(SAVED_DIR, 'dense_ae_best.pt'), map_location='cpu', weights_only=False)
model = DenseAutoencoder(
    input_dim=ckpt['input_dim'],
    encoding_dim=ckpt['encoding_dim'],
    dropout=ckpt.get('dropout', 0.2)
)
model.load_state_dict(ckpt['model_state_dict'])
model.eval()

with open(os.path.join(SAVED_DIR, 'threshold.json')) as f:
    ae_meta = json.load(f)
ae_threshold = ae_meta['threshold']

X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
t0 = time.perf_counter()
with torch.no_grad():
    ae_errors = model.compute_reconstruction_error(X_test_tensor, reduction='none').numpy()
ae_latency = ((time.perf_counter() - t0) / len(X_test)) * 1000

ae_preds = (ae_errors >= ae_threshold).astype(int)
res_ae = evaluate_predictions("Dense Autoencoder (Ours)", "Deep Learning", ae_errors, ae_preds, y_test, ae_latency)
results.append(res_ae)

# ============================================================
# Print Comparison Table
# ============================================================
print("\n" + "=" * 90)
print("BASELINE COMPARISON BENCHMARK ON HELD-OUT TEST DATA")
print("=" * 90)
header = f"{'Model':<26} | {'Type':<16} | {'Precision':<9} | {'Recall':<8} | {'F1-Score':<8} | {'FPR':<6} | {'ROC-AUC':<8} | {'Latency'}"
print(header)
print("-" * 90)

for r in results:
    row = (
        f"{r['model']:<26} | {r['type']:<16} | "
        f"{r['precision']*100:>8.2f}% | {r['recall']*100:>7.2f}% | "
        f"{r['f1']*100:>7.2f}% | {r['fpr']*100:>5.2f}% | "
        f"{r['roc_auc']:>8.4f} | {r['latency_ms']:>5.2f} ms"
    )
    print(row)
print("=" * 90)

# Save results JSON
out_path = os.path.join(SAVED_DIR, 'evaluation', 'baseline_comparison.json')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved benchmark results to {out_path}")
