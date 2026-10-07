import os

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../database.sqlite")
    
    # Toggle this between "dense" and "lstm"
    MODEL_TYPE = os.getenv("MODEL_TYPE", "lstm")
    
    if MODEL_TYPE == "dense":
        MODEL_PATH = os.getenv("MODEL_PATH", "../ml-pipeline/saved_models/dense_ae_best.pt")
        SCALER_PATH = os.getenv("SCALER_PATH", "../ml-pipeline/data/processed/scaler.pkl")
        THRESHOLD_PATH = os.getenv("THRESHOLD_PATH", "../ml-pipeline/saved_models/threshold.json")
        VOCAB_PATH = None
    else:
        MODEL_PATH = os.getenv("MODEL_PATH", "../ml-pipeline/saved_models/lstm_ae_best.pt")
        SCALER_PATH = None
        THRESHOLD_PATH = os.getenv("THRESHOLD_PATH", "../ml-pipeline/saved_models/lstm_threshold.json")
        VOCAB_PATH = os.getenv("VOCAB_PATH", "../ml-pipeline/data/processed/endpoint_vocab.pkl")
        
    POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "2"))
    PORT = int(os.getenv("PORT", "8001"))

config = Config()
