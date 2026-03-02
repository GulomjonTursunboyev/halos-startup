"""
HALOS Atmos Payment Handlers
Manages UI and interactions for Atmos card binding and auto-renewal subscriptions.
"""
import logging
from datetime import datetime, timedelta
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ApplicationHandlerStop
from telegram.constants import ParseMode

from app.database import get_database
from app.subscription import PRICING_PLANS, get_plan_price, is_discount_active, ORIGINAL_PRICES
from app.atmos_payment import bind_card_init, bind_card_confirm, pay_with_token
from app.payment_webhook import send_pro_activation_message

logger = logging.getLogger(__name__)

async def atmos_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle '💳 Avto-to'lov (Atmos)' method selection in UI"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Check if a plan is already selected, else show plan options for Atmos
    weekly_price = get_plan_price("pro_weekly")
    monthly_price = get_plan_price("pro_monthly")
    
    db = await get_database()
    telegram_id = update.effective_user.id
    user = await db.get_user(telegram_id)
    
    # Check if user already has bounds card
    has_card = False
    if db.is_postgres:
        cards = await db.fetch_all("SELECT * FROM user_cards WHERE user_id = $1 AND is_active = TRUE", user['id'])
    else:
        cards = await db.fetch_all("SELECT * FROM user_cards WHERE user_id = ? AND is_active = 1", user['id'])
        
    if cards:
        has_card = True
        card_mask = cards[0]['card_mask']
    
    if lang == "uz":
        msg = (
            "💳 *Atmos orqali Avto-to'lov*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Atmos orqali kartangizni ulang va "
            "obuna tugaganda avtomatik uzaytirilishidan bahramand bo'ling.\n"
            "Siz istalgan vaqt obunani bekor qilishingiz mumkin.\n\n"
            "Tarifni tanlang:\n\n"
            f"├ ⚡ 1 hafta — *{weekly_price:,}* so'm / hafta\n"
            f"└ ⭐ 1 oy — *{monthly_price:,}* so'm / oy _(tavsiya)_\n"
        )
    else:
        msg = (
            "💳 *Авто-оплата через Atmos*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Привяжите карту через Atmos и наслаждайтесь "
            "автоматическим продлением подписки.\n"
            "Вы можете отменить подписку в любой момент.\n\n"
            "Выберите тариф:\n\n"
            f"├ ⚡ 1 неделя — *{weekly_price:,}* сум / нед\n"
            f"└ ⭐ 1 месяц — *{monthly_price:,}* сум / мес _(реком.)_\n"
        )
    
    # If already has a card
    if has_card:
        if lang == "uz":
            msg += f"\n✅ Sizning kartangiz ulangan: `{card_mask}`"
        else:
            msg += f"\n✅ Ваша карта привязана: `{card_mask}`"
            
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(f"⚡ 1 hafta — {weekly_price:,}", callback_data="atmos_buy_pro_weekly")],
            [InlineKeyboardButton(f"⭐ 1 oy — {monthly_price:,} (tavsiya)", callback_data="atmos_buy_pro_monthly")],
            [InlineKeyboardButton("⚙️ Kartani bekor qilish", callback_data="atmos_unbind_card")] if has_card else [],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="show_pricing")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(f"⚡ 1 нед — {weekly_price:,}", callback_data="atmos_buy_pro_weekly")],
            [InlineKeyboardButton(f"⭐ 1 мес — {monthly_price:,} (реком.)", callback_data="atmos_buy_pro_monthly")],
            [InlineKeyboardButton("⚙️ Отвязать карту", callback_data="atmos_unbind_card")] if has_card else [],
            [InlineKeyboardButton("◀️ Назад", callback_data="show_pricing")]
        ]
        
    keyboard = [row for row in keyboard if row]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def atmos_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Atmos plan selection - ask for card or pay immediately if stored"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("atmos_buy_", "")
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    if plan_id not in PRICING_PLANS:
        await query.answer("❌ Tarif topilmadi" if lang == "uz" else "❌ Тариф не найден", show_alert=True)
        return
        
    context.user_data["selected_plan"] = plan_id
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check bounded card
    if db.is_postgres:
        cards = await db.fetch_all("SELECT * FROM user_cards WHERE user_id = $1 AND is_active = TRUE", user['id'])
    else:
        cards = await db.fetch_all("SELECT * FROM user_cards WHERE user_id = ? AND is_active = 1", user['id'])
        
    if cards:
        # User has a card. Confirm payment!
        actual_price = get_plan_price(plan_id)
        card = cards[0]
        context.user_data["active_card_token"] = card["token"]
        context.user_data["active_card_id"] = card["id"]
        
        if lang == "uz":
            msg = (
                f"💳 *To'lovni tasdiqlang*\n\n"
                f"Karta: `{card['card_mask']}`\n"
                f"Summa: *{actual_price:,}* so'm\n"
                f"Tarif: *{PRICING_PLANS[plan_id].description_uz}*\n\n"
                "To'lovni tasdiqlaysizmi?"
            )
            keyboard = [
                [InlineKeyboardButton("✅ Tasdiqlash va to'lash", callback_data="atmos_confirm_pay")],
                [InlineKeyboardButton("💳 Boshqa karta ulash", callback_data="atmos_new_card")],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="payment_method_atmos")]
            ]
        else:
            msg = (
                f"💳 *Подтвердите оплату*\n\n"
                f"Карта: `{card['card_mask']}`\n"
                f"Сумма: *{actual_price:,}* сум\n"
                f"Тариф: *{PRICING_PLANS[plan_id].description_ru}*\n\n"
                "Подтверждаете оплату?"
            )
            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить и оплатить", callback_data="atmos_confirm_pay")],
                [InlineKeyboardButton("💳 Привязать другую карту", callback_data="atmos_new_card")],
                [InlineKeyboardButton("❌ Отмена", callback_data="payment_method_atmos")]
            ]
            
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Prompt for new card
        await prompt_new_card(update, context, plan_id)


