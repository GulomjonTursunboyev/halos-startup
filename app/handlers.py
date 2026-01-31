"""
HALOS Bot Handlers
All conversation handlers and command handlers
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ApplicationHandlerStop
)

from app.config import States, PDF_UPLOAD_DIR, TRANSACTION_UPLOAD_DIR, TRANSACTION_EXTENSIONS, ADMIN_IDS
from app.database import get_database
import asyncio
from app.languages import get_message, format_number
from app.subscription_handlers import require_pro, is_user_pro, show_pricing, show_pricing_new_message, show_subscription_expiring_warning
from app.engine import calculate_finances, format_result_message

# Timezone helper for consistent Tashkent time
UZ_TZ = timezone(timedelta(hours=5))


def now_uz():
    """Return current datetime in Asia/Tashkent (UTC+5)."""
    return datetime.now(UZ_TZ)
from app.pdf_parser import parse_katm_pdf, parse_katm_file
from app.transaction_parser import parse_transactions, calculate_monthly_averages

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

async def get_user_language(telegram_id: int) -> str:
    """Get user's language preference"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    return user.get("language", "uz") if user else "uz"


def parse_number(text: str) -> float:
    """Parse number from user input"""
    # Remove spaces, commas, and common text
    cleaned = text.strip().replace(" ", "").replace(",", "").replace(".", "")
    cleaned = cleaned.replace("so'm", "").replace("sum", "").replace("сум", "")
    cleaned = cleaned.replace("mln", "000000").replace("млн", "000000")
    
    try:
        return float(cleaned)
    except ValueError:
        return -1


