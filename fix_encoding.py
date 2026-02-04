# -*- coding: utf-8 -*-
"""Fix encoding issues in handlers.py - Qarzlar and Profil sections"""

def fix_menu_debts():
    """Fix menu_debts_handler with proper emojis and text"""
    
    # Read file
    with open('app/handlers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find menu_debts_handler function
    start_marker = 'async def menu_debts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:'
    end_marker = '    # ========== KEYBOARD =========='
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker, start_idx)
    
    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find menu_debts_handler section")
        return False
    
    # New menu_debts_handler code (message building part only)
    new_code = '''async def menu_debts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle 💳 Qarzlar button - PROFESSIONAL QARZLAR DASHBOARD
    
    Senior PM & UX Designer approach:
    1. Clear visual hierarchy with sections
    2. Personal debts (lent/borrowed) - separate section
    3. Bank credits/loans - separate section  
    4. Quick summary at top
    5. Actionable buttons for each section
    """
    telegram_id = update.effective_user.id
    lang = await get_user_language(telegram_id)
    context.user_data["lang"] = lang
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user or not user.get("phone_number"):
        await update.message.reply_text(
            get_message("contact_required", lang),
            parse_mode="Markdown"
        )
        return
    
    # ========== 1. SHAXSIY QARZLAR (Personal Debts) ==========
    from app.ai_assistant import get_debt_summary
    
    try:
        debt_summary = await get_debt_summary(db, user["id"])
    except:
        debt_summary = {"total_lent": 0, "total_borrowed": 0, "net_balance": 0, "lent_count": 0, "borrowed_count": 0}
    
    total_lent = debt_summary.get("total_lent", 0)
    total_borrowed = debt_summary.get("total_borrowed", 0)
    net_balance = debt_summary.get("net_balance", 0)
    lent_count = debt_summary.get("lent_count", 0)
    borrowed_count = debt_summary.get("borrowed_count", 0)
    
    # ========== 2. BANK KREDITLARI (KATM Loans) ==========
    try:
        katm_loans = await db.get_user_katm_loans(user["id"])
    except:
        katm_loans = []
    
    total_credit_balance = sum(loan.get("remaining_balance", 0) or 0 for loan in katm_loans)
    total_monthly_payment = sum(loan.get("monthly_payment", 0) or 0 for loan in katm_loans)
    credit_count = len(katm_loans)
    
    # ========== 3. PROFILDA LOAN_PAYMENT (Legacy kredit to'lovi) ==========
    try:
        profile = await db.get_financial_profile(user["id"])
        legacy_loan_payment = profile.get("loan_payment", 0) if profile else 0
        legacy_total_debt = profile.get("total_debt", 0) if profile else 0
    except:
        legacy_loan_payment = 0
        legacy_total_debt = 0
    
    # Agar KATM bo'lmasa, lekin profilda kredit bor
    if not katm_loans and (legacy_loan_payment > 0 or legacy_total_debt > 0):
        total_credit_balance = legacy_total_debt
        total_monthly_payment = legacy_loan_payment
        credit_count = 1 if legacy_total_debt > 0 else 0
    
    # ========== 4. UMUMIY HISOB ==========
    # Jami qarz yuklamasi = bank krediti + shaxsiy qarz
    total_debt_burden = total_credit_balance + total_borrowed
    total_receivable = total_lent  # Sizga qaytarilishi kerak
    
    # ========== MESSAGE BUILDING ==========
    if lang == "uz":
        # HEADER - Quick Summary
        msg = "💳 *QARZLAR DASHBOARD*\\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n"
        
        # SUMMARY BLOCK
        if total_receivable > 0 and total_debt_burden > 0:
            diff = total_receivable - total_debt_burden
            if diff > 0:
                msg += f"📊 *Balans:* 🟢 +{diff:,.0f} so'm\\n\\n"
            else:
                msg += f"📊 *Balans:* 🔴 {diff:,.0f} so'm\\n\\n"
        elif total_receivable > 0:
            msg += f"📊 *Balans:* 🟢 +{total_receivable:,.0f} so'm\\n\\n"
        elif total_debt_burden > 0:
            msg += f"📊 *Balans:* 🔴 -{total_debt_burden:,.0f} so'm\\n\\n"
        else:
            msg += "📊 *Balans:* ⚪ Qarz yo'q\\n\\n"
        
        # ========== SECTION 1: SHAXSIY QARZLAR ==========
        msg += "👥 *SHAXSIY QARZLAR*\\n"
        msg += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\\n"
        
        if total_lent > 0 or total_borrowed > 0:
            if total_lent > 0:
                msg += f"📤 Berdingiz: *{total_lent:,.0f}* ({lent_count})\\n"
                msg += "    _↳ Sizga qaytariladi_\\n"
            if total_borrowed > 0:
                msg += f"📥 Oldingiz: *{total_borrowed:,.0f}* ({borrowed_count})\\n"
                msg += "    _↳ Siz qaytarasiz_\\n"
        else:
            msg += "✅ Shaxsiy qarz yo'q\\n"
        
        msg += "\\n"
        
        # ========== SECTION 2: BANK KREDITLARI ==========
        msg += "🏦 *BANK KREDITLARI*\\n"
        msg += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\\n"
        
        if credit_count > 0:
            msg += f"💳 Kreditlar: *{credit_count}* ta\\n"
            msg += f"📉 Qoldiq: *{total_credit_balance:,.0f}* so'm\\n"
            msg += f"📆 Oylik to'lov: *{total_monthly_payment:,.0f}* so'm\\n"
            
            # Har bir kredit detali (max 3 ta)
            if katm_loans:
                msg += "\\n📋 *Kreditlar ro'yxati:*\\n"
                for i, loan in enumerate(katm_loans[:3], 1):
                    bank = loan.get("bank_name", "Bank")
                    balance = loan.get("remaining_balance", 0) or 0
                    monthly = loan.get("monthly_payment", 0) or 0
                    msg += f"  {i}. {bank}\\n"
                    msg += f"     💵 {balance:,.0f} | 📅 {monthly:,.0f}/oy\\n"
                
                if len(katm_loans) > 3:
                    msg += f"  _...va yana {len(katm_loans) - 3} ta_\\n"
        else:
            msg += "✅ Bank krediti yo'q\\n"
        
        msg += "\\n━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        msg += "💡 _Qarz qo'shish: \\"Ali 100k berdi\\"_\\n"
        msg += "📄 _Kredit qo'shish: KATM PDF yuklang_"
        
    else:
        # RUSSIAN VERSION
        msg = "💳 *DASHBOARD ДОЛГОВ*\\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n"
        
        # SUMMARY BLOCK
        if total_receivable > 0 and total_debt_burden > 0:
            diff = total_receivable - total_debt_burden
            if diff > 0:
                msg += f"📊 *Баланс:* 🟢 +{diff:,.0f} сум\\n\\n"
            else:
                msg += f"📊 *Баланс:* 🔴 {diff:,.0f} сум\\n\\n"
        elif total_receivable > 0:
            msg += f"📊 *Баланс:* 🟢 +{total_receivable:,.0f} сум\\n\\n"
        elif total_debt_burden > 0:
            msg += f"📊 *Баланс:* 🔴 -{total_debt_burden:,.0f} сум\\n\\n"
        else:
            msg += "📊 *Баланс:* ⚪ Долгов нет\\n\\n"
        
        # ========== SECTION 1: ЛИЧНЫЕ ДОЛГИ ==========
        msg += "👥 *ЛИЧНЫЕ ДОЛГИ*\\n"
        msg += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\\n"
        
        if total_lent > 0 or total_borrowed > 0:
            if total_lent > 0:
                msg += f"📤 Вы дали: *{total_lent:,.0f}* ({lent_count})\\n"
                msg += "    _↳ Вам вернут_\\n"
            if total_borrowed > 0:
                msg += f"📥 Вы взяли: *{total_borrowed:,.0f}* ({borrowed_count})\\n"
                msg += "    _↳ Вы вернёте_\\n"
        else:
            msg += "✅ Личных долгов нет\\n"
        
        msg += "\\n"
        
        # ========== SECTION 2: БАНКОВСКИЕ КРЕДИТЫ ==========
        msg += "🏦 *БАНКОВСКИЕ КРЕДИТЫ*\\n"
        msg += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\\n"
        
        if credit_count > 0:
            msg += f"💳 Кредитов: *{credit_count}* шт\\n"
            msg += f"📉 Остаток: *{total_credit_balance:,.0f}* сум\\n"
            msg += f"📆 Ежемесячно: *{total_monthly_payment:,.0f}* сум\\n"
            
            if katm_loans:
                msg += "\\n📋 *Список кредитов:*\\n"
                for i, loan in enumerate(katm_loans[:3], 1):
                    bank = loan.get("bank_name", "Банк")
                    balance = loan.get("remaining_balance", 0) or 0
                    monthly = loan.get("monthly_payment", 0) or 0
                    msg += f"  {i}. {bank}\\n"
                    msg += f"     💵 {balance:,.0f} | 📅 {monthly:,.0f}/мес\\n"
                
                if len(katm_loans) > 3:
                    msg += f"  _...и ещё {len(katm_loans) - 3} шт_\\n"
        else:
            msg += "✅ Банковских кредитов нет\\n"
        
        msg += "\\n━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        msg += "💡 _Добавить долг: \\"Али 100к дал\\"_\\n"
        msg += "📄 _Добавить кредит: загрузите KATM PDF_"
    
'''
    
    # Replace the section
    content = content[:start_idx] + new_code + content[end_idx:]
    
    # Write back
    with open('app/handlers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("SUCCESS: menu_debts_handler fixed!")
    return True


def fix_menu_language():
    """Fix menu_language_handler buttons"""
    
    with open('app/handlers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace language buttons
    old_buttons = '''keyboard = [
        [
            InlineKeyboardButton("рџ‡єрџ‡ї O'zbekcha", callback_data="change_lang_uz"),
            InlineKeyboardButton("рџ‡·рџ‡є Р СѓСЃСЃРєРёР№", callback_data="change_lang_ru")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "рџЊђ Tilni tanlang / Р'С‹Р±РµСЂРёС‚Рµ СЏР·С‹Рє:",'''
    
    new_buttons = '''keyboard = [
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="change_lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="change_lang_ru")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 Tilni tanlang / Выберите язык:",'''
    
    if old_buttons in content:
        content = content.replace(old_buttons, new_buttons)
        with open('app/handlers.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS: menu_language_handler fixed!")
        return True
    else:
        print("WARNING: Could not find language buttons to fix")
        return False


if __name__ == "__main__":
    fix_menu_debts()
    fix_menu_language()
    print("\nAll fixes applied!")
