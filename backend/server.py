from fastapi import FastAPI
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from config import settings

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from utils.db import db, client

# Create the main app
app = FastAPI(title="Voice Sales Agent API")

# Import routers
from routes import auth, campaigns, leads, calls, test_mode, conversation_states, voice

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(test_mode.router, prefix="/api")
app.include_router(conversation_states.router, prefix="/api")
app.include_router(voice.router, prefix="/api")

# Root endpoint
@app.get("/api/")
async def root():
    return {"message": "Voice Sales Agent API"}

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
