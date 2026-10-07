import os
import json
import torch
import numpy as np

from models.dense_autoencoder import DenseAutoencoder
from models.lstm_autoencoder import LSTMAutoencoder
import pickle

data_dir = os.path.join(os.path.dirname(__file__), "data", "processed")
models_dir = os.path.join(os.path.dirname(__file__), "saved_models")

# --- 1. Load Test Data ---
print("Loading pre-built test sets...")
try:
    dense_test_x = np.load(os.path.join(data_dir, "test_features.npy"))
    dense_test_y = np.load(os.path.join(data_dir, "test_labels.npy"))
except FileNotFoundError:
    print("Could not find Dense model test data. You must run features/feature_builder.py first.")
    exit(1)

lstm_test_x = np.load(os.path.join(data_dir, "test_sequences.npy"))
lstm_test_y = np.load(os.path.join(data_dir, "test_seq_labels.npy"))

# --- 2. Load Models & Thresholds ---
print("Loading Models...")
dense_ckpt = torch.load(os.path.join(models_dir, "dense_ae_best.pt"), weights_only=False)
dense_model = DenseAutoencoder(input_dim=14, encoding_dim=6)
dense_model.load_state_dict(dense_ckpt['model_state_dict'])
dense_model.eval()

with open(os.path.join(models_dir, "threshold.json"), "r") as f:
    dense_threshold = json.load(f)["threshold"]

with open(os.path.join(data_dir, "endpoint_vocab.pkl"), "rb") as f:
    vocab = pickle.load(f)

lstm_ckpt = torch.load(os.path.join(models_dir, "lstm_ae_best.pt"), weights_only=False)
lstm_model = LSTMAutoencoder(vocab_size=len(vocab), seq_len=30, input_dim=10)
lstm_model.load_state_dict(lstm_ckpt['model_state_dict'])
lstm_model.eval()

with open(os.path.join(models_dir, "lstm_threshold.json"), "r") as f:
    lstm_threshold = json.load(f)["threshold"]

# --- 3. Evaluate Dense Autoencoder ---
dense_tensor = torch.tensor(dense_test_x, dtype=torch.float32)
with torch.no_grad():
    dense_recon = dense_model(dense_tensor)
    dense_mse = torch.mean((dense_tensor - dense_recon) ** 2, dim=1).numpy()
    
dense_preds = (dense_mse >= dense_threshold).astype(int)

# --- 4. Evaluate LSTM Autoencoder ---
lstm_tensor = torch.tensor(lstm_test_x, dtype=torch.float32)
with torch.no_grad():
    lstm_mse = lstm_model.compute_reconstruction_error(lstm_tensor, reduction='none').numpy()

lstm_preds = (lstm_mse >= lstm_threshold).astype(int)

# --- 5. Print and Save Results ---
results_path = os.path.join(os.path.dirname(__file__), "evaluation_results.txt")

def print_metrics(model_name, y_true, y_pred, y_scores, f_out):
    output = []
    output.append(f"\n=========================================")
    output.append(f"Results for {model_name}")
    output.append(f"=========================================")
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
    roc_auc = roc_auc_score(y_true, y_scores)
    cm = confusion_matrix(y_true, y_pred)
    
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    output.append(f"Recall (Detection Rate): {r:.2%}")
    output.append(f"Precision:               {p:.2%}")
    output.append(f"F1-Score:                {f1:.2%}")
    output.append(f"ROC-AUC:                 {roc_auc:.4f}")
    output.append(f"False Positive Rate:     {fpr:.2%} (Should be low!)")
    output.append(f"True Negatives: {tn} | False Positives: {fp}")
    output.append(f"False Negatives: {fn} | True Positives: {tp}")
    
    text = "\n".join(output)
    print(text)
    f_out.write(text + "\n")

with open(results_path, "w") as f_out:
    print_metrics("Dense Autoencoder", dense_test_y, dense_preds, dense_mse, f_out)
    print_metrics("LSTM Autoencoder", lstm_test_y, lstm_preds, lstm_mse, f_out)
    print(f"\nEvaluation Complete! Results saved to {results_path}")
