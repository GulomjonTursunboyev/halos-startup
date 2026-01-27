"""
Users Router
User profile management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import logging

from api.models import UserProfile, UserUpdate, FinancialProfile, NotificationSettings, PushTokenRequest
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile"""
    return UserProfile(
        id=current_user["id"],
        phone_number=current_user["phone_number"],
        telegram_id=current_user.get("telegram_id"),
        first_name=current_user.get("first_name"),
        last_name=current_user.get("last_name"),
        username=current_user.get("username"),
        language=current_user.get("language", "uz"),
        subscription_tier=current_user.get("subscription_tier", "free"),
        subscription_expires=current_user.get("subscription_expires"),
        created_at=current_user["created_at"],
        last_active=current_user.get("last_active")
    )


@router.patch("/profile", response_model=UserProfile)
async def update_profile(
    update: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build dynamic update query
        updates = []
        values = []
        param_idx = 1
        
        if update.first_name is not None:
            updates.append(f"first_name = ${param_idx}")
            values.append(update.first_name)
            param_idx += 1
        
        if update.last_name is not None:
            updates.append(f"last_name = ${param_idx}")
            values.append(update.last_name)
            param_idx += 1
        
        if update.language is not None:
            updates.append(f"language = ${param_idx}")
            values.append(update.language)
            param_idx += 1
        
        if update.avatar_url is not None:
            updates.append(f"avatar_url = ${param_idx}")
            values.append(update.avatar_url)
            param_idx += 1
        
        if updates:
            updates.append("updated_at = NOW()")
            values.append(current_user["id"])
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
            user = await conn.fetchrow(query, *values)
        else:
            user = current_user
    
    return UserProfile(
        id=user["id"],
        phone_number=user["phone_number"],
        telegram_id=user.get("telegram_id"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        username=user.get("username"),
        language=user.get("language", "uz"),
        subscription_tier=user.get("subscription_tier", "free"),
        subscription_expires=user.get("subscription_expires"),
        created_at=user["created_at"],
        last_active=user.get("last_active")
    )


@router.get("/financial-profile", response_model=FinancialProfile)
async def get_financial_profile(current_user: dict = Depends(get_current_user)):
    """Get user's financial profile"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        profile = await conn.fetchrow(
            "SELECT * FROM financial_profiles WHERE user_id = $1",
            current_user["id"]
        )
    
    if not profile:
        return FinancialProfile()
    
    return FinancialProfile(
        monthly_income=profile.get("monthly_income", 0) or 0,
        monthly_expenses=profile.get("monthly_expenses", 0) or 0,
        savings_goal=profile.get("savings_goal", 0) or 0,
        savings_current=profile.get("savings_current", 0) or 0,
        currency=profile.get("currency", "UZS")
    )


@router.put("/financial-profile", response_model=FinancialProfile)
async def update_financial_profile(
    profile: FinancialProfile,
    current_user: dict = Depends(get_current_user)
):
    """Update user's financial profile"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow("""
            INSERT INTO financial_profiles (user_id, monthly_income, monthly_expenses, savings_goal, savings_current, currency)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE SET
                monthly_income = EXCLUDED.monthly_income,
                monthly_expenses = EXCLUDED.monthly_expenses,
                savings_goal = EXCLUDED.savings_goal,
                savings_current = EXCLUDED.savings_current,
                currency = EXCLUDED.currency,
                updated_at = NOW()
            RETURNING *
        """, current_user["id"], profile.monthly_income, profile.monthly_expenses,
            profile.savings_goal, profile.savings_current, profile.currency.value)
    
    return FinancialProfile(
        monthly_income=result.get("monthly_income", 0) or 0,
        monthly_expenses=result.get("monthly_expenses", 0) or 0,
        savings_goal=result.get("savings_goal", 0) or 0,
        savings_current=result.get("savings_current", 0) or 0,
        currency=result.get("currency", "UZS")
    )


@router.get("/notifications/settings", response_model=NotificationSettings)
async def get_notification_settings(current_user: dict = Depends(get_current_user)):
    """Get user's notification settings"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        settings = await conn.fetchrow(
            "SELECT * FROM user_notification_settings WHERE user_id = $1",
            current_user["id"]
        )
    
    if not settings:
        return NotificationSettings()
    
    return NotificationSettings(
        debt_reminders=settings.get("debt_reminders", True),
        budget_alerts=settings.get("budget_alerts", True),
        weekly_report=settings.get("weekly_report", True),
        monthly_report=settings.get("monthly_report", True),
        push_enabled=settings.get("push_enabled", True),
        reminder_time=settings.get("reminder_time", "09:00")
    )


@router.put("/notifications/settings", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: dict = Depends(get_current_user)
):
    """Update notification settings"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_notification_settings 
            (user_id, debt_reminders, budget_alerts, weekly_report, monthly_report, push_enabled, reminder_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id) DO UPDATE SET
                debt_reminders = EXCLUDED.debt_reminders,
                budget_alerts = EXCLUDED.budget_alerts,
                weekly_report = EXCLUDED.weekly_report,
                monthly_report = EXCLUDED.monthly_report,
                push_enabled = EXCLUDED.push_enabled,
                reminder_time = EXCLUDED.reminder_time,
                updated_at = NOW()
        """, current_user["id"], settings.debt_reminders, settings.budget_alerts,
            settings.weekly_report, settings.monthly_report, settings.push_enabled,
            settings.reminder_time)
    
    return settings


@router.post("/push-token")
async def register_push_token(
    request: PushTokenRequest,
    current_user: dict = Depends(get_current_user)
):
    """Register device push notification token"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_push_tokens (user_id, token, platform, device_id, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, token) DO UPDATE SET
                platform = EXCLUDED.platform,
                device_id = EXCLUDED.device_id,
                updated_at = NOW()
        """, current_user["id"], request.token, request.platform, request.device_id)
    
    return {"message": "Push token registered"}


@router.delete("/push-token/{token}")
async def unregister_push_token(
    token: str,
    current_user: dict = Depends(get_current_user)
):
    """Unregister device push notification token"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_push_tokens WHERE user_id = $1 AND token = $2",
            current_user["id"], token
        )
    
    return {"message": "Push token unregistered"}
