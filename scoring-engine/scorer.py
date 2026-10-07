import torch
import joblib
import json
import numpy as np
import os
import sys
import pickle

from config import config

class ModelScorer:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.thresholds = None
        self.tau = 0.0
        self.vocab = None
        self.model_type = config.MODEL_TYPE
        
    def load(self):
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../ml-pipeline')))
        
        # Load Vocab if LSTM
        if config.MODEL_TYPE == "lstm" and os.path.exists(config.VOCAB_PATH):
            with open(config.VOCAB_PATH, 'rb') as f:
                self.vocab = pickle.load(f)
                
        if os.path.exists(config.MODEL_PATH):
            try:
                if config.MODEL_TYPE == "dense":
                    from models.dense_autoencoder import DenseAutoencoder
                    self.model = DenseAutoencoder(input_dim=14, encoding_dim=6)
                else:
                    from models.lstm_autoencoder import LSTMAutoencoder
                    self.model = LSTMAutoencoder(vocab_size=len(self.vocab), seq_len=30, input_dim=10)
                    
                checkpoint = torch.load(config.MODEL_PATH, map_location=torch.device('cpu'), weights_only=False)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.model.eval()
            except Exception as e:
                print(f"Error loading model: {e}")
                
        if config.MODEL_TYPE == "dense" and config.SCALER_PATH and os.path.exists(config.SCALER_PATH):
            try:
                self.scaler = joblib.load(config.SCALER_PATH)
            except Exception as e:
                print(f"Error loading scaler: {e}")
                
        if os.path.exists(config.THRESHOLD_PATH):
            try:
                with open(config.THRESHOLD_PATH, 'r') as f:
                    self.thresholds = json.load(f)
                    self.tau = self.thresholds.get("threshold", 0.1)
            except Exception as e:
                print(f"Error loading thresholds: {e}")
                
    def score_features(self, features: np.ndarray):
        if self.model is None:
            return 0.0, "normal", {}
            
        try:
            if config.MODEL_TYPE == "dense":
                scaled_features = self.scaler.transform(features.reshape(1, -1))
                tensor_features = torch.tensor(scaled_features, dtype=torch.float32)
                
                with torch.no_grad():
                    reconstruction = self.model(tensor_features)
                    mse = torch.mean((tensor_features - reconstruction)**2).item()
                    
                    from features.feature_utils import extract_per_feature_errors
                    feature_contributions = extract_per_feature_errors(tensor_features.numpy()[0], reconstruction.numpy()[0])
            else:
                # LSTM scoring
                tensor_features = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    mse = self.model.compute_reconstruction_error(tensor_features, reduction='none').numpy()[0]
                feature_contributions = {} # Not easily mapped per feature in sequences
                
            score = float(mse)
            
            if score < self.tau:
                severity = "normal"
            elif score < 2 * self.tau:
                severity = "warning"
            else:
                severity = "critical"
                
            return score, severity, feature_contributions
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Scoring error: {e}")
            return 0.0, "normal", {}

scorer = ModelScorer()
