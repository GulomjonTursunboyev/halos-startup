"""
HALOS Click Payment Webhook Handler
Handles Click payment notifications and activates PRO subscriptions
"""
import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiohttp

from app.database import get_database
from app.subscription import PRICING_PLANS

logger = logging.getLogger(__name__)

# Click configuration
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "oOV5UCfhefh")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "18872")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "18872")

# Admin notification bot
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")  # Separate bot for notifications
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")  # Admin chat/channel ID

# Error codes
CLICK_ERRORS = {
    0: "Success",
    -1: "SIGN CHECK FAILED",
    -2: "Incorrect parameter amount",
    -3: "Action not found",
    -4: "Already paid",
    -5: "User does not exist",
    -6: "Transaction does not exist",
    -7: "Failed to update user",
    -8: "Error in request from click",
    -9: "Transaction cancelled"
}


def verify_click_signature(data: Dict[str, Any], action: int) -> bool:
    """Verify Click webhook signature"""
    try:
        if action == 0:  # Prepare
            sign_string = (
                f"{data.get('click_trans_id')}"
                f"{data.get('service_id')}"
                f"{CLICK_SECRET_KEY}"
                f"{data.get('merchant_trans_id')}"
                f"{data.get('amount')}"
                f"{action}"
                f"{data.get('sign_time')}"
            )
        else:  # Complete
            sign_string = (
                f"{data.get('click_trans_id')}"
                f"{data.get('service_id')}"
                f"{CLICK_SECRET_KEY}"
                f"{data.get('merchant_trans_id')}"
                f"{data.get('merchant_prepare_id')}"
                f"{data.get('amount')}"
                f"{action}"
                f"{data.get('sign_time')}"
            )
        
        expected_sign = hashlib.md5(sign_string.encode()).hexdigest()
        actual_sign = data.get('sign_string', '')
        
        return expected_sign == actual_sign
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


async def send_admin_notification(
    telegram_id: int,
    plan_id: str,
    amount: int,
    status: str,
    payment_id: str = None,
    user_name: str = None,
    phone: str = None
):
    """Send payment notification to admin bot"""
    if not ADMIN_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Admin notification not configured (ADMIN_BOT_TOKEN or ADMIN_CHAT_ID missing)")
        return
    
    try:
        plan = PRICING_PLANS.get(plan_id, {})
        plan_name = getattr(plan, 'description_uz', plan_id) if plan else plan_id
        
        status_emoji = {
            'pending': '⏳',
            'completed': '✅',
            'failed': '❌',
            'cancelled': '🚫'
        }.get(status, '❓')
        
        message = (
            f"{status_emoji} *TO'LOV XABARNOMASI*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *Foydalanuvchi:* {user_name or 'N/A'}\n"
            f"📱 *Telefon:* {phone or 'N/A'}\n"
            f"🆔 *Telegram ID:* `{telegram_id}`\n\n"
            f"📦 *Tarif:* {plan_name}\n"
            f"💰 *Summa:* {amount:,} so'm\n"
            f"📋 *Status:* {status.upper()}\n"
            f"🔑 *Payment ID:* `{payment_id or 'N/A'}`\n\n"
            f"🕐 *Vaqt:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": ADMIN_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }) as response:
                if response.status == 200:
                    logger.info(f"Admin notification sent for payment {payment_id}")
                else:
                    logger.error(f"Failed to send admin notification: {await response.text()}")
                    
    except Exception as e:
        logger.error(f"Error sending admin notification: {e}")


