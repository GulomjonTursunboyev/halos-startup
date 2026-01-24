"""
SOLVO Bot Handlers
All conversation handlers and command handlers
"""
import logging
import os
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
    filters
)

from app.config import States, PDF_UPLOAD_DIR, TRANSACTION_UPLOAD_DIR, TRANSACTION_EXTENSIONS
from app.database import get_database
import asyncio
from app.languages import get_message, format_number
from app.subscription_handlers import require_pro, is_user_pro, show_pricing, show_pricing_new_message, show_subscription_expiring_warning
from app.engine import calculate_finances, format_result_message
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
            ["📊 Мой план", "👤 Профиль"],
            ["💎 Подписка", "🌐 Язык"],
            ["❓ Помощь"]
        ]
    else:
        keyboard = [
            ["📊 Qarz rejam", "👤 Profil"],
            ["💎 Obuna", "🌐 Til"],
            ["❓ Yordam"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# Main menu button texts for matching
MENU_BUTTONS = {
    "plan": ["📊 Qarz rejam", "📊 Мой план"],
    "profile": ["👤 Profil", "👤 Профиль"],
    "subscription": ["💎 Obuna", "💎 Подписка"],
    "language": ["🌐 Til", "🌐 Язык"],
    "help": ["❓ Yordam", "❓ Помощь"],
}


# ==================== START COMMAND ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - check if registered, if not request phone number"""
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
    """Handle language selection"""
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
    
    # Go directly to mode selection - subscription check will be after results
    # Ask for mode
    keyboard = [
        [
            InlineKeyboardButton(get_message("mode_solo", lang), callback_data="mode_solo"),
            InlineKeyboardButton(get_message("mode_family", lang), callback_data="mode_family")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message("select_mode", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.MODE


# ==================== MODE SELECTION ====================

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection (solo/family)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    mode = query.data.replace("mode_", "")
    context.user_data["mode"] = mode
    
    # Update user mode in database
    telegram_id = update.effective_user.id
    db = await get_database()
    await db.update_user(telegram_id, mode=mode)
    
    # Confirm mode
    if mode == "solo":
        mode_msg = await query.edit_message_text(get_message("mode_set_solo", lang))
    else:
        mode_msg = await query.edit_message_text(get_message("mode_set_family", lang))
    try:
        await asyncio.sleep(1)
        await mode_msg.delete()
    except:
        pass
    
    # Go directly to income input - user can send file or number
    await query.message.reply_text(
        get_message("input_income_self", lang),
        parse_mode="Markdown"
    )
    
    return States.INCOME_SELF


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
                    
                    # Continue to next step
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
    
    # Check if family mode
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


async def quick_partner_income_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for partner with no income"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["income_partner"] = 0
    
    await query.edit_message_text(
        get_message("income_saved", lang).format(amount="0")
    )
    
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


# ==================== LIVING COSTS INPUT ====================

async def rent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle rent input"""
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
    
    # Add quick button for no kindergarten
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


async def quick_rent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for own home (rent = 0)"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["rent"] = 0
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount="0")
    )
    
    # Add quick button for no kindergarten
    keyboard = [
        [InlineKeyboardButton(get_message("btn_no_kids", lang), callback_data="quick_kindergarten_0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        get_message("input_kindergarten", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KINDERGARTEN


async def kindergarten_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle kindergarten/education input"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text
    
    amount = parse_number(text)
    
    if amount < 0:
        await update.message.reply_text(
            get_message("invalid_number", lang),
            parse_mode="Markdown"
        )
        return States.KINDERGARTEN
    
    context.user_data["kindergarten"] = amount
    
    await update.message.reply_text(
        get_message("cost_saved", lang).format(amount=format_number(amount))
    )
    
    # Add quick buttons for common utility amounts
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


async def quick_kindergarten_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for no kindergarten/kids"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["kindergarten"] = 0
    
    await query.edit_message_text(
        get_message("cost_saved", lang).format(amount="0")
    )
    
    # Add quick buttons for common utility amounts
    keyboard = [
        [
            InlineKeyboardButton(get_message("btn_utilities_300", lang), callback_data="quick_utilities_300000"),
            InlineKeyboardButton(get_message("btn_utilities_500", lang), callback_data="quick_utilities_500000"),
            InlineKeyboardButton(get_message("btn_utilities_800", lang), callback_data="quick_utilities_800000")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        get_message("input_utilities", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.UTILITIES


async def utilities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle utilities input"""
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
    
    # Ask about KATM PDF upload
    keyboard = [
        [
            InlineKeyboardButton(get_message("katm_yes", lang), callback_data="katm_yes"),
            InlineKeyboardButton(get_message("katm_no", lang), callback_data="katm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_message("katm_choice", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KATM_CHOICE


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
    
    # Ask about KATM PDF upload
    keyboard = [
        [
            InlineKeyboardButton(get_message("katm_yes", lang), callback_data="katm_yes"),
            InlineKeyboardButton(get_message("katm_no", lang), callback_data="katm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        get_message("katm_choice", lang),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return States.KATM_CHOICE


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
    """Handle monthly loan payment input"""
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
    
    # If no loan payment, skip total debt
    if amount == 0:
        context.user_data["total_debt"] = 0
        return await calculate_and_show_results(update, context)
    
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
    """Handle quick button for no loans"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["loan_payment"] = 0
    context.user_data["total_debt"] = 0
    
    await query.edit_message_text(
        get_message("debt_saved", lang)
    )
    
    # Go to calculation
    return await calculate_and_show_results_from_callback(query, context)


async def quick_debt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick button for no remaining debt"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["total_debt"] = 0
    
    await query.edit_message_text(
        get_message("debt_saved", lang)
    )
    
    # Go to calculation
    return await calculate_and_show_results_from_callback(query, context)


async def total_debt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle total debt input"""
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
    
    return await calculate_and_show_results(update, context)


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
    await db._connection.execute(
        """
        UPDATE users SET subscription_tier = 'pro', subscription_expires = ?, subscription_plan = 'trial', trial_used = 1, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?
        """,
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
    """Calculate finances and show results"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = update.effective_user.id
    
    # Show calculating message
    calc_msg = await update.message.reply_text(
        get_message("calculating", lang)
    )
    
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
    
    # Delete calculating message
    await calc_msg.delete()
    
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
                "💎 To'liq natijani ko'rish" if lang == "uz" else "💎 Увидеть полный результат",
                callback_data="show_pricing"
            )],
            [InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate")],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        result_message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Show subscription offer for free users
    if not is_pro:
        offer_keyboard = [
            [InlineKeyboardButton(
                "⚡ 1 hafta - 5,000 so'm" if lang == "uz" else "⚡ 1 нед - 5,000 сум",
                callback_data="click_buy_pro_weekly"
            )],
            [InlineKeyboardButton(
                "⭐ 1 oy - 15,000 so'm" if lang == "uz" else "⭐ 1 мес - 15,000 сум",
                callback_data="click_buy_pro_monthly"
            )],
            [InlineKeyboardButton(
                "🏆 1 yil - 120,000 so'm (-33%)" if lang == "uz" else "🏆 1 год - 120,000 сум (-33%)",
                callback_data="click_buy_pro_yearly"
            )],
        ]
        offer_markup = InlineKeyboardMarkup(offer_keyboard)
        
        await update.message.reply_text(
            get_message("offer_after_first_calc", lang),
            parse_mode="Markdown",
            reply_markup=offer_markup
        )
    
    # Show main menu keyboard
    await update.message.reply_text(
        "⬇️" if lang == "uz" else "⬇️",
        reply_markup=get_main_menu_keyboard(lang)
    )
    
    return ConversationHandler.END


async def calculate_and_show_results_from_callback(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculate finances and show results (from callback query)"""
    lang = context.user_data.get("lang", "uz")
    telegram_id = query.from_user.id
    
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
                "💎 To'liq natijani ko'rish" if lang == "uz" else "💎 Увидеть полный результат",
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
    
    # Show subscription offer for free users
    if not is_pro:
        offer_keyboard = [
            [InlineKeyboardButton(
                "⚡ 1 hafta - 5,000 so'm" if lang == "uz" else "⚡ 1 нед - 5,000 сум",
                callback_data="click_buy_pro_weekly"
            )],
            [InlineKeyboardButton(
                "⭐ 1 oy - 15,000 so'm" if lang == "uz" else "⭐ 1 мес - 15,000 сум",
                callback_data="click_buy_pro_monthly"
            )],
            [InlineKeyboardButton(
                "🏆 1 yil - 120,000 so'm (-33%)" if lang == "uz" else "🏆 1 год - 120,000 сум (-33%)",
                callback_data="click_buy_pro_yearly"
            )],
        ]
        offer_markup = InlineKeyboardMarkup(offer_keyboard)
        
        await query.message.reply_text(
            get_message("offer_after_first_calc", lang),
            parse_mode="Markdown",
            reply_markup=offer_markup
        )
    
    # Show main menu keyboard
    await query.message.reply_text(
        "⬇️",
        reply_markup=get_main_menu_keyboard(lang)
    )
    
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
                "💎 To'liq natijani ko'rish" if lang == "uz" else "💎 Увидеть полный результат",
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
    
    # Show main menu keyboard
    await query.message.reply_text(
        "⬇️",
        reply_markup=get_main_menu_keyboard(lang)
    )
    
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
    """Build profile text and keyboard for display"""
    from app.engine import FinancialInput, FinancialEngine, format_exit_date
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Format profile info
    mode_text = "👤 Yolg'iz" if user.get("mode") == "solo" else "👨‍👩‍👦 Oila"
    if lang == "ru":
        mode_text = "👤 Один" if user.get("mode") == "solo" else "👨‍👩‍👦 Семья"
    
    lang_text = "🇺🇿 O'zbekcha" if user.get("language") == "uz" else "🇷🇺 Русский"
    
    profile_text = get_message("profile_info", lang).format(
        income_self=format_number(profile.get("income_self", 0)) + " so'm",
        income_partner=format_number(profile.get("income_partner", 0)) + " so'm",
        rent=format_number(profile.get("rent", 0)) + " so'm",
        kindergarten=format_number(profile.get("kindergarten", 0)) + " so'm",
        utilities=format_number(profile.get("utilities", 0)) + " so'm",
        loan_payment=format_number(profile.get("loan_payment", 0)) + " so'm",
        total_debt=format_number(profile.get("total_debt", 0)) + " so'm",
        mode=mode_text,
        language=lang_text
    )
    
    # Calculate debt status if user has debt
    total_debt = profile.get("total_debt", 0)
    loan_payment = profile.get("loan_payment", 0)
    
    debt_text = ""
    is_pro = await get_user_subscription_status(telegram_id)
    
    if total_debt > 0 and loan_payment > 0:
        # Calculate simple exit
        simple_exit_months = int(total_debt / loan_payment) + 1
        simple_exit_date = datetime.now() + relativedelta(months=simple_exit_months)
        simple_exit_formatted = format_exit_date(simple_exit_date.strftime("%Y-%m"), lang)
        
        debt_text = get_message("profile_debt_status", lang).format(
            total_debt=format_number(total_debt) + " so'm",
            monthly_payment=format_number(loan_payment) + " so'm",
            simple_exit_date=simple_exit_formatted,
            simple_exit_months=simple_exit_months
        )
        
        # If not PRO, add teaser for faster exit
        if not is_pro:
            # Calculate PRO exit (70-20-10 method)
            income = profile.get("income_self", 0) + profile.get("income_partner", 0)
            mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
            free_cash = income - mandatory - loan_payment
            
            if free_cash > 0:
                # PRO method: 70% living, 20% accelerated debt, 10% savings
                extra_debt_payment = free_cash * 0.2
                monthly_savings = free_cash * 0.1
                total_debt_payment = loan_payment + extra_debt_payment
                
                if total_debt_payment > 0:
                    pro_exit_months = int(total_debt / total_debt_payment) + 1
                    months_saved = simple_exit_months - pro_exit_months
                    savings_at_exit = monthly_savings * pro_exit_months
                    
                    if months_saved > 0:
                        pro_exit_date = datetime.now() + relativedelta(months=pro_exit_months)
                        pro_exit_formatted = format_exit_date(pro_exit_date.strftime("%Y-%m"), lang)
                        
                        debt_text += get_message("profile_pro_teaser", lang).format(
                            pro_exit_date=pro_exit_formatted,
                            months_saved=months_saved,
                            savings_at_exit=format_number(savings_at_exit) + " so'm"
                        )
    
    # Create edit buttons
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
    
    # Add action buttons based on user status
    if total_debt > 0 and not is_pro:
        keyboard.append([
            InlineKeyboardButton(get_message("btn_faster_exit", lang), callback_data="show_pricing")
        ])
    
    keyboard.append([
        InlineKeyboardButton(get_message("btn_recalculate", lang), callback_data="recalculate"),
    ])
    
    full_text = get_message("profile_header", lang) + "\n\n" + profile_text + debt_text
    
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
    
    if not profile:
        await update.message.reply_text(
            get_message("profile_no_data", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Build profile content
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
    
    if not profile:
        await query.edit_message_text(get_message("profile_no_data", lang))
        return
    
    # Build profile content using shared helper
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
        return
    
    # Update in database
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return
    
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
    
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Error: {context.error}")
    
    if update and update.effective_message:
        lang = context.user_data.get("lang", "uz") if context.user_data else "uz"
        
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
    application.add_handler(CallbackQueryHandler(start_trial_callback, pattern="^start_trial$"), group=0)
    application.add_handler(CallbackQueryHandler(show_profile_callback, pattern="^show_profile$"), group=0)
    application.add_handler(CallbackQueryHandler(edit_profile_field_callback, pattern="^edit_"), group=0)
    application.add_handler(CallbackQueryHandler(profile_mode_callback, pattern="^profile_mode_"), group=0)
    application.add_handler(CommandHandler("profile", profile_command), group=0)
    
    # Main menu button handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(📊 Qarz rejam|📊 Мой план)$"),
        menu_plan_handler
    ), group=1)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(👤 Profil|👤 Профиль)$"),
        menu_profile_handler
    ), group=1)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(💎 Obuna|💎 Подписка)$"),
        menu_subscription_handler
    ), group=1)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(🌐 Til|🌐 Язык)$"),
        menu_language_handler
    ), group=1)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(❓ Yordam|❓ Помощь)$"),
        menu_help_handler
    ), group=1)


# ==================== MAIN MENU HANDLERS ====================

async def menu_plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 📊 Qarz rejam button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Update activity for PRO care scheduler
    await db.update_user_activity(telegram_id)
    
    if not user:
        await update.message.reply_text(
            get_message("profile_no_data", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    profile = await db.get_financial_profile(user["id"])
    
    if not profile or profile.get("income_self", 0) == 0:
        await update.message.reply_text(
            get_message("profile_no_data", lang),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Calculate and show results
    calc_msg = await update.message.reply_text(
        get_message("calculating_saved", lang)
    )
    
    mode = user.get("mode", "solo")
    
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
    
    result = calculate_finances(financial_input)
    is_pro = await get_user_subscription_status(telegram_id)
    result_message = format_result_message(result, lang, is_pro=is_pro)
    
    await calc_msg.delete()
    
    # Add inline buttons
    if is_pro:
        keyboard = [
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(
                "💎 To'liq natijani ko'rish" if lang == "uz" else "💎 Увидеть полный результат",
                callback_data="show_pricing"
            )],
            [InlineKeyboardButton(get_message("btn_profile", lang), callback_data="show_profile")]
        ]
    
    await update.message.reply_text(
        result_message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 👤 Profil button"""
    # Update activity for PRO care scheduler
    db = await get_database()
    await db.update_user_activity(update.effective_user.id)
    
    await profile_command(update, context)


async def menu_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 💎 Obuna button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    # Update activity for PRO care scheduler
    db = await get_database()
    await db.update_user_activity(telegram_id)
    
    # Show subscription status and options
    user = await db.get_user(telegram_id)
    is_pro = await get_user_subscription_status(telegram_id)
    
    if is_pro and user:
        # Show PRO status
        expires = user.get("subscription_expires", "")
        status_text = get_message("subscription_active", lang).format(
            expires=expires[:10] if expires else "∞"
        )
        await update.message.reply_text(
            status_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(lang)
        )
    else:
        # Show pricing
        await show_pricing_new_message(update, context)


async def menu_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 🌐 Til button"""
    # Update activity for PRO care scheduler
    db = await get_database()
    await db.update_user_activity(update.effective_user.id)
    
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


async def menu_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ❓ Yordam button"""
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    
    # Update activity for PRO care scheduler
    db = await get_database()
    await db.update_user_activity(telegram_id)
    
    await update.message.reply_text(
        get_message("help", lang),
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(lang)
    )


# Keep old function for backwards compatibility
def add_trial_handler_to_app(application):
    add_global_handlers_to_app(application)

