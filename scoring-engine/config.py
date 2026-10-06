import os

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anomaly_user:anomaly_pass_2024@localhost:5432/api_security")
    MODEL_PATH = os.getenv("MODEL_PATH", "../ml-pipeline/saved_models/dense_ae_best.pt")
    SCALER_PATH = os.getenv("SCALER_PATH", "../ml-pipeline/data/processed/scaler.pkl")
    THRESHOLD_PATH = os.getenv("THRESHOLD_PATH", "../ml-pipeline/saved_models/threshold.json")
    POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "2"))
    PORT = int(os.getenv("PORT", "8001"))

config = Config()
