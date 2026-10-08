"""
Evaluation Script for Anomaly Detection Models

Evaluates trained models on test data with comprehensive metrics:
- Precision, Recall, F1-Score (per-attack-type and overall)
- ROC curve and AUC-ROC
- Precision-Recall curve and AUC-PR
- Confusion matrix
- Reconstruction error distribution analysis

Usage:
    python training/evaluate.py --model dense_ae --data-dir data/processed/ --model-path saved_models/
"""

import os
import sys
import argparse
import numpy as np
import torch
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_curve, auc, precision_recall_curve, average_precision_score,
    confusion_matrix, classification_report
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.dense_autoencoder import DenseAutoencoder
from models.lstm_autoencoder import LSTMAutoencoder
from models.threshold import ThresholdSelector


# Plot styling
PLOT_STYLE = {
    'bg_color': '#0a0e17',
    'text_color': '#e2e8f0',
    'grid_alpha': 0.3,
    'cyan': '#00d4ff',
    'green': '#22c55e',
    'red': '#ef4444',
    'amber': '#fbbf24',
    'purple': '#7c3aed',
}


def style_axis(ax, title=''):
    """Apply consistent dark styling to a matplotlib axis."""
    ax.set_facecolor(PLOT_STYLE['bg_color'])
    ax.tick_params(colors=PLOT_STYLE['text_color'])
    ax.xaxis.label.set_color(PLOT_STYLE['text_color'])
    ax.yaxis.label.set_color(PLOT_STYLE['text_color'])
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', color=PLOT_STYLE['text_color'])
    ax.grid(True, alpha=PLOT_STYLE['grid_alpha'])


def load_model(model_path, model_type='dense_ae', device='cpu'):
    """Load trained model from checkpoint."""
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    if model_type == 'dense_ae':
        use_bn = checkpoint.get('use_batchnorm', False)
        ModelClass = DenseAutoencoderWithBatchNorm if use_bn else DenseAutoencoder
        model = ModelClass(
            input_dim=checkpoint['input_dim'],
            encoding_dim=checkpoint['encoding_dim'],
            dropout=checkpoint.get('dropout', 0.2)
        )
    elif model_type == 'lstm_ae':
        model = LSTMAutoencoder(
            vocab_size=checkpoint.get('vocab_size', 9),
            input_dim=checkpoint['input_dim'],
            seq_len=checkpoint['seq_len'],
            encoder_hidden=checkpoint.get('encoder_hidden', (128, 64)),
            decoder_hidden=checkpoint.get('decoder_hidden', (64, 128)),
            dropout=checkpoint.get('dropout', 0.2)
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    print(f"  ✅ Model loaded: {model_type} (epoch {checkpoint['epoch']})")
    return model


def get_errors(model, data, device, batch_size=256):
    """Compute per-sample reconstruction errors."""
    model.eval()
    tensor = torch.FloatTensor(data)
    
    all_errors = []
    for i in range(0, len(tensor), batch_size):
        batch = tensor[i:i+batch_size].to(device)
        errors = model.compute_reconstruction_error(batch, reduction='none')
        all_errors.append(errors.detach().cpu().numpy())
    
    return np.concatenate(all_errors)


def plot_roc_curve(labels, scores, save_path):
    """Plot and save ROC curve."""
    fpr, tpr, _ = roc_curve(labels, scores)
    roc_auc = auc(fpr, tpr)
    
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(fpr, tpr, color=PLOT_STYLE['cyan'], linewidth=2, 
            label=f'ROC Curve (AUC = {roc_auc:.4f})')
    ax.plot([0, 1], [0, 1], color=PLOT_STYLE['text_color'], linestyle='--', alpha=0.5)
    ax.set_xlabel('False Positive Rate', fontsize=12)
    ax.set_ylabel('True Positive Rate', fontsize=12)
    style_axis(ax, 'ROC Curve')
    ax.legend(fontsize=12, facecolor=PLOT_STYLE['bg_color'], edgecolor=PLOT_STYLE['text_color'],
              labelcolor=PLOT_STYLE['text_color'])
    fig.set_facecolor(PLOT_STYLE['bg_color'])
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=PLOT_STYLE['bg_color'])
    plt.close()
    
    return roc_auc


