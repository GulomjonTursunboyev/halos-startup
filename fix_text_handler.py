# -*- coding: utf-8 -*-
"""
Fix 2 issues in handlers.py:
1. Remove duplicate parse_debt_transaction block in voice handler (lines ~7930)
2. Fix text handler (line ~8351) to support ALL users and add reply for no-amount messages
"""

file_path = r'c:\Users\ANUBIS PC\Desktop\Halos 2\halos\temp_git_repos\halos-startup\app\handlers.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

# ===== FIX 1: Remove duplicate parse_debt_transaction =====
debt_parse_lines = []
for i, line in enumerate(lines):
    if 'debt_info = await parse_debt_transaction(text, lang)' in line:
        debt_parse_lines.append(i)

print(f"Found parse_debt_transaction at lines: {[x+1 for x in debt_parse_lines]}")

fix1_start = None
fix1_end = None

if len(debt_parse_lines) >= 2:
    fix1_start = debt_parse_lines[1]  # Second occurrence (duplicate)
    for i in range(fix1_start, fix1_start + 50):
        if 'QOLGAN HOLAT' in lines[i]:
            fix1_end = i
            break
    print(f"FIX1: Will remove lines {fix1_start+1} to {fix1_end}")

# ===== FIX 2: Fix text handler in ai_text_handler =====
# Find "if not transactions:" INSIDE ai_text_handler (after line 8300)
fix2_start = None
fix2_end = None

for i in range(8300, 8500):
    stripped = lines[i].rstrip('\r\n')
    if stripped == '        if not transactions:':
        fix2_start = i
        print(f"FIX2: Found 'if not transactions:' at line {i+1}")
        break

if fix2_start is not None:
    # Find end: "            return" at 12-space indent that closes the outer if
    for i in range(fix2_start + 2, fix2_start + 40):
        stripped = lines[i].rstrip('\r\n')
        if stripped == '            return' and lines[i-1].rstrip('\r\n').endswith('return'):
            # Two consecutive returns - inner then outer
            fix2_end = i + 1
            print(f"FIX2: End at line {fix2_end} (two returns pattern)")
            break
    
    if fix2_end is None:
        # Alternative: look for line that is just "            return" followed by blank/Get budget
        for i in range(fix2_start + 2, fix2_start + 40):
            stripped = lines[i].rstrip('\r\n')
            if stripped == '            return':
                next_stripped = lines[i+1].rstrip('\r\n').strip() if i+1 < len(lines) else ''
                if next_stripped == '' or 'Get budget' in next_stripped or 'budget' in next_stripped:
                    fix2_end = i + 1
                    print(f"FIX2: End at line {fix2_end} (return + blank/budget)")
                    break

# Show what we found
if fix2_start is not None and fix2_end is not None:
    print(f"\nFIX2 block (lines {fix2_start+1} to {fix2_end}):")
    for i in range(fix2_start, fix2_end):
        print(f"  {i+1}: {lines[i].rstrip()[:80]}")