async def atmos_new_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = context.user_data.get("selected_plan", "pro_monthly")
    await prompt_new_card(update, context, plan_id)


async def prompt_new_card(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: str) -> None:
    lang = context.user_data.get("lang", "uz")
    
    # Store state
    context.user_data["awaiting_atmos_card"] = True
    context.user_data["selected_plan"] = plan_id
    
    if lang == "uz":
        msg = (
            "💳 *Kartani ulash (Atmos)*\n\n"
            "Iltimos, karta raqami va amal qilish muddatini kiriting.\n"
            "Misol: `8600123456789012 12/26`"
        )
        keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="payment_method_atmos")]]
    else:
        msg = (
            "💳 *Привязка карты (Atmos)*\n\n"
            "Пожалуйста, введите номер карты и срок действия.\n"
            "Пример: `8600123456789012 12/26`"
        )
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="payment_method_atmos")]]
        
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def process_atmos_card_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if message was handled as an Atmos card input"""
    if not context.user_data.get("awaiting_atmos_card"):
        return False
        
    text = update.message.text.strip()
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Basic validation
    text_clean = text.replace(" ", "")
    if len(text_clean) < 20 or not text_clean[:16].isdigit() or "/" not in text_clean:
        if lang == "uz":
            await update.message.reply_text("❌ Noto'g'ri format! Iltimos, boshqatdan kiriting: `8600123456789012 12/26`", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Неверный формат! Заново: `8600123456789012 12/26`", parse_mode="Markdown")
        return True
        
    card_number = text_clean[:16]
    expiry = text_clean[16:].replace("/", "")
    
    msg = await update.message.reply_text("⏳ Yuklanmoqda..." if lang == "uz" else "⏳ Загрузка...")
    
    # Call Atmos API
    res = await bind_card_init(card_number, expiry)
    
    if not res.get("success"):
        context.user_data["awaiting_atmos_card"] = False
        error = res.get('error', 'Noma\'lum xatolik')
        if lang == "uz":
            await msg.edit_text(f"❌ Xatolik yuz berdi:\n{error}\n\nKarta ulash bekor qilindi.")
        else:
            await msg.edit_text(f"❌ Ошибка:\n{error}\n\nПривязка отменена.")
        return True
        
    # Store transaction for OTP
    context.user_data["atmos_bind_txn"] = res["transaction_id"]
    context.user_data["awaiting_atmos_card"] = False
    context.user_data["awaiting_atmos_otp"] = True
    
    phone_mask = res.get("phone_mask", "")
    
    if lang == "uz":
        text_reply = (
            f"📱 *Kodni kiriting*\n\n"
            f"`{phone_mask}` raqamiga SMS kod yuborildi.\n"
            "Iltimos, kodni kiriting:"
        )
        keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="payment_method_atmos")]]
    else:
        text_reply = (
            f"📱 *Введите код*\n\n"
            f"SMS код отправлен на `{phone_mask}`.\n"
            "Пожалуйста, введите код:"
        )
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="payment_method_atmos")]]
        
    await msg.edit_text(text_reply, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return True


async def process_atmos_otp_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if message was handled as an Atmos OTP input"""
    if not context.user_data.get("awaiting_atmos_otp"):
        return False
        
    otp = update.message.text.strip()
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    txn_id = context.user_data.get("atmos_bind_txn")
    plan_id = context.user_data.get("selected_plan", "pro_monthly")
    
    msg = await update.message.reply_text("⏳ Tekshirilmoqda..." if lang == "uz" else "⏳ Проверяется...")
    
    res = await bind_card_confirm(txn_id, otp)
    
    if not res.get("success"):
        # Let them try again or fail? We'll just fail to be safe and restart the flow
        context.user_data["awaiting_atmos_otp"] = False
        error = res.get('error', 'Noto\'g\'ri kod')
        if lang == "uz":
            await msg.edit_text(f"❌ Xatolik (yoki noto'g'ri kod):\n{error}\n\nBoshlash tugmasini bosing: /start")
        else:
            await msg.edit_text(f"❌ Ошибка (или неверный код):\n{error}\n\nНажмите /start")
        return True
        
    token = res.get("token")
    card_mask = res.get("card_mask", "****")
    
    context.user_data["awaiting_atmos_otp"] = False
    
    # Save to user_cards db
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # First set all active to false (one active card at a time max)
    if db.is_postgres:
        await db.execute_update("UPDATE user_cards SET is_active = FALSE WHERE user_id = $1", user['id'])
        await db.execute_update(
            """INSERT INTO user_cards (user_id, card_number, card_mask, expiry_date, token, is_active, is_default)
            VALUES ($1, $2, $3, $4, $5, TRUE, TRUE)""",
            user['id'], 'encrypted', card_mask, 'xx/xx', token
        )
    else:
        await db.execute_update("UPDATE user_cards SET is_active = 0 WHERE user_id = ?", user['id'])
        await db.execute_update(
            """INSERT INTO user_cards (user_id, card_number, card_mask, expiry_date, token, is_active, is_default)
            VALUES (?, ?, ?, ?, ?, 1, 1)""",
            user['id'], 'encrypted', card_mask, 'xx/xx', token
        )
        
    await msg.edit_text("✅ Karta ulandi! To'lov amalga oshirilmoqda..." if lang == "uz" else "✅ Карта привязана! Оплата выполняется...")
    
    # Direct to payment
    context.user_data["active_card_token"] = token
    await process_atmos_payment(update, context, msg)
    return True


