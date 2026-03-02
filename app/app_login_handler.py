"""
App Login Handler for HALOS Bot
Handles mobile app authentication via Telegram
"""
import httpx
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import os

logger = logging.getLogger(__name__)

# API Base URL for mobile app backend
API_URL = os.getenv("AUTH_API_URL", "http://halos-api:8000/api/auth")


async def handle_app_login(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    """
    Handle login request from mobile app
    Called when user opens bot with start=login_xxx parameter
    """
    user = update.effective_user
    
    # Show confirmation message
    keyboard = [
        [
            InlineKeyboardButton(" Tasdiqlash", callback_data=f"app_login_confirm:{session_id}"),
            InlineKeyboardButton(" Bekor qilish", callback_data="app_login_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f" *HALOS ilovasiga kirish*\n\n"
        f"Salom, {user.first_name}! \n\n"
        f"Siz HALOS mobil ilovasiga kirmoqchisiz.\n"
        f"Telegram hisobingiz bilan kirishni tasdiqlaysizmi?\n\n"
        f" Bu amal sizning barcha ma'lumotlaringizni mobil ilovada ko'rsatadi.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def app_login_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Confirm app login - send user data to API
    """
    query = update.callback_query
    await query.answer()
    
    # Extract session_id from callback data
    session_id = query.data.split(":")[1]
    user = update.effective_user
    
    try:
        # Call API to confirm login session
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_URL}/telegram/session/{session_id}/confirm",
                json={
                    "telegram_id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "telegram_username": user.username
                }
            )
            
            if response.status_code == 200:
                await query.edit_message_text(
                    " *Kirish tasdiqlandi!*\n\n"
                    "Endi mobil ilovaga qaytishingiz mumkin.\n"
                    "Ilova avtomatik tarzda sizni tizimga kiritadi.\n\n"
                    " HALOS ilovasidan foydalanganingiz uchun rahmat!",
                    parse_mode="Markdown"
                )
            elif response.status_code == 404:
                await query.edit_message_text(
                    " *Sessiya topilmadi*\n\n"
                    "Kirish sessiyasi muddati tugagan yoki noto'g'ri.\n"
                    "Iltimos, ilovada qaytadan urinib ko'ring.",
                    parse_mode="Markdown"
                )
            elif response.status_code == 410:
                await query.edit_message_text(
                    " *Vaqt tugadi*\n\n"
                    "Kirish sessiyasi muddati tugagan.\n"
                    "Iltimos, ilovada qaytadan urinib ko'ring.",
                    parse_mode="Markdown"
                )
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                await query.edit_message_text(
                    " *Xatolik yuz berdi*\n\n"
                    "Iltimos, keyinroq qaytadan urinib ko'ring.",
                    parse_mode="Markdown"
                )
                
    except httpx.TimeoutException:
        await query.edit_message_text(
            " *Server javob bermadi*\n\n"
            "Iltimos, keyinroq qaytadan urinib ko'ring.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"App login error: {e}")
        await query.edit_message_text(
            " *Xatolik yuz berdi*\n\n"
            f"Xato: {str(e)}\n"
            "Iltimos, keyinroq qaytadan urinib ko'ring.",
            parse_mode="Markdown"
        )


async def app_login_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel app login request
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        " *Kirish bekor qilindi*\n\n"
        "Mobil ilovaga kirish bekor qilindi.\n"
        "Istalgan vaqt qaytadan urinishingiz mumkin.",
        parse_mode="Markdown"
    )





