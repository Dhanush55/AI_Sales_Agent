import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


class Settings:
    MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    DB_NAME = os.environ.get('DB_NAME', 'test_database')
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
    JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8001')


settings = Settings()
