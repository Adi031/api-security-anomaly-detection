"""
LSTM Autoencoder for API Call Sequence Anomaly Detection (Stage 2 — Stretch)

Architecture:
  Input(T=30, D=10)
      ↓
  LSTM(input=10, hidden=128, dropout=0.2)    [Encoder Layer 1]
      ↓
  LSTM(input=128, hidden=64, dropout=0.2)    [Encoder Layer 2]
      ↓
  Bottleneck: last hidden state (64-dim)
      ↓
  RepeatVector(T=30)                          [Repeat across timesteps]
      ↓
  LSTM(input=64, hidden=64, dropout=0.2)     [Decoder Layer 1]
      ↓
  LSTM(input=64, hidden=128, dropout=0.2)    [Decoder Layer 2]
      ↓
  TimeDistributed Linear(128 → D)             [Output projection]

Models the ORDER and TIMING of API calls per session.
Better at catching sequence-pattern attacks (e.g., scraping in systematic order)
that the feature-based model misses.
"""

import torch
import torch.nn as nn


class LSTMEncoder(nn.Module):
    """
    Two-layer LSTM encoder that compresses a variable-length sequence
    into a fixed-size bottleneck vector.
    """
    
    def __init__(self, input_dim, hidden_dims=(128, 64), dropout=0.2):
        super(LSTMEncoder, self).__init__()
        
        self.hidden_dims = hidden_dims
        
        self.lstm1 = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dims[0],
            batch_first=True,
            dropout=0.0  # No dropout on single-layer LSTM
        )
        
        self.lstm2 = nn.LSTM(
            input_size=hidden_dims[0],
            hidden_size=hidden_dims[1],
            batch_first=True,
            dropout=0.0
        )
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        """
        Args:
            x: Input tensor of shape (batch, seq_len, input_dim)
            
        Returns:
            bottleneck: Last hidden state of shape (batch, hidden_dims[-1])
        """
        # Layer 1
        out, _ = self.lstm1(x)
        out = self.dropout(out)
        
        # Layer 2
        out, (h_n, c_n) = self.lstm2(out)
        
        # Bottleneck = last hidden state from final layer
        bottleneck = h_n[-1]  # Shape: (batch, hidden_dims[-1])
        
        return bottleneck


class LSTMDecoder(nn.Module):
    """
    Two-layer LSTM decoder that reconstructs the input sequence
    from the bottleneck vector.
    """
    
    def __init__(self, output_dim, seq_len, hidden_dims=(64, 128), dropout=0.2):
        super(LSTMDecoder, self).__init__()
        
        self.seq_len = seq_len
        self.hidden_dims = hidden_dims
        
        self.lstm1 = nn.LSTM(
            input_size=hidden_dims[0],  # Takes repeated bottleneck
            hidden_size=hidden_dims[0],
            batch_first=True,
            dropout=0.0
        )
        
        self.lstm2 = nn.LSTM(
            input_size=hidden_dims[0],
            hidden_size=hidden_dims[1],
            batch_first=True,
            dropout=0.0
        )
        
        self.dropout = nn.Dropout(dropout)
        
        # TimeDistributed Dense: project each timestep back to output_dim
        self.output_proj = nn.Linear(hidden_dims[1], output_dim)
    
    def forward(self, bottleneck):
        """
        Args:
            bottleneck: Tensor of shape (batch, latent_dim)
            
        Returns:
            reconstructed: Tensor of shape (batch, seq_len, output_dim)
        """
        # RepeatVector: repeat bottleneck across all timesteps
        # (batch, latent_dim) → (batch, seq_len, latent_dim)
        repeated = bottleneck.unsqueeze(1).repeat(1, self.seq_len, 1)
        
        # Layer 1
        out, _ = self.lstm1(repeated)
        out = self.dropout(out)
        
        # Layer 2
        out, _ = self.lstm2(out)
        out = self.dropout(out)
        
        # TimeDistributed Linear projection
        # (batch, seq_len, hidden_dims[-1]) → (batch, seq_len, output_dim)
        reconstructed = self.output_proj(out)
        
        return reconstructed