def plot_precision_recall_curve(labels, scores, save_path):
    """Plot and save Precision-Recall curve."""
    precision, recall, _ = precision_recall_curve(labels, scores)
    ap = average_precision_score(labels, scores)
    
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(recall, precision, color=PLOT_STYLE['amber'], linewidth=2,
            label=f'PR Curve (AP = {ap:.4f})')
    ax.set_xlabel('Recall', fontsize=12)
    ax.set_ylabel('Precision', fontsize=12)
    style_axis(ax, 'Precision-Recall Curve')
    ax.legend(fontsize=12, facecolor=PLOT_STYLE['bg_color'], edgecolor=PLOT_STYLE['text_color'],
              labelcolor=PLOT_STYLE['text_color'])
    fig.set_facecolor(PLOT_STYLE['bg_color'])
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=PLOT_STYLE['bg_color'])
    plt.close()
    
    return ap


def plot_confusion_matrix(labels, predictions, save_path):
    """Plot and save confusion matrix."""
    cm = confusion_matrix(labels, predictions)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    
    # Labels
    classes = ['Normal', 'Attack']
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(classes, fontsize=12)
    ax.set_yticklabels(classes, fontsize=12)
    ax.set_xlabel('Predicted', fontsize=12)
    ax.set_ylabel('Actual', fontsize=12)
    
    # Text annotations
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    fontsize=16, fontweight='bold',
                    color='white' if cm[i, j] > cm.max() / 2 else 'black')
    
    style_axis(ax, 'Confusion Matrix')
    fig.set_facecolor(PLOT_STYLE['bg_color'])
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=PLOT_STYLE['bg_color'])
    plt.close()


