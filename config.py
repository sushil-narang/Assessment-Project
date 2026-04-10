# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here_for_dev_only'
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'database.db')