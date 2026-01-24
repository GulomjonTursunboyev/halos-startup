"""
DEPRECATED: P2P Payment System (Card-to-card, Payme, CardXabarBot)
This file is no longer used. All payment logic is now handled via MyUzcard API.
"""
import logging
import re
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.database import get_database
from app.languages import format_number
from app.subscription import PRICING_PLANS, P2P_CONFIG, SubscriptionTier

logger = logging.getLogger(__name__)



async def get_pending_payment_by_amount(amount: int, tolerance: int = 100) -> Optional[Dict[str, Any]]:
    """Find pending payment by amount (with tolerance for rounding)"""
    now = datetime.now()
    


# ==================== PAYME API AUTO-CHECK ====================

async def check_payments_via_payme(bot) -> None:
    """
    Check pending payments via Payme API
    This runs in background and auto-confirms payments
    """
    try:
        from app.payme_api import get_payme_api, PAYME_CONFIG
        
        if not PAYME_CONFIG.get("enabled"):
            return
        
        api = await get_payme_api()
        if not api:
            return
        
        # Get all cheques
        await api.get_all_cheques({'count': 50, 'group': 'time'})
        
        now = datetime.now()
        
        # Check each pending payment
            f"└─────────────────────┘\n"
        )
        if discount > 0:
            msg += f"🎁 Chegirma: *{discount}%* qo'llanildi\n"
        msg += (
            f"\n📅 Tarif: *{plan.period.value} kunlik PRO*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📲 *QUYIDAGI KARTAGA O'TKAZING:*\n\n"
            f"🏦 Bank: *{P2P_CONFIG['bank_name']}*\n\n"
            f"💳 *Karta raqami:*\n"
            f"╔══════════════════════╗\n"
            f"║  `{P2P_CONFIG['card_number']}`  ║\n"
            f"╚══════════════════════╝\n\n"
            f"👤 *Karta egasi:*\n"
            f"    *{P2P_CONFIG['card_holder']}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *IZOH (MUHIM!):*\n"
            f"╔══════════════════════╗\n"
            f"║  `{comment_text}`  ║\n"
            f"╚══════════════════════╝\n"
            f"_To'lov izohiga shu kodni yozing!_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *MUHIM ESLATMALAR:*\n\n"
            f"• Aynan *{format_number(final_amount)} so'm* o'tkazing\n"
            f"• Izohga *{comment_text}* yozing\n"
            f"• To'lov *{P2P_CONFIG['payment_timeout_minutes']} daqiqa* ichida bo'lishi kerak\n\n"
            f"🔄 *To'lov avtomatik tekshiriladi!*"
        )
    else:
        msg = (
            f"💳 *ОПЛАТА SOLVO PRO*\n\n"
            f"📋 Номер заказа: `{payment_id}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *СУММА ОПЛАТЫ:*\n"
            f"┌─────────────────────┐\n"
            f"│   `{format_number(final_amount)} сум`   │\n"
            f"└─────────────────────┘\n"
        )
        if discount > 0:
            msg += f"🎁 Скидка: *{discount}%* применена\n"
        msg += (
            f"\n📅 Тариф: *PRO на {plan.period.value} дней*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📲 *ПЕРЕВЕДИТЕ НА КАРТУ:*\n\n"
            f"🏦 Банк: *{P2P_CONFIG['bank_name']}*\n\n"
            f"💳 *Номер карты:*\n"
            f"╔══════════════════════╗\n"
            f"║  `{P2P_CONFIG['card_number']}`  ║\n"
            f"╚══════════════════════╝\n\n"
            f"👤 *Владелец карты:*\n"
            f"    *{P2P_CONFIG['card_holder']}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *КОММЕНТАРИЙ (ВАЖНО!):*\n"
            f"╔══════════════════════╗\n"
            f"║  `{comment_text}`  ║\n"
            f"╚══════════════════════╝\n"
            f"_Укажите этот код в комментарии!_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *ВАЖНЫЕ ЗАМЕЧАНИЯ:*\n\n"
            f"• Переведите ровно *{format_number(final_amount)} сум*\n"
            f"• В комментарии укажите *{comment_text}*\n"
            f"• Оплата в течение *{P2P_CONFIG['payment_timeout_minutes']} минут*\n\n"
            f"🔄 *Оплата проверяется автоматически!*"
        )
    
    # Buttons
    keyboard = [
        [InlineKeyboardButton(
            "✅ To'ladim" if lang == "uz" else "✅ Оплатил",
            callback_data=f"p2p_confirm_{payment_id}"
        )],
        [InlineKeyboardButton(
            "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
            callback_data=f"p2p_cancel_{payment_id}"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


async def p2p_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user clicking 'I paid' button"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Extract payment_id from callback data
    payment_id = query.data.replace("p2p_confirm_", "")
    
    payment = await get_pending_payment(payment_id)
    
    if not payment:
        await query.edit_message_text(
            "❌ To'lov topilmadi yoki muddati o'tgan" if lang == "uz" 
            else "❌ Платёж не найден или истёк"
        )
        return
    
    if payment["status"] != "pending":
        await query.edit_message_text(
            "✅ Bu to'lov allaqachon tasdiqlangan" if lang == "uz"
            else "✅ Этот платёж уже подтверждён"
        )
        return
    
    # Store user's telegram_id for notification
    context.user_data["awaiting_payment_id"] = payment_id
    
    # Show waiting message with instructions for admin
    if lang == "uz":
        msg = (
            "⏳ *To'lov tekshirilmoqda...*\n\n"
            f"📋 Buyurtma: `{payment_id}`\n"
            f"💰 Summa: *{format_number(payment['final_amount'])} so'm*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔄 *To'lov avtomatik tekshiriladi*\n\n"
            "Admin @CardXabarBot dan kelgan xabarni\n"
            "botga forward qilganda to'lov tasdiqlanadi.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏱ Agar 5 daqiqa ichida tasdiqlanmasa:\n"
            "📞 Admin: @solvo_support"
        )
    else:
        msg = (
            "⏳ *Проверка оплаты...*\n\n"
            f"📋 Заказ: `{payment_id}`\n"
            f"💰 Сумма: *{format_number(payment['final_amount'])} сум*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔄 *Оплата проверяется автоматически*\n\n"
            "Когда админ пересылает сообщение от\n"
            "@CardXabarBot, оплата подтверждается.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏱ Если не подтвердится за 5 минут:\n"
            "📞 Админ: @solvo_support"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "🔄 Tekshirish" if lang == "uz" else "🔄 Проверить",
            callback_data=f"p2p_check_{payment_id}"
        )],
        [InlineKeyboardButton(
            "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
            callback_data=f"p2p_cancel_{payment_id}"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


async def p2p_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle check payment status button"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    payment_id = query.data.replace("p2p_check_", "")
    
    payment = await get_pending_payment(payment_id)
    
    if not payment:
        await query.edit_message_text(
            "❌ To'lov topilmadi" if lang == "uz" else "❌ Платёж не найден"
        )
        return
    
    if payment["status"] == "completed":
        # Payment was confirmed!
        plan = PRICING_PLANS.get(payment["plan_id"])
        expires_at = datetime.now() + timedelta(days=plan.period.value if plan else 30)
        
        if lang == "uz":
            msg = (
                "🎉 *TO'LOV TASDIQLANDI!*\n\n"
                "✅ Sizning *SOLVO PRO* obunangiz\n"
                "muvaffaqiyatli faollashtirildi!\n\n"
                f"📅 Amal qilish muddati:\n"
                f"*{expires_at.strftime('%d.%m.%Y')}*\n\n"
                "💎 Endi barcha PRO imkoniyatlaridan\n"
                "foydalanishingiz mumkin!\n\n"
                "Boshlash uchun /start buyrug'ini yuboring."
            )
        else:
            msg = (
                "🎉 *ОПЛАТА ПОДТВЕРЖДЕНА!*\n\n"
                "✅ Ваша подписка *SOLVO PRO*\n"
                "успешно активирована!\n\n"
                f"📅 Действует до:\n"
                f"*{expires_at.strftime('%d.%m.%Y')}*\n\n"
                "💎 Теперь вам доступны все\n"
                "PRO возможности!\n\n"
                "Для начала отправьте /start."
            )
        
        await query.edit_message_text(msg, parse_mode="Markdown")
    else:
        # Still pending
        if lang == "uz":
            msg = (
                "⏳ *To'lov hali tasdiqlanmagan*\n\n"
                f"📋 Buyurtma: `{payment_id}`\n"
                f"💰 Summa: *{format_number(payment['final_amount'])} so'm*\n\n"
                "Iltimos, biroz kuting yoki\n"
                "admin bilan bog'laning: @solvo_support"
            )
        else:
            msg = (
                "⏳ *Оплата ещё не подтверждена*\n\n"
                f"📋 Заказ: `{payment_id}`\n"
                f"💰 Сумма: *{format_number(payment['final_amount'])} сум*\n\n"
                "Пожалуйста, подождите или\n"
                "свяжитесь с админом: @solvo_support"
            )
        
        keyboard = [
            [InlineKeyboardButton(
                "🔄 Qayta tekshirish" if lang == "uz" else "🔄 Проверить снова",
                callback_data=f"p2p_check_{payment_id}"
            )],
            [InlineKeyboardButton(
                "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
                callback_data=f"p2p_cancel_{payment_id}"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


async def p2p_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment cancellation"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    payment_id = query.data.replace("p2p_cancel_", "")
    
    await cancel_payment(payment_id)
    
    await query.edit_message_text(
        "❌ To'lov bekor qilindi" if lang == "uz" else "❌ Платёж отменён"
    )


async def process_card_xabar_notification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Process incoming payment notification from @CardXabarBot
    This is called when admin forwards a message from CardXabarBot or
    any message containing payment information
    """
    if not update.message:
        return
    
    text = update.message.text or update.message.caption or ""
    
    # Check if message contains payment info (kirim/income indicators)
    income_indicators = [
        "kirim", "income", "+", "tushdi", "получен", "поступ", 
        "o'tkazildi", "transfer", "credited", "пополнение",
        "kartangizga", "на карту", "5614", "1731"
    ]
    is_income = any(ind.lower() in text.lower() for ind in income_indicators)
    
    if not is_income:
        logger.debug(f"Message doesn't look like income notification: {text[:50]}")
        return
    
    logger.info(f"Processing potential payment notification: {text[:100]}")
    
    # Parse the message
    parsed = parse_card_xabar_message(text)
    
    if not parsed or parsed["amount"] == 0:
        logger.warning(f"Could not parse amount from CardXabar message: {text[:100]}")
        await update.message.reply_text(
            f"⚠️ Xabar topildi, lekin summani aniqlab bo'lmadi.\n"
            f"Matn: {text[:200]}"
        )
        return
    
    amount = parsed["amount"]
    logger.info(f"Detected incoming payment: {amount} so'm")
    
    # Find matching pending payment
    payment = await get_pending_payment_by_amount(amount)
    
    if not payment:
        logger.info(f"No pending payment found for amount {amount}")
        # Notify admin about unmatched payment
        await update.message.reply_text(
            f"⚠️ *Kirim aniqlandi:* {format_number(amount)} so'm\n\n"
            f"❌ Lekin mos kutilayotgan to'lov topilmadi.\n\n"
            f"_Ehtimol foydalanuvchi hali to'lov so'ramagan yoki boshqa summa o'tkazilgan._",
            parse_mode="Markdown"
        )
        return
    
    payment_id = payment["payment_id"]
    telegram_id = payment["telegram_id"]
    
    logger.info(f"Found matching payment {payment_id} for user {telegram_id}")
    
    # Confirm the payment
    success = await confirm_payment(payment_id)
    
    if success:
        # Get plan info
        plan = PRICING_PLANS.get(payment["plan_id"])
        expires_at = datetime.now() + timedelta(days=plan.period.value if plan else 30)
        
        # Notify the user
        try:
            # Get user's language
            db = await get_database()
            user = await db.get_user(telegram_id)
            lang = user.get("language", "uz") if user else "uz"
            
            if lang == "uz":
                user_msg = (
                    "🎉 *TO'LOV QABUL QILINDI!*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "✅ Sizning *SOLVO PRO* obunangiz\n"
                    "muvaffaqiyatli faollashtirildi!\n\n"
                    f"📅 Amal qilish muddati:\n"
                    f"*{expires_at.strftime('%d.%m.%Y')}* gacha\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "💎 Endi barcha PRO imkoniyatlaridan\n"
                    "foydalanishingiz mumkin!\n\n"
                    "🚀 Boshlash uchun /start buyrug'ini yuboring."
                )
            else:
                user_msg = (
                    "🎉 *ОПЛАТА ПОЛУЧЕНА!*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "✅ Ваша подписка *SOLVO PRO*\n"
                    "успешно активирована!\n\n"
                    f"📅 Действует до:\n"
                    f"*{expires_at.strftime('%d.%m.%Y')}*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "💎 Теперь вам доступны все\n"
                    "PRO возможности!\n\n"
                    "🚀 Для начала отправьте /start."
                )
            
            await context.bot.send_message(
                chat_id=telegram_id,
                text=user_msg,
                parse_mode="Markdown"
            )
            
            # Notify admin with success
            await update.message.reply_text(
                f"✅ *TO'LOV AVTOMATIK TASDIQLANDI!*\n\n"
                f"📋 Buyurtma ID: `{payment_id}`\n"
                f"👤 Foydalanuvchi: `{telegram_id}`\n"
                f"💰 Summa: *{format_number(amount)} so'm*\n"
                f"📅 PRO: *{expires_at.strftime('%d.%m.%Y')}* gacha",
                parse_mode="Markdown"
            )
            
            logger.info(f"Payment {payment_id} auto-confirmed for user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Failed to notify user {telegram_id}: {e}")
            await update.message.reply_text(
                f"✅ To'lov tasdiqlandi!\n"
                f"⚠️ Lekin foydalanuvchiga xabar yuborishda xatolik:\n{e}"
            )
    else:
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi. Iltimos, /start bilan qayta boshlang.\n"
            f"Payment ID: {payment_id}"
        )


async def manual_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to manually confirm a payment
    Usage: /confirm_payment PAYMENT_ID
    """
    from app.config import ADMIN_IDS
    
    if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Faqat admin uchun")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /confirm_payment PAYMENT_ID")
        return
    
    payment_id = args[0].upper()
    payment = await get_pending_payment(payment_id)
    
    if not payment:
        await update.message.reply_text(f"❌ To'lov topilmadi: {payment_id}")
        return
    
    success = await confirm_payment(payment_id)
    
    if success:
        telegram_id = payment["telegram_id"]
        plan = PRICING_PLANS.get(payment["plan_id"])
        expires_at = datetime.now() + timedelta(days=plan.period.value if plan else 30)
        
        # Notify user
        try:
            db = await get_database()
            user = await db.get_user(telegram_id)
            lang = user.get("language", "uz") if user else "uz"
            
            if lang == "uz":
                user_msg = (
                    "🎉 *To'lov qabul qilindi!*\n\n"
                    f"✅ Sizning *SOLVO PRO* obunangiz faollashtirildi!\n\n"
                    f"📅 Amal qilish muddati: *{expires_at.strftime('%d.%m.%Y')}*\n\n"
                    "Endi barcha PRO imkoniyatlaridan foydalanishingiz mumkin! 💎"
                )
            else:
                user_msg = (
                    "🎉 *Оплата получена!*\n\n"
                    f"✅ Ваша подписка *SOLVO PRO* активирована!\n\n"
                    f"📅 Действует до: *{expires_at.strftime('%d.%m.%Y')}*\n\n"
                    "Теперь вам доступны все PRO возможности! 💎"
                )
            
            await context.bot.send_message(
                chat_id=telegram_id,
                text=user_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
        
        await update.message.reply_text(
            f"✅ To'lov tasdiqlandi!\n"
            f"👤 User: {telegram_id}\n"
            f"💰 Summa: {format_number(payment['final_amount'])} so'm"
        )
    else:
        await update.message.reply_text(f"❌ Xatolik: {payment_id}")


async def list_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to list all pending payments
    Usage: /pending_payments
    """
    from app.config import ADMIN_IDS
    
    if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Faqat admin uchun")
        return
    
    now = datetime.now()
    pending = []
    
    for pid, payment in PENDING_PAYMENTS.items():
        if payment["status"] == "pending" and payment["expires_at"] > now:
            pending.append({
                "id": pid,
                "telegram_id": payment["telegram_id"],
                "amount": payment["final_amount"],
                "created": payment["created_at"],
                "expires": payment["expires_at"]
            })
    
    if not pending:
        await update.message.reply_text("📋 Kutilayotgan to'lovlar yo'q")
        return
    
    msg = "📋 *KUTILAYOTGAN TO'LOVLAR:*\n\n"
    
    for i, p in enumerate(pending, 1):
        minutes_left = int((p["expires"] - now).total_seconds() / 60)
        msg += (
            f"{i}. ID: `{p['id']}`\n"
            f"   👤 User: `{p['telegram_id']}`\n"
            f"   💰 Summa: *{format_number(p['amount'])} so'm*\n"
            f"   ⏱ Qoldi: {minutes_left} daqiqa\n\n"
        )
    
    msg += f"\n_Tasdiqlash: /confirm\\_payment ID_"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin commands help"""
    from app.config import ADMIN_IDS
    
    if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
        return
    
    # Check Payme status
    payme_status = "❌ O'chirilgan"
    try:
        from app.payme_api import PAYME_CONFIG
        if PAYME_CONFIG.get("enabled"):
            payme_status = "✅ Yoqilgan"
    except:
        pass
    
    msg = (
        "🔧 *ADMIN BUYRUQLARI:*\n\n"
        "📋 /pending\\_payments - Kutilayotgan to'lovlar\n"
        "✅ /confirm\\_payment ID - To'lovni tasdiqlash\n"
        "⚙️ /payme\\_setup - Payme API sozlash\n"
        "📊 /payme\\_status - Payme API holati\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔄 *PAYME API:* {payme_status}\n\n"
        "Payme API yoqilgan bo'lsa, to'lovlar\n"
        "avtomatik tekshiriladi va tasdiqlanadi.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 *QOLDA TASDIQLASH:*\n\n"
        "@CardXabarBot dan kelgan xabarni\n"
        "shu botga forward qiling yoki\n"
        "to'lov summani yozing:\n"
        "`15000 kirim`"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def payme_setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to setup Payme API"""
    from app.config import ADMIN_IDS
    
    if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Faqat admin uchun")
        return
    
    msg = (
        "⚙️ *PAYME API SOZLASH*\n\n"
        "Payme API orqali to'lovlar avtomatik\n"
        "tekshiriladi va tasdiqlanadi.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 *SOZLASH BOSQICHLARI:*\n\n"
        "1️⃣ `app/payme_api.py` faylini oching\n\n"
        "2️⃣ `PAYME_CONFIG` ni to'ldiring:\n"
        "```python\n"
        "PAYME_CONFIG = {\n"
        '    "enabled": True,\n'
        '    "login": "901234567",  # Payme raqam\n'
        '    "password": "parol",   # Payme parol\n'
        '    "device_id": "",       # 3-bosqichda\n'
        '    "card_id": "",         # 3-bosqichda\n'
        "}\n"
        "```\n\n"
        "3️⃣ Device ID va Card ID olish:\n"
        "   `/payme_register` buyrug'ini ishlating\n\n"
        "4️⃣ Botni qayta ishga tushiring\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ *MUHIM:*\n"
        "- Payme akkauntingizga kartangizni ulang\n"
        "- Device ID bir marta olinadi\n"
        "- SMS kod kerak bo'ladi"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def payme_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to check Payme API status"""
    from app.config import ADMIN_IDS
    
    if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Faqat admin uchun")
        return
    
    try:
        from app.payme_api import PAYME_CONFIG, get_payme_api
        
        if not PAYME_CONFIG.get("enabled"):
            await update.message.reply_text(
                "❌ *Payme API o'chirilgan*\n\n"
                "Sozlash: /payme\\_setup",
                parse_mode="Markdown"
            )
            return
        
        # Try to get API and check connection
        api = await get_payme_api()
        if api:
            # Try to login
            try:
                await api.login()
                status = "✅ Ulangan"
            except Exception as e:
                status = f"⚠️ Xatolik: {str(e)[:50]}"
        else:
            status = "❌ API mavjud emas"
        
        msg = (
            "📊 *PAYME API HOLATI*\n\n"
            f"🔌 Status: {status}\n"
            f"📱 Login: `{PAYME_CONFIG.get('login', 'N/A')}`\n"
            f"🔑 Device: `{PAYME_CONFIG.get('device_id', 'N/A')[:20]}...`\n"
            f"💳 Card: `{PAYME_CONFIG.get('card_id', 'N/A')[:20]}...`\n"
            f"⏱ Interval: {PAYME_CONFIG.get('check_interval_seconds', 30)}s\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 Kutilayotgan to'lovlar: {len([p for p in PENDING_PAYMENTS.values() if p['status'] == 'pending'])}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except ImportError:
        await update.message.reply_text(
            "❌ Payme API moduli topilmadi\n\n"
            "Sozlash: /payme\\_setup",
            parse_mode="Markdown"
        )