async def process_click_prepare(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Click PREPARE request (action=0)
    Verify order exists and return prepare response
    """
    try:
        # Verify signature
        if not verify_click_signature(data, action=0):
            logger.error("Click prepare: signature verification failed")
            return {"error": -1, "error_note": CLICK_ERRORS[-1]}
        
        merchant_trans_id = data.get('merchant_trans_id', '')
        amount = float(data.get('amount', 0))
        click_trans_id = data.get('click_trans_id')
        
        # Parse order ID: halos_{telegram_id}_{plan_id}
        parts = merchant_trans_id.split('_')
        if len(parts) < 3 or parts[0] != 'halos':
            return {"error": -5, "error_note": "Invalid order format"}
        
        telegram_id = int(parts[1])
        plan_id = '_'.join(parts[2:])  # pro_weekly, pro_monthly, etc.
        
        # Check if plan exists
        if plan_id not in PRICING_PLANS:
            return {"error": -5, "error_note": "Plan not found"}
        
        plan = PRICING_PLANS[plan_id]
        expected_amount = plan.price_uzs
        
        # Verify amount
        if abs(amount - expected_amount) > 1:  # Allow 1 UZS tolerance
            logger.error(f"Amount mismatch: expected {expected_amount}, got {amount}")
            return {"error": -2, "error_note": CLICK_ERRORS[-2]}
        
        # Check if user exists
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            return {"error": -5, "error_note": CLICK_ERRORS[-5]}
        
        # Check if already paid
        existing_payment = await db.fetch_one(
            "SELECT * FROM payments WHERE payment_id = $1 AND status = 'completed'",
            str(click_trans_id)
        ) if db.is_postgres else await db.fetch_one(
            "SELECT * FROM payments WHERE payment_id = ? AND status = 'completed'",
            str(click_trans_id)
        )
        
        if existing_payment:
            return {"error": -4, "error_note": CLICK_ERRORS[-4]}
        
        # Create pending payment record
        await db.execute_update(
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status)
               VALUES ($1, $2, $3, 'click', $4, 'pending')""" if db.is_postgres else
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status)
               VALUES (?, ?, ?, 'click', ?, 'pending')""",
            user['id'], plan_id, amount, str(click_trans_id)
        )
        
        # Send admin notification
        await send_admin_notification(
            telegram_id=telegram_id,
            plan_id=plan_id,
            amount=int(amount),
            status='pending',
            payment_id=str(click_trans_id),
            user_name=user.get('first_name'),
            phone=user.get('phone_number')
        )
        
        logger.info(f"Click prepare success for order {merchant_trans_id}")
        
        return {
            "error": 0,
            "error_note": "Success",
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": user['id']  # Use user ID as prepare ID
        }
        
    except Exception as e:
        logger.error(f"Click prepare error: {e}")
        return {"error": -8, "error_note": str(e)}


async def process_click_complete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Click COMPLETE request (action=1)
    Activate PRO subscription after successful payment
    """
    try:
        # Verify signature
        if not verify_click_signature(data, action=1):
            logger.error("Click complete: signature verification failed")
            return {"error": -1, "error_note": CLICK_ERRORS[-1]}
        
        merchant_trans_id = data.get('merchant_trans_id', '')
        click_trans_id = data.get('click_trans_id')
        error_code = int(data.get('error', 0))
        
        # Parse order ID
        parts = merchant_trans_id.split('_')
        if len(parts) < 3:
            return {"error": -6, "error_note": "Invalid order format"}
        
        telegram_id = int(parts[1])
        plan_id = '_'.join(parts[2:])
        
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            return {"error": -5, "error_note": CLICK_ERRORS[-5]}
        
        # If Click reports error, mark payment as failed
        if error_code < 0:
            await db.execute_update(
                "UPDATE payments SET status = 'failed' WHERE payment_id = $1" if db.is_postgres else
                "UPDATE payments SET status = 'failed' WHERE payment_id = ?",
                str(click_trans_id)
            )
            
            await send_admin_notification(
                telegram_id=telegram_id,
                plan_id=plan_id,
                amount=int(data.get('amount', 0)),
                status='failed',
                payment_id=str(click_trans_id),
                user_name=user.get('first_name'),
                phone=user.get('phone_number')
            )
            
            return {"error": error_code, "error_note": f"Payment failed: {error_code}"}
        
        # Check if already completed
        existing = await db.fetch_one(
            "SELECT * FROM payments WHERE payment_id = $1 AND status = 'completed'" if db.is_postgres else
            "SELECT * FROM payments WHERE payment_id = ? AND status = 'completed'",
            str(click_trans_id)
        )
        
        if existing:
            return {"error": -4, "error_note": CLICK_ERRORS[-4]}
        
        # Activate PRO subscription
        plan = PRICING_PLANS.get(plan_id)
        if not plan:
            return {"error": -6, "error_note": "Plan not found"}
        
        # Calculate subscription end date
        now = datetime.now()
        if 'weekly' in plan_id:
            expires = now + timedelta(days=7)
        elif 'monthly' in plan_id:
            expires = now + timedelta(days=30)
        elif 'quarterly' in plan_id:
            expires = now + timedelta(days=90)
        elif 'yearly' in plan_id:
            expires = now + timedelta(days=365)
        else:
            expires = now + timedelta(days=30)  # Default to monthly
        
        # Update user subscription
        if db.is_postgres:
            await db.execute_update(
                """UPDATE users SET 
                   subscription_tier = 'pro',
                   subscription_expires = $1
                   WHERE telegram_id = $2""",
                expires, telegram_id
            )
        else:
            await db.execute_update(
                """UPDATE users SET 
                   subscription_tier = 'pro',
                   subscription_expires = ?
                   WHERE telegram_id = ?""",
                expires.isoformat(), telegram_id
            )
        
        # Update payment status
        await db.execute_update(
            "UPDATE payments SET status = 'completed', completed_at = $1 WHERE payment_id = $2" if db.is_postgres else
            "UPDATE payments SET status = 'completed', completed_at = ? WHERE payment_id = ?",
            now, str(click_trans_id)
        )
        
        # Send admin notification
        await send_admin_notification(
            telegram_id=telegram_id,
            plan_id=plan_id,
            amount=int(data.get('amount', 0)),
            status='completed',
            payment_id=str(click_trans_id),
            user_name=user.get('first_name'),
            phone=user.get('phone_number')
        )
        
        logger.info(f"PRO activated for user {telegram_id}, plan: {plan_id}, expires: {expires}")
        
        # Send success message to user (via main bot)
        await send_pro_activation_message(telegram_id, plan_id, expires)
        
        return {
            "error": 0,
            "error_note": "Success",
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": user['id']
        }
        
    except Exception as e:
        logger.error(f"Click complete error: {e}")
        return {"error": -8, "error_note": str(e)}


