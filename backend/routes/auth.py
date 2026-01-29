from fastapi import APIRouter, HTTPException, status
from models.user import UserCreate, UserLogin, TokenResponse, User
from utils.security import hash_password, verify_password, create_access_token
from utils.db import db, prepare_for_mongo
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Register a new user"""
    try:
        # Check if user exists
        existing_user = await db.users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        user = User(
            email=user_data.email,
            company_name=user_data.company_name
        )
        
        user_doc = prepare_for_mongo(user.model_dump())
        user_doc["password_hash"] = hash_password(user_data.password)
        
        await db.users.insert_one(user_doc)
        
        # Generate token
        access_token = create_access_token({"sub": user.id})
        
        return TokenResponse(
            access_token=access_token,
            user=user
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user"""
    try:
        # Find user
        user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(credentials.password, user_doc["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create user object (exclude password_hash)
        user_data = {k: v for k, v in user_doc.items() if k != "password_hash"}
        user = User(**user_data)
        
        # Generate token
        access_token = create_access_token({"sub": user.id})
        
        return TokenResponse(
            access_token=access_token,
            user=user
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )