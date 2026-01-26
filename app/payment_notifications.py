"""
HALOS Payment Notifications
Sends payment notifications to a separate bot for admins
"""
import logging
from datetime import datetime
from typing import Optional
import aiohttp

from app.config import PAYMENT_BOT_TOKEN, PAYMENT_ADMIN_IDS, BOT_TOKEN, ADMIN_IDS

logger = logging.getLogger(__name__)


async def send_payment_notification(
    telegram_id: int,
    plan_id: str,
    plan_name: str,
    amount: int,
    status: str,
    payment_id: str = None,
    user_name: str = None,
    phone: str = None,
    payment_method: str = "Click"
):
    """
    Send payment notification to payment bot admins
    Falls back to main bot admins if payment bot not configured
    """
    
    # Determine which bot and admins to use
    if PAYMENT_BOT_TOKEN and PAYMENT_ADMIN_IDS:
        bot_token = PAYMENT_BOT_TOKEN
        admin_ids = PAYMENT_ADMIN_IDS
        logger.info("Using separate payment bot for notification")
    elif BOT_TOKEN and ADMIN_IDS:
        bot_token = BOT_TOKEN
        admin_ids = ADMIN_IDS
        logger.info("Using main bot for payment notification (payment bot not configured)")
    else:
        logger.warning("No bot configured for payment notifications")
        return
    
    # Status emoji and text
    status_info = {
        'pending': ('⏳', 'KUTILMOQDA'),
        'completed': ('✅', 'MUVAFFAQIYATLI'),
        'failed': ('❌', 'MUVAFFAQIYATSIZ'),
        'cancelled': ('🚫', 'BEKOR QILINDI')
    }
    
    emoji, status_text = status_info.get(status, ('❓', status.upper()))
    
    # Build message
    message = (
        f"{emoji} *TO'LOV XABARNOMASI*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Status:* {status_text}\n"
        f"💳 *Usul:* {payment_method}\n\n"
        f"👤 *Foydalanuvchi:*\n"
        f"├ Ism: {user_name or 'Noma\'lum'}\n"
        f"├ Telefon: {phone or 'Noma\'lum'}\n"
        f"└ Telegram ID: `{telegram_id}`\n\n"
        f"📦 *To'lov:*\n"
        f"├ Tarif: {plan_name}\n"
        f"├ Summa: *{amount:,} so'm*\n"
        f"└ Payment ID: `{payment_id or 'N/A'}`\n\n"
        f"🕐 *Vaqt:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    # Add action buttons for completed payments
    if status == 'completed':
        message += "\n\n✅ PRO obuna avtomatik aktivlashtirildi!"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with aiohttp.ClientSession() as session:
            for admin_id in admin_ids:
                try:
                    async with session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }) as response:
                        if response.status == 200:
                            logger.info(f"Payment notification sent to admin {admin_id}")
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to send payment notification to {admin_id}: {error_text}")
                except Exception as e:
                    logger.error(f"Error sending notification to admin {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in payment notification: {e}")


async def send_daily_payment_report(
    total_payments: int,
    total_amount: int,
    successful_count: int,
    failed_count: int
):
    """
    Send daily payment summary to admins
    """
    if PAYMENT_BOT_TOKEN and PAYMENT_ADMIN_IDS:
        bot_token = PAYMENT_BOT_TOKEN
        admin_ids = PAYMENT_ADMIN_IDS
    elif BOT_TOKEN and ADMIN_IDS:
        bot_token = BOT_TOKEN
        admin_ids = ADMIN_IDS
    else:
        return
    
    message = (
        f"📊 *KUNLIK TO'LOV HISOBOTI*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
        f"📈 *Statistika:*\n"
        f"├ Jami to'lovlar: {total_payments} ta\n"
        f"├ Muvaffaqiyatli: ✅ {successful_count} ta\n"
        f"├ Muvaffaqiyatsiz: ❌ {failed_count} ta\n"
        f"└ Jami summa: *{total_amount:,} so'm*\n\n"
        f"💎 HALOS Payment System"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with aiohttp.ClientSession() as session:
            for admin_id in admin_ids:
                try:
                    async with session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }) as response:
                        if response.status == 200:
                            logger.info(f"Daily report sent to admin {admin_id}")
                except Exception as e:
                    logger.error(f"Error sending daily report to {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error in daily report: {e}")
