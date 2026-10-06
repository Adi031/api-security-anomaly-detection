import torch
import joblib
import json
import numpy as np
import os
import sys

from config import config

class ModelScorer:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.thresholds = None
        self.tau = 0.0
        self.model_type = "dense_autoencoder"
        
    def load(self):
        if os.path.exists(config.MODEL_PATH):
            try:
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../ml-pipeline')))
                from models.dense_autoencoder import DenseAutoencoder
                self.model = DenseAutoencoder()
                
                checkpoint = torch.load(config.MODEL_PATH, map_location=torch.device('cpu'))
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.model.eval()
            except Exception as e:
                print(f"Error loading model: {e}")
                
        if os.path.exists(config.SCALER_PATH):
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
        if self.model is None or self.scaler is None:
            return 0.0, "normal", {}
            
        try:
            scaled_features = self.scaler.transform(features.reshape(1, -1))
            tensor_features = torch.tensor(scaled_features, dtype=torch.float32)
            
            with torch.no_grad():
                reconstruction = self.model(tensor_features)
                if isinstance(reconstruction, tuple):
                    reconstruction = reconstruction[0] # Handle LSTM output if needed
                    
                mse = torch.mean((tensor_features - reconstruction)**2).item()
                
                from features.feature_utils import extract_per_feature_errors
                feature_contributions = extract_per_feature_errors(tensor_features.numpy()[0], reconstruction.numpy()[0])
                
            score = mse
            
            if score < self.tau:
                severity = "normal"
            elif score < 2 * self.tau:
                severity = "warning"
            else:
                severity = "critical"
                
            return score, severity, feature_contributions
            
        except Exception as e:
            print(f"Scoring error: {e}")
            return 0.0, "normal", {}

scorer = ModelScorer()