async def atmos_confirm_pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    msg = await query.edit_message_text("⏳ To'lov amalga oshirilmoqda..." if lang == "uz" else "⏳ Оплата выполняется...")
    await process_atmos_payment(update, context, msg)


async def process_atmos_payment(update, context, status_msg) -> None:
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    plan_id = context.user_data.get("selected_plan", "pro_monthly")
    token = context.user_data.get("active_card_token")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    actual_price = get_plan_price(plan_id)
    
    res = await pay_with_token(account_id=str(user['id']), amount=actual_price, token=token)
    
    if not res.get("success"):
        if lang == "uz":
            await status_msg.edit_text(f"❌ To'lovda xatolik:\n{res.get('error')}\n\nBoshqa ulanishni sinab ko'rsangiz bo'ladi.")
        else:
            await status_msg.edit_text(f"❌ Ошибка оплаты:\n{res.get('error')}")
        return
        
    # SUCCESS PAYMENT! Activate PRO!
    await activate_pro_subscription(telegram_id, plan_id, db, payment_id=res.get("payment_id", "atmos_auto"), amount=actual_price)
    
    plan = PRICING_PLANS.get(plan_id)
    now = datetime.now()
    if 'weekly' in plan_id:
        expires = now + timedelta(days=7)
    elif 'monthly' in plan_id:
        expires = now + timedelta(days=30)
    elif 'yearly' in plan_id:
        expires = now + timedelta(days=365)
    else:
        expires = now + timedelta(days=30)
        
    if lang == "uz":
        text = (
            "🎉 *TABRIKLAYMIZ!*\n\n"
            f"To'lov Muvaffaqiyatli! ({actual_price:,} so'm)\n"
            f"Avto-to'lov faollashtirildi.\n\n"
            "Keyingi to'lov sizning kartangizdan avtomatik yechiladi. Obunani bekor qilish uchun kartani o'chirib qo'yishingiz mumkin."
        )
    else:
        text = (
            "🎉 *ПОЗДРАВЛЯЕМ!*\n\n"
            f"Оплата успешна! ({actual_price:,} сум)\n"
            f"Авто-продление активировано.\n\n"
            "Следующий платеж будет списан автоматически. Вы можете отключить в настройках."
        )
        
    await status_msg.edit_text(text, parse_mode="Markdown")
    # Send main welcome message
    await send_pro_activation_message(telegram_id, plan_id, expires)


