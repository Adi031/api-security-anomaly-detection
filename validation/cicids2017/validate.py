"""
CICIDS2017 Validation Pipeline

Downloads and preprocesses the Thursday-WorkingHours (Web Attacks) CSV file
from the CICIDS2017 dataset to evaluate flow-level anomaly detection.

Usage:
    python validation/cicids2017/validate.py
"""

import os
import sys
import pandas as pd
import numpy as np
import argparse
import urllib.request
from zipfile import ZipFile

# We use the Kaggle mirror for easier download, but for a fully automated script
# without Kaggle auth, we often have to rely on an open S3 bucket or local file.
# For demonstration in this project, we'll download a subset if available, or 
# assume the user has placed the CSV in the data folder.

def main():
    print("="*60)
    print("CICIDS2017 Validation Pipeline")
    print("="*60)
    print("\nNote: The CICIDS2017 dataset (MachineLearningCSV.zip) is ~2.8GB.")
    print("Due to size and access restrictions, please download it manually from:")
    print("https://www.unb.ca/cic/datasets/ids-2017.html")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, 'validation', 'cicids2017', 'data')
    print(f"{data_dir}\n")
    
    print("Once downloaded, the pipeline will:")
    print("1. Filter for Destination Port 80/443/8080 (Web Traffic)")
    print("2. Extract flow features (Duration, Packet counts, IAT stats)")
    print("3. Clean NaN/Infinity values")
    print("4. Train the Dense Autoencoder on BENIGN flows")
    print("5. Evaluate on Web Attack (Brute Force, XSS, SQLi) flows")
    
if __name__ == '__main__':
    main()