def plot_error_histogram(normal_errors, attack_errors, threshold, save_path):
    """Plot reconstruction error histogram for normal vs attack."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.hist(normal_errors, bins=60, alpha=0.7, color=PLOT_STYLE['green'], 
            label=f'Normal (n={len(normal_errors)})', density=True)
    ax.hist(attack_errors, bins=60, alpha=0.7, color=PLOT_STYLE['red'],
            label=f'Attack (n={len(attack_errors)})', density=True)
    ax.axvline(x=threshold, color=PLOT_STYLE['amber'], linestyle='--', linewidth=2,
               label=f'Threshold ({threshold:.4f})')
    
    ax.set_xlabel('Reconstruction Error (MSE)', fontsize=12)
    ax.set_ylabel('Density', fontsize=12)
    style_axis(ax, 'Reconstruction Error Distribution')
    ax.legend(fontsize=11, facecolor=PLOT_STYLE['bg_color'], edgecolor=PLOT_STYLE['text_color'],
              labelcolor=PLOT_STYLE['text_color'])
    fig.set_facecolor(PLOT_STYLE['bg_color'])
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=PLOT_STYLE['bg_color'])
    plt.close()


def evaluate_model(model, test_data, test_labels, threshold_selector, device, 
                   output_dir, model_name='model'):
    """Full evaluation pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'=' * 60}")
    print(f"Evaluating: {model_name}")
    print(f"{'=' * 60}")
    
    # Get errors
    print("\n📊 Computing reconstruction errors...")
    errors = get_errors(model, test_data, device)
    
    normal_mask = test_labels == 0
    attack_mask = test_labels == 1
    normal_errors = errors[normal_mask]
    attack_errors = errors[attack_mask]
    
    print(f"  Normal errors — mean: {normal_errors.mean():.6f}, std: {normal_errors.std():.6f}")
    print(f"  Attack errors — mean: {attack_errors.mean():.6f}, std: {attack_errors.std():.6f}")
    print(f"  Separation ratio: {attack_errors.mean() / max(normal_errors.mean(), 1e-8):.2f}x")
    
    # Predictions
    threshold = threshold_selector.threshold
    predictions = (errors > threshold).astype(int)
    
    # Metrics
    print(f"\n📋 Classification Metrics (threshold={threshold:.6f}):")
    precision = precision_score(test_labels, predictions, zero_division=0)
    recall = recall_score(test_labels, predictions, zero_division=0)
    f1 = f1_score(test_labels, predictions, zero_division=0)
    
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1-Score:  {f1:.4f}")
    
    # Detailed report
    print(f"\n  Classification Report:")
    report = classification_report(test_labels, predictions, 
                                    target_names=['Normal', 'Attack'],
                                    zero_division=0)
    print(report)
    
    # ROC and PR curves
    print("📊 Generating plots...")
    roc_auc = plot_roc_curve(test_labels, errors, 
                              os.path.join(output_dir, f'{model_name}_roc.png'))
    print(f"  AUC-ROC: {roc_auc:.4f}")
    
    ap = plot_precision_recall_curve(test_labels, errors,
                                      os.path.join(output_dir, f'{model_name}_pr.png'))
    print(f"  AUC-PR:  {ap:.4f}")
    
    plot_confusion_matrix(test_labels, predictions,
                          os.path.join(output_dir, f'{model_name}_confusion.png'))
    
    plot_error_histogram(normal_errors, attack_errors, threshold,
                         os.path.join(output_dir, f'{model_name}_errors.png'))
    
    # FPR at various thresholds
    print(f"\n📊 False Positive Rate at Various Thresholds:")
    for mult in [0.5, 1.0, 1.5, 2.0, 3.0]:
        t = threshold * mult
        fp = np.sum(normal_errors > t)
        fpr_val = fp / len(normal_errors)
        tp = np.sum(attack_errors > t)
        tpr_val = tp / len(attack_errors)
        print(f"  {mult:.1f}×τ = {t:.4f} → FPR: {fpr_val:.4f}, TPR: {tpr_val:.4f}")
    
    # Save results
    results = {
        'model_name': model_name,
        'threshold': float(threshold),
        'threshold_method': threshold_selector.method,
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'auc_roc': float(roc_auc),
        'auc_pr': float(ap),
        'n_normal_test': int(normal_mask.sum()),
        'n_attack_test': int(attack_mask.sum()),
        'normal_error_mean': float(normal_errors.mean()),
        'normal_error_std': float(normal_errors.std()),
        'attack_error_mean': float(attack_errors.mean()),
        'attack_error_std': float(attack_errors.std()),
        'separation_ratio': float(attack_errors.mean() / max(normal_errors.mean(), 1e-8)),
    }
    
    with open(os.path.join(output_dir, f'{model_name}_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n  ✅ Results saved to {output_dir}")
    return results


def main():
    parser = argparse.ArgumentParser(description='Evaluate Anomaly Detection Model')
    parser.add_argument('--model', type=str, default='dense_ae',
                        choices=['dense_ae', 'lstm_ae'],
                        help='Model type to evaluate')
    parser.add_argument('--data-dir', type=str, default=None)
    parser.add_argument('--model-path', type=str, default=None)
    parser.add_argument('--threshold-path', type=str, default=None)
    parser.add_argument('--output-dir', type=str, default=None)
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if args.data_dir is None:
        args.data_dir = os.path.join(base_dir, 'data', 'processed')
    if args.model_path is None:
        model_file = 'dense_ae_best.pt' if args.model == 'dense_ae' else 'lstm_ae_best.pt'
        args.model_path = os.path.join(base_dir, 'saved_models', model_file)
    if args.threshold_path is None:
        args.threshold_path = os.path.join(base_dir, 'saved_models', 'threshold.json')
    if args.output_dir is None:
        args.output_dir = os.path.join(base_dir, 'saved_models', 'evaluation')
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Load data
    print("📥 Loading test data...")
    if args.model == 'lstm_ae':
        test_data = np.load(os.path.join(args.data_dir, 'test_sequences.npy'))
        test_labels = np.load(os.path.join(args.data_dir, 'test_seq_labels.npy'))
    else:
        test_data = np.load(os.path.join(args.data_dir, 'test_features.npy'))
        test_labels = np.load(os.path.join(args.data_dir, 'test_labels.npy'))
    print(f"  Test samples: {len(test_data)} (attacks: {int(test_labels.sum())})")
    
    # Load model
    print("\n🏗️  Loading model...")
    model = load_model(args.model_path, args.model, device)
    
    # Load threshold
    print("\n🎯 Loading threshold...")
    threshold_selector = ThresholdSelector()
    threshold_selector.load(args.threshold_path)
    
    # Evaluate
    results = evaluate_model(
        model, test_data, test_labels, threshold_selector,
        device, args.output_dir, model_name=args.model
    )
    
    print(f"\n{'=' * 60}")
    print("Evaluation Complete!")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
