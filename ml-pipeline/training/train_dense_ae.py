"""
Training Script for Dense Autoencoder (Stage 1 — Baseline)

Trains the dense autoencoder on normal traffic features only.
Anomalous traffic is never seen during training — the model learns
to reconstruct normal patterns, and fails on anomalies.

Usage:
    python training/train_dense_ae.py [--epochs 100] [--batch-size 64] [--lr 0.001]
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.dense_autoencoder import DenseAutoencoder, count_parameters
from models.threshold import ThresholdSelector, compare_thresholds


def load_data(data_dir):
    """Load preprocessed feature data."""
    train = np.load(os.path.join(data_dir, 'train_features.npy'))
    val = np.load(os.path.join(data_dir, 'val_features.npy'))
    
    test_path = os.path.join(data_dir, 'test_features.npy')
    test = np.load(test_path) if os.path.exists(test_path) else None
    
    labels_path = os.path.join(data_dir, 'test_labels.npy')
    test_labels = np.load(labels_path) if os.path.exists(labels_path) else None
    
    print(f"  Train: {train.shape}")
    print(f"  Val:   {val.shape}")
    if test is not None:
        print(f"  Test:  {test.shape}")
    if test_labels is not None:
        print(f"  Test labels: {test_labels.shape} (attacks: {int(test_labels.sum())})")
    
    return train, val, test, test_labels


def create_dataloaders(train_data, val_data, batch_size=64):
    """Create PyTorch DataLoaders."""
    train_tensor = torch.FloatTensor(train_data)
    val_tensor = torch.FloatTensor(val_data)
    
    train_dataset = TensorDataset(train_tensor, train_tensor)  # Input = target for AE
    val_dataset = TensorDataset(val_tensor, val_tensor)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader


def train_epoch(model, train_loader, optimizer, criterion, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    n_batches = 0
    
    for batch_x, _ in train_loader:
        batch_x = batch_x.to(device)
        
        # Forward
        x_hat = model(batch_x)
        loss = criterion(x_hat, batch_x)
        
        # Backward
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        n_batches += 1
    
    return total_loss / n_batches


def validate(model, val_loader, criterion, device):
    """Validate and return loss."""
    model.eval()
    total_loss = 0.0
    n_batches = 0
    
    with torch.no_grad():
        for batch_x, _ in val_loader:
            batch_x = batch_x.to(device)
            x_hat = model(batch_x)
            loss = criterion(x_hat, batch_x)
            total_loss += loss.item()
            n_batches += 1
    
    return total_loss / n_batches


def get_reconstruction_errors(model, data, device, batch_size=256):
    """Get per-sample reconstruction errors."""
    model.eval()
    tensor = torch.FloatTensor(data)
    loader = DataLoader(TensorDataset(tensor), batch_size=batch_size, shuffle=False)
    
    all_errors = []
    with torch.no_grad():
        for (batch_x,) in loader:
            batch_x = batch_x.to(device)
            errors = model.compute_reconstruction_error(batch_x, reduction='none')
            all_errors.append(errors.cpu().numpy())
    
    return np.concatenate(all_errors)


def plot_training_curves(train_losses, val_losses, save_path):
    """Plot and save training/validation loss curves."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    
    ax.plot(train_losses, label='Train Loss', color='#00d4ff', linewidth=2)
    ax.plot(val_losses, label='Val Loss', color='#fbbf24', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('MSE Loss', fontsize=12)
    ax.set_title('Dense Autoencoder Training', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#0a0e17')
    fig.set_facecolor('#0a0e17')
    ax.tick_params(colors='#e2e8f0')
    ax.xaxis.label.set_color('#e2e8f0')
    ax.yaxis.label.set_color('#e2e8f0')
    ax.title.set_color('#e2e8f0')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
    plt.close()
    print(f"  📊 Training curves saved to {save_path}")


def plot_error_distribution(normal_errors, attack_errors, threshold, save_path):
    """Plot reconstruction error distribution for normal vs attack."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    
    ax.hist(normal_errors, bins=50, alpha=0.7, color='#22c55e', label='Normal', density=True)
    if attack_errors is not None and len(attack_errors) > 0:
        ax.hist(attack_errors, bins=50, alpha=0.7, color='#ef4444', label='Attack', density=True)
    
    ax.axvline(x=threshold, color='#fbbf24', linestyle='--', linewidth=2, label=f'Threshold ({threshold:.4f})')
    
    ax.set_xlabel('Reconstruction Error (MSE)', fontsize=12)
    ax.set_ylabel('Density', fontsize=12)
    ax.set_title('Reconstruction Error Distribution', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#0a0e17')
    fig.set_facecolor('#0a0e17')
    ax.tick_params(colors='#e2e8f0')
    ax.xaxis.label.set_color('#e2e8f0')
    ax.yaxis.label.set_color('#e2e8f0')
    ax.title.set_color('#e2e8f0')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
    plt.close()
    print(f"  📊 Error distribution saved to {save_path}")


def main():
    parser = argparse.ArgumentParser(description='Train Dense Autoencoder')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory with preprocessed features')
    parser.add_argument('--save-dir', type=str, default=None,
                        help='Directory to save model and artifacts')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Max training epochs (default: 100)')
    parser.add_argument('--batch-size', type=int, default=64,
                        help='Batch size (default: 64)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='Learning rate (default: 0.001)')
    parser.add_argument('--encoding-dim', type=int, default=6,
                        help='Bottleneck dimension (default: 6)')
    parser.add_argument('--dropout', type=float, default=0.2,
                        help='Dropout rate (default: 0.2)')
    parser.add_argument('--patience', type=int, default=10,
                        help='Early stopping patience (default: 10)')
    parser.add_argument('--smoke-test', action='store_true',
                        help='Quick smoke test with minimal epochs')
    
    args = parser.parse_args()
    
    # Defaults
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    
    if args.data_dir is None:
        args.data_dir = os.path.join(base_dir, 'data', 'processed')
    if args.save_dir is None:
        args.save_dir = os.path.join(base_dir, 'saved_models')
    
    if args.smoke_test:
        args.epochs = 5
        args.patience = 3
    
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    print("=" * 60)
    print("Dense Autoencoder Training")
    print("=" * 60)
    print(f"  Device:       {device}")
    print(f"  Data dir:     {args.data_dir}")
    print(f"  Save dir:     {args.save_dir}")
    print(f"  Epochs:       {args.epochs}")
    print(f"  Batch size:   {args.batch_size}")
    print(f"  LR:           {args.lr}")
    print(f"  Encoding dim: {args.encoding_dim}")
    print(f"  Dropout:      {args.dropout}")
    print(f"  Patience:     {args.patience}")
    print("=" * 60)
    
    # Load data
    print("\n📥 Loading data...")
    train_data, val_data, test_data, test_labels = load_data(args.data_dir)
    input_dim = train_data.shape[1]
    
    # Create model
    print(f"\n🏗️  Building model (input_dim={input_dim})...")
    model = DenseAutoencoder(
        input_dim=input_dim, encoding_dim=args.encoding_dim, dropout=args.dropout
    )
    
    model = model.to(device)
    print(f"  Parameters: {count_parameters(model):,}")
    
    # Training setup
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    
    train_loader, val_loader = create_dataloaders(train_data, val_data, args.batch_size)
    
    # Training loop
    print(f"\n🚀 Training...")
    train_losses = []
    val_losses = []
    best_val_loss = float('inf')
    patience_counter = 0
    best_epoch = 0
    
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss = validate(model, val_loader, criterion, device)
        
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        
        scheduler.step(val_loss)
        
        # Early stopping check
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_epoch = epoch
            # Save best model
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss': train_loss,
                'val_loss': val_loss,
                'input_dim': input_dim,
                'encoding_dim': args.encoding_dim,
                'dropout': args.dropout,
            }, os.path.join(args.save_dir, 'dense_ae_best.pt'))
        else:
            patience_counter += 1
        
        if epoch % 5 == 0 or epoch == 1 or patience_counter == 0:
            marker = " ✓ best" if patience_counter == 0 else ""
            print(f"  Epoch {epoch:3d}/{args.epochs} | "
                  f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                  f"LR: {optimizer.param_groups[0]['lr']:.6f}{marker}")
        
        if patience_counter >= args.patience:
            print(f"\n  ⏹️  Early stopping at epoch {epoch} (best: epoch {best_epoch})")
            break
    
    # Load best model
    checkpoint = torch.load(os.path.join(args.save_dir, 'dense_ae_best.pt'), weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"\n  ✅ Best model loaded (epoch {checkpoint['epoch']}, val_loss={checkpoint['val_loss']:.6f})")
    
    # Compute reconstruction errors on validation set
    print("\n📊 Computing reconstruction errors...")
    val_errors = get_reconstruction_errors(model, val_data, device)
    print(f"  Val errors — mean: {val_errors.mean():.6f}, std: {val_errors.std():.6f}, "
          f"max: {val_errors.max():.6f}")
    
    # Compute threshold
    print("\n🎯 Selecting threshold...")
    threshold_selector = ThresholdSelector()
    
    if test_data is not None and test_labels is not None:
        test_errors = get_reconstruction_errors(model, test_data, device)
        normal_test_errors = test_errors[test_labels == 0]
        attack_test_errors = test_errors[test_labels == 1]
        
        # Use 99th percentile on validation data
        threshold_selector.fit_percentile(val_errors, 99.0)
        
        # Also compute comparison
        print("\n  Threshold comparison:")
        results = compare_thresholds(val_errors, attack_test_errors)
        for method, stats in results.items():
            print(f"    {method}: τ={stats['threshold']:.6f}")
        
        # Plot error distribution
        plot_error_distribution(
            normal_test_errors, attack_test_errors,
            threshold_selector.threshold,
            os.path.join(args.save_dir, 'error_distribution.png')
        )
    else:
        # No labeled data — use 99th percentile
        threshold_selector.fit_percentile(val_errors, 99.0)
    
    threshold_selector.summary()
    threshold_selector.save(os.path.join(args.save_dir, 'threshold.json'))
    
    # Plot training curves
    plot_training_curves(
        train_losses, val_losses,
        os.path.join(args.save_dir, 'training_curves.png')
    )
    
    # Final summary
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"  Best epoch:     {checkpoint['epoch']}")
    print(f"  Best val loss:  {checkpoint['val_loss']:.6f}")
    print(f"  Threshold:      {threshold_selector.threshold:.6f} ({threshold_selector.method})")
    print(f"  Model saved:    {os.path.join(args.save_dir, 'dense_ae_best.pt')}")
    print(f"  Threshold:      {os.path.join(args.save_dir, 'threshold.json')}")
    print("=" * 60)


if __name__ == '__main__':
    main()
