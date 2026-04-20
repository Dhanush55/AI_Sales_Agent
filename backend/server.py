from fastapi import FastAPI
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
from config import settings

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from utils.db import db, client, create_indexes

app = FastAPI(title="Voice Sales Agent API")

from routes import (
    auth, campaigns, leads, calls, test_mode, conversation_states, voice,
    bulk_operations, analytics, phone_calls, dialer, admin, media_stream,
)

app.include_router(auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(test_mode.router, prefix="/api")
app.include_router(conversation_states.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(bulk_operations.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(phone_calls.router, prefix="/api")
app.include_router(dialer.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(media_stream.router)


@app.get("/api/")
async def root():
    return {"message": "Voice Sales Agent API"}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    try:
        await create_indexes()
        logger.info("MongoDB indexes created")
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

    # Warm up faster-whisper so the first real call has no cold-start delay
    try:
        from services.voice_service import voice_service
        import asyncio
        if hasattr(voice_service.stt_provider, '_get_model'):
            await asyncio.to_thread(voice_service.stt_provider._get_model)
            logger.info("faster-whisper model warmed up")
    except Exception as e:
        logger.warning(f"faster-whisper warm-up skipped: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
