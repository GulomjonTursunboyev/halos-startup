"""
HALOS Telegram Payments Integration
Uses Telegram Bot API for payments via Click Terminal
"""
import os
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.database import get_database
from app.subscription import PRICING_PLANS

logger = logging.getLogger(__name__)

# Click Terminal Provider Token (from @BotFather)
# Test: 398062629:TEST:999999999_F91D8F69C042267444B74CC0B3C747757EB0E065
# Live: 333605228:LIVE:13464_31ACF1A3C571667379481B13BEDCCA774AEBA199
CLICK_PROVIDER_TOKEN = os.getenv(
    "CLICK_PROVIDER_TOKEN", 
    "333605228:LIVE:13464_31ACF1A3C571667379481B13BEDCCA774AEBA199"
)

# Check if we're in test mode
IS_TEST_MODE = ":TEST:" in CLICK_PROVIDER_TOKEN


async def send_payment_invoice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    plan_id: str
) -> None:
    """
    Send payment invoice to user using Telegram Payments API
    
    Args:
        update: Telegram update
        context: Bot context
        plan_id: Plan ID (pro_weekly, pro_monthly, etc.)
    """
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Get plan details
    if plan_id not in PRICING_PLANS:
        if query:
            await query.answer("❌ Plan not found", show_alert=True)
        return
    
    plan = PRICING_PLANS[plan_id]
    
    # Telegram Payments uses smallest currency unit (tiyin for UZS)
    # 1 UZS = 100 tiyin
    amount_tiyin = int(plan.price_uzs * 100)
    
    # Create short invoice payload: h_{user_id}_{plan_short}_{time}
    plan_short = plan_id.replace("pro_", "")[:3]  # weekly->wee, monthly->mon, yearly->yea
    payload = f"h_{telegram_id}_{plan_short}_{datetime.now().strftime('%m%d%H%M')}"
    
    # Invoice details - short and clear
    duration_days = plan.period.value
    
    # Short plan names
    if "weekly" in plan_id:
        period_name_uz, period_name_ru = "1 hafta", "1 неделя"
    elif "monthly" in plan_id:
        period_name_uz, period_name_ru = "1 oy", "1 месяц"
    else:
        period_name_uz, period_name_ru = "1 yil", "1 год"
    
    if lang == "uz":
        title = "HALOS PRO"
        description = (
            f"⏱ {period_name_uz} ({duration_days} kun)\n\n"
            "✨ Barcha PRO imkoniyatlar"
        )
        price_label = f"PRO {period_name_uz}"
    else:
        title = "HALOS PRO"
        description = (
            f"⏱ {period_name_ru} ({duration_days} дней)\n\n"
            "✨ Все PRO возможности"
        )
        price_label = f"PRO {period_name_ru}"
    
    # Price labels
    prices = [
        LabeledPrice(
            label=price_label,
            amount=amount_tiyin
        )
    ]
    
    # Send invoice
    try:
        chat_id = update.effective_chat.id
        
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=CLICK_PROVIDER_TOKEN,
            currency="UZS",
            prices=prices,
            start_parameter=f"pro{plan_short}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
        )
        
        logger.info(f"Invoice sent to user {telegram_id} for plan {plan_id}, amount: {plan.price_uzs} UZS")
        
    except Exception as e:
        logger.error(f"Failed to send invoice: {e}")
        
        error_msg = (
            "❌ To'lov tizimida xatolik yuz berdi.\n"
            "Iltimos, keyinroq urinib ko'ring."
        ) if lang == "uz" else (
            "❌ Ошибка платежной системы.\n"
            "Пожалуйста, попробуйте позже."
        )
        
        if query:
            await query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle pre-checkout query - MUST respond within 10 seconds!
    Keep this handler EXTREMELY FAST - just approve immediately!
    """
    query = update.pre_checkout_query
    
    # IMMEDIATELY approve - no checks, no delays!
    # All validation will be done in successful_payment_handler
    await query.answer(ok=True)
    
    logger.info(f"Pre-checkout approved for user {query.from_user.id}")


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle successful payment - activate PRO subscription
    """
    message = update.message
    payment = message.successful_payment
    
    # Get telegram_id from the actual user who paid
    telegram_id = update.effective_user.id
    
    logger.info(f"Payment received from user {telegram_id}: {payment.total_amount} {payment.currency}")
    
    try:
        # Parse payload: h_{user_id}_{plan_short}_{time}
        payload = payment.invoice_payload
        parts = payload.split('_')
        
        plan_short = parts[2] if len(parts) > 2 else 'mon'
        
        # Convert short to full plan_id
        plan_map = {'wee': 'pro_weekly', 'mon': 'pro_monthly', 'yea': 'pro_yearly'}
        plan_id = plan_map.get(plan_short, 'pro_monthly')
        
        logger.info(f"Plan detected: {plan_id} from payload: {payload}")
        
        # Get plan details
        plan = PRICING_PLANS.get(plan_id)
        if not plan:
            logger.error(f"Plan not found: {plan_id}")
            await message.reply_text("❌ Tarif topilmadi. Admin bilan bog'laning: @halos_support")
            return
        
        # Calculate subscription expiration
        now = datetime.now()
        duration_days = plan.period.value
        expires = now + timedelta(days=duration_days)
        
        logger.info(f"Activating PRO for user {telegram_id}, expires: {expires}")
        
        # Get database
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            logger.error(f"User not found: {telegram_id}")
            await message.reply_text("❌ Foydalanuvchi topilmadi. /start bosing va qayta urinib ko'ring.")
            return
        
        # Activate PRO subscription
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
        
        logger.info(f"PRO subscription updated in database for user {telegram_id}")
        
        # Record payment
        try:
            await db.execute_update(
                """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status, completed_at)
                   VALUES ($1, $2, $3, 'telegram_click', $4, 'completed', $5)""" if db.is_postgres else
                """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status, completed_at)
                   VALUES (?, ?, ?, 'telegram_click', ?, 'completed', ?)""",
                user['id'], plan_id, plan.price_uzs, payment.telegram_payment_charge_id, now
            )
            logger.info(f"Payment recorded: {payment.telegram_payment_charge_id}")
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            # Continue anyway - PRO is already activated
        
        # Get user language
        lang = user.get("language", "uz")
        
        # Send success message
        if lang == "uz":
            success_msg = (
                "🎉 *TABRIKLAYMIZ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ *HALOS PRO muvaffaqiyatli aktivlashtirildi!*\n\n"
                f"📦 Tarif: *{plan.description_uz}*\n"
                f"💰 To'landi: *{plan.price_uzs:,} so'm*\n"
                f"📅 Amal qilish: *{expires.strftime('%d.%m.%Y')}* gacha\n\n"
                "🌟 *Sizning yangi imkoniyatlaringiz:*\n"
                "├ 🗓 HALOS sanangiz\n"
                "├ ⚡ Tezkor qutilish rejasi\n"
                "├ 💰 Shaxsiy kapital hisoblash\n"
                "├ 🎤 Ovozli AI yordamchi\n"
                "├ 📊 Batafsil statistika\n"
                "├ 🔔 Aqlli eslatmalar\n"
                "└ 📥 Excel hisobot\n\n"
                "🚀 /start bosing va boshlaymiz!"
            )
        else:
            success_msg = (
                "🎉 *ПОЗДРАВЛЯЕМ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ *HALOS PRO успешно активирован!*\n\n"
                f"📦 Тариф: *{plan.description_ru}*\n"
                f"💰 Оплачено: *{plan.price_uzs:,} сум*\n"
                f"📅 Действует до: *{expires.strftime('%d.%m.%Y')}*\n\n"
                "🌟 *Ваши новые возможности:*\n"
                "├ 🗓 Дата HALOS\n"
                "├ ⚡ Быстрый план погашения\n"
                "├ 💰 Расчет личного капитала\n"
                "├ 🎤 Голосовой AI помощник\n"
                "├ 📊 Детальная статистика\n"
                "├ 🔔 Умные напоминания\n"
                "└ 📥 Excel отчет\n\n"
                "🚀 Нажмите /start и начнем!"
            )
        
        keyboard = [[InlineKeyboardButton(
            "🏠 Bosh menyu" if lang == "uz" else "🏠 Главное меню",
            callback_data="main_menu"
        )]]
        
        await message.reply_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"PRO activated via Telegram Payments: user={telegram_id}, plan={plan_id}, expires={expires}")
        
        # Send admin notification (optional)
        await send_admin_payment_notification(
            telegram_id=telegram_id,
            user_name=user.get('first_name'),
            plan_id=plan_id,
            amount=plan.price_uzs,
            payment_id=payment.telegram_payment_charge_id
        )
        
    except Exception as e:
        logger.error(f"Error processing successful payment: {e}")
        await message.reply_text(
            "✅ To'lov qabul qilindi!\n"
            "⚠️ PRO aktivatsiyada xatolik. Admin bilan bog'laning: @halos_support"
        )


