"""
SOLVO Subscription Handlers
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

async def show_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pricing options for Click payment"""
    query = update.callback_query
    if query:
        await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    if lang == "uz":
        msg = (
            "💎 *SOLVO PRO - Premium Tarif*\n\n"
            "PRO obunasi bilan siz quyidagi imkoniyatlarga ega bo'lasiz:\n\n"
            "✅ *Cheksiz hisob-kitoblar*\n"
            "✅ *To'liq moliyaviy tahlil*\n"
            "✅ *KATM kredit tarixini tahlil*\n"
            "✅ *Karta tarixi import qilish*\n"
            "✅ *AI maslahatlar*\n"
            "✅ *PDF hisobotlar*\n"
            "✅ *Ustuvor qo'llab-quvvatlash*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *Narxlar:*\n\n"
            "📅 *1 oylik:* `15,000 so'm`\n"
            "📅 *3 oylik:* `40,500 so'm` _(10% tejash)_\n"
            "📅 *1 yillik:* `135,000 so'm` _(25% tejash)_\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 *To'lov: Click orqali*"
        )
    else:
        msg = (
            "💎 *SOLVO PRO - Премиум Тариф*\n\n"
            "С подпиской PRO вы получаете:\n\n"
            "✅ *Безлимитные расчёты*\n"
            "✅ *Полный финансовый анализ*\n"
            "✅ *Анализ кредитной истории КАТМ*\n"
            "✅ *Импорт истории карты*\n"
            "✅ *AI рекомендации*\n"
            "✅ *PDF отчёты*\n"
            "✅ *Приоритетная поддержка*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *Цены:*\n\n"
            "📅 *1 месяц:* `15,000 сум`\n"
            "📅 *3 месяца:* `40,500 сум` _(скидка 10%)_\n"
            "📅 *1 год:* `135,000 сум` _(скидка 25%)_\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 *Оплата: через Click*"
        )
    
    # Click Payment buttons
    keyboard = [
        [InlineKeyboardButton(
            "📅 1 oy - 15,000 so'm" if lang == "uz" else "📅 1 мес - 15,000 сум",
            callback_data="click_buy_pro_monthly"
        )],
        [InlineKeyboardButton(
            "📅 3 oy - 40,500 so'm (-10%)" if lang == "uz" else "📅 3 мес - 40,500 сум (-10%)",
            callback_data="click_buy_pro_quarterly"
        )],
        [InlineKeyboardButton(
            "📅 1 yil - 135,000 so'm (-25%)" if lang == "uz" else "📅 1 год - 135,000 сум (-25%)",
            callback_data="click_buy_pro_yearly"
        )],
        [InlineKeyboardButton(
            "🎁 Promo-kod" if lang == "uz" else "🎁 Промо-код",
            callback_data="enter_promo"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
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


async def pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pro command - show pricing"""
    await show_pricing(update, context)


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
    order_id = f"solvo_{update.effective_user.id}_{plan_id}"
    return_url = "https://t.me/solvo_bot"  # Redirect back to bot after payment
    
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
            "Misol: `SOLVO2024`"
        )
    else:
        msg = (
            "🎁 *Ввод промо-кода*\n\n"
            "Если у вас есть промо-код, введите его:\n\n"
            "Пример: `SOLVO2024`"
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
    Check if user has PRO access. If not, show payment required message.
    Returns True if user has PRO, False otherwise.
    """
    telegram_id = update.effective_user.id
    
    if await is_user_pro(telegram_id):
        return True
    
    # User doesn't have PRO - show payment required
    await show_payment_required(update, context)
    return False


async def show_payment_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment required message for non-PRO users"""
    lang = context.user_data.get("lang", "uz")
    
    if lang == "uz":
        msg = (
            "🔒 *PRO obuna talab qilinadi*\n\n"
            "Bu funksiya faqat PRO foydalanuvchilar uchun!\n\n"
            "💎 PRO obunasi bilan:\n"
            "• Cheksiz moliyaviy hisob-kitoblar\n"
            "• To'liq KATM tahlili\n"
            "• Karta tarixi import\n"
            "• AI maslahatlar\n"
            "• PDF hisobotlar\n\n"
            "💰 *Narxlar:*\n"
            "• 1 oy: 15,000 so'm\n"
            "• 3 oy: 40,500 so'm\n"
            "• 1 yil: 135,000 so'm\n\n"
            "💳 *To'lov: Click orqali*\n\n"
            "👇 Obunani sotib olish uchun tugmani bosing:"
        )
    else:
        msg = (
            "🔒 *Требуется PRO подписка*\n\n"
            "Эта функция доступна только PRO пользователям!\n\n"
            "💎 С подпиской PRO:\n"
            "• Безлимитные финансовые расчёты\n"
            "• Полный анализ КАТМ\n"
            "• Импорт истории карты\n"
            "• AI рекомендации\n"
            "• PDF отчёты\n\n"
            "💰 *Цены:*\n"
            "• 1 месяц: 15,000 сум\n"
            "• 3 месяца: 40,500 сум\n"
            "• 1 год: 135,000 сум\n\n"
            "💳 *Оплата: через Click*\n\n"
            "👇 Нажмите кнопку для покупки:"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "💎 PRO sotib olish" if lang == "uz" else "💎 Купить PRO",
            callback_data="show_pricing"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
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


# ==================== HELPER FUNCTIONS ====================

async def get_feature_usage(user_id: int, feature: str, db) -> int:
    """Get today's usage count for a feature"""
    async with db._connection.execute("""
        SELECT usage_count FROM feature_usage 
        WHERE user_id = ? AND feature = ? AND usage_date = DATE('now')
    """, (user_id, feature)) as cursor:
        row = await cursor.fetchone()
        return row["usage_count"] if row else 0


async def increment_feature_usage(user_id: int, feature: str, db) -> None:
    """Increment feature usage counter"""
    await db._connection.execute("""
        INSERT INTO feature_usage (user_id, feature, usage_date, usage_count)
        VALUES (?, ?, DATE('now'), 1)
        ON CONFLICT(user_id, feature, usage_date) 
        DO UPDATE SET usage_count = usage_count + 1
    """, (user_id, feature))
    await db._connection.commit()