async def send_pro_activation_message(telegram_id: int, plan_id: str, expires: datetime):
    """Send PRO activation confirmation to user via main bot"""
    try:
        from app.config import BOT_TOKEN
        
        plan = PRICING_PLANS.get(plan_id)
        plan_name = getattr(plan, 'description_uz', plan_id) if plan else plan_id
        
        message = (
            "🎉 *TABRIKLAYMIZ!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *HALOS PRO muvaffaqiyatli aktivlashtirildi!*\n\n"
            f"📦 Tarif: *{plan_name}*\n"
            f"📅 Amal qilish: *{expires.strftime('%d.%m.%Y')}* gacha\n\n"
            "🌟 *Sizning yangi imkoniyatlaringiz:*\n"
            "├ 🗓 HALOS sanangiz\n"
            "├ ⚡ Tezkor qutilish rejasi\n"
            "├ 💰 Shaxsiy kapital hisoblash\n"
            "├ 🎤 Ovozli AI yordamchi\n"
            "├ 📊 Batafsil statistika\n"
            "├ 🔔 Aqlli eslatmalar\n"
            "└ 📥 Excel hisobot\n\n"
            "🚀 Boshlash uchun /start bosing!"
        )
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": telegram_id,
                "text": message,
                "parse_mode": "Markdown"
            }) as response:
                if response.status == 200:
                    logger.info(f"PRO activation message sent to user {telegram_id}")
                else:
                    logger.error(f"Failed to send activation message: {await response.text()}")
                    
    except Exception as e:
        logger.error(f"Error sending PRO activation message: {e}")


async def handle_click_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """Main webhook handler - routes to prepare or complete"""
    action = int(data.get('action', -1))
    
    logger.info(f"Click webhook received: action={action}, data={data}")
    
    if action == 0:
        return await process_click_prepare(data)
    elif action == 1:
        return await process_click_complete(data)
    else:
        return {"error": -3, "error_note": CLICK_ERRORS[-3]}


# ==================== MANUAL PAYMENT VERIFICATION ====================

async def verify_payment_manually(telegram_id: int, plan_id: str) -> bool:
    """
    Manually verify and activate payment (for admin use)
    Used when webhook fails or for manual activation
    """
    try:
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            logger.error(f"User not found: {telegram_id}")
            return False
        
        plan = PRICING_PLANS.get(plan_id)
        if not plan:
            logger.error(f"Plan not found: {plan_id}")
            return False
        
        # Calculate expiration
        now = datetime.now()
        if 'weekly' in plan_id:
            expires = now + timedelta(days=7)
        elif 'monthly' in plan_id:
            expires = now + timedelta(days=30)
        elif 'quarterly' in plan_id:
            expires = now + timedelta(days=90)
        elif 'yearly' in plan_id:
            expires = now + timedelta(days=365)
        else:
            expires = now + timedelta(days=30)
        
        # Activate subscription
        if db.is_postgres:
            await db.execute_update(
                """UPDATE users SET 
                   subscription_tier = 'pro',
                   subscription_expires = $1
                   WHERE telegram_id = $2""",
                expires, telegram_id
            )
        else:
            await db.execute_update(
                """UPDATE users SET 
                   subscription_tier = 'pro',
                   subscription_expires = ?
                   WHERE telegram_id = ?""",
                expires.isoformat(), telegram_id
            )
        
        # Record manual payment
        await db.execute_update(
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, status, completed_at)
               VALUES ($1, $2, $3, 'manual', 'completed', $4)""" if db.is_postgres else
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, status, completed_at)
               VALUES (?, ?, ?, 'manual', 'completed', ?)""",
            user['id'], plan_id, plan.price_uzs, now
        )
        
        logger.info(f"Manual PRO activation for user {telegram_id}, plan: {plan_id}")
        
        # Send notification
        await send_pro_activation_message(telegram_id, plan_id, expires)
        
        return True
        
    except Exception as e:
        logger.error(f"Manual payment verification error: {e}")
        return False