# Apply fixes
if fix1_start is not None and fix1_end is not None and fix2_start is not None and fix2_end is not None:
    print("\nApplying fixes...")
    
    new_lines = []
    i = 0
    while i < len(lines):
        if i == fix1_start:
            # Skip duplicate block
            print(f"  Skipping duplicate debt lines {fix1_start+1} to {fix1_end}")
            i = fix1_end
            continue
        elif i == fix2_start:
            # Replace text handler block
            print(f"  Replacing text handler lines {fix2_start+1} to {fix2_end}")
            
            new_lines.append('        if not transactions:\r\n')
            new_lines.append('            # ==================== ODDIY PARSING (PRO VA BEPUL) ====================\r\n')
            new_lines.append('            # Oddiy regex bilan parse qilish\r\n')
            new_lines.append('            simple_tx = await simple_parse_transaction(text, lang)\r\n')
            new_lines.append('            if simple_tx:\r\n')
            new_lines.append('                transaction_id = await save_transaction(db, user["id"], simple_tx)\r\n')
            new_lines.append('                \r\n')
            new_lines.append('                # Qisqa xabar\r\n')
            new_lines.append('                emoji = "\U0001f4c9" if simple_tx["type"] == "expense" else "\U0001f4c8"\r\n')
            new_lines.append('                amount = simple_tx["amount"]\r\n')
            new_lines.append('                desc = simple_tx.get("description", "")\r\n')
            new_lines.append('                \r\n')
            new_lines.append('                # Bugungi balansni hisoblash\r\n')
            new_lines.append('                from app.ai_assistant import get_transaction_summary\r\n')
            new_lines.append('                today_summary = await get_transaction_summary(db, user["id"], days=1)\r\n')
            new_lines.append('                today_balance = today_summary.get("total_income", 0) - today_summary.get("total_expense", 0)\r\n')
            new_lines.append('                \r\n')
            new_lines.append('                if lang == "uz":\r\n')
            new_lines.append("                    msg = f\"{emoji} *{desc}* \u2014 {amount:,} so'm\\n\U0001f4c9 Bugun: {today_balance:+,}\"\r\n")
            new_lines.append('                else:\r\n')
            new_lines.append('                    msg = f"{emoji} *{desc}* \u2014 {amount:,} \u0441\u0443\u043c\\n\U0001f4c9 \u0421\u0435\u0433\u043e\u0434\u043d\u044f: {today_balance:+,}"\r\n')
            new_lines.append('                \r\n')
            new_lines.append('                keyboard = [\r\n')
            new_lines.append('                    [\r\n')
            new_lines.append('                        InlineKeyboardButton(\r\n')
            new_lines.append("                            \"\u2705 To'g'ri\" if lang == \"uz\" else \"\u2705 \u0412\u0435\u0440\u043d\u043e\",\r\n")
            new_lines.append('                            callback_data="ai_confirm_ok"\r\n')
            new_lines.append('                        ),\r\n')
            new_lines.append('                        InlineKeyboardButton(\r\n')
            new_lines.append("                            \"\u274c Noto'g'ri\" if lang == \"uz\" else \"\u274c \u041d\u0435\u0432\u0435\u0440\u043d\u043e\",\r\n")
            new_lines.append('                            callback_data=f"ai_correct_{transaction_id}"\r\n')
            new_lines.append('                        )\r\n')
            new_lines.append('                    ]\r\n')
            new_lines.append('                ]\r\n')
            new_lines.append('                \r\n')
            new_lines.append('                await update.message.reply_text(\r\n')
            new_lines.append('                    msg, \r\n')
            new_lines.append('                    parse_mode="Markdown",\r\n')
            new_lines.append('                    reply_markup=InlineKeyboardMarkup(keyboard)\r\n')
            new_lines.append('                )\r\n')
            new_lines.append('                return\r\n')
            new_lines.append('            else:\r\n')
            new_lines.append('                # Hech qanday summa topilmadi - oddiy xabar\r\n')
            new_lines.append('                if len(text) < 200:\r\n')
            new_lines.append('                    if lang == "uz":\r\n')
            new_lines.append('                        msg = (\r\n')
            new_lines.append('                            "\U0001f4a1 *Xabaringiz qabul qilindi!*\\n\\n"\r\n')
            new_lines.append('                            "Tranzaksiya yozish uchun summa yozing:\\n"\r\n')
            new_lines.append("                            '_\"choy 5000\" yoki \"maosh 3 mln\"_\\n\\n'\r\n")
            new_lines.append("                            \"\U0001f4ca Hisobotingizni ko'rish uchun \U0001f4ca *Hisobotlar* tugmasini bosing.\"\r\n")
            new_lines.append('                        )\r\n')
            new_lines.append('                    else:\r\n')
            new_lines.append('                        msg = (\r\n')
            new_lines.append('                            "\U0001f4a1 *\u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u043e!*\\n\\n"\r\n')
            new_lines.append('                            "\u0414\u043b\u044f \u0437\u0430\u043f\u0438\u0441\u0438 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0441\u0443\u043c\u043c\u0443:\\n"\r\n')
            new_lines.append("                            '_\"\u0447\u0430\u0439 5000\" \u0438\u043b\u0438 \"\u0437\u0430\u0440\u043f\u043b\u0430\u0442\u0430 3 \u043c\u043b\u043d\"_\\n\\n'\r\n")
            new_lines.append('                            "\U0001f4ca \u0414\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430 \u043e\u0442\u0447\u0451\u0442\u0430 \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \U0001f4ca *\u041e\u0442\u0447\u0451\u0442\u044b*."\r\n')
            new_lines.append('                        )\r\n')
            new_lines.append('                    await update.message.reply_text(msg, parse_mode="Markdown")\r\n')
            new_lines.append('                return\r\n')
            
            i = fix2_end
            continue
        
        new_lines.append(lines[i])
        i += 1
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"\nNew file: {len(new_lines)} lines (was {len(lines)})")
    print("SUCCESS!")
else:
    print(f"\nFAILED!")
    print(f"  fix1_start={fix1_start}, fix1_end={fix1_end}")
    print(f"  fix2_start={fix2_start}, fix2_end={fix2_end}")