async def activate_pro_subscription(telegram_id: int, plan_id: str, db, payment_id: str, amount: int):
    user = await db.get_user(telegram_id)
    now = datetime.now()
    if 'weekly' in plan_id:
        expires = now + timedelta(days=7)
    elif 'monthly' in plan_id:
        expires = now + timedelta(days=30)
    elif 'yearly' in plan_id:
        expires = now + timedelta(days=365)
    else:
        expires = now + timedelta(days=30)
        
    if db.is_postgres:
        await db.execute_update(
            """UPDATE users SET 
                subscription_tier = 'pro',
                subscription_expires = $1,
                subscription_plan = $2,
                subscription_auto_renew = 1
                WHERE telegram_id = $3""",
            expires, plan_id, telegram_id
        )
        await db.execute_update(
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status, completed_at)
                VALUES ($1, $2, $3, 'atmos_auto', $4, 'completed', $5)""",
            user['id'], plan_id, amount, payment_id, now
        )
    else:
        await db.execute_update(
            """UPDATE users SET 
                subscription_tier = 'pro',
                subscription_expires = ?,
                subscription_plan = ?,
                subscription_auto_renew = 1
                WHERE telegram_id = ?""",
            expires.isoformat(), plan_id, telegram_id
        )
        await db.execute_update(
            """INSERT INTO payments (user_id, plan_id, amount_uzs, payment_method, payment_id, status, completed_at)
                VALUES (?, ?, ?, 'atmos_auto', ?, 'completed', ?)""",
            user['id'], plan_id, amount, payment_id, now.isoformat()
        )


async def atmos_unbind_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if db.is_postgres:
        await db.execute_update("UPDATE user_cards SET is_active = FALSE WHERE user_id = $1", user['id'])
        await db.execute_update("UPDATE users SET subscription_auto_renew = 0 WHERE telegram_id = $1", telegram_id)
    else:
        await db.execute_update("UPDATE user_cards SET is_active = 0 WHERE user_id = ?", user['id'])
        await db.execute_update("UPDATE users SET subscription_auto_renew = 0 WHERE telegram_id = ?", telegram_id)
        
    if lang == "uz":
        await query.edit_message_text("✅ Karta va avto-to'lov muvaffaqiyatli bekor qilindi.\n\nEndi sizdan pul yechilmaydi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menyu", callback_data="back_to_main")]]))
    else:
        await query.edit_message_text("✅ Карта и авто-оплата успешно отменены.\n\nБольше списаний не будет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_to_main")]]))

async def handle_atmos_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Master text handler for Atmos states"""
    # Debug logging
    logger.info(f"[ATMOS] handle_atmos_input called. Card={context.user_data.get('awaiting_atmos_card')}, OTP={context.user_data.get('awaiting_atmos_otp')}")
    
    handled = False
    if context.user_data.get("awaiting_atmos_card"):
        handled = await process_atmos_card_input(update, context)
    elif context.user_data.get("awaiting_atmos_otp"):
        handled = await process_atmos_otp_input(update, context)
        
    if handled:
        raise ApplicationHandlerStop()
