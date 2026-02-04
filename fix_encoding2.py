# -*- coding: utf-8 -*-
"""Fix all encoding issues in handlers.py"""

with open('app/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix keyboard buttons with encoding issues
fixes = [
    ('рџ'Ґ Shaxsiy qarzlar', '👥 Shaxsiy qarzlar'),
    ('рџ'Ґ Р›РёС‡РЅС‹Рµ РґРѕР»РіРё', '👥 Личные долги'),
    ('рџЏ¦ Kreditlar', '🏦 Kreditlar'),
    ('рџЏ¦ РљСЂРµРґРёС‚С‹', '🏦 Кредиты'),
    ('вћ• Qarz', '➕ Qarz'),
    ('вћ• Р"РѕР±Р°РІРёС‚СЊ', '➕ Добавить'),
    ('рџ"„ KATM', '📄 KATM'),
    ('рџ"„ Р—Р°РіСЂСѓР·РёС‚СЊ', '📄 Загрузить'),
    ('рџ‡єрџ‡ї', '🇺🇿'),
    ('рџ‡·рџ‡є', '🇷🇺'),
    ('рџЊђ Tilni tanlang', '🌐 Tilni tanlang'),
    ('Р'С‹Р±РµСЂРёС‚Рµ СЏР·С‹Рє', 'Выберите язык'),
    ('Р СѓСЃСЃРєРёР№', 'Русский'),
    # Common broken patterns
    ('рџ'¤', '👤'),
    ('рџ'Ћ', '💎'),
    ('рџ"Љ', '📊'),
    ('рџ'°', '💰'),
    ('рџ'і', '💳'),
    ('рџ"…', '📅'),
    ('рџ"†', '📆'),
    ('рџ"‰', '📉'),
    ('рџ"‹', '📋'),
    ('рџ'µ', '💵'),
    ('вњ…', '✅'),
    ('вћ•', '➕'),
    ('вћ–', '➖'),
    ('вќ"', '❓'),
    ('рџ'Ґ', '👥'),
    ('рџЏ¦', '🏦'),
    ('рџ"¤', '📤'),
    ('рџ"Ґ', '📥'),
]

count = 0
for old, new in fixes:
    if old in content:
        content = content.replace(old, new)
        count += 1
        print(f'Fixed: {repr(old)} -> {new}')

with open('app/handlers.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nTotal fixes: {count}')
print('Done!')
