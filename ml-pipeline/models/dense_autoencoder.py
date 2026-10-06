"""
Dense Autoencoder for API Behavioral Anomaly Detection (Stage 1 — Baseline)

Architecture:
  Input(14) → Dense(64, ReLU) → Dense(32, ReLU) → Dense(16, ReLU)  [Encoder]
                                                      ↓
                                            Bottleneck (16-dim)
                                                      ↓
  Dense(16, ReLU) → Dense(32, ReLU) → Dense(64, ReLU) → Dense(14)   [Decoder]

Trained only on normal traffic. High reconstruction error = anomaly.
"""

import torch
import torch.nn as nn


class DenseAutoencoder(nn.Module):
    """
    Symmetric dense autoencoder for behavioral feature vectors.
    
    The encoder compresses the input feature vector into a low-dimensional
    bottleneck, and the decoder reconstructs it. Normal traffic patterns 
    are reconstructed well (low error); anomalous patterns are not (high error).
    """
    
    def __init__(self, input_dim=14, encoding_dim=6, dropout=0.2):
        super(DenseAutoencoder, self).__init__()
        
        self.input_dim = input_dim
        self.encoding_dim = encoding_dim
        
        # Encoder: input_dim → 64 → 32 → encoding_dim
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(32, encoding_dim),
            nn.ReLU(),
        )
        
        # Decoder: encoding_dim → 32 → 64 → input_dim
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(64, input_dim),
            # No activation on output — features are standardized (can be negative)
        )
    
    def encode(self, x):
        """Encode input to bottleneck representation."""
        return self.encoder(x)
    
    def decode(self, z):
        """Decode bottleneck representation back to input space."""
        return self.decoder(z)
    
    def forward(self, x):
        """Full forward pass: encode → decode."""
        z = self.encode(x)
        x_reconstructed = self.decode(z)
        return x_reconstructed
    
    def compute_reconstruction_error(self, x, reduction='none'):
        """
        Compute per-sample reconstruction error (MSE).
        
        Args:
            x: Input tensor of shape (batch_size, input_dim)
            reduction: 'none' returns per-sample error, 'mean' returns scalar
            
        Returns:
            errors: Per-sample MSE if reduction='none', else scalar
        """
        with torch.no_grad():
            x_hat = self.forward(x)
            # Per-feature MSE, then mean across features → per-sample score
            errors = torch.mean((x - x_hat) ** 2, dim=1)
            
            if reduction == 'mean':
                return errors.mean()
            return errors
    
    def get_anomaly_scores(self, x):
        """Alias for compute_reconstruction_error (for scoring engine compatibility)."""
        return self.compute_reconstruction_error(x, reduction='none')


def count_parameters(model):
    """Count trainable parameters in model."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == '__main__':
    # Quick sanity check
    model = DenseAutoencoder(input_dim=14, encoding_dim=6)
    print(f"Model: DenseAutoencoder")
    print(f"Parameters: {count_parameters(model):,}")
    print(f"\nArchitecture:\n{model}")
    
    # Test forward pass
    x = torch.randn(32, 14)  # Batch of 32 samples, 14 features
    x_hat = model(x)
    errors = model.compute_reconstruction_error(x)
    
    print(f"\nInput shape:  {x.shape}")
    print(f"Output shape: {x_hat.shape}")
    print(f"Errors shape: {errors.shape}")
    print(f"Mean error:   {errors.mean():.4f}")
