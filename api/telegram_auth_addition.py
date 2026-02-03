
# ==================== TELEGRAM AUTH ====================
# In-memory session storage (use Redis in production)
_telegram_sessions: dict = {}


class TelegramAuthRequest(BaseModel):
    """Telegram auth session request"""
    pass


class TelegramSessionResponse(BaseModel):
    """Telegram auth session response"""
    session_id: str
    expires_in: int


class TelegramCallbackData(BaseModel):
    """Telegram Login Widget callback data"""
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


@router.post("/telegram/session", response_model=TelegramSessionResponse)
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
    
    return TelegramSessionResponse(
        session_id=session_id,
        expires_in=300  # 5 minutes
    )


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
                # Update last active
                await conn.execute(
                    "UPDATE users SET last_active = NOW() WHERE id = $1",
                    user["id"]
                )
        
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
async def confirm_telegram_session(session_id: str, telegram_id: int, first_name: str = None, last_name: str = None, username: str = None, photo_url: str = None):
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


@router.post("/telegram/callback", response_model=TokenResponse)
async def telegram_widget_callback(data: TelegramCallbackData):
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
    data_check = []
    for key in sorted(data.model_dump().keys()):
        if key != 'hash':
            value = getattr(data, key)
            if value is not None:
                data_check.append(f"{key}={value}")
    data_check_string = "\\n".join(data_check)
    
    # Verify hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if calculated_hash != data.hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication data"
        )
    
    # Check auth_date (should be within 24 hours)
    auth_time = datetime.fromtimestamp(data.auth_date)
    if datetime.utcnow() - auth_time > timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication data expired"
        )
    
    # Get or create user
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            data.id
        )
        
        if not user:
            user = await conn.fetchrow("""
                INSERT INTO users (telegram_id, first_name, last_name, language, created_at, last_active)
                VALUES ($1, $2, $3, 'uz', NOW(), NOW())
                RETURNING *
            """, data.id, data.first_name, data.last_name)
        else:
            await conn.execute(
                "UPDATE users SET last_active = NOW(), first_name = COALESCE($2, first_name), last_name = COALESCE($3, last_name) WHERE id = $1",
                user["id"], data.first_name, data.last_name
            )
    
    # Generate tokens
    access_token = create_access_token(user["id"], user.get("phone_number", ""))
    refresh_token = create_refresh_token(user["id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


