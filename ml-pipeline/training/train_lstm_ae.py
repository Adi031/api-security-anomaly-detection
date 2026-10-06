"""
Training Script for LSTM Autoencoder (Stage 2 — Stretch Goal)

Trains the LSTM autoencoder on normal API call sequences.
Models the order and timing of API calls per session.

Usage:
    python training/train_lstm_ae.py [--epochs 50] [--batch-size 64] [--seq-len 30]
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.lstm_autoencoder import LSTMAutoencoder, count_parameters
from models.threshold import ThresholdSelector


def load_data(data_dir):
    """Load preprocessed sequence data."""
    train = np.load(os.path.join(data_dir, 'train_sequences.npy'))
    val = np.load(os.path.join(data_dir, 'val_sequences.npy'))
    
    test_path = os.path.join(data_dir, 'test_sequences.npy')
    test = np.load(test_path) if os.path.exists(test_path) else None
    
    labels_path = os.path.join(data_dir, 'test_seq_labels.npy')
    test_labels = np.load(labels_path) if os.path.exists(labels_path) else None
    
    with open(os.path.join(data_dir, 'endpoint_vocab.pkl'), 'rb') as f:
        vocab = pickle.load(f)
    
    print(f"  Train: {train.shape}")
    print(f"  Val:   {val.shape}")
    if test is not None:
        print(f"  Test:  {test.shape}")
    print(f"  Vocab size: {len(vocab)}")
    
    return train, val, test, test_labels, len(vocab)


def train_epoch(model, train_loader, optimizer, criterion, device, clip_grad=1.0):
    """Train for one epoch with gradient clipping."""
    model.train()
    total_loss = 0.0
    n_batches = 0
    
    for batch_x, _ in train_loader:
        batch_x = batch_x.to(device)
        
        # Forward and compute loss with padding mask
        loss = model.compute_reconstruction_error(batch_x, reduction='mean')
        
        optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping — critical for LSTM stability
        torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad)
        
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
            loss = model.compute_reconstruction_error(batch_x, reduction='mean')
            total_loss += loss.item()
            n_batches += 1
    
    return total_loss / n_batches


def get_errors(model, data, device, batch_size=128):
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


def plot_curves(train_losses, val_losses, save_path):
    """Plot training curves."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(train_losses, label='Train Loss', color='#00d4ff', linewidth=2)
    ax.plot(val_losses, label='Val Loss', color='#fbbf24', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('MSE Loss', fontsize=12)
    ax.set_title('LSTM Autoencoder Training', fontsize=14, fontweight='bold')
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


def main():
    parser = argparse.ArgumentParser(description='Train LSTM Autoencoder')
    parser.add_argument('--data-dir', type=str, default=None)
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--dropout', type=float, default=0.2)
    parser.add_argument('--clip-grad', type=float, default=1.0)
    parser.add_argument('--patience', type=int, default=5)
    parser.add_argument('--smoke-test', action='store_true')
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.data_dir is None:
        args.data_dir = os.path.join(base_dir, 'data', 'processed')
    if args.save_dir is None:
        args.save_dir = os.path.join(base_dir, 'saved_models')
    
    if args.smoke_test:
        args.epochs = 5
        args.patience = 3
    
    os.makedirs(args.save_dir, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    print("=" * 60)
    print("LSTM Autoencoder Training")
    print("=" * 60)
    print(f"  Device:        {device}")
    print(f"  Epochs:        {args.epochs}")
    print(f"  Batch size:    {args.batch_size}")
    print(f"  LR:            {args.lr}")
    print(f"  Gradient clip: {args.clip_grad}")
    print("=" * 60)
    
    # Load data
    print("\n📥 Loading sequence data...")
    train_data, val_data, test_data, test_labels, vocab_size = load_data(args.data_dir)
    
    seq_len = train_data.shape[1]
    input_dim = train_data.shape[2]
    
    # Create model
    print(f"\n🏗️  Building model (seq_len={seq_len}, input_dim={input_dim}, vocab_size={vocab_size})...")
    model = LSTMAutoencoder(
        vocab_size=vocab_size, embedding_dim=16, input_dim=input_dim, seq_len=seq_len,
        encoder_hidden=(128, 64), decoder_hidden=(64, 128),
        dropout=args.dropout
    )
    
    model = model.to(device)
    print(f"  Parameters: {count_parameters(model):,}")
    
    # Training setup
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=3
    )
    
    train_tensor = torch.FloatTensor(train_data)
    val_tensor = torch.FloatTensor(val_data)
    train_loader = DataLoader(
        TensorDataset(train_tensor, train_tensor),
        batch_size=args.batch_size, shuffle=True
    )
    val_loader = DataLoader(
        TensorDataset(val_tensor, val_tensor),
        batch_size=args.batch_size, shuffle=False
    )
    
    # Training loop
    print(f"\n🚀 Training...")
    train_losses = []
    val_losses = []
    best_val_loss = float('inf')
    patience_counter = 0
    best_epoch = 0
    
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device, args.clip_grad)
        val_loss = validate(model, val_loader, criterion, device)
        
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        scheduler.step(val_loss)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_epoch = epoch
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss': train_loss,
                'val_loss': val_loss,
                'input_dim': input_dim,
                'seq_len': seq_len,
                'vocab_size': vocab_size,
                'encoder_hidden': (128, 64),
                'decoder_hidden': (64, 128),
                'dropout': args.dropout,
            }, os.path.join(args.save_dir, 'lstm_ae_best.pt'))
        else:
            patience_counter += 1
        
        if epoch % 2 == 0 or epoch == 1 or patience_counter == 0:
            marker = " ✓ best" if patience_counter == 0 else ""
            print(f"  Epoch {epoch:3d}/{args.epochs} | "
                  f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                  f"LR: {optimizer.param_groups[0]['lr']:.6f}{marker}")
        
        if patience_counter >= args.patience:
            print(f"\n  ⏹️  Early stopping at epoch {epoch} (best: {best_epoch})")
            break
    
    # Load best
    checkpoint = torch.load(os.path.join(args.save_dir, 'lstm_ae_best.pt'), weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    # Threshold
    print("\n🎯 Computing threshold...")
    val_errors = get_errors(model, val_data, device)
    ts = ThresholdSelector()
    ts.fit_percentile(val_errors, 99.0)
    ts.summary()
    ts.save(os.path.join(args.save_dir, 'lstm_threshold.json'))
    
    # Plot
    plot_curves(train_losses, val_losses, os.path.join(args.save_dir, 'lstm_training_curves.png'))
    
    print(f"\n✅ LSTM AE training complete!")
    print(f"  Best epoch: {best_epoch}, Val loss: {best_val_loss:.6f}")


if __name__ == '__main__':
    main()
