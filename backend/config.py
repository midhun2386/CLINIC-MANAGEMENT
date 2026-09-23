import os
from dotenv import load_dotenv

# Load .env from the project root (one level up from backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-dev-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///clinic.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_EXPIRY_MINUTES = int(os.getenv('JWT_EXPIRY_MINUTES', '60'))
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'uploads')
