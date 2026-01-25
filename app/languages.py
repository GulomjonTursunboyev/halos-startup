"""
HALOS Language Dictionaries
Uzbek and Russian translations for all bot messages
"""

MESSAGES = {
    "trial_already_used": {
        "uz": "❗️ Siz allaqachon 3 kunlik bepul PRO sinovidan foydalandingiz.",
        "ru": "❗️ Вы уже использовали 3-дневный бесплатный PRO."
    },
    # ==================== WELCOME & REGISTRATION ====================
    "welcome": {
        "uz": (
            "✨ *HALOS* ga xush kelibsiz\n\n"
            "Sizni moliyaviy yukdan xalos bo'lib, o'z boyligingizni qurish yo'liga olib chiqaman.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *HALOS sizga yordam beradi:*\n\n"
            "🕊 Moliyaviy yukdan *qachon* xalos bo'lishni ko'rsatadi\n"
            "💎 Oylik *qancha* shaxsiy kapital ortira olishingizni hisoblaydi\n"
            "🌅 *Moliyaviy tinchlik* yo'lingizni tuzadi\n"
            "📊 Statistika va *batafsil hisobotlar*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Boshlash uchun* ro'yxatdan o'ting 👇"
        ),
        "ru": (
            "✨ Добро пожаловать в *HALOS*\n\n"
            "Помогу вам выйти из финансового бремени и начать строить собственный капитал.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *HALOS поможет вам:*\n\n"
            "🕊 Показать *когда* вы освободитесь от бремени\n"
            "💎 Рассчитать *сколько* личного капитала сможете создать\n"
            "🌅 Построить путь к *финансовому спокойствию*\n"
            "📊 Статистика и *детальные отчёты*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Чтобы начать* зарегистрируйтесь 👇"
        )
    },
    
    "share_contact_button": {
        "uz": "📱 Ro'yxatdan o'tish",
        "ru": "📱 Зарегистрироваться"
    },
    
    "contact_received": {
        "uz": "✅ Rahmat! Ro'yxatdan muvaffaqiyatli o'tdingiz.",
        "ru": "✅ Спасибо! Вы успешно зарегистрированы."
    },
    
    "contact_required": {
        "uz": "📱 Iltimos, davom etish uchun ro'yxatdan o'ting.",
        "ru": "📱 Пожалуйста, зарегистрируйтесь для продолжения."
    },
    
    # ==================== LANGUAGE SELECTION ====================
    "select_language": {
        "uz": "🌐 Tilni tanlang:",
        "ru": "🌐 Выберите язык:"
    },
    
    "language_set": {
        "uz": "✅ Til o'rnatildi: O'zbekcha",
        "ru": "✅ Язык установлен: Русский"
    },
    
    # ==================== MODE SELECTION ====================
    "select_mode": {
        "uz": (
            "👥 *Rejim tanlang*\n\n"
            "• *Yolg'iz* — faqat o'zingiz\n"
            "• *Oila* — siz va turmush o'rtog'ingiz"
        ),
        "ru": (
            "👥 *Выберите режим*\n\n"
            "• *Один* — только вы\n"
            "• *Семья* — вы и ваш партнёр"
        )
    },
    
    "mode_solo": {
        "uz": "👤 Yolg'iz",
        "ru": "👤 Один"
    },
    
    "mode_family": {
        "uz": "👨‍👩‍� Oila",
        "ru": "👨‍👩‍👦 Семья"
    },
    
    "mode_set_solo": {
        "uz": "✅ Yolg'iz rejim tanlandi",
        "ru": "✅ Выбран режим «Один»"
    },
    
    "mode_set_family": {
        "uz": "✅ Oila rejimi tanlandi",
        "ru": "✅ Выбран режим «Семья»"
    },
    
    # ==================== TRANSACTION HISTORY UPLOAD ====================
    "transaction_choice": {
        "uz": (
            "💳 *Karta tarixini yuklaysizmi?*\n\n"
            "Bank kartangiz tarixini yuklasangiz, daromad va xarajatlaringizni avtomatik aniqlayman.\n\n"
            "Quyidagi formatlar qo'llab-quvvatlanadi:\n"
            "• PDF, HTML, Excel, TXT, CSV\n\n"
            "📱 Click, Payme, Uzcard, Humo va boshqa banklar"
        ),
        "ru": (
            "💳 *Загрузить историю карты?*\n\n"
            "Если загрузите историю банковской карты, я автоматически определю ваши доходы и расходы.\n\n"
            "Поддерживаемые форматы:\n"
            "• PDF, HTML, Excel, TXT, CSV\n\n"
            "📱 Click, Payme, Uzcard, Humo и другие банки"
        )
    },
    
    "transaction_yes": {
        "uz": "📤 Ha, tarix yuklash",
        "ru": "📤 Да, загрузить историю"
    },
    
    "transaction_no": {
        "uz": "✍️ Yo'q, qo'lda kiritaman",
        "ru": "✍️ Нет, введу вручную"
    },
    
    "transaction_instructions": {
        "uz": (
            "📋 *Karta tarixini yuklang*\n\n"
            "Bir nechta karta tarixini yuklashingiz mumkin!\n\n"
            "*Click:*\n"
            "Tarix → Yuklab olish → HTML/PDF\n\n"
            "*Payme:*\n"
            "Tarix → Eksport → PDF\n\n"
            "*Bank ilovasi:*\n"
            "Karta tarixi → Yuklab olish\n\n"
            "📎 Birinchi faylni yuboring\n"
            "_(PDF, HTML, Excel, TXT, CSV)_"
        ),
        "ru": (
            "📋 *Загрузите историю карты*\n\n"
            "Вы можете загрузить историю нескольких карт!\n\n"
            "*Click:*\n"
            "История → Скачать → HTML/PDF\n\n"
            "*Payme:*\n"
            "История → Экспорт → PDF\n\n"
            "*Банковское приложение:*\n"
            "История карты → Скачать\n\n"
            "📎 Отправьте первый файл\n"
            "_(PDF, HTML, Excel, TXT, CSV)_"
        )
    },
    
    "transaction_processing": {
        "uz": "⏳ Fayl qayta ishlanmoqda...",
        "ru": "⏳ Обрабатываю файл..."
    },
    
    "transaction_success": {
        "uz": (
            "✅ *Karta tarixi muvaffaqiyatli o'qildi!*\n\n"
            "📊 *{period}* davri uchun:\n\n"
            "💰 *Kirimlar:* {income_count} ta\n"
            "   Jami: {total_income} so'm\n"
            "   Oyiga: ~{monthly_income} so'm\n\n"
            "💸 *Chiqimlar:* {expense_count} ta\n"
            "   Jami: {total_expense} so'm\n"
            "   Oyiga: ~{monthly_expense} so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Oylik taxminiy:*\n"
            "• Daromad: {monthly_income} so'm\n"
            "• Xarajat: {monthly_expense} so'm"
        ),
        "ru": (
            "✅ *История карты успешно прочитана!*\n\n"
            "📊 *Период {period}:*\n\n"
            "💰 *Поступления:* {income_count} шт\n"
            "   Всего: {total_income} сум\n"
            "   В месяц: ~{monthly_income} сум\n\n"
            "💸 *Расходы:* {expense_count} шт\n"
            "   Всего: {total_expense} сум\n"
            "   В месяц: ~{monthly_expense} сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Примерно в месяц:*\n"
            "• Доход: {monthly_income} сум\n"
            "• Расход: {monthly_expense} сум"
        )
    },
    
    "transaction_categories": {
        "uz": (
            "\n📂 *Xarajatlar bo'yicha:*\n"
            "{categories}"
        ),
        "ru": (
            "\n📂 *По категориям расходов:*\n"
            "{categories}"
        )
    },
    
    "transaction_failed": {
        "uz": (
            "⚠️ *Faylni o'qib bo'lmadi*\n\n"
            "Fayl formati noto'g'ri yoki ma'lumotlar topilmadi.\n\n"
            "Iltimos, boshqa format yuboring yoki qo'lda kiriting."
        ),
        "ru": (
            "⚠️ *Не удалось прочитать файл*\n\n"
            "Неверный формат файла или данные не найдены.\n\n"
            "Пожалуйста, отправьте другой формат или введите вручную."
        )
    },
    
    "transaction_invalid_file": {
        "uz": "❌ Iltimos, qo'llab-quvvatlanadigan fayl yuboring (PDF, HTML, Excel, TXT, CSV).",
        "ru": "❌ Пожалуйста, отправьте поддерживаемый файл (PDF, HTML, Excel, TXT, CSV)."
    },
    
    "transaction_use_data": {
        "uz": "Bu ma'lumotlardan foydalanaylikmi?",
        "ru": "Использовать эти данные?"
    },
    
    "transaction_confirm_yes": {
        "uz": "✅ Ha, foydalanish",
        "ru": "✅ Да, использовать"
    },
    
    "transaction_confirm_no": {
        "uz": "✏️ Yo'q, qo'lda kiritaman",
        "ru": "✏️ Нет, введу вручную"
    },
    
    "transaction_income_used": {
        "uz": "✅ Daromad avtomatik aniqlandi: {amount} so'm/oy",
        "ru": "✅ Доход определён автоматически: {amount} сум/мес"
    },
    
    # Multi-card support
    "transaction_card_added": {
        "uz": (
            "✅ *Karta #{card_num} qo'shildi: {card_name}*\n\n"
            "📊 *{period}*\n"
            "💰 Kirim: {income_count} ta ({total_income} so'm)\n"
            "💸 Chiqim: {expense_count} ta ({total_expense} so'm)\n\n"
            "━━━━━━━━━━━━━━━━━━"
        ),
        "ru": (
            "✅ *Карта #{card_num} добавлена: {card_name}*\n\n"
            "📊 *{period}*\n"
            "💰 Доход: {income_count} шт ({total_income} сум)\n"
            "💸 Расход: {expense_count} шт ({total_expense} сум)\n\n"
            "━━━━━━━━━━━━━━━━━━"
        )
    },
    
    "transaction_add_more": {
        "uz": "📤 Yana karta qo'shish",
        "ru": "📤 Добавить ещё карту"
    },
    
    "transaction_finish_cards": {
        "uz": "✅ Tugatish va ko'rish",
        "ru": "✅ Завершить и посмотреть"
    },
    
    "transaction_add_more_prompt": {
        "uz": "Yana boshqa karta tarixini yuklashni xohlaysizmi?",
        "ru": "Хотите загрузить ещё одну карту?"
    },
    
    "transaction_multi_summary": {
        "uz": (
            "📊 *BARCHA KARTALAR BO'YICHA HISOBOT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "{card_details}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📈 *UMUMIY NATIJA:*\n\n"
            "💰 *Jami kirimlar:* {total_income} so'm\n"
            "💸 *Jami chiqimlar:* {total_expense} so'm\n"
            "📊 *Balans:* {balance} so'm\n\n"
            "📅 *Oylik o'rtacha:*\n"
            "• Daromad: ~{monthly_income} so'm\n"
            "• Xarajat: ~{monthly_expense} so'm\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "ru": (
            "📊 *ОТЧЁТ ПО ВСЕМ КАРТАМ*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "{card_details}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📈 *ОБЩИЙ ИТОГ:*\n\n"
            "💰 *Всего поступлений:* {total_income} сум\n"
            "💸 *Всего расходов:* {total_expense} сум\n"
            "📊 *Баланс:* {balance} сум\n\n"
            "📅 *В среднем за месяц:*\n"
            "• Доход: ~{monthly_income} сум\n"
            "• Расход: ~{monthly_expense} сум\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    },
    
    "transaction_card_detail": {
        "uz": (
            "💳 *{card_name}*\n"
            "   💰 Kirim: {total_income} so'm\n"
            "   💸 Chiqim: {total_expense} so'm\n"
        ),
        "ru": (
            "💳 *{card_name}*\n"
            "   💰 Доход: {total_income} сум\n"
            "   💸 Расход: {total_expense} сум\n"
        )
    },
    
    "transaction_monthly_breakdown": {
        "uz": (
            "\n📅 *Oylar bo'yicha:*\n"
            "{months}"
        ),
        "ru": (
            "\n📅 *По месяцам:*\n"
            "{months}"
        )
    },
    
    "transaction_month_row": {
        "uz": "• {month}: +{income} / -{expense}",
        "ru": "• {month}: +{income} / -{expense}"
    },
    
    "transaction_summary_confirm": {
        "uz": "Bu ma'lumotlar to'g'rimi?",
        "ru": "Эти данные верны?"
    },
    
    "transaction_summary_confirm_yes": {
        "uz": "✅ Ha, to'g'ri",
        "ru": "✅ Да, верно"
    },
    
    "transaction_summary_add_income": {
        "uz": "➕ Qo'shimcha daromad qo'shish",
        "ru": "➕ Добавить дополнительный доход"
    },
    
    "transaction_summary_manual": {
        "uz": "✏️ Qo'lda kiritish",
        "ru": "✏️ Ввести вручную"
    },
    
    "transaction_extra_income_prompt": {
        "uz": (
            "💰 *Qo'shimcha daromad*\n\n"
            "Kartada ko'rinmagan oylik daromadingiz bormi?\n"
            "(Masalan: naqd maosh, ijara daromadi va h.k.)\n\n"
            "Miqdorni kiriting yoki `0` bosing."
        ),
        "ru": (
            "💰 *Дополнительный доход*\n\n"
            "Есть ли у вас доход, который не отображается на карте?\n"
            "(Например: наличная зарплата, аренда и т.д.)\n\n"
            "Введите сумму или нажмите `0`."
        )
    },
    
    # ==================== INCOME INPUT ====================
    "input_income_self": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QADAM 1/5 — DAROMAD*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *O'zingizning oylik maoshingiz*\n\n"
            "Raqam yozing yoki karta tarixi faylini yuboring.\n"
            "Bot avtomatik aniqlaydi.\n\n"
            "📝 Masalan: `5000000` yoki `5 mln`\n"
            "📎 Yoki: PDF, HTML, Excel fayl"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ШАГ 1/5 — ДОХОД*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *Ваша ежемесячная зарплата*\n\n"
            "Напишите число или отправьте файл истории карты.\n"
            "Бот определит автоматически.\n\n"
            "📝 Например: `5000000` или `5 млн`\n"
            "📎 Или: PDF, HTML, Excel файл"
        )
    },
    
    "input_income_partner": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QADAM 2/5 — JUFT DAROMADI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *Turmush o'rtog'ingizning oylik maoshi*\n\n"
            "Raqam yozing yoki fayl yuboring.\n\n"
            "📝 Masalan: `3000000`\n"
            "📎 Yoki: PDF, HTML, Excel fayl"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ШАГ 2/5 — ДОХОД ПАРТНЁРА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *Зарплата вашего супруга/супруги*\n\n"
            "Напишите число или отправьте файл.\n\n"
            "📝 Например: `3000000`\n"
            "📎 Или: PDF, HTML, Excel файл"
        )
    },
    
    "btn_partner_no_income": {
        "uz": "🚫 Ishlamaydi / Daromadi yo'q",
        "ru": "🚫 Не работает / Нет дохода"
    },
    
    "income_saved": {
        "uz": "✅ Daromad saqlandi: {amount} so'm",
        "ru": "✅ Доход сохранён: {amount} сум"
    },
    
    # ==================== MANDATORY LIVING COSTS ====================
    "input_rent": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QADAM 3/5 — UY IJARASI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏠 *Oylik ijara haqi*\n\n"
            "📝 Raqam yozing: `2000000`\n"
            "🏡 O'z uyingiz bo'lsa: `0`"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ШАГ 3/5 — АРЕНДА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏠 *Ежемесячная аренда*\n\n"
            "📝 Напишите число: `2000000`\n"
            "🏡 Если своё жильё: `0`"
        )
    },
    
    "btn_own_home": {
        "uz": "🏡 O'z uyimda yashayman",
        "ru": "🏡 Живу в своём жилье"
    },
    
    "input_kindergarten": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QADAM 4/5 — MAJBURIY TO'LOVLAR*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 *Boshqa majburiy to'lovlar:*\n\n"
            "• 👶 Bog'cha / Maktab to'lovi\n"
            "• 🏥 Sug'urta (avto, uy, hayot)\n"
            "• 📚 Kurslar, repetitor\n"
            "• 🚗 Transport (benzin, avtobus)\n"
            "• 💊 Doimiy dori-darmonlar\n\n"
            "📝 Jami oylik summa: `500000`\n"
            "❌ Yo'q bo'lsa: `0`"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ШАГ 4/5 — ОБЯЗАТЕЛЬНЫЕ ПЛАТЕЖИ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 *Другие обязательные платежи:*\n\n"
            "• 👶 Детсад / Школа\n"
            "• 🏥 Страховка (авто, дом, жизнь)\n"
            "• 📚 Курсы, репетитор\n"
            "• 🚗 Транспорт (бензин, автобус)\n"
            "• 💊 Регулярные лекарства\n\n"
            "📝 Итого в месяц: `500000`\n"
            "❌ Если нет: `0`"
        )
    },
    
    "btn_no_kids": {
        "uz": "❌ Bunday to'lovlarim yo'q",
        "ru": "❌ Таких платежей нет"
    },
    
    "input_utilities": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QADAM 5/5 — KOMMUNAL*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 *Elektr, gaz, suv, internet*\n\n"
            "📝 Jami oylik: `400000`\n"
            "💡 O'rtacha: 300K - 800K so'm"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ШАГ 5/5 — КОММУНАЛКА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 *Электр, газ, вода, интернет*\n\n"
            "📝 Всего в месяц: `400000`\n"
            "💡 Обычно: 300K - 800K сум"
        )
    },
    
    "btn_utilities_300": {
        "uz": "💡 ~300 000",
        "ru": "💡 ~300 000"
    },
    
    "btn_utilities_500": {
        "uz": "💡 ~500 000",
        "ru": "💡 ~500 000"
    },
    
    "btn_utilities_800": {
        "uz": "💡 ~800 000",
        "ru": "💡 ~800 000"
    },
    
    "cost_saved": {
        "uz": "✅ Saqlandi: {amount} so'm",
        "ru": "✅ Сохранено: {amount} сум"
    },
    
    # ==================== KATM PDF UPLOAD ====================
    "katm_choice": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *KREDIT TARIXI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📄 *KATM kredit tarixingizni yuklang*\n\n"
            "infokredit.uz dan olingan faylni yuboring.\n"
            "PDF yoki HTML format qabul qilinadi.\n\n"
            "🔄 Yoki qo'lda kredit ma'lumotlarini kiriting."
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *КРЕДИТНАЯ ИСТОРИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📄 *Загрузите историю из KATM*\n\n"
            "Отправьте файл с infokredit.uz.\n"
            "Принимается PDF или HTML формат.\n\n"
            "🔄 Или введите данные о кредитах вручную."
        )
    },
    
    "katm_yes": {
        "uz": "📤 Fayl yuklash (PDF/HTML)",
        "ru": "📤 Загрузить файл (PDF/HTML)"
    },
    
    "katm_no": {
        "uz": "✍️ Qo'lda kiritaman",
        "ru": "✍️ Введу вручную"
    },
    
    "katm_instructions": {
        "uz": (
            "📋 *KATM dan kredit tarixini olish:*\n\n"
            "1️⃣ infokredit.uz saytiga kiring\n"
            "2️⃣ OneID orqali tizimga kiring\n"
            "3️⃣ \"Kredit tarixi\" → \"Yuklab olish\"\n"
            "4️⃣ *PDF yoki HTML* faylni yuklab oling\n"
            "5️⃣ *Shu yerga yuboring* 👇\n\n"
            "📎 PDF yoki HTML faylni kutayapman..."
        ),
        "ru": (
            "📋 *Как получить кредитную историю из KATM:*\n\n"
            "1️⃣ Зайдите на infokredit.uz\n"
            "2️⃣ Войдите через OneID\n"
            "3️⃣ «Кредитная история» → «Скачать»\n"
            "4️⃣ Скачайте *PDF или HTML* файл\n"
            "5️⃣ *Отправьте его сюда* 👇\n\n"
            "📎 Жду PDF или HTML файл..."
        )
    },
    
    "katm_processing": {
        "uz": "⏳ Fayl qayta ishlanmoqda...",
        "ru": "⏳ Обрабатываю файл..."
    },
    
    "katm_success": {
        "uz": (
            "✅ *Kredit tarixi muvaffaqiyatli o'qildi!*\n\n"
            "🏦 *Topilgan kreditlar:*\n"
            "{loans_list}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Jami qarz:* {total_debt} so'm\n"
            "💳 *Oylik to'lov:* {monthly_payment} so'm"
        ),
        "ru": (
            "✅ *Кредитная история успешно прочитана!*\n\n"
            "🏦 *Найденные кредиты:*\n"
            "{loans_list}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Общий долг:* {total_debt} сум\n"
            "💳 *Ежемесячный платёж:* {monthly_payment} сум"
        )
    },
    
    "katm_loan_item": {
        "uz": "• {bank}: {amount} so'm",
        "ru": "• {bank}: {amount} сум"
    },
    
    "katm_failed": {
        "uz": (
            "⚠️ *PDF ni o'qib bo'lmadi*\n\n"
            "Fayl formati noto'g'ri yoki ma'lumotlar topilmadi.\n\n"
            "Iltimos, qarz ma'lumotlarini qo'lda kiriting."
        ),
        "ru": (
            "⚠️ *Не удалось прочитать PDF*\n\n"
            "Неверный формат файла или данные не найдены.\n\n"
            "Пожалуйста, введите данные о кредитах вручную."
        )
    },
    
    "katm_not_pdf": {
        "uz": "❌ Iltimos, PDF yoki HTML fayl yuboring.",
        "ru": "❌ Пожалуйста, отправьте PDF или HTML файл."
    },
    
    "katm_confirm": {
        "uz": "Bu ma'lumotlar to'g'rimi?",
        "ru": "Эти данные верны?"
    },
    
    "katm_confirm_yes": {
        "uz": "✅ Ha, davom etish",
        "ru": "✅ Да, продолжить"
    },
    
    "katm_confirm_no": {
        "uz": "✏️ Yo'q, o'zgartirish",
        "ru": "✏️ Нет, изменить"
    },
    
    "katm_skip": {
        "uz": "⏭ O'tkazib yuborish",
        "ru": "⏭ Пропустить"
    },
    
    # ==================== CREDIT HISTORY CHOICE ====================
    "credit_history_choice": {
        "uz": (
            "🏦 *Kredit ma'lumotlari*\n\n"
            "Kredit tarixingizni qanday kiritmoqchisiz?\n\n"
            "📄 *Kredit tarixi* — infokredit.uz dan yuklab olingan HTML/PDF fayl\n"
            "✏️ *Qo'lda kiritish* — ma'lumotlarni o'zingiz yozasiz"
        ),
        "ru": (
            "🏦 *Данные о кредитах*\n\n"
            "Как хотите ввести кредитную историю?\n\n"
            "📄 *Кредитная история* — HTML/PDF файл с infokredit.uz\n"
            "✏️ *Ввести вручную* — введёте данные сами"
        )
    },
    
    "btn_upload_credit": {
        "uz": "📄 Kredit tarixi yuklash",
        "ru": "📄 Загрузить кредитную историю"
    },
    
    "btn_manual_credit": {
        "uz": "✏️ Qo'lda kiritish",
        "ru": "✏️ Ввести вручную"
    },
    
    "btn_no_credit": {
        "uz": "✨ Kreditim yo'q",
        "ru": "✨ Нет кредитов"
    },
    
    "upload_credit_file": {
        "uz": (
            "📄 *Kredit tarixini yuklang*\n\n"
            "infokredit.uz dan olingan HTML yoki PDF faylni yuboring.\n\n"
            "💡 Fayl avtomatik tahlil qilinadi va ma'lumotlar olinadi."
        ),
        "ru": (
            "📄 *Загрузите кредитную историю*\n\n"
            "Отправьте HTML или PDF файл с infokredit.uz.\n\n"
            "💡 Файл будет автоматически проанализирован."
        )
    },
    
    # ==================== LOAN INPUT ====================
    "input_loan_payment": {
        "uz": (
            "🏦 *Oylik kredit to'lovi*\n\n"
            "Barcha kreditlar bo'yicha oylik to'lovni kiriting (so'mda).\n\n"
            "Kreditingiz yo'qmi — pastdagi tugmani bosing."
        ),
        "ru": (
            "🏦 *Ежемесячный платёж по кредитам*\n\n"
            "Введите общий ежемесячный платёж по всем кредитам (в сумах).\n\n"
            "Нет кредитов — нажмите кнопку ниже."
        )
    },
    
    "btn_no_loans": {
        "uz": "✨ Kreditim yo'q",
        "ru": "✨ Нет кредитов"
    },
    
    "input_total_debt": {
        "uz": (
            "📊 *Jami qarz qoldig'i*\n\n"
            "Barcha kreditlar bo'yicha umumiy qarz qoldig'ini kiriting (so'mda).\n\n"
            "Masalan: `50 000 000`"
        ),
        "ru": (
            "📊 *Общий остаток долга*\n\n"
            "Введите общую сумму оставшегося долга по всем кредитам (в сумах).\n\n"
            "Например: `50 000 000`"
        )
    },
    
    "btn_no_debt": {
        "uz": "✨ Qarzim yo'q",
        "ru": "✨ Нет долгов"
    },
    
    "debt_saved": {
        "uz": "✅ Qarz ma'lumotlari saqlandi",
        "ru": "✅ Данные о долге сохранены"
    },
    
    # ==================== VALIDATION ====================
    "invalid_number": {
        "uz": "❌ Iltimos, faqat raqam kiriting. Masalan: `5000000`",
        "ru": "❌ Пожалуйста, введите только число. Например: `5000000`"
    },
    
    "number_too_small": {
        "uz": "❌ Raqam 0 dan katta bo'lishi kerak.",
        "ru": "❌ Число должно быть больше 0."
    },
    
    "number_negative": {
        "uz": "❌ Manfiy raqam kiritish mumkin emas.",
        "ru": "❌ Нельзя вводить отрицательные числа."
    },
    
    # ==================== CALCULATION & RESULTS ====================
    "calculating": {
        "uz": "⏳ Hisoblanmoqda...",
        "ru": "⏳ Рассчитываем..."
    },
    
    "result_debt_mode": {
        "uz": (
            "🌟 *SIZNING HALOS SANANGIZ*\n\n"
            "Siz *{exit_date}* da moliyaviy erkinlikka erishasiz.\n\n"
            "Shu yo'lda davom etsangiz, {exit_months} oy ichida\n"
            "*{savings_exit}* so'm shaxsiy kapital qurasiz.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Oylik balans:*\n\n"
            "💳 Yukni to'lash: *{debt_payment}* so'm\n"
            "💎 Kapital qurish: *{savings}* so'm\n"
            "🏠 Xotirjam yashash: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Sizning yo'lingiz:*\n\n"
            "• 12 oyda kapital: *{savings_12}* so'm\n"
            "• HALOS sanangizda: *{savings_exit}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Har bir qadam sizni yengillikka yaqinlashtiradi.\n"
            "Tinch nafas oling — siz to'g'ri yo'ldasiz."
        ),
        "ru": (
            "🌟 *ВАША ДАТА HALOS*\n\n"
            "Вы достигнете финансовой свободы *{exit_date}*.\n\n"
            "Следуя этому пути, за {exit_months} мес\n"
            "создадите *{savings_exit}* сум личного капитала.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Ежемесячный баланс:*\n\n"
            "💳 Погашение бремени: *{debt_payment}* сум\n"
            "💎 Рост капитала: *{savings}* сум\n"
            "🏠 Спокойная жизнь: *{living}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Ваш путь:*\n\n"
            "• Капитал за 12 мес: *{savings_12}* сум\n"
            "• К дате HALOS: *{savings_exit}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Каждый шаг приближает вас к лёгкости.\n"
            "Вдохните спокойно — вы на верном пути."
        )
    },
    
    "result_debt_mode_partial": {
        "uz": (
            "� *SIZNING ERKINLIK YO'LINGIZ*\n\n"
            "📊 *Oylik taqsimot:*\n\n"
            "💳 Qarz to'lovi: *{debt_payment}* so'm\n"
            "💰 Jamg'arma: *{savings}* so'm\n"
            "🏠 Yashash uchun: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔒 *To'liq rejani ochish uchun PRO:*\n\n"
            "• 📅 Qarzsizlik sanasi\n"
            "• 💰 12 oylik jamg'arma\n"
            "• 🎁 Erkinlikdagi jamg'arma"
        ),
        "ru": (
            "🌟 *ВАШ ПУТЬ К СВОБОДЕ*\n\n"
            "📊 *Ежемесячное распределение:*\n\n"
            "💳 Платёж по долгу: *{debt_payment}* сум\n"
            "💰 Накопления: *{savings}* сум\n"
            "🏠 На жизнь: *{living}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔒 *Для полного плана нужен PRO:*\n\n"
            "• 📅 Дата свободы от долгов\n"
            "• 💰 Накопления за 12 месяцев\n"
            "• 🎁 Накопления к свободе"
        )
    },
    
    "result_debt_mode_free": {
        "uz": (
            "📋 *HOZIRGI YO'LINGIZ*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *ODDIY YO'L*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Faqat minimal to'lov bilan davom etsangiz:\n\n"
            "🗓 Yengillik sanasi: *{simple_exit_date}*\n"
            "⏱ Qolgan vaqt: *{simple_exit_months} oy*\n"
            "💳 Oylik to'lov: *{monthly_payment}* so'm\n\n"
            "📍 Kapital qurilmaydi\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *HALOS PRO BILAN*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ HALOS sanangiz: *{pro_exit_date}*\n"
            "✅ *{months_saved} oy* tezroq yengillik\n"
            "✅ *{savings_at_exit}* so'm shaxsiy kapital\n\n"
            "👇 _Tezroq erkinlik va kapital qurish uchun PRO_"
        ),
        "ru": (
            "📋 *ВАШ ТЕКУЩИЙ ПУТЬ*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *ОБЫЧНЫЙ ПУТЬ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "При минимальных платежах:\n\n"
            "🗓 Дата свободы: *{simple_exit_date}*\n"
            "⏱ Осталось: *{simple_exit_months} мес*\n"
            "💳 Ежемес. платёж: *{monthly_payment}* сум\n\n"
            "📍 Капитал не создаётся\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *С HALOS PRO*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Дата HALOS: *{pro_exit_date}*\n"
            "✅ На *{months_saved} мес* быстрее к свободе\n"
            "✅ *{savings_at_exit}* сум личного капитала\n\n"
            "👇 _Быстрее к свободе и росту капитала с PRO_"
        )
    },
    
    "upgrade_cta_after_free": {
        "uz": (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *HALOS PRO*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "PRO bilan siz olasiz:\n\n"
            "✓ *Tezroq* moliyaviy yengillik\n"
            "✓ Shaxsiy *kapital qurish*\n"
            "✓ Moliyaviy *xotirjamlik*\n"
            "✓ *Aniq yo'l* — HALOS sanangiz\n\n"
            "👇 Tinch kelajak uchun boshlang"
        ),
        "ru": (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *HALOS PRO*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "С PRO вы получите:\n\n"
            "✓ *Быстрее* к финансовой лёгкости\n"
            "✓ Рост личного *капитала*\n"
            "✓ Финансовое *спокойствие*\n"
            "✓ *Точный путь* — ваша дата HALOS\n\n"
            "👇 Начните путь к спокойствию"
        )
    },
    
    "result_wealth_mode": {
        "uz": (
            "🌟 *TABRIKLAYMIZ — SIZ ERKINLIKDASIZ!*\n\n"
            "Moliyaviy yuk ortda qoldi. Endi boylik qurish vaqti.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Oylik balans:*\n\n"
            "📈 Kelajak kapitali: *{invest}* so'm\n"
            "💎 Moliyaviy aktiv: *{savings}* so'm\n"
            "🏠 Xotirjam yashash: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🚀 *12 oyda sizning kapitalingiz:*\n\n"
            "• Moliyaviy aktiv: *{savings_12}* so'm\n"
            "• Kelajak kapitali: *{invest_12}* so'm\n"
            "• Jami boylik: *{total_12}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Har oyda pulingiz siz uchun ishlaydi.\n"
            "Siz erkin — endi shaxsiy kapital qurasiz."
        ),
        "ru": (
            "🌟 *ПОЗДРАВЛЯЕМ — ВЫ СВОБОДНЫ!*\n\n"
            "Финансовое бремя позади. Время строить капитал.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Ежемесячный баланс:*\n\n"
            "📈 Будущий капитал: *{invest}* сум\n"
            "💎 Финансовые активы: *{savings}* сум\n"
            "🏠 Спокойная жизнь: *{living}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🚀 *Ваш капитал за 12 месяцев:*\n\n"
            "• Финансовые активы: *{savings_12}* сум\n"
            "• Будущий капитал: *{invest_12}* сум\n"
            "• Всего капитал: *{total_12}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Каждый месяц ваши деньги работают на вас.\n"
            "Вы свободны — теперь строите личный капитал."
        )
    },
    
    "result_wealth_mode_partial": {
        "uz": (
            "� *TABRIKLAYMIZ!*\n\n"
            "Siz qarzsiz — endi boylik yaratish vaqti keldi.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Oylik taqsimot:*\n\n"
            "📈 Investitsiya: *{invest}* so'm\n"
            "💰 Jamg'arma: *{savings}* so'm\n"
            "🏠 Yashash uchun: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔒 *To'liq rejani ochish uchun PRO:*\n\n"
            "• 12 oylik jamg'arma\n"
            "• 12 oylik investitsiya\n"
            "• Jami boylik"
        ),
        "ru": (
            "🎉 *ПОЗДРАВЛЯЕМ!*\n\n"
            "Вы свободны от долгов — пора создавать богатство.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Ежемесячное распределение:*\n\n"
            "📈 Инвестиции: *{invest}* сум\n"
            "💰 Накопления: *{savings}* сум\n"
            "🏠 На жизнь: *{living}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔒 *Для полного плана нужен PRO:*\n\n"
            "• Накопления за 12 месяцев\n"
            "• Инвестиции за 12 месяцев\n"
            "• Общий капитал"
        )
    },
    
    "result_negative_cash": {
        "uz": (
            "⚠️ *Diqqat!*\n\n"
            "Sizning xarajatlaringiz daromaddan oshib ketdi.\n\n"
            "• Daromad: {income} so'm\n"
            "• Xarajatlar: {expenses} so'm\n"
            "• Farq: {difference} so'm\n\n"
            "Iltimos, xarajatlarni qayta ko'rib chiqing yoki daromadni oshiring.\n\n"
            "Qayta boshlash uchun /start bosing."
        ),
        "ru": (
            "⚠️ *Внимание!*\n\n"
            "Ваши расходы превышают доход.\n\n"
            "• Доход: {income} сум\n"
            "• Расходы: {expenses} сум\n"
            "• Разница: {difference} сум\n\n"
            "Это сложная ситуация, но выход есть.\n"
            "Давайте вместе найдём способ снизить расходы.\n\n"
            "Для перезапуска нажмите /start."
        )
    },
    
    # ==================== NAVIGATION ====================
    "restart": {
        "uz": "🔄 Qayta boshlash uchun /start bosing.",
        "ru": "🔄 Для перезапуска нажмите /start."
    },
    
    "help": {
        "uz": (
            "ℹ️ *HALOS yordam*\n\n"
            "*Buyruqlar:*\n"
            "/start — Qayta boshlash\n"
            "/help — Yordam\n"
            "/status — Joriy yo'lingiz\n"
            "/language — Tilni o'zgartirish\n\n"
            "*HALOS nima?*\n"
            "HALOS — moliyaviy yukdan xalos bo'lib, shaxsiy kapital qurish yo'li.\n\n"
            "*Savollar bo'lsa:*\n"
            "Telegram: @halos_support"
        ),
        "ru": (
            "ℹ️ *Помощь HALOS*\n\n"
            "*Команды:*\n"
            "/start — Перезапуск\n"
            "/help — Помощь\n"
            "/status — Ваш текущий путь\n"
            "/language — Сменить язык\n\n"
            "*Что такое HALOS?*\n"
            "HALOS — путь от финансового бремени к свободе и личному капиталу.\n\n"
            "*Есть вопросы?*\n"
            "Telegram: @halos_support"
        )
    },
    
    "no_data": {
        "uz": "📋 Ma'lumot topilmadi. Boshlash uchun /start bosing.",
        "ru": "📋 Данные не найдены. Нажмите /start для начала."
    },
    
    "status_header": {
        "uz": "📊 *Sizning joriy rejangiz:*",
        "ru": "📊 *Ваш текущий план:*"
    },
    
    # ==================== ERRORS ====================
    "error_generic": {
        "uz": "❌ Xatolik yuz berdi. Iltimos, /start bilan qayta boshlang.",
        "ru": "❌ Произошла ошибка. Пожалуйста, начните заново с /start."
    },
    
    "error_contact_mismatch": {
        "uz": "❌ Iltimos, o'zingizning raqamingiz bilan ro'yxatdan o'ting.",
        "ru": "❌ Пожалуйста, зарегистрируйтесь со своим номером."
    },
    
    # ==================== BUTTONS ====================
    "btn_uzbek": {
        "uz": "🇺🇿 O'zbekcha",
        "ru": "🇺🇿 O'zbekcha"
    },
    
    "btn_russian": {
        "uz": "🇷🇺 Русский",
        "ru": "🇷🇺 Русский"
    },
    
    "btn_recalculate": {
        "uz": "🔄 Qayta hisoblash",
        "ru": "🔄 Пересчитать"
    },
    
    "btn_profile": {
        "uz": "👤 Profilim",
        "ru": "👤 Мой профиль"
    },
    
    "btn_new_calculation": {
        "uz": "🔄 Yangi hisoblash",
        "ru": "🔄 Новый расчёт"
    },
    
    "btn_use_saved_data": {
        "uz": "📊 Saqlangan ma'lumotlar bilan",
        "ru": "📊 С сохранёнными данными"
    },
    
    "recalculate_choice": {
        "uz": "🔄 *Qayta hisoblash*\n\nSaqlangan ma'lumotlaringiz bilan hisoblashni xohlaysizmi yoki yangidan kiritasizmi?",
        "ru": "🔄 *Пересчёт*\n\nИспользовать сохранённые данные или ввести заново?"
    },
    
    "calculating_saved": {
        "uz": "⏳ Saqlangan ma'lumotlar bilan hisoblanmoqda...",
        "ru": "⏳ Расчёт с сохранёнными данными..."
    },
    
    "btn_share": {
        "uz": "📤 Do'stlarga ulashish",
        "ru": "📤 Поделиться с друзьями"
    },
    
    # ==================== SUBSCRIPTION & PREMIUM ====================
    "btn_upgrade_pro": {
        "uz": "💎 PRO ga yangilash",
        "ru": "💎 Перейти на PRO"
    },
    
    "btn_try_free": {
        "uz": "🎁 3 kun BEPUL sinab ko'rish",
        "ru": "🎁 3 дня БЕСПЛАТНО"
    },
    
    "subscription_active": {
        "uz": (
            "💎 *PRO OBUNA FAOL*\n\n"
            "✅ Sizda PRO obuna mavjud!\n\n"
            "📅 Amal qilish muddati: *{expires}*\n\n"
            "🎉 Barcha imkoniyatlardan foydalanishingiz mumkin."
        ),
        "ru": (
            "💎 *PRO ПОДПИСКА АКТИВНА*\n\n"
            "✅ У вас есть PRO подписка!\n\n"
            "📅 Действует до: *{expires}*\n\n"
            "🎉 Вам доступны все возможности."
        )
    },
    
    "subscription_status": {
        "uz": (
            "📊 *Obuna holati*\n\n"
            "👤 Foydalanuvchi: {name}\n"
            "📱 Telefon: {phone}\n"
            "💎 Tarif: *{tier}*\n"
            "{expires_info}"
        ),
        "ru": (
            "📊 *Статус подписки*\n\n"
            "👤 Пользователь: {name}\n"
            "📱 Телефон: {phone}\n"
            "💎 Тариф: *{tier}*\n"
            "{expires_info}"
        )
    },
    
    "subscription_expires": {
        "uz": "⏳ Amal qilish muddati: {date}",
        "ru": "⏳ Действует до: {date}"
    },
    
    "subscription_free": {
        "uz": "🆓 Bepul (cheklangan)",
        "ru": "🆓 Бесплатный (ограничен)"
    },
    
    "subscription_pro": {
        "uz": "💎 PRO",
        "ru": "💎 PRO"
    },
    
    "premium_pricing": {
        "uz": (
            "💎 *HALOS PRO*\n\n"
            "Hozirgi yo'lingiz bilan *{simple_months} oy*da yengillik.\n"
            "PRO bilan *{pro_months} oy*da — *{months_saved} oy tezroq!*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *PRO BILAN SIZ OLASIZ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *HALOS sanangiz* — erkinlik sanasini bilasiz\n"
            "✅ *Tezroq yengillik* — bir necha oy oldin erkinlikka\n"
            "✅ *Shaxsiy kapital* — yuk to'layotganda ham kapital qurasiz\n"
            "✅ *Oylik balans* — qancha sarflash, qancha yig'ish\n"
            "✅ *12 oylik yo'l* — kelajakni ko'rasiz\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *NARXLAR:*\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        "ru": (
            "💎 *HALOS PRO*\n\n"
            "Обычным путём свобода через *{simple_months} мес*.\n"
            "С PRO за *{pro_months} мес* — *на {months_saved} мес быстрее!*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 *С PRO ВЫ ПОЛУЧИТЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Дата HALOS* — знаете когда станете свободны\n"
            "✅ *Быстрее к лёгкости* — на несколько мес раньше\n"
            "✅ *Личный капитал* — создаёте даже выплачивая бремя\n"
            "✅ *Баланс месяца* — сколько тратить, сколько растить\n"
            "✅ *Путь на 12 мес* — видите будущее\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *ЦЕНЫ:*\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
    },
    
    "price_weekly": {
        "uz": "├ ⚡ 1 hafta: *5,000 so'm* — sinab ko'ring",
        "ru": "├ ⚡ 1 неделя: *5,000 сум* — попробуйте"
    },
    
    "price_monthly": {
        "uz": "├ ⭐ 1 oy: *15,000 so'm* — tavsiya etiladi",
        "ru": "├ ⭐ 1 месяц: *15,000 сум* — рекомендуем"
    },
    
    "price_quarterly": {
        "uz": "├ 3 oy: *40,000 so'm* (−11%)",
        "ru": "├ 3 месяца: *40,000 сум* (−11%)"
    },
    
    "price_yearly": {
        "uz": "└ 🏆 1 yil: *120,000 so'm* (−33% tejash)",
        "ru": "└ 🏆 1 год: *120,000 сум* (−33% экономия)"
    },
    
    "btn_buy_weekly": {
        "uz": "⚡ 1 hafta - 5,000 so'm",
        "ru": "⚡ 1 неделя - 5,000 сум"
    },
    
    "btn_buy_monthly": {
        "uz": "⭐ 1 oy - 15,000 so'm",
        "ru": "⭐ 1 месяц - 15,000 сум"
    },
    
    "btn_buy_quarterly": {
        "uz": "3 oy - 40,000 so'm",
        "ru": "3 месяца - 40,000 сум"
    },
    
    "btn_buy_yearly": {
        "uz": "🏆 1 yil - 120,000 so'm",
        "ru": "🏆 1 год - 120,000 сум"
    },
    
    "btn_pay_click": {
        "uz": "💳 Click orqali to'lash",
        "ru": "💳 Оплатить через Click"
    },
    
    "btn_pay_payme": {
        "uz": "💳 Payme orqali to'lash",
        "ru": "💳 Оплатить через Payme"
    },
    
    "payment_success": {
        "uz": (
            "� *Tabriklaymiz!*\n\n"
            "Siz endi *HALOS PRO* foydalanuvchisisiz.\n\n"
            "✅ Obunangiz {days} kunga faollashtirildi.\n"
            "⏳ Amal qilish muddati: {date}\n\n"
            "Tezroq erkinlik va kapital qurish yo'lida!"
        ),
        "ru": (
            "🌟 *Поздравляем!*\n\n"
            "Теперь вы пользователь *HALOS PRO*.\n\n"
            "✅ Подписка активирована на {days} дней.\n"
            "⏳ Действует до: {date}\n\n"
            "На пути к свободе и росту капитала!"
        )
    },
    
    "payment_failed": {
        "uz": "❌ To'lov amalga oshmadi. Qaytadan urinib ko'ring.",
        "ru": "❌ Оплата не прошла. Попробуйте ещё раз."
    },
    
    "premium_required": {
        "uz": (
            "🔒 *Bu imkoniyat faqat PRO foydalanuvchilar uchun*\n\n"
            "PRO obunasi bilan siz quyidagilarni olasiz:\n"
            "• ♾️ Cheksiz tahlillar\n"
            "• 📊 PDF hisobotlar\n"
            "• 📈 Qarz to'lash rejasi\n"
            "• 🤖 AI maslahatlar\n\n"
            "💰 Atigi *15,000 so'm/oy* yoki *50 ⭐*\n\n"
            "🎁 Yoki 3 kun BEPUL sinab ko'ring!"
        ),
        "ru": (
            "🔒 *Эта функция доступна только для PRO*\n\n"
            "С PRO подпиской вы получите:\n"
            "• ♾️ Безлимитные анализы\n"
            "• 📊 PDF отчёты\n"
            "• 📈 План погашения долга\n"
            "• 🤖 AI советы\n\n"
            "💰 Всего *15,000 сум/мес* или *50 ⭐*\n\n"
            "🎁 Или попробуйте 3 дня БЕСПЛАТНО!"
        )
    },
    
    "feature_limit_reached": {
        "uz": (
            "⚠️ *Bepul limit tugadi!*\n\n"
            "Siz bepul versiyaning imkoniyatlarini ishlatib bo'ldingiz.\n\n"
            "📊 Bepul versiyada:\n"
            "• KATM tahlili: 1 marta\n"
            "• Tranzaksiya tahlili: 1 marta\n"
            "• Hisob-kitob: kuniga 1 ta\n\n"
            "🔓 *PRO bilan cheksiz foydalaning!*\n\n"
            "⏰ *Maxsus taklif:* Hozir PRO olsangiz *20% chegirma!*"
        ),
        "ru": (
            "⚠️ *Лимит исчерпан!*\n\n"
            "Вы использовали все возможности бесплатной версии.\n\n"
            "📊 В бесплатной версии:\n"
            "• Анализ KATM: 1 раз\n"
            "• Анализ транзакций: 1 раз\n"
            "• Расчёт: 1 в день\n\n"
            "🔓 *С PRO — безлимитно!*\n\n"
            "⏰ *Спецпредложение:* Оформите PRO сейчас и получите *скидку 20%!*"
        )
    },
    
    "partial_results_notice": {
        "uz": (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *Ba'zi ma'lumotlar yashirilgan*\n\n"
            "Bepul versiyada quyidagilar ko'rsatilmaydi:\n"
            "• 📈 Batafsil qarz to'lash rejasi\n"
            "• 💰 12 oylik jamg'arma prognozi\n"
            "• 🎯 Qarzdan chiqish sanasi\n"
            "• 📊 Xarajat tahlili\n\n"
            "💎 *PRO ga o'ting* va to'liq natijalarni oling!"
        ),
        "ru": (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *Часть данных скрыта*\n\n"
            "В бесплатной версии не показываются:\n"
            "• 📈 Детальный план погашения долга\n"
            "• 💰 Прогноз накоплений на 12 месяцев\n"
            "• 🎯 Дата выхода из долгов\n"
            "• 📊 Анализ расходов\n\n"
            "💎 *Перейдите на PRO* и получите полные результаты!"
        )
    },
    
    "trial_offer": {
        "uz": (
            "🎁 *3 KUN BEPUL PRO!*\n\n"
            "Hali PRO ni sinab ko'rmadingizmi?\n\n"
            "✅ 3 kun davomida barcha PRO imkoniyatlaridan foydalaning:\n"
            "• ♾️ Cheksiz tahlillar\n"
            "• 📊 To'liq natijalar\n"
            "• 📈 Qarz to'lash rejasi\n"
            "• 🤖 AI maslahatlar\n\n"
            "❌ Karta bog'lash shart emas!\n"
            "❌ Avtomatik to'lov yo'q!\n\n"
            "👇 Hoziroq boshlang!"
        ),
        "ru": (
            "🎁 *3 ДНЯ PRO БЕСПЛАТНО!*\n\n"
            "Ещё не пробовали PRO?\n\n"
            "✅ 3 дня пользуйтесь всеми PRO возможностями:\n"
            "• ♾️ Безлимитные анализы\n"
            "• 📊 Полные результаты\n"
            "• 📈 План погашения долга\n"
            "• 🤖 AI советы\n\n"
            "❌ Не нужно привязывать карту!\n"
            "❌ Нет автоматических платежей!\n\n"
            "👇 Начните прямо сейчас!"
        )
    },
    
    "trial_activated": {
        "uz": (
            "🎉 *3 kunlik bepul PRO faollashtirildi!*\n\n"
            "Endi sizda barcha PRO imkoniyatlari bor:\n"
            "• ♾️ Cheksiz tahlillar\n"
            "• 📊 To'liq natijalar\n"
            "• 📈 Qarz to'lash rejasi\n\n"
            "⏳ Amal qilish muddati: {date}\n\n"
            "Yoqib qolsa, PRO ni davom ettiring! 💎"
        ),
        "ru": (
            "🎉 *3-дневный бесплатный PRO активирован!*\n\n"
            "Теперь у вас есть все PRO возможности:\n"
            "• ♾️ Безлимитные анализы\n"
            "• 📊 Полные результаты\n"
            "• 📈 План погашения долга\n\n"
            "⏳ Действует до: {date}\n\n"
            "Понравится — продлите PRO! 💎"
        )
    },
    
    "trial_ending_soon": {
        "uz": (
            "⚠️ *Bepul PRO tugayapti!*\n\n"
            "Sizning 3 kunlik bepul PRO {hours} soatdan so'ng tugaydi.\n\n"
            "💎 PRO ni davom ettiring va:\n"
            "• Barcha imkoniyatlardan foydalaning\n"
            "• Ma'lumotlaringiz saqlanadi\n\n"
            "🎁 *Hozir olsangiz 30% chegirma!*\n"
            "Kod: `TRIAL30`"
        ),
        "ru": (
            "⚠️ *Бесплатный PRO заканчивается!*\n\n"
            "Ваш 3-дневный PRO истекает через {hours} часов.\n\n"
            "💎 Продлите PRO и:\n"
            "• Пользуйтесь всеми возможностями\n"
            "• Ваши данные сохранятся\n\n"
            "🎁 *Оформите сейчас со скидкой 30%!*\n"
            "Код: `TRIAL30`"
        )
    },
    
    "offer_after_first_calc": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *Ajoyib! Birinchi qadamni qo'ydingiz!* 👏\n\n"
            "Natijangiz tayyor. Endi keyingi bosqichga o'ting:\n\n"
            "🔓 *PRO bilan qo'shimcha imkoniyatlar:*\n"
            "├ 📅 Qarzdan *aniq qachon* chiqishingiz\n"
            "├ 💰 12 oylik *jamg'arma rejasi*\n"
            "├ 📊 Batafsil *moliyaviy tahlil*\n"
            "└ 🤖 *AI maslahatlar* sizga moslashtirilgan\n\n"
            "💡 _Har kuni ishlatib, moliyaviy erkinlikka erishing!_\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 *Отлично! Вы сделали первый шаг!* 👏\n\n"
            "Ваш результат готов. Переходите к следующему этапу:\n\n"
            "🔓 *Дополнительные возможности с PRO:*\n"
            "├ 📅 *Точная дата* выхода из долгов\n"
            "├ 💰 *План накоплений* на 12 месяцев\n"
            "├ 📊 Детальный *финансовый анализ*\n"
            "└ 🤖 *AI советы*, адаптированные для вас\n\n"
            "💡 _Используйте ежедневно для достижения финансовой свободы!_\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
    },
    
    "why_pro_stats": {
        "uz": (
            "📊 *HALOS PRO foydalanuvchilari statistikasi:*\n\n"
            "• 🕊 O'rtacha *47%* tezroq yengillikka erishadilar\n"
            "• 💎 Oyiga *300,000+* so'm kapital qurishadi\n"
            "• 🌟 *89%* moliyaviy tinchlikka erishadilar\n\n"
            "Siz ham ulardan biri bo'ling!"
        ),
        "ru": (
            "📊 *Статистика пользователей HALOS PRO:*\n\n"
            "• 🕊 Достигают свободы в среднем на *47%* быстрее\n"
            "• 💎 Создают *300,000+* сум капитала в месяц\n"
            "• 🌟 *89%* достигают финансового спокойствия\n\n"
            "Станьте одним из них!"
        )
    },
    
    "promo_code_prompt": {
        "uz": "🎁 Promo-kodingiz bormi? Kiriting yoki o'tkazib yuboring:",
        "ru": "🎁 Есть промокод? Введите или пропустите:"
    },
    
    "promo_code_valid": {
        "uz": "✅ Promo-kod qabul qilindi! Chegirma: *{discount}%*",
        "ru": "✅ Промокод принят! Скидка: *{discount}%*"
    },
    
    "promo_code_invalid": {
        "uz": "❌ Noto'g'ri promo-kod",
        "ru": "❌ Неверный промокод"
    },
    
    "btn_skip_promo": {
        "uz": "⏭️ O'tkazib yuborish",
        "ru": "⏭️ Пропустить"
    },
    
    "referral_info": {
        "uz": (
            "👥 *Do'stlaringizni taklif qiling!*\n\n"
            "Sizning havola: `{link}`\n\n"
            "Har bir do'stingiz ro'yxatdan o'tganida:\n"
            "• Siz olasiz: *1 hafta bepul PRO*\n"
            "• Do'stingiz oladi: *3 kun bepul PRO*"
        ),
        "ru": (
            "👥 *Приглашайте друзей!*\n\n"
            "Ваша ссылка: `{link}`\n\n"
            "За каждого приглашённого:\n"
            "• Вы получите: *1 неделя PRO бесплатно*\n"
            "• Друг получит: *3 дня PRO бесплатно*"
        )
    },
    
    # ==================== MY DEBTS (QARZLARIM) ====================
    "my_debts_header": {
        "uz": "💳 *MENING QARZLARIM*",
        "ru": "💳 *МОИ ДОЛГИ*"
    },
    
    "my_debts_info": {
        "uz": (
            "📊 *Qarz holati:*\n\n"
            "💰 Umumiy qarz: *{total_debt}*\n"
            "📅 Oylik to'lov: *{monthly_payment}*"
        ),
        "ru": (
            "📊 *Статус долга:*\n\n"
            "💰 Общий долг: *{total_debt}*\n"
            "📅 Ежемес. платёж: *{monthly_payment}*"
        )
    },
    
    "my_debts_simple": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *ODDIY USULDA:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🗓 Qarzdan chiqish: *{simple_exit_date}*\n"
            "⏱ Qoldi: *{simple_exit_months} oy*"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *ОБЫЧНЫМ СПОСОБОМ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🗓 Выход из долга: *{simple_exit_date}*\n"
            "⏱ Осталось: *{simple_exit_months} мес*"
        )
    },
    
    "my_debts_pro_plan": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *SIZNING SHAXSIY REJA:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🗓 Qarzdan chiqish: *{exit_date}*\n"
            "⏱ Qoldi: *{exit_months} oy*\n\n"
            "💰 Chiqishdagi jamg'arma: *{savings_at_exit}*\n"
            "📈 Oylik jamg'arma: *{monthly_savings}*\n"
            "⚡ Qo'shimcha to'lov: *{accelerated_payment}*"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *ВАШ ПЕРСОНАЛЬНЫЙ ПЛАН:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🗓 Выход из долга: *{exit_date}*\n"
            "⏱ Осталось: *{exit_months} мес*\n\n"
            "💰 Накопления к выходу: *{savings_at_exit}*\n"
            "📈 Ежемес. накопления: *{monthly_savings}*\n"
            "⚡ Доп. платёж: *{accelerated_payment}*"
        )
    },
    
    "my_debts_pro_teaser": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *PRO BILAN TEZROQ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *{pro_exit_date}* da qarzsiz\n"
            "✅ *{months_saved} oy* tez\n"
            "✅ *{savings_at_exit}* jamg'arma\n\n"
            "� _PRO ga o'ting va tezroq qutiling_"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *С PRO БЫСТРЕЕ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Свободны *{pro_exit_date}*\n"
            "✅ На *{months_saved} мес* быстрее\n"
            "✅ Накопите *{savings_at_exit}*\n\n"
            "� _Перейдите на PRO и освободитесь быстрее_"
        )
    },
    
    "debt_no_data": {
        "uz": "💳 Qarz ma'lumotlari topilmadi.\n\n/start buyrug'ini bosing va ma'lumotlaringizni kiriting.",
        "ru": "💳 Данные о долгах не найдены.\n\nНажмите /start и введите свои данные."
    },
    
    "debt_free_message": {
        "uz": (
            "✨ *SIZ ERKINLIKDASIZ!*\n\n"
            "Sizda moliyaviy yuk yo'q.\n\n"
            "Endi shaxsiy kapital qurish vaqti.\n"
            "Kelajak kapitalingizni boshlang! 🌟"
        ),
        "ru": (
            "✨ *ВЫ СВОБОДНЫ!*\n\n"
            "У вас нет финансового бремени.\n\n"
            "Теперь время строить личный капитал.\n"
            "Начните создавать будущий капитал! 🌟"
        )
    },
    
    # ==================== PROFILE ====================
    "profile_header": {
        "uz": "👤 *MENING PROFILIM*",
        "ru": "👤 *МОЙ ПРОФИЛЬ*"
    },
    
    "profile_info": {
        "uz": (
            "👤 *Shaxsiy ma'lumotlar:*\n\n"
            "📅 *Rejim:* {mode}\n"
            "🌐 *Til:* {language}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *Moliyaviy ma'lumotlar:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *Daromad (men):* {income_self}\n"
            "💵 *Daromad (sherik):* {income_partner}\n\n"
            "🏠 *Ijara:* {rent}\n"
            "📋 *Majburiy to'lovlar:* {kindergarten}\n"
            "💡 *Kommunal:* {utilities}\n\n"
            "💳 *Oylik to'lov:* {loan_payment}\n"
            "📉 *Umumiy qarz:* {total_debt}"
        ),
        "ru": (
            "👤 *Личные данные:*\n\n"
            "📅 *Режим:* {mode}\n"
            "🌐 *Язык:* {language}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 *Финансовые данные:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 *Доход (я):* {income_self}\n"
            "💵 *Доход (партнёр):* {income_partner}\n\n"
            "🏠 *Аренда:* {rent}\n"
            "📋 *Обязательные:* {kindergarten}\n"
            "💡 *Коммунальные:* {utilities}\n\n"
            "💳 *Ежемесячный платёж:* {loan_payment}\n"
            "📉 *Общий долг:* {total_debt}"
        )
    },
    
    "profile_no_data": {
        "uz": "👤 Ma'lumotlar topilmadi.\n\n/start buyrug'ini bosing va ma'lumotlaringizni kiriting.",
        "ru": "👤 Данные не найдены.\n\nНажмите /start и введите свои данные."
    },
    
    "profile_edit_menu": {
        "uz": "✏️ *Qaysi ma'lumotni o'zgartirmoqchisiz?*",
        "ru": "✏️ *Что хотите изменить?*"
    },
    
    "btn_edit_income_self": {
        "uz": "💰 Daromadim",
        "ru": "💰 Мой доход"
    },
    
    "btn_edit_income_partner": {
        "uz": "💰 Sherik daromadi",
        "ru": "💰 Доход партнёра"
    },
    
    "btn_edit_rent": {
        "uz": "🏠 Ijara",
        "ru": "🏠 Аренда"
    },
    
    "btn_edit_kindergarten": {
        "uz": "� Majburiy",
        "ru": "📋 Обязат."
    },
    
    "btn_edit_utilities": {
        "uz": "💡 Kommunal",
        "ru": "💡 Коммунальные"
    },
    
    "btn_edit_loan_payment": {
        "uz": "💳 Oylik to'lov",
        "ru": "💳 Ежемес. платёж"
    },
    
    "btn_edit_total_debt": {
        "uz": "📉 Umumiy qarz",
        "ru": "📉 Общий долг"
    },
    
    "btn_edit_mode": {
        "uz": "📅 Rejim",
        "ru": "📅 Режим"
    },
    
    "btn_back_to_profile": {
        "uz": "◀️ Profilga qaytish",
        "ru": "◀️ Назад к профилю"
    },
    
    "edit_enter_new_value": {
        "uz": "✏️ *{field}* uchun yangi qiymatni kiriting (so'm):",
        "ru": "✏️ Введите новое значение для *{field}* (сум):"
    },
    
    "edit_success": {
        "uz": "✅ *{field}* muvaffaqiyatli yangilandi!",
        "ru": "✅ *{field}* успешно обновлено!"
    },
    
    "edit_invalid_number": {
        "uz": "❌ Noto'g'ri raqam. Iltimos, faqat son kiriting.",
        "ru": "❌ Неверное число. Пожалуйста, введите только цифры."
    },
    
    "btn_recalculate": {
        "uz": "🔄 Qayta hisoblash",
        "ru": "🔄 Пересчитать"
    },
    
    "profile_updated_recalculate": {
        "uz": "✅ Ma'lumotlar yangilandi!\n\nYangi natijalarni ko'rish uchun \"Qayta hisoblash\" tugmasini bosing.",
        "ru": "✅ Данные обновлены!\n\nНажмите \"Пересчитать\" для новых результатов."
    },
    
    "profile_debt_status": {
        "uz": (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *QARZ HOLATI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 Umumiy qarz: *{total_debt}*\n"
            "📅 Oylik to'lov: *{monthly_payment}*\n\n"
            "🗓 Oddiy usulda: *{simple_exit_date}*\n"
            "⏱ Qoldi: *{simple_exit_months} oy*"
        ),
        "ru": (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *СТАТУС ДОЛГА*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 Общий долг: *{total_debt}*\n"
            "📅 Ежемес. платёж: *{monthly_payment}*\n\n"
            "🗓 Обычным способом: *{simple_exit_date}*\n"
            "⏱ Осталось: *{simple_exit_months} мес*"
        )
    },
    
    "profile_pro_teaser": {
        "uz": (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *TEZROQ CHIQISH MUMKIN!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "PRO obuna bilan siz:\n\n"
            "✅ *{pro_exit_date}* da qarzsiz\n"
            "✅ *{months_saved} oy* tez\n"
            "✅ *{savings_at_exit}* jamg'arma\n\n"
            "💎 _PRO ga o'ting va tezroq qutiling_"
        ),
        "ru": (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *МОЖНО БЫСТРЕЕ!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "С PRO подпиской вы:\n\n"
            "✅ Свободны *{pro_exit_date}*\n"
            "✅ На *{months_saved} мес* быстрее\n"
            "✅ Накопите *{savings_at_exit}*\n\n"
            "💎 _Перейдите на PRO и освободитесь быстрее_"
        )
    },
    
    "btn_faster_exit": {
        "uz": "🚀 Qarzdan tezroq chiqish",
        "ru": "🚀 Быстрее выйти из долга"
    },
    
    "btn_my_debt_plan": {
        "uz": "📋 Qarz rejam",
        "ru": "📋 Мой план долга"
    },
    
    # ==================== PRO CARING MESSAGES ====================
    # Wolt-style supportive messages
    "care_inactive_3days": {
        "uz": (
            "💙 Biz hali shu yerdamiz.\n\n"
            "Siz o'ylaganingizdan *yaqinroqsiz*.\n"
            "Keling, davom etamiz — qadam qadamdan."
        ),
        "ru": (
            "💙 Мы всё ещё здесь.\n\n"
            "Вы *ближе*, чем думаете.\n"
            "Давайте продолжим — шаг за шагом."
        )
    },
    
    "care_salary_day": {
        "uz": (
            "🌟 Bugun kuchli kun.\n\n"
            "Oylik keldi — bu *imkoniyat lahzasi*.\n"
            "Kelajagingiz bugun quriladi.\n\n"
            "📊 Qarz rejangizni ko'ring →"
        ),
        "ru": (
            "🌟 Сегодня важный день.\n\n"
            "Пришла зарплата — это *момент возможности*.\n"
            "Ваше будущее строится сегодня.\n\n"
            "📊 Посмотрите ваш план →"
        )
    },
    
    "care_first_week": {
        "uz": (
            "🎯 Birinchi hafta o'tdi!\n\n"
            "Eng qiyin qadam — boshlash.\n"
            "Siz allaqachon *harakatdasiz*.\n\n"
            "Har bir kun — yangi imkoniyat."
        ),
        "ru": (
            "🎯 Первая неделя позади!\n\n"
            "Самый сложный шаг — начать.\n"
            "Вы уже *в движении*.\n\n"
            "Каждый день — новая возможность."
        )
    },
    
    "care_milestone_50": {
        "uz": (
            "🏆 Ajoyib natija!\n\n"
            "Siz qarzingizning *50%* ini to'ladingiz.\n"
            "Yarim yo'ldasiz — davom eting!"
        ),
        "ru": (
            "🏆 Отличный результат!\n\n"
            "Вы погасили *50%* вашего долга.\n"
            "Полпути пройдено — продолжайте!"
        )
    },
    
    # Weekly progress messages
    "weekly_progress": {
        "uz": (
            "📊 *Haftalik hisobot*\n\n"
            "Bu hafta siz qarzingizdan\n"
            "*{amount}* ga yaqinlashdingiz.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 To'langan: *{paid}*\n"
            "📅 Qoldi: *{remaining}*\n"
            "⏱ Chiqish sanasi: *{exit_date}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💪 Davom eting!"
        ),
        "ru": (
            "📊 *Еженедельный отчёт*\n\n"
            "На этой неделе вы приблизились\n"
            "к свободе от долгов на *{amount}*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Погашено: *{paid}*\n"
            "📅 Осталось: *{remaining}*\n"
            "⏱ Дата выхода: *{exit_date}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💪 Продолжайте!"
        )
    },
    
    "weekly_progress_family": {
        "uz": (
            "👨‍👩‍👦 *Oilaviy haftalik hisobot*\n\n"
            "Bu hafta oilangiz qarzdan\n"
            "*{amount}* ga yaqinlashdi.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 To'langan: *{paid}*\n"
            "📅 Qoldi: *{remaining}*\n"
            "⏱ Chiqish sanasi: *{exit_date}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👏 Birgalikda kuchlimizsiz!"
        ),
        "ru": (
            "👨‍👩‍👦 *Семейный еженедельный отчёт*\n\n"
            "На этой неделе ваша семья\n"
            "приблизилась к свободе на *{amount}*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Погашено: *{paid}*\n"
            "📅 Осталось: *{remaining}*\n"
            "⏱ Дата выхода: *{exit_date}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👏 Вместе вы сильнее!"
        )
    },
    
    # Monthly countdown messages
    "monthly_countdown": {
        "uz": (
            "📅 *Oylik eslatma*\n\n"
            "🗓 Qarzdan chiqish sanangiz:\n"
            "*{exit_date}*\n\n"
            "⏱ Yana *{months_left} oy* qoldi.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💳 Qolgan qarz: *{remaining_debt}*\n"
            "💰 Jamg'arma: *{savings}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 Maqsadga yaqinlashmoqdasiz!"
        ),
        "ru": (
            "📅 *Ежемесячное напоминание*\n\n"
            "🗓 Ваша дата свободы от долгов:\n"
            "*{exit_date}*\n\n"
            "⏱ Осталось *{months_left} месяцев*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💳 Остаток долга: *{remaining_debt}*\n"
            "💰 Накопления: *{savings}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 Вы приближаетесь к цели!"
        )
    },
    
    "monthly_countdown_family": {
        "uz": (
            "👨‍👩‍👦 *Oilaviy oylik eslatma*\n\n"
            "🗓 Oilangiz qarzdan chiqish sanasi:\n"
            "*{exit_date}*\n\n"
            "⏱ Yana *{months_left} oy* qoldi.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💳 Qolgan qarz: *{remaining_debt}*\n"
            "👨‍👩‍👦 Oilaviy jamg'arma: *{savings}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏠 Oilangiz bilan birgalikda maqsadga!"
        ),
        "ru": (
            "👨‍👩‍👦 *Семейное напоминание*\n\n"
            "🗓 Дата свободы вашей семьи:\n"
            "*{exit_date}*\n\n"
            "⏱ Осталось *{months_left} месяцев*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💳 Остаток долга: *{remaining_debt}*\n"
            "👨‍👩‍👦 Семейные накопления: *{savings}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏠 Вместе — к цели!"
        )
    },
    
    # Celebration messages
    "debt_free_congrats": {
        "uz": (
            "✨✨✨\n\n"
            "*SIZ ERKINLIKKA ERISHDINGIZ!*\n\n"
            "Moliyaviy yuk ortda qoldi.\n\n"
            "Bu sizning mehnatingiz natijasi.\n"
            "Endi shaxsiy kapital qurish vaqti!\n\n"
            "🌟 Yangi bosqichga tayyormisiz?"
        ),
        "ru": (
            "✨✨✨\n\n"
            "*ВЫ ДОСТИГЛИ СВОБОДЫ!*\n\n"
            "Финансовое бремя позади.\n\n"
            "Это результат вашего труда.\n"
            "Теперь время строить личный капитал!\n\n"
            "🌟 Готовы к новому этапу?"
        )
    },
}


# Month names for date formatting
MONTHS = {
    "uz": [
        "yanvar", "fevral", "mart", "aprel", "may", "iyun",
        "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"
    ],
    "ru": [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
}


def get_message(key: str, lang: str = "uz") -> str:
    """Get message by key and language"""
    if key in MESSAGES:
        return MESSAGES[key].get(lang, MESSAGES[key].get("uz", key))
    return key


def get_month_name(month: int, lang: str = "uz") -> str:
    """Get month name by number (1-12)"""
    if 1 <= month <= 12:
        return MONTHS[lang][month - 1]
    return str(month)


def format_number(number: float) -> str:
    """Format number with thousand separators"""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f} mln".replace(".0 ", " ")
    elif number >= 1_000:
        return f"{number:,.0f}".replace(",", " ")
    return str(int(number))
