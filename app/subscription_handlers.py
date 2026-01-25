"""
HALOS Subscription Handlers
Click Payment Integration
"""
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.database import get_database
from app.languages import get_message, format_number
from app.subscription import (
    PRICING_PLANS,
    FEATURE_LIMITS,
    SubscriptionTier,
    validate_promo_code,
)
from app.click_payment import generate_click_payment_url

logger = logging.getLogger(__name__)


# ==================== SUBSCRIPTION STATUS ====================

async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /subscription command - show subscription status"""
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await update.message.reply_text(
            get_message("error_not_registered", lang)
        )
        return
    
    # Get subscription info
    tier = user.get("subscription_tier", "free")
    expires = user.get("subscription_expires")
    
    if tier == "free":
        tier_name = get_message("subscription_free", lang)
        expires_info = ""
    else:
        tier_name = get_message("subscription_pro", lang)
        if expires:
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires)
            expires_info = get_message("subscription_expires", lang).format(
                date=expires.strftime("%d.%m.%Y")
            )
        else:
            expires_info = ""
    
    # Build status message
    status_msg = get_message("subscription_status", lang).format(
        name=user.get("first_name", ""),
        phone=user.get("phone_number", ""),
        tier=tier_name,
        expires_info=expires_info
    )
    
    # Add buttons
    if tier == "free":
        keyboard = [
            [InlineKeyboardButton(
                get_message("btn_upgrade_pro", lang),
                callback_data="show_pricing"
            )]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(
                get_message("referral_info", lang)[:20] + "...",
                callback_data="show_referral"
            )]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        status_msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ==================== PRICING DISPLAY ====================

async def show_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE, is_required: bool = False) -> None:
    """Show pricing options for Click payment
    
    Args:
        is_required: If True, shows that subscription is required to use the bot
    """
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Get user's debt info for personalization
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = None
    simple_months = 0
    pro_months = 0
    months_saved = 0
    savings_at_exit = 0
    
    if user:
        profile = await db.get_financial_profile(user["id"])
        if profile:
            total_debt = profile.get("total_debt", 0)
            loan_payment = profile.get("loan_payment", 0)
            
            if loan_payment > 0 and total_debt > 0:
                import math
                # Simple calculation (just paying minimum)
                simple_months = math.ceil(total_debt / loan_payment)
                
                # PRO calculation (with acceleration)
                income = profile.get("income_self", 0) + profile.get("income_partner", 0)
                mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
                free_cash = income - mandatory - loan_payment
                
                if free_cash > 0:
                    accelerated_debt = free_cash * 0.2  # 20% extra to debt
                    total_payment = loan_payment + accelerated_debt
                    pro_months = math.ceil(total_debt / total_payment)
                    months_saved = simple_months - pro_months
                    savings_at_exit = (free_cash * 0.1) * pro_months  # 10% savings
    
    if lang == "uz":
        # Personalized header if user has debt data
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO*\n\n"
                f"Hozirgi yo'lingiz bilan *{simple_months} oy*da yengillik.\n"
                f"PRO bilan *{pro_months} oy*da — *{months_saved} oy tezroq!*\n"
                f"Bundan tashqari *{format_number(int(savings_at_exit))} so'm* shaxsiy kapital.\n\n"
            )
        else:
            header = "💎 *HALOS PRO*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *PRO BILAN SIZ OLASIZ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *HALOS sanangiz* — erkinlik sanasini bilasiz\n"
            "✅ *Tezroq yengillik* — bir necha oy oldin\n"
            "✅ *Shaxsiy kapital* — yuk to'layotganda ham\n\n"
            "📊 *Statistika* — haftalik/oylik/yillik\n"
            "🔔 *Eslatmalar* — to'lov eslatmalari\n"
            "📋 *Nazorat* — monitoring\n"
            "📥 *Excel hisobot* — yuklab olish\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *NARXLAR:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 hafta:* `4,990 so'm` — sinab ko'ring\n"
            "├ ⭐ *1 oy:* `14,990 so'm` — tavsiya etiladi\n"
            "└ 🏆 *1 yil:* `119,990 so'm` (33% tejash)\n\n"
            "💳 *To'lov: Click orqali*"
        )
    else:
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO*\n\n"
                f"Обычным путём свобода через *{simple_months} мес*.\n"
                f"С PRO за *{pro_months} мес* — *на {months_saved} мес быстрее!*\n"
                f"Плюс *{format_number(int(savings_at_exit))} сум* личного капитала.\n\n"
            )
        else:
            header = "💎 *HALOS PRO*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *С PRO ВЫ ПОЛУЧИТЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Дата HALOS* — знаете когда станете свободны\n"
            "✅ *Быстрее к лёгкости* — на несколько мес раньше\n"
            "✅ *Личный капитал* — растёт даже выплачивая бремя\n\n"
            "📊 *Статистика* — еженед/ежемес/ежегод\n"
            "🔔 *Напоминания* — об оплате\n"
            "📋 *Контроль* — мониторинг\n"
            "📥 *Excel отчёт* — скачать\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ЦЕНЫ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 неделя:* `4,990 сум` — попробуйте\n"
            "├ ⭐ *1 месяц:* `14,990 сум` — рекомендуем\n"
            "└ 🏆 *1 год:* `119,990 сум` (скидка 33%)\n\n"
            "💳 *Оплата: через Click*"
        )
    
    # Click Payment buttons
    keyboard = [
        [InlineKeyboardButton(
            "⚡ 1 hafta - 5,000 so'm" if lang == "uz" else "⚡ 1 нед - 5,000 сум",
            callback_data="click_buy_pro_weekly"
        )],
        [InlineKeyboardButton(
            "⭐ 1 oy - 15,000 so'm (tavsiya)" if lang == "uz" else "⭐ 1 мес - 15,000 сум (реком.)",
            callback_data="click_buy_pro_monthly"
        )],
        [InlineKeyboardButton(
            "🏆 1 yil - 120,000 so'm (-33%)" if lang == "uz" else "🏆 1 год - 120,000 сум (-33%)",
            callback_data="click_buy_pro_yearly"
        )],
        [InlineKeyboardButton(
            "🎁 Promo-kod" if lang == "uz" else "🎁 Промо-код",
            callback_data="enter_promo"
        )],
    ]
    
    # Only show back button if not required (i.e., user came here voluntarily)
    if not is_required:
        keyboard.append([InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


async def show_pricing_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE, is_required: bool = False) -> None:
    """Show pricing options as a NEW message (not editing existing)
    
    Use this when you can't edit the previous message (e.g., after deleting it)
    """
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Get user's debt info for personalization
    db = await get_database()
    user = await db.get_user(telegram_id)
    simple_months = 0
    pro_months = 0
    months_saved = 0
    savings_at_exit = 0
    
    if user:
        profile = await db.get_financial_profile(user["id"])
        if profile:
            total_debt = profile.get("total_debt", 0)
            loan_payment = profile.get("loan_payment", 0)
            
            if loan_payment > 0 and total_debt > 0:
                import math
                simple_months = math.ceil(total_debt / loan_payment)
                
                income = profile.get("income_self", 0) + profile.get("income_partner", 0)
                mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
                free_cash = income - mandatory - loan_payment
                
                if free_cash > 0:
                    accelerated_debt = free_cash * 0.2
                    total_payment = loan_payment + accelerated_debt
                    pro_months = math.ceil(total_debt / total_payment)
                    months_saved = simple_months - pro_months
                    savings_at_exit = (free_cash * 0.1) * pro_months
    
    if lang == "uz":
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO*\n\n"
                f"Hozirgi yo'lingiz bilan *{simple_months} oy*da yengillik.\n"
                f"PRO bilan *{pro_months} oy*da — *{months_saved} oy tezroq!*\n"
                f"Bundan tashqari *{format_number(int(savings_at_exit))} so'm* shaxsiy kapital.\n\n"
            )
        else:
            header = "💎 *HALOS PRO*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *PRO BILAN SIZ OLASIZ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *HALOS sanangiz* — erkinlik sanasini bilasiz\n"
            "✅ *Tezroq yengillik* — bir necha oy oldin\n"
            "✅ *Shaxsiy kapital* — yuk to'layotganda ham\n\n"
            "📊 *Statistika* — haftalik/oylik/yillik\n"
            "🔔 *Eslatmalar* — to'lov eslatmalari\n"
            "📋 *Nazorat* — monitoring\n"
            "📥 *Excel hisobot* — yuklab olish\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *NARXLAR:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 hafta:* `4,990 so'm` — sinab ko'ring\n"
            "├ ⭐ *1 oy:* `14,990 so'm` — tavsiya etiladi\n"
            "└ 🏆 *1 yil:* `119,990 so'm` (33% tejash)\n\n"
            "💳 *To'lov: Click orqali*"
        )
    else:
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO*\n\n"
                f"Обычным путём свобода через *{simple_months} мес*.\n"
                f"С PRO за *{pro_months} мес* — *на {months_saved} мес быстрее!*\n"
                f"Плюс *{format_number(int(savings_at_exit))} сум* личного капитала.\n\n"
            )
        else:
            header = "💎 *HALOS PRO*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *С PRO ВЫ ПОЛУЧИТЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Дата HALOS* — знаете когда станете свободны\n"
            "✅ *Быстрее к лёгкости* — на несколько мес раньше\n"
            "✅ *Личный капитал* — растёт даже выплачивая бремя\n\n"
            "📊 *Статистика* — еженед/ежемес/ежегод\n"
            "🔔 *Напоминания* — об оплате\n"
            "📋 *Контроль* — мониторинг\n"
            "📥 *Excel отчёт* — скачать\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ЦЕНЫ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 неделя:* `4,990 сум` — попробуйте\n"
            "├ ⭐ *1 месяц:* `14,990 сум` — рекомендуем\n"
            "└ 🏆 *1 год:* `119,990 сум` (скидка 33%)\n\n"
            "💳 *Оплата: через Click*"
        )
    
    # Click Payment buttons
    keyboard = [
        [InlineKeyboardButton(
            "⚡ 1 hafta - 4,990 so'm" if lang == "uz" else "⚡ 1 нед - 4,990 сум",
            callback_data="click_buy_pro_weekly"
        )],
        [InlineKeyboardButton(
            "⭐ 1 oy - 14,990 so'm (tavsiya)" if lang == "uz" else "⭐ 1 мес - 14,990 сум (реком.)",
            callback_data="click_buy_pro_monthly"
        )],
        [InlineKeyboardButton(
            "🏆 1 yil - 119,990 so'm (-33%)" if lang == "uz" else "🏆 1 год - 119,990 сум (-33%)",
            callback_data="click_buy_pro_yearly"
        )],
        [InlineKeyboardButton(
            "🎁 Promo-kod" if lang == "uz" else "🎁 Промо-код",
            callback_data="enter_promo"
        )],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Always send as new message
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pro command - show pricing"""
    await show_pricing(update, context)


