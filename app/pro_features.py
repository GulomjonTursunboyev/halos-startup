"""
HALOS PRO Features Module
Statistics, Reminders, Debt Monitoring, Excel Export
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.database import get_database
from app.languages import get_message, format_number
from app.subscription_handlers import is_user_pro

logger = logging.getLogger(__name__)


# ==================== STATISTICS ====================

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user statistics - weekly/monthly/yearly"""
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        if lang == "uz":
            msg = "🔒 *Statistika PRO foydalanuvchilar uchun*\n\nPRO ga o'ting va batafsil statistikani ko'ring!"
        else:
            msg = "🔒 *Статистика для PRO пользователей*\n\nПерейдите на PRO и смотрите детальную статистику!"
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return
    
    # Get user data
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    if not profile:
        if lang == "uz":
            msg = "📊 Statistika ko'rish uchun avval ma'lumotlaringizni kiriting."
        else:
            msg = "📊 Для просмотра статистики сначала введите свои данные."
        
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    # Build statistics
    income = profile.get("income_self", 0) + profile.get("income_partner", 0)
    mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
    loan_payment = profile.get("loan_payment", 0)
    total_debt = profile.get("total_debt", 0)
    free_cash = income - mandatory - loan_payment
    
    if free_cash > 0:
        savings = free_cash * 0.1  # 10% savings
        extra_debt = free_cash * 0.2  # 20% extra to debt
        living = free_cash * 0.7  # 70% for living
    else:
        savings = living = extra_debt = 0
    
    # Calculate projections
    weekly_savings = savings / 4
    monthly_savings = savings
    yearly_savings = savings * 12
    
    weekly_income = income / 4
    monthly_income = income
    yearly_income = income * 12
    
    weekly_expense = (mandatory + loan_payment + living) / 4
    monthly_expense = mandatory + loan_payment + living
    yearly_expense = monthly_expense * 12
    
    # Get AI transaction summary
    from app.ai_assistant import get_transaction_summary
    ai_summary = await get_transaction_summary(db, user["id"], days=30)
    ai_income = ai_summary.get("total_income", 0)
    ai_expense = ai_summary.get("total_expense", 0)
    ai_balance = ai_income - ai_expense
    
    if lang == "uz":
        msg = (
            "📊 *SIZNING STATISTIKANGIZ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📅 *HAFTALIK:*\n"
            f"├ 💰 Daromad: ~{format_number(int(weekly_income))} so'm\n"
            f"├ 💸 Xarajat: ~{format_number(int(weekly_expense))} so'm\n"
            f"└ 🏦 Boylik: +{format_number(int(weekly_savings))} so'm\n\n"
            
            "📅 *OYLIK:*\n"
            f"├ 💰 Daromad: {format_number(int(monthly_income))} so'm\n"
            f"├ 💸 Xarajat: {format_number(int(monthly_expense))} so'm\n"
            f"└ 🏦 Boylik: +{format_number(int(monthly_savings))} so'm\n\n"
            
            "📅 *YILLIK PROGNOZ:*\n"
            f"├ 💰 Daromad: {format_number(int(yearly_income))} so'm\n"
            f"├ 💸 Xarajat: {format_number(int(yearly_expense))} so'm\n"
            f"└ 🏦 Boylik: +{format_number(int(yearly_savings))} so'm\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 *AI YORDAMCHI (30 kun):*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 💰 Daromadlar: +{format_number(int(ai_income))} so'm\n"
            f"├ 💸 Xarajatlar: -{format_number(int(ai_expense))} so'm\n"
            f"└ 📊 Balans: {'+' if ai_balance >= 0 else ''}{format_number(int(ai_balance))} so'm\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Umumiy qarz: {format_number(int(total_debt))} so'm"
        )
    else:
        msg = (
            "📊 *ВАША СТАТИСТИКА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "📅 *ЕЖЕНЕДЕЛЬНО:*\n"
            f"├ 💰 Доход: ~{format_number(int(weekly_income))} сум\n"
            f"├ 💸 Расход: ~{format_number(int(weekly_expense))} сум\n"
            f"└ 🏦 Богатство: +{format_number(int(weekly_savings))} сум\n\n"
            
            "📅 *ЕЖЕМЕСЯЧНО:*\n"
            f"├ 💰 Доход: {format_number(int(monthly_income))} сум\n"
            f"├ 💸 Расход: {format_number(int(monthly_expense))} сум\n"
            f"└ 🏦 Богатство: +{format_number(int(monthly_savings))} сум\n\n"
            
            "📅 *ГОДОВОЙ ПРОГНОЗ:*\n"
            f"├ 💰 Доход: {format_number(int(yearly_income))} сум\n"
            f"├ 💸 Расход: {format_number(int(yearly_expense))} сум\n"
            f"└ 🏦 Богатство: +{format_number(int(yearly_savings))} сум\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 *AI ПОМОЩНИК (30 дней):*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 💰 Доходы: +{format_number(int(ai_income))} сум\n"
            f"├ 💸 Расходы: -{format_number(int(ai_expense))} сум\n"
            f"└ 📊 Баланс: {'+' if ai_balance >= 0 else ''}{format_number(int(ai_balance))} сум\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Общий долг: {format_number(int(total_debt))} сум"
        )
    
    keyboard = [[InlineKeyboardButton(
        "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
        callback_data="pro_menu"
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


# ==================== REMINDERS ====================

async def show_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show and manage payment reminders"""
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        if lang == "uz":
            msg = "🔒 *Eslatmalar PRO foydalanuvchilar uchun*\n\nPRO ga o'ting va to'lov eslatmalarini oling!"
        else:
            msg = "🔒 *Напоминания для PRO пользователей*\n\nПерейдите на PRO и получайте напоминания!"
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return
    
    # Get user's reminders
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if lang == "uz":
        msg = (
            "🔔 *TO'LOV ESLATMALARI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "HALOS sizga quyidagilarni eslatib turadi:\n\n"
            
            "✅ *Oylik to'lov* — har oy 1-sanada\n"
            "✅ *Haftalik hisobot* — har dushanba\n"
            "✅ *Qarz holati* — har 15 kunda\n"
            "✅ *Boylik o'sishi* — har oyda\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Eslatmalar avtomatik yoqilgan.\n"
            "Xabarnomalar Telegram orqali keladi."
        )
    else:
        msg = (
            "🔔 *НАПОМИНАНИЯ ОБ ОПЛАТЕ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "HALOS напомнит вам о:\n\n"
            
            "✅ *Ежемесячный платёж* — 1-го числа\n"
            "✅ *Еженедельный отчёт* — каждый понедельник\n"
            "✅ *Состояние долга* — каждые 15 дней\n"
            "✅ *Рост богатства* — каждый месяц\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Напоминания включены автоматически.\n"
            "Уведомления приходят через Telegram."
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "🔕 O'chirish" if lang == "uz" else "🔕 Отключить",
            callback_data="toggle_reminders_off"
        ), InlineKeyboardButton(
            "🔔 Yoqish" if lang == "uz" else "🔔 Включить",
            callback_data="toggle_reminders_on"
        )],
        [InlineKeyboardButton(
            "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
            callback_data="pro_menu"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


# ==================== DEBT MONITORING ====================

async def show_debt_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show debt monitoring with progress and tips"""
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        if lang == "uz":
            msg = "🔒 *Qarz nazorati PRO foydalanuvchilar uchun*\n\nPRO ga o'ting va qarzlaringizni nazorat qiling!"
        else:
            msg = "🔒 *Контроль долгов для PRO пользователей*\n\nПерейдите на PRO и контролируйте долги!"
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return
    
    # Get user data
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    if not profile:
        if lang == "uz":
            msg = "📋 Qarz nazorati uchun avval ma'lumotlaringizni kiriting."
        else:
            msg = "📋 Для контроля долгов сначала введите свои данные."
        
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    # Calculate debt progress
    total_debt = profile.get("total_debt", 0)
    loan_payment = profile.get("loan_payment", 0)
    income = profile.get("income_self", 0) + profile.get("income_partner", 0)
    mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
    free_cash = income - mandatory - loan_payment
    
    import math
    if loan_payment > 0 and total_debt > 0:
        # Simple months
        simple_months = math.ceil(total_debt / loan_payment)
        
        # PRO months (with extra payments)
        if free_cash > 0:
            extra_debt = free_cash * 0.2
            total_payment = loan_payment + extra_debt
            pro_months = math.ceil(total_debt / total_payment)
        else:
            pro_months = simple_months
            extra_debt = 0
        
        # Calculate progress (assume user started today)
        progress_percent = 0  # Will be calculated based on actual tracking
        
        # Exit dates
        today = datetime.now()
        simple_exit = today + timedelta(days=simple_months * 30)
        pro_exit = today + timedelta(days=pro_months * 30)
        
        # Progress bar
        bar_filled = int(progress_percent / 10)
        bar_empty = 10 - bar_filled
        progress_bar = "█" * bar_filled + "░" * bar_empty
        
        if lang == "uz":
            msg = (
                "📋 *YO'LINGIZ NAZORATI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"💳 *Umumiy yuk:* {format_number(int(total_debt))} so'm\n"
                f"📅 *Oylik to'lov:* {format_number(int(loan_payment))} so'm\n"
                f"⚡ *Qo'shimcha:* +{format_number(int(extra_debt))} so'm\n\n"
                
                f"[{progress_bar}] {progress_percent}%\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📊 *PROGNOZ:*\n"
                f"├ Oddiy yo'l: {simple_exit.strftime('%B %Y')}\n"
                f"└ HALOS PRO bilan: {pro_exit.strftime('%B %Y')}\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *MASLAHAT:*\n"
                "Har oyda qo'shimcha to'lov qilsangiz,\n"
                f"*{simple_months - pro_months} oy* oldin yengillikka erishasiz!"
            )
        else:
            msg = (
                "📋 *КОНТРОЛЬ ВАШЕГО ПУТИ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"💳 *Общее бремя:* {format_number(int(total_debt))} сум\n"
                f"📅 *Ежемесячно:* {format_number(int(loan_payment))} сум\n"
                f"⚡ *Дополнительно:* +{format_number(int(extra_debt))} сум\n\n"
                
                f"[{progress_bar}] {progress_percent}%\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📊 *ПРОГНОЗ:*\n"
                f"├ Обычный путь: {simple_exit.strftime('%B %Y')}\n"
                f"└ С HALOS PRO: {pro_exit.strftime('%B %Y')}\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *СОВЕТ:*\n"
                "Делая дополнительные платежи,\n"
                f"достигнете свободы на *{simple_months - pro_months} мес* раньше!"
            )
    else:
        if lang == "uz":
            msg = "📋 Qarz ma'lumotlari topilmadi. Iltimos, qarz summasini kiriting."
        else:
            msg = "📋 Данные о долге не найдены. Пожалуйста, введите сумму долга."
    
    keyboard = [[InlineKeyboardButton(
        "◀️ Orqaga" if lang == "uz" else "◀️ Назад",
        callback_data="pro_menu"
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


# ==================== EXCEL EXPORT ====================

async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export user data to Excel file"""
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    if not is_pro:
        if lang == "uz":
            msg = "🔒 *Excel eksport PRO foydalanuvchilar uchun*\n\nPRO ga o'ting va hisobotlaringizni yuklab oling!"
        else:
            msg = "🔒 *Excel экспорт для PRO пользователей*\n\nПерейдите на PRO и скачивайте отчёты!"
        
        keyboard = [[InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return
    
    # Get user data
    db = await get_database()
    user = await db.get_user(telegram_id)
    profile = await db.get_financial_profile(user["id"]) if user else None
    
    if not profile:
        if lang == "uz":
            msg = "📥 Eksport qilish uchun avval ma'lumotlaringizni kiriting."
        else:
            msg = "📥 Для экспорта сначала введите свои данные."
        
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    # Generate Excel file
    try:
        import pandas as pd
        from io import BytesIO
        import math
        
        # Prepare data
        income = profile.get("income_self", 0) + profile.get("income_partner", 0)
        mandatory = profile.get("rent", 0) + profile.get("kindergarten", 0) + profile.get("utilities", 0)
        loan_payment = profile.get("loan_payment", 0)
        total_debt = profile.get("total_debt", 0)
        free_cash = income - mandatory - loan_payment
        
        if free_cash > 0:
            savings = free_cash * 0.1
            extra_debt = free_cash * 0.2
            living = free_cash * 0.7
        else:
            savings = living = extra_debt = 0
        
        # Calculate exit months
        if loan_payment > 0 and total_debt > 0:
            simple_months = math.ceil(total_debt / loan_payment)
            total_payment = loan_payment + extra_debt
            pro_months = math.ceil(total_debt / total_payment) if total_payment > 0 else simple_months
        else:
            simple_months = pro_months = 0
        
        # Create dataframe
        if lang == "uz":
            data = {
                "Ko'rsatkich": [
                    "Daromad (shaxsiy)", "Daromad (sherik)", "Umumiy daromad",
                    "Ijara", "Bog'cha", "Kommunal", "Yuk to'lovi", "Majburiy xarajatlar",
                    "Bo'sh pul", "Boylik uchun", "Kredit to'lovi", "Yashash",
                    "Umumiy yuk", "Oddiy yo'l (oy)", "HALOS bilan (oy)"
                ],
                "Qiymat (so'm)": [
                    profile.get("income_self", 0), profile.get("income_partner", 0), income,
                    profile.get("rent", 0), profile.get("kindergarten", 0), profile.get("utilities", 0),
                    loan_payment, mandatory + loan_payment,
                    free_cash, savings, extra_debt, living,
                    total_debt, simple_months, pro_months
                ]
            }
        else:
            data = {
                "Показатель": [
                    "Доход (личный)", "Доход (партнёр)", "Общий доход",
                    "Аренда", "Детсад", "Коммуналка", "Платёж по бремени", "Обязательные расходы",
                    "Свободные средства", "Для богатства", "Платёж по кредиту", "Жизнь",
                    "Общее бремя", "Обычный путь (мес)", "С HALOS (мес)"
                ],
                "Значение (сум)": [
                    profile.get("income_self", 0), profile.get("income_partner", 0), income,
                    profile.get("rent", 0), profile.get("kindergarten", 0), profile.get("utilities", 0),
                    loan_payment, mandatory + loan_payment,
                    free_cash, savings, extra_debt, living,
                    total_debt, simple_months, pro_months
                ]
            }
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='HALOS Report', index=False)
        output.seek(0)
        
        # Send file
        filename = f"HALOS_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        if query:
            chat_id = query.message.chat_id
        else:
            chat_id = update.message.chat_id
        
        await context.bot.send_document(
            chat_id=chat_id,
            document=output,
            filename=filename,
            caption="📊 HALOS Report" if lang == "uz" else "📊 Отчёт HALOS"
        )
        
        if lang == "uz":
            msg = "✅ Excel hisobot yuborildi!"
        else:
            msg = "✅ Excel отчёт отправлен!"
        
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
            
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        if lang == "uz":
            msg = "❌ Eksportda xatolik yuz berdi. Keyinroq urinib ko'ring."
        else:
            msg = "❌ Ошибка при экспорте. Попробуйте позже."
        
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)


# ==================== PRO MENU ====================

async def show_pro_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show PRO features menu"""
    query = update.callback_query
    if query:
        await query.answer()
    
    telegram_id = update.effective_user.id
    lang = context.user_data.get("lang", "uz")
    
    # Check PRO status
    is_pro = await is_user_pro(telegram_id)
    
    if not is_pro:
        # Show pricing instead
        from app.subscription_handlers import show_pricing
        await show_pricing(update, context)
        return
    
    if lang == "uz":
        msg = (
            "💎 *HALOS PRO*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "PRO imkoniyatlaringiz:\n\n"
            
            "🤖 *AI yordamchi* — ovozli xarajat/daromad yozish\n"
            "📊 *Statistika* — haftalik/oylik/yillik\n"
            "🔔 *Eslatmalar* — to'lov eslatmalari\n"
            "📋 *Yuk nazorati* — monitoring va maslahatlar\n"
            "📥 *Excel hisobot* — yuklab olish\n"
        )
    else:
        msg = (
            "💎 *HALOS PRO*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "Ваши PRO возможности:\n\n"
            
            "🤖 *AI помощник* — голосовая запись расходов/доходов\n"
            "📊 *Статистика* — еженедельно/ежемесячно/ежегодно\n"
            "🔔 *Напоминания* — напоминания об оплате\n"
            "📋 *Контроль нагрузки* — мониторинг и советы\n"
            "📥 *Excel отчёт* — скачать\n"
        )
    
    keyboard = [
        [InlineKeyboardButton(
            "🤖 AI yordamchi" if lang == "uz" else "🤖 AI помощник",
            callback_data="ai_assistant"
        )],
        [InlineKeyboardButton(
            "📊 Statistika" if lang == "uz" else "📊 Статистика",
            callback_data="pro_statistics"
        )],
        [InlineKeyboardButton(
            "🔔 Eslatmalar" if lang == "uz" else "🔔 Напоминания",
            callback_data="pro_reminders"
        )],
        [InlineKeyboardButton(
            "📋 Yuk nazorati" if lang == "uz" else "📋 Контроль нагрузки",
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


# ==================== CALLBACK HANDLERS ====================

async def pro_statistics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle statistics callback"""
    await show_statistics(update, context)


async def pro_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle reminders callback"""
    await show_reminders(update, context)


async def pro_debt_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle debt monitoring callback"""
    await show_debt_monitoring(update, context)


async def pro_export_excel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Excel export callback"""
    await export_excel(update, context)


async def pro_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle PRO menu callback"""
    await show_pro_menu(update, context)


async def toggle_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle reminder toggle"""
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "uz")
    action = query.data.replace("toggle_reminders_", "")
    
    if action == "on":
        if lang == "uz":
            msg = "✅ Eslatmalar yoqildi!"
        else:
            msg = "✅ Напоминания включены!"
    else:
        if lang == "uz":
            msg = "🔕 Eslatmalar o'chirildi."
        else:
            msg = "🔕 Напоминания отключены."
    
    await query.answer(msg, show_alert=True)
    
    # Go back to reminders menu
    await show_reminders(update, context)