async def send_admin_payment_notification(
    telegram_id: int,
    user_name: str,
    plan_id: str,
    amount: float,
    payment_id: str
):
    """Send notification to admin about successful payment"""
    try:
        from app.config import ADMIN_IDS, BOT_TOKEN
        import aiohttp
        
        if not ADMIN_IDS:
            return
        
        plan = PRICING_PLANS.get(plan_id)
        plan_name = plan.description_uz if plan else plan_id
        
        message = (
            "💰 *YANGI TO'LOV!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Foydalanuvchi: *{user_name or 'N/A'}*\n"
            f"🆔 Telegram ID: `{telegram_id}`\n\n"
            f"📦 Tarif: *{plan_name}*\n"
            f"💵 Summa: *{amount:,} so'm*\n"
            f"🔑 Payment ID: `{payment_id}`\n\n"
            f"🕐 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'🧪 TEST MODE' if IS_TEST_MODE else '✅ LIVE MODE'}"
        )
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        async with aiohttp.ClientSession() as session:
            for admin_id in ADMIN_IDS:
                try:
                    async with session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }) as response:
                        if response.status != 200:
                            logger.error(f"Failed to notify admin {admin_id}")
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Admin notification error: {e}")


# ==================== TELEGRAM PAY CALLBACK ====================

async def telegram_pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Telegram Pay button click - send invoice
    callback_data format: tg_pay_{plan_id}
    """
    query = update.callback_query
    await query.answer()
    
    # Extract plan_id from callback data
    plan_id = query.data.replace("tg_pay_", "")
    
    # Delete the message with buttons
    try:
        await query.message.delete()
    except:
        pass
    
    # Send invoice
    await send_payment_invoice(update, context, plan_id)
