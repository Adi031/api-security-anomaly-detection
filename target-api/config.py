import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'super-secret-jwt-key')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'api_security')
    DB_USER = os.getenv('DB_USER', 'anomaly_user')
    DB_PASS = os.getenv('DB_PASS', 'anomaly_pass_2024')
    DEBUG = True
