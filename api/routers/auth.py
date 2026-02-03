"""
Authentication Router
Phone OTP login, JWT tokens, Telegram linking
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta
import random
import logging
import httpx

from api.models import (
    PhoneLoginRequest, OTPVerifyRequest, TokenResponse,
    RefreshTokenRequest, TelegramLinkRequest
)
from api.database import get_pool
from api.auth import (
    create_access_token, create_refresh_token,
    verify_refresh_token, get_current_user
)
from api.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory OTP storage (use Redis in production)
_otp_store: dict = {}


async def send_sms_otp(phone_number: str, otp_code: str) -> bool:
    """Send OTP via Eskiz.uz SMS service"""
    try:
        # Get Eskiz token
        async with httpx.AsyncClient() as client:
            # Login to get token
            auth_response = await client.post(
                "https://notify.eskiz.uz/api/auth/login",
                data={
                    "email": settings.ESKIZ_EMAIL,
                    "password": settings.ESKIZ_PASSWORD
                }
            )
            
            if auth_response.status_code != 200:
                logger.error(f"Eskiz auth failed: {auth_response.text}")
                return False
            
            token = auth_response.json().get("data", {}).get("token")
            
            # Send SMS
            sms_response = await client.post(
                "https://notify.eskiz.uz/api/message/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "mobile_phone": phone_number.replace("+", ""),
                    "message": f"HALOS ilovasi uchun tasdiqlash kodi: {otp_code}",
                    "from": "4546"
                }
            )
            
            if sms_response.status_code == 200:
                logger.info(f"OTP sent to {phone_number}")
                return True
            else:
                logger.error(f"SMS send failed: {sms_response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        return False


@router.post("/login", response_model=dict)
async def request_otp(request: PhoneLoginRequest):
    """
    Request OTP code for phone number login
    """
    phone = request.phone_number
    
    # Generate 6-digit OTP
    otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Store OTP with expiration
    _otp_store[phone] = {
        "code": otp_code,
        "expires": datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        "attempts": 0
    }
    
    # Send OTP via SMS
    # In development, just log it
    if settings.DEBUG:
        logger.info(f"[DEBUG] OTP for {phone}: {otp_code}")
    else:
        success = await send_sms_otp(phone, otp_code)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP"
            )
    
    return {
        "message": "OTP sent successfully",
        "phone_number": phone,
        "expires_in": settings.OTP_EXPIRE_MINUTES * 60
    }


@router.post("/verify", response_model=TokenResponse)
async def verify_otp(request: OTPVerifyRequest):
    """
    Verify OTP and return JWT tokens
    Creates new user if not exists
    """
    phone = request.phone_number
    otp_code = request.otp_code
    
    # Check OTP
    stored = _otp_store.get(phone)
    
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found. Please request a new one."
        )
    
    if datetime.utcnow() > stored["expires"]:
        del _otp_store[phone]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new one."
        )
    
    stored["attempts"] += 1
    if stored["attempts"] > 3:
        del _otp_store[phone]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many attempts. Please request a new OTP."
        )
    
    if stored["code"] != otp_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code"
        )
    
    # OTP is valid, remove from store
    del _otp_store[phone]
    
    # Get or create user
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if user exists
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE phone_number = $1",
            phone
        )
        
        if not user:
            # Create new user
            user = await conn.fetchrow("""
                INSERT INTO users (phone_number, telegram_id, language, created_at, last_active)
                VALUES ($1, 0, 'uz', NOW(), NOW())
                RETURNING *
            """, phone)
            logger.info(f"New user created: {phone}")
        else:
            # Update last active
            await conn.execute(
                "UPDATE users SET last_active = NOW() WHERE id = $1",
                user["id"]
            )
    
    # Generate tokens
    access_token = create_access_token(user["id"], phone)
    refresh_token = create_refresh_token(user["id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    user_id = verify_refresh_token(request.refresh_token)
    
    # Get user
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Generate new tokens
    access_token = create_access_token(user["id"], user["phone_number"])
    refresh_token = create_refresh_token(user["id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/link-telegram")
async def link_telegram_account(
    request: TelegramLinkRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Link Telegram account to mobile app account
    User must first get a verification code from Telegram bot
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if Telegram account exists
        telegram_user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            request.telegram_id
        )
        
        if not telegram_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telegram account not found. Please start the bot first."
            )
        
        # Verify linking code (stored in user's context)
        # This should be implemented with a proper verification mechanism
        
        # If phone numbers match, merge accounts
        if telegram_user["phone_number"] == current_user["phone_number"]:
            # Update mobile user with telegram_id
            await conn.execute("""
                UPDATE users SET telegram_id = $1 WHERE id = $2
            """, request.telegram_id, current_user["id"])
            
            return {"message": "Telegram account linked successfully"}
        else:
            # Merge data from telegram account to mobile account
            # This is a complex operation - transfer all transactions, debts, etc.
            await conn.execute("""
                UPDATE transactions SET user_id = $1 WHERE user_id = $2
            """, current_user["id"], telegram_user["id"])
            
            await conn.execute("""
                UPDATE personal_debts SET user_id = $1 WHERE user_id = $2
            """, current_user["id"], telegram_user["id"])
            
            # Update telegram_id
            await conn.execute("""
                UPDATE users SET telegram_id = $1 WHERE id = $2
            """, request.telegram_id, current_user["id"])
            
            # Mark old telegram user as merged
            await conn.execute("""
                UPDATE users SET phone_number = $1 WHERE id = $2
            """, f"merged_{telegram_user['id']}", telegram_user["id"])
            
            return {"message": "Accounts merged successfully"}


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info"""
    return {
        "id": current_user["id"],
        "phone_number": current_user["phone_number"],
        "telegram_id": current_user.get("telegram_id"),
        "first_name": current_user.get("first_name"),
        "last_name": current_user.get("last_name"),
        "language": current_user.get("language", "uz"),
        "subscription_tier": current_user.get("subscription_tier", "free")
    }