async def show_pricing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show_pricing callback button - wrapper for show_pricing"""
    await show_pricing(update, context, is_required=False)


# ==================== CLICK PAYMENT HANDLER ====================

async def click_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Click payment button click - show payment link"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("click_buy_", "")  # pro_monthly, pro_quarterly, pro_yearly
    lang = context.user_data.get("lang", "uz")

    if plan_id not in PRICING_PLANS:
        await query.answer("❌ Plan not found", show_alert=True)
        return

    plan = PRICING_PLANS[plan_id]
    amount = plan.price_uzs
    order_id = f"halos_{update.effective_user.id}_{plan_id}"
    return_url = "https://t.me/HalosRobot"  # Redirect back to bot after payment
    
    click_url = generate_click_payment_url(
        amount=amount, 
        order_id=order_id, 
        return_url=return_url, 
        description=plan.description_uz
    )

    if lang == "uz":
        msg = (
            f"💳 *Click orqali to'lov*\n\n"
            f"📦 Tarif: *{plan.description_uz}*\n"
            f"💰 Narx: *{amount:,} so'm*\n\n"
            f"👇 Quyidagi tugmani bosing va Click orqali to'lovni amalga oshiring.\n\n"
            f"✅ To'lovdan so'ng PRO imkoniyatlar *darhol* ochiladi!"
        )
        pay_btn = "💳 Click orqali to'lash"
        back_btn = "◀️ Orqaga"
    else:
        msg = (
            f"💳 *Оплата через Click*\n\n"
            f"📦 Тариф: *{plan.description_ru}*\n"
            f"💰 Цена: *{amount:,} сум*\n\n"
            f"👇 Нажмите кнопку ниже и оплатите через Click.\n\n"
            f"✅ После оплаты PRO откроется *мгновенно*!"
        )
        pay_btn = "💳 Оплатить через Click"
        back_btn = "◀️ Назад"

    keyboard = [
        [InlineKeyboardButton(pay_btn, url=click_url)],
        [InlineKeyboardButton(back_btn, callback_data="show_pricing")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        msg, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=reply_markup
    )


# ==================== PROMO CODE ====================

async def enter_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle promo code entry"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Set state for promo code input
    context.user_data["awaiting_promo"] = True
    
    if lang == "uz":
        msg = (
            "🎁 *Promo-kod kiritish*\n\n"
            "Agar sizda promo-kod bo'lsa, uni kiriting:\n\n"
            "Misol: `HALOS2024`"
        )
    else:
        msg = (
            "🎁 *Ввод промо-кода*\n\n"
            "Если у вас есть промо-код, введите его:\n\n"
            "Пример: `HALOS2024`"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
            callback_data="cancel_promo"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


async def handle_promo_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle promo code text input, returns True if handled"""
    if not context.user_data.get("awaiting_promo"):
        return False
    
    lang = context.user_data.get("lang", "uz")
    code = update.message.text.strip().upper()
    
    context.user_data["awaiting_promo"] = False
    
    # Validate promo code
    promo = validate_promo_code(code)
    
    if not promo:
        await update.message.reply_text(
            "❌ Noto'g'ri promo-kod" if lang == "uz" else "❌ Неверный промо-код"
        )
        return True
    
    if promo["type"] == "discount":
        discount = promo["value"]
        context.user_data["promo_discount"] = discount
        context.user_data["promo_code"] = code
        
        if lang == "uz":
            msg = (
                f"✅ *Promo-kod qabul qilindi!*\n\n"
                f"🎁 Chegirma: *{discount}%*\n\n"
                f"Endi tarifni tanlang:"
            )
        else:
            msg = (
                f"✅ *Промо-код принят!*\n\n"
                f"🎁 Скидка: *{discount}%*\n\n"
                f"Теперь выберите тариф:"
            )
        
        keyboard = [
            [InlineKeyboardButton(
                "📅 1 oy" if lang == "uz" else "📅 1 мес",
                callback_data="click_buy_pro_monthly"
            )],
            [InlineKeyboardButton(
                "📅 3 oy" if lang == "uz" else "📅 3 мес",
                callback_data="click_buy_pro_quarterly"
            )],
            [InlineKeyboardButton(
                "📅 1 yil" if lang == "uz" else "📅 1 год",
                callback_data="click_buy_pro_yearly"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    
    elif promo["type"] == "free_days":
        days = promo["value"]
        telegram_id = update.effective_user.id
        
        # Activate free days
        expires_at = datetime.now() + timedelta(days=days)
        
        db = await get_database()
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users 
                    SET subscription_tier = 'pro',
                        subscription_expires = $1,
                        subscription_plan = 'promo',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = $2
                """, expires_at, telegram_id)
        else:
            await db._connection.execute("""
                UPDATE users 
                SET subscription_tier = 'pro',
                    subscription_expires = ?,
                    subscription_plan = 'promo',
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (expires_at.isoformat(), telegram_id))
            await db._connection.commit()
        
        if lang == "uz":
            msg = (
                f"🎉 *Promo-kod faollashtirildi!*\n\n"
                f"✅ Sizga *{days} kun* bepul PRO berildi!\n\n"
                f"📅 Amal qilish muddati: *{expires_at.strftime('%d.%m.%Y')}*"
            )
        else:
            msg = (
                f"🎉 *Промо-код активирован!*\n\n"
                f"✅ Вам подарено *{days} дней* PRO бесплатно!\n\n"
                f"📅 Действует до: *{expires_at.strftime('%d.%m.%Y')}*"
            )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    return True


async def cancel_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel promo code entry"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["awaiting_promo"] = False
    
    # Return to pricing
    await show_pricing(update, context)


# ==================== FEATURE ACCESS CHECK ====================

async def is_user_pro(telegram_id: int) -> bool:
    """Check if user has active PRO subscription"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return False
    
    tier = user.get("subscription_tier", "free")
    expires = user.get("subscription_expires")
    
    if tier == "free":
        return False
    
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if datetime.now() > expires:
            return False
    
    return True


async def require_pro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if user has PRO access. If not, show subscription required message.
    Returns True if user has PRO, False otherwise.
    This is the main gate - bot CANNOT be used without active subscription.
    """
    telegram_id = update.effective_user.id
    
    if await is_user_pro(telegram_id):
        return True
    
    # User doesn't have PRO - show subscription required with pricing
    await show_pricing(update, context, is_required=True)
    return False


async def get_subscription_days_left(telegram_id: int) -> int:
    """Get remaining days of subscription, -1 if expired or no subscription"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return -1
    
    tier = user.get("subscription_tier", "free")
    expires = user.get("subscription_expires")
    
    if tier == "free" or not expires:
        return -1
    
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    
    days_left = (expires - datetime.now()).days
    return max(0, days_left)


async def show_subscription_expiring_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show warning if subscription is expiring soon (3 days or less)"""
    telegram_id = update.effective_user.id
    days_left = await get_subscription_days_left(telegram_id)
    
    if days_left <= 0 or days_left > 3:
        return
    
    lang = context.user_data.get("lang", "uz")
    
    if lang == "uz":
        if days_left == 0:
            msg = "⚠️ *Obunangiz bugun tugaydi!* Davom etish uchun yangilang 👇"
        elif days_left == 1:
            msg = "⚠️ *Obunangiz ertaga tugaydi!* Hozir yangilang 👇"
        else:
            msg = f"⚠️ *Obunangiz {days_left} kundan so'ng tugaydi.* Yangilang 👇"
    else:
        if days_left == 0:
            msg = "⚠️ *Подписка истекает сегодня!* Продлите сейчас 👇"
        elif days_left == 1:
            msg = "⚠️ *Подписка истекает завтра!* Продлите сейчас 👇"
        else:
            msg = f"⚠️ *Подписка истекает через {days_left} дн.* Продлите 👇"
    
    keyboard = [[InlineKeyboardButton(
        "🔄 Yangilash" if lang == "uz" else "🔄 Продлить",
        callback_data="show_pricing"
    )]]
    
    await update.effective_message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_payment_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment required message for non-PRO users - redirects to pricing"""
    await show_pricing(update, context, is_required=True)


# ==================== HELPER FUNCTIONS ====================

async def get_feature_usage(user_id: int, feature: str, db) -> int:
    """Get today's usage count for a feature"""
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT usage_count FROM feature_usage 
                WHERE user_id = $1 AND feature = $2 AND usage_date = CURRENT_DATE
            """, user_id, feature)
            return row["usage_count"] if row else 0
    else:
        async with db._connection.execute("""
            SELECT usage_count FROM feature_usage 
            WHERE user_id = ? AND feature = ? AND usage_date = DATE('now')
        """, (user_id, feature)) as cursor:
            row = await cursor.fetchone()
            return row["usage_count"] if row else 0


async def increment_feature_usage(user_id: int, feature: str, db) -> None:
    """Increment feature usage counter"""
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO feature_usage (user_id, feature, usage_date, usage_count)
                VALUES ($1, $2, CURRENT_DATE, 1)
                ON CONFLICT(user_id, feature, usage_date) 
                DO UPDATE SET usage_count = feature_usage.usage_count + 1
            """, user_id, feature)
    else:
        await db._connection.execute("""
            INSERT INTO feature_usage (user_id, feature, usage_date, usage_count)
            VALUES (?, ?, DATE('now'), 1)
            ON CONFLICT(user_id, feature, usage_date) 
            DO UPDATE SET usage_count = usage_count + 1
        """, (user_id, feature))
        await db._connection.commit()