class LSTMAutoencoder(nn.Module):
    """
    Full LSTM Autoencoder for sequence anomaly detection.
    
    Trained on normal API call sequences; high reconstruction error
    on test sequences indicates anomalous behavior.
    """
    
    def __init__(self, vocab_size, embedding_dim=16, input_dim=10, seq_len=30, 
                 encoder_hidden=(128, 64), decoder_hidden=(64, 128),
                 dropout=0.2):
        super(LSTMAutoencoder, self).__init__()
        
        self.input_dim = input_dim
        self.seq_len = seq_len
        self.latent_dim = encoder_hidden[-1]
        
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        lstm_input_dim = embedding_dim + (input_dim - 1)
        
        self.encoder = LSTMEncoder(
            input_dim=lstm_input_dim,
            hidden_dims=encoder_hidden,
            dropout=dropout
        )
        
        self.decoder = LSTMDecoder(
            output_dim=lstm_input_dim,
            seq_len=seq_len,
            hidden_dims=decoder_hidden,
            dropout=dropout
        )
    
    def forward(self, x):
        """
        Full forward pass: encode sequence → bottleneck → reconstruct.
        
        Args:
            x: Input tensor of shape (batch, seq_len, input_dim)
            
        Returns:
            x_hat: Reconstructed tensor of shape (batch, seq_len, lstm_input_dim)
            x_combined: Combined input tensor of shape (batch, seq_len, lstm_input_dim)
        """
        ep_ids = x[:, :, 0].long()
        ep_emb = self.embedding(ep_ids)
        rest_features = x[:, :, 1:]
        x_combined = torch.cat([ep_emb, rest_features], dim=-1)
        
        bottleneck = self.encoder(x_combined)
        x_hat = self.decoder(bottleneck)
        return x_hat, x_combined
    
    def encode(self, x):
        """Get bottleneck representation for a sequence."""
        ep_ids = x[:, :, 0].long()
        ep_emb = self.embedding(ep_ids)
        rest_features = x[:, :, 1:]
        x_combined = torch.cat([ep_emb, rest_features], dim=-1)
        return self.encoder(x_combined)
    
    def compute_reconstruction_error(self, x, reduction='none'):
        """
        Compute per-sample reconstruction error.
        
        Args:
            x: Input tensor of shape (batch, seq_len, input_dim)
            reduction: 'none' = per-sample, 'mean' = scalar
            
        Returns:
            errors: Per-sample MSE (mean across timesteps and features)
        """
        x_hat, x_combined = self.forward(x)
        
        ep_ids = x[:, :, 0]
        pad_mask = (ep_ids != 0).float()
        
        mse = (x_combined - x_hat) ** 2
        mse = mse.mean(dim=-1) * pad_mask
        
        errors = mse.sum(dim=1) / pad_mask.sum(dim=1).clamp(min=1)
        
        if reduction == 'mean':
            return errors.mean()
        return errors
    
    def get_anomaly_scores(self, x):
        """Alias for scoring engine compatibility."""
        with torch.no_grad():
            return self.compute_reconstruction_error(x, reduction='none')


def count_parameters(model):
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == '__main__':
    # Sanity check for all models
    print("=" * 60)
    
    # Standard LSTM AE
    model = LSTMAutoencoder(vocab_size=100, embedding_dim=16, input_dim=10, seq_len=30)
    x = torch.randn(16, 30, 10)  # Batch of 16 sequences
    # Mock some integer endpoints
    x[:, :, 0] = torch.randint(0, 100, (16, 30)).float()
    
    x_hat, x_combined = model(x)
    errors = model.compute_reconstruction_error(x)
    
    print(f"LSTMAutoencoder")
    print(f"  Parameters: {count_parameters(model):,}")
    print(f"  Input:  {x.shape}")
    print(f"  Output: {x_hat.shape}")
    print(f"  Errors: {errors.shape}, mean={errors.mean():.4f}")
