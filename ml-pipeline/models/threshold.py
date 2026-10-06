"""
Threshold Selection for Anomaly Detection

Provides multiple strategies for selecting the anomaly detection threshold
from the reconstruction error distribution of normal traffic.

Methods:
1. 3-Sigma (Gaussian): τ = μ + 3σ
2. Percentile (Non-parametric): τ = 99th percentile
3. F1-Sweep (Supervised): Sweep threshold to maximize F1 on labeled data
"""

import numpy as np
from sklearn.metrics import (
    precision_recall_curve, f1_score, precision_score, recall_score,
    roc_curve, auc
)
import json
import os


class ThresholdSelector:
    """
    Selects and stores anomaly detection threshold from reconstruction errors.
    """
    
    def __init__(self):
        self.threshold = None
        self.method = None
        self.stats = {}
    
    def fit_sigma(self, normal_errors, n_sigma=3):
        """
        3-Sigma method: τ = μ + n × σ
        
        Assumes reconstruction errors are roughly Gaussian for normal traffic.
        
        Args:
            normal_errors: array of reconstruction errors on normal validation data
            n_sigma: number of standard deviations (default: 3)
            
        Returns:
            threshold: float
        """
        mu = np.mean(normal_errors)
        sigma = np.std(normal_errors)
        self.threshold = mu + n_sigma * sigma
        self.method = f'{n_sigma}-sigma'
        self.stats = {
            'method': self.method,
            'mu': float(mu),
            'sigma': float(sigma),
            'n_sigma': n_sigma,
            'threshold': float(self.threshold),
            'normal_max': float(np.max(normal_errors)),
            'normal_min': float(np.min(normal_errors)),
        }
        
        return self.threshold
    
    def fit_percentile(self, normal_errors, percentile=99.0):
        """
        Percentile method: τ = P(errors, percentile)
        
        Non-parametric — makes no distribution assumptions.
        Bounds the false alarm rate to (100 - percentile)%.
        
        Args:
            normal_errors: array of reconstruction errors on normal validation data
            percentile: percentile value (default: 99.0 → ~1% FPR on normal data)
            
        Returns:
            threshold: float
        """
        self.threshold = np.percentile(normal_errors, percentile)
        self.method = f'percentile-{percentile}'
        self.stats = {
            'method': self.method,
            'percentile': percentile,
            'threshold': float(self.threshold),
            'bounded_fpr': (100 - percentile) / 100,
            'normal_max': float(np.max(normal_errors)),
            'normal_min': float(np.min(normal_errors)),
        }
        
        return self.threshold
    
    def fit_f1_sweep(self, errors, labels, n_thresholds=1000, beta=1.0):
        """
        F1-Sweep method: find threshold that maximizes F-beta score.
        
        Requires labeled data (both normal and attack).
        
        Args:
            errors: array of reconstruction errors (all samples)
            labels: array of labels (0=normal, 1=attack)
            n_thresholds: number of threshold candidates to evaluate
            beta: F-beta parameter (1.0=F1, 0.5=favor precision, 2.0=favor recall)
            
        Returns:
            threshold: float
        """
        min_err = np.min(errors)
        max_err = np.max(errors)
        
        thresholds = np.linspace(min_err, max_err, n_thresholds)
        
        best_f = 0.0
        best_threshold = thresholds[0]
        best_precision = 0.0
        best_recall = 0.0
        
        for t in thresholds:
            predictions = (errors > t).astype(int)
            
            if predictions.sum() == 0 or predictions.sum() == len(predictions):
                continue
            
            p = precision_score(labels, predictions, zero_division=0)
            r = recall_score(labels, predictions, zero_division=0)
            
            if p + r > 0:
                f_beta = (1 + beta**2) * (p * r) / (beta**2 * p + r)
            else:
                f_beta = 0.0
            
            if f_beta > best_f:
                best_f = f_beta
                best_threshold = t
                best_precision = p
                best_recall = r
        
        self.threshold = best_threshold
        self.method = f'f{beta}-sweep'
        self.stats = {
            'method': self.method,
            'beta': beta,
            'threshold': float(best_threshold),
            'best_f_score': float(best_f),
            'precision_at_threshold': float(best_precision),
            'recall_at_threshold': float(best_recall),
            'n_normal': int((labels == 0).sum()),
            'n_attack': int((labels == 1).sum()),
        }
        
        return self.threshold
    
    def predict(self, errors):
        """
        Classify errors as normal (0) or anomalous (1) using stored threshold.
        
        Args:
            errors: array of reconstruction errors
            
        Returns:
            predictions: binary array (0=normal, 1=anomaly)
        """
        if self.threshold is None:
            raise ValueError("No threshold set. Call fit_sigma/fit_percentile/fit_f1_sweep first.")
        return (errors > self.threshold).astype(int)
    
    def get_severity(self, errors):
        """
        Classify errors into severity levels.
        
        Returns:
            severity: array of strings ('normal', 'info', 'warning', 'critical')
        """
        if self.threshold is None:
            raise ValueError("No threshold set.")
        
        severity = np.full(len(errors), 'normal', dtype=object)
        severity[errors > 0.5 * self.threshold] = 'info'
        severity[errors > self.threshold] = 'warning'
        severity[errors > 2.0 * self.threshold] = 'critical'
        
        return severity
    
    def save(self, filepath):
        """Save threshold and stats to JSON."""
        data = {
            'threshold': float(self.threshold) if self.threshold else None,
            'method': self.method,
            'stats': self.stats,
        }
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Threshold saved to {filepath}")
    
    def load(self, filepath):
        """Load threshold and stats from JSON."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.threshold = data['threshold']
        self.method = data['method']
        self.stats = data['stats']
        print(f"✅ Threshold loaded: {self.threshold:.6f} (method: {self.method})")
        return self.threshold
    
    def summary(self):
        """Print threshold summary."""
        print(f"\n{'=' * 50}")
        print(f"Threshold Summary")
        print(f"{'=' * 50}")
        print(f"  Method:    {self.method}")
        print(f"  Threshold: {self.threshold:.6f}")
        for key, value in self.stats.items():
            if key not in ('method', 'threshold'):
                print(f"  {key}: {value}")
        print(f"{'=' * 50}")


def compare_thresholds(normal_errors, attack_errors=None):
    """
    Compare all threshold methods and return results.
    
    Args:
        normal_errors: reconstruction errors on normal validation data
        attack_errors: reconstruction errors on attack data (optional, for F1)
        
    Returns:
        dict of method → {threshold, stats}
    """
    results = {}
    
    # 3-Sigma
    ts_3sigma = ThresholdSelector()
    ts_3sigma.fit_sigma(normal_errors, n_sigma=3)
    results['3-sigma'] = ts_3sigma.stats.copy()
    
    # 2-Sigma (more sensitive)
    ts_2sigma = ThresholdSelector()
    ts_2sigma.fit_sigma(normal_errors, n_sigma=2)
    results['2-sigma'] = ts_2sigma.stats.copy()
    
    # 99th percentile
    ts_p99 = ThresholdSelector()
    ts_p99.fit_percentile(normal_errors, percentile=99.0)
    results['percentile-99'] = ts_p99.stats.copy()
    
    # 95th percentile
    ts_p95 = ThresholdSelector()
    ts_p95.fit_percentile(normal_errors, percentile=95.0)
    results['percentile-95'] = ts_p95.stats.copy()
    
    # F1-Sweep (if labeled data available)
    if attack_errors is not None:
        all_errors = np.concatenate([normal_errors, attack_errors])
        all_labels = np.concatenate([
            np.zeros(len(normal_errors)),
            np.ones(len(attack_errors))
        ])
        
        ts_f1 = ThresholdSelector()
        ts_f1.fit_f1_sweep(all_errors, all_labels, beta=1.0)
        results['f1-sweep'] = ts_f1.stats.copy()
        
        ts_f2 = ThresholdSelector()
        ts_f2.fit_f1_sweep(all_errors, all_labels, beta=2.0)
        results['f2-sweep'] = ts_f2.stats.copy()
    
    return results


if __name__ == '__main__':
    # Demo with synthetic data
    np.random.seed(42)
    
    # Simulate normal errors (low) and attack errors (high)
    normal_errors = np.random.exponential(0.1, size=1000)
    attack_errors = np.random.exponential(0.5, size=200) + 0.3
    
    print("Comparing threshold methods:")
    print("=" * 60)
    
    results = compare_thresholds(normal_errors, attack_errors)
    
    for method, stats in results.items():
        print(f"\n{method}:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
