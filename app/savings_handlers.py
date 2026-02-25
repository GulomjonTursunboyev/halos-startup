"""
HALOS Savings Handler
Maqsadli jamg'arma funksionalini boshqarish
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from app.database import get_database
from app.languages import get_message, format_number
from app.config import States

# Circular import prevention: We define local helper instead of importing from handlers
logger = logging.getLogger(__name__)

def parse_number_local(text: str) -> float:
    """Parse number from user input"""
    cleaned = text.strip().replace(" ", "").replace(",", "").replace(".", "")
    cleaned = cleaned.replace("so'm", "").replace("sum", "").replace("сум", "")
    try:
        return float(cleaned)
    except ValueError:
        return -1

async def menu_savings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maqsadli Jamg'arma Menyusi"""
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    if not user:
        return

    try:
        goals = await db.get_user_savings_goals(user["id"])
    except AttributeError:
        # Schema not updated yet or method not found
        goals = []
    except Exception as e:
        logger.error(f"Error getting savings goals: {e}")
        goals = []
    
    msg = ""
    keyboard = []
    
    if lang == "uz":
        msg = "💰 *MAQSADLI JAMG'ARMA*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "💡 _Kelajakdagi maqsadlaringiz uchun pul yig'ing (Uy, Mashina, Haj)_\n\n"
    else:
        msg = "💰 *ЦЕЛЕВЫЕ СБЕРЕЖЕНИЯ*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "💡 _Копите на будущие цели (Дом, Машина, Хадж)_\n\n"

    if goals:
        total = sum(g['current_amount'] for g in goals)
        if lang == "uz":
            msg += f"💵 Jami jamg'arma: *{format_number(total)}* so'm\n\n"
        else:
            msg += f"💵 Всего накоплено: *{format_number(total)}* сум\n\n"
            
        for g in goals:
            target = g['target_amount']
            current = g['current_amount']
            percent = (current / target) * 100 if target > 0 else 0
            # Progress bar visual (simplified)
            p_val = min(100, int(percent))
            
            icon = g.get('icon', '💰')
            name = g['name']
            
            keyboard.append([InlineKeyboardButton(
                f"{icon} {name} | {p_val}% ({format_number(current)})",
                callback_data=f"savings_view:{g['id']}"
            )])
    else:
        if lang == "uz":
            msg += "Sizda hali maqsadlar yo'q.\n"
        else:
            msg += "У вас пока нет целей.\n"

    btn_text = "➕ Yangi maqsad" if lang == "uz" else "➕ Новая цель"
    keyboard.append([InlineKeyboardButton(btn_text, callback_data="savings_add_new")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def savings_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding new savings goal"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    
    context.user_data["awaiting_savings_input"] = True # AI block
    
    if lang == "uz":
        msg = "🎯 *YANGI MAQSAD*\n\nMaqsad nomini yozing:\n_Masalan: Umra safari, Chevrolet Tracker..._"
    else:
        msg = "🎯 *НОВАЯ ЦЕЛЬ*\n\nВведите название цели:\n_Например: Поездка в Умру, Chevrolet Tracker..._"
        
    await query.edit_message_text(msg, parse_mode="Markdown")
    return States.SAVINGS_NAME

async def handle_savings_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive savings goal name"""
    lang = context.user_data.get("lang", "uz")
    name = update.message.text.strip()
    
    context.user_data["new_savings_name"] = name
    
    if lang == "uz":
        msg = f"✅ Maqsad: *{name}*\n\nEndi kerakli summani kiriting (so'mda):"
    else:
        msg = f"✅ Цель: *{name}*\n\nТеперь введите необходимую сумму (в сумах):"
        
    await update.message.reply_text(msg, parse_mode="Markdown")
    return States.SAVINGS_TARGET

async def handle_savings_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive savings target amount and create goal"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text.strip()
    telegram_id = update.effective_user.id
    
    amount = parse_number_local(text)
    if amount <= 0:
        err = "❌ Noto'g'ri summa. Raqam kiriting:" if lang == "uz" else "❌ Неверная сумма. Введите число:"
        await update.message.reply_text(err)
        return States.SAVINGS_TARGET
    
    name = context.user_data.get("new_savings_name", "Maqsad")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    # Create goal (default icon for now)
    try:
        await db.create_savings_goal(user["id"], name, amount)
        success = "✅ Maqsad muvaffaqiyatli yaratildi!" if lang == "uz" else "✅ Цель успешно создана!"
    except Exception as e:
        logger.error(f"Error creating savings goal: {e}")
        success = "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка"
    
    # Send success message
    await update.message.reply_text(success)
    
    # Show updated list
    await menu_savings_handler(update, context)
    
    context.user_data["awaiting_savings_input"] = False
    return ConversationHandler.END

async def savings_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View details of a savings goal"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    try:
        goal_id = int(query.data.split(":")[1])
    except:
        return
        
    db = await get_database()
    goal = await db.get_savings_goal(goal_id)
    
    if not goal:
        if lang == "uz":
            await query.edit_message_text("❌ Maqsad topilmadi")
        else:
            await query.edit_message_text("❌ Цель не найдена")
        return
        
    target = goal['target_amount']
    current = goal['current_amount']
    percent = (current / target) * 100 if target > 0 else 0
    
    if percent >= 10:
        progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
    else:
        progress_bar = "░" * 10
    
    if lang == "uz":
        msg = f"🎯 *{goal['name']}*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Yig'ildi: *{format_number(current)}*\n"
        msg += f"🏁 Maqsad: *{format_number(target)}*\n"
        msg += f"\n{progress_bar} {percent:.1f}%\n"
    else:
        msg = f"🎯 *{goal['name']}*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Накоплено: *{format_number(current)}*\n"
        msg += f"🏁 Цель: *{format_number(target)}*\n"
        msg += f"\n{progress_bar} {percent:.1f}%\n"
        
    keyboard = [
        [
            InlineKeyboardButton("➕ Pul qo'shish" if lang == "uz" else "➕ Внести", callback_data=f"savings_dep:{goal['id']}"),
            InlineKeyboardButton("➖ Pul yechish" if lang == "uz" else "➖ Снять", callback_data=f"savings_wd:{goal['id']}")
        ],
        [
             InlineKeyboardButton("❌ O'chirish" if lang == "uz" else "❌ Удалить", callback_data=f"savings_del:{goal['id']}")
        ],
        [
            InlineKeyboardButton("🔙 Ortga" if lang == "uz" else "🔙 Назад", callback_data="back_to_savings")
        ]
    ]
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def savings_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deposit/withdraw start"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    action, goal_id = query.data.split(":")
    
    context.user_data["savings_goal_id"] = int(goal_id)
    context.user_data["savings_action"] = "deposit" if "dep" in action else "withdraw"
    context.user_data["awaiting_savings_input"] = True
    
    action_text = "qo'shmoqchi" if "dep" in action else "yechmoqchi"
    if lang != "uz":
        action_text = "внести" if "dep" in action else "снять"
        
    if lang == "uz":
        msg = f"Summani kiriting (qancha {action_text}siz?):"
    else:
        msg = f"Введите сумму (сколько хотите {action_text}?):"
        
    await query.edit_message_text(msg)
    return States.SAVINGS_DEPOSIT

async def handle_savings_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process deposit/withdraw amount"""
    lang = context.user_data.get("lang", "uz")
    text = update.message.text.strip()
    telegram_id = update.effective_user.id
    
    amount = parse_number_local(text)
    if amount <= 0:
        await update.message.reply_text("❌")
        return States.SAVINGS_DEPOSIT
        
    goal_id = context.user_data.get("savings_goal_id")
    action = context.user_data.get("savings_action")
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    try:
        success = await db.add_savings_transaction(goal_id, user["id"], amount, action)
    except Exception:
        success = False
    
    if success:
        await update.message.reply_text("✅ Muvaffaqiyatli!" if lang == "uz" else "✅ Успешно!")
    else:
        await update.message.reply_text("❌ Xatolik!" if lang == "uz" else "❌ Ошибка!")
        
    # Back to list
    await menu_savings_handler(update, context)
    context.user_data["awaiting_savings_input"] = False
    return ConversationHandler.END

async def active_savings_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete savings goal"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    try:
        goal_id = int(query.data.split(":")[1])
    except:
        return
        
    telegram_id = update.effective_user.id
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    await db.delete_savings_goal(goal_id, user["id"])
    
    if lang == "uz":
        await query.edit_message_text("🗑 Maqsad o'chirildi.")
    else:
        await query.edit_message_text("🗑 Цель удалена.")
    
    # Close context flag
    context.user_data["awaiting_savings_input"] = False

async def back_to_savings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await menu_savings_handler(update, context)