# ==================== TELEGRAM APP AUTH ====================
# In-memory session storage (use Redis in production)
_telegram_sessions: dict = {}


@router.post("/telegram/session")
async def create_telegram_session():
    """
    Create a new Telegram auth session for mobile app
    Returns session_id that should be passed to bot via deep link
    """
    import uuid
    session_id = str(uuid.uuid4())
    
    _telegram_sessions[session_id] = {
        "status": "pending",
        "created_at": datetime.utcnow(),
        "expires": datetime.utcnow() + timedelta(minutes=5),
        "user_data": None
    }
    
    return {
        "session_id": session_id,
        "expires_in": 300  # 5 minutes
    }


@router.get("/telegram/session/{session_id}")
async def check_telegram_session(session_id: str):
    """
    Check Telegram auth session status (for polling from mobile app)
    Returns user data and tokens when session is completed
    """
    session = _telegram_sessions.get(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired"
        )
    
    if datetime.utcnow() > session["expires"]:
        del _telegram_sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired"
        )
    
    if session["status"] == "pending":
        return {"status": "pending"}
    
    if session["status"] == "completed":
        user_data = session["user_data"]
        
        # Get or create user in database
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                user_data["telegram_id"]
            )
            
            if not user:
                # Create new user
                user = await conn.fetchrow("""
                    INSERT INTO users (telegram_id, first_name, last_name, language, created_at, last_active)
                    VALUES ($1, $2, $3, 'uz', NOW(), NOW())
                    RETURNING *
                """, user_data["telegram_id"], user_data.get("first_name"), user_data.get("last_name"))
            else:
                # Update last active and info
                await conn.execute("""
                    UPDATE users SET last_active = NOW(), 
                    first_name = COALESCE($2, first_name),
                    last_name = COALESCE($3, last_name)
                    WHERE id = $1
                """, user["id"], user_data.get("first_name"), user_data.get("last_name"))
                # Re-fetch updated user
                user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user["id"])
        
        # Generate tokens
        access_token = create_access_token(user["id"], user.get("phone_number", ""))
        refresh_token = create_refresh_token(user["id"])
        
        # Clean up session
        del _telegram_sessions[session_id]
        
        return {
            "status": "completed",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user["id"],
                "telegram_id": user["telegram_id"],
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": user_data.get("username"),
                "photo_url": user_data.get("photo_url"),
                "language_code": user.get("language", "uz")
            }
        }
    
    return {"status": session["status"]}


@router.post("/telegram/session/{session_id}/confirm")
async def confirm_telegram_session(
    session_id: str,
    telegram_id: int,
    first_name: str = None,
    last_name: str = None,
    username: str = None,
    photo_url: str = None
):
    """
    Confirm Telegram auth session (called by bot when user confirms login)
    This endpoint should be called from the Telegram bot
    """
    session = _telegram_sessions.get(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired"
        )
    
    if datetime.utcnow() > session["expires"]:
        del _telegram_sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired"
        )
    
    # Update session with user data
    _telegram_sessions[session_id] = {
        **session,
        "status": "completed",
        "user_data": {
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "photo_url": photo_url
        }
    }
    
    return {"status": "confirmed", "message": "Login confirmed successfully"}


@router.post("/telegram/callback")
async def telegram_widget_callback(
    id: int,
    first_name: str = None,
    last_name: str = None,
    username: str = None,
    photo_url: str = None,
    auth_date: int = 0,
    hash: str = ""
):
    """
    Handle Telegram Login Widget callback (for web)
    Verifies hash and creates/returns user session
    """
    import hashlib
    import hmac
    
    # Verify telegram data
    bot_token = settings.BOT_TOKEN
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bot token not configured"
        )
    
    # Create data check string
    data_dict = {
        "id": id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "photo_url": photo_url,
        "auth_date": auth_date
    }
    data_check = []
    for key in sorted(data_dict.keys()):
        value = data_dict[key]
        if value is not None:
            data_check.append(f"{key}={value}")
    data_check_string = "\n".join(data_check)
    
    # Verify hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if calculated_hash != hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication data"
        )
    
    # Check auth_date (should be within 24 hours)
    from datetime import timezone
    auth_time = datetime.fromtimestamp(auth_date, tz=timezone.utc)
    if datetime.now(timezone.utc) - auth_time > timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication data expired"
        )
    
    # Get or create user
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            id
        )
        
        if not user:
            user = await conn.fetchrow("""
                INSERT INTO users (telegram_id, first_name, last_name, language, created_at, last_active)
                VALUES ($1, $2, $3, 'uz', NOW(), NOW())
                RETURNING *
            """, id, first_name, last_name)
        else:
            await conn.execute("""
                UPDATE users SET last_active = NOW(), 
                first_name = COALESCE($2, first_name), 
                last_name = COALESCE($3, last_name) 
                WHERE id = $1
            """, user["id"], first_name, last_name)
            user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user["id"])
    
    # Generate tokens
    access_token = create_access_token(user["id"], user.get("phone_number", ""))
    refresh_token = create_refresh_token(user["id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
