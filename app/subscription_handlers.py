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
from telegram.ext import ContextTypes, ApplicationHandlerStop
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
                f"💎 *HALOS PRO — Moliyaviy erkinlik yo'li*\n\n"
                f"📍 Hozirgi tezligingiz: *{simple_months} oy*\n"
                f"🚀 PRO bilan: *{pro_months} oy* — *{months_saved} oy tezroq!*\n"
                f"💰 Bonus: *{format_number(int(savings_at_exit))} so'm* shaxsiy kapital\n\n"
            )
        else:
            header = "💎 *HALOS PRO — Moliyaviy erkinlik yo'li*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *FAQAT PRO FOYDALANUVCHILAR UCHUN:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "🗓 *HALOS SANANGIZ*\n"
            "Qarzlardan qachon xalos bo'lishingizni\n"
            "aniq sana bilan ko'rasiz\n\n"
            
            "⚡ *TEZKOR QUTILISH REJASI*\n"
            "Maxsus algoritm sizga eng optimal\n"
            "to'lov strategiyasini tayyorlaydi\n\n"
            
            "💰 *SHAXSIY KAPITAL*\n"
            "Qarz to'layotgan paytda ham\n"
            "jamg'arma hosil qilasiz\n\n"
            
            "🎤 *OVOZLI AI YORDAMCHI*\n"
            "Ovozingiz bilan xarajat va daromadni\n"
            "bir zumda kiritasiz\n\n"
            
            "📊 *BATAFSIL STATISTIKA*\n"
            "Haftalik, oylik, yillik hisobotlar\n"
            "Xarajatlar tahlili va dinamikasi\n\n"
            
            "🔔 *AQLLI ESLATMALAR*\n"
            "To'lov sanasi yaqinlashganda\n"
            "avtomatik xabar olasiz\n\n"
            
            "📥 *EXCEL HISOBOT*\n"
            "Barcha ma'lumotlaringizni Excel\n"
            "formatida yuklab oling\n\n"
            
            "👨‍👩‍👧 *OILAVIY REJIM*\n"
            "Oila byudjetini birgalikda boshqaring\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *NARXLAR:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 hafta:* `14,990 so'm`\n"
            "│   _Sinab ko'ring_\n"
            "├ ⭐ *1 oy:* `29,990 so'm`\n"
            "│   _Eng ommabop_\n"
            "└ 🏆 *1 yil:* `249,990 so'm`\n"
            "    _30% tejash!_\n\n"
            "💳 *To'lov: Click orqali*"
        )
    else:
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO — Путь к финансовой свободе*\n\n"
                f"📍 Текущая скорость: *{simple_months} мес*\n"
                f"🚀 С PRO: *{pro_months} мес* — *на {months_saved} мес быстрее!*\n"
                f"💰 Бонус: *{format_number(int(savings_at_exit))} сум* личный капитал\n\n"
            )
        else:
            header = "💎 *HALOS PRO — Путь к финансовой свободе*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *ТОЛЬКО ДЛЯ PRO ПОЛЬЗОВАТЕЛЕЙ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "🗓 *ДАТА HALOS*\n"
            "Узнайте точную дату освобождения\n"
            "от долгов\n\n"
            
            "⚡ *ПЛАН БЫСТРОГО ОСВОБОЖДЕНИЯ*\n"
            "Специальный алгоритм создаст\n"
            "оптимальную стратегию выплат\n\n"
            
            "💰 *ЛИЧНЫЙ КАПИТАЛ*\n"
            "Копите даже пока\n"
            "выплачиваете долги\n\n"
            
            "🎤 *ГОЛОСОВОЙ AI ПОМОЩНИК*\n"
            "Вносите расходы и доходы\n"
            "голосом за секунды\n\n"
            
            "📊 *ДЕТАЛЬНАЯ СТАТИСТИКА*\n"
            "Еженедельные, ежемесячные отчёты\n"
            "Анализ и динамика расходов\n\n"
            
            "🔔 *УМНЫЕ НАПОМИНАНИЯ*\n"
            "Автоматические уведомления\n"
            "о приближении платежей\n\n"
            
            "📥 *EXCEL ОТЧЁТ*\n"
            "Скачивайте все данные\n"
            "в формате Excel\n\n"
            
            "👨‍👩‍👧 *СЕМЕЙНЫЙ РЕЖИМ*\n"
            "Управляйте бюджетом семьи вместе\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ЦЕНЫ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 неделя:* `14,990 сум`\n"
            "│   _Попробуйте_\n"
            "├ ⭐ *1 месяц:* `29,990 сум`\n"
            "│   _Самый популярный_\n"
            "└ 🏆 *1 год:* `249,990 сум`\n"
            "    _Скидка 30%!_\n\n"
            "💳 *Оплата: через Click*"
        )
    
    # Click Payment buttons
    keyboard = [
        [InlineKeyboardButton(
            "⚡ 1 hafta - 14,990 so'm" if lang == "uz" else "⚡ 1 нед - 14,990 сум",
            callback_data="click_buy_pro_weekly"
        )],
        [InlineKeyboardButton(
            "⭐ 1 oy - 29,990 so'm (tavsiya)" if lang == "uz" else "⭐ 1 мес - 29,990 сум (реком.)",
            callback_data="click_buy_pro_monthly"
        )],
        [InlineKeyboardButton(
            "🏆 1 yil - 249,990 so'm (-30%)" if lang == "uz" else "🏆 1 год - 249,990 сум (-30%)",
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
                f"💎 *HALOS PRO — Moliyaviy erkinlik yo'li*\n\n"
                f"📍 Hozirgi tezligingiz: *{simple_months} oy*\n"
                f"🚀 PRO bilan: *{pro_months} oy* — *{months_saved} oy tezroq!*\n"
                f"💰 Bonus: *{format_number(int(savings_at_exit))} so'm* shaxsiy kapital\n\n"
            )
        else:
            header = "💎 *HALOS PRO — Moliyaviy erkinlik yo'li*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *FAQAT PRO FOYDALANUVCHILAR UCHUN:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "🗓 *HALOS SANANGIZ*\n"
            "Qarzlardan qachon xalos bo'lishingizni\n"
            "aniq sana bilan ko'rasiz\n\n"
            
            "⚡ *TEZKOR QUTILISH REJASI*\n"
            "Maxsus algoritm sizga eng optimal\n"
            "to'lov strategiyasini tayyorlaydi\n\n"
            
            "💰 *SHAXSIY KAPITAL*\n"
            "Qarz to'layotgan paytda ham\n"
            "jamg'arma hosil qilasiz\n\n"
            
            "🎤 *OVOZLI AI YORDAMCHI*\n"
            "Ovozingiz bilan xarajat va daromadni\n"
            "bir zumda kiritasiz\n\n"
            
            "📊 *BATAFSIL STATISTIKA*\n"
            "Haftalik, oylik, yillik hisobotlar\n"
            "Xarajatlar tahlili va dinamikasi\n\n"
            
            "🔔 *AQLLI ESLATMALAR*\n"
            "To'lov sanasi yaqinlashganda\n"
            "avtomatik xabar olasiz\n\n"
            
            "📥 *EXCEL HISOBOT*\n"
            "Barcha ma'lumotlaringizni Excel\n"
            "formatida yuklab oling\n\n"
            
            "👨‍👩‍👧 *OILAVIY REJIM*\n"
            "Oila byudjetini birgalikda boshqaring\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *NARXLAR:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 hafta:* `14,990 so'm`\n"
            "│   _Sinab ko'ring_\n"
            "├ ⭐ *1 oy:* `29,990 so'm`\n"
            "│   _Eng ommabop_\n"
            "└ 🏆 *1 yil:* `249,990 so'm`\n"
            "    _30% tejash!_\n\n"
            "💳 *To'lov: Click orqali*"
        )
    else:
        if simple_months > 0 and months_saved > 0:
            header = (
                f"💎 *HALOS PRO — Путь к финансовой свободе*\n\n"
                f"📍 Текущая скорость: *{simple_months} мес*\n"
                f"🚀 С PRO: *{pro_months} мес* — *на {months_saved} мес быстрее!*\n"
                f"💰 Бонус: *{format_number(int(savings_at_exit))} сум* личный капитал\n\n"
            )
        else:
            header = "💎 *HALOS PRO — Путь к финансовой свободе*\n\n"
        
        msg = (
            f"{header}"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *ТОЛЬКО ДЛЯ PRO ПОЛЬЗОВАТЕЛЕЙ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "🗓 *ДАТА HALOS*\n"
            "Узнайте точную дату освобождения\n"
            "от долгов\n\n"
            
            "⚡ *ПЛАН БЫСТРОГО ОСВОБОЖДЕНИЯ*\n"
            "Специальный алгоритм создаст\n"
            "оптимальную стратегию выплат\n\n"
            
            "💰 *ЛИЧНЫЙ КАПИТАЛ*\n"
            "Копите даже пока\n"
            "выплачиваете долги\n\n"
            
            "🎤 *ГОЛОСОВОЙ AI ПОМОЩНИК*\n"
            "Вносите расходы и доходы\n"
            "голосом за секунды\n\n"
            
            "📊 *ДЕТАЛЬНАЯ СТАТИСТИКА*\n"
            "Еженедельные, ежемесячные отчёты\n"
            "Анализ и динамика расходов\n\n"
            
            "🔔 *УМНЫЕ НАПОМИНАНИЯ*\n"
            "Автоматические уведомления\n"
            "о приближении платежей\n\n"
            
            "📥 *EXCEL ОТЧЁТ*\n"
            "Скачивайте все данные\n"
            "в формате Excel\n\n"
            
            "👨‍👩‍👧 *СЕМЕЙНЫЙ РЕЖИМ*\n"
            "Управляйте бюджетом семьи вместе\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ЦЕНЫ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "├ ⚡ *1 неделя:* `14,990 сум`\n"
            "│   _Попробуйте_\n"
            "├ ⭐ *1 месяц:* `29,990 сум`\n"
            "│   _Самый популярный_\n"
            "└ 🏆 *1 год:* `249,990 сум`\n"
            "    _Скидка 30%!_\n\n"
            "💳 *Оплата: через Click*"
        )
    
    # Click Payment buttons
    keyboard = [
        [InlineKeyboardButton(
            "⚡ 1 hafta - 14,990 so'm" if lang == "uz" else "⚡ 1 нед - 14,990 сум",
            callback_data="click_buy_pro_weekly"
        )],
        [InlineKeyboardButton(
            "⭐ 1 oy - 29,990 so'm (tavsiya)" if lang == "uz" else "⭐ 1 мес - 29,990 сум (реком.)",
            callback_data="click_buy_pro_monthly"
        )],
        [InlineKeyboardButton(
            "🏆 1 yil - 249,990 so'm (-30%)" if lang == "uz" else "🏆 1 год - 249,990 сум (-30%)",
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


# ==================== PAYMENT METHOD SELECTION ====================

async def click_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Click payment button - directly go to Telegram Payment"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("click_buy_", "")
    
    # Store selected plan
    context.user_data["selected_plan"] = plan_id
    
    # Get plan info
    if plan_id not in PRICING_PLANS:
        await query.answer("❌ Tarif topilmadi", show_alert=True)
        return
    
    # Directly go to Telegram Payment (Click Terminal)
    from app.telegram_payments import send_payment_invoice
    
    try:
        await query.message.delete()
    except:
        pass
    
    await send_payment_invoice(update, context, plan_id)


# NOTE: Click havola payment temporarily disabled - code kept for future use
# async def click_buy_callback_with_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle Click payment button - show payment method selection"""
#     query = update.callback_query
#     await query.answer()
#     
#     plan_id = query.data.replace("click_buy_", "")
#     lang = context.user_data.get("lang", "uz")
#     
#     # Store selected plan
#     context.user_data["selected_plan"] = plan_id
#     
#     # Get plan info
#     if plan_id not in PRICING_PLANS:
#         await query.answer("❌ Tarif topilmadi", show_alert=True)
#         return
#     
#     plan = PRICING_PLANS[plan_id]
#     
#     if lang == "uz":
#         msg = (
#             f"💳 *To'lov usulini tanlang*\n\n"
#             f"📦 Tarif: *{plan.description_uz}*\n"
#             f"💰 Narx: *{plan.price_uzs:,} so'm*\n\n"
#             "👇 Quyidagilardan birini tanlang:"
#         )
#         keyboard = [
#             [InlineKeyboardButton("📱 Click (Telegram)", callback_data=f"pay_tg_{plan_id}")],
#             [InlineKeyboardButton("🔗 Click havola", callback_data=f"pay_link_{plan_id}")],
#             [InlineKeyboardButton("◀️ Orqaga", callback_data="show_pricing")]
#         ]
#     else:
#         msg = (
#             f"💳 *Выберите способ оплаты*\n\n"
#             f"📦 Тариф: *{plan.description_ru}*\n"
#             f"💰 Цена: *{plan.price_uzs:,} сум*\n\n"
#             "👇 Выберите один из вариантов:"
#         )
#         keyboard = [
#             [InlineKeyboardButton("📱 Click (Telegram)", callback_data=f"pay_tg_{plan_id}")],
#             [InlineKeyboardButton("🔗 Click ссылка", callback_data=f"pay_link_{plan_id}")],
#             [InlineKeyboardButton("◀️ Назад", callback_data="show_pricing")]
#         ]
#     
#     await query.edit_message_text(
#         msg,
#         parse_mode="Markdown",
#         reply_markup=InlineKeyboardMarkup(keyboard)
#     )


async def pay_telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Telegram Payment (Click Terminal) selection"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("pay_tg_", "")
    
    from app.telegram_payments import send_payment_invoice
    
    try:
        await query.message.delete()
    except:
        pass
    
    await send_payment_invoice(update, context, plan_id)


async def pay_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Click link payment selection"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("pay_link_", "")
    lang = context.user_data.get("lang", "uz")
    
    if plan_id not in PRICING_PLANS:
        return
    
    plan = PRICING_PLANS[plan_id]
    
    # Generate Click payment URL
    from app.click_payment import generate_click_payment_url
    
    order_id = f"halos_{update.effective_user.id}_{plan_id}"
    click_url = generate_click_payment_url(
        amount=plan.price_uzs,
        order_id=order_id,
        return_url="https://t.me/HalosRobot",
        description=plan.description_uz
    )
    
    if lang == "uz":
        msg = (
            f"🔗 *Click havola orqali to'lov*\n\n"
            f"📦 Tarif: *{plan.description_uz}*\n"
            f"💰 Narx: *{plan.price_uzs:,} so'm*\n\n"
            "👇 Quyidagi tugmani bosing va Click orqali to'lang.\n\n"
            "⚠️ To'lovdan keyin /start bosing."
        )
        pay_btn = "💳 Click orqali to'lash"
    else:
        msg = (
            f"🔗 *Оплата по ссылке Click*\n\n"
            f"📦 Тариф: *{plan.description_ru}*\n"
            f"💰 Цена: *{plan.price_uzs:,} сум*\n\n"
            "👇 Нажмите кнопку и оплатите через Click.\n\n"
            "⚠️ После оплаты нажмите /start."
        )
        pay_btn = "💳 Оплатить через Click"
    
    keyboard = [
        [InlineKeyboardButton(pay_btn, url=click_url)],
        [InlineKeyboardButton("◀️ Orqaga" if lang == "uz" else "◀️ Назад", callback_data=f"click_buy_{plan_id}")]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle P2P card payment selection"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("pay_card_", "")
    lang = context.user_data.get("lang", "uz")
    
    if plan_id not in PRICING_PLANS:
        return
    
    plan = PRICING_PLANS[plan_id]
    
    # P2P to'lov kartasi
    CARD_NUMBER = "9860 1701 0444 4616"  # O'zingizning karta raqamingiz
    CARD_HOLDER = "HALOS"
    
    if lang == "uz":
        msg = (
            f"💳 *Karta orqali to'lov (P2P)*\n\n"
            f"📦 Tarif: *{plan.description_uz}*\n"
            f"💰 Summa: *{plan.price_uzs:,} so'm*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Karta: `{CARD_NUMBER}`\n"
            f"👤 Egasi: *{CARD_HOLDER}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 *Qadamlar:*\n"
            "1️⃣ Yuqoridagi karta raqamini nusxalang\n"
            f"2️⃣ *{plan.price_uzs:,} so'm* o'tkazing\n"
            "3️⃣ Chekni rasmga olib yuboring\n\n"
            "⚠️ Chekni admin tekshirgach PRO ochiladi."
        )
    else:
        msg = (
            f"💳 *Оплата картой (P2P)*\n\n"
            f"📦 Тариф: *{plan.description_ru}*\n"
            f"💰 Сумма: *{plan.price_uzs:,} сум*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Карта: `{CARD_NUMBER}`\n"
            f"👤 Владелец: *{CARD_HOLDER}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 *Шаги:*\n"
            "1️⃣ Скопируйте номер карты\n"
            f"2️⃣ Переведите *{plan.price_uzs:,} сум*\n"
            "3️⃣ Отправьте фото чека\n\n"
            "⚠️ PRO откроется после проверки."
        )
    
    # Store for photo receipt
    context.user_data["awaiting_receipt"] = plan_id
    
    keyboard = [
        [InlineKeyboardButton("📋 Karta raqamini nusxalash" if lang == "uz" else "📋 Копировать номер", 
                              callback_data="copy_card")],
        [InlineKeyboardButton("◀️ Orqaga" if lang == "uz" else "◀️ Назад", callback_data=f"click_buy_{plan_id}")]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # Send payment invoice
    await send_payment_invoice(update, context, plan_id)


# ==================== PROMO CODE ====================

async def enter_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle promo code entry"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Set state for promo code input
    context.user_data["awaiting_promo"] = True
    
    logger.info(f"[PROMO] enter_promo_callback: Set awaiting_promo=True for user {query.from_user.id}")
    
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
    # Debug logging
    logger.info(f"[PROMO] handle_promo_code_input called. awaiting_promo={context.user_data.get('awaiting_promo')}")
    
    if not context.user_data.get("awaiting_promo"):
        return False
    
    lang = context.user_data.get("lang", "uz")
    code = update.message.text.strip().upper()
    
    logger.info(f"[PROMO] Processing promo code: {code}")
    
    context.user_data["awaiting_promo"] = False
    
    # Validate promo code
    promo = validate_promo_code(code)
    
    logger.info(f"[PROMO] Validation result: {promo}")
    
    if not promo:
        # Promo code invalid - show error and redirect to pricing
        if lang == "uz":
            error_msg = (
                "❌ *Promo-kod xato!*\n\n"
                f"Kiritilgan kod: `{code}`\n"
                "Iltimos, to'g'ri promo-kodni kiriting yoki tarif tanlang:"
            )
        else:
            error_msg = (
                "❌ *Промо-код неверный!*\n\n"
                f"Введённый код: `{code}`\n"
                "Пожалуйста, введите правильный код или выберите тариф:"
            )
        
        # Show pricing buttons
        keyboard = [
            [InlineKeyboardButton(
                "⚡ 1 hafta - 14,990 so'm" if lang == "uz" else "⚡ 1 нед - 14,990 сум",
                callback_data="click_buy_pro_weekly"
            )],
            [InlineKeyboardButton(
                "⭐ 1 oy - 29,990 so'm" if lang == "uz" else "⭐ 1 мес - 29,990 сум",
                callback_data="click_buy_pro_monthly"
            )],
            [InlineKeyboardButton(
                "🏆 1 yil - 249,990 so'm (-30%)" if lang == "uz" else "🏆 1 год - 249,990 сум (-30%)",
                callback_data="click_buy_pro_yearly"
            )],
            [InlineKeyboardButton(
                "🎁 Boshqa promo-kod" if lang == "uz" else "🎁 Другой промо-код",
                callback_data="enter_promo"
            )],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(error_msg, parse_mode="Markdown", reply_markup=reply_markup)
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
                "⚡ 1 hafta - 14,990 so'm" if lang == "uz" else "⚡ 1 нед - 14,990 сум",
                callback_data="click_buy_pro_weekly"
            )],
            [InlineKeyboardButton(
                "⭐ 1 oy - 29,990 so'm" if lang == "uz" else "⭐ 1 мес - 29,990 сум",
                callback_data="click_buy_pro_monthly"
            )],
            [InlineKeyboardButton(
                "🏆 1 yil - 249,990 so'm (-30%)" if lang == "uz" else "🏆 1 год - 249,990 сум (-30%)",
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
        logger.info(f"[PROMO] FREE DAYS activated for user {telegram_id}: {days} days until {expires_at}")
    
    # Stop other handlers from processing this message
    raise ApplicationHandlerStop()


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


# ==================== VOICE PACK PURCHASE ====================

async def buy_voice_pack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Voice Pack purchase request"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import VOICE_PACK_PRICE, VOICE_PACK_COUNT
    
    # Show Voice Pack purchase options
    if lang == "uz":
        msg = (
            "🎤 *VOICE PACK*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 *{VOICE_PACK_COUNT} ta* qo'shimcha ovozli xabar\n\n"
            "✅ *Afzalliklari:*\n"
            "├ Bir marta to'lov\n"
            "├ Muddatsiz amal qiladi\n"
            "└ Har qanday vaqtda ishlatish mumkin\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Narxi:* `{format_number(VOICE_PACK_PRICE)} so'm`\n\n"
            "💳 *To'lov: Telegram Payment*"
        )
    else:
        msg = (
            "🎤 *VOICE PACK*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 *{VOICE_PACK_COUNT}* дополнительных голосовых\n\n"
            "✅ *Преимущества:*\n"
            "├ Разовый платёж\n"
            "├ Бессрочно\n"
            "└ Использовать в любое время\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Цена:* `{format_number(VOICE_PACK_PRICE)} сум`\n\n"
            "💳 *Оплата: Telegram Payment*"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            f"💳 To'lash {format_number(VOICE_PACK_PRICE)} so'm" if lang == "uz" else f"💳 Оплатить {format_number(VOICE_PACK_PRICE)} сум",
            callback_data="tg_pay_voice_pack"
        )],
        [InlineKeyboardButton(
            "💎 PRO obuna (cheksiz)" if lang == "uz" else "💎 PRO (безлимит)",
            callback_data="show_pricing"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="cancel_voice_pack"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_voice_pack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel voice pack purchase"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    await query.edit_message_text(
        "✅ Bekor qilindi" if lang == "uz" else "✅ Отменено"
    )


async def add_bonus_voice(telegram_id: int, count: int = 100) -> bool:
    """Add bonus voice messages to user account"""
    db = await get_database()
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users 
                    SET bonus_voice_count = COALESCE(bonus_voice_count, 0) + $1
                    WHERE telegram_id = $2
                """, count, telegram_id)
        else:
            await db._connection.execute("""
                UPDATE users 
                SET bonus_voice_count = COALESCE(bonus_voice_count, 0) + ?
                WHERE telegram_id = ?
            """, (count, telegram_id))
            await db._connection.commit()
        
        logger.info(f"[VOICE_PACK] Added {count} bonus voice messages for user {telegram_id}")
        return True
    except Exception as e:
        logger.error(f"[VOICE_PACK] Error adding bonus voice: {e}")
        return False


# ==================== VOICE TIER PURCHASE (Voice+, Voice Unlimited) ====================

async def buy_voice_plus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Voice+ tier purchase request"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import VOICE_PLUS_PRICE, VOICE_TIERS
    
    # Show Voice+ purchase info
    if lang == "uz":
        msg = (
            "🎤 *VOICE+ OBUNA*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 *Nima kiradi:*\n"
            "├ 📊 Oyiga *60 ta* ovozli xabar\n"
            "├ ⏱ Har biri *60 soniyagacha*\n"
            "└ 📝 Matnli kiritish - BEPUL va cheksiz\n\n"
            "✅ *Afzalliklari:*\n"
            "├ Basic dan 2 baravar ko'p\n"
            "├ Uzunroq ovozli xabarlar\n"
            "└ Oylik obuna\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Narxi:* `{format_number(VOICE_PLUS_PRICE)} so'm/oy`\n\n"
            "💳 *To'lov: Telegram Payment*"
        )
    else:
        msg = (
            "🎤 *VOICE+ ПОДПИСКА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 *Что включено:*\n"
            "├ 📊 *60* голосовых в месяц\n"
            "├ ⏱ До *60 секунд* каждое\n"
            "└ 📝 Текстовый ввод - БЕСПЛАТНО\n\n"
            "✅ *Преимущества:*\n"
            "├ В 2 раза больше Basic\n"
            "├ Более длинные голосовые\n"
            "└ Ежемесячная подписка\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Цена:* `{format_number(VOICE_PLUS_PRICE)} сум/мес`\n\n"
            "💳 *Оплата: Telegram Payment*"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            f"💳 To'lash {format_number(VOICE_PLUS_PRICE)} so'm" if lang == "uz" else f"💳 Оплатить {format_number(VOICE_PLUS_PRICE)} сум",
            callback_data="tg_pay_voice_plus"
        )],
        [InlineKeyboardButton(
            f"🎤 Voice Unlimited - {format_number(29990)} so'm" if lang == "uz" else f"🎤 Voice Unlimited - {format_number(29990)} сум",
            callback_data="buy_voice_unlimited"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="cancel_voice_tier"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buy_voice_unlimited_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Voice Unlimited tier purchase request"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import VOICE_UNLIMITED_PRICE, VOICE_TIERS
    
    # Show Voice Unlimited purchase info
    if lang == "uz":
        msg = (
            "🎤 *VOICE UNLIMITED*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 *Nima kiradi:*\n"
            "├ 📊 *CHEKSIZ* ovozli xabar\n"
            "├ ⏱ Har biri *60 soniyagacha*\n"
            "└ 📝 Matnli kiritish - BEPUL va cheksiz\n\n"
            "✅ *Afzalliklari:*\n"
            "├ Hech qanday limit yo'q\n"
            "├ Uzun ovozli xabarlar\n"
            "├ Premium foydalanuvchi\n"
            "└ Oylik obuna\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Narxi:* `{format_number(VOICE_UNLIMITED_PRICE)} so'm/oy`\n\n"
            "💳 *To'lov: Telegram Payment*"
        )
    else:
        msg = (
            "🎤 *VOICE UNLIMITED*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 *Что включено:*\n"
            "├ 📊 *БЕЗЛИМИТ* голосовых\n"
            "├ ⏱ До *60 секунд* каждое\n"
            "└ 📝 Текстовый ввод - БЕСПЛАТНО\n\n"
            "✅ *Преимущества:*\n"
            "├ Никаких лимитов\n"
            "├ Длинные голосовые\n"
            "├ Премиум пользователь\n"
            "└ Ежемесячная подписка\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Цена:* `{format_number(VOICE_UNLIMITED_PRICE)} сум/мес`\n\n"
            "💳 *Оплата: Telegram Payment*"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            f"💳 To'lash {format_number(VOICE_UNLIMITED_PRICE)} so'm" if lang == "uz" else f"💳 Оплатить {format_number(VOICE_UNLIMITED_PRICE)} сум",
            callback_data="tg_pay_voice_unlimited"
        )],
        [InlineKeyboardButton(
            f"🎤 Voice+ - {format_number(14990)} so'm" if lang == "uz" else f"🎤 Voice+ - {format_number(14990)} сум",
            callback_data="buy_voice_plus"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="cancel_voice_tier"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_voice_tier_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel voice tier purchase"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    await query.edit_message_text(
        "✅ Bekor qilindi" if lang == "uz" else "✅ Отменено"
    )


async def activate_voice_tier(telegram_id: int, tier: str = "plus") -> bool:
    """Activate voice tier for user (1 month duration)"""
    db = await get_database()
    from datetime import datetime, timedelta
    
    expires = datetime.now() + timedelta(days=30)
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users 
                    SET voice_tier = $1, voice_tier_expires = $2
                    WHERE telegram_id = $3
                """, tier, expires, telegram_id)
        else:
            await db._connection.execute("""
                UPDATE users 
                SET voice_tier = ?, voice_tier_expires = ?
                WHERE telegram_id = ?
            """, (tier, expires.isoformat(), telegram_id))
            await db._connection.commit()
        
        logger.info(f"[VOICE_TIER] Activated {tier} for user {telegram_id} until {expires}")
        return True
    except Exception as e:
        logger.error(f"[VOICE_TIER] Error activating tier: {e}")
        return False
