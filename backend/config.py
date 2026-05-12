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
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', '')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8001')

    # Telephony selection
    TELEPHONY_PROVIDER = os.environ.get('TELEPHONY_PROVIDER', 'twilio')

    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

    # Exotel
    EXOTEL_SID = os.environ.get('EXOTEL_SID', '')
    EXOTEL_API_KEY = os.environ.get('EXOTEL_API_KEY', '')
    EXOTEL_API_TOKEN = os.environ.get('EXOTEL_API_TOKEN', '')
    EXOTEL_SUBDOMAIN = os.environ.get('EXOTEL_SUBDOMAIN', 'api')
    EXOTEL_PHONE_NUMBER = os.environ.get('EXOTEL_PHONE_NUMBER', '')


settings = Settings()
