import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'super-secret-jwt-key')
    DEBUG = True