def get_main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Get persistent main menu keyboard"""
    if lang == "ru":
        keyboard = [
            ["📊 Мои отчёты"],
            ["👤 Профиль", "💎 PRO"],
            ["🌐 Язык", "❓ Помощь"]
        ]
    else:
        keyboard = [
            ["📊 Hisobotlarim"],
            ["👤 Profil", "💎 PRO"],
            ["🌐 Til", "❓ Yordam"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# Main menu button texts for matching
MENU_BUTTONS = {
    "plan": ["📊 Hisobotlarim", "📊 Мои отчёты"],
    "profile": ["👤 Profil", "👤 Профиль"],
    "subscription": ["💎 PRO", "💎 PRO"],
    "language": ["🌐 Til", "🌐 Язык"],
    "help": ["❓ Yordam", "❓ Помощь"],
}


# ==================== START COMMAND ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - check if registered, if not request phone number"""
    # Always clear context for new session/chat
    context.user_data.clear()
    user = update.effective_user
    telegram_id = user.id
    
    # Check if user already registered in database
    db = await get_database()
    existing_user = await db.get_user(telegram_id)
    
    if existing_user and existing_user.get("phone_number"):
        # Update user activity for PRO care scheduler
        await db.update_user_activity(telegram_id)
        
        # User already registered - skip contact sharing
        lang = existing_user.get("language", "uz")
        context.user_data["telegram_id"] = telegram_id
        context.user_data["first_name"] = existing_user.get("first_name") or user.first_name
        context.user_data["last_name"] = existing_user.get("last_name") or user.last_name
        context.user_data["username"] = existing_user.get("username") or user.username
        context.user_data["phone_number"] = existing_user.get("phone_number")
        context.user_data["lang"] = lang
        
        # Show main menu for registered users
        welcome_back = "👋 Xush kelibsiz!\n\nQuyidagi menyudan foydalaning:" if lang == "uz" else "👋 Добро пожаловать!\n\nИспользуйте меню ниже:"
        
        await update.message.reply_text(
            welcome_back,
            reply_markup=get_main_menu_keyboard(lang)
        )
        
        return ConversationHandler.END
        
        return States.MODE
    
    # New user - request phone number for registration
    lang = "uz"  # Default for new users
    
    # Store user info in context
    context.user_data["telegram_id"] = telegram_id
    context.user_data["first_name"] = user.first_name
    context.user_data["last_name"] = user.last_name
    context.user_data["username"] = user.username
    context.user_data["lang"] = lang
    
    # Request phone number
    keyboard = [
        [KeyboardButton(
            get_message("share_contact_button", lang),
            request_contact=True
        )]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        get_message("welcome", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.LANGUAGE


# ==================== CONTACT HANDLER ====================

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle shared contact - save to database immediately"""
    contact = update.message.contact
    telegram_id = update.effective_user.id
    user = update.effective_user
    lang = context.user_data.get("lang", "uz")
    
    # Verify it's the user's own contact
    if contact.user_id != telegram_id:
        await update.message.reply_text(
            get_message("error_contact_mismatch", lang),
            parse_mode="Markdown"
        )
        return States.LANGUAGE
    
    # Store phone number in context
    context.user_data["phone_number"] = contact.phone_number
    
    # IMMEDIATELY save user to database
    db = await get_database()
    existing_user = await db.get_user(telegram_id)
    
    if not existing_user:
        # Create new user in database with phone, name, and telegram_id
        await db.create_user(
            telegram_id=telegram_id,
            phone_number=contact.phone_number,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            language=lang
        )
        logger.info(f"New user registered: {telegram_id} - {contact.phone_number} - {user.first_name}")
    else:
        # Update existing user's phone if needed
        await db.update_user(
            telegram_id,
            phone_number=contact.phone_number,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username
        )
    
    # Send confirmation
    msg = await update.message.reply_text(
        get_message("contact_received", lang),
        reply_markup=ReplyKeyboardRemove()
    )
    try:
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass
    
    # Ask for language
    keyboard = [
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("select_language", lang),
        reply_markup=reply_markup
    )
    
    return States.LANGUAGE


# ==================== LANGUAGE SELECTION ====================

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle language selection - then start financial profile setup"""
    query = update.callback_query
    await query.answer()
    
    # Get selected language
    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang
    
    telegram_id = update.effective_user.id
    db = await get_database()
    
    # User is already created in contact_handler, just update language
    await db.update_user(telegram_id, language=lang)
    
    # Delete the language selection message
    try:
        await query.message.delete()
    except:
        pass
    
    # Registration complete - NOW ASK FOR MODE SELECTION
    welcome_msg = (
        "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n\n"
        "Keling, sizning moliyaviy holatgizni bilib olaylik.\n"
        "Bu sizga kreditlaringizni tezroq to'lab tugatishga yordam beradi! 💪"
    ) if lang == "uz" else (
        "✅ *Вы успешно зарегистрированы!*\n\n"
        "Давайте узнаем вашу финансовую ситуацию.\n"
        "Это поможет вам быстрее погасить кредиты! 💪"
    )
    
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_msg,
        parse_mode="Markdown"
    )
    
    # Ask for mode selection
    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Yolg'iz" if lang == "uz" else "👤 Один",
                callback_data="mode_solo"
            ),
            InlineKeyboardButton(
                "👨‍👩‍👧 Oila" if lang == "uz" else "👨‍👩‍👧 Семья",
                callback_data="mode_family"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mode_msg = (
        "📊 *Qanday rejalashtirmoqchisiz?*\n\n"
        "👤 *Yolg'iz* - faqat o'zingizning moliyangiz\n"
        "👨‍👩‍👧 *Oila* - oila a'zolari bilan birgalikda"
    ) if lang == "uz" else (
        "📊 *Как вы планируете?*\n\n"
        "👤 *Один* - только ваши финансы\n"
        "👨‍👩‍👧 *Семья* - вместе с семьей"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=mode_msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.MODE


# ==================== MODE SELECTION ====================

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection (solo/family) - NEW 7-STEP UX FLOW"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    mode = query.data.replace("mode_", "")
    context.user_data["mode"] = mode
    
    # Set conversation flag - AI should not process text while in conversation
    context.user_data["in_conversation"] = True
    
    # Update user mode in database
    telegram_id = update.effective_user.id
    db = await get_database()
    await db.update_user(telegram_id, mode=mode)
    
    # Confirm mode
    chat_id = update.effective_chat.id
    
    if mode == "solo":
        await query.edit_message_text(get_message("mode_set_solo", lang))
    else:
        await query.edit_message_text(get_message("mode_set_family", lang))
    
    # NEW 7-STEP UX: Start with Step 1 - LOAN PAYMENT
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_loans", lang), callback_data="quick_loan_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_loan_payment", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.LOAN_PAYMENT


# ==================== TRANSACTION HISTORY UPLOAD (MULTI-CARD) ====================

async def transaction_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle transaction history upload choice"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "tx_yes":
        # Initialize multi-card storage
        context.user_data["tx_cards"] = []  # List of card results
        
        # Show instructions
        await query.edit_message_text(
            get_message("transaction_instructions", lang),
            parse_mode="Markdown"
        )
        return States.TRANSACTION_UPLOAD
    
    else:  # tx_no - manual entry
        await query.edit_message_text(
            get_message("input_income_self", lang),
            parse_mode="Markdown"
        )
        return States.INCOME_SELF


def get_monthly_breakdown(transactions):
    """Group transactions by month for breakdown view"""
    from collections import defaultdict
    from datetime import datetime
    
    monthly = defaultdict(lambda: {"income": 0, "expense": 0})
    
    for t in transactions:
        if not t.date:
            continue
        # Try to parse date
        try:
            # Handle various date formats
            date_str = t.date
            month_key = None
            for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                try:
                    dt = datetime.strptime(date_str[:10], fmt)
                    month_key = dt.strftime("%Y-%m")
                    break
                except:
                    continue
            
            if month_key:
                if t.transaction_type.value == "income":
                    monthly[month_key]["income"] += t.amount
                elif t.transaction_type.value == "expense":
                    monthly[month_key]["expense"] += t.amount
        except:
            continue
    
    return dict(sorted(monthly.items()))


async def transaction_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle transaction file upload (supports multiple cards)"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    document = update.message.document
    
    if not document:
        await update.message.reply_text(
            get_message("transaction_invalid_file", lang)
        )
        return States.TRANSACTION_UPLOAD
    
    # Check file extension
    file_ext = Path(document.file_name).suffix.lower()
    if file_ext not in TRANSACTION_EXTENSIONS:
        await update.message.reply_text(
            get_message("transaction_invalid_file", lang)
        )
        return States.TRANSACTION_UPLOAD
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        get_message("transaction_processing", lang)
    )
    
    try:
        # Create upload directory
        TRANSACTION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Download file
        file = await document.get_file()
        file_name = f"{telegram_id}_{document.file_name}"
        file_path = TRANSACTION_UPLOAD_DIR / file_name
        
        await file.download_to_drive(str(file_path))
        
        # Parse transactions
        result = parse_transactions(str(file_path))
        
        # Delete processing message
        await processing_msg.delete()
        
        if result.success and (result.income_count > 0 or result.expense_count > 0):
            # Initialize cards list if not exists
            if "tx_cards" not in context.user_data:
                context.user_data["tx_cards"] = []
            
            # Get card name from filename
            card_name = Path(document.file_name).stem
            # Clean up card name
            card_name = card_name.replace("_", " ").replace("-", " ")
            if len(card_name) > 30:
                card_name = card_name[:30] + "..."
            
            # Calculate monthly averages
            averages = calculate_monthly_averages(result)
            monthly_breakdown = get_monthly_breakdown(result.transactions)
            
            # Store card data
            card_data = {
                "name": card_name,
                "file_name": document.file_name,
                "result": result,
                "averages": averages,
                "monthly_breakdown": monthly_breakdown,
                "total_income": result.total_income,
                "total_expense": result.total_expense,
                "income_count": result.income_count,
                "expense_count": result.expense_count,
                "period_start": result.period_start,
                "period_end": result.period_end
            }
            context.user_data["tx_cards"].append(card_data)
            
            card_num = len(context.user_data["tx_cards"])
            
            # Format period
            period = ""
            if result.period_start and result.period_end:
                period = f"{result.period_start} — {result.period_end}"
            else:
                period = "—"
            
            # Show card added message
            card_msg = get_message("transaction_card_added", lang).format(
                card_num=card_num,
                card_name=card_name,
                period=period,
                income_count=result.income_count,
                total_income=format_number(result.total_income),
                expense_count=result.expense_count,
                total_expense=format_number(result.total_expense)
            )
            
            await update.message.reply_text(card_msg, parse_mode="Markdown")
            
            # Ask to add more or finish
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_message("transaction_add_more", lang),
                        callback_data="tx_add_more"
                    ),
                    InlineKeyboardButton(
                        get_message("transaction_finish_cards", lang),
                        callback_data="tx_finish"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                get_message("transaction_add_more_prompt", lang),
                reply_markup=reply_markup
            )
            
            return States.TRANSACTION_UPLOAD
        
        else:
            # Parsing failed
            await update.message.reply_text(
                get_message("transaction_failed", lang),
                parse_mode="Markdown"
            )
            
            # If we have some cards already, ask to continue
            if context.user_data.get("tx_cards"):
                keyboard = [
                    [
                        InlineKeyboardButton(
                            get_message("transaction_add_more", lang),
                            callback_data="tx_add_more"
                        ),
                        InlineKeyboardButton(
                            get_message("transaction_finish_cards", lang),
                            callback_data="tx_finish"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    get_message("transaction_add_more_prompt", lang),
                    reply_markup=reply_markup
                )
                return States.TRANSACTION_UPLOAD
            else:
                await update.message.reply_text(
                    get_message("input_income_self", lang),
                    parse_mode="Markdown"
                )
                return States.INCOME_SELF
    
    except Exception as e:
        logger.error(f"Transaction file processing error: {e}")
        await processing_msg.delete()
        
        await update.message.reply_text(
            get_message("transaction_failed", lang),
            parse_mode="Markdown"
        )
        
        # If we have some cards, allow continue
        if context.user_data.get("tx_cards"):
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_message("transaction_add_more", lang),
                        callback_data="tx_add_more"
                    ),
                    InlineKeyboardButton(
                        get_message("transaction_finish_cards", lang),
                        callback_data="tx_finish"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                get_message("transaction_add_more_prompt", lang),
                reply_markup=reply_markup
            )
            return States.TRANSACTION_UPLOAD
        else:
            await update.message.reply_text(
                get_message("input_income_self", lang),
                parse_mode="Markdown"
            )
            return States.INCOME_SELF


async def transaction_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle add more cards or finish"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    action = query.data
    
    if action == "tx_add_more":
        await query.edit_message_text(
            get_message("transaction_instructions", lang),
            parse_mode="Markdown"
        )
        return States.TRANSACTION_UPLOAD
    
    elif action == "tx_finish":
        # Show multi-card summary
        return await show_transaction_summary(query, context)
    
    return States.TRANSACTION_UPLOAD


async def show_transaction_summary(query, context) -> int:
    """Show summary of all uploaded cards"""
    lang = context.user_data.get("lang", "uz")
    cards = context.user_data.get("tx_cards", [])
    
    if not cards:
        await query.edit_message_text(
            get_message("input_income_self", lang),
            parse_mode="Markdown"
        )
        return States.INCOME_SELF
    
    # Calculate totals
    total_income = sum(c["total_income"] for c in cards)
    total_expense = sum(c["total_expense"] for c in cards)
    balance = total_income - total_expense
    
    # Calculate monthly averages across all cards
    all_monthly = {}
    for card in cards:
        for month, data in card.get("monthly_breakdown", {}).items():
            if month not in all_monthly:
                all_monthly[month] = {"income": 0, "expense": 0}
            all_monthly[month]["income"] += data["income"]
            all_monthly[month]["expense"] += data["expense"]
    
    # Calculate average monthly
    if all_monthly:
        num_months = len(all_monthly)
        monthly_income = sum(m["income"] for m in all_monthly.values()) / num_months
        monthly_expense = sum(m["expense"] for m in all_monthly.values()) / num_months
    else:
        monthly_income = total_income
        monthly_expense = total_expense
    
    # Store for later use
    context.user_data["tx_total_income"] = total_income
    context.user_data["tx_total_expense"] = total_expense
    context.user_data["tx_monthly_income"] = monthly_income
    context.user_data["tx_monthly_expense"] = monthly_expense
    context.user_data["tx_all_monthly"] = all_monthly
    
    # Build card details
    card_details = ""
    for i, card in enumerate(cards, 1):
        card_detail = get_message("transaction_card_detail", lang).format(
            card_name=f"#{i} {card['name']}",
            total_income=format_number(card["total_income"]),
            total_expense=format_number(card["total_expense"])
        )
        card_details += card_detail + "\n"
    
    # Build monthly breakdown (last 3 months)
    month_lines = []
    sorted_months = sorted(all_monthly.keys(), reverse=True)[:3]
    month_names = {
        "01": "Yanvar" if lang == "uz" else "Январь",
        "02": "Fevral" if lang == "uz" else "Февраль",
        "03": "Mart" if lang == "uz" else "Март",
        "04": "Aprel" if lang == "uz" else "Апрель",
        "05": "May" if lang == "uz" else "Май",
        "06": "Iyun" if lang == "uz" else "Июнь",
        "07": "Iyul" if lang == "uz" else "Июль",
        "08": "Avgust" if lang == "uz" else "Август",
        "09": "Sentyabr" if lang == "uz" else "Сентябрь",
        "10": "Oktyabr" if lang == "uz" else "Октябрь",
        "11": "Noyabr" if lang == "uz" else "Ноябрь",
        "12": "Dekabr" if lang == "uz" else "Декабрь",
    }
    
    for month_key in sorted_months:
        data = all_monthly[month_key]
        year, month = month_key.split("-")
        month_name = month_names.get(month, month)
        month_lines.append(get_message("transaction_month_row", lang).format(
            month=f"{month_name} {year}",
            income=format_number(data["income"]),
            expense=format_number(data["expense"])
        ))
    
    # Build summary message
    summary_msg = get_message("transaction_multi_summary", lang).format(
        card_details=card_details,
        total_income=format_number(total_income),
        total_expense=format_number(total_expense),
        balance=format_number(balance),
        monthly_income=format_number(monthly_income),
        monthly_expense=format_number(monthly_expense)
    )
    
    if month_lines:
        summary_msg += get_message("transaction_monthly_breakdown", lang).format(
            months="\n".join(month_lines)
        )
    
    await query.edit_message_text(summary_msg, parse_mode="Markdown")
    
    # Ask for confirmation
    keyboard = [
        [
            InlineKeyboardButton(
                get_message("transaction_summary_confirm_yes", lang),
                callback_data="tx_summary_confirm"
            )
        ],
        [
            InlineKeyboardButton(
                get_message("transaction_summary_add_income", lang),
                callback_data="tx_summary_add_income"
            )
        ],
        [
            InlineKeyboardButton(
                get_message("transaction_summary_manual", lang),
                callback_data="tx_summary_manual"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        get_message("transaction_summary_confirm", lang),
        reply_markup=reply_markup
    )
    
    return States.TRANSACTION_SUMMARY


async def transaction_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle transaction summary confirmation"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    action = query.data
    
    if action == "tx_summary_confirm":
        # Use the calculated monthly income
        monthly_income = context.user_data.get("tx_monthly_income", 0)
        
        if monthly_income > 0:
            context.user_data["income_self"] = monthly_income
            
            await query.edit_message_text(
                get_message("transaction_income_used", lang).format(
                    amount=format_number(monthly_income)
                )
            )
            
            # Check if family mode needs partner income
            if context.user_data.get("mode") == "family":
                # Add quick button for partner with no income
                keyboard = [
                    [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    get_message("input_income_partner", lang),
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                return States.INCOME_PARTNER
            else:
                context.user_data["income_partner"] = 0
                # Add quick button for own home
                keyboard = [
                    [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    get_message("input_rent", lang),
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                return States.RENT
        else:
            await query.edit_message_text(
                get_message("input_income_self", lang),
                parse_mode="Markdown"
            )
            return States.INCOME_SELF
    
    elif action == "tx_summary_add_income":
        # Ask for additional income
        await query.edit_message_text(
            get_message("transaction_extra_income_prompt", lang),
            parse_mode="Markdown"
        )
        return States.TRANSACTION_SUMMARY
    
    elif action == "tx_summary_manual":
        # Manual entry
        await query.edit_message_text(
            get_message("input_income_self", lang),
            parse_mode="Markdown"
        )
        return States.INCOME_SELF
    
    return States.TRANSACTION_SUMMARY


async def transaction_extra_income_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle extra income input during transaction summary"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    extra_income = parse_number(text)
    
    if extra_income < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.TRANSACTION_SUMMARY
    
    # Add extra income to monthly income
    monthly_income = context.user_data.get("tx_monthly_income", 0)
    total_income = monthly_income + extra_income
    context.user_data["income_self"] = total_income
    
    await update.message.reply_text(
        get_message("transaction_income_used", lang).format(
            amount=format_number(total_income)
        )
    )
    
    # Check if family mode needs partner income
    if context.user_data.get("mode") == "family":
        # Add quick button for partner with no income
        keyboard = [
            [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("input_income_partner", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return States.INCOME_PARTNER
    else:
        context.user_data["income_partner"] = 0
        # Add quick button for own home
        keyboard = [
            [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("input_rent", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return States.RENT


async def transaction_skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text during transaction upload (skip to manual)"""
    lang = context.user_data.get("lang", "uz")
    
    # If we have cards, show summary
    if context.user_data.get("tx_cards"):
        # Create a fake query object for show_transaction_summary
        class FakeQuery:
            message = update.message
            async def edit_message_text(self, text, parse_mode=None):
                await update.message.reply_text(text, parse_mode=parse_mode)
        
        return await show_transaction_summary(FakeQuery(), context)
    
    await update.message.reply_text(
        get_message("input_income_self", lang),
        parse_mode="Markdown"
    )
    
    return States.INCOME_SELF


# ==================== INCOME INPUT ====================

async def income_self_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's income input - accepts text number or file"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Check if this is NEW 7-STEP UX FLOW (expenses already entered)
    is_new_ux_flow = "loan_payment" in context.user_data and "rent" in context.user_data
    
    # Check if user sent a file
    if update.message.document:
        document = update.message.document
        file_ext = Path(document.file_name).suffix.lower()
        
        if file_ext in TRANSACTION_EXTENSIONS:
            # Process transaction file
            processing_msg = await update.message.reply_text(
                get_message("transaction_processing", lang)
            )
            
            try:
                TRANSACTION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                file = await document.get_file()
                file_name = f"{telegram_id}_{document.file_name}"
                file_path = TRANSACTION_UPLOAD_DIR / file_name
                await file.download_to_drive(str(file_path))
                
                result = parse_transactions(str(file_path))
                await processing_msg.delete()
                
                if result.success and result.monthly_income > 0:
                    context.user_data["income_self"] = result.monthly_income
                    
                    await update.message.reply_text(
                        f"✅ *Fayl o'qildi!*\n\n"
                        f"💰 Oylik daromad: *{format_number(result.monthly_income)}* so'm\n"
                        f"📊 {result.income_count} ta kirim topildi",
                        parse_mode="Markdown"
                    )
                    
                    # NEW UX FLOW: Calculate directly
                    if is_new_ux_flow:
                        if context.user_data.get("mode") == "family":
                            keyboard = [
                                [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0_calc")]
                            ]
                            await update.message.reply_text(
                                get_message("input_income_partner", lang),
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                            return States.INCOME_PARTNER
                        else:
                            context.user_data["income_partner"] = 0
                            return await calculate_and_show_results(update, context)
                    
                    # OLD FLOW: Continue to next step
                    if context.user_data.get("mode") == "family":
                        keyboard = [
                            [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0")]
                        ]
                        await update.message.reply_text(
                            get_message("input_income_partner", lang),
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        return States.INCOME_PARTNER
                    else:
                        context.user_data["income_partner"] = 0
                        await update.message.reply_text(
                            get_message("input_rent", lang),
                            parse_mode="Markdown"
                        )
                        return States.RENT
                else:
                    await update.message.reply_text(
                        "❌ Fayldan daromad topilmadi. Raqam kiriting.",
                        parse_mode="Markdown"
                    )
                    return States.INCOME_SELF
            except Exception as e:
                await processing_msg.delete()
                await update.message.reply_text(
                    f"❌ Xatolik. Raqam kiriting.",
                    parse_mode="Markdown"
                )
                return States.INCOME_SELF
    
    # Process text input
    text = update.message.text
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.INCOME_SELF
    
    if amount == 0:
        await update.message.reply_text(
            get_message("number_too_small", lang)
        )
        return States.INCOME_SELF
    
    context.user_data["income_self"] = amount
    
    await update.message.reply_text(
        get_message("income_saved", lang).format(amount=format_number(amount))
    )
    
    # NEW UX FLOW: Calculate directly (expenses already entered)
    if is_new_ux_flow:
        if context.user_data.get("mode") == "family":
            keyboard = [
                [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0_calc")]
            ]
            await update.message.reply_text(
                get_message("input_income_partner", lang),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return States.INCOME_PARTNER
        else:
            context.user_data["income_partner"] = 0
            return await calculate_and_show_results(update, context)
    
    # OLD FLOW: Check if family mode
    if context.user_data.get("mode") == "family":
        # Add quick button for partner with no income
        keyboard = [
            [InlineKeyboardButton(get_message("btn_partner_no_income", lang), callback_data="quick_partner_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("input_income_partner", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return States.INCOME_PARTNER
    else:
        context.user_data["income_partner"] = 0
        await update.message.reply_text(
            get_message("input_rent", lang),
            parse_mode="Markdown"
        )
        return States.RENT


async def income_partner_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle partner's income input"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.INCOME_PARTNER
    
    context.user_data["income_partner"] = amount
    
    await update.message.reply_text(
        get_message("income_saved", lang).format(amount=format_number(amount))
    )
    
    # NEW UX FLOW: Calculate directly (expenses already entered)
    is_new_ux_flow = "loan_payment" in context.user_data and "rent" in context.user_data
    if is_new_ux_flow:
        return await calculate_and_show_results(update, context)
    
    # OLD FLOW: Add quick button for own home
    keyboard = [
        [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_rent", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.RENT


async def quick_partner_income_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for partner with no income"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["income_partner"] = 0
    
    await query.edit_message_text(
        get_message("income_saved", lang).format(amount="0")
    )
    
    # NEW UX FLOW: Calculate directly (expenses already entered)
    is_new_ux_flow = "loan_payment" in context.user_data and "rent" in context.user_data
    if is_new_ux_flow:
        return await calculate_and_show_results_from_callback(update, context)
    
    # OLD FLOW: Add quick button for own home
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_rent", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.RENT


# ==================== LIVING COSTS INPUT ====================

async def rent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle rent input - Step 4, then go to utilities"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.RENT
    
    context.user_data["rent"] = amount
    
    await update.message.reply_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Go to Step 5: Utilities
    keyboard = [
        [
            InlineKeyboardButton(get_message("btn_utilities_300", lang), callback_data="quick_utilities_300000"),
            InlineKeyboardButton(get_message("btn_utilities_500", lang), callback_data="quick_utilities_500000"),
            InlineKeyboardButton(get_message("btn_utilities_800", lang), callback_data="quick_utilities_800000")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_utilities", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.UTILITIES


async def quick_rent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for own home (rent = 0)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["rent"] = 0
    chat_id = update.effective_chat.id
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount="0")
    )
    
    # Go to Step 5: Utilities
    keyboard = [
        [
            InlineKeyboardButton(get_message("btn_utilities_300", lang), callback_data="quick_utilities_300000"),
            InlineKeyboardButton(get_message("btn_utilities_500", lang), callback_data="quick_utilities_500000"),
            InlineKeyboardButton(get_message("btn_utilities_800", lang), callback_data="quick_utilities_800000")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_utilities", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.UTILITIES


async def kindergarten_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle other debts input (personal loans from friends/family) - Step 3"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.KINDERGARTEN
    
    context.user_data["kindergarten"] = amount  # Store as kindergarten for DB compatibility
    
    await update.message.reply_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Go to Step 4: Rent
    keyboard = [
        [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_rent", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.RENT


async def quick_kindergarten_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for no other debts"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["kindergarten"] = 0
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount="0")
    )
    
    # Go to Step 4: Rent
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton(get_message("btn_own_home", lang), callback_data="quick_rent_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_rent", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.RENT


async def utilities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle utilities input - Step 5, then go to mandatory expenses"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.UTILITIES
    
    context.user_data["utilities"] = amount
    
    await update.message.reply_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Go to Step 6: Mandatory expenses (then calculate)
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_mandatory", lang), callback_data="quick_mandatory_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_mandatory_expenses", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.MANDATORY_EXPENSES


async def quick_utilities_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for common utility amounts"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Extract amount from callback data (quick_utilities_300000 -> 300000)
    amount = int(query.data.split("_")[-1])
    context.user_data["utilities"] = amount
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Go to Step 6: Mandatory expenses (then calculate)
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_mandatory", lang), callback_data="quick_mandatory_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_mandatory_expenses", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.MANDATORY_EXPENSES


# ==================== MANDATORY EXPENSES (STEP 6/7) ====================

async def mandatory_expenses_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Step 6: Mandatory expenses input"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text.strip()
    
    # Parse amount (supports: 12mln, 12 mln, 12000000, etc)
    amount = parse_number(text)
    if amount < 0:
        await update.message.reply_text(get_message("error_parse", lang))
        return States.MANDATORY_EXPENSES
    
    amount = amount if amount >= 0 else 0
    context.user_data["mandatory_expenses"] = amount
    
    # Confirmation
    await update.message.reply_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Step 7: Ask for INCOME (final step before calculate)
    await update.message.reply_text(
        get_message("input_income_self", lang),
        parse_mode="Markdown"
    )
    
    return States.INCOME_SELF


async def quick_mandatory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'no mandatory expenses' quick button"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    chat_id = update.effective_chat.id
    
    context.user_data["mandatory_expenses"] = 0
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount=format_number(0))
    )
    
    # Step 7: Ask for INCOME (final step before calculate)
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_income_self", lang),
        parse_mode="Markdown"
    )
    
    return States.INCOME_SELF


# ==================== KATM PDF UPLOAD ====================

async def katm_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle KATM choice (yes/no)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "katm_yes":
        # PRO tekshiruv
        if not await require_pro(update, context):
            context.user_data["in_conversation"] = False
            return ConversationHandler.END
        # Show instructions for PDF upload
        await query.edit_message_text(
            get_message("katm_instructions", lang),
            parse_mode="Markdown"
        )
        return States.KATM_UPLOAD
    
    else:  # katm_no - manual entry
        # Add quick button for no loans
        keyboard = [
            [InlineKeyboardButton(get_message("btn_no_loans", lang), callback_data="quick_loan_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return States.LOAN_PAYMENT


async def katm_pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle PDF or HTML file upload for KATM"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Check if document exists
    document = update.message.document
    if not document:
        await update.message.reply_text(
            get_message("katm_not_pdf", lang)
        )
        return States.KATM_UPLOAD
    
    # Check file extension - accept PDF and HTML
    file_ext = Path(document.file_name).suffix.lower()
    if file_ext not in ['.pdf', '.html', '.htm']:
        await update.message.reply_text(
            get_message("katm_not_pdf", lang)
        )
        return States.KATM_UPLOAD
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        get_message("katm_processing", lang)
    )
    
    try:
        # Create upload directory
        PDF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Download file
        file = await document.get_file()
        file_name = f"{telegram_id}_{document.file_name}"
        file_path = PDF_UPLOAD_DIR / file_name
        
        await file.download_to_drive(str(file_path))
        
        # Parse file (auto-detect format)
        from app.pdf_parser import parse_katm_file
        result = parse_katm_file(str(file_path))
        
        # Delete processing message
        await processing_msg.delete()
        
        if result.success and result.loans:
            # Store parsed data
            context.user_data["loan_payment"] = result.total_monthly_payment
            context.user_data["total_debt"] = result.total_remaining_debt
            context.user_data["katm_loans"] = result.loans
            context.user_data["katm_pdf"] = file_name
            
            # Save to database
            db = await get_database()
            user = await db.get_user(telegram_id)
            if user:
                await db.delete_user_katm_loans(user["id"])
                await db.save_katm_loans(
                    user_id=user["id"],
                    loans=result.loans,
                    pdf_filename=file_name
                )
            
            # Format loans list
            loans_list = "\n".join([
                get_message("katm_loan_item", lang).format(
                    bank=loan.bank_name,
                    amount=format_number(loan.remaining_balance)
                )
                for loan in result.loans
            ])
            
            # Show success message with parsed data
            success_msg = get_message("katm_success", lang).format(
                loans_list=loans_list,
                total_debt=format_number(result.total_remaining_debt),
                monthly_payment=format_number(result.total_monthly_payment)
            )
            
            # Add confirmation buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_message("katm_confirm_yes", lang), 
                        callback_data="katm_confirm_yes"
                    ),
                    InlineKeyboardButton(
                        get_message("katm_confirm_no", lang), 
                        callback_data="katm_confirm_no"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_msg + "\n\n" + get_message("katm_confirm", lang),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
            return States.KATM_UPLOAD
        
        else:
            # Parsing failed - fallback to manual
            error_msg = result.error_message if result.error_message else ""
            
            await update.message.reply_text(
                get_message("katm_failed", lang),
                parse_mode="Markdown"
            )
            
            await update.message.reply_text(
                get_message("input_loan_payment", lang),
                parse_mode="Markdown"
            )
            
            return States.LOAN_PAYMENT
    
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        await processing_msg.delete()
        
        await update.message.reply_text(
            get_message("katm_failed", lang),
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )
        
        return States.LOAN_PAYMENT


async def katm_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle KATM data confirmation"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "katm_confirm_yes":
        # Data confirmed, proceed to calculation
        await query.edit_message_text(
            get_message("debt_saved", lang)
        )
        
        # Go directly to calculation
        return await calculate_and_show_results_from_callback(query, context)
    
    else:  # katm_confirm_no - manual entry
        await query.edit_message_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )
        return States.LOAN_PAYMENT


async def katm_skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle skip button or text during KATM upload"""
    lang = context.user_data.get("lang", "uz")
    
    await update.message.reply_text(
        get_message("input_loan_payment", lang),
        parse_mode="Markdown"
    )
    
    return States.LOAN_PAYMENT


# ==================== LOAN INPUT ====================

async def loan_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle monthly loan payment input - Step 1/8"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.LOAN_PAYMENT
    
    context.user_data["loan_payment"] = amount
    
    await update.message.reply_text(
        get_message("debt_saved", lang)
    )
    
    # If no loan payment, skip total debt and go to Step 3 (other debts)
    if amount == 0:
        context.user_data["total_debt"] = 0
        
        # Go to Step 3: Other debts (personal loans)
        keyboard = [
            [InlineKeyboardButton(get_message("btn_no_kids", lang), callback_data="quick_kindergarten_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("input_kindergarten", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        return States.KINDERGARTEN
    
    # Add quick button for no debt remaining
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_debt", lang), callback_data="quick_debt_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_total_debt", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.TOTAL_DEBT


async def quick_loan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for no loans - go to Step 3 (other debts)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    chat_id = update.effective_chat.id
    
    context.user_data["loan_payment"] = 0
    context.user_data["total_debt"] = 0
    
    await query.edit_message_text(
        get_message("debt_saved", lang)
    )
    
    # Go to Step 3: Other debts (personal loans from friends/family)
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_kids", lang), callback_data="quick_kindergarten_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_kindergarten", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KINDERGARTEN


async def quick_debt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for no remaining debt"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    chat_id = update.effective_chat.id
    
    context.user_data["total_debt"] = 0
    
    await query.edit_message_text(
        get_message("debt_saved", lang)
    )
    
    # Go to Step 3: Other debts (personal loans)
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_kids", lang), callback_data="quick_kindergarten_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("input_kindergarten", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KINDERGARTEN


async def total_debt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle total debt input - Step 2, then go to other debts"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.TOTAL_DEBT
    
    context.user_data["total_debt"] = amount
    
    await update.message.reply_text(
        get_message("debt_saved", lang)
    )
    
    # Go to Step 3: Other debts (personal loans from friends/family)
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_kids", lang), callback_data="quick_kindergarten_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("input_kindergarten", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KINDERGARTEN


# ==================== CALCULATION & RESULTS ====================

# ==================== TRIAL HANDLER ====================
async def start_trial_callback(update, context):
    """Handle 3-day free trial activation"""
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    db = await get_database()
    user = await db.get_user(telegram_id)
    if not user:
        await update.callback_query.answer(get_message("error_not_registered", lang), show_alert=True)
        return ConversationHandler.END
    if user.get("trial_used", 0):
        await update.callback_query.answer(get_message("trial_already_used", lang) if "trial_already_used" in get_message else "Siz allaqachon trialdan foydalandingiz", show_alert=True)
        return ConversationHandler.END
    # Activate trial: set PRO, 3 days, mark trial_used
    from datetime import datetime, timedelta
    expires = datetime.now() + timedelta(days=3)
    
    if db.is_postgres:
        await db.execute_update(
            """UPDATE users SET subscription_tier = 'pro', subscription_expires = $1, 
               subscription_plan = 'trial', trial_used = 1, updated_at = CURRENT_TIMESTAMP 
               WHERE telegram_id = $2""",
            expires, telegram_id
        )
    else:
        await db._connection.execute(
            """UPDATE users SET subscription_tier = 'pro', subscription_expires = ?, 
               subscription_plan = 'trial', trial_used = 1, updated_at = CURRENT_TIMESTAMP 
               WHERE telegram_id = ?""",
            (expires.isoformat(), telegram_id)
        )
        await db._connection.commit()
    # Show confirmation
    msg = get_message("trial_activated", lang)
    if isinstance(msg, dict):
        msg = msg.get(lang, list(msg.values())[0])
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        msg.format(date=expires.strftime("%d.%m.%Y")),
        parse_mode="Markdown"
    )
    # Clear conversation flag
    context.user_data["in_conversation"] = False
    return ConversationHandler.END

async def get_user_subscription_status(telegram_id: int) -> bool:
    """Check if user has active PRO subscription"""
    from datetime import datetime
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return False
    
    tier = user.get("subscription_tier", "free")
    if tier == "free":
        return False
    
    expires = user.get("subscription_expires")
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if datetime.now() > expires:
            return False
    
    return True


async def calculate_and_show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculate finances and show results with DRAMATIC animation"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # === DRAMATIC CALCULATION ANIMATION ===
    # Step 1: Initial calculating message
    calc_msg = await update.message.reply_text(
        get_message("calculating", lang),
        parse_mode="Markdown"
    )
    await asyncio.sleep(1.0)
    
    # Step 2: Analyzing data
    try:
        await calc_msg.edit_text(
            get_message("calculating_step1", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(1.2)
    
    # Step 3: Finding HALOS date
    try:
        await calc_msg.edit_text(
            get_message("calculating_step2", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(1.5)
    
    # Step 4: Result ready!
    try:
        await calc_msg.edit_text(
            get_message("calculating_step3", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(0.8)
    
    # Delete calculating message
    try:
        await calc_msg.delete()
    except:
        pass
    
    # Get all input data
    income_self = context.user_data.get("income_self", 0)
    income_partner = context.user_data.get("income_partner", 0)
    rent = context.user_data.get("rent", 0)
    kindergarten = context.user_data.get("kindergarten", 0)
    utilities = context.user_data.get("utilities", 0)
    loan_payment = context.user_data.get("loan_payment", 0)
    total_debt = context.user_data.get("total_debt", 0)
    
    # Build financial input
    from app.engine import FinancialInput
    financial_input = FinancialInput(
        mode=context.user_data.get("mode", "solo"),
        income_self=income_self,
        income_partner=income_partner,
        rent=rent,
        kindergarten=kindergarten,
        utilities=utilities,
        loan_payment=loan_payment,
        total_debt=total_debt
    )
    
    # Calculate
    result = calculate_finances(financial_input)
    
    # Save to database
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        # Create financial profile
        profile_id = await db.create_financial_profile(
            user_id=user["id"],
            income_self=income_self,
            income_partner=income_partner,
            rent=rent,
            kindergarten=kindergarten,
            utilities=utilities,
            loan_payment=loan_payment,
            total_debt=total_debt
        )
        
        # Save calculation
        await db.save_calculation(
            user_id=user["id"],
            profile_id=profile_id,
            calculation_data=result
        )
    
    # Check if user has PRO subscription
    is_pro = await get_user_subscription_status(telegram_id)
    
    # Format and send result (partial for free users)
    result_message = format_result_message(result, lang, is_pro=is_pro)
    
    # Add action buttons
    if is_pro:
        keyboard = [
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    else:
        # Show PRO upgrade button for free users
        keyboard = [
            [InlineKeyboardButton(
                "💎 PRO" if lang == "uz" else "💎 PRO",
                callback_data="show_pricing"
            )],
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        result_message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Clear conversation flag
    context.user_data["in_conversation"] = False
    return ConversationHandler.END


async def calculate_and_show_results_from_callback(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculate finances and show results (from callback query) with DRAMATIC animation"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = query.from_user.id
    
    # === DRAMATIC CALCULATION ANIMATION ===
    # Step 1: Initial calculating message
    calc_msg = await query.message.reply_text(
        get_message("calculating", lang),
        parse_mode="Markdown"
    )
    await asyncio.sleep(1.0)
    
    # Step 2: Analyzing data
    try:
        await calc_msg.edit_text(
            get_message("calculating_step1", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(1.2)
    
    # Step 3: Finding HALOS date
    try:
        await calc_msg.edit_text(
            get_message("calculating_step2", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(1.5)
    
    # Step 4: Result ready!
    try:
        await calc_msg.edit_text(
            get_message("calculating_step3", lang),
            parse_mode="Markdown"
        )
    except:
        pass
    await asyncio.sleep(0.8)
    
    # Delete calculating message
    try:
        await calc_msg.delete()
    except:
        pass
    
    # Get all input data
    income_self = context.user_data.get("income_self", 0)
    income_partner = context.user_data.get("income_partner", 0)
    rent = context.user_data.get("rent", 0)
    kindergarten = context.user_data.get("kindergarten", 0)
    utilities = context.user_data.get("utilities", 0)
    loan_payment = context.user_data.get("loan_payment", 0)
    total_debt = context.user_data.get("total_debt", 0)
    
    # Build financial input
    from app.engine import FinancialInput
    financial_input = FinancialInput(
        mode=context.user_data.get("mode", "solo"),
        income_self=income_self,
        income_partner=income_partner,
        rent=rent,
        kindergarten=kindergarten,
        utilities=utilities,
        loan_payment=loan_payment,
        total_debt=total_debt
    )
    
    # Calculate
    result = calculate_finances(financial_input)
    
    # Save to database
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        # Create financial profile
        profile_id = await db.create_financial_profile(
            user_id=user["id"],
            income_self=income_self,
            income_partner=income_partner,
            rent=rent,
            kindergarten=kindergarten,
            utilities=utilities,
            loan_payment=loan_payment,
            total_debt=total_debt
        )
        
        # Update KATM loans with profile_id if they exist
        katm_loans = context.user_data.get("katm_loans")
        if katm_loans:
            # Loans already saved, could update profile_id here if needed
            pass
        
        # Save calculation
        await db.save_calculation(
            user_id=user["id"],
            profile_id=profile_id,
            calculation_data=result
        )
    
    # Check if user has PRO subscription
    is_pro = await get_user_subscription_status(telegram_id)
    
    # Format and send result (partial for free users)
    result_message = format_result_message(result, lang, is_pro=is_pro)
    
    # Add action buttons
    if is_pro:
        keyboard = [
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(
                "💎 PRO" if lang == "uz" else "💎 PRO",
                callback_data="show_pricing"
            )],
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        result_message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Clear conversation flag
    context.user_data["in_conversation"] = False
    return ConversationHandler.END


# ==================== RECALCULATE ====================

async def recalculate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle recalculate button - directly show result if saved data exists"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check if user has saved financial profile
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        profile = await db.get_financial_profile(user["id"])
        if profile and profile.get("income_self", 0) > 0:
            # User has saved data - calculate directly
            return await recalc_saved_callback(update, context)
    
    # No saved data - go to new calculation
    return await recalc_new_callback(update, context)


async def recalc_saved_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recalculate using saved profile data"""
    query = update.callback_query
    if query and not query.data.startswith("recalc"):
        # Already answered in recalculate_callback
        pass
    elif query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return await recalc_new_callback(update, context)
    
    profile = await db.get_financial_profile(user["id"])
    
    if not profile:
        return await recalc_new_callback(update, context)
    
    # Show calculating message
    calc_msg = await query.message.reply_text(
        get_message("calculating_saved", lang)
    )
    
    # Get mode from user settings
    mode = user.get("mode", "solo")
    
    # Build financial input from saved profile
    from app.engine import FinancialInput
    
    financial_input = FinancialInput(
        mode=mode,
        income_self=profile.get("income_self", 0),
        income_partner=profile.get("income_partner", 0),
        rent=profile.get("rent", 0),
        kindergarten=profile.get("kindergarten", 0),
        utilities=profile.get("utilities", 0),
        loan_payment=profile.get("loan_payment", 0),
        total_debt=profile.get("total_debt", 0)
    )
    
    # Calculate
    result = calculate_finances(financial_input)
    
    # Check PRO status
    is_pro = await get_user_subscription_status(telegram_id)
    
    # Format result
    result_message = format_result_message(result, lang, is_pro=is_pro)
    
    # Delete calculating message
    await calc_msg.delete()
    
    # Add action buttons
    if is_pro:
        keyboard = [
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(
                "💎 PRO ga o'tish" if lang == "uz" else "💎 Перейти на PRO",
                callback_data="show_pricing"
            )],
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        result_message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Clear conversation flag
    context.user_data["in_conversation"] = False
    return ConversationHandler.END


async def recalc_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start new calculation from scratch"""
    query = update.callback_query
    if query:
        await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Clear previous data but keep user info
    telegram_id = context.user_data.get("telegram_id") or update.effective_user.id
    phone = context.user_data.get("phone_number")
    
    context.user_data.clear()
    context.user_data["telegram_id"] = telegram_id
    context.user_data["phone_number"] = phone
    context.user_data["lang"] = lang
    
    # Ask for mode again
    keyboard = [
        [
            InlineKeyboardButton(get_message("mode_solo", lang), callback_data="mode_solo"),
            InlineKeyboardButton(get_message("mode_family", lang), callback_data="mode_family")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.message.reply_text(
            get_message("select_mode", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    return States.MODE


# ==================== OTHER COMMANDS ====================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    await update.message.reply_text(
        get_message("help", lang),
        parse_mode="Markdown"
    )


# ==================== PROFILE MANAGEMENT ====================

async def build_profile_content(user: dict, profile: dict, lang: str, telegram_id: int) -> tuple:
    """Build profile text and keyboard for display - shows user info, financial data and subscription status"""
    from datetime import datetime
    
    # Get user personal info - only first name, ignore last name
    first_name = user.get("first_name") or ""
    # Clean up - remove None and empty strings
    first_name = first_name if first_name and first_name != "None" else ""
    display_name = first_name.strip() or ("Foydalanuvchi" if lang == "uz" else "Пользователь")
    phone = user.get("phone_number", "")
    mode = user.get("mode", "solo")
    
    # Get subscription status
    is_pro = await get_user_subscription_status(telegram_id)
    tier = user.get("subscription_tier", "free")
    expires = user.get("subscription_expires")
    
    if is_pro and expires:
        if isinstance(expires, str):
            try:
                expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                days_left = (expires_dt - datetime.now()).days
                if lang == "uz":
                    sub_status = f"💎 PRO ({days_left} kun qoldi)"
                else:
                    sub_status = f"💎 PRO ({days_left} дней осталось)"
            except:
                sub_status = "💎 PRO" if lang == "uz" else "💎 PRO"
        else:
            sub_status = "💎 PRO" if lang == "uz" else "💎 PRO"
    else:
        sub_status = "🆓 Bepul" if lang == "uz" else "🆓 Бесплатный"
    
    # Get financial data from profile
    income_self = profile.get("income_self", 0) if profile else 0
    income_partner = profile.get("income_partner", 0) if profile else 0
    rent = profile.get("rent", 0) if profile else 0
    kindergarten = profile.get("kindergarten", 0) if profile else 0
    utilities = profile.get("utilities", 0) if profile else 0
    loan_payment = profile.get("loan_payment", 0) if profile else 0
    total_debt = profile.get("total_debt", 0) if profile else 0
    
    # Mode text
    if lang == "uz":
        mode_text = "👤 Yolg'iz" if mode == "solo" else "👥 Oila"
    else:
        mode_text = "👤 Один" if mode == "solo" else "👥 Семья"
    
    # Build profile with all financial data
    if lang == "uz":
        profile_text = (
            f"👤 *{display_name}*\n"
            f"📱 {phone}\n"
            f"📊 Obuna: {sub_status}\n"
            f"🏠 Rejim: {mode_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *DAROMADLAR:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Mening daromadim: *{format_number(income_self)} so'm*\n"
        )
        if mode == "family" or income_partner > 0:
            profile_text += f"└ Sherik daromadi: *{format_number(income_partner)} so'm*\n"
        else:
            profile_text = profile_text.replace("├ Mening", "└ Mening")
        
        profile_text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *XARAJATLAR:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Ijara: *{format_number(rent)} so'm*\n"
            f"├ Majburiy to'lovlar: *{format_number(kindergarten)} so'm*\n"
            f"└ Kommunal: *{format_number(utilities)} so'm*\n"
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 *KREDIT:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Oylik to'lov: *{format_number(loan_payment)} so'm*\n"
            f"└ Umumiy qarz: *{format_number(total_debt)} so'm*\n"
        )
    else:
        profile_text = (
            f"👤 *{display_name}*\n"
            f"📱 {phone}\n"
            f"📊 Подписка: {sub_status}\n"
            f"🏠 Режим: {mode_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *ДОХОДЫ:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Мой доход: *{format_number(income_self)} сум*\n"
        )
        if mode == "family" or income_partner > 0:
            profile_text += f"└ Доход партнёра: *{format_number(income_partner)} сум*\n"
        else:
            profile_text = profile_text.replace("├ Мой", "└ Мой")
        
        profile_text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *РАСХОДЫ:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Аренда: *{format_number(rent)} сум*\n"
            f"├ Обязат. платежи: *{format_number(kindergarten)} сум*\n"
            f"└ Коммунальные: *{format_number(utilities)} сум*\n"
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 *КРЕДИТ:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Ежемес. платёж: *{format_number(loan_payment)} сум*\n"
            f"└ Общий долг: *{format_number(total_debt)} сум*\n"
        )
    
    # Create keyboard - edit buttons for financial data
    keyboard = [
        [
            InlineKeyboardButton(get_message("btn_edit_income_self", lang), callback_data="edit_income_self"),
            InlineKeyboardButton(get_message("btn_edit_income_partner", lang), callback_data="edit_income_partner"),
        ],
        [
            InlineKeyboardButton(get_message("btn_edit_rent", lang), callback_data="edit_rent"),
            InlineKeyboardButton(get_message("btn_edit_kindergarten", lang), callback_data="edit_kindergarten"),
        ],
        [
            InlineKeyboardButton(get_message("btn_edit_utilities", lang), callback_data="edit_utilities"),
            InlineKeyboardButton(get_message("btn_edit_loan_payment", lang), callback_data="edit_loan_payment"),
        ],
        [
            InlineKeyboardButton(get_message("btn_edit_total_debt", lang), callback_data="edit_total_debt"),
            InlineKeyboardButton(get_message("btn_edit_mode", lang), callback_data="edit_mode"),
        ],
    ]
    
    # Add upgrade button if not PRO
    if not is_pro:
        # Check if trial available
        trial_available = user and not user.get("trial_used", 0)
        if trial_available:
            keyboard.append([
                InlineKeyboardButton("🎁 3 kun BEPUL sinash" if lang == "uz" else "🎁 3 дня БЕСПЛАТНО", callback_data="activate_trial")
            ])
        keyboard.append([
            InlineKeyboardButton("💎 PRO olish" if lang == "uz" else "💎 Получить PRO", callback_data="show_pricing")
        ])
    
    full_text = get_message("profile_header", lang) + "\n\n" + profile_text
    
    return full_text, keyboard


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command - show user profile with edit options"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await update.message.reply_text(
            get_message("profile_no_data", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    profile = await db.get_financial_profile(user["id"])
    
    # Build profile content even if no financial profile yet
    # profile can be None, build_profile_content handles it
    full_text, keyboard = await build_profile_content(user, profile, lang, telegram_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        full_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def show_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show profile from callback"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await query.edit_message_text(get_message("profile_no_data", lang))
        return
    
    profile = await db.get_financial_profile(user["id"])
    
    # Build profile content even if no financial profile yet
    full_text, keyboard = await build_profile_content(user, profile, lang, telegram_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            full_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception:
        # If edit fails, send new message
        await query.message.reply_text(
            full_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


# Field name mappings
PROFILE_FIELDS = {
    "income_self": {"uz": "Daromadim", "ru": "Мой доход"},
    "income_partner": {"uz": "Sherik daromadi", "ru": "Доход партнёра"},
    "rent": {"uz": "Ijara", "ru": "Аренда"},
    "kindergarten": {"uz": "Majburiy to'lovlar", "ru": "Обязат. платежи"},
    "utilities": {"uz": "Kommunal", "ru": "Коммунальные"},
    "loan_payment": {"uz": "Oylik to'lov", "ru": "Ежемес. платёж"},
    "total_debt": {"uz": "Umumiy qarz", "ru": "Общий долг"},
}


async def edit_profile_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit field button click - ask for new value"""
    query = update.callback_query
    await query.answer()
    
    field = query.data.replace("edit_", "")  # e.g., "income_self"
    lang = context.user_data.get("lang", "uz")
    
    if field == "mode":
        # Show mode selection
        keyboard = [
            [
                InlineKeyboardButton(get_message("mode_solo", lang), callback_data="profile_mode_solo"),
                InlineKeyboardButton(get_message("mode_family", lang), callback_data="profile_mode_family")
            ],
            [InlineKeyboardButton(get_message("btn_back_to_profile", lang), callback_data="show_profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_message("select_mode", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return
    
    # Store which field we're editing
    context.user_data["editing_field"] = field
    
    field_name = PROFILE_FIELDS.get(field, {}).get(lang, field)
    
    keyboard = [[InlineKeyboardButton(get_message("btn_back_to_profile", lang), callback_data="show_profile")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        get_message("edit_enter_new_value", lang).format(field=field_name),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def handle_profile_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for profile field editing"""
    editing_field = context.user_data.get("editing_field")
    
    if not editing_field:
        return  # Not editing anything
    
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Parse the number
    value = parse_number(update.message.text)
    
    if value < 0:
        await update.message.reply_text(
            get_message("edit_invalid_number", lang)
        )
        # Stop propagation - don't let AI process invalid input
        raise ApplicationHandlerStop()
    
    # Update in database
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        raise ApplicationHandlerStop()
    
    profile = await db.get_financial_profile(user["id"])
    
    if profile:
        # Update existing profile
        await db.update_financial_profile(profile["id"], **{editing_field: value})
    else:
        # Create new profile with this field
        await db.create_financial_profile(user["id"], **{editing_field: value})
    
    # Clear editing state
    field_name = PROFILE_FIELDS.get(editing_field, {}).get(lang, editing_field)
    context.user_data["editing_field"] = None
    
    # Show success message with recalculate button
    keyboard = [
        [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
        [InlineKeyboardButton(get_message("btn_back_to_profile", lang), callback_data="show_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("edit_success", lang).format(field=field_name) + "\n\n" + 
        get_message("profile_updated_recalculate", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Stop propagation - don't let AI process this input
    raise ApplicationHandlerStop()


async def profile_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mode change from profile"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace("profile_mode_", "")  # "solo" or "family"
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Update in database
    db = await get_database()
    await db.update_user(telegram_id, mode=mode)
    
    # Show success and return to profile
    mode_name = get_message("mode_solo", lang) if mode == "solo" else get_message("mode_family", lang)
    
    keyboard = [
        [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
        [InlineKeyboardButton(get_message("btn_back_to_profile", lang), callback_data="show_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        get_message("edit_success", lang).format(field=mode_name) + "\n\n" +
        get_message("profile_updated_recalculate", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show last calculation"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await update.message.reply_text(
            get_message("no_data", lang)
        )
        return
    
    calculation = await db.get_latest_calculation(user["id"])
    
    if not calculation:
        await update.message.reply_text(
            get_message("no_data", lang)
        )
        return
    
    # Format result
    result_message = format_result_message(calculation, lang)
    
    await update.message.reply_text(
        get_message("status_header", lang) + "\n\n" + result_message,
        parse_mode="Markdown"
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /language command"""
    keyboard = [
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="change_lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="change_lang_ru")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 Tilni tanlang / Выберите язык:",
        reply_markup=reply_markup
    )


async def change_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language change from /language command"""
    query = update.callback_query
    await query.answer()
    
    lang = query.data.replace("change_lang_", "")
    telegram_id = update.effective_user.id
    
    db = await get_database()
    await db.update_user(telegram_id, language=lang)
    
    context.user_data["lang"] = lang
    
    await query.edit_message_text(
        get_message("language_set", lang)
    )
    
    # Update main menu with new language
    await query.message.reply_text(
        "✅",
        reply_markup=get_main_menu_keyboard(lang)
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel command"""
    lang = context.user_data.get("lang", "uz")
    
    await update.message.reply_text(
        get_message("restart", lang),
        reply_markup=get_main_menu_keyboard(lang)
    )
    
    # Clear conversation flag
    context.user_data["in_conversation"] = False
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    error = context.error
    
    # Log error with full details
    if error:
        import traceback
        error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"Error occurred: {type(error).__name__}: {error}\n{error_traceback}")
    else:
        logger.error("Unknown error occurred (no error details)")
    
    if update and update.effective_message:
        lang = context.user_data.get("lang", "uz") if context.user_data else "uz"
        
        # Database timeout uchun maxsus xabar
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            await update.effective_message.reply_text(
                "⏳ Server band. Iltimos, qayta urinib ko'ring." if lang == "uz" else 
                "⏳ Сервер занят. Попробуйте ещё раз."
            )
        else:
            await update.effective_message.reply_text(
                get_message("error_generic", lang)
            )


# ==================== CONVERSATION HANDLER ====================

def get_conversation_handler() -> ConversationHandler:
    """Create and return the main conversation handler"""
    
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(recalculate_callback, pattern="^recalculate$"),
            CallbackQueryHandler(recalc_saved_callback, pattern="^recalc_saved$"),
            CallbackQueryHandler(recalc_new_callback, pattern="^recalc_new$"),
            # Entry point for menu mode selection (from 📊 Hisobotlarim)
            CallbackQueryHandler(mode_callback, pattern="^mode_(solo|family)$"),
        ],
        states={
            States.LANGUAGE: [
                MessageHandler(filters.CONTACT, contact_handler),
                CallbackQueryHandler(language_callback, pattern="^lang_"),
            ],
            States.MODE: [
                CallbackQueryHandler(mode_callback, pattern="^mode_"),
                CallbackQueryHandler(recalc_saved_callback, pattern="^recalc_saved$"),
                CallbackQueryHandler(recalc_new_callback, pattern="^recalc_new$"),
            ],
            States.TRANSACTION_CHOICE: [
                CallbackQueryHandler(transaction_choice_callback, pattern="^tx_(yes|no)$"),
            ],
            States.TRANSACTION_UPLOAD: [
                MessageHandler(filters.Document.ALL, transaction_file_handler),
                CallbackQueryHandler(transaction_action_callback, pattern="^tx_(add_more|finish)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_skip_handler),
            ],
            States.TRANSACTION_SUMMARY: [
                CallbackQueryHandler(transaction_summary_callback, pattern="^tx_summary_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_extra_income_handler),
            ],
            States.INCOME_SELF: [
                MessageHandler(filters.Document.ALL, income_self_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, income_self_handler),
            ],
            States.INCOME_PARTNER: [
                MessageHandler(filters.Document.ALL, income_partner_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, income_partner_handler),
                CallbackQueryHandler(quick_partner_income_callback, pattern="^quick_partner_0$"),
            ],
            States.RENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rent_handler),
                CallbackQueryHandler(quick_rent_callback, pattern="^quick_rent_0$"),
            ],
            States.KINDERGARTEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, kindergarten_handler),
                CallbackQueryHandler(quick_kindergarten_callback, pattern="^quick_kindergarten_0$"),
            ],
            States.UTILITIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, utilities_handler),
                CallbackQueryHandler(quick_utilities_callback, pattern="^quick_utilities_"),
            ],
            States.KATM_CHOICE: [
                CallbackQueryHandler(katm_choice_callback, pattern="^katm_(yes|no)$"),
            ],
            States.KATM_UPLOAD: [
                MessageHandler(filters.Document.PDF, katm_pdf_handler),
                MessageHandler(filters.Document.ALL, katm_pdf_handler),  # Catch non-PDF
                CallbackQueryHandler(katm_confirm_callback, pattern="^katm_confirm_(yes|no)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, katm_skip_handler),
            ],
            States.LOAN_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, loan_payment_handler),
                CallbackQueryHandler(quick_loan_callback, pattern="^quick_loan_0$"),
            ],
            States.TOTAL_DEBT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, total_debt_handler),
                CallbackQueryHandler(quick_debt_callback, pattern="^quick_debt_0$"),
            ],
            States.MANDATORY_EXPENSES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mandatory_expenses_handler),
                CallbackQueryHandler(quick_mandatory_callback, pattern="^quick_mandatory_0$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CommandHandler("start", start_command),
        ],
        allow_reentry=True,
        per_message=False,
    )

# Register additional handlers globally (for dispatcher setup)
def add_global_handlers_to_app(application):
    """Add handlers that work outside the conversation flow"""
    # Only add trial handler here - other handlers are added in bot.py
    application.add_handler(CallbackQueryHandler(start_trial_callback, pattern="^start_trial$"), group=0)


# Keep old function for backwards compatibility
def add_trial_handler_to_app(application):
    add_global_handlers_to_app(application)


# ==================== MAIN MENU HANDLERS ====================

async def menu_plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 📊 Hisobotlarim button - show comprehensive financial report"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    # If no profile yet, start the data collection flow
    if not profile:
        # Ask for mode (solo/family)
        keyboard = [
            [
                InlineKeyboardButton(get_message("mode_solo", lang), callback_data="mode_solo"),
                InlineKeyboardButton(get_message("mode_family", lang), callback_data="mode_family")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("select_mode", lang),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    
    # ==================== BUGUNGI KUNLIK HISOBOT (YANGI UX) ====================
    from app.ai_assistant import get_transaction_summary, EXPENSE_CATEGORIES, INCOME_CATEGORIES, get_debt_summary
    from datetime import datetime
    
    # Bugungi tranzaksiyalar
    try:
        today_summary = await get_transaction_summary(db, user["id"], days=1)
    except:
        today_summary = {"total_income": 0, "total_expense": 0, "income_by_category": {}, "expense_by_category": {}}
    
    # Oylik summari
    try:
        month_summary = await get_transaction_summary(db, user["id"], days=30)
    except:
        month_summary = {"total_income": 0, "total_expense": 0, "income_by_category": {}, "expense_by_category": {}}
    
    today_income = today_summary.get("total_income", 0)
    today_expense = today_summary.get("total_expense", 0)
    today_balance = today_income - today_expense
    
    month_income = month_summary.get("total_income", 0)
    month_expense = month_summary.get("total_expense", 0)
    month_balance = month_income - month_expense
    
    # Profil ma'lumotlari
    income_self = profile.get("income_self", 0) or 0
    income_partner = profile.get("income_partner", 0) or 0
    total_income = income_self + income_partner
    
    rent = profile.get("rent", 0) or 0
    kindergarten = profile.get("kindergarten", 0) or 0
    utilities = profile.get("utilities", 0) or 0
    loan_payment = profile.get("loan_payment", 0) or 0
    total_debt = profile.get("total_debt", 0) or 0
    
    mandatory_total = rent + kindergarten + utilities + loan_payment
    free_cash = total_income - mandatory_total
    
    # Shaxsiy qarzlar
    try:
        debt_summary = await get_debt_summary(db, user["id"])
    except:
        debt_summary = {"total_lent": 0, "total_borrowed": 0, "net_balance": 0, "lent_count": 0, "borrowed_count": 0}
    
    # ==================== ZAMONAVIY KUNLIK HISOBOT ====================
    today_date = datetime.now().strftime("%d.%m.%Y")
    
    if lang == "uz":
        msg = (
            f"📊 *BUGUNGI HISOBOT* • {today_date}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        # Bugungi balans (katta va aniq)
        if today_balance >= 0:
            msg += f"💰 *Bugungi balans:* +{today_balance:,} so'm\n"
        else:
            msg += f"🔴 *Bugungi balans:* {today_balance:,} so'm\n"
        
        msg += (
            f"   ├ 📥 Kirim: +{today_income:,}\n"
            f"   └ 📤 Chiqim: -{today_expense:,}\n\n"
        )
        
        # Bugungi xarajatlar kategoriya bo'yicha
        if today_summary.get("expense_by_category"):
            msg += "💸 *Bugungi xarajatlar:*\n"
            sorted_expenses = sorted(today_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses[:5]:  # Top 5
                cat_name = EXPENSE_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                percentage = (amount / today_expense * 100) if today_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"   {cat_name}\n   {bar} {amount:,} ({percentage:.0f}%)\n"
            msg += "\n"
        
        # Oylik xulosa (qisqacha)
        msg += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *OYLIK XULOSA* (30 kun)\n"
        )
        if month_balance >= 0:
            msg += f"   💚 Balans: +{month_balance:,} so'm\n"
        else:
            msg += f"   🔴 Balans: {month_balance:,} so'm\n"
        msg += (
            f"   ├ Kirim: +{month_income:,}\n"
            f"   └ Chiqim: -{month_expense:,}\n\n"
        )
        
        # PRO uchun HALOS USULI
        if is_pro and free_cash > 0:
            living_70 = free_cash * 0.70
            debt_20 = free_cash * 0.20
            wealth_10 = free_cash * 0.10
            
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🌟 *HALOS USULI*\n"
                f"   Bo'sh pul: *{free_cash:,}* so'm\n\n"
                f"   🏠 *Yashash*\n"
                f"      {living_70:,.0f} so'm/oy\n"
                f"      {living_70/30:,.0f} so'm/kun\n\n"
                f"   ⚡ *Qarz to'lash*\n"
                f"      {debt_20:,.0f} so'm/oy\n"
            )
            if total_debt > 0:
                import math
                from dateutil.relativedelta import relativedelta
                months_to_pay = math.ceil(total_debt / (loan_payment + debt_20)) if (loan_payment + debt_20) > 0 else 0
                exit_date = datetime.now() + relativedelta(months=months_to_pay)
                msg += f"      📆 Qarzdan chiqish: {exit_date.strftime('%B %Y')}\n"
            
            msg += (
                f"\n   💰 *Jamg'arma*\n"
                f"      {wealth_10:,.0f} so'm/oy\n"
                f"      Yilda: ~{wealth_10*12:,.0f} so'm\n"
            )
        elif not is_pro and free_cash > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 *HALOS USULI*\n"
                "   _PRO obuna bilan HALOS_\n"
                "   _usulini oching_\n"
            )
        
        # Shaxsiy qarzlar (qisqacha)
        if debt_summary["total_lent"] > 0 or debt_summary["total_borrowed"] > 0:
            net = debt_summary['net_balance']
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n🤝 *QARZLAR*\n"
            if net > 0:
                msg += f"   💚 Sizga qaytariladi: +{net:,} so'm\n"
            elif net < 0:
                msg += f"   🔴 Siz qaytarasiz: {net:,} so'm\n"
            else:
                msg += "   ⚪ Qarz yo'q\n"
    
    else:
        # Russian version
        msg = (
            f"📊 *ОТЧЁТ ЗА СЕГОДНЯ* • {today_date}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if today_balance >= 0:
            msg += f"💰 *Баланс за сегодня:* +{today_balance:,} сум\n"
        else:
            msg += f"🔴 *Баланс за сегодня:* {today_balance:,} сум\n"
        
        msg += (
            f"   ├ 📥 Приход: +{today_income:,}\n"
            f"   └ 📤 Расход: -{today_expense:,}\n\n"
        )
        
        if today_summary.get("expense_by_category"):
            msg += "💸 *Расходы сегодня:*\n"
            sorted_expenses = sorted(today_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses[:5]:
                cat_name = EXPENSE_CATEGORIES["ru"].get(cat, "📦 Прочее")
                percentage = (amount / today_expense * 100) if today_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"   {cat_name}\n   {bar} {amount:,} ({percentage:.0f}%)\n"
            msg += "\n"
        
        msg += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *ИТОГИ МЕСЯЦА* (30 дней)\n"
        )
        if month_balance >= 0:
            msg += f"   💚 Баланс: +{month_balance:,} сум\n"
        else:
            msg += f"   🔴 Баланс: {month_balance:,} сум\n"
        msg += (
            f"   ├ Приход: +{month_income:,}\n"
            f"   └ Расход: -{month_expense:,}\n\n"
        )
        
        if is_pro and free_cash > 0:
            living_70 = free_cash * 0.70
            debt_20 = free_cash * 0.20
            wealth_10 = free_cash * 0.10
            
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🌟 *МЕТОД HALOS*\n"
                f"   Свободные: *{free_cash:,}* сум\n\n"
                f"   🏠 *Жизнь (70%)*\n"
                f"      {living_70:,.0f} сум/мес\n"
                f"      {living_70/30:,.0f} сум/день\n\n"
                f"   ⚡ *Погашение долга (20%)*\n"
                f"      {debt_20:,.0f} сум/мес\n"
            )
            if total_debt > 0:
                import math
                from dateutil.relativedelta import relativedelta
                months_to_pay = math.ceil(total_debt / (loan_payment + debt_20)) if (loan_payment + debt_20) > 0 else 0
                exit_date = datetime.now() + relativedelta(months=months_to_pay)
                msg += f"      📆 Выход из долга: {exit_date.strftime('%B %Y')}\n"
            
            msg += (
                f"\n   💰 *Накопления (10%)*\n"
                f"      {wealth_10:,.0f} сум/мес\n"
                f"      В год: ~{wealth_10*12:,.0f} сум\n"
            )
        elif not is_pro and free_cash > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 *МЕТОД HALOS*\n"
                "   _С PRO подпиской метод_\n"
                "   _HALOS доступен_\n"
            )
        
        if debt_summary["total_lent"] > 0 or debt_summary["total_borrowed"] > 0:
            net = debt_summary['net_balance']
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n🤝 *ДОЛГИ*\n"
            if net > 0:
                msg += f"   💚 Вернут вам: +{net:,} сум\n"
            elif net < 0:
                msg += f"   🔴 Вернёте вы: {net:,} сум\n"
            else:
                msg += "   ⚪ Долгов нет\n"
    
    # ==================== TUGMALAR (YANGI UX) ====================
    if is_pro:
        keyboard = [
            [InlineKeyboardButton(
                "🌟 HALOS holati" if lang == "uz" else "🌟 Статус HALOS",
                callback_data="show_halos_status"
            )],
            [InlineKeyboardButton(
                "📈 Batafsil hisobot" if lang == "uz" else "📈 Подробный отчёт",
                callback_data="detailed_report"
            )],
            [
                InlineKeyboardButton(
                    "📅 Haftalik" if lang == "uz" else "📅 Неделя",
                    callback_data="report_weekly"
                ),
                InlineKeyboardButton(
                    "📆 Oylik" if lang == "uz" else "📆 Месяц",
                    callback_data="report_monthly"
                )
            ],
            [InlineKeyboardButton(
                "📥 Excel yuklab olish" if lang == "uz" else "📥 Скачать Excel",
                callback_data="pro_export_excel"
            )],
            [
                InlineKeyboardButton(
                    "📋 Qarzlar" if lang == "uz" else "📋 Долги",
                    callback_data="ai_debt_list"
                ),
                InlineKeyboardButton(
                    "✏️ Tahrirlash" if lang == "uz" else "✏️ Изменить",
                    callback_data="recalculate"
                )
            ]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(
                "📈 Batafsil hisobot" if lang == "uz" else "📈 Подробный отчёт",
                callback_data="detailed_report"
            )],
            [InlineKeyboardButton(
                "💎 PRO ga o'tish" if lang == "uz" else "💎 Перейти на PRO",
                callback_data="show_pricing"
            )],
            [
                InlineKeyboardButton(
                    "📋 Qarzlar" if lang == "uz" else "📋 Долги",
                    callback_data="ai_debt_list"
                ),
                InlineKeyboardButton(
                    "✏️ Tahrirlash" if lang == "uz" else "✏️ Изменить",
                    callback_data="recalculate"
                )
            ]
        ]
    
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection from main menu (solo/family) - NEW 8-STEP UX FLOW"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    mode = query.data.replace("mode_", "")
    context.user_data["mode"] = mode
    
    # Update user mode in database
    db = await get_database()
    await db.update_user(telegram_id, mode=mode)
    
    # Confirm mode
    if mode == "solo":
        confirm_msg = get_message("mode_set_solo", lang)
    else:
        confirm_msg = get_message("mode_set_family", lang)
    
    await query.edit_message_text(confirm_msg)
    
    # Wait a moment
    await asyncio.sleep(1)
    
    # NEW 8-STEP UX: Start with Step 1 - LOAN PAYMENT
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_loans", lang), callback_data="quick_loan_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        get_message("input_loan_payment", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Set conversation state
    context.user_data["in_onboarding_flow"] = True
    return States.LOAN_PAYMENT


async def menu_income_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle income input from main menu flow"""
    if not context.user_data.get("awaiting_income"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    text = update.message.text.strip()
    
    # Parse income amount
    income = parse_number(text)
    if income <= 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return
    
    context.user_data["income_self"] = income
    context.user_data["awaiting_income"] = False
    
    mode = context.user_data.get("mode", "solo")
    
    if mode == "family":
        # Ask for partner income
        context.user_data["awaiting_partner_income"] = True
        await update.message.reply_text(
            get_message("input_income_partner", lang),
            parse_mode="Markdown"
        )
    else:
        # Skip to credit history choice
        context.user_data["income_partner"] = 0
        await ask_credit_history_choice(update, context, lang)


async def ask_credit_history_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    """Ask user to input credit data - step by step"""
    # Set flags for credit input flow
    context.user_data["awaiting_credit_input"] = True
    context.user_data["awaiting_credit_file"] = True
    context.user_data["credit_step"] = "initial"  # initial -> monthly -> total
    
    keyboard = [
        [InlineKeyboardButton(
            get_message("btn_upload_credit", lang),
            callback_data="menu_credit_upload"
        )],
        [InlineKeyboardButton(
            get_message("btn_no_credit", lang),
            callback_data="menu_credit_none"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("credit_history_choice", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


def parse_simple_number(text: str) -> int:
    """
    Parse a simple number from text with mln/млн support.
    Returns the number in base units (so'm)
    """
    import re
    
    text_lower = text.lower().strip()
    
    # Check if just "0" or "yo'q" / "нет"
    if text_lower in ["0", "yo'q", "yoq", "нет", "net"]:
        return 0
    
    # Remove spaces
    text_clean = re.sub(r'\s+', '', text_lower)
    
    # Check for mln/млн suffix
    multiplier = 1
    if 'mln' in text_clean or 'млн' in text_clean or 'million' in text_clean:
        multiplier = 1_000_000
        text_clean = re.sub(r'(mln|млн|million)', '', text_clean)
    elif 'ming' in text_clean or 'тыс' in text_clean:
        multiplier = 1_000
        text_clean = re.sub(r'(ming|тыс)', '', text_clean)
    
    # Extract number
    match = re.search(r'[\d.,]+', text_clean)
    if match:
        num_str = match.group().replace(',', '.')
        try:
            value = float(num_str) * multiplier
            return int(value)
        except:
            pass
    
    # Fallback to parse_number
    return parse_number(text)


async def smart_credit_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle credit input - step by step (monthly payment -> total debt)"""
    logger.info(f"smart_credit_input_handler called. awaiting_credit_input={context.user_data.get('awaiting_credit_input')}")
    
    if not context.user_data.get("awaiting_credit_input"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    text = update.message.text.strip()
    credit_step = context.user_data.get("credit_step", "initial")
    
    logger.info(f"Processing credit input: {text}, step: {credit_step}")
    
    # Parse the number
    amount = parse_simple_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return
    
    # Step logic
    if credit_step == "initial" or credit_step == "monthly":
        # First step: Monthly payment
        context.user_data["loan_payment"] = amount
        
        if amount == 0:
            # No credit - save and finish
            context.user_data["total_debt"] = 0
            context.user_data["awaiting_credit_input"] = False
            context.user_data["awaiting_credit_file"] = False
            context.user_data["credit_step"] = None
            await update.message.reply_text("✅")
            await save_and_show_menu_results(update.message, context, telegram_id, lang)
        else:
            # Move to step 2: Ask for total debt
            context.user_data["credit_step"] = "total"
            await update.message.reply_text(
                get_message("input_total_debt", lang),
                parse_mode="Markdown"
            )
    
    elif credit_step == "total":
        # Second step: Total debt
        context.user_data["total_debt"] = amount
        context.user_data["awaiting_credit_input"] = False
        context.user_data["awaiting_credit_file"] = False
        context.user_data["credit_step"] = None
        
        # Show confirmation
        monthly = context.user_data.get("loan_payment", 0)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    get_message("credit_confirm_yes", lang),
                    callback_data="credit_confirm_yes"
                ),
                InlineKeyboardButton(
                    get_message("credit_confirm_no", lang),
                    callback_data="credit_confirm_no"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_message("credit_parsed_result", lang).format(
                monthly_payment=format_number(monthly),
                total_debt=format_number(amount)
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


async def credit_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle credit data confirmation"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "credit_confirm_yes":
        # Confirmed - save and show results
        context.user_data["awaiting_credit_input"] = False
        context.user_data["awaiting_credit_file"] = False
        context.user_data["credit_step"] = None
        await query.edit_message_text(get_message("debt_saved", lang))
        await save_and_show_menu_results(query.message, context, telegram_id, lang)
    
    else:  # credit_confirm_no - restart from monthly payment
        context.user_data["awaiting_credit_input"] = True
        context.user_data["credit_step"] = "monthly"
        await query.edit_message_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )


async def menu_credit_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle credit history choice from menu"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "menu_credit_upload":
        # Ask for file upload
        context.user_data["awaiting_credit_file"] = True
        context.user_data["awaiting_credit_input"] = True
        context.user_data["credit_step"] = "file"
        await query.edit_message_text(
            get_message("upload_credit_file", lang),
            parse_mode="Markdown"
        )
    
    elif choice == "menu_credit_manual":
        # Manual entry - step by step
        context.user_data["awaiting_credit_input"] = True
        context.user_data["awaiting_credit_file"] = False
        context.user_data["credit_step"] = "monthly"
        await query.edit_message_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )
    
    elif choice == "menu_credit_none":
        # No credits - save and show results
        context.user_data["loan_payment"] = 0
        context.user_data["total_debt"] = 0
        context.user_data["awaiting_credit_input"] = False
        context.user_data["awaiting_credit_file"] = False
        context.user_data["credit_step"] = None
        await query.edit_message_text("✅")
        await save_and_show_menu_results(query.message, context, telegram_id, lang)


async def menu_credit_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle credit history file upload from menu flow"""
    if not context.user_data.get("awaiting_credit_file"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    document = update.message.document
    if not document:
        return
    
    # Check file extension
    file_ext = Path(document.file_name).suffix.lower()
    if file_ext not in ['.pdf', '.html', '.htm']:
        await update.message.reply_text(
            get_message("katm_not_pdf", lang)
        )
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        get_message("katm_processing", lang)
    )
    
    try:
        # Create upload directory
        PDF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Download file
        file = await document.get_file()
        file_name = f"{telegram_id}_{document.file_name}"
        file_path = PDF_UPLOAD_DIR / file_name
        
        await file.download_to_drive(str(file_path))
        
        # Parse file
        from app.pdf_parser import parse_katm_file
        result = parse_katm_file(str(file_path))
        
        # Delete processing message
        await processing_msg.delete()
        
        if result.success and result.loans:
            # Store parsed data
            context.user_data["loan_payment"] = result.total_monthly_payment
            context.user_data["total_debt"] = result.total_remaining_debt
            context.user_data["katm_loans"] = result.loans
            context.user_data["awaiting_credit_file"] = False
            
            # Save to database
            db = await get_database()
            user = await db.get_user(telegram_id)
            if user:
                await db.delete_user_katm_loans(user["id"])
                await db.save_katm_loans(
                    user_id=user["id"],
                    loans=result.loans,
                    pdf_filename=file_name
                )
            
            # Format loans list
            loans_list = "\n".join([
                get_message("katm_loan_item", lang).format(
                    bank=loan.bank_name,
                    amount=format_number(loan.remaining_balance)
                )
                for loan in result.loans
            ])
            
            # Show success message with parsed data
            success_msg = get_message("katm_success", lang).format(
                loans_list=loans_list,
                total_debt=format_number(result.total_remaining_debt),
                monthly_payment=format_number(result.total_monthly_payment)
            )
            
            # Add confirmation buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_message("katm_confirm_yes", lang), 
                        callback_data="menu_katm_confirm_yes"
                    ),
                    InlineKeyboardButton(
                        get_message("katm_confirm_no", lang), 
                        callback_data="menu_katm_confirm_no"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_msg + "\n\n" + get_message("katm_confirm", lang),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        else:
            # Parsing failed - fallback to manual
            context.user_data["awaiting_credit_file"] = False
            context.user_data["awaiting_loan_payment"] = True
            
            await update.message.reply_text(
                get_message("katm_failed", lang),
                parse_mode="Markdown"
            )
            
            await update.message.reply_text(
                get_message("input_loan_payment", lang),
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Credit file processing error: {e}")
        await processing_msg.delete()
        
        context.user_data["awaiting_credit_file"] = False
        context.user_data["awaiting_loan_payment"] = True
        
        await update.message.reply_text(
            get_message("katm_failed", lang),
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )


async def menu_katm_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle KATM confirmation from menu flow"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    choice = query.data
    
    if choice == "menu_katm_confirm_yes":
        # Data confirmed - save and show results
        await query.edit_message_text(get_message("debt_saved", lang))
        await save_and_show_menu_results(query.message, context, telegram_id, lang)
    
    else:  # menu_katm_confirm_no - manual entry
        context.user_data["awaiting_loan_payment"] = True
        await query.edit_message_text(
            get_message("input_loan_payment", lang),
            parse_mode="Markdown"
        )


async def save_and_show_menu_results(message, context: ContextTypes.DEFAULT_TYPE, telegram_id: int, lang: str) -> None:
    """Save profile and show results from menu flow"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        await db.create_financial_profile(
            user_id=user["id"],
            income_self=context.user_data.get("income_self", 0),
            income_partner=context.user_data.get("income_partner", 0),
            loan_payment=context.user_data.get("loan_payment", 0),
            total_debt=context.user_data.get("total_debt", 0)
        )
    
    total_debt = context.user_data.get("total_debt", 0)
    
    if total_debt == 0:
        # Wealth mode - no debt
        await message.reply_text(
            get_message("debt_free_message", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
    else:
        # Show debt results
        import math
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        
        loan_payment = context.user_data.get("loan_payment", 0)
        if loan_payment > 0:
            months = math.ceil(total_debt / loan_payment)
            exit_date = datetime.now() + relativedelta(months=months)
            exit_str = exit_date.strftime("%B %Y")
            
            # Calculate PRO benefits
            income_self = context.user_data.get('income_self', 0)
            income_partner = context.user_data.get('income_partner', 0)
            total_income = income_self + income_partner
            free_cash = total_income - loan_payment
            
            if free_cash > 0:
                extra_payment = free_cash * 0.2  # 20% extra to debt
                savings_monthly = free_cash * 0.1  # 10% savings
                total_payment_pro = loan_payment + extra_payment
                pro_months = math.ceil(total_debt / total_payment_pro)
                months_saved = months - pro_months
                pro_exit_date = datetime.now() + relativedelta(months=pro_months)
                pro_exit_str = pro_exit_date.strftime("%B %Y")
                savings_at_exit = savings_monthly * pro_months
            else:
                months_saved = 0
                pro_exit_str = exit_str
                savings_at_exit = 0
            
            if lang == "uz":
                msg = (
                    f"✅ *Ma'lumotlar saqlandi!*\n\n"
                    f"📊 *Sizning yo'lingiz:*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Daromad: *{format_number(income_self)} so'm*\n"
                    f"💳 Yuk: *{format_number(total_debt)} so'm*\n"
                    f"📅 To'lov: *{format_number(loan_payment)} so'm/oy*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🗓 *Taxminiy HALOS sanangiz:* {exit_str}\n"
                    f"📆 *Qolgan muddat:* {months} oy\n\n"
                )
                
                if months_saved > 0:
                    msg += (
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💎 *PRO YECHIM:*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *Aqlli taqsimlash:*\n"
                        f"├ 🏦 Boylik uchun: *{format_number(int(savings_monthly))} so'm*\n"
                        f"├ ⚡ Kredit to'lovi: *{format_number(int(extra_payment))} so'm*\n"
                        f"└ 🏠 Yashash: *{format_number(int(free_cash * 0.7))} so'm*\n\n"
                        f"📅 *Natija:*\n"
                        f"├ ⏱ *{months_saved} oy* ertaroq — *{pro_exit_str}*\n"
                        f"└ 💰 *{format_number(int(savings_at_exit))} so'm* boylik\n\n"
                        f"🎁 *PRO imkoniyatlari:*\n"
                        f"├ 📈 Haftalik/oylik statistika\n"
                        f"├ 📊 Excel hisobotlar\n"
                        f"├ 🔔 Eslatmalar va maslahatlar\n"
                        f"└ 🏆 Shaxsiy maqsadlar\n\n"
                        f"🔒 _To'liq foydalanish uchun PRO oling_"
                    )
                else:
                    msg += f"💎 PRO bilan tezroq yengillashish mumkin!"
            else:
                msg = (
                    f"✅ *Данные сохранены!*\n\n"
                    f"📊 *Ваш путь:*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Доход: *{format_number(income_self)} сум*\n"
                    f"💳 Нагрузка: *{format_number(total_debt)} сум*\n"
                    f"📅 Платёж: *{format_number(loan_payment)} сум/мес*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🗓 *Примерная дата HALOS:* {exit_str}\n"
                    f"📆 *Осталось:* {months} мес\n\n"
                )
                
                if months_saved > 0:
                    msg += (
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💎 *PRO РЕШЕНИЕ:*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *Умное распределение:*\n"
                        f"├ 🏦 Для богатства: *{format_number(int(savings_monthly))} сум*\n"
                        f"├ ⚡ Платёж по кредиту: *{format_number(int(extra_payment))} сум*\n"
                        f"└ 🏠 Жизнь: *{format_number(int(free_cash * 0.7))} сум*\n\n"
                        f"📅 *Результат:*\n"
                        f"├ ⏱ На *{months_saved} мес* раньше — *{pro_exit_str}*\n"
                        f"└ 💰 *{format_number(int(savings_at_exit))} сум* богатства\n\n"
                        f"🎁 *Возможности PRO:*\n"
                        f"├ 📈 Еженедельная/месячная статистика\n"
                        f"├ 📊 Excel отчёты\n"
                        f"├ 🔔 Напоминания и советы\n"
                        f"└ 🏆 Личные цели\n\n"
                        f"🔒 _Получите PRO для полного доступа_"
                    )
                else:
                    msg += f"💎 С PRO можно освободиться быстрее!"
        else:
            msg = get_message("debt_no_data", lang) if lang == "uz" else get_message("debt_no_data", lang)
        
        await message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )


async def menu_partner_income_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle partner income input"""
    if not context.user_data.get("awaiting_partner_income"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    text = update.message.text.strip()
    income = parse_number(text)
    
    if income < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return
    
    context.user_data["income_partner"] = income
    context.user_data["awaiting_partner_income"] = False
    
    # Ask for credit history choice instead of direct loan payment
    await ask_credit_history_choice(update, context, lang)


async def menu_loan_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle loan payment input"""
    if not context.user_data.get("awaiting_loan_payment"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    text = update.message.text.strip()
    payment = parse_number(text)
    
    if payment < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return
    
    context.user_data["loan_payment"] = payment
    context.user_data["awaiting_loan_payment"] = False
    context.user_data["awaiting_total_debt"] = True
    
    await update.message.reply_text(
        get_message("input_total_debt", lang),
        parse_mode="Markdown"
    )


async def menu_total_debt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle total debt input and save profile"""
    if not context.user_data.get("awaiting_total_debt"):
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    text = update.message.text.strip()
    debt = parse_number(text)
    
    if debt < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return
    
    context.user_data["total_debt"] = debt
    context.user_data["awaiting_total_debt"] = False
    
    # Save to database
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        await db.create_financial_profile(
            user_id=user["id"],
            income_self=context.user_data.get("income_self", 0),
            income_partner=context.user_data.get("income_partner", 0),
            loan_payment=context.user_data.get("loan_payment", 0),
            total_debt=debt
        )
    
    # Show results
    if debt == 0:
        # Wealth mode
        await update.message.reply_text(
            get_message("debt_free_message", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
    else:
        # Debt mode - show simple calculation
        import math
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        
        loan_payment = context.user_data.get("loan_payment", 0)
        if loan_payment > 0:
            months = math.ceil(debt / loan_payment)
            exit_date = datetime.now() + relativedelta(months=months)
            exit_str = exit_date.strftime("%B %Y")
            
            # Calculate PRO benefits
            income_self = context.user_data.get('income_self', 0)
            income_partner = context.user_data.get('income_partner', 0)
            total_income = income_self + income_partner
            free_cash = total_income - loan_payment
            
            if free_cash > 0:
                extra_payment = free_cash * 0.2  # 20% extra to debt
                savings_monthly = free_cash * 0.1  # 10% savings
                total_payment_pro = loan_payment + extra_payment
                pro_months = math.ceil(debt / total_payment_pro)
                months_saved = months - pro_months
                pro_exit_date = datetime.now() + relativedelta(months=pro_months)
                pro_exit_str = pro_exit_date.strftime("%B %Y")
                savings_at_exit = savings_monthly * pro_months
            else:
                months_saved = 0
                pro_exit_str = exit_str
                savings_at_exit = 0
            
            if lang == "uz":
                msg = (
                    f"✅ *Ma'lumotlar saqlandi!*\n\n"
                    f"📊 *Sizning yo'lingiz:*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Daromad: *{format_number(income_self)} so'm*\n"
                    f"💳 Yuk: *{format_number(debt)} so'm*\n"
                    f"📅 To'lov: *{format_number(loan_payment)} so'm/oy*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🗓 *Taxminiy HALOS sanangiz:* {exit_str}\n"
                    f"📆 *Qolgan muddat:* {months} oy\n\n"
                )
                
                if months_saved > 0:
                    msg += (
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💎 *PRO YECHIM:*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *Aqlli taqsimlash:*\n"
                        f"├ 🏦 Boylik uchun: *{format_number(int(savings_monthly))} so'm*\n"
                        f"├ ⚡ Kredit to'lovi: *{format_number(int(extra_payment))} so'm*\n"
                        f"└ 🏠 Yashash: *{format_number(int(free_cash * 0.7))} so'm*\n\n"
                        f"📅 *Natija:*\n"
                        f"├ ⏱ *{months_saved} oy* ertaroq — *{pro_exit_str}*\n"
                        f"└ 💰 *{format_number(int(savings_at_exit))} so'm* boylik\n\n"
                        f"🎁 *PRO imkoniyatlari:*\n"
                        f"├ 📈 Haftalik/oylik statistika\n"
                        f"├ 📊 Excel hisobotlar\n"
                        f"├ 🔔 Eslatmalar va maslahatlar\n"
                        f"└ 🏆 Shaxsiy maqsadlar\n\n"
                        f"🔒 _To'liq foydalanish uchun PRO oling_"
                    )
                else:
                    msg += f"💎 PRO bilan tezroq yengillashish mumkin!"
            else:
                msg = (
                    f"✅ *Данные сохранены!*\n\n"
                    f"📊 *Ваш путь:*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Доход: *{format_number(income_self)} сум*\n"
                    f"💳 Нагрузка: *{format_number(debt)} сум*\n"
                    f"📅 Платёж: *{format_number(loan_payment)} сум/мес*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🗓 *Примерная дата HALOS:* {exit_str}\n"
                    f"📆 *Осталось:* {months} мес\n\n"
                )
                
                if months_saved > 0:
                    msg += (
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💎 *PRO РЕШЕНИЕ:*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *Умное распределение:*\n"
                        f"├ 🏦 Для богатства: *{format_number(int(savings_monthly))} сум*\n"
                        f"├ ⚡ Платёж по кредиту: *{format_number(int(extra_payment))} сум*\n"
                        f"└ 🏠 Жизнь: *{format_number(int(free_cash * 0.7))} сум*\n\n"
                        f"📅 *Результат:*\n"
                        f"├ ⏱ На *{months_saved} мес* раньше — *{pro_exit_str}*\n"
                        f"└ 💰 *{format_number(int(savings_at_exit))} сум* богатства\n\n"
                        f"🎁 *Возможности PRO:*\n"
                        f"├ 📈 Еженедельная/месячная статистика\n"
                        f"├ 📊 Excel отчёты\n"
                        f"├ 🔔 Напоминания и советы\n"
                        f"└ 🏆 Личные цели\n\n"
                        f"🔒 _Получите PRO для полного доступа_"
                    )
                else:
                    msg += f"💎 С PRO можно освободиться быстрее!"
        else:
            msg = get_message("debt_no_data", lang) if lang == "uz" else get_message("debt_no_data", lang)
        
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )


async def menu_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 👤 Profil button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    await profile_command(update, context)


async def menu_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 💎 PRO button - show PRO features menu for PRO users, pricing for others"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    # Check if user has PRO
    is_pro = await is_user_pro(telegram_id)
    
    if is_pro:
        # Show PRO features menu
        from app.pro_features import show_pro_menu
        await show_pro_menu(update, context)
    else:
        # Show pricing
        await show_pricing_new_message(update, context)


async def menu_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 🌐 Til button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    keyboard = [
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="change_lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="change_lang_ru")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 Tilni tanlang / Выберите язык:",
        reply_markup=reply_markup
    )


# ==================== TEXT EXPENSE INPUT HANDLER ====================

async def menu_expense_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ✍️ Xarajat button - enable text expense input mode"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Enable text expense mode
    context.user_data["expense_text_mode"] = True
    
    if lang == "uz":
        msg = (
            "✍️ *MATN ORQALI XARAJAT KIRITISH*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 *AI yordamchi matndan avtomatik aniqlaydi:*\n"
            "• 💰 Summalarni\n"
            "• 📁 Kategoriyalarni\n"
            "• 📝 Tavsiflarni\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📝 *Misol xabarlar:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "• `50 ming ovqatga`\n"
            "• `100000 taksiga`\n"
            "• `bugun 30 mingga non oldim, 50 mingga benzin quydum`\n"
            "• `2 mln kredit to'ladim`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *Qoidalar:*\n"
            "• Bir xabarda bir nechta xarajat yozishingiz mumkin\n"
            "• AI avtomatik ajratib oladi\n"
            "• Limit yo'q - xohlagancha yozing!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎙 *Ovozli xabar* ham yuborishingiz mumkin (PRO)\n\n"
            "👇 *Xarajatlaringizni yozing:*"
        )
    else:
        msg = (
            "✍️ *ВВОД РАСХОДОВ ТЕКСТОМ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 *AI помощник автоматически определит:*\n"
            "• 💰 Суммы\n"
            "• 📁 Категории\n"
            "• 📝 Описания\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📝 *Примеры сообщений:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "• `50 тысяч на еду`\n"
            "• `100000 на такси`\n"
            "• `сегодня 30 тысяч на хлеб, 50 тысяч на бензин`\n"
            "• `2 млн оплата кредита`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *Правила:*\n"
            "• Можно писать несколько расходов в одном сообщении\n"
            "• AI автоматически разделит\n"
            "• Лимита нет - пишите сколько хотите!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎙 *Голосовое сообщение* тоже работает (PRO)\n\n"
            "👇 *Напишите ваши расходы:*"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
            callback_data="cancel_expense_mode"
        )]
    ]
    
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_expense_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel text expense input mode"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Disable expense mode and clear pending transactions
    context.user_data["expense_text_mode"] = False
    context.user_data.pop("pending_transactions", None)
    
    await query.edit_message_text(
        "✅ Bekor qilindi" if lang == "uz" else "✅ Отменено",
        parse_mode="Markdown"
    )


async def text_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    UNIVERSAL TEXT HANDLER - Har qanday matnni AI tahlil qiladi
    
    Tugmasiz ishlaydi - foydalanuvchi istalgan matn yozsa:
    1. AI tahlil qiladi (summa, kategoriya, daromad/xarajat)
    2. Natijani ko'rsatadi
    3. Tasdiqlash yoki o'zgartirish imkoniyatini beradi
    """
    
    telegram_id = update.effective_user.id
    text = update.message.text
    
    # Skip if it's a menu button
    for button_texts in MENU_BUTTONS.values():
        if text in button_texts:
            return
    
    # Skip commands
    if text.startswith('/'):
        return
    
    # Skip very short texts (less than 3 chars)
    if len(text.strip()) < 3:
        return
    
    lang = context.user_data.get("lang") or await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user or not user.get("phone_number"):
        return
    
    # Import AI functions
    from app.ai_assistant import (
        parse_multiple_transactions,
        EXPENSE_CATEGORIES, INCOME_CATEGORIES,
        extract_amount
    )
    
    # Quick check - does text contain any amount-like content?
    amount = extract_amount(text)
    if not amount:
        # No amount found - not a transaction, ignore silently
        return
    
    logger.info(f"[SMART_INPUT] User {telegram_id} sent potential transaction: '{text}'")
    
    # Show processing message
    if lang == "uz":
        processing_text = "🤖 *AI tahlil qilmoqda...*"
    else:
        processing_text = "🤖 *AI анализирует...*"
    
    processing_msg = await update.message.reply_text(
        processing_text,
        parse_mode="Markdown"
    )
    
    try:
        # Parse transactions from text
        transactions = await parse_multiple_transactions(text, lang)
        
        if not transactions:
            # Could not parse - delete processing message silently
            try:
                await processing_msg.delete()
            except:
                pass
            return
        
        # Store pending transactions for confirmation
        context.user_data["pending_transactions"] = transactions
        context.user_data["pending_original_text"] = text
        context.user_data["original_message_id"] = update.message.message_id
        
        # Format preview message
        if lang == "uz":
            msg = "🤖 *AI TAHLIL NATIJASI*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            total_expense = 0
            total_income = 0
            
            for i, tx in enumerate(transactions, 1):
                if tx["type"] == "income":
                    emoji = "📥"
                    type_name = "Daromad"
                    total_income += tx["amount"]
                else:
                    emoji = "📤"
                    type_name = "Xarajat"
                    total_expense += tx["amount"]
                
                msg += f"{emoji} *#{i} {type_name}*\n"
                msg += f"├ Summa: *{format_number(tx['amount'])} so'm*\n"
                msg += f"├ Kategoriya: {tx['category_name']}\n"
                if tx.get('description'):
                    msg += f"└ Tavsif: _{tx['description'][:30]}_\n"
                msg += "\n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            if total_income > 0:
                msg += f"📥 Jami daromad: *{format_number(total_income)} so'm*\n"
            if total_expense > 0:
                msg += f"📤 Jami xarajat: *{format_number(total_expense)} so'm*\n"
            msg += "\n"
            msg += "👇 *To'g'rimi?*"
        else:
            msg = "🤖 *РЕЗУЛЬТАТ AI АНАЛИЗА*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            total_expense = 0
            total_income = 0
            
            for i, tx in enumerate(transactions, 1):
                if tx["type"] == "income":
                    emoji = "📥"
                    type_name = "Доход"
                    total_income += tx["amount"]
                else:
                    emoji = "📤"
                    type_name = "Расход"
                    total_expense += tx["amount"]
                
                msg += f"{emoji} *#{i} {type_name}*\n"
                msg += f"├ Сумма: *{format_number(tx['amount'])} сум*\n"
                msg += f"├ Категория: {tx['category_name']}\n"
                if tx.get('description'):
                    msg += f"└ Описание: _{tx['description'][:30]}_\n"
                msg += "\n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            if total_income > 0:
                msg += f"📥 Всего доход: *{format_number(total_income)} сум*\n"
            if total_expense > 0:
                msg += f"📤 Всего расход: *{format_number(total_expense)} сум*\n"
            msg += "\n"
            msg += "👇 *Верно?*"
        
        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Ha, saqlash" if lang == "uz" else "✅ Да, сохранить",
                    callback_data="confirm_transaction_save"
                ),
                InlineKeyboardButton(
                    "✏️ O'zgartirish" if lang == "uz" else "✏️ Изменить",
                    callback_data="edit_pending_transaction"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Turni almashtirish" if lang == "uz" else "🔄 Поменять тип",
                    callback_data="swap_pending_type"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
                    callback_data="cancel_pending_transaction"
                )
            ]
        ]
        
        await processing_msg.edit_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"[SMART_INPUT] Error: {e}")
        try:
            await processing_msg.delete()
        except:
            pass


async def confirm_transaction_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm and save pending transactions"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    transactions = context.user_data.get("pending_transactions")
    if not transactions:
        await query.edit_message_text(
            "❌ Ma'lumot topilmadi" if lang == "uz" else "❌ Данные не найдены"
        )
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Save transactions
    from app.ai_assistant import save_multiple_transactions, get_budget_status
    
    tx_ids = await save_multiple_transactions(db, user["id"], transactions)
    
    # Try to delete the original user message (the one they typed/voice)
    original_message_id = context.user_data.get("original_message_id")
    if original_message_id:
        try:
            await context.bot.delete_message(
                chat_id=telegram_id,
                message_id=original_message_id
            )
        except Exception:
            pass  # Message may already be deleted or too old
        context.user_data.pop("original_message_id", None)
    
    # Clear pending
    context.user_data.pop("pending_transactions", None)
    context.user_data.pop("pending_original_text", None)
    
    # Get budget status
    budget_status = await get_budget_status(db, user["id"])
    
    today_income = budget_status.get('today_income', 0)
    today_expense = budget_status.get('today_expense', 0)
    today_balance = today_income - today_expense
    
    # Build beautiful success message
    if lang == "uz":
        msg = "✅ *SAQLANDI!*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for tx in transactions:
            emoji = "💰" if tx["type"] == "income" else "💸"
            msg += f"{emoji} {tx['category_name']}: *{format_number(tx['amount'])}* so'm\n"
        
        msg += "\n"
        msg += "┌─────────────────────┐\n"
        msg += "│    📊 *BUGUNGI HISOBOT*    │\n"
        msg += "└─────────────────────┘\n\n"
        
        msg += f"💰 Daromad: *{format_number(today_income)}* so'm\n"
        msg += f"💸 Xarajat: *{format_number(today_expense)}* so'm\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if today_balance >= 0:
            msg += f"📈 Balans: *+{format_number(today_balance)}* so'm ✅"
        else:
            msg += f"📉 Balans: *{format_number(today_balance)}* so'm ⚠️"
        
    else:
        msg = "✅ *СОХРАНЕНО!*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for tx in transactions:
            emoji = "💰" if tx["type"] == "income" else "💸"
            msg += f"{emoji} {tx['category_name']}: *{format_number(tx['amount'])}* сум\n"
        
        msg += "\n"
        msg += "┌─────────────────────┐\n"
        msg += "│    📊 *ОТЧЁТ ЗА ДЕНЬ*    │\n"
        msg += "└─────────────────────┘\n\n"
        
        msg += f"💰 Доход: *{format_number(today_income)}* сум\n"
        msg += f"💸 Расход: *{format_number(today_expense)}* сум\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if today_balance >= 0:
            msg += f"📈 Баланс: *+{format_number(today_balance)}* сум ✅"
        else:
            msg += f"📉 Баланс: *{format_number(today_balance)}* сум ⚠️"
    
    # Add quick action buttons
    keyboard = [[
        InlineKeyboardButton(
            "📊 Batafsil" if lang == "uz" else "📊 Подробнее",
            callback_data="show_reports"
        ),
        InlineKeyboardButton(
            "➕ Yana kiritish" if lang == "uz" else "➕ Ещё запись",
            callback_data="add_transaction_menu"
        )
    ]]
    
    await query.edit_message_text(
        msg, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_pending_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel pending transaction"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Clear pending
    context.user_data.pop("pending_transactions", None)
    context.user_data.pop("pending_original_text", None)
    
    await query.edit_message_text(
        "❌ Bekor qilindi" if lang == "uz" else "❌ Отменено"
    )


async def swap_pending_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Swap transaction type (income <-> expense)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    transactions = context.user_data.get("pending_transactions")
    if not transactions:
        return
    
    from app.ai_assistant import EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    # Swap types for all transactions
    for tx in transactions:
        if tx["type"] == "income":
            tx["type"] = "expense"
            # Change category
            if tx["category"] in INCOME_CATEGORIES.get("uz", {}):
                tx["category"] = "boshqa"
            tx["category_name"] = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(tx["category"], "📦 Boshqa")
        else:
            tx["type"] = "income"
            # Change category
            if tx["category"] in EXPENSE_CATEGORIES.get("uz", {}):
                tx["category"] = "boshqa"
            tx["category_name"] = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(tx["category"], "📦 Boshqa")
    
    context.user_data["pending_transactions"] = transactions
    
    # Rebuild preview message
    if lang == "uz":
        msg = "🔄 *TUR ALMASHTIRILDI*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_expense = 0
        total_income = 0
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                emoji = "📥"
                type_name = "Daromad"
                total_income += tx["amount"]
            else:
                emoji = "📤"
                type_name = "Xarajat"
                total_expense += tx["amount"]
            
            msg += f"{emoji} *#{i} {type_name}*\n"
            msg += f"├ Summa: *{format_number(tx['amount'])} so'm*\n"
            msg += f"└ Kategoriya: {tx['category_name']}\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "👇 *To'g'rimi?*"
    else:
        msg = "🔄 *ТИП ИЗМЕНЁН*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_expense = 0
        total_income = 0
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                emoji = "📥"
                type_name = "Доход"
                total_income += tx["amount"]
            else:
                emoji = "📤"
                type_name = "Расход"
                total_expense += tx["amount"]
            
            msg += f"{emoji} *#{i} {type_name}*\n"
            msg += f"├ Сумма: *{format_number(tx['amount'])} сум*\n"
            msg += f"└ Категория: {tx['category_name']}\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "👇 *Верно?*"
    
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ha, saqlash" if lang == "uz" else "✅ Да, сохранить",
                callback_data="confirm_transaction_save"
            ),
            InlineKeyboardButton(
                "✏️ O'zgartirish" if lang == "uz" else "✏️ Изменить",
                callback_data="edit_pending_transaction"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Turni almashtirish" if lang == "uz" else "🔄 Поменять тип",
                callback_data="swap_pending_type"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
                callback_data="cancel_pending_transaction"
            )
        ]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_pending_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show options to edit pending transaction"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    transactions = context.user_data.get("pending_transactions")
    if not transactions:
        return
    
    # Show edit options
    if lang == "uz":
        msg = "✏️ *TAHRIRLASH*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "Qaysi tranzaksiyani tahrirlash kerak?\n\n"
    else:
        msg = "✏️ *РЕДАКТИРОВАНИЕ*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "Какую транзакцию редактировать?\n\n"
    
    keyboard = []
    
    for i, tx in enumerate(transactions):
        emoji = "📥" if tx["type"] == "income" else "📤"
        btn_text = f"{emoji} #{i+1}: {format_number(tx['amount'])} - {tx['category_name']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"edit_tx_{i}")])
    
    keyboard.append([
        InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_pending_preview"
        )
    ])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_single_tx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit a single transaction - show category options"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Get transaction index
    tx_index = int(query.data.replace("edit_tx_", ""))
    context.user_data["editing_tx_index"] = tx_index
    
    transactions = context.user_data.get("pending_transactions")
    if not transactions or tx_index >= len(transactions):
        return
    
    tx = transactions[tx_index]
    
    from app.ai_assistant import EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    # Show category selection
    if lang == "uz":
        msg = f"✏️ *KATEGORIYA TANLANG*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"💰 Summa: *{format_number(tx['amount'])} so'm*\n\n"
    else:
        msg = f"✏️ *ВЫБЕРИТЕ КАТЕГОРИЮ*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"💰 Сумма: *{format_number(tx['amount'])} сум*\n\n"
    
    keyboard = []
    
    # Show expense categories first, then income
    if lang == "uz":
        msg += "📤 *Xarajat kategoriyalari:*\n"
    else:
        msg += "📤 *Категории расходов:*\n"
    
    expense_cats = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"])
    row = []
    for cat_key, cat_name in expense_cats.items():
        btn = InlineKeyboardButton(cat_name, callback_data=f"set_cat_expense_{cat_key}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Separator
    keyboard.append([InlineKeyboardButton("━━━━━━━━━━━━", callback_data="noop")])
    
    if lang == "uz":
        msg += "\n📥 *Daromad kategoriyalari:*\n"
    else:
        msg += "\n📥 *Категории доходов:*\n"
    
    income_cats = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"])
    row = []
    for cat_key, cat_name in income_cats.items():
        btn = InlineKeyboardButton(cat_name, callback_data=f"set_cat_income_{cat_key}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="edit_pending_transaction"
        )
    ])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set category for a transaction"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Parse callback data: set_cat_expense_oziq_ovqat or set_cat_income_ish_haqi
    data = query.data.replace("set_cat_", "")
    parts = data.split("_", 1)
    tx_type = parts[0]  # expense or income
    category = parts[1] if len(parts) > 1 else "boshqa"
    
    tx_index = context.user_data.get("editing_tx_index", 0)
    transactions = context.user_data.get("pending_transactions")
    
    if not transactions or tx_index >= len(transactions):
        return
    
    from app.ai_assistant import EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    # Update transaction
    transactions[tx_index]["type"] = tx_type
    transactions[tx_index]["category"] = category
    
    if tx_type == "income":
        transactions[tx_index]["category_name"] = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(category, "📦 Boshqa")
    else:
        transactions[tx_index]["category_name"] = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(category, "📦 Boshqa")
    
    context.user_data["pending_transactions"] = transactions
    
    # Go back to preview
    await back_to_pending_preview_callback(update, context)


async def back_to_pending_preview_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to pending transactions preview"""
    query = update.callback_query
    if query.data != "noop":
        await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    transactions = context.user_data.get("pending_transactions")
    if not transactions:
        return
    
    # Rebuild preview message
    if lang == "uz":
        msg = "🤖 *AI TAHLIL NATIJASI*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_expense = 0
        total_income = 0
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                emoji = "📥"
                type_name = "Daromad"
                total_income += tx["amount"]
            else:
                emoji = "📤"
                type_name = "Xarajat"
                total_expense += tx["amount"]
            
            msg += f"{emoji} *#{i} {type_name}*\n"
            msg += f"├ Summa: *{format_number(tx['amount'])} so'm*\n"
            msg += f"├ Kategoriya: {tx['category_name']}\n"
            if tx.get('description'):
                msg += f"└ Tavsif: _{tx['description'][:30]}_\n"
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        if total_income > 0:
            msg += f"📥 Jami daromad: *{format_number(total_income)} so'm*\n"
        if total_expense > 0:
            msg += f"📤 Jami xarajat: *{format_number(total_expense)} so'm*\n"
        msg += "\n👇 *To'g'rimi?*"
    else:
        msg = "🤖 *РЕЗУЛЬТАТ AI АНАЛИЗА*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_expense = 0
        total_income = 0
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                emoji = "📥"
                type_name = "Доход"
                total_income += tx["amount"]
            else:
                emoji = "📤"
                type_name = "Расход"
                total_expense += tx["amount"]
            
            msg += f"{emoji} *#{i} {type_name}*\n"
            msg += f"├ Сумма: *{format_number(tx['amount'])} сум*\n"
            msg += f"├ Категория: {tx['category_name']}\n"
            if tx.get('description'):
                msg += f"└ Описание: _{tx['description'][:30]}_\n"
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        if total_income > 0:
            msg += f"📥 Всего доход: *{format_number(total_income)} сум*\n"
        if total_expense > 0:
            msg += f"📤 Всего расход: *{format_number(total_expense)} сум*\n"
        msg += "\n👇 *Верно?*"
    
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ha, saqlash" if lang == "uz" else "✅ Да, сохранить",
                callback_data="confirm_transaction_save"
            ),
            InlineKeyboardButton(
                "✏️ O'zgartirish" if lang == "uz" else "✏️ Изменить",
                callback_data="edit_pending_transaction"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Turni almashtirish" if lang == "uz" else "🔄 Поменять тип",
                callback_data="swap_pending_type"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Bekor qilish" if lang == "uz" else "❌ Отмена",
                callback_data="cancel_pending_transaction"
            )
        ]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def add_more_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Continue adding expenses"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Keep expense mode enabled
    context.user_data["expense_text_mode"] = True
    
    await query.edit_message_text(
        "👇 *Keyingi xarajatni yozing:*" if lang == "uz" else "👇 *Напишите следующий расход:*",
        parse_mode="Markdown"
    )


async def show_halos_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    🌟 HALOS USULI STATUS - PRO foydalanuvchilar uchun
    
    Bu callback HALOS usuliga qanchalik amal qilinayotganini ko'rsatadi:
    - 70% yashash
    - 20% qarz to'lash  
    - 10% jamg'arma
    
    Shuningdek qarzdan chiqish sanasini va tejalgan oylarni ko'rsatadi.
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # PRO tekshirish
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        if lang == "uz":
            msg = "🔒 *HALOS USULI* PRO obunachilarga ochiq.\n\n💎 PRO ga o'ting va HALOS usuli bilan qarzdan tezroq chiqing!"
        else:
            msg = "🔒 *МЕТОД HALOS* доступен PRO подписчикам.\n\n💎 Перейдите на PRO и выходите из долга быстрее с методом HALOS!"
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # HALOS holatini olish
    from app.ai_assistant import get_halos_method_status, format_halos_status_message
    
    halos_status = await get_halos_method_status(db, user["id"], lang)
    msg = format_halos_status_message(halos_status, lang)
    
    # Tugmalar
    keyboard = [
        [InlineKeyboardButton(
            "📊 Hisobotga qaytish" if lang == "uz" else "📊 Вернуться к отчёту",
            callback_data="menu_plan"
        )],
        [InlineKeyboardButton(
            "👤 Profilni tahrirlash" if lang == "uz" else "👤 Редактировать профиль",
            callback_data="show_profile"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def detailed_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed financial report with full breakdown"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    profile = await db.get_financial_profile(user["id"])
    is_pro = await is_user_pro(telegram_id)
    
    from app.ai_assistant import get_transaction_summary, get_debt_summary, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    from datetime import datetime
    import math
    from dateutil.relativedelta import relativedelta
    from app.engine import format_exit_date
    
    # Ma'lumotlarni yig'ish
    month_summary = await get_transaction_summary(db, user["id"], days=30)
    debt_summary = await get_debt_summary(db, user["id"])
    
    # Profil ma'lumotlari
    income_self = profile.get("income_self", 0) or 0 if profile else 0
    income_partner = profile.get("income_partner", 0) or 0 if profile else 0
    total_income = income_self + income_partner
    
    rent = profile.get("rent", 0) or 0 if profile else 0
    kindergarten = profile.get("kindergarten", 0) or 0 if profile else 0
    utilities = profile.get("utilities", 0) or 0 if profile else 0
    loan_payment = profile.get("loan_payment", 0) or 0 if profile else 0
    total_debt = profile.get("total_debt", 0) or 0 if profile else 0
    
    mandatory_total = rent + kindergarten + utilities + loan_payment
    free_cash = total_income - mandatory_total
    
    # Qarzdan chiqish hisoblash
    if loan_payment > 0 and total_debt > 0:
        simple_exit_months = math.ceil(total_debt / loan_payment)
        simple_exit_date = datetime.now() + relativedelta(months=simple_exit_months)
        simple_exit_formatted = format_exit_date(simple_exit_date.strftime("%Y-%m"), lang)
    else:
        simple_exit_months = 0
        simple_exit_formatted = "-"
    
    # PRO usul
    if free_cash > 0 and total_debt > 0:
        extra_debt = free_cash * 0.2
        savings_monthly = free_cash * 0.1
        living_budget = free_cash * 0.7
        total_payment = loan_payment + extra_debt
        pro_exit_months = math.ceil(total_debt / total_payment) if total_payment > 0 else 0
        pro_exit_date = datetime.now() + relativedelta(months=pro_exit_months)
        pro_exit_formatted = format_exit_date(pro_exit_date.strftime("%Y-%m"), lang)
        savings_at_exit = savings_monthly * pro_exit_months
        months_saved = simple_exit_months - pro_exit_months
    else:
        extra_debt = 0
        savings_monthly = 0
        living_budget = 0
        pro_exit_months = simple_exit_months
        pro_exit_formatted = simple_exit_formatted
        savings_at_exit = 0
        months_saved = 0
    
    month_income = month_summary.get("total_income", 0)
    month_expense = month_summary.get("total_expense", 0)
    
    if lang == "uz":
        msg = (
            "📈 *BATAFSIL HISOBOT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "💰 *DAROMADLAR:*\n"
            f"├ 👤 Shaxsiy: *{income_self:,}* so'm\n"
        )
        if income_partner > 0:
            msg += f"├ 👫 Sherik: *{income_partner:,}* so'm\n"
        msg += f"└ 📊 Jami oylik: *{total_income:,}* so'm\n\n"
        
        msg += (
            "📌 *MAJBURIY TO'LOVLAR:*\n"
            f"├ 🏠 Ijara/ipoteka: *{rent:,}* so'm\n"
            f"├ 👶 Bog'cha/maktab: *{kindergarten:,}* so'm\n"
            f"├ 💡 Kommunal: *{utilities:,}* so'm\n"
            f"├ 💳 Kredit to'lovi: *{loan_payment:,}* so'm\n"
            f"└ 📊 Jami majburiy: *{mandatory_total:,}* so'm\n\n"
            
            f"💵 *BO'SH PUL:* *{free_cash:,}* so'm\n\n"
        )
        
        if total_debt > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💳 *QARZ HOLATI:*\n"
                f"├ Umumiy qarz: *{total_debt:,}* so'm\n"
                f"├ Oylik to'lov: *{loan_payment:,}* so'm\n\n"
                
                "🌿 *Oddiy usul:*\n"
                f"├ Muddat: {simple_exit_months} oy\n"
                f"└ Sana: {simple_exit_formatted}\n\n"
            )
            
            if is_pro:
                msg += (
                    "🌟 *HALOS PRO usuli:*\n"
                    f"├ Muddat: *{pro_exit_months}* oy\n"
                    f"├ Sana: *{pro_exit_formatted}*\n"
                    f"├ ⏱ {months_saved} oy tezroq!\n"
                    f"├ 💎 Jamg'arma: {savings_at_exit:,.0f} so'm\n"
                    f"└ Oylik qo'shimcha: {extra_debt:,.0f} so'm\n\n"
                )
        
        # Oylik AI tranzaksiyalar
        if month_income > 0 or month_expense > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 *AI YORDAMCHI (30 kun):*\n"
                f"├ 📥 Kirim: +{month_income:,} so'm\n"
                f"├ 📤 Chiqim: -{month_expense:,} so'm\n"
                f"└ 💰 Balans: {month_income - month_expense:,} so'm\n\n"
            )
            
            # Xarajatlar bo'yicha
            if month_summary.get("expense_by_category"):
                msg += "💸 *Xarajatlar kategoriya bo'yicha:*\n"
                sorted_expenses = sorted(month_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
                for cat, amount in sorted_expenses:
                    cat_name = EXPENSE_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                    percentage = (amount / month_expense * 100) if month_expense > 0 else 0
                    msg += f"├ {cat_name}: {amount:,} ({percentage:.0f}%)\n"
                msg += "\n"
            
            # Daromadlar bo'yicha
            if month_summary.get("income_by_category"):
                msg += "💰 *Daromadlar kategoriya bo'yicha:*\n"
                for cat, amount in month_summary["income_by_category"].items():
                    cat_name = INCOME_CATEGORIES["uz"].get(cat, "💵 Boshqa")
                    msg += f"├ {cat_name}: +{amount:,} so'm\n"
                msg += "\n"
        
        # Shaxsiy qarzlar
        if debt_summary["total_lent"] > 0 or debt_summary["total_borrowed"] > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤝 *SHAXSIY QARZLAR:*\n"
                f"├ 📤 Bergan: {debt_summary['total_lent']:,} so'm ({debt_summary['lent_count']} ta)\n"
                f"├ 📥 Olgan: {debt_summary['total_borrowed']:,} so'm ({debt_summary['borrowed_count']} ta)\n"
            )
            net = debt_summary['net_balance']
            if net > 0:
                msg += f"└ 💚 Sof: +{net:,} so'm\n"
            elif net < 0:
                msg += f"└ 🔴 Sof: {net:,} so'm\n"
            else:
                msg += "└ ⚪ Sof: 0 so'm\n"
    
    else:
        # Russian version
        msg = (
            "📈 *ПОДРОБНЫЙ ОТЧЁТ*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "💰 *ДОХОДЫ:*\n"
            f"├ 👤 Личный: *{income_self:,}* сум\n"
        )
        if income_partner > 0:
            msg += f"├ 👫 Партнёр: *{income_partner:,}* сум\n"
        msg += f"└ 📊 Всего в месяц: *{total_income:,}* сум\n\n"
        
        msg += (
            "📌 *ОБЯЗАТЕЛЬНЫЕ:*\n"
            f"├ 🏠 Аренда/ипотека: *{rent:,}* сум\n"
            f"├ 👶 Детсад/школа: *{kindergarten:,}* сум\n"
            f"├ 💡 Коммунальные: *{utilities:,}* сум\n"
            f"├ 💳 Платёж по кредиту: *{loan_payment:,}* сум\n"
            f"└ 📊 Всего обязательных: *{mandatory_total:,}* сум\n\n"
            
            f"💵 *СВОБОДНЫЕ:* *{free_cash:,}* сум\n\n"
        )
        
        if total_debt > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💳 *СОСТОЯНИЕ ДОЛГА:*\n"
                f"├ Общий долг: *{total_debt:,}* сум\n"
                f"├ Ежемесячный платёж: *{loan_payment:,}* сум\n\n"
                
                "🌿 *Обычный способ:*\n"
                f"├ Срок: {simple_exit_months} мес\n"
                f"└ Дата: {simple_exit_formatted}\n\n"
            )
            
            if is_pro:
                msg += (
                    "🌟 *Способ HALOS PRO:*\n"
                    f"├ Срок: *{pro_exit_months}* мес\n"
                    f"├ Дата: *{pro_exit_formatted}*\n"
                    f"├ ⏱ На {months_saved} мес быстрее!\n"
                    f"├ 💎 Накопления: {savings_at_exit:,.0f} сум\n"
                    f"└ Доп. платёж: {extra_debt:,.0f} сум\n\n"
                )
        
        if month_income > 0 or month_expense > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 *AI ПОМОЩНИК (30 дней):*\n"
                f"├ 📥 Приход: +{month_income:,} сум\n"
                f"├ 📤 Расход: -{month_expense:,} сум\n"
                f"└ 💰 Баланс: {month_income - month_expense:,} сум\n\n"
            )
            
            if month_summary.get("expense_by_category"):
                msg += "💸 *Расходы по категориям:*\n"
                sorted_expenses = sorted(month_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
                for cat, amount in sorted_expenses:
                    cat_name = EXPENSE_CATEGORIES["ru"].get(cat, "📦 Прочее")
                    percentage = (amount / month_expense * 100) if month_expense > 0 else 0
                    msg += f"├ {cat_name}: {amount:,} ({percentage:.0f}%)\n"
                msg += "\n"
        
        if debt_summary["total_lent"] > 0 or debt_summary["total_borrowed"] > 0:
            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤝 *ЛИЧНЫЕ ДОЛГИ:*\n"
                f"├ 📤 Дал: {debt_summary['total_lent']:,} сум ({debt_summary['lent_count']})\n"
                f"├ 📥 Взял: {debt_summary['total_borrowed']:,} сум ({debt_summary['borrowed_count']})\n"
            )
            net = debt_summary['net_balance']
            if net > 0:
                msg += f"└ 💚 Чистый: +{net:,} сум\n"
            elif net < 0:
                msg += f"└ 🔴 Чистый: {net:,} сум\n"
            else:
                msg += "└ ⚪ Чистый: 0 сум\n"
    
    keyboard = [
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_report"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def report_weekly_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show weekly report"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import get_transaction_summary, EXPENSE_CATEGORIES
    from datetime import datetime, timedelta
    
    week_summary = await get_transaction_summary(db, user["id"], days=7)
    
    week_income = week_summary.get("total_income", 0)
    week_expense = week_summary.get("total_expense", 0)
    week_balance = week_income - week_expense
    
    # Kunlik o'rtacha
    avg_expense = week_expense / 7 if week_expense > 0 else 0
    avg_income = week_income / 7 if week_income > 0 else 0
    
    start_date = (datetime.now() - timedelta(days=7)).strftime("%d.%m")
    end_date = datetime.now().strftime("%d.%m")
    
    if lang == "uz":
        msg = (
            f"📅 *HAFTALIK HISOBOT*\n"
            f"📆 {start_date} - {end_date}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"💰 *UMUMIY:*\n"
            f"├ 📥 Kirim: +{week_income:,} so'm\n"
            f"├ 📤 Chiqim: -{week_expense:,} so'm\n"
        )
        if week_balance >= 0:
            msg += f"└ 💚 Balans: +{week_balance:,} so'm\n\n"
        else:
            msg += f"└ 🔴 Balans: {week_balance:,} so'm\n\n"
        
        msg += (
            f"📊 *KUNLIK O'RTACHA:*\n"
            f"├ Kirim: ~{avg_income:,.0f} so'm\n"
            f"└ Chiqim: ~{avg_expense:,.0f} so'm\n\n"
        )
        
        if week_summary.get("expense_by_category"):
            msg += "💸 *XARAJATLAR:*\n"
            sorted_expenses = sorted(week_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses[:7]:
                cat_name = EXPENSE_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                percentage = (amount / week_expense * 100) if week_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"{cat_name}\n{bar} {amount:,} ({percentage:.0f}%)\n"
    else:
        msg = (
            f"📅 *НЕДЕЛЬНЫЙ ОТЧЁТ*\n"
            f"📆 {start_date} - {end_date}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"💰 *ИТОГО:*\n"
            f"├ 📥 Приход: +{week_income:,} сум\n"
            f"├ 📤 Расход: -{week_expense:,} сум\n"
        )
        if week_balance >= 0:
            msg += f"└ 💚 Баланс: +{week_balance:,} сум\n\n"
        else:
            msg += f"└ 🔴 Баланс: {week_balance:,} сум\n\n"
        
        msg += (
            f"📊 *СРЕДНЕЕ В ДЕНЬ:*\n"
            f"├ Приход: ~{avg_income:,.0f} сум\n"
            f"└ Расход: ~{avg_expense:,.0f} сум\n\n"
        )
        
        if week_summary.get("expense_by_category"):
            msg += "💸 *РАСХОДЫ:*\n"
            sorted_expenses = sorted(week_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses[:7]:
                cat_name = EXPENSE_CATEGORIES["ru"].get(cat, "📦 Прочее")
                percentage = (amount / week_expense * 100) if week_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"{cat_name}\n{bar} {amount:,} ({percentage:.0f}%)\n"
    
    keyboard = [
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_report"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def report_monthly_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly report"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import get_transaction_summary, EXPENSE_CATEGORIES
    from datetime import datetime
    
    month_summary = await get_transaction_summary(db, user["id"], days=30)
    
    month_income = month_summary.get("total_income", 0)
    month_expense = month_summary.get("total_expense", 0)
    month_balance = month_income - month_expense
    
    # Kunlik o'rtacha
    avg_expense = month_expense / 30 if month_expense > 0 else 0
    avg_income = month_income / 30 if month_income > 0 else 0
    
    current_month = datetime.now().strftime("%B %Y")
    
    if lang == "uz":
        msg = (
            f"📆 *OYLIK HISOBOT*\n"
            f"📅 {current_month}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"💰 *UMUMIY:*\n"
            f"├ 📥 Kirim: +{month_income:,} so'm\n"
            f"├ 📤 Chiqim: -{month_expense:,} so'm\n"
        )
        if month_balance >= 0:
            msg += f"└ 💚 Balans: +{month_balance:,} so'm\n\n"
        else:
            msg += f"└ 🔴 Balans: {month_balance:,} so'm\n\n"
        
        msg += (
            f"📊 *KUNLIK O'RTACHA:*\n"
            f"├ Kirim: ~{avg_income:,.0f} so'm\n"
            f"└ Chiqim: ~{avg_expense:,.0f} so'm\n\n"
        )
        
        if month_summary.get("expense_by_category"):
            msg += "💸 *XARAJATLAR TAQSIMOTI:*\n"
            sorted_expenses = sorted(month_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses:
                cat_name = EXPENSE_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                percentage = (amount / month_expense * 100) if month_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"{cat_name}\n{bar} {amount:,} ({percentage:.0f}%)\n"
    else:
        msg = (
            f"📆 *МЕСЯЧНЫЙ ОТЧЁТ*\n"
            f"📅 {current_month}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"💰 *ИТОГО:*\n"
            f"├ 📥 Приход: +{month_income:,} сум\n"
            f"├ 📤 Расход: -{month_expense:,} сум\n"
        )
        if month_balance >= 0:
            msg += f"└ 💚 Баланс: +{month_balance:,} сум\n\n"
        else:
            msg += f"└ 🔴 Баланс: {month_balance:,} сум\n\n"
        
        msg += (
            f"📊 *СРЕДНЕЕ В ДЕНЬ:*\n"
            f"├ Приход: ~{avg_income:,.0f} сум\n"
            f"└ Расход: ~{avg_expense:,.0f} сум\n\n"
        )
        
        if month_summary.get("expense_by_category"):
            msg += "💸 *РАСПРЕДЕЛЕНИЕ РАСХОДОВ:*\n"
            sorted_expenses = sorted(month_summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_expenses:
                cat_name = EXPENSE_CATEGORIES["ru"].get(cat, "📦 Прочее")
                percentage = (amount / month_expense * 100) if month_expense > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                msg += f"{cat_name}\n{bar} {amount:,} ({percentage:.0f}%)\n"
    
    keyboard = [
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_report"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def back_to_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to main report view"""
    query = update.callback_query
    await query.answer()
    
    # Yangi xabar yuborish o'rniga 📊 Hisobotlarim funksiyasini chaqirish
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Foydalanuvchi ma'lumotlarini o'rnatish
    class FakeMessage:
        def __init__(self, user_id, chat_id, reply_func):
            self.from_user = type('User', (), {'id': user_id})()
            self.chat = type('Chat', (), {'id': chat_id})()
            self.reply_text = reply_func
    
    async def edit_as_reply(text, **kwargs):
        await query.edit_message_text(text, **kwargs)
    
    # menu_plan_handler ni chaqirish o'rniga sodda qaytarish
    await query.edit_message_text(
        "📊 *Hisobotga qaytish uchun* \"📊 Hisobotlarim\" *tugmasini bosing*" if lang == "uz" else 
        "📊 *Для возврата к отчёту нажмите* \"📊 Мои отчёты\"",
        parse_mode="Markdown"
    )


async def show_expense_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's expense report"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    from app.ai_assistant import get_budget_status
    budget_status = await get_budget_status(db, user["id"])
    
    if lang == "uz":
        msg = (
            "📊 *BUGUNGI HISOBOT*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📥 Daromad: *{format_number(budget_status.get('today_income', 0))} so'm*\n"
            f"📤 Xarajat: *{format_number(budget_status.get('today_expense', 0))} so'm*\n"
            f"💰 Balans: *{format_number(budget_status.get('today_balance', 0))} so'm*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Oylik:*\n"
            f"├ Daromad: *{format_number(budget_status.get('monthly_income', 0))} so'm*\n"
            f"├ Xarajat: *{format_number(budget_status.get('monthly_expense', 0))} so'm*\n"
            f"└ Balans: *{format_number(budget_status.get('monthly_balance', 0))} so'm*"
        )
    else:
        msg = (
            "📊 *ОТЧЁТ ЗА СЕГОДНЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📥 Доход: *{format_number(budget_status.get('today_income', 0))} сум*\n"
            f"📤 Расход: *{format_number(budget_status.get('today_expense', 0))} сум*\n"
            f"💰 Баланс: *{format_number(budget_status.get('today_balance', 0))} сум*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *За месяц:*\n"
            f"├ Доход: *{format_number(budget_status.get('monthly_income', 0))} сум*\n"
            f"├ Расход: *{format_number(budget_status.get('monthly_expense', 0))} сум*\n"
            f"└ Баланс: *{format_number(budget_status.get('monthly_balance', 0))} сум*"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "➕ Yana qo'shish" if lang == "uz" else "➕ Добавить ещё",
            callback_data="add_more_expense"
        )],
        [InlineKeyboardButton(
            "✅ Tayyor" if lang == "uz" else "✅ Готово",
            callback_data="cancel_expense_mode"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ❓ Yordam button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Check if user is registered
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    await update.message.reply_text(
        get_message("help", lang),
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(lang)
    )


# ==================== DEBT PLAN HANDLERS ====================

async def debt_plan_free_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show FREE debt exit plan details"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    if not profile:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    import math
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    from app.engine import format_exit_date
    
    total_debt = profile.get("total_debt", 0)
    loan_payment = profile.get("loan_payment", 0)
    income_self = profile.get("income_self", 0)
    income_partner = profile.get("income_partner", 0)
    rent = profile.get("rent", 0)
    kindergarten = profile.get("kindergarten", 0)
    utilities = profile.get("utilities", 0)
    
    total_income = income_self + income_partner
    total_expenses = rent + kindergarten + utilities + loan_payment
    free_cash = total_income - total_expenses
    
    simple_exit_months = math.ceil(total_debt / loan_payment) if loan_payment > 0 else 0
    simple_exit_date = datetime.now() + relativedelta(months=simple_exit_months)
    simple_exit_formatted = format_exit_date(simple_exit_date.strftime("%Y-%m"), lang)
    
    if lang == "uz":
        msg = (
            "🆓 *BEPUL QARZDAN CHIQISH REJASI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📋 *USUL:* Faqat minimal to'lov\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *MOLIYAVIY HOLAT:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Daromad: *{format_number(total_income)} so'm*\n"
            f"├ Xarajatlar: *{format_number(total_expenses)} so'm*\n"
            f"└ Bo'sh pul: *{format_number(free_cash)} so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QARZ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Umumiy qarz: *{format_number(total_debt)} so'm*\n"
            f"└ Oylik to'lov: *{format_number(loan_payment)} so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *NATIJA:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Chiqish muddati: *{simple_exit_months} oy*\n"
            f"📆 Sana: *{simple_exit_formatted}*\n"
            f"💰 Yig'ilgan boylik: *0 so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Eslatma:* Bu usulda faqat qarz to'lanadi.\n"
            "Boylik yig'ilmaydi. PRO bilan tezroq chiqasiz\n"
            "va boylik ham ortirasiz!"
        )
    else:
        msg = (
            "🆓 *БЕСПЛАТНЫЙ ПЛАН ВЫХОДА ИЗ ДОЛГА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📋 *МЕТОД:* Только минимальный платёж\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ФИНАНСОВОЕ СОСТОЯНИЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Доход: *{format_number(total_income)} сум*\n"
            f"├ Расходы: *{format_number(total_expenses)} сум*\n"
            f"└ Свободные: *{format_number(free_cash)} сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ДОЛГ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Общий долг: *{format_number(total_debt)} сум*\n"
            f"└ Ежемесячно: *{format_number(loan_payment)} сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *РЕЗУЛЬТАТ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Срок выхода: *{simple_exit_months} мес*\n"
            f"📆 Дата: *{simple_exit_formatted}*\n"
            f"💰 Накопленное богатство: *0 сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Примечание:* Этот способ только погашает долг.\n"
            "Богатство не копится. С PRO выйдете быстрее\n"
            "и накопите богатство!"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "💎 PRO ga o'tish" if lang == "uz" else "💎 Перейти на PRO",
            callback_data="show_pricing"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def debt_plan_pro_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show PRO debt exit plan details (for PRO users)"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        await show_pricing(update, context)
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    if not profile:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    import math
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    from app.engine import format_exit_date
    
    total_debt = profile.get("total_debt", 0)
    loan_payment = profile.get("loan_payment", 0)
    income_self = profile.get("income_self", 0)
    income_partner = profile.get("income_partner", 0)
    rent = profile.get("rent", 0)
    kindergarten = profile.get("kindergarten", 0)
    utilities = profile.get("utilities", 0)
    
    total_income = income_self + income_partner
    mandatory = rent + kindergarten + utilities
    free_cash = total_income - mandatory - loan_payment
    
    # Calculate PRO plan
    if free_cash > 0:
        savings = free_cash * 0.1  # 10% boylik
        extra_debt = free_cash * 0.2  # 20% qo'shimcha qarz
        living = free_cash * 0.7  # 70% yashash
        total_payment = loan_payment + extra_debt
        pro_exit_months = math.ceil(total_debt / total_payment)
        savings_at_exit = savings * pro_exit_months
    else:
        savings = extra_debt = living = 0
        total_payment = loan_payment
        pro_exit_months = math.ceil(total_debt / loan_payment) if loan_payment > 0 else 0
        savings_at_exit = 0
    
    pro_exit_date = datetime.now() + relativedelta(months=pro_exit_months)
    pro_exit_formatted = format_exit_date(pro_exit_date.strftime("%Y-%m"), lang)
    
    # Simple comparison
    simple_exit_months = math.ceil(total_debt / loan_payment) if loan_payment > 0 else 0
    months_saved = simple_exit_months - pro_exit_months
    
    if lang == "uz":
        msg = (
            "💎 *PRO QARZDAN CHIQISH REJASI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📋 *USUL:* Aqlli taqsimlash\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *MOLIYAVIY HOLAT:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Daromad: *{format_number(total_income)} so'm*\n"
            f"├ Majburiy: *{format_number(mandatory)} so'm*\n"
            f"├ Qarz to'lovi: *{format_number(loan_payment)} so'm*\n"
            f"└ Bo'sh pul: *{format_number(free_cash)} so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *AQLLI TAQSIMLASH:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 🏦 Boylik uchun: *{format_number(int(savings))} so'm*\n"
            f"├ ⚡ Kredit to'lovi: *{format_number(int(extra_debt))} so'm*\n"
            f"└ 🏠 Yashash: *{format_number(int(living))} so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *NATIJA:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Chiqish muddati: *{pro_exit_months} oy*\n"
            f"📆 Sana: *{pro_exit_formatted}*\n"
            f"⏱ Tejash: *{months_saved} oy tezroq!*\n"
            f"💰 Yig'ilgan boylik: *{format_number(int(savings_at_exit))} so'm*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Oylik qarz to'lovi: *{format_number(int(total_payment))} so'm*\n"
            f"   (asosiy + qo'shimcha)"
        )
    else:
        msg = (
            "💎 *PRO ПЛАН ВЫХОДА ИЗ ДОЛГА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📋 *МЕТОД:* Умное распределение\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ФИНАНСОВОЕ СОСТОЯНИЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ Доход: *{format_number(total_income)} сум*\n"
            f"├ Обязательные: *{format_number(mandatory)} сум*\n"
            f"├ Платёж по долгу: *{format_number(loan_payment)} сум*\n"
            f"└ Свободные: *{format_number(free_cash)} сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *УМНОЕ РАСПРЕДЕЛЕНИЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 🏦 Для богатства: *{format_number(int(savings))} сум*\n"
            f"├ ⚡ Платёж по кредиту: *{format_number(int(extra_debt))} сум*\n"
            f"└ 🏠 Жизнь: *{format_number(int(living))} сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *РЕЗУЛЬТАТ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Срок выхода: *{pro_exit_months} мес*\n"
            f"📆 Дата: *{pro_exit_formatted}*\n"
            f"⏱ Экономия: *{months_saved} мес быстрее!*\n"
            f"💰 Накопленное богатство: *{format_number(int(savings_at_exit))} сум*\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Ежемесячный платёж: *{format_number(int(total_payment))} сум*\n"
            f"   (основной + дополнительный)"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 Statistika" if lang == "uz" else "📊 Статистика",
            callback_data="pro_statistics"
        )],
        [InlineKeyboardButton(
            "📋 Qarz nazorati" if lang == "uz" else "📋 Контроль долгов",
            callback_data="pro_debt_monitor"
        )],
        [InlineKeyboardButton(
            "📥 Excel yuklab olish" if lang == "uz" else "📥 Скачать Excel",
            callback_data="pro_export_excel"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================== AI YORDAMCHI HANDLERS ====================

async def ai_assistant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI assistant menu"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    from app.subscription_handlers import is_user_pro
    is_pro = await is_user_pro(telegram_id)
    
    if not is_pro:
        if lang == "uz":
            msg = (
                "🤖 *AI YORDAMCHI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Bu funksiya faqat PRO foydalanuvchilar uchun!\n\n"
                "💎 PRO obuna bilan:\n"
                "├ 🎤 Ovozli xabar orqali daromad/xarajat yozish\n"
                "├ 📊 Avtomatik kategoriyalash\n"
                "├ 📈 Guruhlab hisobot ko'rish\n"
                "└ 🧠 AI tahlil va maslahatlar\n\n"
                "PRO obuna oling va AI yordamchidan foydalaning!"
            )
        else:
            msg = (
                "🤖 *AI ПОМОЩНИК*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Эта функция только для PRO пользователей!\n\n"
                "💎 С PRO подпиской:\n"
                "├ 🎤 Запись доходов/расходов голосом\n"
                "├ 📊 Автоматическая категоризация\n"
                "├ 📈 Групповые отчёты\n"
                "└ 🧠 AI анализ и советы\n\n"
                "Оформите PRO и пользуйтесь AI помощником!"
            )
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # PRO user - show AI assistant menu
    if lang == "uz":
        msg = (
            "🤖 *AI YORDAMCHI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎤 *Ovozli xabar* yuboring va men:\n"
            "├ 📝 Matnni aniqlayman\n"
            "├ 💰 Daromad yoki xarajatni ajrataman\n"
            "├ 📊 Kategoriyaga qo'shaman\n"
            "└ 📈 Hisobotda ko'rsataman\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📌 *MISOL:*\n"
            "\"Bugun ovqatga 50 ming berdim\"\n"
            "\"Maosh tushdi 5 million\"\n\n"
            "👇 Ovozli xabar yuboring yoki tugmani bosing:"
        )
    else:
        msg = (
            "🤖 *AI ПОМОЩНИК*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎤 Отправьте *голосовое сообщение* и я:\n"
            "├ 📝 Распознаю текст\n"
            "├ 💰 Определю доход или расход\n"
            "├ 📊 Добавлю в категорию\n"
            "└ 📈 Покажу в отчёте\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📌 *ПРИМЕР:*\n"
            "\"Сегодня на еду потратил 50 тысяч\"\n"
            "\"Получил зарплату 5 миллионов\"\n\n"
            "👇 Отправьте голосовое или нажмите кнопку:"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 Hisobot ko'rish" if lang == "uz" else "📊 Посмотреть отчёт",
            callback_data="ai_report"
        )],
        [InlineKeyboardButton(
            "📋 Oxirgi yozuvlar" if lang == "uz" else "📋 Последние записи",
            callback_data="ai_recent"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    # Enable voice message mode
    context.user_data["awaiting_voice"] = True
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages for AI assistant - works automatically for PRO users
    MULTI-TRANSACTION SUPPORT: Bir ovozli xabarda bir nechta tranzaksiyalarni aniqlaydi
    
    PRO obunasi kerak. Obunasi yo'q foydalanuvchilarga PRO taklif qilinadi.
    """
    voice = update.message.voice
    if not voice:
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    logger.info(f"[VOICE] Voice message received from {telegram_id}, duration={voice.duration}s")
    
    # Import AI functions
    import os
    import tempfile
    from app.ai_assistant import (
        transcribe_voice, parse_voice_transaction, save_transaction,
        EXPENSE_CATEGORIES, INCOME_CATEGORIES,
        VOICE_TIERS, VOICE_PLUS_PRICE, VOICE_UNLIMITED_PRICE,
        check_voice_limit, increment_voice_usage, get_voice_tier_limits,
        format_voice_limit_message, format_voice_duration_error,
        # Multi-transaction imports
        parse_multiple_transactions, save_multiple_transactions,
        format_multiple_transactions_message
    )
    from app.subscription_handlers import is_user_pro
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        logger.warning(f"[VOICE] User {telegram_id} not found in DB")
        return
    
    # ==================== ADMIN TEKSHIRUVI ====================
    from app.config import ADMIN_IDS
    is_admin = telegram_id in ADMIN_IDS
    
    # ==================== 1. PRO OBUNA TEKSHIRUVI ====================
    # PRO obunasi bormi tekshirish (subscription_expires)
    is_pro = await is_user_pro(telegram_id) if not is_admin else True
    
    if not is_pro:
        # PRO obunasi yo'q - taklif qilish
        if lang == "uz":
            msg = (
                "🎤 *Ovozli kiritish - PRO funksiya*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Ovozli xabarlar orqali xarajatlarni kiritish "
                "faqat PRO foydalanuvchilar uchun mavjud.\n\n"
                "✅ Matnli kiritish *BEPUL* va cheksiz!\n"
                "Shunchaki yozing: _\"non 5000, choy 3000\"_\n\n"
                "💎 PRO bilan ovoz orqali ham kiritishingiz mumkin!"
            )
        else:
            msg = (
                "🎤 *Голосовой ввод - PRO функция*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Ввод расходов голосом доступен "
                "только для PRO пользователей.\n\n"
                "✅ Текстовый ввод *БЕСПЛАТНО* и без лимитов!\n"
                "Просто напишите: _\"хлеб 5000, чай 3000\"_\n\n"
                "💎 С PRO можете вводить и голосом!"
            )
        
        keyboard = [
            [InlineKeyboardButton(
                "💎 PRO ga o'tish" if lang == "uz" else "💎 Перейти на PRO",
                callback_data="show_pricing"
            )]
        ]
        
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== 2. VOICE TIER VA LIMITLAR ====================
    # PRO foydalanuvchi - voice tier tekshirish
    voice_tier = user.get("voice_tier", "plus") or "plus"  # PRO default = plus
    voice_tier_expires = user.get("voice_tier_expires")
    
    # Check if voice tier has expired - revert to plus (PRO default)
    if voice_tier not in ["plus", "unlimited"] and voice_tier_expires:
        from datetime import datetime
        if isinstance(voice_tier_expires, str):
            try:
                voice_tier_expires = datetime.fromisoformat(voice_tier_expires.replace("Z", "+00:00"))
            except:
                voice_tier_expires = None
        
        if voice_tier_expires and datetime.now() > voice_tier_expires.replace(tzinfo=None):
            voice_tier = "plus"  # PRO default
            logger.info(f"[VOICE] User {telegram_id} voice tier expired, reverted to plus")
    
    # PRO foydalanuvchi uchun minimal tier = plus
    if voice_tier == "basic":
        voice_tier = "plus"
    
    # ==================== 3. OVOZ UZUNLIGI TEKSHIRUVI ====================
    # Get tier limits
    tier_limits = get_voice_tier_limits(voice_tier)
    max_duration = tier_limits["max_duration"]
    
    # Get bonus voice count
    bonus_voice = user.get("bonus_voice_count", 0) or 0
    
    logger.info(f"[VOICE] User {telegram_id} - Tier: {voice_tier}, Max Duration: {max_duration}s, Bonus: {bonus_voice}")
    
    # Check voice duration limit (based on tier)
    voice_duration = voice.duration or 0
    
    # Admin uchun limitlarni tekshirmaslik
    if not is_admin and voice_duration > max_duration:
        await update.message.reply_text(
            format_voice_duration_error(voice_duration, voice_tier, lang),
            parse_mode="Markdown"
        )
        return
    
    # ==================== 4. OYLIK LIMIT TEKSHIRUVI ====================
    if not is_admin:
        limit_info = await check_voice_limit(db, user["id"], voice_tier=voice_tier, bonus_voice=bonus_voice)
    else:
        # Admin uchun cheksiz
        limit_info = {"allowed": True, "remaining": 999, "limit": 999, "used": 0}
    
    if not limit_info["allowed"]:
        # Limit tugagan - qo'shimcha ovozli paket taklif qilish
        if voice_tier == "plus":
            # Voice+ userga Voice Unlimited taklif qilish
            if lang == "uz":
                msg = (
                    "🎤 *Oylik limit tugadi*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Siz bu oyda *{limit_info['limit']} ta* ovozli xabar ishlatdingiz.\n\n"
                    "🚀 *Voice Unlimited* bilan cheksiz ovozli xabar yuboring!"
                )
            else:
                msg = (
                    "🎤 *Месячный лимит исчерпан*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Вы использовали *{limit_info['limit']}* голосовых сообщений в этом месяце.\n\n"
                    "🚀 С *Voice Unlimited* отправляйте без ограничений!"
                )
            
            keyboard = [
                [InlineKeyboardButton(
                    f"🎤 Voice Unlimited - {format_number(VOICE_UNLIMITED_PRICE)} so'm" if lang == "uz" else f"🎤 Voice Unlimited - {format_number(VOICE_UNLIMITED_PRICE)} сум",
                    callback_data="buy_voice_unlimited"
                )]
            ]
            
            await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        # unlimited tier uchun limit yo'q, bu yerga kelmaydi
        return
    
    try:
        # ==================== BOSQICH 1: Ovoz qabul qilindi ====================
        # Limit ma'lumotini "AI tahlil qilmoqda" joyida ko'rsatish uchun
        used = limit_info.get('used', 0) + 1  # hozirgi xabar ham
        limit = limit_info.get('limit', 60)
        
        # Admin uchun limit ko'rsatmaslik
        if is_admin:
            limit_text = ""
        elif voice_tier == "unlimited":
            limit_text = " _(cheksiz)_" if lang == "uz" else " _(безлимит)_"
        else:
            limit_text = f" _({used}/{limit})_"
        
        if lang == "uz":
            step1_text = "🎤 _Ovoz qabul qilindi..._"
        else:
            step1_text = "🎤 _Голос получен..._"
        
        processing_msg = await update.message.reply_text(step1_text, parse_mode="Markdown")
        
        # ==================== BOSQICH 2: Faylni yuklash ====================
        voice_file = await voice.get_file()
        logger.info(f"[VOICE] Got file: {voice_file.file_path}")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        await voice_file.download_to_drive(tmp_path)
        logger.info(f"[VOICE] Downloaded to: {tmp_path}")
        
        # Update message - AI tahlil qilmoqda + limit ko'rsatish
        if lang == "uz":
            step2_text = f"🤖 _AI tahlil qilmoqda..._{limit_text}"
        else:
            step2_text = f"🤖 _AI анализирует..._{limit_text}"
        
        await processing_msg.edit_text(step2_text, parse_mode="Markdown")
        
        # ==================== BOSQICH 3: Transcribe voice ====================
        logger.info(f"[VOICE] Calling transcribe_voice...")
        text = await transcribe_voice(tmp_path)
        logger.info(f"[VOICE] Transcribed text: '{text}'")
        
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except:
            pass
        
        if not text:
            logger.warning(f"[VOICE] Transcription returned None/empty")
            await processing_msg.edit_text(
                "❌ Ovozni aniqlab bo'lmadi. Qaytadan urinib ko'ring." if lang == "uz" else 
                "❌ Не удалось распознать голос. Попробуйте ещё раз.",
                parse_mode="Markdown"
            )
            return
        
        logger.info(f"[VOICE] Successfully transcribed: '{text}'")
        
        # Matnni qisqartirish (40 belgidan ko'p bo'lsa)
        short_text = text[:37] + "..." if len(text) > 40 else text
        
        # Increment voice usage AFTER successful transcription (Admin uchun skip)
        if not is_admin:
            await increment_voice_usage(db, user["id"], voice_duration)
        
        # ==================== AVVAL KO'P TRANZAKSIYA BORLIGINI TEKSHIRISH ====================
        # Agar matnda bir nechta summa bo'lsa, avval parse_multiple_transactions chaqiriladi
        # Bu "3 million tushdi, 1 million qarzga berdim, 500 ming ijaraga..." kabi xabarlar uchun
        
        from app.ai_assistant import (
            parse_debt_transaction, save_personal_debt, format_debt_saved_message,
            get_debt_summary, format_debt_summary_message,
            find_all_amounts_with_context  # Ko'p summa borligini tekshirish uchun
        )
        
        # Ko'p summa bormi tekshirish
        amounts_found = find_all_amounts_with_context(text)
        has_multiple_amounts = len(amounts_found) > 1
        
        logger.info(f"[VOICE] Summalar soni: {len(amounts_found)}, ko'p summa: {has_multiple_amounts}")
        
        # ==================== MULTI-TRANSACTION PARSING (BIRINCHI) ====================
        # Agar ko'p summa bo'lsa YOKI matnda vergul/va bilan ajratilgan gaplar bo'lsa
        if has_multiple_amounts or ',' in text or ' va ' in text.lower():
            logger.info(f"[VOICE] Ko'p tranzaksiya rejimi - parse_multiple_transactions chaqirilmoqda")
            
            transactions = await parse_multiple_transactions(text, lang)
            
            if transactions and len(transactions) > 0:
                logger.info(f"[VOICE] {len(transactions)} ta tranzaksiya topildi")
                
                # Get budget status
                from app.ai_assistant import get_budget_status
                budget_status = await get_budget_status(db, user["id"])
                
                if len(transactions) == 1:
                    # ==================== BITTA TRANZAKSIYA ====================
                    transaction = transactions[0]
                    
                    # Save transaction to database
                    from app.ai_assistant import format_expense_saved_with_budget
                    transaction_id = await save_transaction(db, user["id"], transaction)
                    
                    # Save original voice message ID for deletion after confirmation
                    context.user_data["original_message_id"] = update.message.message_id
                    
                    # O'RGANISH UCHUN: Context da saqlash (ko'pni tozalash)
                    context.user_data.pop("last_multi_transactions", None)
                    context.user_data["last_transaction"] = {
                        "original_text": text,
                        "transaction_id": transaction_id,
                        "type": transaction["type"],
                        "category": transaction["category"],
                        "amount": transaction["amount"],
                        "description": transaction.get("description", ""),
                        "ai_source": transaction.get("ai_source", "local"),
                        "needs_learning": True  # Har doim o'rganish
                    }
                    
                    # Format response with budget info
                    msg = format_expense_saved_with_budget(transaction, budget_status, lang)
                    
                    # AI manbasini ko'rsatish
                    ai_source = transaction.get("ai_source", "local")
                    if ai_source == "gemini":
                        msg += "\n\n🤖 _Gemini AI yordamida tahlil qilindi_" if lang == "uz" else "\n\n🤖 _Анализ с помощью Gemini AI_"
                    
                    # Get updated voice limit info (Admin uchun ko'rsatmaslik)
                    if not is_admin:
                        new_limit_info = await check_voice_limit(db, user["id"])
                        limit_msg = f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} ovozli xabar qoldi_" if lang == "uz" else f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} голосовых осталось_"
                        msg += limit_msg
                    
                    # Aniqlashtirish kerakmi tekshirish - kengaytirilgan
                    needs_clarification = (
                        transaction.get("needs_confirmation", False) or 
                        transaction.get("needs_clarification", False) or
                        transaction.get("category") == "boshqa" or
                        transaction.get("category_key") == "boshqa"
                    )
                    
                    # Keyboard - birinchi aniqlashtirish (agar kerak)
                    keyboard = []
                    
                    # Aniqlashtirish tugmasi - ixtiyoriy (birinchi qatorda)
                    if needs_clarification:
                        keyboard.append([InlineKeyboardButton(
                            "🔍 Kategoriyani aniqlashtirish" if lang == "uz" else "🔍 Уточнить категорию",
                            callback_data=f"ai_clarify_category_{transaction_id}"
                        )])
                        # Xabar oxiriga eslatma
                        msg += "\n\n_💡 Kategoriya noaniq. Aniqlashtirish ixtiyoriy._" if lang == "uz" else "\n\n_💡 Категория неточна. Уточнение необязательно._"
                    
                    # To'g'ri/Noto'g'ri tugmalari
                    keyboard.append([
                        InlineKeyboardButton(
                            "✅ To'g'ri" if lang == "uz" else "✅ Верно",
                            callback_data="ai_confirm_learn"
                        ),
                        InlineKeyboardButton(
                            "❌ Noto'g'ri" if lang == "uz" else "❌ Неверно",
                            callback_data=f"ai_correct_{transaction_id}"
                        )
                    ])
                    
                    # Hisobot tugmasi
                    keyboard.append([InlineKeyboardButton(
                        "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
                        callback_data="ai_report"
                    )])
                    
                    await processing_msg.edit_text(
                        msg,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                else:
                    # ==================== KO'P TRANZAKSIYALAR ====================
                    # Save all transactions
                    transaction_ids = await save_multiple_transactions(db, user["id"], transactions)
                    
                    # Save original voice message ID for deletion after confirmation
                    context.user_data["original_message_id"] = update.message.message_id
                    
                    # O'RGANISH UCHUN: Ko'p tranzaksiyalarni context ga saqlash (bittani tozalash)
                    context.user_data.pop("last_transaction", None)
                    context.user_data["last_multi_transactions"] = {
                        "original_text": text,
                        "transactions": transactions,
                        "transaction_ids": transaction_ids
                    }
                    
                    # Format response (now returns tuple with needs_clarification_list)
                    msg, needs_clarification_list = format_multiple_transactions_message(transactions, budget_status, lang)
                    
                    # Get updated voice limit info (Admin uchun ko'rsatmaslik)
                    if not is_admin:
                        new_limit_info = await check_voice_limit(db, user["id"])
                        limit_msg = f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} ovozli xabar qoldi_" if lang == "uz" else f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} голосовых осталось_"
                        msg += limit_msg
                    
                    # Keyboard
                    ids_str = ",".join([str(tid) for tid in transaction_ids])
                    keyboard = []
                    
                    # Aniqlashtirish tugmasi - agar kerak bo'lsa
                    if needs_clarification_list:
                        keyboard.append([InlineKeyboardButton(
                            f"🔍 Aniqlashtirish ({len(needs_clarification_list)} ta)" if lang == "uz" else f"🔍 Уточнить ({len(needs_clarification_list)})",
                            callback_data=f"ai_clarify_multi_{ids_str}"
                        )])
                    
                    keyboard.append([
                        InlineKeyboardButton(
                            "✅ Hammasi to'g'ri" if lang == "uz" else "✅ Всё верно",
                            callback_data="ai_confirm_learn"  # O'rganish bilan tasdiqlash
                        ),
                        InlineKeyboardButton(
                            "✏️ Tuzatish" if lang == "uz" else "✏️ Исправить",
                            callback_data=f"ai_correct_multi_{ids_str}"
                        )
                    ])
                    keyboard.append([InlineKeyboardButton(
                        "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
                        callback_data="ai_report"
                    )])
                    
                    await processing_msg.edit_text(
                        msg,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
        
        # ==================== QARZ TEKSHIRISH (BITTA SUMMA BO'LGANDA) ====================
        # Faqat bitta summa bo'lganda qarz tekshiruvi
        debt_info = await parse_debt_transaction(text, lang)
        
        if debt_info:
            # Bu qarz tranzaksiyasi
            debt_id = await save_personal_debt(db, user["id"], debt_info)
            
            # Qarz xulosasini olish
            debt_summary = await get_debt_summary(db, user["id"])
            
            # Xabarni formatlash
            msg = format_debt_saved_message(debt_info, lang)
            msg += "\n\n" + format_debt_summary_message(debt_summary, lang)
            
            # Get updated voice limit info (Admin uchun ko'rsatmaslik)
            if not is_admin:
                new_limit_info = await check_voice_limit(db, user["id"])
                msg += f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} ovozli xabar qoldi_" if lang == "uz" else f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} голосовых осталось_"
            
            await update.message.reply_text(
                msg,
                parse_mode="Markdown"
            )
            return
        debt_info = await parse_debt_transaction(text, lang)
        
        if debt_info:
            # Bu qarz tranzaksiyasi
            debt_id = await save_personal_debt(db, user["id"], debt_info)
            
            # Qarz xulosasini olish
            debt_summary = await get_debt_summary(db, user["id"])
            
            # Xabarni formatlash
            msg = format_debt_saved_message(debt_info, lang)
            msg += "\n\n" + format_debt_summary_message(debt_summary, lang)
            
            # Get updated voice limit info (Admin uchun ko'rsatmaslik)
            if not is_admin:
                new_limit_info = await check_voice_limit(db, user["id"])
                limit_msg = f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} ovozli xabar qoldi_" if lang == "uz" else f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} голосовых осталось_"
                msg += limit_msg
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ To'g'ri" if lang == "uz" else "✅ Верно",
                        callback_data="ai_confirm_ok"
                    ),
                    InlineKeyboardButton(
                        "❌ Noto'g'ri" if lang == "uz" else "❌ Неверно",
                        callback_data=f"ai_debt_correct_{debt_id}"
                    )
                ],
                [InlineKeyboardButton(
                    "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
                    callback_data="ai_debt_list"
                )]
            ]
            
            await processing_msg.edit_text(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # ==================== QOLGAN HOLAT - SUMMA TOPILMADI ====================
        # Agar yuqoridagi hech biri ishlamagan bo'lsa
        transactions = await parse_multiple_transactions(text, lang)
        
        if not transactions:
            await processing_msg.edit_text(
                f"📝 *Aniqlangan matn:* {text}\n\n"
                f"❌ Summa topilmadi. Summani aniq ayting." if lang == "uz" else
                f"📝 *Распознанный текст:* {text}\n\n"
                f"❌ Сумма не найдена. Назовите сумму чётко.",
                parse_mode="Markdown"
            )
            return
        
        # Get budget status
        from app.ai_assistant import get_budget_status
        budget_status = await get_budget_status(db, user["id"])
        
        # Bitta tranzaksiya
        transaction = transactions[0]
        from app.ai_assistant import format_expense_saved_with_budget
        transaction_id = await save_transaction(db, user["id"], transaction)
        
        # Save original voice message ID for deletion after confirmation
        context.user_data["original_message_id"] = update.message.message_id
        
        # Context da saqlash
        context.user_data["last_transaction"] = {
            "original_text": text,
            "transaction_id": transaction_id,
            "type": transaction["type"],
            "category": transaction["category"],
            "amount": transaction["amount"],
            "description": transaction.get("description", ""),
            "ai_source": transaction.get("ai_source", "local"),
            "needs_learning": transaction.get("ai_source") == "gemini"
        }
        
        msg = format_expense_saved_with_budget(transaction, budget_status, lang)
        
        # Admin uchun limit ko'rsatmaslik
        if not is_admin:
            new_limit_info = await check_voice_limit(db, user["id"])
            limit_msg = f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} ovozli xabar qoldi_" if lang == "uz" else f"\n\n🎤 _{new_limit_info['remaining']}/{new_limit_info['limit']} голосовых осталось_"
            msg += limit_msg
        
        # Aniqlashtirish kerakmi tekshirish
        needs_clarification = transaction.get("needs_confirmation", False) or transaction.get("category") == "boshqa"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ To'g'ri" if lang == "uz" else "✅ Верно",
                    callback_data="ai_confirm_learn"
                ),
                InlineKeyboardButton(
                    "❌ Noto'g'ri" if lang == "uz" else "❌ Неверно",
                    callback_data=f"ai_correct_{transaction_id}"
                )
            ]
        ]
        
        if needs_clarification:
            keyboard.insert(0, [InlineKeyboardButton(
                "🔍 Kategoriyani aniqlashtirish" if lang == "uz" else "🔍 Уточнить категорию",
                callback_data=f"ai_clarify_category_{transaction_id}"
            )])
            msg += "\n\n_💡 Kategoriya noaniq. Aniqlashtirish ixtiyoriy._" if lang == "uz" else "\n\n_💡 Категория неточна. Уточнение необязательно._"
        
        keyboard.append([InlineKeyboardButton(
            "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
            callback_data="ai_report"
        )])
        
        await processing_msg.edit_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        print(f"AI voice handler error: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка",
            parse_mode="Markdown"
        )


async def ai_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text messages for AI assistant - auto-detect expenses/income/debts from text
    Works for PRO users without pressing any button
    """
    # Skip if message is a command or from conversation handler
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    
    # Skip menu buttons and commands
    menu_patterns = [
        "📊", "👤", "💎", "🌐", "❓", "/", "Hisobotlarim", "Мои отчёты",
        "Profil", "Профиль", "PRO", "Til", "Язык", "Yordam", "Помощь",
        # Menu tugmalari - yangi qo'shildi
        "✍️", "Xarajat", "Расход", "💰", "Daromad", "Доход",
        "📋", "Qarzlar", "Долги", "🔄", "Transfer", "Перевод",
        "⚙️", "Sozlamalar", "Настройки", "📈", "Statistika", "Статистика",
        "🏠", "Bosh sahifa", "Главная", "⬅️", "Orqaga", "Назад"
    ]
    for pattern in menu_patterns:
        if pattern in text:
            return
    
    # ========== YANGI KATEGORIYA KIRITISH ==========
    if context.user_data.get("awaiting_new_category"):
        transaction_id = context.user_data.get("new_category_transaction_id")
        if transaction_id:
            # Yangi kategoriya nomini saqlash
            new_category_name = text.strip()
            
            # Kategoriya kalitini yaratish (emoji va nomdan)
            import re
            # Emoji ni ajratish
            emoji_match = re.match(r'^([\U0001F300-\U0001F9FF\U00002600-\U000027BF]+)\s*(.+)$', new_category_name)
            if emoji_match:
                emoji = emoji_match.group(1)
                name = emoji_match.group(2)
                category_key = f"custom_{name.lower().replace(' ', '_')}"
            else:
                emoji = "📦"
                name = new_category_name
                category_key = f"custom_{name.lower().replace(' ', '_')}"
                new_category_name = f"{emoji} {name}"
            
            from app.ai_assistant import get_transaction_by_id, confirm_and_learn
            
            db = await get_database()
            user = await db.get_user(telegram_id)
            
            if user:
                transaction = await get_transaction_by_id(db, transaction_id)
                
                if transaction and transaction["user_id"] == user["id"]:
                    # Database'ni yangilash
                    try:
                        if db.is_postgres:
                            async with db._pool.acquire() as conn:
                                await conn.execute("""
                                    UPDATE transactions 
                                    SET category = $1, category_key = $2
                                    WHERE id = $3 AND user_id = $4
                                """, new_category_name, category_key, transaction_id, user["id"])
                        else:
                            await db._connection.execute("""
                                UPDATE transactions 
                                SET category = ?, category_key = ?
                                WHERE id = ? AND user_id = ?
                            """, (new_category_name, category_key, transaction_id, user["id"]))
                            await db._connection.commit()
                        
                        # AI'ga o'rgatish
                        original_text = transaction.get("description", "")
                        if original_text:
                            await confirm_and_learn(original_text, {
                                "type": transaction["type"],
                                "category": category_key,
                                "amount": transaction["amount"],
                                "description": transaction.get("description", "")
                            })
                        
                        lang = context.user_data.get("lang", "uz")
                        if lang == "uz":
                            msg = (
                                "✅ *YANGI KATEGORIYA YARATILDI*\n"
                                "━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"📂 Kategoriya: *{new_category_name}*\n"
                                f"💰 Summa: *{transaction['amount']:,}* so'm\n\n"
                                "🧠 _AI bu kategoriyani o'rgandi!_"
                            )
                        else:
                            msg = (
                                "✅ *НОВАЯ КАТЕГОРИЯ СОЗДАНА*\n"
                                "━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"📂 Категория: *{new_category_name}*\n"
                                f"💰 Сумма: *{transaction['amount']:,}* сум\n\n"
                                "🧠 _AI запомнил эту категорию!_"
                            )
                        
                        await update.message.reply_text(msg, parse_mode="Markdown")
                        
                    except Exception as e:
                        print(f"[NEW-CATEGORY] Error: {e}")
                        await update.message.reply_text("❌ Xatolik" if lang == "uz" else "❌ Ошибка")
            
            # Flaglarni tozalash
            context.user_data["awaiting_new_category"] = False
            context.user_data["new_category_transaction_id"] = None
            return
    
    # Skip if user is editing a profile field
    if context.user_data.get("editing_field"):
        return
    
    # Skip if user is in some editing mode or ConversationHandler state
    editing_modes = [
        # Old modes
        "awaiting_income", "awaiting_partner_income", "awaiting_loan", 
        "awaiting_total_debt", "editing_profile", "awaiting_promo",
        "ai_correcting", "awaiting_new_category",
        # ConversationHandler related states
        "in_conversation",  # General conversation flag
        "entering_income", "entering_rent", "entering_utilities",
        "entering_loan", "entering_debt", "entering_mandatory",
        "entering_kindergarten", "uploading_transaction", "uploading_katm",
        # Profile editing states
        "editing_income_self", "editing_income_partner", "editing_rent",
        "editing_utilities", "editing_loan", "editing_mandatory",
        "editing_kindergarten", "editing_total_debt",
        # Recurring/credit entry states  
        "adding_recurring", "adding_credit", "adding_fixed_income",
        "editing_recurring", "editing_credit", "editing_fixed_income",
        # Other input states
        "awaiting_text_input", "awaiting_number_input",
        # Registration states
        "awaiting_phone", "awaiting_contact", "awaiting_language",
        # AI correction states
        "ai_amount_editing", "ai_editing_amount"
    ]
    for mode in editing_modes:
        if context.user_data.get(mode):
            return
    
    # Check if currently in active ConversationHandler state
    # ConversationHandler stores its state in user_data with special keys
    conv_keys = [k for k in context.user_data.keys() if isinstance(k, tuple) and len(k) >= 2]
    if conv_keys:
        # User is in active conversation
        return
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check if user is registered (has phone number)
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Agar ro'yxatdan o'tmagan bo'lsa (telefon raqam yo'q) - AI ishlamasin
    if not user.get("phone_number"):
        return
    
    # Check PRO status
    from app.subscription_handlers import is_user_pro
    is_pro = await is_user_pro(telegram_id)
    
    if not is_pro:
        return  # Silently ignore for non-PRO users
    
    try:
        # ==================== QARZ TEKSHIRISH ====================
        from app.ai_assistant import (
            parse_debt_transaction, save_personal_debt, format_debt_saved_message,
            get_debt_summary, format_debt_summary_message,
            parse_voice_transaction, save_transaction, 
            get_budget_status, format_expense_saved_with_budget,
            # Multi-transaction imports
            parse_multiple_transactions, save_multiple_transactions,
            format_multiple_transactions_message
        )
        
        # Avval qarz ekanligini tekshirish
        debt_info = await parse_debt_transaction(text, lang)
        
        if debt_info:
            # Bu qarz tranzaksiyasi
            debt_id = await save_personal_debt(db, user["id"], debt_info)
            
            # Qarz xulosasini olish
            debt_summary = await get_debt_summary(db, user["id"])
            
            # Xabarni formatlash
            msg = format_debt_saved_message(debt_info, lang)
            msg += "\n\n" + format_debt_summary_message(debt_summary, lang)
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ To'g'ri" if lang == "uz" else "✅ Верно",
                        callback_data="ai_confirm_ok"
                    ),
                    InlineKeyboardButton(
                        "❌ Noto'g'ri" if lang == "uz" else "❌ Неверно",
                        callback_data=f"ai_debt_correct_{debt_id}"
                    )
                ],
                [InlineKeyboardButton(
                    "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
                    callback_data="ai_debt_list"
                )]
            ]
            
            await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # ==================== MULTI-TRANSACTION PARSING ====================
        # Bir matnda bir nechta tranzaksiyalarni aniqlash
        
        transactions = await parse_multiple_transactions(text, lang)
        
        # If no transactions found, this is probably not a transaction message
        if not transactions:
            return
        
        # Get budget status
        budget_status = await get_budget_status(db, user["id"])
        
        if len(transactions) == 1:
            # ==================== BITTA TRANZAKSIYA - TO'LIQ IMKONIYATLAR ====================
            transaction = transactions[0]
            
            # Save transaction
            transaction_id = await save_transaction(db, user["id"], transaction)
            
            # O'RGANISH UCHUN: Context da saqlash (ko'pni tozalash)
            context.user_data.pop("last_multi_transactions", None)
            context.user_data["last_transaction"] = {
                "original_text": text,
                "transaction_id": transaction_id,
                "type": transaction["type"],
                "category": transaction["category"],
                "amount": transaction["amount"],
                "description": transaction.get("description", ""),
                "ai_source": transaction.get("ai_source", "local"),
                "needs_learning": True  # Har doim o'rganish
            }
            
            # Format response with budget info
            msg = format_expense_saved_with_budget(transaction, budget_status, lang)
            
            # AI manbasini ko'rsatish
            ai_source = transaction.get("ai_source", "local")
            confidence = transaction.get("confidence", 0)
            if ai_source == "gemini":
                msg += f"\n\n🤖 _Gemini AI tahlili_" if lang == "uz" else f"\n\n🤖 _Анализ Gemini AI_"
            elif ai_source == "learned":
                msg += f"\n\n🧠 _O'rganilgan pattern ({confidence}%)_" if lang == "uz" else f"\n\n🧠 _Изученный паттерн ({confidence}%)_"
            
            # Aniqlashtirish kerakmi tekshirish
            needs_clarification = (
                transaction.get("needs_confirmation", False) or 
                transaction.get("needs_clarification", False) or
                transaction.get("category") == "boshqa" or
                transaction.get("category_key") == "boshqa"
            )
            
            # Keyboard with correction and clarification options
            keyboard = []
            
            # Aniqlashtirish tugmasi - agar kerak bo'lsa, birinchi qatorda
            if needs_clarification:
                keyboard.append([InlineKeyboardButton(
                    "🔍 Kategoriyani aniqlashtirish" if lang == "uz" else "🔍 Уточнить категорию",
                    callback_data=f"ai_clarify_category_{transaction_id}"
                )])
                msg += "\n\n_💡 Kategoriya noaniq. Aniqlashtirish ixtiyoriy._" if lang == "uz" else "\n\n_💡 Категория неточна. Уточнение необязательно._"
            
            # To'g'ri/Noto'g'ri tugmalari
            keyboard.append([
                InlineKeyboardButton(
                    "✅ To'g'ri" if lang == "uz" else "✅ Верно",
                    callback_data="ai_confirm_learn"  # O'rganish bilan
                ),
                InlineKeyboardButton(
                    "❌ Noto'g'ri" if lang == "uz" else "❌ Неверно",
                    callback_data=f"ai_correct_{transaction_id}"
                )
            ])
            
            # Hisobot tugmasi
            keyboard.append([InlineKeyboardButton(
                "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
                callback_data="ai_report"
            )])
        else:
            # ==================== KO'P TRANZAKSIYALAR ====================
            # Faqat eng yaxshi bitta tranzaksiyani ko'rsatish (UX va mpl uchun)
            best_tx = transactions[0] if transactions else None
            if best_tx:
                transaction_ids = await save_multiple_transactions(db, user["id"], [best_tx])
                context.user_data.pop("last_transaction", None)
                context.user_data["last_multi_transactions"] = {
                    "original_text": text,
                    "transactions": [best_tx],
                    "transaction_ids": transaction_ids
                }
                # Format single transaction as if it was a multi
                from app.ai_assistant import format_multiple_transactions_message
                msg, needs_clarification_list = format_multiple_transactions_message([best_tx], budget_status, lang)
                ids_str = ",".join([str(tid) for tid in transaction_ids])
                keyboard = []
                if needs_clarification_list:
                    keyboard.append([InlineKeyboardButton(
                        f"🔍 Aniqlashtirish (1 ta)" if lang == "uz" else f"🔍 Уточнить (1)",
                        callback_data=f"ai_clarify_multi_{ids_str}"
                    )])
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Hammasi to'g'ri" if lang == "uz" else "✅ Всё верно",
                        callback_data="ai_confirm_learn"
                    ),
                    InlineKeyboardButton(
                        "✏️ Tuzatish" if lang == "uz" else "✏️ Исправить",
                        callback_data=f"ai_correct_multi_{ids_str}"
                    )
                ])
                keyboard.append([InlineKeyboardButton(
                    "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
                    callback_data="ai_report"
                )])
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    "❌ AI tranzaksiya aniqlay olmadi.",
                    parse_mode="Markdown"
                )
        
    except Exception as e:
        print(f"AI text handler error: {e}")
        import traceback
        traceback.print_exc()


async def ai_confirm_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User confirmed transaction is correct - WITHOUT learning"""
    query = update.callback_query
    await query.answer("✅" if context.user_data.get("lang") == "uz" else "✅")
    
    # Just remove the buttons, keep the message
    await query.edit_message_reply_markup(reply_markup=None)


async def ai_confirm_learn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User confirmed transaction is correct - WITH learning from AI response"""
    query = update.callback_query
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # O'rganish uchun saqlangan ma'lumotlarni olish
    last_tx = context.user_data.get("last_transaction")
    last_multi_tx = context.user_data.get("last_multi_transactions")  # Ko'p tranzaksiyalar
    
    learned = False
    
    # Bitta tranzaksiyadan o'rganish - har doim o'rganish
    if last_tx:
        from app.ai_assistant import confirm_and_learn
        
        original_text = last_tx.get("original_text", "")
        confirmed_result = {
            "type": last_tx.get("type"),
            "category": last_tx.get("category"),
            "amount": last_tx.get("amount"),
            "description": last_tx.get("description")
        }
        
        # Original text bo'lsa o'rganish
        if original_text and confirmed_result.get("type") and confirmed_result.get("category"):
            learned = await confirm_and_learn(original_text, confirmed_result)
    
    # Ko'p tranzaksiyalardan o'rganish
    if last_multi_tx:
        from app.ai_assistant import learn_from_multi_transaction
        
        original_text = last_multi_tx.get("original_text", "")
        transactions = last_multi_tx.get("transactions", [])
        
        if transactions and original_text:
            learned = await learn_from_multi_transaction(original_text, transactions)
    
    # Try to delete the original user message (voice or text)
    original_message_id = context.user_data.get("original_message_id")
    if original_message_id:
        try:
            await context.bot.delete_message(
                chat_id=telegram_id,
                message_id=original_message_id
            )
        except Exception:
            pass  # Message may already be deleted or too old
        context.user_data.pop("original_message_id", None)
    
    # Get daily statistics
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if user:
        from app.ai_assistant import get_budget_status
        budget_status = await get_budget_status(db, user["id"])
        
        today_income = budget_status.get('today_income', 0)
        today_expense = budget_status.get('today_expense', 0)
        today_balance = today_income - today_expense
        
        # Build beautiful confirmation message with daily stats
        if lang == "uz":
            msg = "✅ *TASDIQLANDI!*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += "┌─────────────────────┐\n"
            msg += "│    📊 *BUGUNGI HISOBOT*    │\n"
            msg += "└─────────────────────┘\n\n"
            msg += f"💰 Daromad: *{format_number(today_income)}* so'm\n"
            msg += f"💸 Xarajat: *{format_number(today_expense)}* so'm\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if today_balance >= 0:
                msg += f"📈 Balans: *+{format_number(today_balance)}* so'm ✅"
            else:
                msg += f"📉 Balans: *{format_number(today_balance)}* so'm ⚠️"
        else:
            msg = "✅ *ПОДТВЕРЖДЕНО!*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += "┌─────────────────────┐\n"
            msg += "│    📊 *ОТЧЁТ ЗА ДЕНЬ*    │\n"
            msg += "└─────────────────────┘\n\n"
            msg += f"💰 Доход: *{format_number(today_income)}* сум\n"
            msg += f"💸 Расход: *{format_number(today_expense)}* сум\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if today_balance >= 0:
                msg += f"📈 Баланс: *+{format_number(today_balance)}* сум ✅"
            else:
                msg += f"📉 Баланс: *{format_number(today_balance)}* сум ⚠️"
        
        # Quick action buttons
        keyboard = [[
            InlineKeyboardButton(
                "📊 Batafsil" if lang == "uz" else "📊 Подробнее",
                callback_data="show_reports"
            ),
            InlineKeyboardButton(
                "➕ Yana kiritish" if lang == "uz" else "➕ Ещё запись",
                callback_data="add_transaction_menu"
            )
        ]]
        
        await query.answer("✅")
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Fallback - just remove buttons
        await query.answer(
            "✅ Qabul qilindi!" if lang == "uz" else "✅ Принято!",
            show_alert=False
        )
        await query.edit_message_reply_markup(reply_markup=None)
    
    # Context ni tozalash
    context.user_data.pop("last_transaction", None)
    context.user_data.pop("last_multi_transactions", None)


async def ai_correct_multi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle correction for multiple transactions"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction IDs from callback data: ai_correct_multi_1,2,3
    callback_data = query.data
    try:
        ids_str = callback_data.replace("ai_correct_multi_", "")
        transaction_ids = [int(x) for x in ids_str.split(",")]
    except:
        await query.edit_message_text("Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка")
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Get all transactions
    transactions = []
    for tid in transaction_ids:
        tx = await get_transaction_by_id(db, tid)
        if tx and tx["user_id"] == user["id"]:
            transactions.append(tx)
    
    if not transactions:
        await query.edit_message_text(
            "❌ Tranzaksiyalar topilmadi" if lang == "uz" else "❌ Транзакции не найдены"
        )
        return
    
    # Show list of transactions to correct
    if lang == "uz":
        msg = (
            "✏️ *QAYSI YOZUVNI TUZATISH KERAK?*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    else:
        msg = (
            "✏️ *КАКУЮ ЗАПИСЬ ИСПРАВИТЬ?*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    keyboard = []
    for i, tx in enumerate(transactions, 1):
        tx_type = "📥 Daromad" if tx['type'] == 'income' else "📤 Xarajat"
        if lang == "ru":
            tx_type = "📥 Доход" if tx['type'] == 'income' else "📤 Расход"
        
        msg += f"{i}. {tx_type}: *{tx['amount']:,}* - {tx.get('description', '')[:30]}\n"
        
        keyboard.append([InlineKeyboardButton(
            f"✏️ #{i} - {tx['amount']:,}",
            callback_data=f"ai_correct_{tx['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "🗑 Hammasini o'chirish" if lang == "uz" else "🗑 Удалить всё",
        callback_data=f"ai_delete_all_{ids_str}"
    )])
    keyboard.append([InlineKeyboardButton(
        "◀️ Bekor qilish" if lang == "uz" else "◀️ Отмена",
        callback_data="ai_cancel_correct"
    )])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_clarify_multi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ko'p tranzaksiyalar uchun aniqlashtirish - qaysi birini aniqlashtirish kerakligini ko'rsatish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction IDs from callback data: ai_clarify_multi_1,2,3
    callback_data = query.data
    try:
        ids_str = callback_data.replace("ai_clarify_multi_", "")
        transaction_ids = [int(x) for x in ids_str.split(",")]
    except:
        await query.edit_message_text("Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка")
        return
    
    from app.ai_assistant import get_transaction_by_id
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Aniqlashtirish kerak bo'lgan tranzaksiyalarni topish
    needs_clarification = []
    for tid in transaction_ids:
        tx = await get_transaction_by_id(db, tid)
        if tx and tx["user_id"] == user["id"]:
            # Kategoriya "boshqa" yoki noaniq bo'lsa
            if tx.get("category_key") == "boshqa" or tx.get("category") in ["Boshqa", "Другое", "boshqa"]:
                needs_clarification.append(tx)
    
    if not needs_clarification:
        await query.edit_message_text(
            "✅ Barcha tranzaksiyalar aniq" if lang == "uz" else "✅ Все транзакции точны"
        )
        return
    
    # Ro'yxatni ko'rsatish
    if lang == "uz":
        msg = (
            "🔍 *QAYSI YOZUVNI ANIQLASHTIRISH KERAK?*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    else:
        msg = (
            "🔍 *КАКУЮ ЗАПИСЬ УТОЧНИТЬ?*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    keyboard = []
    for i, tx in enumerate(needs_clarification, 1):
        tx_type = "📥" if tx['type'] == 'income' else "📤"
        msg += f"{i}. {tx_type} *{tx['amount']:,}* - {tx.get('description', '')[:30]}\n"
        
        keyboard.append([InlineKeyboardButton(
            f"🔍 #{i} - {tx['amount']:,}",
            callback_data=f"ai_clarify_category_{tx['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
        callback_data="ai_cancel_correct"
    )])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_clarify_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kategoriyani aniqlashtirish uchun kategoriya ro'yxatini ko'rsatish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID from callback data: ai_clarify_category_123
    callback_data = query.data
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        await query.edit_message_text("Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка")
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        await query.edit_message_text(
            "❌ Tranzaksiya topilmadi" if lang == "uz" else "❌ Транзакция не найдена"
        )
        return
    
    # Kategoriyalar ro'yxati
    if transaction["type"] == "income":
        categories = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"])
    else:
        categories = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"])
    
    if lang == "uz":
        msg = (
            "🔍 *Kategoriyani tanlang*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Tavsif: _{transaction['description']}_\n"
            f"💰 Summa: *{transaction['amount']:,}* so'm\n\n"
            "_Qaysi kategoriyaga saqlash kerak?_"
        )
    else:
        msg = (
            "🔍 *Выберите категорию*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Описание: _{transaction['description']}_\n"
            f"💰 Сумма: *{transaction['amount']:,}* сум\n\n"
            "_В какую категорию сохранить?_"
        )
    
    # Kategoriyalar tugmalari (2 ta qatorda)
    keyboard = []
    cat_items = list(categories.items())
    
    for i in range(0, len(cat_items), 2):
        row = []
        for j in range(2):
            if i + j < len(cat_items):
                cat_key, cat_name = cat_items[i + j]
                row.append(InlineKeyboardButton(
                    cat_name,
                    callback_data=f"ai_set_category_{transaction_id}_{cat_key}"
                ))
        keyboard.append(row)
    
    # Bekor qilish tugmasi
    keyboard.append([InlineKeyboardButton(
        "◀️ Bekor qilish" if lang == "uz" else "◀️ Отмена",
        callback_data="ai_cancel_correct"
    )])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_set_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tanlangan kategoriyani saqlash va AI ga o'rgatish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID and category: ai_set_category_123_oziq_ovqat
    callback_data = query.data
    parts = callback_data.replace("ai_set_category_", "").split("_", 1)
    
    try:
        transaction_id = int(parts[0])
        new_category = parts[1] if len(parts) > 1 else "boshqa"
    except:
        await query.edit_message_text("Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка")
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES, learn_from_correction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        await query.edit_message_text(
            "❌ Tranzaksiya topilmadi" if lang == "uz" else "❌ Транзакция не найдена"
        )
        return
    
    old_category = transaction.get("category_key", "boshqa")
    
    # Yangi kategoriya nomini olish
    if transaction["type"] == "income":
        categories = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"])
    else:
        categories = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"])
    
    new_category_name = categories.get(new_category, "📦 Boshqa")
    
    # Database'da yangilash
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE transactions 
                    SET category = $1, category_key = $2
                    WHERE id = $3 AND user_id = $4
                """, new_category_name, new_category, transaction_id, user["id"])
        else:
            await db._connection.execute("""
                UPDATE transactions 
                SET category = ?, category_key = ?
                WHERE id = ? AND user_id = ?
            """, (new_category_name, new_category, transaction_id, user["id"]))
            await db._connection.commit()
        
        # AI ga o'rgatish - kategoriya tuzatilganda
        original_text = transaction.get("description", "")
        if original_text:
            wrong_result = {
                "type": transaction["type"],
                "category": old_category,
                "amount": transaction["amount"],
                "description": original_text
            }
            correct_result = {
                "type": transaction["type"],
                "category": new_category,
                "amount": transaction["amount"],
                "description": original_text
            }
            await learn_from_correction(original_text, wrong_result, correct_result)
        
        if lang == "uz":
            msg = (
                "✅ *Kategoriya yangilandi!*\n\n"
                f"📁 Yangi kategoriya: *{new_category_name}*\n\n"
                "_🧠 AI bu so'zni keyingi safar to'g'ri taniydi._"
            )
        else:
            msg = (
                "✅ *Категория обновлена!*\n\n"
                f"📁 Новая категория: *{new_category_name}*\n\n"
                "_🧠 AI запомнит это для следующих разов._"
            )
        
        await query.edit_message_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error updating category: {e}")
        await query.edit_message_text(
            "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка"
        )


async def ai_delete_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all transactions from multi-transaction"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction IDs
    callback_data = query.data
    try:
        ids_str = callback_data.replace("ai_delete_all_", "")
        transaction_ids = [int(x) for x in ids_str.split(",")]
    except:
        return
    
    from app.ai_assistant import delete_transaction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Delete all
    deleted = 0
    for tid in transaction_ids:
        result = await delete_transaction(db, tid, user["id"])
        if result:
            deleted += 1
    
    await query.edit_message_text(
        f"🗑 {deleted} ta yozuv o'chirildi" if lang == "uz" else f"🗑 Удалено {deleted} записей",
        parse_mode="Markdown"
    )


async def ai_correct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start transaction correction process - with Gemini re-analysis option"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID from callback data
    callback_data = query.data  # ai_correct_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        await query.edit_message_text("Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка")
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        await query.edit_message_text(
            "❌ Tranzaksiya topilmadi" if lang == "uz" else "❌ Транзакция не найдена"
        )
        return
    
    # Store correction info and original text for re-learning
    context.user_data["ai_correcting"] = transaction_id
    context.user_data["ai_correction_original"] = transaction.get("description", "")
    
    # Determine opposite type for swap button
    current_type = transaction['type']
    new_type = "expense" if current_type == "income" else "income"
    new_type_label = "Xarajat" if new_type == "expense" else "Daromad"
    new_type_label_ru = "Расход" if new_type == "expense" else "Доход"
    
    # Description uchun xavfsiz escape (Markdown maxsus belgilardan)
    description = transaction.get('description', '') or ''
    # Markdown maxsus belgilarni escape qilish
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        description = description.replace(char, '\\' + char)
    
    if lang == "uz":
        msg = (
            "✏️ *TUZATISH*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Joriy yozuv:\n"
            f"├ Turi: *{'Daromad' if transaction['type'] == 'income' else 'Xarajat'}*\n"
            f"├ Kategoriya: *{transaction['category']}*\n"
            f"├ Summa: *{transaction['amount']:,}* so'm\n"
            f"└ Tavsif: _{description}_\n\n"
            "🤖 _Noto'g'ri tahlil qildim. Qanday tuzatay?_"
        )
    else:
        msg = (
            "✏️ *ИСПРАВЛЕНИЕ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Текущая запись:\n"
            f"├ Тип: *{'Доход' if transaction['type'] == 'income' else 'Расход'}*\n"
            f"├ Категория: *{transaction['category']}*\n"
            f"├ Сумма: *{transaction['amount']:,}* сум\n"
            f"└ Описание: _{description}_\n\n"
            "🤖 _Неверный анализ. Как исправить?_"
        )
    
    keyboard = [
        # Gemini bilan qayta tahlil
        [InlineKeyboardButton(
            "🤖 Gemini bilan qayta tahlil" if lang == "uz" else "🤖 Повторный анализ Gemini",
            callback_data=f"ai_reanalyze_{transaction_id}"
        )],
        [InlineKeyboardButton(
            f"🔄 {new_type_label}ga o'zgartirish" if lang == "uz" else f"🔄 Сделать {new_type_label_ru.lower()}ом",
            callback_data=f"ai_swap_type_{transaction_id}_{new_type}"
        )],
        [InlineKeyboardButton(
            "📝 Kategoriyani o'zgartirish" if lang == "uz" else "📝 Изменить категорию",
            callback_data=f"ai_change_category_{transaction_id}"
        )],
        [InlineKeyboardButton(
            "✏️ Summani o'zgartirish" if lang == "uz" else "✏️ Изменить сумму",
            callback_data=f"ai_edit_amount_{transaction_id}"
        )],
        [InlineKeyboardButton(
            "🗑 O'chirish" if lang == "uz" else "🗑 Удалить",
            callback_data=f"ai_delete_{transaction_id}"
        )],
        [InlineKeyboardButton(
            "◀️ Bekor qilish" if lang == "uz" else "◀️ Отмена",
            callback_data="ai_cancel_correct"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_swap_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Swap transaction type (income <-> expense) and teach AI - XATOLARDAN O'RGANISH"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract data: ai_swap_type_123_expense
    callback_data = query.data
    parts = callback_data.split("_")
    try:
        transaction_id = int(parts[3])
        new_type = parts[4]  # "income" or "expense"
    except:
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES, learn_from_correction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        return
    
    old_type = transaction["type"]
    old_category = transaction.get("category_key", "boshqa")
    description = transaction.get("description", "")
    original_text = transaction.get("original_text", description)
    
    # Yangi kategoriya aniqlash
    if new_type == "expense":
        new_category = "oziq_ovqat"  # Default expense category
        # Kontekstdan aniqlash
        desc_lower = description.lower()
        if any(w in desc_lower for w in ['taksi', 'transport', 'yol', 'benzin']):
            new_category = "transport"
        elif any(w in desc_lower for w in ['non', 'ovqat', 'gosht', 'suv', 'yedim']):
            new_category = "oziq_ovqat"
        elif any(w in desc_lower for w in ['kiyim', 'koylak', 'shim']):
            new_category = "kiyim"
        elif any(w in desc_lower for w in ['dori', 'apteka']):
            new_category = "sog'liq"
        elif any(w in desc_lower for w in ['ijara', 'arenda', 'kvartira']):
            new_category = "uy_joy"
        elif any(w in desc_lower for w in ['qarz', 'nasiya']):
            new_category = "qarz_berdim"
        new_category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(new_category, "📦 Boshqa")
    else:
        new_category = "ish_haqi"  # Default income category
        desc_lower = description.lower()
        if any(w in desc_lower for w in ['sotdim', 'savdo', 'foyda']):
            new_category = "biznes"
        elif any(w in desc_lower for w in ['ijara', 'arenda']):
            new_category = "ijara_daromad"
        elif any(w in desc_lower for w in ['qarz', 'qaytardi']):
            new_category = "qarz_qaytarish"
        new_category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(new_category, "💼 Ish haqi")
    
    # ==================== XATOLARDAN O'RGANISH (KUCHLI!) ====================
    if original_text and (old_type != new_type or old_category != new_category):
        wrong_result = {
            "type": old_type,
            "category": old_category,
            "amount": transaction["amount"],
            "description": description
        }
        correct_result = {
            "type": new_type,
            "category": new_category,
            "amount": transaction["amount"],
            "description": description
        }
        # Bu juda muhim o'rganish - type o'zgarishi!
        await learn_from_correction(original_text, wrong_result, correct_result)
        print(f"[AI-LEARNING] 🧠 TIP O'ZGARISHIDAN O'RGANILDI: {old_type}/{old_category} -> {new_type}/{new_category}")
    
    # ==================== TRANZAKSIYANI YANGILASH ====================
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE transactions 
                    SET type = $1, category = $2, category_key = $3
                    WHERE id = $4 AND user_id = $5
                """, new_type, new_category_name, new_category, transaction_id, user["id"])
        else:
            await db._connection.execute("""
                UPDATE transactions 
                SET type = ?, category = ?, category_key = ?
                WHERE id = ? AND user_id = ?
            """, (new_type, new_category_name, new_category, transaction_id, user["id"]))
            await db._connection.commit()
    except Exception as e:
        print(f"[AI-CORRECT] Error updating transaction: {e}")
        await query.edit_message_text(
            "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка"
        )
        return
    
    context.user_data.pop("ai_correcting", None)
    
    if lang == "uz":
        msg = (
            "✅ *Tuzatildi va AI xatadan xulosa chiqardi!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔄 Turi o'zgartirildi:\n"
            f"├ {'📥 Daromad' if old_type == 'income' else '📤 Xarajat'} → "
            f"{'📥 Daromad' if new_type == 'income' else '📤 Xarajat'}\n"
            f"├ Kategoriya: *{new_category_name}*\n"
            f"└ Summa: *{transaction['amount']:,}* so'm\n\n"
            "🧠 _AI bu xatoni chuqur tahlil qildi va eslab qoldi!_\n"
            "_Keyingi safar xuddi shunday xabarni to'g'ri tahlil qiladi._"
        )
    else:
        msg = (
            "✅ *Исправлено! AI сделал выводы!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔄 Тип изменён:\n"
            f"├ {'📥 Доход' if old_type == 'income' else '📤 Расход'} → "
            f"{'📥 Доход' if new_type == 'income' else '📤 Расход'}\n"
            f"├ Категория: *{new_category_name}*\n"
            f"└ Сумма: *{transaction['amount']:,}* сум\n\n"
            "🧠 _AI глубоко проанализировал эту ошибку!_\n"
            "_В следующий раз подобное сообщение будет обработано правильно._"
        )
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_reanalyze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gemini bilan qayta tahlil qilish va AI'ni o'rgatish"""
    query = update.callback_query
    await query.answer("🤖 Gemini tahlil qilmoqda..." if context.user_data.get("lang") == "uz" else "🤖 Gemini анализирует...")
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_reanalyze_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        await query.edit_message_text("Xatolik" if lang == "uz" else "Ошибка")
        return
    
    from app.ai_assistant import (
        get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES,
        confirm_and_learn
    )
    from app.gemini_ai import analyze_with_gemini, is_gemini_available
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        return
    
    # Original description ni olish
    original_text = transaction.get("description", "") or context.user_data.get("ai_correction_original", "")
    
    if not original_text or not is_gemini_available():
        await query.edit_message_text(
            "❌ Gemini mavjud emas yoki matn topilmadi" if lang == "uz" else "❌ Gemini недоступен или текст не найден"
        )
        return
    
    # Gemini bilan qayta tahlil
    try:
        gemini_result = await analyze_with_gemini(original_text, lang)
        
        if not gemini_result:
            await query.edit_message_text(
                "❌ Gemini javob bermadi. Boshqa usulni tanlang." if lang == "uz" else "❌ Gemini не ответил. Выберите другой способ."
            )
            return
        
        new_type = gemini_result.get("type", "expense")
        new_category = gemini_result.get("category", "boshqa")
        new_amount = gemini_result.get("amount") or transaction["amount"]
        new_description = gemini_result.get("description", original_text)
        
        # Kategoriya nomini olish
        if new_type == "income":
            new_category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(new_category, "📦 Boshqa")
        else:
            new_category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(new_category, "📦 Boshqa")
        
        # Database'ni yangilash
        try:
            if db.is_postgres:
                async with db._pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE transactions 
                        SET type = $1, category = $2, category_key = $3, amount = $4, description = $5
                        WHERE id = $6 AND user_id = $7
                    """, new_type, new_category_name, new_category, new_amount, new_description, transaction_id, user["id"])
            else:
                await db._connection.execute("""
                    UPDATE transactions 
                    SET type = ?, category = ?, category_key = ?, amount = ?, description = ?
                    WHERE id = ? AND user_id = ?
                """, (new_type, new_category_name, new_category, new_amount, new_description, transaction_id, user["id"]))
                await db._connection.commit()
        except Exception as e:
            print(f"[AI-REANALYZE] DB error: {e}")
            await query.edit_message_text("❌ Xatolik" if lang == "uz" else "❌ Ошибка")
            return
        
        # AI'ga o'rgatish - Gemini natijasini to'g'ri deb belgilash
        await confirm_and_learn(original_text, {
            "type": new_type,
            "category": new_category,
            "amount": new_amount,
            "description": new_description
        })
        
        # Natijani ko'rsatish va tasdiqlash so'rash
        if lang == "uz":
            msg = (
                "🤖 *GEMINI QAYTA TAHLILI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 Yangi natija:\n"
                f"├ Turi: *{'📥 Daromad' if new_type == 'income' else '📤 Xarajat'}*\n"
                f"├ Kategoriya: *{new_category_name}*\n"
                f"├ Summa: *{new_amount:,}* so'm\n"
                f"└ Tavsif: _{new_description}_\n\n"
                "✅ _Yangilandi va AI o'rgandi!_"
            )
        else:
            msg = (
                "🤖 *ПОВТОРНЫЙ АНАЛИЗ GEMINI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 Новый результат:\n"
                f"├ Тип: *{'📥 Доход' if new_type == 'income' else '📤 Расход'}*\n"
                f"├ Категория: *{new_category_name}*\n"
                f"├ Сумма: *{new_amount:,}* сум\n"
                f"└ Описание: _{new_description}_\n\n"
                "✅ _Обновлено и AI обучился!_"
            )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ To'g'ri" if lang == "uz" else "✅ Верно", callback_data="ai_confirm_ok"),
                InlineKeyboardButton("❌ Yana noto'g'ri" if lang == "uz" else "❌ Всё ещё неверно", callback_data=f"ai_correct_{transaction_id}")
            ]
        ]
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        print(f"[AI-REANALYZE] Error: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка"
        )


async def ai_change_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kategoriyani o'zgartirish - kategoriyalar ro'yxatini ko'rsatish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_change_category_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        return
    
    # Turi bo'yicha kategoriyalarni ko'rsatish
    tx_type = transaction["type"]
    
    if tx_type == "income":
        categories = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"])
    else:
        categories = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"])
    
    if lang == "uz":
        msg = (
            "📂 *KATEGORIYA TANLANG*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Joriy: *{transaction['category']}*\n\n"
            "Yangi kategoriya:"
        )
    else:
        msg = (
            "📂 *ВЫБЕРИТЕ КАТЕГОРИЮ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Текущая: *{transaction['category']}*\n\n"
            "Новая категория:"
        )
    
    keyboard = []
    for cat_key, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(
            cat_name,
            callback_data=f"ai_set_category_{transaction_id}_{cat_key}"
        )])
    
    # Yangi kategoriya yaratish tugmasi
    keyboard.append([InlineKeyboardButton(
        "➕ Yangi kategoriya" if lang == "uz" else "➕ Новая категория",
        callback_data=f"ai_new_category_{transaction_id}"
    )])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
        callback_data=f"ai_correct_{transaction_id}"
    )])
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def ai_new_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yangi kategoriya yaratish - foydalanuvchi o'zi nom beradi"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_new_category_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        return
    
    # Yangi kategoriya kiritish so'rovi
    context.user_data["awaiting_new_category"] = True
    context.user_data["new_category_transaction_id"] = transaction_id
    
    if lang == "uz":
        msg = (
            "➕ *YANGI KATEGORIYA*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Yangi kategoriya nomini kiriting:\n"
            "_Masalan: 🎮 O'yinlar, 🐱 Uy hayvonlari_\n\n"
            "⚠️ Bekor qilish uchun /cancel"
        )
    else:
        msg = (
            "➕ *НОВАЯ КАТЕГОРИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Введите название новой категории:\n"
            "_Например: 🎮 Игры, 🐱 Домашние животные_\n\n"
            "⚠️ Для отмены /cancel"
        )
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_set_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tanlangan kategoriyani o'rnatish va AI'ga o'rgatish - XATOLARDAN O'RGANISH"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract data: ai_set_category_123_oziq_ovqat
    callback_data = query.data
    parts = callback_data.split("_")
    try:
        transaction_id = int(parts[3])
        new_category = "_".join(parts[4:])  # kategoriya nomi bo'sh joy bilan bo'lishi mumkin
    except:
        return
    
    from app.ai_assistant import get_transaction_by_id, EXPENSE_CATEGORIES, INCOME_CATEGORIES, confirm_and_learn, learn_from_correction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    transaction = await get_transaction_by_id(db, transaction_id)
    
    if not transaction or transaction["user_id"] != user["id"]:
        return
    
    tx_type = transaction["type"]
    old_category = transaction.get("category_key") or transaction.get("category", "boshqa")
    
    # Kategoriya nomini olish
    if tx_type == "income":
        new_category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(new_category, "📦 Boshqa")
    else:
        new_category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(new_category, "📦 Boshqa")
    
    # Database'ni yangilash
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE transactions 
                    SET category = $1, category_key = $2
                    WHERE id = $3 AND user_id = $4
                """, new_category_name, new_category, transaction_id, user["id"])
        else:
            await db._connection.execute("""
                UPDATE transactions 
                SET category = ?, category_key = ?
                WHERE id = ? AND user_id = ?
            """, (new_category_name, new_category, transaction_id, user["id"]))
            await db._connection.commit()
    except Exception as e:
        print(f"[AI-SET-CATEGORY] DB error: {e}")
        await query.edit_message_text("❌ Xatolik" if lang == "uz" else "❌ Ошибка")
        return
    
    # AI'ga o'rgatish - XATOLARDAN O'RGANISH
    original_text = transaction.get("description", "") or context.user_data.get("ai_correction_original", "")
    
    if original_text and old_category != new_category:
        # Kategoriya o'zgargan - XATADAN O'RGANISH!
        wrong_result = {
            "type": tx_type,
            "category": old_category,
            "amount": transaction["amount"],
            "description": transaction.get("description", "")
        }
        correct_result = {
            "type": tx_type,
            "category": new_category,
            "amount": transaction["amount"],
            "description": transaction.get("description", "")
        }
        # Xatadan o'rganish
        await learn_from_correction(original_text, wrong_result, correct_result)
    elif original_text:
        # Oddiy tasdiqlash
        await confirm_and_learn(original_text, {
            "type": tx_type,
            "category": new_category,
            "amount": transaction["amount"],
            "description": transaction.get("description", "")
        })
    
    if lang == "uz":
        msg = (
            "✅ *KATEGORIYA O'ZGARTIRILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📂 Yangi kategoriya: *{new_category_name}*\n"
            f"💰 Summa: *{transaction['amount']:,}* so'm\n\n"
            "🧠 _AI bu xatadan xulosa chiqardi va o'rgandi!_"
        )
    else:
        msg = (
            "✅ *КАТЕГОРИЯ ИЗМЕНЕНА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📂 Новая категория: *{new_category_name}*\n"
            f"💰 Сумма: *{transaction['amount']:,}* сум\n\n"
            "🧠 _AI сделал выводы из этой ошибки и запомнил!_"
        )
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a transaction"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_delete_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        return
    
    from app.ai_assistant import delete_transaction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    await delete_transaction(db, transaction_id, user["id"])
    context.user_data.pop("ai_correcting", None)
    
    if lang == "uz":
        msg = "🗑 *Yozuv o'chirildi*\n\nYangi yozuv qo'shish uchun ovozli yoki matnli xabar yuboring."
    else:
        msg = "🗑 *Запись удалена*\n\nОтправьте голосовое или текстовое сообщение для новой записи."
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_rewrite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rewrite a transaction - delete old and prompt for new"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_rewrite_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        return
    
    from app.ai_assistant import delete_transaction
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    await delete_transaction(db, transaction_id, user["id"])
    context.user_data.pop("ai_correcting", None)
    
    if lang == "uz":
        msg = (
            "🔄 *QAYTA YOZISH*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Eski yozuv o'chirildi.\n\n"
            "🎤 Ovozli xabar yoki\n"
            "✍️ Matnli xabar yuboring.\n\n"
            "Masalan: \"Ovqatga 50 ming berdim\""
        )
    else:
        msg = (
            "🔄 *ПЕРЕЗАПИСЬ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Старая запись удалена.\n\n"
            "🎤 Отправьте голосовое или\n"
            "✍️ текстовое сообщение.\n\n"
            "Например: \"На еду потратил 50 тысяч\""
        )
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_edit_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit transaction amount"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract transaction ID
    callback_data = query.data  # ai_edit_amount_123
    try:
        transaction_id = int(callback_data.split("_")[-1])
    except:
        return
    
    context.user_data["ai_editing_amount"] = transaction_id
    
    if lang == "uz":
        msg = (
            "✏️ *SUMMANI O'ZGARTIRISH*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Yangi summani yozing:\n\n"
            "Masalan: `50000` yoki `ellik ming`"
        )
    else:
        msg = (
            "✏️ *ИЗМЕНИТЬ СУММУ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Напишите новую сумму:\n\n"
            "Например: `50000` или `пятьдесят тысяч`"
        )
    
    keyboard = [[InlineKeyboardButton(
        "◀️ Bekor qilish" if lang == "uz" else "◀️ Отмена",
        callback_data="ai_cancel_correct"
    )]]
    
    await query.edit_message_text(
        msg, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_amount_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle new amount input"""
    if not context.user_data.get("ai_editing_amount"):
        return
    
    transaction_id = context.user_data["ai_editing_amount"]
    text = update.message.text.strip()
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    from app.ai_assistant import extract_amount, update_transaction, get_budget_status, format_budget_warning
    
    # Parse amount
    new_amount = extract_amount(text)
    
    if not new_amount:
        await update.message.reply_text(
            "❌ Summani aniqlab bo'lmadi. Qaytadan kiriting." if lang == "uz" else
            "❌ Не удалось определить сумму. Попробуйте ещё раз.",
            parse_mode="Markdown"
        )
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Update transaction
    await update_transaction(db, transaction_id, user["id"], amount=new_amount)
    
    # Clear editing mode
    context.user_data.pop("ai_editing_amount", None)
    context.user_data.pop("ai_correcting", None)
    
    # Get updated budget status
    budget_status = await get_budget_status(db, user["id"])
    budget_msg = format_budget_warning(budget_status, lang) or ""
    
    if lang == "uz":
        msg = f"✅ *Summa yangilandi: {new_amount:,} so'm*\n\n{budget_msg}"
    else:
        msg = f"✅ *Сумма обновлена: {new_amount:,} сум*\n\n{budget_msg}"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def ai_cancel_correct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel correction process"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    # Clear correction modes
    context.user_data.pop("ai_correcting", None)
    context.user_data.pop("ai_editing_amount", None)
    
    if lang == "uz":
        msg = "↩️ Bekor qilindi"
    else:
        msg = "↩️ Отменено"
    
    await query.edit_message_text(msg, parse_mode="Markdown")


async def ai_budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed budget status"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import get_budget_status, format_budget_warning, get_voice_usage, MONTHLY_VOICE_LIMIT
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    budget_status = await get_budget_status(db, user["id"])
    voice_usage = await get_voice_usage(db, user["id"])
    
    if budget_status["status"] == "no_data":
        if lang == "uz":
            msg = (
                "💰 *BYUDJET*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📝 Byudjetni hisoblash uchun avval daromad va xarajatlaringizni kiriting.\n\n"
                "📊 *Hisoblash* tugmasini bosing."
            )
        else:
            msg = (
                "💰 *БЮДЖЕТ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📝 Для расчёта бюджета сначала введите свои доходы и расходы.\n\n"
                "📊 Нажмите кнопку *Расчёт*."
            )
    else:
        msg = format_budget_warning(budget_status, lang)
        
        # Add detailed breakdown
        budget_info = budget_status.get("budget_info", {})
        if budget_info.get("has_data"):
            if lang == "uz":
                msg += (
                    f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 *TAQSIMLASH:*\n"
                    f"├ 💰 Daromad: *{budget_info['total_income']:,.0f}* so'm\n"
                    f"├ 📌 Majburiy: *{budget_info['mandatory_expenses']:,.0f}* so'm\n"
                    f"├ 💵 Bo'sh pul: *{budget_info['free_cash']:,.0f}* so'm\n"
                    f"├ 🏦 Boylik (10%): *{budget_info['savings_budget']:,.0f}* so'm\n"
                    f"├ ⚡ Qarz (20%): *{budget_info['extra_debt_budget']:,.0f}* so'm\n"
                    f"└ 🏠 Yashash (70%): *{budget_info['living_budget']:,.0f}* so'm"
                )
            else:
                msg += (
                    f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 *РАСПРЕДЕЛЕНИЕ:*\n"
                    f"├ 💰 Доход: *{budget_info['total_income']:,.0f}* сум\n"
                    f"├ 📌 Обязательные: *{budget_info['mandatory_expenses']:,.0f}* сум\n"
                    f"├ 💵 Свободные: *{budget_info['free_cash']:,.0f}* сум\n"
                    f"├ 🏦 Богатство (10%): *{budget_info['savings_budget']:,.0f}* сум\n"
                    f"├ ⚡ Долг (20%): *{budget_info['extra_debt_budget']:,.0f}* сум\n"
                    f"└ 🏠 Жизнь (70%): *{budget_info['living_budget']:,.0f}* сум"
                )
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 Xarajatlar" if lang == "uz" else "📊 Расходы",
            callback_data="ai_report"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI transaction report with real balance"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import (
        get_transaction_summary, format_transaction_summary, 
        get_budget_status, get_user_real_balance, format_real_balance_message
    )
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    # Get real balance (including debts)
    balance_data = await get_user_real_balance(db, user["id"])
    
    # Get summary for last 30 days
    summary = await get_transaction_summary(db, user["id"], days=30)
    
    if summary["total_income"] == 0 and summary["total_expense"] == 0:
        if lang == "uz":
            msg = (
                "📊 *MOLIYAVIY HISOBOT*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📭 Hali hech qanday yozuv yo'q.\n\n"
                "🎤 Ovozli xabar yuboring:\n"
                "\"Bugun ovqatga 50 ming berdim\"\n"
                "\"Maosh tushdi 5 million\""
            )
        else:
            msg = (
                "📊 *ФИНАНСОВЫЙ ОТЧЁТ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📭 Записей пока нет.\n\n"
                "🎤 Отправьте голосовое сообщение:\n"
                "\"Сегодня на еду потратил 50 тысяч\"\n"
                "\"Получил зарплату 5 миллионов\""
            )
    else:
        msg = format_transaction_summary(summary, lang)
        # Append real balance info
        msg += "\n\n" + format_real_balance_message(balance_data, lang)
    
    keyboard = [
        [InlineKeyboardButton(
            "📋 Oxirgi yozuvlar" if lang == "uz" else "📋 Последние записи",
            callback_data="ai_recent"
        )],
        [InlineKeyboardButton(
            "💰 Haqiqiy balans" if lang == "uz" else "💰 Реальный баланс",
            callback_data="ai_real_balance"
        )],
        [InlineKeyboardButton(
            "🎤 Yangi yozuv" if lang == "uz" else "🎤 Новая запись",
            callback_data="ai_assistant"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_real_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's real balance including debts"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import get_user_real_balance, format_real_balance_message
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    # Get real balance
    balance_data = await get_user_real_balance(db, user["id"])
    msg = format_real_balance_message(balance_data, lang)
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 To'liq hisobot" if lang == "uz" else "📊 Полный отчёт",
            callback_data="ai_report"
        )],
        [InlineKeyboardButton(
            "💳 Qarzlarim" if lang == "uz" else "💳 Мои долги",
            callback_data="ai_debt_list"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="ai_assistant"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_recent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent AI transactions"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import get_user_transactions, EXPENSE_CATEGORIES, INCOME_CATEGORIES
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        await query.edit_message_text("Ma'lumot topilmadi" if lang == "uz" else "Данные не найдены")
        return
    
    # Get last 10 transactions
    transactions = await get_user_transactions(db, user["id"], days=30)
    transactions = transactions[:10]  # Limit to 10
    
    if not transactions:
        if lang == "uz":
            msg = (
                "📋 *OXIRGI YOZUVLAR*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📭 Hali hech qanday yozuv yo'q."
            )
        else:
            msg = (
                "📋 *ПОСЛЕДНИЕ ЗАПИСИ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📭 Записей пока нет."
            )
    else:
        if lang == "uz":
            msg = "📋 *OXIRGI YOZUVLAR*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        else:
            msg = "📋 *ПОСЛЕДНИЕ ЗАПИСИ*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for t in transactions:
            type_emoji = "💰" if t["type"] == "income" else "💸"
            if t["type"] == "income":
                cat_name = INCOME_CATEGORIES[lang].get(t["category"], "📦 Boshqa")
            else:
                cat_name = EXPENSE_CATEGORIES[lang].get(t["category"], "📦 Boshqa")
            
            date_str = t["created_at"][:10] if t["created_at"] else ""
            msg += f"{type_emoji} {cat_name}: *{t['amount']:,}* so'm\n"
            msg += f"   _{t['description']}_ ({date_str})\n\n"
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 Hisobot" if lang == "uz" else "📊 Отчёт",
            callback_data="ai_report"
        )],
        [InlineKeyboardButton(
            "🎤 Yangi yozuv" if lang == "uz" else "🎤 Новая запись",
            callback_data="ai_assistant"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================== QARZ HANDLERS ====================

async def ai_debt_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of user's debts"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import get_user_debts, get_debt_summary
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    debts = await get_user_debts(db, user["id"], status="active")
    summary = await get_debt_summary(db, user["id"])
    
    if lang == "uz":
        msg = (
            "📋 *QARZLAR RO'YXATI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if not debts:
            msg += "📭 Hech qanday faol qarz yo'q.\n"
        else:
            # Bergan qarzlar
            lent_debts = [d for d in debts if d["debt_type"] == "lent"]
            if lent_debts:
                msg += "📤 *BERGAN QARZLAR:*\n"
                for d in lent_debts:
                    remaining = d["amount"] - d["returned_amount"]
                    due = f" (qaytarish: {d['due_date']})" if d["due_date"] else ""
                    msg += f"├ {d['person_name']}: *{remaining:,.0f}* so'm{due}\n"
                msg += "\n"
            
            # Olgan qarzlar
            borrowed_debts = [d for d in debts if d["debt_type"] == "borrowed"]
            if borrowed_debts:
                msg += "📥 *OLGAN QARZLAR:*\n"
                for d in borrowed_debts:
                    remaining = d["amount"] - d["returned_amount"]
                    due = f" (qaytarish: {d['due_date']})" if d["due_date"] else ""
                    msg += f"├ {d['person_name']}: *{remaining:,.0f}* so'm{due}\n"
                msg += "\n"
        
        msg += (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 Bergan jami: *{summary['total_lent']:,}* so'm\n"
            f"📥 Olgan jami: *{summary['total_borrowed']:,}* so'm\n"
        )
        
        net = summary['net_balance']
        if net > 0:
            msg += f"💚 Sof balans: *+{net:,}* so'm"
        elif net < 0:
            msg += f"🔴 Sof balans: *{net:,}* so'm"
        else:
            msg += f"⚪ Sof balans: *0* so'm"
    else:
        msg = (
            "📋 *СПИСОК ДОЛГОВ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if not debts:
            msg += "📭 Нет активных долгов.\n"
        else:
            lent_debts = [d for d in debts if d["debt_type"] == "lent"]
            if lent_debts:
                msg += "📤 *ДАЛ В ДОЛГ:*\n"
                for d in lent_debts:
                    remaining = d["amount"] - d["returned_amount"]
                    due = f" (возврат: {d['due_date']})" if d["due_date"] else ""
                    msg += f"├ {d['person_name']}: *{remaining:,.0f}* сум{due}\n"
                msg += "\n"
            
            borrowed_debts = [d for d in debts if d["debt_type"] == "borrowed"]
            if borrowed_debts:
                msg += "📥 *ВЗЯЛ В ДОЛГ:*\n"
                for d in borrowed_debts:
                    remaining = d["amount"] - d["returned_amount"]
                    due = f" (возврат: {d['due_date']})" if d["due_date"] else ""
                    msg += f"├ {d['person_name']}: *{remaining:,.0f}* сум{due}\n"
                msg += "\n"
        
        msg += (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 Всего дал: *{summary['total_lent']:,}* сум\n"
            f"📥 Всего взял: *{summary['total_borrowed']:,}* сум\n"
        )
        
        net = summary['net_balance']
        if net > 0:
            msg += f"💚 Чистый баланс: *+{net:,}* сум"
        elif net < 0:
            msg += f"🔴 Чистый баланс: *{net:,}* сум"
        else:
            msg += f"⚪ Чистый баланс: *0* сум"
    
    keyboard = [
        [InlineKeyboardButton(
            "✅ Qarz qaytarildi" if lang == "uz" else "✅ Долг возвращён",
            callback_data="ai_debt_mark_returned"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_debt_mark_returned_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show debts that can be marked as returned"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    from app.ai_assistant import get_user_debts
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    debts = await get_user_debts(db, user["id"], status="active")
    
    if not debts:
        if lang == "uz":
            msg = "📭 Faol qarzlar yo'q"
        else:
            msg = "📭 Нет активных долгов"
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    
    if lang == "uz":
        msg = (
            "✅ *QARZ QAYTARILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Qaysi qarz qaytarilganini tanlang:"
        )
    else:
        msg = (
            "✅ *ДОЛГ ВОЗВРАЩЁН*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Выберите возвращённый долг:"
        )
    
    keyboard = []
    for d in debts[:10]:  # Limit to 10
        type_emoji = "📤" if d["debt_type"] == "lent" else "📥"
        remaining = d["amount"] - d["returned_amount"]
        btn_text = f"{type_emoji} {d['person_name']}: {remaining:,.0f}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ai_debt_return_{d['id']}")])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
        callback_data="ai_debt_list"
    )])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_debt_return_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark a specific debt as returned"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract debt ID
    callback_data = query.data  # ai_debt_return_123
    try:
        debt_id = int(callback_data.split("_")[-1])
    except:
        return
    
    from app.ai_assistant import update_debt_status, get_debt_summary, format_debt_summary_message
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Get debt info first
    if db.is_postgres:
        debt = await db.fetch_one(
            "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, user["id"]
        )
    else:
        cursor = await db._connection.execute(
            "SELECT * FROM personal_debts WHERE id = ? AND user_id = ?",
            (debt_id, user["id"])
        )
        debt = await cursor.fetchone()
        debt = dict(debt) if debt else None
    
    if not debt:
        return
    
    # Mark as returned (full amount)
    await update_debt_status(db, debt_id, user["id"], "returned", debt["amount"])
    
    # Get updated summary
    summary = await get_debt_summary(db, user["id"])
    
    if lang == "uz":
        type_text = "Bergan qarz" if debt["debt_type"] == "lent" else "Olgan qarz"
        msg = (
            f"✅ *{type_text} qaytarildi!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 {debt['person_name']}\n"
            f"💵 {debt['amount']:,.0f} so'm\n\n"
        )
    else:
        type_text = "Данный долг" if debt["debt_type"] == "lent" else "Взятый долг"
        msg = (
            f"✅ *{type_text} возвращён!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 {debt['person_name']}\n"
            f"💵 {debt['amount']:,.0f} сум\n\n"
        )
    
    msg += format_debt_summary_message(summary, lang)
    
    keyboard = [
        [InlineKeyboardButton(
            "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
            callback_data="ai_debt_list"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="back_to_main"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_debt_correct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Correct a debt entry"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract debt ID
    callback_data = query.data  # ai_debt_correct_123
    try:
        debt_id = int(callback_data.split("_")[-1])
    except:
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Get debt info
    if db.is_postgres:
        debt = await db.fetch_one(
            "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, user["id"]
        )
    else:
        cursor = await db._connection.execute(
            "SELECT * FROM personal_debts WHERE id = ? AND user_id = ?",
            (debt_id, user["id"])
        )
        debt = await cursor.fetchone()
        debt = dict(debt) if debt else None
    
    if not debt:
        await query.edit_message_text(
            "❌ Qarz topilmadi" if lang == "uz" else "❌ Долг не найден"
        )
        return
    
    if lang == "uz":
        type_text = "Bergan qarz" if debt["debt_type"] == "lent" else "Olgan qarz"
        msg = (
            f"✏️ *QARZNI TUZATISH*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Joriy yozuv:\n"
            f"├ Turi: *{type_text}*\n"
            f"├ Kim: *{debt['person_name']}*\n"
            f"├ Summa: *{debt['amount']:,.0f}* so'm\n"
            f"└ Sana: *{debt['given_date']}*\n\n"
            "Quyidagilardan birini tanlang:"
        )
    else:
        type_text = "Дал в долг" if debt["debt_type"] == "lent" else "Взял в долг"
        msg = (
            f"✏️ *ИСПРАВИТЬ ДОЛГ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Текущая запись:\n"
            f"├ Тип: *{type_text}*\n"
            f"├ Кто: *{debt['person_name']}*\n"
            f"├ Сумма: *{debt['amount']:,.0f}* сум\n"
            f"└ Дата: *{debt['given_date']}*\n\n"
            "Выберите действие:"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "🗑 O'chirish" if lang == "uz" else "🗑 Удалить",
            callback_data=f"ai_debt_delete_{debt_id}"
        )],
        [InlineKeyboardButton(
            "◀️ Bekor qilish" if lang == "uz" else "◀️ Отмена",
            callback_data="ai_confirm_ok"
        )]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ai_debt_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a debt entry"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract debt ID
    callback_data = query.data  # ai_debt_delete_123
    try:
        debt_id = int(callback_data.split("_")[-1])
    except:
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Delete debt
    if db.is_postgres:
        await db.execute_update(
            "DELETE FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, user["id"]
        )
    else:
        await db._connection.execute(
            "DELETE FROM personal_debts WHERE id = ? AND user_id = ?",
            (debt_id, user["id"])
        )
        await db._connection.commit()
    
    if lang == "uz":
        msg = "🗑 *Qarz yozuvi o'chirildi*"
    else:
        msg = "🗑 *Запись о долге удалена*"
    
    await query.edit_message_text(msg, parse_mode="Markdown")


# ==================== ADMIN COMMAND ====================

async def admin_activate_pro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /activate command - manually activate PRO for a user
    Usage: /activate <telegram_id> <plan_id>
    Example: /activate 123456789 pro_monthly
    """
    telegram_id = update.effective_user.id
    
    # Faqat adminlar uchun
    if telegram_id not in ADMIN_IDS:
        return
    
    # Parse arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ *Xato format!*\n\n"
            "✅ To'g'ri format:\n"
            "`/activate <telegram_id> <plan_id>`\n\n"
            "📋 *Mavjud tariflar:*\n"
            "├ `pro_weekly` - Haftalik (7 kun)\n"
            "├ `pro_monthly` - Oylik (30 kun)\n"
            "├ `pro_quarterly` - 3 oylik (90 kun)\n"
            "└ `pro_yearly` - Yillik (365 kun)\n\n"
            "📌 *Misol:*\n"
            "`/activate 123456789 pro_monthly`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        plan_id = context.args[1].lower()
        
        # Validate plan_id
        valid_plans = ['pro_weekly', 'pro_monthly', 'pro_quarterly', 'pro_yearly']
        if plan_id not in valid_plans:
            await update.message.reply_text(
                f"❌ Noto'g'ri tarif: `{plan_id}`\n\n"
                f"✅ Mavjud tariflar: {', '.join(valid_plans)}",
                parse_mode="Markdown"
            )
            return
        
        await update.message.reply_text("⏳ PRO aktivatsiya qilinmoqda...")
        
        # Import and call manual activation
        from app.payment_webhook import verify_payment_manually
        
        result = await verify_payment_manually(target_user_id, plan_id)
        
        if result:
            await update.message.reply_text(
                f"✅ *PRO muvaffaqiyatli aktivlashtirildi!*\n\n"
                f"👤 Foydalanuvchi: `{target_user_id}`\n"
                f"📦 Tarif: `{plan_id}`\n\n"
                f"ℹ️ Foydalanuvchiga xabar yuborildi.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ *Aktivatsiya muvaffaqiyatsiz!*\n\n"
                f"Foydalanuvchi topilmadi yoki xatolik yuz berdi.\n"
                f"Telegram ID: `{target_user_id}`",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Telegram ID raqam bo'lishi kerak!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin activate error: {e}")
        await update.message.reply_text(f"❌ Xatolik: {e}")


async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /payments command - show recent payments
    Usage: /payments [limit]
    """
    telegram_id = update.effective_user.id
    
    if telegram_id not in ADMIN_IDS:
        return
    
    try:
        limit = int(context.args[0]) if context.args else 10
        limit = min(limit, 50)  # Max 50 payments
        
        db = await get_database()
        
        if db.is_postgres:
            payments = await db.fetch_all(
                """SELECT p.*, u.telegram_id, u.first_name 
                   FROM payments p 
                   JOIN users u ON p.user_id = u.id 
                   ORDER BY p.created_at DESC LIMIT $1""",
                limit
            )
        else:
            payments = await db.fetch_all(
                """SELECT p.*, u.telegram_id, u.first_name 
                   FROM payments p 
                   JOIN users u ON p.user_id = u.id 
                   ORDER BY p.created_at DESC LIMIT ?""",
                limit
            )
        
        if not payments:
            await update.message.reply_text("📋 Hech qanday to'lov topilmadi.")
            return
        
        message = "📋 *SO'NGI TO'LOVLAR*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for p in payments:
            status_emoji = {'completed': '✅', 'pending': '⏳', 'failed': '❌'}.get(p.get('status'), '❓')
            message += (
                f"{status_emoji} *{p.get('first_name', 'N/A')}* (`{p.get('telegram_id')}`)\n"
                f"   📦 {p.get('plan_id')} | 💰 {p.get('amount_uzs'):,} so'm\n"
                f"   📅 {p.get('created_at')}\n\n"
            )
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Admin payments error: {e}")
        await update.message.reply_text(f"❌ Xatolik: {e}")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command - show admin panel with statistics"""
    telegram_id = update.effective_user.id
    
    logger.info(f"Admin command received from user {telegram_id}")
    
    # Faqat adminlar uchun
    if telegram_id not in ADMIN_IDS:
        logger.info(f"User {telegram_id} is not admin, ignoring")
        return
    
    logger.info(f"User {telegram_id} is admin, showing panel...")
    
    await update.message.reply_text("⏳ Admin panel yuklanmoqda...")
    
    # Admin panel asosiy menyusini ko'rsatish
    await show_admin_main_menu(update, context)


async def show_admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    """Admin panel asosiy menyusi"""
    
    message = (
        "🎛 *HALOS ADMIN PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔐 Xush kelibsiz, Admin!\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton("💎 PRO hisoboti", callback_data="admin_pro_report")
        ],
        [
            InlineKeyboardButton("💰 Kotib.ai balans", callback_data="admin_kotib_balance"),
            InlineKeyboardButton("💳 To'lovlar", callback_data="admin_payments_list")
        ],
        [
            InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users"),
            InlineKeyboardButton("📈 Faollik", callback_data="admin_activity")
        ],
        [
            InlineKeyboardButton("🎁 TRIAL barchaga", callback_data="admin_trial_all"),
            InlineKeyboardButton("📤 Broadcast", callback_data="admin_broadcast")
        ],
        # Yangi admin funksiyalar
        [
            InlineKeyboardButton("🗑️ User o'chirish", callback_data="admin_delete_user"),
            InlineKeyboardButton("🧹 TX tozalash", callback_data="admin_clear_user_tx")
        ],
        [
            InlineKeyboardButton("⚠️ BARCHA TX o'chirish", callback_data="admin_clear_all_tx"),
            InlineKeyboardButton("👥 Userlar", callback_data="admin_list_users")
        ],
        [
            InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")
        ]
    ]
    
    if edit:
        await update.callback_query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin panel callbacks"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    
    # Faqat adminlar uchun
    if telegram_id not in ADMIN_IDS:
        return
    
    # ==================== ASOSIY MENYU ====================
    if query.data == "admin_main":
        await show_admin_main_menu(update, context, edit=True)
        return
    
    # ==================== STATISTIKA ====================
    if query.data == "admin_stats":
        db = await get_database()
        stats = await db.get_admin_statistics()
        
        # O'sish foizini hisoblash
        total = stats.get("total_users", 0)
        week = stats.get("week_users", 0)
        growth = round((week / max(total - week, 1)) * 100, 1) if total > 0 else 0
        
        message = (
            "📊 *UMUMIY STATISTIKA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "👥 *FOYDALANUVCHILAR*\n"
            f"┌ 📈 Jami: *{stats.get('total_users', 0):,}* ta\n"
            f"├ 🆕 Bugun: *+{stats.get('today_users', 0):,}* ta\n"
            f"├ 📅 Haftalik: *+{stats.get('week_users', 0):,}* ta\n"
            f"├ 📆 Oylik: *+{stats.get('month_users', 0):,}* ta\n"
            f"└ 📊 O'sish: *{growth}%* (haftalik)\n\n"
            
            "📈 *FAOLLIK*\n"
            f"┌ 💬 Jami tranzaksiyalar: *{stats.get('total_transactions', 0):,}*\n"
            f"├ ⚡ Bugungi: *{stats.get('today_transactions', 0):,}*\n"
            f"├ 🤝 Aktiv qarzlar: *{stats.get('active_debts', 0):,}*\n"
            f"└ 💵 Qarzlar summasi: *{int(stats.get('total_debt_amount', 0)):,}* so'm\n\n"
            
            "🌐 *TILLAR*\n"
        )
        
        langs = stats.get("languages", {})
        for i, (lang, count) in enumerate(langs.items()):
            prefix = "└" if i == len(langs) - 1 else "├"
            flag = "🇺🇿" if lang == "uz" else "🇷🇺"
            message += f"{prefix} {flag} {lang.upper()}: *{count:,}* ta\n"
        
        message += f"\n⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_stats")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== PRO HISOBOTI ====================
    if query.data == "admin_pro_report":
        db = await get_database()
        stats = await db.get_admin_statistics()
        
        active_pro = stats.get("active_pro", 0)
        total = stats.get("total_users", 0)
        pro_percent = round((active_pro / max(total, 1)) * 100, 1)
        
        # PRO daromad hisoblash (taxminiy)
        weekly_count = stats.get("pro_weekly", 0)
        monthly_count = stats.get("pro_monthly", 0)
        yearly_count = stats.get("pro_yearly", 0)
        
        # Narxlar (so'mda)
        weekly_price = 14900
        monthly_price = 29900
        yearly_price = 199000
        
        total_revenue = (weekly_count * weekly_price) + (monthly_count * monthly_price) + (yearly_count * yearly_price)
        
        message = (
            "💎 *PRO OBUNALAR HISOBOTI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"📊 *UMUMIY*\n"
            f"┌ ✅ Aktiv PRO: *{active_pro:,}* ta\n"
            f"├ 📈 Konversiya: *{pro_percent}%*\n"
            f"└ ❌ Muddati tugagan: *{stats.get('pro_expired', 0):,}* ta\n\n"
            
            "📦 *REJALAR BO'YICHA*\n"
            f"┌ 📅 Haftalik: *{weekly_count:,}* ta\n"
            f"├ 📆 Oylik: *{monthly_count:,}* ta\n"
            f"├ 📅 Yillik: *{yearly_count:,}* ta\n"
            f"├ 🎁 Promo: *{stats.get('pro_promo', 0):,}* ta\n"
            f"└ 🆓 Trial: *{stats.get('pro_trial', 0):,}* ta\n\n"
            
            f"💰 *DAROMAD (taxminiy)*\n"
            f"└ 💵 Jami: *{total_revenue:,}* so'm\n\n"
            
            f"⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_pro_report")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== KOTIB.AI BALANS ====================
    if query.data == "admin_kotib_balance":
        from app.ai_assistant import get_kotib_balance
        
        balance_info = await get_kotib_balance()
        
        if balance_info and balance_info.get("status") == "success":
            balance = balance_info.get("balance", 0)
            duration = balance_info.get("duration", "N/A")
            translation = balance_info.get("translation", "N/A")
            
            # Status aniqlash
            if balance > 100000:
                status_emoji = "🟢"
                status_text = "Yaxshi"
            elif balance > 50000:
                status_emoji = "🟡"
                status_text = "O'rtacha"
            elif balance > 10000:
                status_emoji = "🟠"
                status_text = "Kam"
            else:
                status_emoji = "🔴"
                status_text = "KRITIK!"
            
            message = (
                "💰 *KOTIB.AI BALANS*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"{status_emoji} *Status:* {status_text}\n\n"
                
                f"💵 *Balans:* *{balance:,}*\n"
                f"🎙 *Audio:* {duration}\n"
                f"📝 *Tarjima:* {translation}\n\n"
                
                "📊 *TAXMINIY ISHLATISH*\n"
                f"┌ 🎙 1 ovozli xabar: ~100-200 kredit\n"
                f"├ 📈 Qolgan xabarlar: ~*{int(balance / 150):,}* ta\n"
                f"└ 📅 Taxminan: ~*{int(balance / 150 / 50)}* kun\n\n"
                
                "⚠️ _Balans kamaysa @HalosPaybot ga ogohlantirish yuboriladi_\n\n"
                
                f"⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
            )
        else:
            message = (
                "💰 *KOTIB.AI BALANS*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                "❌ *Balansni olishda xatolik!*\n\n"
                "_API bilan bog'lanishda muammo yoki_\n"
                "_API kaliti noto'g'ri._\n\n"
                
                f"⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
            )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_kotib_balance")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== TO'LOVLAR RO'YXATI ====================
    if query.data == "admin_payments_list":
        db = await get_database()
        
        try:
            if db.is_postgres:
                async with db._pool.acquire() as conn:
                    payments = await conn.fetch("""
                        SELECT p.*, u.telegram_id as user_tid, u.first_name 
                        FROM payments p 
                        JOIN users u ON p.user_id = u.id 
                        ORDER BY p.created_at DESC 
                        LIMIT 15
                    """)
            else:
                async with db._connection.execute("""
                    SELECT p.*, u.telegram_id as user_tid, u.first_name 
                    FROM payments p 
                    JOIN users u ON p.user_id = u.id 
                    ORDER BY p.created_at DESC 
                    LIMIT 15
                """) as cursor:
                    payments = await cursor.fetchall()
            
            message = (
                "💳 *SO'NGI TO'LOVLAR*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            if payments:
                for p in payments:
                    p = dict(p)
                    status_emoji = {
                        'completed': '✅', 
                        'pending': '⏳', 
                        'failed': '❌'
                    }.get(p.get('status'), '❓')
                    
                    amount = p.get('amount_uzs', 0) or 0
                    created = p.get('created_at', '')
                    if hasattr(created, 'strftime'):
                        created = created.strftime('%d.%m %H:%M')
                    else:
                        created = str(created)[:10]
                    
                    message += (
                        f"{status_emoji} *{p.get('first_name', 'N/A')}*\n"
                        f"   📦 {p.get('plan_id', '-')} | 💰 {amount:,} so'm\n"
                        f"   📅 {created}\n\n"
                    )
            else:
                message += "📭 _Hech qanday to'lov topilmadi_\n"
            
            message += f"⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
            
        except Exception as e:
            logger.error(f"Admin payments list error: {e}")
            message = f"❌ Xatolik: {e}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_payments_list")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== FOYDALANUVCHILAR ====================
    if query.data == "admin_users":
        db = await get_database()
        
        try:
            if db.is_postgres:
                async with db._pool.acquire() as conn:
                    # So'nggi 10 ta yangi foydalanuvchi
                    users = await conn.fetch("""
                        SELECT telegram_id, first_name, username, subscription_tier, created_at
                        FROM users 
                        ORDER BY created_at DESC 
                        LIMIT 10
                    """)
            else:
                async with db._connection.execute("""
                    SELECT telegram_id, first_name, username, subscription_tier, created_at
                    FROM users 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """) as cursor:
                    users = await cursor.fetchall()
            
            message = (
                "👥 *SO'NGI FOYDALANUVCHILAR*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            for u in users:
                u = dict(u)
                tier = u.get('subscription_tier', 'free')
                tier_emoji = "💎" if tier == 'pro' else "🆓"
                username = u.get('username', '')
                username_str = f"@{username}" if username else "-"
                
                created = u.get('created_at', '')
                if hasattr(created, 'strftime'):
                    created = created.strftime('%d.%m.%Y')
                else:
                    created = str(created)[:10]
                
                message += (
                    f"{tier_emoji} *{u.get('first_name', 'N/A')}*\n"
                    f"   👤 {username_str} | 📅 {created}\n\n"
                )
            
            message += f"⏰ _Yangilangan: {now_uz().strftime('%H:%M:%S')}_"
            
        except Exception as e:
            logger.error(f"Admin users error: {e}")
            message = f"❌ Xatolik: {e}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_users")],
            [InlineKeyboardButton("🔍 ID bo'yicha qidirish", callback_data="admin_search_user")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== FAOLLIK ====================
    if query.data == "admin_activity":
        db = await get_database()
        
        try:
            if db.is_postgres:
                async with db._pool.acquire() as conn:
                    # Bugungi faollik
                    today_stats = await conn.fetchrow("""
                        SELECT 
                            (SELECT COUNT(*) FROM transactions WHERE DATE(created_at) = CURRENT_DATE) as today_tx,
                            (SELECT COUNT(*) FROM personal_debts WHERE DATE(created_at) = CURRENT_DATE) as today_debts,
                            (SELECT COUNT(*) FROM voice_usage WHERE month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')) as voice_users
                    """)
                    
                    # Ovozli xabarlar
                    voice_total = await conn.fetchrow("""
                        SELECT COALESCE(SUM(voice_count), 0) as total FROM voice_usage
                    """)
            else:
                today_stats = {"today_tx": 0, "today_debts": 0, "voice_users": 0}
                voice_total = {"total": 0}
            
            ts = dict(today_stats) if today_stats else {}
            vt = dict(voice_total) if voice_total else {}
            
            message = (
                "📈 *FAOLLIK HISOBOTI*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                "⚡ *BUGUNGI FAOLLIK*\n"
                f"┌ 💬 Tranzaksiyalar: *{ts.get('today_tx', 0):,}*\n"
                f"├ 🤝 Yangi qarzlar: *{ts.get('today_debts', 0):,}*\n"
                f"└ 🎙 Ovoz ishlatganlar: *{ts.get('voice_users', 0):,}* ta\n\n"
                
                "🎙 *OVOZLI YORDAMCHI*\n"
                f"└ 📊 Jami ovozli xabarlar: *{vt.get('total', 0):,}*\n\n"
                
                f"⏰ _Yangilangan: {datetime.now().strftime('%H:%M:%S')}_"
            )
            
        except Exception as e:
            logger.error(f"Admin activity error: {e}")
            message = f"❌ Xatolik: {e}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_activity")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== ESLATMA YUBORISH ====================
    if query.data == "admin_send_reminders":
        from app.scheduler import get_debts_due_today, get_debts_due_soon
        
        db = await get_database()
        
        # Bugungi qarzlar
        today_debts = await get_debts_due_today(db)
        # Yaqinlashayotgan qarzlar (3 kun)
        upcoming_debts = await get_debts_due_soon(db, days=3)
        
        message = (
            "🔔 *QARZ ESLATMALARI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"📅 *Bugungi qarzlar:* {len(today_debts)} ta\n"
            f"⏰ *Yaqinlashayotgan (3 kun):* {len(upcoming_debts)} ta\n\n"
        )
        
        if today_debts:
            message += "*Bugungi qarzlar:*\n"
            for d in today_debts[:5]:
                d = dict(d)
                message += f"├ {d.get('person_name')}: {d.get('amount'):,.0f} so'm\n"
            if len(today_debts) > 5:
                message += f"└ _...va yana {len(today_debts) - 5} ta_\n"
            message += "\n"
        
        message += "Eslatmalarni hozir yuborish uchun tugmani bosing:"
        
        keyboard = [
            [InlineKeyboardButton("🔔 Hozir yuborish", callback_data="admin_trigger_reminders")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== ESLATMALARNI TRIGGER QILISH ====================
    if query.data == "admin_trigger_reminders":
        from app.scheduler import get_debts_due_today, get_scheduler
        
        await query.edit_message_text(
            "⏳ Eslatmalar yuborilmoqda...",
            parse_mode="Markdown"
        )
        
        db = await get_database()
        today_debts = await get_debts_due_today(db)
        
        sent_count = 0
        failed_count = 0
        
        for debt in today_debts:
            try:
                debt = dict(debt)
                lang = debt.get("language", "uz")
                person = debt.get("person_name", "Noma'lum")
                amount = debt.get("amount", 0)
                debt_type = debt.get("debt_type")
                debt_id = debt.get("id")
                description = debt.get("description", "")
                
                # Valyuta formatlash
                currency = debt.get("currency", "UZS")
                if currency == "USD":
                    amount_str = f"${amount:,.0f}"
                elif currency == "RUB":
                    amount_str = f"₽{amount:,.0f}"
                else:
                    amount_str = f"{amount:,.0f} so'm"
                
                if lang == "uz":
                    if debt_type == "lent":
                        msg = (
                            "🔔 *BUGUN QARZ QAYTISH KUNI!*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"👤 *{person}* sizga qarz qaytarishi kerak\n\n"
                            f"💰 Summa: *{amount_str}*\n"
                            f"📅 Sana: *Bugun*\n"
                        )
                    else:
                        msg = (
                            "⚠️ *BUGUN QARZ QAYTARISH KUNI!*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"👤 *{person}*ga qarz qaytarishingiz kerak\n\n"
                            f"💰 Summa: *{amount_str}*\n"
                            f"📅 Sana: *Bugun*\n"
                        )
                else:
                    if debt_type == "lent":
                        msg = (
                            "🔔 *СЕГОДНЯ ДЕНЬ ВОЗВРАТА ДОЛГА!*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"👤 *{person}* должен вернуть вам долг\n\n"
                            f"💰 Сумма: *{amount_str}*\n"
                            f"📅 Дата: *Сегодня*\n"
                        )
                    else:
                        msg = (
                            "⚠️ *СЕГОДНЯ ДЕНЬ ВОЗВРАТА ДОЛГА!*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"👤 Вы должны вернуть долг *{person}*\n\n"
                            f"💰 Сумма: *{amount_str}*\n"
                            f"📅 Дата: *Сегодня*\n"
                        )
                
                if description:
                    if lang == "uz":
                        msg += f"📝 Izoh: _{description}_\n"
                    else:
                        msg += f"📝 Заметка: _{description}_\n"
                
                msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                if lang == "uz":
                    msg += "💡 _Qarz qaytarilsa, tugmani bosing_"
                else:
                    msg += "💡 _Нажмите кнопку когда долг вернут_"
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ Qaytarildi" if lang == "uz" else "✅ Возвращён",
                            callback_data=f"debt_reminder_returned:{debt_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⏰ Ertaga eslatish" if lang == "uz" else "⏰ Напомнить завтра",
                            callback_data=f"debt_reminder_snooze:{debt_id}"
                        ),
                        InlineKeyboardButton(
                            "📋 Qarzlar" if lang == "uz" else "📋 Долги",
                            callback_data="ai_debt_list"
                        )
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=debt["telegram_id"],
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                sent_count += 1
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error sending reminder: {e}")
                failed_count += 1
        
        result_message = (
            "✅ *ESLATMALAR YUBORILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Yuborildi: *{sent_count}* ta\n"
            f"❌ Xato: *{failed_count}* ta\n\n"
            f"⏰ _{now_uz().strftime('%H:%M:%S')}_"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            result_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== SOZLAMALAR ====================
    if query.data == "admin_settings":
        message = (
            "⚙️ *ADMIN SOZLAMALARI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "🔔 *Ogohlantirish chegaralari:*\n"
            "├ 🟡 50,000 so'm - O'rtacha\n"
            "├ 🟠 20,000 so'm - Kam\n"
            "└ 🔴 10,000 so'm - Kritik\n\n"
            
            "📤 *Ogohlantirish yuboriladi:*\n"
            "└ @HalosPaybot\n\n"
            
            "_Sozlamalarni o'zgartirish hozircha mavjud emas_"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== TRIAL BARCHAGA ====================
    if query.data == "admin_trial_all":
        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, boshlayman", callback_data="admin_trial_confirm"),
                InlineKeyboardButton("❌ Yo'q", callback_data="admin_main")
            ]
        ]
        
        await query.edit_message_text(
            "🎁 *3 KUNLIK TRIAL YOQISH*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ Bu amalni bajarsangiz:\n\n"
            "• Barcha foydalanuvchilarga 3 kunlik\n"
            "  TRIAL PRO obuna beriladi\n"
            "• 10 ta ovozli xabar limiti\n"
            "• 10 soniya audio limiti\n"
            "• Barcha PRO funksiyalar ochiladi\n\n"
            "📢 Keyin broadcast xabar yuborishingiz mumkin\n\n"
            "*Davom etasizmi?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if query.data == "admin_trial_confirm":
        await query.edit_message_text(
            "⏳ *TRIAL yoqilmoqda...*\n\n"
            "Iltimos kuting...",
            parse_mode="Markdown"
        )
        
        # Trial yoqish
        from app.subscription import TRIAL_CONFIG
        from datetime import datetime, timedelta
        
        trial_end_date = (datetime.now() + timedelta(days=TRIAL_CONFIG["duration_days"])).strftime("%Y-%m-%d")
        
        # Barcha foydalanuvchilarni olish
        users = db.get_all_users_for_broadcast()
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for user in users:
            try:
                user_id = user.get("id") or user.get("telegram_id")
                if not user_id:
                    continue
                
                # Foydalanuvchi ma'lumotlarini olish
                user_data = await db.get_user(user_id)
                
                if not user_data:
                    continue
                
                # Agar PRO obunasi bo'lsa yoki trial ishlatgan bo'lsa - o'tkazib yuborish
                current_tier = user_data.get("subscription_tier", "free")
                trial_used = user_data.get("trial_used", 0)
                
                if current_tier == "pro":
                    skip_count += 1
                    continue
                
                if trial_used == 1:
                    skip_count += 1
                    continue
                
                # Trial yoqish
                await db.update_user(
                    user_id,
                    subscription_tier="trial",
                    subscription_expires=trial_end_date,
                    voice_tier="trial",
                    trial_used=1
                )
                success_count += 1
                
            except Exception as e:
                logger.error(f"Trial yoqishda xato (user {user_id}): {e}")
                error_count += 1
        
        keyboard = [
            [InlineKeyboardButton("📤 Broadcast yuborish", callback_data="admin_trial_broadcast")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            "🎁 *TRIAL YOQILDI!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Muvaffaqiyatli: *{success_count}* ta\n"
            f"⏭ O'tkazib yuborildi: *{skip_count}* ta\n"
            f"❌ Xatolik: *{error_count}* ta\n\n"
            f"📅 Trial tugash sanasi: *{trial_end_date}*\n\n"
            "📢 Endi foydalanuvchilarga xabar yuborasizmi?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if query.data == "admin_trial_broadcast":
        # Trial haqida tayyor xabar
        trial_message = (
            "🎁 *SIZGA SOVG'A!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Hurmatli foydalanuvchi!\n\n"
            "Sizga *3 kunlik BEPUL PRO* obuna taqdim etildi! 🎉\n\n"
            "✨ *Sizda ochilgan imkoniyatlar:*\n"
            "• 🎤 10 ta ovozli xabar\n"
            "• ⏱ 10 soniyagacha audio\n"
            "• 📊 Hisobotlar va statistika\n"
            "• 💳 Cheksiz kategoriyalar\n"
            "• 📈 Export va arxiv\n\n"
            "⏰ *Muddati:* 3 kun\n\n"
            "💡 _Bu imkoniyatlarni sinab ko'ring va\n"
            "moliyangizni oson boshqaring!_\n\n"
            "PRO sotib olish: /pro"
        )
        
        context.user_data["admin_trial_broadcast_message"] = trial_message
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yuborish", callback_data="admin_trial_broadcast_send"),
                InlineKeyboardButton("✏️ Tahrirlash", callback_data="admin_trial_broadcast_edit")
            ],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            "📤 *TRIAL XABARI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Quyidagi xabar yuboriladi:\n\n"
            "─────────────────────\n"
            f"{trial_message}\n"
            "─────────────────────\n\n"
            "*Yuborishni tasdiqlaysizmi?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if query.data == "admin_trial_broadcast_edit":
        context.user_data["admin_trial_broadcast_editing"] = True
        
        keyboard = [
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            "✏️ *XABARNI TAHRIRLASH*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Yangi xabar matnini yozing:\n\n"
            "💡 _Markdown formatlash qo'llab-quvvatlanadi_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if query.data == "admin_trial_broadcast_send":
        trial_message = context.user_data.get("admin_trial_broadcast_message", "")
        if not trial_message:
            await query.answer("❌ Xabar topilmadi!", show_alert=True)
            return
        
        await query.edit_message_text(
            "📤 *XABAR YUBORILMOQDA...*\n\n"
            "⏳ Iltimos kuting...",
            parse_mode="Markdown"
        )
        
        # Barcha foydalanuvchilarga yuborish
        users = db.get_all_users_for_broadcast()
        
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                user_id = user.get("id") or user.get("telegram_id")
                if not user_id:
                    continue
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=trial_message,
                    parse_mode="Markdown"
                )
                success_count += 1
                
                # Rate limit uchun
                await asyncio.sleep(0.05)
                
            except Exception as e:
                error_count += 1
        
        keyboard = [
            [InlineKeyboardButton("◀️ Admin panel", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            "✅ *XABAR YUBORILDI!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📤 Yuborildi: *{success_count}* ta\n"
            f"❌ Xatolik: *{error_count}* ta",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== BROADCAST ====================
    if query.data == "admin_broadcast":
        context.user_data["admin_broadcast"] = True
        
        keyboard = [
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_main")]
        ]
        
        await query.edit_message_text(
            "📤 *XABAR YUBORISH*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Barcha foydalanuvchilarga yuboriladigan\n"
            "xabarni yozing yoki media yuboring:\n\n"
            "✅ Matn\n"
            "✅ 📷 Rasm + matn (caption)\n"
            "✅ 🎬 Video + matn (caption)\n"
            "✅ 📄 Fayl + matn (caption)\n\n"
            "💡 _Markdown formatlash qo'llab-quvvatlanadi_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== FOYDALANUVCHI QIDIRISH ====================
    if query.data == "admin_search_user":
        context.user_data["admin_search_user"] = True
        
        keyboard = [
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_users")]
        ]
        
        await query.edit_message_text(
            "🔍 *FOYDALANUVCHI QIDIRISH*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Telegram ID ni kiriting:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ==================== YANGI ADMIN AMALLAR ====================
    
    # User o'chirish
    if query.data == "admin_delete_user":
        return await admin_delete_user_start(update, context)
    
    # User tranzaksiyalarini tozalash
    if query.data == "admin_clear_user_tx":
        return await admin_clear_user_tx_start(update, context)
    
    # Barcha tranzaksiyalarni o'chirish
    if query.data == "admin_clear_all_tx":
        return await admin_clear_all_tx_confirm(update, context)
    
    # Barcha tranzaksiyalarni o'chirishni tasdiqlash
    if query.data == "admin_confirm_clear_all":
        return await admin_confirm_clear_all(update, context)
    
    # Userlar ro'yxati
    if query.data == "admin_list_users":
        return await admin_list_users(update, context)
    
    # User o'chirishni tasdiqlash
    if query.data.startswith("admin_confirm_delete:"):
        return await admin_confirm_delete_user(update, context)
    
    # User tranzaksiyalarini tozalashni tasdiqlash
    if query.data.startswith("admin_confirm_clear_tx:"):
        return await admin_confirm_clear_tx(update, context)
    
    # Orqaga qaytish
    if query.data == "admin_back":
        return await admin_back(update, context)
    
    # Yopish
    if query.data == "admin_close":
        return await admin_close(update, context)
    
    # Legacy support
    if query.data == "admin_refresh":
        # admin_stats ga yo'naltirish
        query.data = "admin_stats"
        await admin_callback(update, context)
        return


async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send broadcast message to all users - supports text, photo, video, document, forward"""
    telegram_id = update.effective_user.id
    
    if telegram_id not in ADMIN_IDS:
        return
    
    if not context.user_data.get("admin_broadcast"):
        return
    
    context.user_data["admin_broadcast"] = False
    
    message = update.message
    
    # Check for cancel command
    if message.text and message.text == "/cancel":
        await message.reply_text("❌ Broadcast bekor qilindi")
        return
    
    db = await get_database()
    
    # Barcha foydalanuvchilarni olish
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            rows = await conn.fetch("SELECT telegram_id FROM users")
            users = [row["telegram_id"] for row in rows]
    else:
        cursor = await db._connection.execute("SELECT telegram_id FROM users")
        rows = await cursor.fetchall()
        users = [row[0] for row in rows]
    
    # Check if message is forwarded - use forward method
    is_forwarded = message.forward_date is not None
    
    # Determine message type
    has_photo = message.photo and len(message.photo) > 0
    has_video = message.video is not None
    has_document = message.document is not None
    has_text = message.text is not None
    caption = message.caption or ""
    
    if is_forwarded:
        media_type = "forward"
        await message.reply_text(f"📤 ↗️ Forward xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")
    elif has_photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
        await message.reply_text(f"📤 📷 Rasm {len(users)} ta foydalanuvchiga yuborilmoqda...")
    elif has_video:
        media_type = "video"
        file_id = message.video.file_id
        await message.reply_text(f"📤 🎬 Video {len(users)} ta foydalanuvchiga yuborilmoqda...")
    elif has_document:
        media_type = "document"
        file_id = message.document.file_id
        await message.reply_text(f"📤 📄 Fayl {len(users)} ta foydalanuvchiga yuborilmoqda...")
    elif has_text:
        media_type = "text"
        file_id = None
        broadcast_text = message.text
        await message.reply_text(f"📤 Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")
    else:
        await message.reply_text("❌ Noto'g'ri format. Matn, rasm, video yoki fayl yuboring.")
        return
    
    success = 0
    failed = 0
    errors_log = []
    
    for user_id in users:
        try:
            if media_type == "forward":
                # Forward the original message
                await message.forward(chat_id=user_id)
            elif media_type == "photo":
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=caption if caption else None
                )
            elif media_type == "video":
                await context.bot.send_video(
                    chat_id=user_id,
                    video=file_id,
                    caption=caption if caption else None
                )
            elif media_type == "document":
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=caption if caption else None
                )
            else:
                # Text only - no prefix, no markdown parsing to avoid errors
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text
                )
            success += 1
        except Exception as e:
            failed += 1
            if len(errors_log) < 3:
                errors_log.append(f"{user_id}: {str(e)[:50]}")
        
        # Rate limiting
        if (success + failed) % 30 == 0:
            await asyncio.sleep(1)
    
    result_msg = f"✅ Broadcast yakunlandi!\n\n✅ Yuborildi: {success} ta\n❌ Xato: {failed} ta"
    
    if errors_log:
        result_msg += f"\n\n🔍 Xato namunalari:\n" + "\n".join(errors_log)
    
    await message.reply_text(result_msg)


# ==================== DEBT REMINDER HANDLERS ====================

async def debt_reminder_returned_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for debt reminder "Qaytarildi" button
    Marks debt as returned from reminder notification
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract debt ID from callback: debt_reminder_returned:123
    try:
        debt_id = int(query.data.split(":")[1])
    except:
        return
    
    from app.ai_assistant import update_debt_status, get_debt_summary, format_debt_summary_message
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Get debt info
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            debt = await conn.fetchrow(
                "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
                debt_id, user["id"]
            )
    else:
        async with db._connection.execute(
            "SELECT * FROM personal_debts WHERE id = ? AND user_id = ?",
            (debt_id, user["id"])
        ) as cursor:
            debt = await cursor.fetchone()
    
    if not debt:
        if lang == "uz":
            msg = "❌ Qarz topilmadi"
        else:
            msg = "❌ Долг не найден"
        await query.edit_message_text(msg)
        return
    
    debt = dict(debt)
    
    # Mark as returned (full amount)
    remaining = debt["amount"] - debt["returned_amount"]
    
    # Update debt status
    success = await update_debt_status(
        db, 
        debt_id=debt_id, 
        user_id=user["id"],
        returned_amount=debt["amount"],  # Full amount
        status="returned"
    )
    
    if success:
        person = debt["person_name"]
        
        # Valyuta formatlash
        currency = debt.get("currency", "UZS")
        if currency == "USD":
            amount_str = f"${remaining:,.0f}"
        elif currency == "RUB":
            amount_str = f"₽{remaining:,.0f}"
        else:
            amount_str = f"{remaining:,.0f} so'm"
        
        if lang == "uz":
            msg = (
                "✅ *QARZ QAYTARILDI!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 *{person}*\n"
                f"💰 Summa: *{amount_str}*\n\n"
                "📊 Qarz holati yangilandi!"
            )
        else:
            msg = (
                "✅ *ДОЛГ ВОЗВРАЩЁН!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 *{person}*\n"
                f"💰 Сумма: *{amount_str}*\n\n"
                "📊 Статус долга обновлён!"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
                callback_data="ai_debt_list"
            )]
        ])
        
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        if lang == "uz":
            msg = "❌ Xatolik yuz berdi"
        else:
            msg = "❌ Произошла ошибка"
        await query.edit_message_text(msg)


async def debt_reminder_snooze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for debt reminder "Ertaga eslatish" button
    Extends due date by 1 day
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Extract debt ID from callback: debt_reminder_snooze:123
    try:
        debt_id = int(query.data.split(":")[1])
    except:
        return
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
    # Update due date to tomorrow (Tashkent time)
    tomorrow = (now_uz() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            await conn.execute(
                "UPDATE personal_debts SET due_date = $1, updated_at = NOW() WHERE id = $2 AND user_id = $3",
                tomorrow, debt_id, user["id"]
            )
    else:
        await db._connection.execute(
            "UPDATE personal_debts SET due_date = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (tomorrow, datetime.now().isoformat(), debt_id, user["id"])
        )
        await db._connection.commit()
    
    # Format tomorrow date nicely (Tashkent time)
    tomorrow_dt = now_uz() + timedelta(days=1)
    day_num = tomorrow_dt.day
    months_uz = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 
                'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']
    months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    
    if lang == "uz":
        date_str = f"{day_num}-{months_uz[tomorrow_dt.month - 1]}"
        msg = (
            "⏰ *ESLATMA KECHIKTIRILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Yangi sana: *{date_str}*\n\n"
            "Ertaga soat 6:00 da yana eslatamiz!"
        )
    else:
        date_str = f"{day_num} {months_ru[tomorrow_dt.month - 1]}"
        msg = (
            "⏰ *НАПОМИНАНИЕ ОТЛОЖЕНО*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Новая дата: *{date_str}*\n\n"
            "Напомним завтра в 6:00!"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
            callback_data="ai_debt_list"
        )]
    ])
    
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ==================== ADMIN USER MANAGEMENT ====================

async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User o'chirish - telegram_id so'rash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    context.user_data["admin_action"] = "delete_user"
    
    await query.edit_message_text(
        "🗑️ *USER O'CHIRISH*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Bu amal foydalanuvchini va uning BARCHA ma'lumotlarini o'chiradi!\n\n"
        "📝 O'chirmoqchi bo'lgan user telegram ID sini yuboring:\n\n"
        "_Bekor qilish uchun /cancel_",
        parse_mode="Markdown"
    )
    
    return States.ADMIN_INPUT


async def admin_clear_user_tx_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User tranzaksiyalarini tozalash - telegram_id so'rash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    context.user_data["admin_action"] = "clear_user_tx"
    
    await query.edit_message_text(
        "🧹 *USER TRANZAKSIYALARINI TOZALASH*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Bu amal foydalanuvchining BARCHA kirim-chiqimlarini o'chiradi!\n"
        "User o'zi o'chirilmaydi.\n\n"
        "📝 Tozalamoqchi bo'lgan user telegram ID sini yuboring:\n\n"
        "_Bekor qilish uchun /cancel_",
        parse_mode="Markdown"
    )
    
    return States.ADMIN_INPUT


async def admin_clear_all_tx_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: BARCHA tranzaksiyalarni o'chirish - tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    context.user_data["admin_action"] = "clear_all_tx"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ HA, BARCHASINI O'CHIR", callback_data="admin_confirm_clear_all")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_close")],
    ])
    
    await query.edit_message_text(
        "⚠️ *OGOHLANTIRISH!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚨 Bu amal BARCHA foydalanuvchilarning\n"
        "BARCHA kirim-chiqim ma'lumotlarini o'chiradi!\n\n"
        "❗ Bu amalni qaytarib bo'lmaydi!\n\n"
        "Davom etasizmi?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    return ConversationHandler.END


async def admin_confirm_clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: BARCHA tranzaksiyalarni o'chirishni tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    db = await get_database()
    result = await db.admin_clear_all_transactions()
    
    if result["success"]:
        await query.edit_message_text(
            "✅ *BARCHA TRANZAKSIYALAR O'CHIRILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🗑️ O'chirilgan tranzaksiyalar: *{result['deleted_count']}* ta",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ Xatolik: {result.get('error', 'Noma\'lum xato')}",
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def admin_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User input qabul qilish (telegram_id)"""
    telegram_id = update.effective_user.id
    
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    text = update.message.text.strip()
    action = context.user_data.get("admin_action")
    
    # Telegram ID ni tekshirish
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format!\n\n"
            "Faqat raqam kiriting (telegram_id).\n"
            "Masalan: `1748575975`",
            parse_mode="Markdown"
        )
        return States.ADMIN_INPUT
    
    db = await get_database()
    
    # User mavjudligini tekshirish
    user_info = await db.admin_get_user_info(target_id)
    
    if not user_info:
        await update.message.reply_text(
            f"❌ User topilmadi: `{target_id}`\n\n"
            "Telegram ID ni tekshiring.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # User ma'lumotlarini ko'rsatish
    username = user_info.get("username") or "Yo'q"
    first_name = user_info.get("first_name") or "Yo'q"
    phone = user_info.get("phone_number") or "Yo'q"
    tx_count = user_info.get("transaction_count", 0)
    debt_count = user_info.get("debt_count", 0)
    total_income = user_info.get("total_income", 0)
    total_expense = user_info.get("total_expense", 0)
    sub_tier = user_info.get("subscription_tier", "free")
    
    user_summary = (
        f"👤 *User ma'lumotlari:*\n"
        f"├ ID: `{target_id}`\n"
        f"├ Username: @{username}\n"
        f"├ Ism: {first_name}\n"
        f"├ Telefon: {phone}\n"
        f"├ Tarif: {sub_tier}\n"
        f"├ Tranzaksiyalar: {tx_count} ta\n"
        f"├ Qarzlar: {debt_count} ta\n"
        f"├ Jami kirim: {total_income:,.0f}\n"
        f"└ Jami chiqim: {total_expense:,.0f}\n"
    )
    
    if action == "delete_user":
        context.user_data["target_user_id"] = target_id
        context.user_data["target_user_info"] = user_info
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ HA, O'CHIR", callback_data=f"admin_confirm_delete:{target_id}")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_close")],
        ])
        
        await update.message.reply_text(
            f"🗑️ *USER O'CHIRILADI*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{user_summary}\n"
            f"⚠️ Bu user va uning BARCHA ma'lumotlari o'chiriladi!\n"
            f"Davom etasizmi?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    elif action == "clear_user_tx":
        context.user_data["target_user_id"] = target_id
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ HA, TOZALA", callback_data=f"admin_confirm_clear_tx:{target_id}")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_close")],
        ])
        
        await update.message.reply_text(
            f"🧹 *TRANZAKSIYALAR TOZALANADI*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{user_summary}\n"
            f"⚠️ Bu userning BARCHA kirim-chiqimlari o'chiriladi!\n"
            f"Davom etasizmi?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    return ConversationHandler.END


async def admin_confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User o'chirishni tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    # callback_data: admin_confirm_delete:1748575975
    target_id = int(query.data.split(":")[1])
    
    db = await get_database()
    result = await db.admin_delete_user(target_id)
    
    if result["success"]:
        user_info = result.get("user_info", {})
        await query.edit_message_text(
            "✅ *USER O'CHIRILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User: `{target_id}` (@{user_info.get('username', 'N/A')})\n\n"
            f"📊 *O'chirilgan ma'lumotlar:*\n"
            f"├ Tranzaksiyalar: {result['transactions_deleted']} ta\n"
            f"├ Qarzlar: {result['debts_deleted']} ta\n"
            f"├ Voice usage: {result['voice_usage_deleted']} ta\n"
            f"├ Feature usage: {result['feature_usage_deleted']} ta\n"
            f"└ Financial profile: {'✅' if result['financial_profile_deleted'] else '❌'}\n",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ *Xatolik:* {result.get('error', 'Noma\'lum xato')}",
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def admin_confirm_clear_tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User tranzaksiyalarini tozalashni tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    # callback_data: admin_confirm_clear_tx:1748575975
    target_id = int(query.data.split(":")[1])
    
    db = await get_database()
    result = await db.admin_clear_all_transactions(target_id)
    
    if result["success"]:
        await query.edit_message_text(
            "✅ *TRANZAKSIYALAR TOZALANDI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User: `{target_id}`\n"
            f"🗑️ O'chirilgan tranzaksiyalar: *{result['deleted_count']}* ta",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ *Xatolik:* {result.get('error', 'Noma\'lum xato')}",
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: Statistika ko'rsatish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    db = await get_database()
    stats = await db.get_admin_statistics()
    
    msg = (
        "📊 *ADMIN STATISTIKA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Foydalanuvchilar:*\n"
        f"├ Jami: {stats.get('total_users', 0)}\n"
        f"├ Bugun: +{stats.get('today_users', 0)}\n"
        f"├ Hafta: +{stats.get('week_users', 0)}\n"
        f"└ Oy: +{stats.get('month_users', 0)}\n\n"
        f"💎 *PRO obunalar:*\n"
        f"├ Aktiv PRO: {stats.get('active_pro', 0)}\n"
        f"├ Haftalik: {stats.get('pro_weekly', 0)}\n"
        f"├ Oylik: {stats.get('pro_monthly', 0)}\n"
        f"├ Yillik: {stats.get('pro_yearly', 0)}\n"
        f"├ Promo: {stats.get('pro_promo', 0)}\n"
        f"├ Trial: {stats.get('pro_trial', 0)}\n"
        f"└ Muddati tugagan: {stats.get('pro_expired', 0)}\n\n"
        f"💰 *Tranzaksiyalar:*\n"
        f"├ Jami: {stats.get('total_transactions', 0)}\n"
        f"└ Bugun: +{stats.get('today_transactions', 0)}\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back")],
    ])
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    
    return ConversationHandler.END


async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: Userlar ro'yxati"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    db = await get_database()
    users = await db.admin_list_users(limit=20)
    
    msg = "👥 *SO'NGI 20 TA USER*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, user in enumerate(users, 1):
        username = user.get("username") or "N/A"
        first_name = user.get("first_name") or "N/A"
        tier = "💎" if user.get("subscription_tier") == "pro" else "🆓"
        tx_count = user.get("tx_count", 0)
        
        msg += f"{i}. {tier} `{user['telegram_id']}` @{username} ({tx_count} tx)\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back")],
    ])
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    
    return ConversationHandler.END


async def admin_search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: User qidirish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    context.user_data["admin_action"] = "search_user"
    
    await query.edit_message_text(
        "🔍 *USER QIDIRISH*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 User telegram ID sini yuboring:\n\n"
        "_Bekor qilish uchun /cancel_",
        parse_mode="Markdown"
    )
    
    return States.ADMIN_INPUT


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: Orqaga qaytish"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        return ConversationHandler.END
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ User o'chirish", callback_data="admin_delete_user")],
        [InlineKeyboardButton("🧹 User tranzaksiyalarini tozalash", callback_data="admin_clear_user_tx")],
        [InlineKeyboardButton("⚠️ BARCHA tranzaksiyalarni o'chirish", callback_data="admin_clear_all_tx")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Userlar ro'yxati", callback_data="admin_list_users")],
        [InlineKeyboardButton("🔍 User qidirish", callback_data="admin_search_user")],
        [InlineKeyboardButton("❌ Yopish", callback_data="admin_close")],
    ])
    
    await query.edit_message_text(
        "🔧 *ADMIN PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Quyidagi amallardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    return ConversationHandler.END


async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin panel yopish"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("✅ Admin panel yopildi.")
    
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin: Bekor qilish"""
    context.user_data.pop("admin_action", None)
    context.user_data.pop("target_user_id", None)
    
    await update.message.reply_text("❌ Amal bekor qilindi.")
    
    return ConversationHandler.END


# Keep old function for backwards compatibility
def add_trial_handler_to_app(application):
    add_global_handlers_to_app(application)


