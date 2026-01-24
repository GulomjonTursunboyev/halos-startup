"""
SOLVO Language Dictionaries
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
            "🌟 *SOLVO* ga xush kelibsiz!\n\n"
            "Men sizning shaxsiy *moliyaviy maslahatchingizman*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *SOLVO sizga yordam beradi:*\n\n"
            "💰 Qarzlardan *qachon* xalos bo'lishni ko'rsatadi\n"
            "📈 Oylik *qancha* jamg'ara olishingizni hisoblaydi\n"
            "🎯 Moliyaviy *erkinlik* rejasini tuzadi\n"
            "🤖 AI asosida *shaxsiy maslahatlar* beradi\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Ro'yxatdan o'tish uchun* telefon raqamingizni ulashing 👇"
        ),
        "ru": (
            "🌟 Добро пожаловать в *SOLVO*!\n\n"
            "Я ваш персональный *финансовый консультант*.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *SOLVO поможет вам:*\n\n"
            "💰 Показать *когда* вы избавитесь от долгов\n"
            "📈 Рассчитать *сколько* сможете откладывать\n"
            "🎯 Построить план *финансовой свободы*\n"
            "🤖 Дать *персональные советы* на основе AI\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Для регистрации* поделитесь номером телефона 👇"
        )
    },
    
    "share_contact_button": {
        "uz": "📱 Telefon raqamni ulashish",
        "ru": "📱 Поделиться номером"
    },
    
    "contact_received": {
        "uz": "✅ Rahmat! Telefon raqamingiz saqlandi.",
        "ru": "✅ Спасибо! Ваш номер сохранён."
    },
    
    "contact_required": {
        "uz": "📱 Iltimos, davom etish uchun telefon raqamingizni ulashing.",
        "ru": "📱 Пожалуйста, поделитесь номером телефона для продолжения."
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
            "� *O'zingizning oylik maoshingiz*\n\n"
            "Oylik daromadingizni kiriting (so'mda).\n\n"
            "Masalan: `5 000 000`"
        ),
        "ru": (
            "💵 *Ваша ежемесячная зарплата*\n\n"
            "Введите вашу зарплату (в сумах).\n\n"
            "Например: `5 000 000`"
        )
    },
    
    "input_income_partner": {
        "uz": (
            "💵 *Turmush o'rtog'ingizning oylik maoshi*\n\n"
            "Juftingizning oylik daromadini kiriting (so'mda).\n\n"
            "Agar ishlamasa — pastdagi tugmani bosing."
        ),
        "ru": (
            "💵 *Зарплата вашего супруга/супруги*\n\n"
            "Введите ежемесячный доход партнёра (в сумах).\n\n"
            "Если не работает — нажмите кнопку ниже."
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
            "🏠 *Uy ijarasi*\n\n"
            "Oylik ijara haqini kiriting (so'mda).\n\n"
            "O'z uyingiz bo'lsa — pastdagi tugmani bosing."
        ),
        "ru": (
            "🏠 *Аренда жилья*\n\n"
            "Введите ежемесячную арендную плату (в сумах).\n\n"
            "Если живёте в своём жилье — нажмите кнопку ниже."
        )
    },
    
    "btn_own_home": {
        "uz": "🏡 O'z uyimda yashayman",
        "ru": "🏡 Живу в своём жилье"
    },
    
    "input_kindergarten": {
        "uz": (
            "👶 *Bog'cha / Ta'lim xarajatlari*\n\n"
            "Bog'cha, maktab yoki kurslar uchun oylik to'lov (so'mda).\n\n"
            "Farzandingiz yo'q yoki to'lovlik emas — pastdagi tugmani bosing."
        ),
        "ru": (
            "👶 *Детский сад / Образование*\n\n"
            "Ежемесячная плата за детсад, школу или курсы (в сумах).\n\n"
            "Нет детей или бесплатно — нажмите кнопку ниже."
        )
    },
    
    "btn_no_kids": {
        "uz": "👶 Farzand yo'q / To'lovlik emas",
        "ru": "👶 Нет детей / Бесплатно"
    },
    
    "input_utilities": {
        "uz": (
            "💡 *Kommunal to'lovlar*\n\n"
            "Elektr, gaz, suv, internet — barchasini kiriting (so'mda).\n\n"
            "Taxminan: 300 000 - 800 000 so'm"
        ),
        "ru": (
            "💡 *Коммунальные платежи*\n\n"
            "Электричество, газ, вода, интернет — введите общую сумму (в сумах).\n\n"
            "Примерно: 300 000 - 800 000 сум"
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
            "📄 *Kredit tarixingizni yuklaysizmi?*\n\n"
            "KATM (infokredit.uz) dan rasmiy kredit tarixingizni PDF formatda yuklashingiz mumkin.\n\n"
            "Bu sizning barcha kreditlaringizni avtomatik aniqlaydi."
        ),
        "ru": (
            "📄 *Загрузить кредитную историю?*\n\n"
            "Вы можете загрузить официальную кредитную историю из KATM (infokredit.uz) в формате PDF.\n\n"
            "Это автоматически определит все ваши кредиты."
        )
    },
    
    "katm_yes": {
        "uz": "📤 Ha, PDF yuklash",
        "ru": "📤 Да, загрузить PDF"
    },
    
    "katm_no": {
        "uz": "✍️ Yo'q, qo'lda kiritaman",
        "ru": "✍️ Нет, введу вручную"
    },
    
    "katm_instructions": {
        "uz": (
            "📋 *KATM dan kredit tarixini olish:*\n\n"
            "1️⃣ infokredit.uz saytiga kiring\n"
            "2️⃣ OneID orqali tizimga kiring\n"
            "3️⃣ \"Kredit tarixi\" → \"Yuklab olish\"\n"
            "4️⃣ PDF faylni yuklab oling\n"
            "5️⃣ *Shu yerga yuboring* 👇\n\n"
            "⏳ PDF faylni kutayapman..."
        ),
        "ru": (
            "📋 *Как получить кредитную историю из KATM:*\n\n"
            "1️⃣ Зайдите на infokredit.uz\n"
            "2️⃣ Войдите через OneID\n"
            "3️⃣ «Кредитная история» → «Скачать»\n"
            "4️⃣ Скачайте PDF файл\n"
            "5️⃣ *Отправьте его сюда* 👇\n\n"
            "⏳ Жду PDF файл..."
        )
    },
    
    "katm_processing": {
        "uz": "⏳ PDF fayl qayta ishlanmoqda...",
        "ru": "⏳ Обрабатываю PDF файл..."
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
        "uz": "❌ Iltimos, faqat PDF fayl yuboring.",
        "ru": "❌ Пожалуйста, отправьте только PDF файл."
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
            "� *SIZNING ERKINLIK YO'LINGIZ*\n\n"
            "Siz *{exit_date}* da qarzsiz bo'lasiz.\n\n"
            "Agar shu rejaga amal qilsangiz, {exit_months} oy ichida\n"
            "*{savings_exit}* so'm jamg'arasiz.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Oylik taqsimot:*\n\n"
            "💳 Qarz to'lovi: *{debt_payment}* so'm\n"
            "💰 Jamg'arma: *{savings}* so'm\n"
            "🏠 Yashash uchun: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Sizning yutuqlaringiz:*\n\n"
            "• 12 oyda jamg'arma: *{savings_12}* so'm\n"
            "• Erkinlikka yetganda: *{savings_exit}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Siz hozirdan boshlab qarz yukidan qutulmoqdasiz.\n"
            "Har bir to'lov — erkinlikka qadam."
        ),
        "ru": (
            "🌟 *ВАШ ПУТЬ К СВОБОДЕ*\n\n"
            "Вы станете свободны от долгов *{exit_date}*.\n\n"
            "Если будете следовать плану, за {exit_months} мес\n"
            "накопите *{savings_exit}* сум.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Ежемесячное распределение:*\n\n"
            "💳 Платёж по долгу: *{debt_payment}* сум\n"
            "💰 Накопления: *{savings}* сум\n"
            "🏠 На жизнь: *{living}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *Ваши достижения:*\n\n"
            "• За 12 месяцев: *{savings_12}* сум\n"
            "• К моменту свободы: *{savings_exit}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Вы уже начинаете освобождаться от долгов.\n"
            "Каждый платёж — шаг к свободе."
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
    
    "result_wealth_mode": {
        "uz": (
            "� *TABRIKLAYMIZ!*\n\n"
            "Siz qarzsiz — endi boylik yaratish vaqti keldi.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 *Oylik taqsimot:*\n\n"
            "📈 Investitsiya: *{invest}* so'm\n"
            "💰 Jamg'arma: *{savings}* so'm\n"
            "🏠 Yashash uchun: *{living}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🚀 *12 oyda sizning yutuqlaringiz:*\n\n"
            "• Jamg'arma: *{savings_12}* so'm\n"
            "• Investitsiya: *{invest_12}* so'm\n"
            "• Jami boylik: *{total_12}* so'm\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Har oyda pulingiz siz uchun ishlaydi.\n"
            "Siz erkin — endi boylik qurasiz."
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
            "🚀 *Ваши достижения за 12 месяцев:*\n\n"
            "• Накопления: *{savings_12}* сум\n"
            "• Инвестиции: *{invest_12}* сум\n"
            "• Всего капитал: *{total_12}* сум\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✨ Каждый месяц ваши деньги работают на вас.\n"
            "Вы свободны — теперь строите богатство."
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
            "ℹ️ *SOLVO yordam*\n\n"
            "*Buyruqlar:*\n"
            "/start — Qayta boshlash\n"
            "/help — Yordam\n"
            "/status — Joriy rejangiz\n"
            "/language — Tilni o'zgartirish\n\n"
            "*SOLVO nima?*\n"
            "SOLVO — qarzdan erkinlikka, erkinlikdan boylikka yo'l.\n\n"
            "*Savollar bo'lsa:*\n"
            "Telegram: @solvo_support"
        ),
        "ru": (
            "ℹ️ *Помощь SOLVO*\n\n"
            "*Команды:*\n"
            "/start — Перезапуск\n"
            "/help — Помощь\n"
            "/status — Ваш текущий план\n"
            "/language — Сменить язык\n\n"
            "*Что такое SOLVO?*\n"
            "SOLVO — путь от долгов к свободе, от свободы к богатству.\n\n"
            "*Есть вопросы?*\n"
            "Telegram: @solvo_support"
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
        "uz": "❌ Iltimos, o'zingizning telefon raqamingizni ulashing.",
        "ru": "❌ Пожалуйста, поделитесь своим собственным номером телефона."
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
            "💎 *SOLVO PRO - Premium Obuna*\n\n"
            "🔓 *PRO bilan siz olasiz:*\n\n"
            "📊 *Asosiy imkoniyatlar:*\n"
            "• ♾️ Cheksiz KATM PDF tahlili\n"
            "• ♾️ Cheksiz tranzaksiya tahlili\n"
            "• ♾️ Cheksiz hisob-kitoblar\n"
            "• 📄 To'liq natijalar (yashirilmagan)\n\n"
            "📈 *Qo'shimcha funksiyalar:*\n"
            "• 📊 PDF hisobot yuklab olish\n"
            "• 🎯 Qarz to'lash rejasi (Snowball/Avalanche)\n"
            "• 📉 Xarajat kategoriyalari tahlili\n"
            "• 💰 Jamg'arma prognozi\n"
            "• 🤖 AI moliyaviy maslahatlar\n"
            "• 🔔 To'lov eslatmalari\n"
            "• 📤 Ma'lumotlarni eksport qilish\n"
            "• 💬 Prioritet yordam\n\n"
            "💰 *Narxlar:*"
        ),
        "ru": (
            "💎 *SOLVO PRO - Премиум Подписка*\n\n"
            "🔓 *С PRO вы получите:*\n\n"
            "📊 *Основные возможности:*\n"
            "• ♾️ Безлимитный анализ KATM PDF\n"
            "• ♾️ Безлимитный анализ транзакций\n"
            "• ♾️ Безлимитные расчёты\n"
            "• 📄 Полные результаты (без скрытия)\n\n"
            "📈 *Дополнительные функции:*\n"
            "• 📊 Скачивание PDF отчёта\n"
            "• 🎯 План погашения долга (Snowball/Avalanche)\n"
            "• 📉 Анализ категорий расходов\n"
            "• 💰 Прогноз накоплений\n"
            "• 🤖 AI финансовые советы\n"
            "• 🔔 Напоминания о платежах\n"
            "• 📤 Экспорт данных\n"
            "• 💬 Приоритетная поддержка\n\n"
            "💰 *Цены:*"
        )
    },
    
    "price_monthly": {
        "uz": "├ 1 oy: *15,000 so'm* yoki *50 ⭐*",
        "ru": "├ 1 месяц: *15,000 сум* или *50 ⭐*"
    },
    
    "price_quarterly": {
        "uz": "├ 3 oy: *40,500 so'm* (−10%) yoki *135 ⭐*",
        "ru": "├ 3 месяца: *40,500 сум* (−10%) или *135 ⭐*"
    },
    
    "price_yearly": {
        "uz": "└ 1 yil: *135,000 so'm* (−25%) yoki *450 ⭐*",
        "ru": "└ 1 год: *135,000 сум* (−25%) или *450 ⭐*"
    },
    
    "btn_buy_monthly": {
        "uz": "1️⃣ 1 oy - 50 ⭐",
        "ru": "1️⃣ 1 месяц - 50 ⭐"
    },
    
    "btn_buy_quarterly": {
        "uz": "3️⃣ 3 oy - 135 ⭐",
        "ru": "3️⃣ 3 месяца - 135 ⭐"
    },
    
    "btn_buy_yearly": {
        "uz": "🎁 1 yil - 450 ⭐ (Eng foydali!)",
        "ru": "🎁 1 год - 450 ⭐ (Выгодно!)"
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
            "🎉 *Tabriklaymiz!*\n\n"
            "Siz endi *SOLVO PRO* foydalanuvchisisiz!\n\n"
            "✅ Obunangiz {days} kunga faollashtirildi.\n"
            "⏳ Amal qilish muddati: {date}\n\n"
            "Barcha PRO imkoniyatlardan foydalaning! 💎"
        ),
        "ru": (
            "🎉 *Поздравляем!*\n\n"
            "Теперь вы пользователь *SOLVO PRO*!\n\n"
            "✅ Подписка активирована на {days} дней.\n"
            "⏳ Действует до: {date}\n\n"
            "Пользуйтесь всеми PRO возможностями! 💎"
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
            "📊 *SOLVO PRO foydalanuvchilari statistikasi:*\n\n"
            "• 📉 O'rtacha *47%* tezroq qarzdan chiqishadi\n"
            "• 💰 Oyiga *300,000+* so'm tejashadi\n"
            "• 🎯 *89%* maqsadlariga erishishadi\n\n"
            "Siz ham ulardan biri bo'ling! 💎"
        ),
        "ru": (
            "📊 *Статистика пользователей SOLVO PRO:*\n\n"
            "• 📉 Выходят из долгов в среднем на *47%* быстрее\n"
            "• 💰 Экономят *300,000+* сум в месяц\n"
            "• 🎯 *89%* достигают своих целей\n\n"
            "Станьте одним из них! 💎"
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
    
    # ==================== PROFILE ====================
    "profile_header": {
        "uz": "👤 *MENING PROFILIM*",
        "ru": "👤 *МОЙ ПРОФИЛЬ*"
    },
    
    "profile_info": {
        "uz": (
            "📊 *Moliyaviy ma'lumotlarim:*\n\n"
            "💰 *Daromad (men):* {income_self}\n"
            "💰 *Daromad (sherik):* {income_partner}\n"
            "🏠 *Ijara:* {rent}\n"
            "👶 *Bog'cha:* {kindergarten}\n"
            "💡 *Kommunal:* {utilities}\n"
            "💳 *Oylik to'lov:* {loan_payment}\n"
            "📉 *Umumiy qarz:* {total_debt}\n\n"
            "📅 *Rejim:* {mode}\n"
            "🌐 *Til:* {language}"
        ),
        "ru": (
            "📊 *Мои финансовые данные:*\n\n"
            "💰 *Доход (я):* {income_self}\n"
            "💰 *Доход (партнёр):* {income_partner}\n"
            "🏠 *Аренда:* {rent}\n"
            "👶 *Детсад:* {kindergarten}\n"
            "💡 *Коммунальные:* {utilities}\n"
            "💳 *Ежемесячный платёж:* {loan_payment}\n"
            "📉 *Общий долг:* {total_debt}\n\n"
            "📅 *Режим:* {mode}\n"
            "🌐 *Язык:* {language}"
        )
    },
    
    "profile_no_data": {
        "uz": "📊 Hali moliyaviy ma'lumotlar kiritilmagan.\n\n/start buyrug'ini bosing va ma'lumotlaringizni kiriting.",
        "ru": "📊 Финансовые данные ещё не введены.\n\nНажмите /start и введите свои данные."
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
        "uz": "👶 Bog'cha",
        "ru": "👶 Детсад"
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
