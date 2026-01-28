"""
AI Yordamchi - Ovozli xabarlarni qayta ishlash va xarajat/daromad tracking
Kotib.ai STT API integratsiyasi
Google Gemini AI integratsiyasi (kategoriya va tahlil uchun)

MULTI-TRANSACTION PARSING ENGINE v2.0
=====================================
Bir ovozli xabarda bir nechta tranzaksiyalarni aniqlash va saqlash
"""

import aiohttp
import os
import re
import io
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Gemini AI (agar mavjud bo'lsa)
try:
    from app.gemini_ai import analyze_with_gemini, smart_categorize, is_gemini_available
    GEMINI_ENABLED = True
except ImportError:
    GEMINI_ENABLED = False
    def is_gemini_available(): return False

# Logger
logger = logging.getLogger(__name__)

# Kotib.ai API konfiguratsiyasi (PRIMARY STT)
KOTIB_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb21wYW55IjoiZWJkYWYyZjctZDc0My00NDUwLTg2MzItOTdhODM0YjE4MTdjIn0.NdyeqX2L61FU6PpBQBo4uYKRSZWS8bXlygJYVlgkrn0"
KOTIB_STT_URL = "https://developer.kotib.ai/api/v1/stt"

# ==================== VOICE LIMITS & TIERS ====================
# Voice Tier System:
# - trial: 10 ta, 10 soniya max (3 kunlik sinov)
# - basic: 30 ta/oy, 30 soniya max (FREE va PRO Basic)
# - plus: 60 ta/oy, 60 soniya max (Voice+ obuna)
# - unlimited: cheksiz, 60 soniya max (Voice Unlimited obuna)

VOICE_TIERS = {
    "trial": {
        "monthly_limit": 10,
        "max_duration": 10,  # soniya - trial uchun cheklangan
        "name_uz": "Sinov",
        "name_ru": "Пробный"
    },
    "basic": {
        "monthly_limit": 30,
        "max_duration": 30,  # soniya
        "name_uz": "Asosiy",
        "name_ru": "Базовый"
    },
    "plus": {
        "monthly_limit": 60,
        "max_duration": 60,  # soniya
        "name_uz": "Voice+",
        "name_ru": "Voice+"
    },
    "unlimited": {
        "monthly_limit": -1,  # cheksiz
        "max_duration": 60,  # soniya
        "name_uz": "Cheksiz",
        "name_ru": "Безлимит"
    }
}

# Voice upgrade prices
VOICE_PLUS_PRICE = 14990      # Voice+ (60 ta, 60 sek) - 1 oy
VOICE_UNLIMITED_PRICE = 29990  # Voice Unlimited - 1 oy

# Legacy constants for backward compatibility
MAX_VOICE_DURATION = 30  # Default max (basic tier)
MONTHLY_VOICE_LIMIT = 30  # Default limit (basic tier)

# Xarajat kategoriyalari
EXPENSE_CATEGORIES = {
    "uz": {
        "oziq_ovqat": "🍔 Oziq-ovqat",
        "transport": "🚗 Transport",
        "uy_joy": "🏠 Uy-joy/Ijara",
        "kommunal": "💡 Kommunal",
        "sog'liq": "💊 Sog'liq",
        "kiyim": "👕 Kiyim-kechak",
        "ta'lim": "📚 Ta'lim",
        "ko'ngilochar": "🎬 Ko'ngilochar",
        "aloqa": "📱 Aloqa",
        "kredit": "💳 Kredit to'lovi",
        "qarz_berdim": "💸 Qarz berdim",
        "obuna": "💎 Obuna",
        "boshqa": "📦 Boshqa"
    },
    "ru": {
        "oziq_ovqat": "🍔 Еда",
        "transport": "🚗 Транспорт",
        "uy_joy": "🏠 Жильё/Аренда",
        "kommunal": "💡 Коммунальные",
        "sog'liq": "💊 Здоровье",
        "kiyim": "👕 Одежда",
        "ta'lim": "📚 Образование",
        "ko'ngilochar": "🎬 Развлечения",
        "aloqa": "📱 Связь",
        "kredit": "💳 Платёж по кредиту",
        "qarz_berdim": "💸 Дал в долг",
        "obuna": "💎 Подписка",
        "boshqa": "📦 Прочее"
    }
}

# Daromad kategoriyalari
INCOME_CATEGORIES = {
    "uz": {
        "ish_haqi": "💼 Ish haqi",
        "biznes": "🏪 Biznes",
        "investitsiya": "📈 Investitsiya",
        "freelance": "💻 Frilanserlik",
        "sovg'a": "🎁 Sovg'a",
        "qarz_qaytarish": "💰 Qarz qaytarish",
        "ijara_daromad": "🏠 Ijara daromadi",
        "boshqa": "📦 Boshqa"
    },
    "ru": {
        "ish_haqi": "💼 Зарплата",
        "biznes": "🏪 Бизнес",
        "investitsiya": "📈 Инвестиции",
        "freelance": "💻 Фриланс",
        "sovg'a": "🎁 Подарок",
        "qarz_qaytarish": "💰 Возврат долга",
        "ijara_daromad": "🏠 Доход от аренды",
        "boshqa": "📦 Прочее"
    }
}

# Kategoriya aniqlash uchun kalit so'zlar - KENGAYTIRILGAN
CATEGORY_KEYWORDS = {
    # Xarajatlar
    "oziq_ovqat": [
        "ovqat", "taom", "restoran", "kafe", "choy", "non", "go'sht", "sabzavot", "meva", 
        "bozor", "magazin", "market", "еда", "продукты", "ресторан", "кафе", "food", "eat",
        "osh", "palov", "somsa", "lag'mon", "shashlik", "tushlik", "nonushta", "kechki",
        "ovqatlandim", "yedim", "ichdim", "olib yedim", "olgani", "sotib oldim ovqat",
        "choyxona", "oshxona", "fastfood", "burger", "pizza", "lavash", "kabob",
        "moshxo'rda", "sho'rva", "manti", "chuchvara", "qazi", "norin"
    ],
    "transport": [
        "taksi", "avtobus", "metro", "benzin", "mashina", "yoqilg'i", "uber", "yandex",
        "такси", "транспорт", "бензин", "taxi", "transport", "fuel", "yo'l", "yol",
        "taksida", "avtobusda", "metroda", "bordim", "keldim", "qaytdim", "olib bordim",
        "olib keldim", "poyezd", "samolyot", "tramvay", "trolleybus", "marshrutka",
        "pochta", "yetkazib berish", "dostavka", "bolt", "mycar"
    ],
    "uy_joy": ["ijara", "uy", "kvartira", "remont", "mebel", "аренда", "квартира", "ремонт", "rent", "house"],
    "kommunal": ["gaz", "suv", "elektr", "tok", "issiqlik", "gas", "вода", "свет", "electricity", "hududiy"],
    "sog'liq": ["dori", "shifoxona", "doktor", "tibbiy", "apteka", "лекарство", "больница", "врач", "medicine", "doctor", "kasalxona", "davolash"],
    "kiyim": ["kiyim", "oyoq kiyim", "ko'ylak", "shim", "одежда", "обувь", "clothes", "shoes", "kurtka", "palto", "futbolka"],
    "ta'lim": ["kurs", "kitob", "o'qish", "ta'lim", "maktab", "курсы", "книги", "обучение", "education", "course", "universitet", "kollej"],
    "ko'ngilochar": ["kino", "teatr", "dam olish", "sayohat", "o'yin", "кино", "отдых", "movie", "entertainment", "konsert", "muzey"],
    "aloqa": ["telefon", "internet", "mobil", "связь", "интернет", "phone", "mobile", "sim", "tarif", "beeline", "ucell", "mobiuz"],
    "kredit": ["kredit", "qarz", "to'lov", "bank", "кредит", "долг", "платёж", "loan", "credit", "ipoteka", "nasiya"],
    
    # Daromadlar
    "ish_haqi": [
        "maosh", "ish haqi", "oylik", "зарплата", "оклад", "salary", "wage",
        "ishlab", "ishladim", "ishlagan", "ishdan", "ish pulim", "topdim",
        "работа", "заработал", "earned", "work", "avans", "bonus", "mukofot"
    ],
    "biznes": [
        "biznes", "savdo", "daromad", "foyda", "sotdim", "бизнес", "продажа", "прибыль", "business", "profit",
        "do'kon", "magazin", "savdo qildim", "tushum", "kassa"
    ],
    "investitsiya": ["dividend", "foiz", "aksiya", "дивиденд", "процент", "акции", "dividend", "investment", "depozit"],
    "freelance": ["frilanser", "buyurtma", "loyiha", "фриланс", "заказ", "проект", "freelance", "project", "ishim", "zakaz"],
    "sovg'a": ["sovg'a", "hadya", "tug'ilgan kun", "подарок", "gift", "present", "tortiq"],
    "qarz_qaytarish": ["qaytarish", "qarz olish", "возврат", "return", "debt return", "qarzimni"]
}


async def transcribe_voice(voice_file_path: str) -> Optional[str]:
    """
    Ovozli faylni textga aylantirish
    Faqat Kotib.ai STT API ishlatiladi
    """
    logger.info(f"[STT] Ovoz faylini o'qish: {voice_file_path}")
    
    # Read file content
    try:
        with open(voice_file_path, 'rb') as f:
            file_content = f.read()
        logger.info(f"[STT] Fayl hajmi: {len(file_content)} bytes")
    except Exception as e:
        logger.error(f"[STT] Fayl o'qishda xato: {e}")
        return None
    
    # Kotib.ai ga so'rov yuborish
    logger.info("[STT] Kotib.ai ga so'rov yuborilmoqda...")
    result = await _transcribe_kotib(file_content)
    
    if result:
        # "Speaker 1:" prefiksini olib tashlash
        result = _clean_kotib_text(result)
        logger.info(f"[STT][Kotib.ai] MUVAFFAQIYATLI: '{result}'")
        return result
    
    logger.error("[STT] Kotib.ai STT ishlamadi!")
    return None


def _clean_kotib_text(text: str) -> str:
    """Kotib.ai natijasini tozalash - 'Speaker X:' prefiksini olib tashlash"""
    import re
    # "Speaker 1:", "Speaker 2:", va hokazo ni olib tashlash
    cleaned = re.sub(r'^Speaker\s*\d+:\s*', '', text, flags=re.IGNORECASE)
    return cleaned.strip()


async def _transcribe_kotib(file_content: bytes) -> Optional[str]:
    """Kotib.ai STT API"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {KOTIB_API_KEY}'}
            
            data = aiohttp.FormData()
            data.add_field('file', file_content, filename='audio.ogg', content_type='audio/ogg')
            data.add_field('language', 'uz')
            data.add_field('blocking', 'true')
            
            async with session.post(KOTIB_STT_URL, data=data, headers=headers, timeout=60) as response:
                response_text = await response.text()
                logger.info(f"[STT][Kotib.ai] Status: {response.status}, Response: {response_text[:500]}")
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        if result.get("status") == "success":
                            text = result.get('text')
                            logger.info(f"[STT][Kotib.ai] Parsed text: '{text}'")
                            return text
                        else:
                            logger.warning(f"[STT][Kotib.ai] Status not success: {result}")
                    except Exception as e:
                        logger.error(f"[STT][Kotib.ai] JSON parse error: {e}")
                return None
    except Exception as e:
        logger.error(f"[STT][Kotib.ai] Exception: {e}")
        return None


# ==================== KOTIB.AI BALANS TEKSHIRISH ====================

# Balans ogohlantirish chegaralari (so'mda)
KOTIB_BALANCE_THRESHOLDS = {
    "critical": 10000,   # 🔴 Kritik - darhol xabar
    "low": 20000,        # 🟠 Kam
    "medium": 50000,     # 🟡 O'rtacha
}

# Ogohlantirish yuborilgan balans (takroriy xabar oldini olish)
_last_alert_balance = None


async def get_kotib_balance() -> Optional[Dict]:
    """
    Kotib.ai API balansini olish
    
    Returns:
        Dict with balance info or None if error
        
    API Response format:
    {
        "balance": "8685",
        "balance_as_duration": "~9m 39s",
        "balance_as_translation": "~45,770 chars"
    }
    """
    try:
        # Kotib.ai balance endpoint - GET /api/v1/get-balance
        balance_url = "https://developer.kotib.ai/api/v1/get-balance"
        
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {KOTIB_API_KEY}'}
            
            try:
                async with session.get(balance_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[Kotib.ai Balance] Response: {result}")
                        
                        # API response: balance, balance_as_duration, balance_as_translation
                        if "balance" in result:
                            # Balance string ko'rinishda keladi, int ga aylantirish
                            balance_str = result.get("balance", "0")
                            try:
                                balance_value = int(balance_str.replace(",", "").strip())
                            except:
                                balance_value = 0
                            
                            return {
                                "balance": balance_value,
                                "balance_raw": balance_str,
                                "duration": result.get("balance_as_duration", "N/A"),
                                "translation": result.get("balance_as_translation", "N/A"),
                                "currency": "UZS",
                                "status": "success"
                            }
                    
                    logger.warning(f"[Kotib.ai Balance] Non-200 status: {response.status}")
                    response_text = await response.text()
                    logger.warning(f"[Kotib.ai Balance] Response: {response_text}")
            except Exception as e:
                logger.warning(f"[Kotib.ai Balance] API error: {e}")
        
        # Agar API ishlamasa, None qaytarish
        return None
        
    except Exception as e:
        logger.error(f"[Kotib.ai Balance] Exception: {e}")
        return None


async def check_kotib_balance_and_alert(bot) -> None:
    """
    Kotib.ai balansini tekshirish va kam bo'lsa @HalosPaybot ga ogohlantirish yuborish
    
    Bu funksiya scheduler orqali chaqiriladi
    """
    global _last_alert_balance
    
    try:
        balance_info = await get_kotib_balance()
        
        if not balance_info:
            logger.warning("[Kotib Balance Alert] Could not get balance")
            return
        
        balance = balance_info.get("balance", 0)
        
        # Ogohlantirish kerakligini tekshirish
        alert_level = None
        if balance <= KOTIB_BALANCE_THRESHOLDS["critical"]:
            alert_level = "critical"
        elif balance <= KOTIB_BALANCE_THRESHOLDS["low"]:
            alert_level = "low"
        elif balance <= KOTIB_BALANCE_THRESHOLDS["medium"]:
            alert_level = "medium"
        
        if not alert_level:
            _last_alert_balance = None  # Reset
            return
        
        # Takroriy xabar yubormaslik
        if _last_alert_balance is not None:
            # Agar balans o'zgargan bo'lsa yoki yangi chegara o'tgan bo'lsa
            if abs(balance - _last_alert_balance) < 5000:
                return  # Takroriy xabar yubormaslik
        
        _last_alert_balance = balance
        
        # Xabar tayyorlash
        if alert_level == "critical":
            emoji = "🔴"
            status = "KRITIK!"
            message = (
                f"{emoji} *KOTIB.AI BALANS KRITIK!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Balans: *{balance:,.0f}* so'm\n\n"
                "⚠️ *DIQQAT!* Ovozli yordamchi tez orada\n"
                "ishlamay qolishi mumkin!\n\n"
                "🔋 Darhol to'ldirish kerak!"
            )
        elif alert_level == "low":
            emoji = "🟠"
            status = "KAM"
            message = (
                f"{emoji} *KOTIB.AI BALANS KAM*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Balans: *{balance:,.0f}* so'm\n\n"
                f"📊 Qolgan xabarlar: ~*{int(balance / 150):,}* ta\n\n"
                "💡 Yaqin orada to'ldirish tavsiya etiladi"
            )
        else:  # medium
            emoji = "🟡"
            status = "O'RTACHA"
            message = (
                f"{emoji} *KOTIB.AI BALANS O'RTACHA*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Balans: *{balance:,.0f}* so'm\n\n"
                f"📊 Qolgan xabarlar: ~*{int(balance / 150):,}* ta\n\n"
                "ℹ️ Kuzatishda davom eting"
            )
        
        # @HalosPaybot ga yuborish
        # Admin ID larga yuborish
        from app.config import ADMIN_IDS
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"[Kotib Balance Alert] Sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"[Kotib Balance Alert] Failed to send to {admin_id}: {e}")
        
    except Exception as e:
        logger.error(f"[Kotib Balance Alert] Exception: {e}")


# ==================== AQLLI AI TAHLIL TIZIMI ====================
# Har bir so'zning kontekstdagi ma'nosini tahlil qiladi

# PHYSICAL ITEMS - bu narsalar "oldim" bilan kelsa = XARAJAT
PHYSICAL_ITEMS = {
    # Oziq-ovqat
    "non", "go'sht", "guruch", "sabzavot", "meva", "sut", "tuxum", "un", "yog'",
    "kolbasa", "pishloq", "shokolad", "choy", "qahva", "suv", "ichimlik", "sharbat",
    "ovqat", "taom", "pivo", "aroq", "vino", "pishiriq", "tort", "shirinlik",
    "kartoshka", "pomidor", "bodring", "piyoz", "sarimsoq", "sabzi", "karam",
    "olma", "anor", "uzum", "banan", "apelsin", "limon", "qovun", "tarvuz",
    "makaron", "tuz", "shakar", "qand", "asal", "konfet", "pechenye", "chips",
    "baliq", "tovuq", "mol go'shti", "qo'y go'shti", "sosiska", "gamburger",
    "lavash", "somsa", "manti", "palov", "osh", "sho'rva", "lag'mon",
    # Transport (xizmat sifatida)
    "taksi", "benzin", "gaz", "avtobus", "metro", "poyezd", "samolyot", "bilet",
    "marshrutka", "tramvay", "trolleybus",
    # Kiyim-kechak
    "kiyim", "ko'ylak", "shim", "oyoq kiyim", "krossovka", "botinka", "tufli",
    "kurtka", "palto", "ko'ylagi", "futbolka", "mayka", "shapka", "sharf",
    "paypoq", "ichki kiyim", "sport kiyim", "kostyum", "galstuk", "belbog'",
    # Texnika va jihozlar
    "telefon", "kompyuter", "noutbuk", "televizor", "muzlatgich", "konditsioner",
    "kir yuvish mashinasi", "changyutgich", "mikrovolnovka", "plita", "choynak",
    "naushnik", "zaryadka", "kabeli", "flesh", "xotira",
    # Uy-joy buyumlari
    "mebel", "stol", "stul", "krovat", "divan", "shkaf", "ko'zgu", "parda",
    "gilam", "ko'rpa", "yostiq", "choyshab", "sochiq", "lagan", "qozon", "pichoq",
    # Sog'liq va gigiyena
    "dori", "tabletka", "vitamin", "maz", "ukol", "bint", "vata",
    "sovun", "shampun", "tish pastasi", "tish cho'tkasi", "krem", "parfyum",
    # Ta'lim va ofis
    "kitob", "daftar", "ruchka", "qalam", "sumka", "portfel",
    # Boshqa
    "o'yinchoq", "sovg'a", "gul", "sham", "batareyka", "lampochka", "sim"
}

# MONEY WORDS - bu so'zlar "oldim" bilan kelsa = DAROMAD
MONEY_WORDS = {
    "pul", "maosh", "oylik", "ish haqi", "avans", "bonus", "mukofot",
    "daromad", "foyda", "tushum", "honorar", "grant", "stipendiya",
    "dividend", "foiz", "kredit", "qarz", "transfer", "o'tkazma",
    "деньги", "зарплата", "аванс", "бонус", "доход", "прибыль"
}

# WORK CONTEXT - bu kontekstlar daromad
WORK_CONTEXTS = {
    "ishlab", "ishlagan", "ishladim", "ishdan", "ish joyida",
    "работал", "заработал", "работа"
}


def detect_transaction_type(text: str) -> str:
    """
    AQLLI AI TAHLIL - Har bir so'zning kontekstdagi ma'nosini aniqlash
    
    QOIDALAR:
    1. PHYSICAL_ITEM + "oldim" = XARAJAT (non oldim, go'sht oldim)
    2. MONEY_WORD + "oldim" = DAROMAD (pul oldim, maosh oldim, oylik oldim)
    3. WORK_CONTEXT + "oldim/topdim" = DAROMAD (ishlab topdim)
    4. "sotdim" = DAROMAD
    5. "to'ladim/berdim/sarfladim" = XARAJAT
    6. Default "oldim" without context = XARAJAT
    """
    text_lower = text.lower()
    
    logger.info(f"[AI] Matn tahlili: '{text_lower[:100]}'")
    
    # ==================== 1. ISH KONTEKSTI TEKSHIRISH ====================
    # "ishlab topdim", "ishlab oldim" = DAROMAD
    for work in WORK_CONTEXTS:
        if work in text_lower:
            if "topdim" in text_lower or "oldim" in text_lower or "keldim" in text_lower:
                logger.info(f"[AI] ISH KONTEKSTI: '{work}' + action = DAROMAD")
                return "income"
    
    # ==================== 2. PUL SO'ZLARI TEKSHIRISH ====================
    # "pul oldim", "maosh oldim", "oylik oldim" = DAROMAD
    for money_word in MONEY_WORDS:
        if money_word in text_lower:
            # "pul oldim", "maosh tushdi", "oylik keldi"
            if "oldim" in text_lower or "tushdi" in text_lower or "keldi" in text_lower:
                logger.info(f"[AI] PUL SO'ZI: '{money_word}' + action = DAROMAD")
                return "income"
    
    # ==================== 3. ANIQ XARAJAT FE'LLARI ====================
    expense_verbs = ["to'ladim", "berdim", "sarfladim", "xarajat", "sotib oldim", 
                     "harid qildim", "потратил", "заплатил", "купил"]
    for verb in expense_verbs:
        if verb in text_lower:
            logger.info(f"[AI] XARAJAT FE'LI: '{verb}' = XARAJAT")
            return "expense"
    
    # ==================== 4. ANIQ DAROMAD FE'LLARI ====================
    income_verbs = ["sotdim", "topshirdim", "yutdim", "продал", "заработал"]
    for verb in income_verbs:
        if verb in text_lower:
            logger.info(f"[AI] DAROMAD FE'LI: '{verb}' = DAROMAD")
            return "income"
    
    # ==================== 5. JISMONIY NARSA + OLDIM = XARAJAT ====================
    # "non oldim", "go'sht oldim", "taksi oldim" = XARAJAT
    if "oldim" in text_lower:
        for item in PHYSICAL_ITEMS:
            if item in text_lower:
                logger.info(f"[AI] JISMONIY NARSA: '{item}' + oldim = XARAJAT")
                return "expense"
        
        # "X ga Y oldim" pattern - summa + nima uchun
        # "10 mingga non oldim" - bu xarajat
        if re.search(r'\d+.*?(ga|uchun)\s+\w+', text_lower):
            logger.info("[AI] SUMMA + GA pattern = XARAJAT")
            return "expense"
    
    # ==================== 6. KONTEKSTSIZ "OLDIM" = XARAJAT ====================
    # Agar "oldim" bor, lekin na pul, na ish konteksti yo'q = XARAJAT
    if "oldim" in text_lower:
        logger.info("[AI] KONTEKSTSIZ 'oldim' = XARAJAT (default)")
        return "expense"
    
    # ==================== 7. "TOPDIM" = DAROMAD ====================
    if "topdim" in text_lower:
        logger.info("[AI] 'topdim' = DAROMAD")
        return "income"
    
    # ==================== 8. TUSHDI/KELDI = DAROMAD ====================
    if "tushdi" in text_lower or "keldi" in text_lower:
        logger.info("[AI] 'tushdi/keldi' = DAROMAD")
        return "income"
    
    # ==================== 9. KETDI/CHIQDI = XARAJAT ====================
    if "ketdi" in text_lower or "chiqdi" in text_lower:
        logger.info("[AI] 'ketdi/chiqdi' = XARAJAT")
        return "expense"
    
    # Default - xarajat (statistika bo'yicha ko'p xarajat yoziladi)
    logger.info("[AI] DEFAULT = XARAJAT")
    return "expense"


def detect_category(text: str, transaction_type: str) -> str:
    """
    Matndan kategoriyani aniqlash
    """
    text_lower = text.lower()
    
    # Qaysi kategoriyalar ro'yxatini ishlatish
    if transaction_type == "income":
        relevant_categories = ["ish_haqi", "biznes", "investitsiya", "freelance", "sovg'a", "qarz_qaytarish"]
    else:
        relevant_categories = ["oziq_ovqat", "transport", "uy_joy", "kommunal", "sog'liq", 
                               "kiyim", "ta'lim", "ko'ngilochar", "aloqa", "kredit"]
    
    best_category = "boshqa"
    best_score = 0
    
    for category in relevant_categories:
        if category in CATEGORY_KEYWORDS:
            score = sum(1 for kw in CATEGORY_KEYWORDS[category] if kw in text_lower)
            if score > best_score:
                best_score = score
                best_category = category
    
    return best_category


def extract_amount(text: str) -> Optional[int]:
    """
    KUCHLI SUMMA ANIQLASH ALGORITMI
    ================================
    
    O'zbek, Rus va Ingliz tillarida yozilgan summalarni aniqlaydi.
    
    Qo'llab-quvvatlaydigan formatlar:
    --------------------------------
    1. Raqam + so'z: "100 ming", "5 million", "100ming"
    2. So'z bilan: "besh yuz ming", "bir million", "yigirma ming"
    3. Qo'shimchalar bilan: "millionga", "mingga", "mingdan", "minglik"
    4. Formatlangan: "1,000,000", "1 000 000"
    5. Oddiy raqam: "500000", "1000000"
    
    Algoritm qoidalari:
    ------------------
    1. Avval matnni tozalash (qo'shimchalarni olib tashlash)
    2. Son so'zlarini raqamlarga aylantirish
    3. Multiplikatorlarni (ming, million, yuz) to'g'ri hisoblash
    4. Eng katta topilgan summani qaytarish
    """
    
    if not text:
        return None
    
    text_lower = text.lower().strip()
    original_text = text
    
    print(f"[SUMMA] Kirish matni: '{text_lower}'")
    
    # ==================== 1-QADAM: MATNNI NORMALIZATSIYA QILISH ====================
    
    # O'zbek qo'shimchalarini olib tashlash uchun maxsus regex
    # "millionga" -> "million", "mingga" -> "ming", "yuzga" -> "yuz"
    
    # Million variantlari
    text_lower = re.sub(r'\b(million|mln)(ga|da|dan|ni|ning|lik|ta|cha|gina|ini|dagi|larcha)\b', r'\1', text_lower)
    text_lower = re.sub(r'\bmillionga\b', 'million', text_lower)
    text_lower = re.sub(r'\bmillionda\b', 'million', text_lower)
    text_lower = re.sub(r'\bmilliondan\b', 'million', text_lower)
    text_lower = re.sub(r'\bmillionni\b', 'million', text_lower)
    text_lower = re.sub(r'\bmillionlik\b', 'million', text_lower)
    
    # Ming variantlari  
    text_lower = re.sub(r'\b(ming)(ga|da|dan|ni|ning|lik|ta|cha|gina|ini|dagi|larcha)\b', r'\1', text_lower)
    text_lower = re.sub(r'\bmingga\b', 'ming', text_lower)
    text_lower = re.sub(r'\bmingda\b', 'ming', text_lower)
    text_lower = re.sub(r'\bmingdan\b', 'ming', text_lower)
    text_lower = re.sub(r'\bmingni\b', 'ming', text_lower)
    text_lower = re.sub(r'\bminglik\b', 'ming', text_lower)
    
    # Yuz variantlari
    text_lower = re.sub(r'\b(yuz)(ga|da|dan|ni|ning|lik|ta|cha|gina|ini|dagi|larcha)\b', r'\1', text_lower)
    text_lower = re.sub(r'\byuzga\b', 'yuz', text_lower)
    text_lower = re.sub(r'\byuzda\b', 'yuz', text_lower)
    text_lower = re.sub(r'\byuzdan\b', 'yuz', text_lower)
    
    print(f"[SUMMA] Tozalangan matn: '{text_lower}'")
    
    # ==================== 2-QADAM: SON SO'ZLARI LUG'ATI ====================
    
    # Birliklar (1-9)
    BIRLIKLAR = {
        'bir': 1, 'ikki': 2, 'uch': 3, 'tort': 4, "to'rt": 4, 'besh': 5,
        'olti': 6, 'yetti': 7, 'sakkiz': 8, 'toqqiz': 9, "to'qqiz": 9,
        # Rus
        'один': 1, 'одна': 1, 'одно': 1, 'два': 2, 'две': 2, 'три': 3,
        'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9,
        # English
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    }
    
    # O'nliklar (10, 20, 30, ... 90)
    ONLIKLAR = {
        'on': 10, "o'n": 10, 'yigirma': 20, 'ottiz': 30, "o'ttiz": 30,
        'qirq': 40, 'ellik': 50, 'oltmish': 60, 'yetmish': 70,
        'sakson': 80, 'toqson': 90, "to'qson": 90,
        # Rus
        'десять': 10, 'двадцать': 20, 'тридцать': 30, 'сорок': 40,
        'пятьдесят': 50, 'шестьдесят': 60, 'семьдесят': 70,
        'восемьдесят': 80, 'девяносто': 90,
        # English
        'ten': 10, 'twenty': 20, 'thirty': 30, 'forty': 40,
        'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
    }
    
    # Yuzliklar (100, 200, ... 900) - faqat Rus tilida alohida so'zlar bor
    YUZLIKLAR_RUS = {
        'сто': 100, 'двести': 200, 'триста': 300, 'четыреста': 400,
        'пятьсот': 500, 'шестьсот': 600, 'семьсот': 700,
        'восемьсот': 800, 'девятьсот': 900,
    }
    
    # Multiplikatorlar
    YUZ = {'yuz': 100, 'сто': 100, 'hundred': 100}
    MING = {'ming': 1000, 'тысяча': 1000, 'тысячи': 1000, 'тысяч': 1000, 'тыс': 1000, 'thousand': 1000, 'k': 1000}
    MILLION = {'million': 1000000, 'mln': 1000000, 'миллион': 1000000, 'миллиона': 1000000, 'миллионов': 1000000, 'млн': 1000000}
    
    # ==================== 3-QADAM: RAQAM + MULTIPLIKATOR PATTERNLARI ====================
    
    # "100 ming", "5 million", "100ming", "5mln"
    digit_thousand = re.search(r'(\d+)\s*ming', text_lower)
    if digit_thousand:
        result = int(digit_thousand.group(1)) * 1000
        print(f"[SUMMA] Raqam+ming topildi: {result}")
        return result
    
    digit_million = re.search(r'(\d+)\s*(million|mln|миллион|млн)', text_lower)
    if digit_million:
        result = int(digit_million.group(1)) * 1000000
        print(f"[SUMMA] Raqam+million topildi: {result}")
        return result
    
    # ==================== 4-QADAM: SO'Z BILAN YOZILGAN SONLAR ====================
    
    # So'zlarni ajratish
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁўғқҳ']+|\d+", text_lower)
    print(f"[SUMMA] So'zlar: {words}")
    
    # Sonlarni hisoblash
    total = 0          # Umumiy natija
    current = 0        # Joriy to'plam (ming/million oldida)
    sub_current = 0    # Yuz ichidagi to'plam
    found_number = False
    
    i = 0
    while i < len(words):
        word = words[i]
        
        # Raqam bo'lsa
        if word.isdigit():
            num = int(word)
            found_number = True
            # Keyingi so'z multiplikator bo'lsa
            if i + 1 < len(words):
                next_word = words[i + 1]
                if next_word in MILLION:
                    total += num * 1000000
                    i += 2
                    continue
                elif next_word in MING:
                    total += num * 1000
                    i += 2
                    continue
                elif next_word in YUZ:
                    current = num * 100
                    i += 2
                    continue
            current = num
            i += 1
            continue
        
        # MILLION
        if word in MILLION:
            found_number = True
            if current == 0 and sub_current == 0:
                current = 1
            total += (current + sub_current) * 1000000
            current = 0
            sub_current = 0
            print(f"[SUMMA] MILLION: total={total}")
            i += 1
            continue
        
        # MING
        if word in MING:
            found_number = True
            if current == 0 and sub_current == 0:
                current = 1
            total += (current + sub_current) * 1000
            current = 0
            sub_current = 0
            print(f"[SUMMA] MING: total={total}")
            i += 1
            continue
        
        # YUZ (o'zbek/ingliz)
        if word in YUZ:
            found_number = True
            if sub_current == 0:
                sub_current = 1
            current += sub_current * 100
            sub_current = 0
            print(f"[SUMMA] YUZ: current={current}")
            i += 1
            continue
        
        # Rus yuzliklar (200, 300, etc.)
        if word in YUZLIKLAR_RUS:
            found_number = True
            current += YUZLIKLAR_RUS[word]
            print(f"[SUMMA] RUS YUZ: current={current}")
            i += 1
            continue
        
        # O'nliklar (10, 20, ... 90)
        if word in ONLIKLAR:
            found_number = True
            sub_current += ONLIKLAR[word]
            print(f"[SUMMA] O'NLIK: sub_current={sub_current}")
            i += 1
            continue
        
        # Birliklar (1-9)
        if word in BIRLIKLAR:
            found_number = True
            sub_current += BIRLIKLAR[word]
            print(f"[SUMMA] BIRLIK: sub_current={sub_current}")
            i += 1
            continue
        
        i += 1
    
    # Qolgan qiymatlarni qo'shish
    total += current + sub_current
    
    if found_number and total > 0:
        print(f"[SUMMA] So'z algoritmi natijasi: {total}")
        return total
    
    # ==================== 5-QADAM: ZAXIRA - FORMATLANGAN RAQAMLAR ====================
    
    # "1,000,000" yoki "1 000 000" formatlar
    formatted_match = re.search(r'(\d{1,3}(?:[,\s]\d{3})+)', original_text)
    if formatted_match:
        num_str = formatted_match.group(1).replace(',', '').replace(' ', '')
        result = int(num_str)
        print(f"[SUMMA] Formatlangan raqam: {result}")
        return result
    
    # Oddiy katta raqam (4+ raqam)
    big_number = re.search(r'\b(\d{4,})\b', original_text)
    if big_number:
        result = int(big_number.group(1))
        print(f"[SUMMA] Katta raqam: {result}")
        return result
    
    # 3 raqamli (100-999)
    three_digit = re.search(r'\b(\d{3})\b', original_text)
    if three_digit:
        result = int(three_digit.group(1))
        print(f"[SUMMA] 3 raqamli: {result}")
        return result
    
    print(f"[SUMMA] Summa topilmadi!")
    return None


def extract_description(text: str, amount: Optional[int]) -> str:
    """
    Matndan tavsifni ajratib olish
    """
    # Raqamlarni olib tashlash
    description = re.sub(r'\d+(?:[,\s]\d+)*', '', text)
    # Ortiqcha so'zlarni olib tashlash
    remove_words = ["so'm", "sum", "сум", "ming", "million", "mln", "млн", "тысяч", "тыс"]
    for word in remove_words:
        description = re.sub(rf'\b{word}\b', '', description, flags=re.IGNORECASE)
    # Bo'shliqlarni tozalash
    description = ' '.join(description.split()).strip()
    return description if description else "Noma'lum"


async def parse_voice_transaction(text: str, lang: str = "uz") -> Dict:
    """
    SELF-LEARNING AI TIZIMI
    =======================
    Matndan to'liq tranzaksiya ma'lumotlarini ajratib olish
    
    ISHLASH TARTIBI:
    1. Avval Local AI (o'rganilgan patternlar) bilan tahlil
    2. Agar ishonch past bo'lsa → Gemini'dan so'rash
    3. Foydalanuvchi tasdiqlasa → Pattern saqlanadi
    4. Keyingi safar tezroq va aniqroq ishlaydi
    """
    from app.self_learning_ai import get_self_learning_ai
    
    # Self-Learning AI instance
    self_ai = get_self_learning_ai()
    
    # ========== 1. LOCAL AI TAHLILI (O'rganilgan patternlar) ==========
    local_result = self_ai.analyze(text)
    
    logger.info(f"[AI] Local tahlil: {local_result['category']} (confidence: {local_result['confidence']}%)")
    
    # Agar ishonch yuqori bo'lsa - to'g'ridan-to'g'ri qaytarish
    if local_result["confidence"] >= 70 and not local_result.get("needs_confirmation"):
        # Kategoriya nomini olish
        if local_result["type"] == "income":
            category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(local_result["category"], "📦 Boshqa")
        else:
            category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(local_result["category"], "📦 Boshqa")
        
        return {
            "type": local_result["type"],
            "category": local_result["category"],
            "category_name": category_name,
            "amount": local_result["amount"],
            "description": local_result["description"],
            "original_text": text,
            "timestamp": datetime.now().isoformat(),
            "ai_source": local_result["source"],
            "confidence": local_result["confidence"],
            "needs_confirmation": False
        }
    
    # ========== 2. GEMINI AI YORDAMI (Ishonch past bo'lsa) ==========
    if GEMINI_ENABLED and is_gemini_available():
        try:
            logger.info("[AI] Ishonch past, Gemini'dan so'ralmoqda...")
            self_ai.increment_gemini_requests()
            
            gemini_result = await analyze_with_gemini(text, lang)
            
            if gemini_result:
                transaction_type = gemini_result.get("type", "expense")
                category = gemini_result.get("category", "boshqa")
                amount = gemini_result.get("amount") or local_result["amount"]
                description = gemini_result.get("description", text[:50])
                
                # Kategoriya nomini olish
                if transaction_type == "income":
                    category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(category, "📦 Boshqa")
                else:
                    category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(category, "📦 Boshqa")
                
                logger.info(f"[AI] Gemini tahlili: {transaction_type} - {category}")
                
                return {
                    "type": transaction_type,
                    "category": category,
                    "category_name": category_name,
                    "amount": amount,
                    "description": description,
                    "original_text": text,
                    "timestamp": datetime.now().isoformat(),
                    "ai_source": "gemini",
                    "confidence": 85,
                    "needs_confirmation": True  # Foydalanuvchi tasdiqlashi kerak
                }
        except Exception as e:
            logger.warning(f"[AI] Gemini xatosi: {e}")
    
    # ========== 3. FALLBACK - Local natija (tasdiqlash bilan) ==========
    if local_result["type"] == "income":
        category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(local_result["category"], "📦 Boshqa")
    else:
        category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(local_result["category"], "📦 Boshqa")
    
    return {
        "type": local_result["type"],
        "category": local_result["category"],
        "category_name": category_name,
        "amount": local_result["amount"],
        "description": local_result["description"],
        "original_text": text,
        "timestamp": datetime.now().isoformat(),
        "ai_source": "local",
        "confidence": local_result["confidence"],
        "needs_confirmation": True  # Past ishonch - tasdiqlash kerak
    }


async def confirm_and_learn(text: str, confirmed_result: Dict) -> bool:
    """
    Foydalanuvchi tasdiqlagan natijadan o'rganish
    
    Bu funksiya callback handler'da chaqiriladi
    """
    from app.self_learning_ai import get_self_learning_ai
    
    self_ai = get_self_learning_ai()
    success = self_ai.learn_from_confirmation(text, confirmed_result)
    
    if success:
        logger.info(f"[AI] Yangi pattern o'rganildi: {text[:30]}... -> {confirmed_result['category']}")
    
    return success


async def learn_from_correction(text: str, wrong_result: Dict, correct_result: Dict) -> bool:
    """
    XATOLARDAN O'RGANISH - ENG QIMMATLI!
    
    Foydalanuvchi tuzatganda chaqiriladi
    AI xatosidan xulosa chiqarib, keyingi safar to'g'ri qiladi
    """
    from app.self_learning_ai import get_self_learning_ai
    
    self_ai = get_self_learning_ai()
    success = self_ai.learn_from_correction(text, wrong_result, correct_result)
    
    if success:
        logger.info(f"[AI] XATADAN O'RGANILDI: {text[:30]}... | {wrong_result.get('category')} -> {correct_result.get('category')}")
    
    return success


async def learn_from_multi_transaction(text: str, transactions: List[Dict]) -> bool:
    """
    Ko'p tranzaksiyali xabarlardan o'rganish
    """
    from app.self_learning_ai import get_self_learning_ai
    
    self_ai = get_self_learning_ai()
    return self_ai.learn_from_multi_transaction(text, transactions)


def check_learned_patterns(text: str) -> Optional[Dict]:
    """
    Avval o'rganilgan patternlarni tekshirish
    Gemini ga murojaat qilishdan oldin chaqiriladi
    """
    from app.self_learning_ai import get_self_learning_ai
    
    self_ai = get_self_learning_ai()
    return self_ai.check_learned_patterns_first(text)


def get_ai_stats() -> Dict:
    """AI statistikasini olish - KENGAYTIRILGAN"""
    from app.self_learning_ai import get_self_learning_ai
    return get_self_learning_ai().get_stats()


# ==================== ADVANCED MULTI-TRANSACTION PARSING ENGINE v4.0 ====================
"""
KUCHLI ALGORITM - Bir xabarda bir nechta daromad va xarajatlarni aniqlash
YANGI: O'rganilgan patternlarni birinchi tekshirish!

Misol: "bugun yuz ming ishlab topdim on minga non oldim yigirma ming yolkira qildim 5 minga suv ichdim"

Natija:
1. 💼 Ish haqi - 100,000 so'm (daromad) - "ishlab topdim"
2. 🍔 Oziq-ovqat - 10,000 so'm (xarajat) - "non oldim"
3. 🚗 Transport - 20,000 so'm (xarajat) - "yo'l kira qildim"
4. 🍔 Oziq-ovqat - 5,000 so'm (xarajat) - "suv ichdim"
"""

# O'zbek son so'zlari - KENGAYTIRILGAN
UZBEK_NUMBERS = {
    # Birliklar
    'bir': 1, 'ikki': 2, 'uch': 3, 'tort': 4, "to'rt": 4, 'besh': 5,
    'olti': 6, 'yetti': 7, 'sakkiz': 8, 'toqqiz': 9, "to'qqiz": 9,
    # O'nliklar
    'on': 10, "o'n": 10, 'yigirma': 20, 'ottiz': 30, "o'ttiz": 30,
    'qirq': 40, 'ellik': 50, 'oltmish': 60, 'yetmish': 70,
    'sakson': 80, 'toqson': 90, "to'qson": 90,
    # Yuz
    'yuz': 100,
}

# Multiplikatorlar
MULTIPLIERS = {
    'ming': 1000, 'mingga': 1000, 'mingda': 1000, 'mingdan': 1000, 'mingni': 1000,
    'million': 1000000, 'mln': 1000000, 'millionni': 1000000,
}

# Daromad indikatorlari (kuchli)
INCOME_INDICATORS = [
    'ishlab topdim', 'ishlab oldim', 'ishlagan pulim', 'ish pulim', 'ishladim',
    'topib oldim', 'topgan pulim', 'topdim', 'topgan',
    'maosh', 'oylik', 'ish haqi', 'ish haqim', 'oyligim',
    'oldim daromad', 'pul oldim', 'pul tushdi', 'pul keldi',
    'sotdim', 'savdodan', 'foyda oldim', 'daromad qildim',
    'заработал', 'зарплата', 'получил', 'доход',
    'earned', 'received', 'salary', 'income', 'got paid'
]

# Xarajat indikatorlari (kuchli)
EXPENSE_INDICATORS = [
    'oldim', 'olib', 'olgan', 'sotib oldim', 'harid qildim',
    'berdim', 'berib', 'bergan', 'to\'ladim', 'to\'lab',
    'sarfladim', 'sarf qildim', 'xarajat qildim',
    'ketdi', 'ketgan', 'chiqim', 'chiqdi',
    'yedim', 'ichdim', 'ovqatlandim',
    'bordim', 'keldim', 'qaytdim', 'qildim',
    'купил', 'потратил', 'заплатил', 'оплатил',
    'paid', 'spent', 'bought', 'purchased'
]

# Kategoriya kalit so'zlari - YANADA KENGAYTIRILGAN
SMART_CATEGORY_KEYWORDS = {
    # ========== XARAJAT KATEGORIYALARI ==========
    "oziq_ovqat": {
        "keywords": [
            "non", "ovqat", "taom", "yedim", "ichdim", "ovqatlandim", 
            "restoran", "kafe", "choy", "go'sht", "sabzavot", "meva",
            "bozor", "magazin", "market", "osh", "palov", "somsa", 
            "lag'mon", "shashlik", "tushlik", "nonushta", "kechki",
            "choyxona", "oshxona", "fastfood", "burger", "pizza", 
            "lavash", "kabob", "moshxo'rda", "sho'rva", "manti", 
            "chuchvara", "qazi", "norin", "suv", "cola", "pepsi",
            "sok", "juice", "kofe", "coffee", "pivo", "beer",
            "еда", "продукты", "хлеб", "вода", "food", "bread", "water"
        ],
        "type": "expense",
        "weight": 3
    },
    "transport": {
        "keywords": [
            "taksi", "taksida", "taksiga", "avtobus", "metro", "benzin", 
            "mashina", "yoqilg'i", "uber", "yandex", "yo'l", "yol",
            "bordim", "keldim", "qaytdim", "olib bordim", "olib keldim", 
            "poyezd", "samolyot", "tramvay", "trolleybus", "marshrutka",
            "yetkazib berish", "dostavka", "bolt", "mycar", "kira",
            "yolkira", "yo'lkira", "transport",
            "такси", "транспорт", "бензин", "taxi", "bus", "fuel"
        ],
        "type": "expense",
        "weight": 3
    },
    "uy_joy": {
        "keywords": [
            "ijara", "uy", "kvartira", "remont", "mebel", "uy-joy",
            "аренда", "квартира", "ремонт", "rent", "house", "apartment"
        ],
        "type": "expense",
        "weight": 2
    },
    "kommunal": {
        "keywords": [
            "gaz", "suv to'lov", "elektr", "tok", "issiqlik", "hududiy",
            "komunal", "kommunal", "счёт", "коммунальные", "electricity", "gas bill"
        ],
        "type": "expense",
        "weight": 2
    },
    "sog'liq": {
        "keywords": [
            "dori", "shifoxona", "doktor", "tibbiy", "apteka", "kasalxona", 
            "davolash", "vrach", "tabletka",
            "лекарство", "больница", "врач", "аптека", "medicine", "doctor", "hospital"
        ],
        "type": "expense",
        "weight": 2
    },
    "kiyim": {
        "keywords": [
            "kiyim", "oyoq kiyim", "ko'ylak", "shim", "kurtka", "palto", 
            "futbolka", "krossovka", "tufli",
            "одежда", "обувь", "clothes", "shoes", "shirt", "pants"
        ],
        "type": "expense",
        "weight": 2
    },
    "ta'lim": {
        "keywords": [
            "kurs", "kitob", "o'qish", "ta'lim", "maktab", "universitet", 
            "kollej", "darslik", "repetitor",
            "курсы", "книги", "обучение", "education", "course", "book"
        ],
        "type": "expense",
        "weight": 2
    },
    "ko'ngilochar": {
        "keywords": [
            "kino", "teatr", "dam olish", "sayohat", "o'yin", "konsert", 
            "muzey", "park", "akvpark",
            "кино", "отдых", "movie", "entertainment", "game", "travel"
        ],
        "type": "expense",
        "weight": 2
    },
    "aloqa": {
        "keywords": [
            "telefon", "internet", "mobil", "sim", "tarif", "beeline", 
            "ucell", "mobiuz", "uzmobile",
            "связь", "интернет", "phone", "mobile", "internet"
        ],
        "type": "expense",
        "weight": 2
    },
    "kredit": {
        "keywords": [
            "kredit", "qarz to'lov", "bank", "ipoteka", "nasiya", "to'lov",
            "кредит", "платёж", "loan", "credit", "payment"
        ],
        "type": "expense",
        "weight": 2
    },
    
    # ========== DAROMAD KATEGORIYALARI ==========
    "ish_haqi": {
        "keywords": [
            "maosh", "ish haqi", "oylik", "ishlab", "ishladim", "ishlagan", 
            "ishdan", "ish pulim", "topdim", "topgan", "avans", "bonus", "mukofot",
            "зарплата", "оклад", "заработал", "salary", "wage", "earned", "work"
        ],
        "type": "income",
        "weight": 4
    },
    "biznes": {
        "keywords": [
            "biznes", "savdo", "daromad", "foyda", "sotdim", "do'kon", 
            "magazin", "savdo qildim", "tushum", "kassa",
            "бизнес", "продажа", "прибыль", "business", "profit", "sale"
        ],
        "type": "income",
        "weight": 3
    },
    "investitsiya": {
        "keywords": [
            "dividend", "foiz", "aksiya", "depozit", "investitsiya",
            "дивиденд", "процент", "акции", "dividend", "investment", "stock"
        ],
        "type": "income",
        "weight": 3
    },
    "freelance": {
        "keywords": [
            "frilanser", "buyurtma", "loyiha", "ishim", "zakaz", "project",
            "фриланс", "заказ", "проект", "freelance", "order"
        ],
        "type": "income",
        "weight": 3
    },
    "sovg'a": {
        "keywords": [
            "sovg'a", "hadya", "tug'ilgan kun", "tortiq", "berdi",
            "подарок", "gift", "present"
        ],
        "type": "income",
        "weight": 2
    },
    "qarz_qaytarish": {
        "keywords": [
            "qarz qaytarish", "qarzimni", "qaytardi", "qarz olish",
            "возврат долга", "debt return", "returned"
        ],
        "type": "income",
        "weight": 2
    },
}


def find_all_amounts_with_context(text: str) -> List[Dict]:
    """
    KUCHAYTIRILGAN SUMMA ANIQLASH ALGORITMI v5.0
    ============================================
    
    Matndan BARCHA summalarni va ularning kontekstini topish.
    HECH QANDAY SUMMANI TASHLAB KETMASLIGI KAFOLATLANADI!
    
    Qo'llab-quvvatlanadigan formatlar:
    1. "yuz ming" = 100,000
    2. "on ming" = 10,000 
    3. "besh ming" = 5,000
    4. "yigirma besh ming" = 25,000
    5. "100 ming" = 100,000
    6. "5 minga" = 5,000
    7. "1000000" = 1,000,000
    8. "bir million" = 1,000,000
    9. "100 000" = 100,000 (bo'sh joy bilan)
    10. "10 000" = 10,000 (bo'sh joy bilan)
    """
    # MUHIM: Avval bo'sh joylarni tozalash (100 000 -> 100000)
    text_cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    text_lower = text_cleaned.lower().strip()
    
    results = []
    
    print(f"\n{'='*60}")
    print(f"[FIND_AMOUNTS v5.0] Original: '{text}'")
    print(f"[FIND_AMOUNTS v5.0] Cleaned: '{text_lower}'")
    print(f"{'='*60}")
    
    # Barcha ishlatilgan pozitsiyalar
    used_positions = set()
    
    # ==================== SO'Z SONLARI LUG'ATI ====================
    NUMBERS = {
        # Birliklar
        'bir': 1, 'ikki': 2, 'uch': 3, 'tort': 4, "to'rt": 4, 'besh': 5,
        'olti': 6, 'yetti': 7, 'sakkiz': 8, 'toqqiz': 9, "to'qqiz": 9,
        # O'nliklar
        'on': 10, "o'n": 10, 'yigirma': 20, 'ottiz': 30, "o'ttiz": 30,
        'qirq': 40, 'ellik': 50, 'oltmish': 60, 'yetmish': 70,
        'sakson': 80, 'toqson': 90, "to'qson": 90,
        # Yuz
        'yuz': 100,
    }
    
    # ==================== PATTERN 1: YUZ MING (100,000) ====================
    # "yuz ming", "yuz mingga", "yuz mingda"
    pattern_yuz_ming = r'\byuz\s+(ming(?:ga|da|dan|ni|lik)?)\b'
    for match in re.finditer(pattern_yuz_ming, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        amount = 100000
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [YUZ MING] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 2: O'NLIK + MING (10,000 - 90,000) ====================
    # "on ming", "yigirma ming", "ellik mingga"
    onliklar = "o'?n|yigirma|o'?ttiz|qirq|ellik|oltmish|yetmish|sakson|to'?qson"
    pattern_onlik_ming = rf'\b({onliklar})\s+(ming(?:ga|da|dan|ni|lik)?)\b'
    for match in re.finditer(pattern_onlik_ming, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        word = match.group(1).replace("'", "'")
        num = NUMBERS.get(word, NUMBERS.get(word.replace("o'", "o'"), 10))
        amount = num * 1000
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [O'NLIK MING] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 3: BIRLIK + MING (1,000 - 9,000) ====================
    # "bir ming", "besh ming", "5 minga"
    birliklar = "bir|ikki|uch|to'?rt|besh|olti|yetti|sakkiz|to'?qqiz"
    pattern_birlik_ming = rf'\b({birliklar})\s+(ming(?:ga|da|dan|ni|lik)?)\b'
    for match in re.finditer(pattern_birlik_ming, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        word = match.group(1).replace("'", "'")
        num = NUMBERS.get(word, NUMBERS.get(word.replace("o'", "o'").replace("to'", "to'"), 1))
        amount = num * 1000
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [BIRLIK MING] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 4: O'NLIK + BIRLIK + MING (11,000 - 99,000) ====================
    # "yigirma besh ming", "o'n ikki ming"
    pattern_complex = rf'\b({onliklar})\s+({birliklar})\s+(ming(?:ga|da|dan|ni|lik)?)\b'
    for match in re.finditer(pattern_complex, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        word1 = match.group(1).replace("'", "'")
        word2 = match.group(2).replace("'", "'")
        num1 = NUMBERS.get(word1, NUMBERS.get(word1.replace("o'", "o'"), 10))
        num2 = NUMBERS.get(word2, NUMBERS.get(word2.replace("o'", "o'").replace("to'", "to'"), 1))
        amount = (num1 + num2) * 1000
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [O'NLIK+BIRLIK MING] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 5: RAQAM + MING ====================
    # "100 ming", "5 minga", "50mingga"
    pattern_digit_ming = r'\b(\d+)\s*(ming(?:ga|da|dan|ni|lik)?)\b'
    for match in re.finditer(pattern_digit_ming, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        amount = int(match.group(1)) * 1000
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [RAQAM MING] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 6: MILLION ====================
    # "bir million", "5 million", "1 mln"
    pattern_million = r'\b(\d+|bir|ikki|uch|to\'?rt|besh|olti|yetti|sakkiz|to\'?qqiz|on)\s*(million|mln|миллион|млн)'
    for match in re.finditer(pattern_million, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        word = match.group(1)
        if word.isdigit():
            num = int(word)
        else:
            num = NUMBERS.get(word.replace("'", "'"), 1)
        amount = num * 1000000
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [MILLION] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 7: KATTA RAQAMLAR (5+ xonali) ====================
    # "100000", "1000000", "50000"
    pattern_big_num = r'\b(\d{5,})\b'
    for match in re.finditer(pattern_big_num, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        amount = int(match.group(1))
        
        context_after = text_lower[end:end+60].strip()
        context_before = text_lower[max(0,start-40):start].strip()
        
        results.append({
            "amount": amount,
            "start": start,
            "end": end,
            "text": match.group(0),
            "context_before": context_before,
            "context_after": context_after
        })
        used_positions.update(range(start, end))
        print(f"  [KATTA RAQAM] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 8: 4 XONALI RAQAMLAR (1000-9999) ====================
    # "5000", "1000"
    pattern_4digit = r'\b(\d{4})\b'
    for match in re.finditer(pattern_4digit, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        amount = int(match.group(1))
        if amount >= 1000:  # faqat 1000+ 
            context_after = text_lower[end:end+60].strip()
            context_before = text_lower[max(0,start-40):start].strip()
            
            results.append({
                "amount": amount,
                "start": start,
                "end": end,
                "text": match.group(0),
                "context_before": context_before,
                "context_after": context_after
            })
            used_positions.update(range(start, end))
            print(f"  [4-XONALI] '{match.group(0)}' = {amount:,}")
    
    # ==================== PATTERN 9: 3 XONALI RAQAMLAR (100-999) ====================
    # "500", "100" - faqat so'm/sum bo'lsa yoki kontekst bo'lsa
    pattern_3digit = r'\b(\d{3})\b'
    for match in re.finditer(pattern_3digit, text_lower):
        start, end = match.start(), match.end()
        if any(p in range(start, end) for p in used_positions):
            continue
        
        amount = int(match.group(1))
        if amount >= 100:
            # Faqat so'm/sum bilan birga kelsa qabul qilish
            after_text = text_lower[end:end+20]
            if re.search(r"so'm|sum|сум", after_text):
                context_after = text_lower[end:end+60].strip()
                context_before = text_lower[max(0,start-40):start].strip()
                
                results.append({
                    "amount": amount,
                    "start": start,
                    "end": end,
                    "text": match.group(0),
                    "context_before": context_before,
                    "context_after": context_after
                })
                used_positions.update(range(start, end))
                print(f"  [3-XONALI] '{match.group(0)}' = {amount:,}")
    
    # Pozitsiya bo'yicha tartiblash
    results.sort(key=lambda x: x['start'])
    
    print(f"\n[FIND_AMOUNTS] ✅ Jami {len(results)} ta summa topildi!")
    for r in results:
        print(f"  - {r['amount']:,} so'm: '{r['text']}'")
    print(f"{'='*60}\n")
    
    return results


async def determine_transaction_type_and_category_smart(context_before: str, context_after: str, 
                                                         text_lower: str, db=None) -> Tuple[str, str, str]:
    """
    SELF-LEARNING AI - Kontekst asosida tranzaksiya turini va kategoriyasini aniqlash.
    
    MUHIM: "X oldim" ni tahlil qilishda X nimaga qarab qaror qiladi:
    - "non oldim", "go'sht oldim", "suv oldim" → XARAJAT (jismoniy narsa)
    - "pul oldim", "oylik oldim", "maosh oldim" → DAROMAD (pul so'zi)
    - "ishlab topdim", "ishlagan pulim" → DAROMAD (ish konteksti)
    
    Returns: (transaction_type, category_key, category_name)
    """
    full_context = f"{context_before} {context_after}".lower()
    
    print(f"    [SMART-DETECT] Context: '{full_context}'")
    
    # ==================== 1. AI O'RGANGAN PATTERNLARNI TEKSHIRISH ====================
    # Avval database dan o'rgangan patternlarni tekshirish
    if db:
        try:
            learned = await db.check_ai_pattern(full_context)
            if learned:
                print(f"    [SMART-DETECT] 🧠 AI o'rgangan pattern topildi: {learned['pattern']}")
                print(f"    [SMART-DETECT] 🎯 Confidence: {learned['confidence']}, Count: {learned['correction_count']}")
                return learned["correct_type"], learned["correct_category"], ""
        except Exception as e:
            print(f"    [SMART-DETECT] AI learning check error: {e}")
    
    # ==================== 2. JISMONIY NARSA + OLDIM = XARAJAT ====================
    # Bu eng muhim qoida: agar "non", "go'sht", "suv" kabi narsa + "oldim" bo'lsa = XARAJAT
    PHYSICAL_ITEMS = {
        # Oziq-ovqat
        'non', 'gosht', "go'sht", 'suv', 'choy', 'kofe', 'meva', 'sabzavot', 'guruch', 'un',
        'qand', 'shakar', 'tuz', 'yog', "yog'", 'sut', 'tuxum', 'tovuq', 'baliq', 'kolbasa',
        'pishloq', 'smetana', 'qatiq', 'kefir', 'yogurt', 'shokolad', 'pechenye', 'tort',
        'shirinlik', 'muzqaymoq', 'chips', 'gazak', 'pivo', 'vino', 'aroq', 'sigaret',
        'osh', 'palov', 'somsa', 'manti', 'chuchvara', 'lagmon', "lag'mon", 'shashlik',
        'kabob', 'burger', 'pizza', 'lavash', 'hotdog', 'sendvich',
        # Kiyim
        'kiyim', 'oyoq', "ko'ylak", 'koylak', 'shim', 'kurtka', 'palto', 'krossovka',
        'tufli', 'botinka', 'shapka', 'kepka', 'galstuk', 'kemer', 'sumka', 'ryukzak',
        # Uy jihozlari
        'mebel', 'stol', 'stul', 'divan', 'krovat', 'shkaf', 'kreslo', 'lamp', 'gilam',
        'parda', 'idish', 'kastrulka', 'skovoroda', 'choynak', 'piyola', 'qoshiq',
        # Texnika
        'telefon', 'noutbuk', 'kompyuter', 'televizor', 'muzlatgich', 'konditsioner',
        'kir yuvish', 'changyutgich', 'dazmol', 'fen', 'mikser',
        # Dori
        'dori', 'tabletka', 'vitamin', 'maz', 'ukol', 'shpris',
        # Transport xizmati (lekin transport = expense)
        'benzin', 'yoqilgi', "yoqilg'i", 'gaz',
    }
    
    # "oldim" so'zi kontekstda borligini tekshirish
    if 'oldim' in full_context or 'olgan' in full_context or 'olib' in full_context:
        # Jismoniy narsa borligini tekshirish
        for item in PHYSICAL_ITEMS:
            if item in full_context:
                print(f"    [SMART-DETECT] 🛒 Jismoniy narsa topildi: '{item}' + oldim = XARAJAT")
                # Kategoriyani aniqlash
                category = detect_expense_category(full_context)
                return "expense", category, ""
    
    # ==================== 3. PUL SO'ZI + OLDIM = DAROMAD ====================
    MONEY_WORDS = {'pul', 'maosh', 'oylik', 'ish haqi', 'daromad', 'foyda', 'bonus', 'mukofot',
                   'stipendiya', 'nafaqa', 'pensiya', 'grant'}
    
    if 'oldim' in full_context or 'olgan' in full_context:
        for word in MONEY_WORDS:
            if word in full_context:
                print(f"    [SMART-DETECT] 💰 Pul so'zi topildi: '{word}' + oldim = DAROMAD")
                return "income", "ish_haqi", ""
    
    # ==================== 4. ISH KONTEKSTI = DAROMAD ====================
    WORK_INDICATORS = ['ishlab topdim', 'ishlab oldim', 'ishlagan', 'ishladim', 
                       'topib oldim', 'topgan', 'topdim pul', 'sotdim', 'savdo qildim']
    
    for indicator in WORK_INDICATORS:
        if indicator in full_context:
            print(f"    [SMART-DETECT] 💼 Ish konteksti topildi: '{indicator}' = DAROMAD")
            return "income", "ish_haqi", ""
    
    # ==================== 5. TRANSPORT KONTEKSTI = XARAJAT ====================
    TRANSPORT_KEYWORDS = ['taksi', 'taksiga', 'taksida', 'yolkira', "yo'lkira", 'avtobus',
                          'metro', 'marshrutka', 'poyezd', 'samolyot', 'uber', 'yandex', 'bolt']
    
    for kw in TRANSPORT_KEYWORDS:
        if kw in full_context:
            print(f"    [SMART-DETECT] 🚗 Transport topildi: '{kw}' = XARAJAT")
            return "expense", "transport", ""
    
    # ==================== 6. UMUMIY DAROMAD/XARAJAT INDIKATORLARI ====================
    income_score = 0
    expense_score = 0
    
    for indicator in INCOME_INDICATORS:
        if indicator in full_context:
            income_score += 3
            print(f"    [SMART-DETECT] Income indicator: '{indicator}' (+3)")
    
    for indicator in EXPENSE_INDICATORS:
        if indicator in full_context:
            expense_score += 2
            print(f"    [SMART-DETECT] Expense indicator: '{indicator}' (+2)")
    
    # ==================== 7. KATEGORIYANI ANIQLASH ====================
    best_category = "boshqa"
    best_score = 0
    best_type = "expense"  # default
    
    for cat_key, cat_info in SMART_CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in cat_info["keywords"]:
            if keyword in full_context:
                score += cat_info["weight"]
        
        if score > best_score:
            best_score = score
            best_category = cat_key
            best_type = cat_info["type"]
    
    # Daromad indikatori kuchli bo'lsa
    if income_score > expense_score + 2 and income_score >= 3:
        best_type = "income"
        if SMART_CATEGORY_KEYWORDS.get(best_category, {}).get("type") == "expense":
            best_category = "ish_haqi"
    
    # Kategoriya nomini olish
    lang = "uz"
    if best_type == "income":
        category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(best_category, "📦 Boshqa")
    else:
        category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(best_category, "📦 Boshqa")
    
    print(f"    [SMART-DETECT] Final: type={best_type}, category={best_category}")
    
    return best_type, best_category, category_name


def detect_expense_category(context: str) -> str:
    """Xarajat kategoriyasini aniqlash"""
    # Oziq-ovqat
    food_words = ['non', 'gosht', "go'sht", 'suv', 'choy', 'meva', 'sabzavot', 'osh', 'ovqat', 
                  'yedim', 'ichdim', 'tushlik', 'kechki', 'nonushta', 'restoran', 'kafe']
    if any(w in context for w in food_words):
        return "oziq_ovqat"
    
    # Transport
    transport_words = ['taksi', 'avtobus', 'metro', 'benzin', 'yolkira', "yo'lkira", 'mashina']
    if any(w in context for w in transport_words):
        return "transport"
    
    # Kiyim
    clothes_words = ['kiyim', "ko'ylak", 'shim', 'kurtka', 'krossovka', 'tufli']
    if any(w in context for w in clothes_words):
        return "kiyim"
    
    # Dori
    medicine_words = ['dori', 'apteka', 'shifoxona', 'tabletka', 'vrach']
    if any(w in context for w in medicine_words):
        return "sog'liq"
    
    return "boshqa"


def determine_transaction_type_and_category(context_before: str, context_after: str, text_lower: str) -> Tuple[str, str, str]:
    """
    MUHIM: Faqat CONTEXT_AFTER ga qarab kategoriya aniqlanadi!
    Chunki summa + keyingi so'z = nima uchun sarflangan
    
    Misol: "20 ming yo'lkira qildim, 50 minga ovqatlandim"
    - 20 ming -> context_after = "yo'lkira qildim" -> TRANSPORT
    - 50 ming -> context_after = "ovqatlandim" -> OZIQ-OVQAT
    
    Returns: (transaction_type, category_key, category_name)
    """
    # MUHIM: Faqat context_after ishlatiladi - bu summadan keyingi so'zlar
    local_context = context_after.lower().strip()
    
    print(f"    [DETECT] Local context (after amount): '{local_context}'")
    
    # ==================== 1. OZIQ-OVQAT TEKSHIRISH (BIRINCHI!) ====================
    FOOD_KEYWORDS = [
        'ovqat', 'ovqatlandim', 'yedim', 'ichdim', 'tushlik', 'nonushta', 'kechki',
        'restoran', 'kafe', 'choyxona', 'oshxona', 'taom', 
        'non', 'gosht', "go'sht", 'suv', 'choy', 'kofe', 'meva', 'sabzavot',
        'osh', 'palov', 'somsa', 'manti', 'chuchvara', 'lagmon', 'shashlik', 
        'kabob', 'burger', 'pizza', 'lavash', 'hotdog'
    ]
    for kw in FOOD_KEYWORDS:
        if kw in local_context:
            print(f"    [DETECT] 🍔 Oziq-ovqat topildi: '{kw}'")
            return "expense", "oziq_ovqat", EXPENSE_CATEGORIES.get("uz", {}).get("oziq_ovqat", "🍔 Oziq-ovqat")
    
    # ==================== 2. TRANSPORT TEKSHIRISH ====================
    TRANSPORT_KEYWORDS = [
        'taksi', 'taksiga', 'taksida', 'yolkira', "yo'lkira", 'yol kira',
        'avtobus', 'metro', 'marshrutka', 'poyezd', 'samolyot',
        'uber', 'yandex', 'bolt', 'mycar', 'benzin', 'yoqilgi'
    ]
    for kw in TRANSPORT_KEYWORDS:
        if kw in local_context:
            print(f"    [DETECT] 🚗 Transport topildi: '{kw}'")
            return "expense", "transport", EXPENSE_CATEGORIES.get("uz", {}).get("transport", "🚗 Transport")
    
    # ==================== 3. KIYIM TEKSHIRISH ====================
    CLOTHES_KEYWORDS = ['kiyim', "ko'ylak", 'koylak', 'shim', 'kurtka', 'palto', 
                        'krossovka', 'tufli', 'botinka', 'oyoq kiyim']
    for kw in CLOTHES_KEYWORDS:
        if kw in local_context:
            print(f"    [DETECT] 👕 Kiyim topildi: '{kw}'")
            return "expense", "kiyim", EXPENSE_CATEGORIES.get("uz", {}).get("kiyim", "👕 Kiyim-kechak")
    
    # ==================== 4. DORI/SOG'LIQ TEKSHIRISH ====================
    HEALTH_KEYWORDS = ['dori', 'apteka', 'shifoxona', 'tabletka', 'vrach', 'doktor', 'kasalxona']
    for kw in HEALTH_KEYWORDS:
        if kw in local_context:
            print(f"    [DETECT] 💊 Sog'liq topildi: '{kw}'")
            return "expense", "sog'liq", EXPENSE_CATEGORIES.get("uz", {}).get("sog'liq", "💊 Sog'liq")
    
    # ==================== 5. KOMMUNAL TEKSHIRISH ====================
    KOMMUNAL_KEYWORDS = ['gaz', 'elektr', 'tok', 'suv tolov', 'kommunal', 'hududiy']
    for kw in KOMMUNAL_KEYWORDS:
        if kw in local_context:
            print(f"    [DETECT] 💡 Kommunal topildi: '{kw}'")
            return "expense", "kommunal", EXPENSE_CATEGORIES.get("uz", {}).get("kommunal", "💡 Kommunal")
    
    # ==================== 6. DAROMAD TEKSHIRISH ====================
    INCOME_KEYWORDS_LOCAL = [
        'ishlab topdim', 'ishlab oldim', 'ishlagan', 'ishladim', 
        'topdim', 'topgan', 'maosh', 'oylik', 'ish haqi',
        'sotdim', 'savdo', 'foyda', 'daromad'
    ]
    for kw in INCOME_KEYWORDS_LOCAL:
        if kw in local_context:
            print(f"    [DETECT] 💼 Daromad topildi: '{kw}'")
            return "income", "ish_haqi", INCOME_CATEGORIES.get("uz", {}).get("ish_haqi", "💼 Ish haqi")
    
    # ==================== 7. JISMONIY NARSA + OLDIM ====================
    PHYSICAL_ITEMS = {
        'non', 'gosht', "go'sht", 'suv', 'choy', 'kofe', 'meva', 'sabzavot',
        'guruch', 'un', 'sut', 'tuxum', 'tovuq', 'baliq', 
        'telefon', 'noutbuk', 'kompyuter', 'mebel'
    }
    
    if 'oldim' in local_context or 'olgan' in local_context:
        for item in PHYSICAL_ITEMS:
            if item in local_context:
                print(f"    [DETECT] 🛒 Jismoniy narsa: '{item}' + oldim")
                category = detect_expense_category(local_context)
                return "expense", category, EXPENSE_CATEGORIES.get("uz", {}).get(category, "📦 Boshqa")
    
    # ==================== 8. UMUMIY XARAJAT INDIKATORLARI ====================
    EXPENSE_VERBS = ['berdim', 'berib', 'sarfladim', 'to\'ladim', 'xarajat', 
                     'ketdi', 'chiqdi', 'qildim', 'oldim']
    for verb in EXPENSE_VERBS:
        if verb in local_context:
            print(f"    [DETECT] 📤 Xarajat verb topildi: '{verb}'")
            # Kategoriyani context_before dan ham qidirish
            combined = f"{context_before} {local_context}".lower()
            category = detect_expense_category(combined)
            return "expense", category, EXPENSE_CATEGORIES.get("uz", {}).get(category, "📦 Boshqa")
    
    # ==================== 9. DEFAULT ====================
    print(f"    [DETECT] ⚠️ Aniq kategoriya topilmadi, default: expense/boshqa")
    return "expense", "boshqa", EXPENSE_CATEGORIES.get("uz", {}).get("boshqa", "📦 Boshqa")


async def parse_multiple_transactions(text: str, lang: str = "uz", user_context: Dict = None) -> List[Dict]:
    """
    ASOSIY MULTI-TRANSACTION PARSING FUNKSIYASI v4.0
    
    Bir matndan BARCHA tranzaksiyalarni (daromad va xarajat) aniqlaydi.
    GEMINI AI integratsiyasi bilan kuchaytirilgan!
    Aniqlashtirish kerak bo'lgan tranzaksiyalarni belgilaydi!
    
    Misol: "bugun 3 million oylik tushdi, 1 million qarzimga berdim, 
           500 ming arendaga berdim, 300 mingga go'sht oldim, 100 mingga tovuq oldim"
    
    Natija:
    [
        {"type": "income", "category": "ish_haqi", "amount": 3000000, "description": "Oylik maosh"},
        {"type": "expense", "category": "qarz_berdim", "amount": 1000000, "description": "Qarzga berdim", 
         "needs_clarification": True, "clarification_type": "debt_recipient"},
        {"type": "expense", "category": "uy_joy", "amount": 500000, "description": "Ijara to'lovi", 
         "is_rent_payment": True},
        {"type": "expense", "category": "oziq_ovqat", "amount": 300000, "description": "Go'sht"},
        {"type": "expense", "category": "oziq_ovqat", "amount": 100000, "description": "Tovuq go'shti", 
         "needs_clarification": True, "clarification_type": "chicken_type"}
    ]
    """
    logger.info(f"[MULTI-PARSE v4.0] Matn: '{text}'")
    print(f"\n{'='*60}")
    print(f"[MULTI-PARSE v4.0] Matn: '{text}'")
    print(f"{'='*60}")
    
    # ========== GEMINI AI BILAN MULTI-TRANSACTION TAHLIL ==========
    logger.info(f"[MULTI-PARSE] GEMINI_ENABLED={GEMINI_ENABLED}, is_available={is_gemini_available()}")
    
    if GEMINI_ENABLED and is_gemini_available():
        try:
            from app.gemini_ai import analyze_multiple_transactions
            logger.info(f"[MULTI-PARSE] Gemini analyze_multiple_transactions chaqirilmoqda...")
            gemini_results = await analyze_multiple_transactions(text, lang, user_context)
            logger.info(f"[MULTI-PARSE] Gemini natijasi: {gemini_results}")
            
            if gemini_results and len(gemini_results) > 0:
                transactions = []
                for item in gemini_results:
                    tx_type = item.get("type", "expense")
                    category = item.get("category", "boshqa")
                    amount = item.get("amount", 0)
                    description = item.get("description", "")
                    
                    # Kategoriya nomini olish
                    if tx_type == "income":
                        category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(category, "📦 Boshqa")
                    else:
                        category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(category, "📦 Boshqa")
                    
                    tx = {
                        "type": tx_type,
                        "category": category,
                        "category_name": category_name,
                        "amount": amount,
                        "description": description,
                        "original_text": text[:100],
                        "timestamp": datetime.now().isoformat(),
                        "created_at": item.get("created_at", datetime.now().isoformat()),
                        "ai_source": "gemini"
                    }
                    
                    # Maxsus flaglarni qo'shish
                    if item.get("needs_clarification"):
                        tx["needs_clarification"] = True
                        tx["clarification_type"] = item.get("clarification_type", "unknown")
                    
                    if item.get("is_rent_payment"):
                        tx["is_rent_payment"] = True
                    
                    if item.get("is_debt_payment"):
                        tx["is_debt_payment"] = True
                    
                    transactions.append(tx)
                
                print(f"[MULTI-PARSE] Gemini: {len(transactions)} ta tranzaksiya topildi")
                
                # Aniqlashtirish kerakli tranzaksiyalarni chiqarish
                needs_clarification = [t for t in transactions if t.get("needs_clarification")]
                if needs_clarification:
                    print(f"[MULTI-PARSE] Aniqlashtirish kerak: {len(needs_clarification)} ta")
                
                return transactions
        except Exception as e:
            logger.warning(f"[MULTI-PARSE] Gemini xatosi, oddiy algoritmga o'tilmoqda: {e}")
            import traceback
            traceback.print_exc()
    
    # ========== ODDIY ALGORITM (FALLBACK) ==========
    # 1. Barcha summalarni va kontekstlarini topish
    amount_items = find_all_amounts_with_context(text)
    
    if not amount_items:
        print("[MULTI-PARSE] Hech qanday summa topilmadi")
        return []
    
    # 2. Har bir summa uchun tranzaksiya yaratish
    transactions = []
    text_lower = text.lower()
    
    for i, item in enumerate(amount_items):
        print(f"\n[MULTI-PARSE] #{i+1}: {item['text']} = {item['amount']:,}")
        
        # Kontekstni kengaytirish - oldingi va keyingi so'zlar
        # Agar bu birinchi summa bo'lmasa, oldingi summadan keyingi matni olish
        if i == 0:
            context_before = text_lower[:item['start']].strip()
        else:
            prev_end = amount_items[i-1]['end']
            context_before = text_lower[prev_end:item['start']].strip()
        
        # Agar bu oxirgi summa bo'lmasa, keyingi summadan oldingi matni olish
        if i == len(amount_items) - 1:
            context_after = text_lower[item['end']:].strip()
        else:
            next_start = amount_items[i+1]['start']
            context_after = text_lower[item['end']:next_start].strip()
        
        print(f"  Context before: '{context_before}'")
        print(f"  Context after: '{context_after}'")
        
        # Tur va kategoriyani aniqlash
        tx_type, category, category_name = determine_transaction_type_and_category(
            context_before, context_after, text_lower
        )
        
        # Tavsif yaratish
        description_parts = []
        if context_after:
            # Keraksiz so'zlarni olib tashlash
            clean_after = context_after
            for remove in ['va', 'ham', 'yana', 'keyin', 'so\'ng']:
                clean_after = re.sub(rf'\b{remove}\b', '', clean_after)
            clean_after = ' '.join(clean_after.split())
            if clean_after:
                description_parts.append(clean_after[:50])
        
        description = ' '.join(description_parts) if description_parts else item['text']
        
        # Kategoriya nomini til bo'yicha olish
        if tx_type == "income":
            category_name = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES["uz"]).get(category, "📦 Boshqa")
        else:
            category_name = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES["uz"]).get(category, "📦 Boshqa")
        
        transaction = {
            "type": tx_type,
            "category": category,
            "category_name": category_name,
            "amount": item['amount'],
            "description": description,
            "original_text": f"{item['text']} {context_after}".strip()[:100],
            "timestamp": datetime.now().isoformat()
        }
        
        transactions.append(transaction)
        print(f"  ✅ {tx_type.upper()}: {category_name} - {item['amount']:,} so'm")
    
    print(f"\n[MULTI-PARSE] Jami {len(transactions)} ta tranzaksiya topildi")
    print(f"{'='*60}\n")
    
    return transactions


async def save_multiple_transactions(db, user_id: int, transactions: List[Dict]) -> List[int]:
    """
    Bir nechta tranzaksiyalarni bazaga saqlash
    """
    transaction_ids = []
    
    for transaction in transactions:
        tx_id = await save_transaction(db, user_id, transaction)
        transaction_ids.append(tx_id)
    
    return transaction_ids


def format_multiple_transactions_message(transactions: List[Dict], budget_status: Dict, lang: str = "uz") -> str:
    """
    Bir nechta tranzaksiyalar uchun xabar formatlash - YAXSHILANGAN v2.0
    Aniqlashtirish kerak bo'lgan tranzaksiyalarni ko'rsatadi
    """
    # Aniqlashtirish turlari uchun matnlar
    clarification_texts = {
        "uz": {
            "chicken_type": "🐔 Bu tovuq go'shtimi yoki jonli hayvonmi?",
            "debt_recipient": "💰 Qarzni kimga berdingiz?",
            "payment_reason": "💳 Bu to'lov nima uchun?",
            "unknown": "❓ Qo'shimcha ma'lumot kerak"
        },
        "ru": {
            "chicken_type": "🐔 Это куриное мясо или живая птица?",
            "debt_recipient": "💰 Кому вы дали в долг?",
            "payment_reason": "💳 За что этот платёж?",
            "unknown": "❓ Нужна дополнительная информация"
        }
    }
    
    if lang == "uz":
        msg = "✅ *AI yordamchi - Tranzaksiyalar saqlandi*\n\n"
        
        total_expense = 0
        total_income = 0
        needs_clarification_list = []
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                type_emoji = "📥"
                type_label = "Daromad"
            else:
                type_emoji = "📤"
                type_label = "Xarajat"
            
            msg += f"{i}. {type_emoji} *{tx['category_name']}*\n"
            msg += f"   💵 {tx['amount']:,} so'm ({type_label})\n"
            if tx.get('description') and tx['description'] != "Noma'lum" and len(tx['description']) > 2:
                msg += f"   📝 _{tx['description'][:40]}_\n"
            
            # Maxsus flaglarni ko'rsatish
            if tx.get("is_rent_payment"):
                msg += f"   🏠 _Ijara to'lovi sifatida belgilandi_\n"
            if tx.get("is_debt_payment"):
                msg += f"   💰 _Qarz to'lovi sifatida belgilandi_\n"
            
            # Aniqlashtirish kerakmi
            if tx.get("needs_clarification"):
                clarification_type = tx.get("clarification_type", "unknown")
                clarification_text = clarification_texts["uz"].get(clarification_type, clarification_texts["uz"]["unknown"])
                msg += f"   ⚠️ _{clarification_text}_\n"
                needs_clarification_list.append((i, tx, clarification_type))
            
            msg += "\n"
            
            if tx["type"] == "expense":
                total_expense += tx["amount"]
            else:
                total_income += tx["amount"]
        
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        if total_income > 0:
            msg += f"📥 Jami daromad: *{total_income:,}* so'm\n"
        if total_expense > 0:
            msg += f"📤 Jami xarajat: *{total_expense:,}* so'm\n"
        
        # Saldo
        balance = total_income - total_expense
        if total_income > 0 and total_expense > 0:
            balance_emoji = "📈" if balance >= 0 else "📉"
            msg += f"{balance_emoji} Saldo: *{balance:+,}* so'm\n"
        
        # Budget status
        if budget_status and total_expense > 0:
            daily_budget = int(budget_status.get("daily_budget", 0))
            spent_today = int(budget_status.get("spent_today", 0) + total_expense)
            remaining = int(daily_budget - spent_today)
            
            if daily_budget > 0:
                msg += f"\n📊 *Bugungi byudjet:*\n"
                msg += f"├ Kunlik limit: {daily_budget:,} so'm\n"
                msg += f"├ Sarflangan: {spent_today:,} so'm\n"
                msg += f"└ Qoldi: {remaining:,} so'm"
                
                if remaining < 0:
                    msg += " ⚠️"
        
        # Aniqlashtirish kerak bo'lgan tranzaksiyalar haqida xabar
        if needs_clarification_list:
            msg += f"\n\n⚠️ *Aniqlashtirish kerak:* {len(needs_clarification_list)} ta\n"
            msg += "_Tugmalardan foydalanib to'g'rilashingiz mumkin_"
    
    else:
        msg = "✅ *AI помощник - Транзакции сохранены*\n\n"
        
        total_expense = 0
        total_income = 0
        needs_clarification_list = []
        
        for i, tx in enumerate(transactions, 1):
            if tx["type"] == "income":
                type_emoji = "📥"
                type_label = "Доход"
            else:
                type_emoji = "📤"
                type_label = "Расход"
            
            msg += f"{i}. {type_emoji} *{tx['category_name']}*\n"
            msg += f"   💵 {tx['amount']:,} сум ({type_label})\n"
            if tx.get('description') and tx['description'] != "Noma'lum" and len(tx['description']) > 2:
                msg += f"   📝 _{tx['description'][:40]}_\n"
            
            # Maxsus flaglarni ko'rsatish
            if tx.get("is_rent_payment"):
                msg += f"   🏠 _Отмечено как оплата аренды_\n"
            if tx.get("is_debt_payment"):
                msg += f"   💰 _Отмечено как оплата долга_\n"
            
            # Aniqlashtirish kerakmi
            if tx.get("needs_clarification"):
                clarification_type = tx.get("clarification_type", "unknown")
                clarification_text = clarification_texts["ru"].get(clarification_type, clarification_texts["ru"]["unknown"])
                msg += f"   ⚠️ _{clarification_text}_\n"
                needs_clarification_list.append((i, tx, clarification_type))
            
            msg += "\n"
            
            if tx["type"] == "expense":
                total_expense += tx["amount"]
            else:
                total_income += tx["amount"]
        
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        if total_income > 0:
            msg += f"📥 Всего доходов: *{total_income:,}* сум\n"
        if total_expense > 0:
            msg += f"📤 Всего расходов: *{total_expense:,}* сум\n"
        
        # Saldo
        balance = total_income - total_expense
        if total_income > 0 and total_expense > 0:
            balance_emoji = "📈" if balance >= 0 else "📉"
            msg += f"{balance_emoji} Баланс: *{balance:+,}* сум\n"
        
        # Aniqlashtirish kerak bo'lgan tranzaksiyalar haqida xabar
        if needs_clarification_list:
            msg += f"\n\n⚠️ *Требуется уточнение:* {len(needs_clarification_list)}\n"
            msg += "_Используйте кнопки для исправления_"
    
    return msg


# Legacy function for backwards compatibility
def split_into_transaction_segments(text: str) -> List[str]:
    """Legacy function - use parse_multiple_transactions instead"""
    return [text]


def extract_amount_from_segment(segment: str) -> Optional[int]:
    """Legacy function - use find_all_amounts_with_context instead"""
    items = find_all_amounts_with_context(segment)
    return items[0]['amount'] if items else None


def detect_category_from_segment(segment: str) -> Tuple[str, str]:
    """Legacy function - use determine_transaction_type_and_category instead"""
    tx_type, category, _ = determine_transaction_type_and_category("", segment, segment)
    return category, tx_type


# Database functions for transactions
async def save_transaction(db, user_id: int, transaction: Dict) -> int:
    """
    Tranzaksiyani bazaga saqlash
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO transactions (user_id, type, category, amount, description, original_text, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                RETURNING id
            """, 
                user_id,
                transaction["type"],
                transaction["category"],
                transaction["amount"],
                transaction["description"],
                transaction["original_text"]
            )
    else:
        await db._connection.execute("""
            INSERT INTO transactions (user_id, type, category, amount, description, original_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            transaction["type"],
            transaction["category"],
            transaction["amount"],
            transaction["description"],
            transaction["original_text"]
        ))
        await db._connection.commit()
        
        cursor = await db._connection.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_user_transactions(db, user_id: int, days: int = 30, transaction_type: str = None) -> List[Dict]:
    """
    Foydalanuvchi tranzaksiyalarini olish
    """
    if db.is_postgres:
        query = """
            SELECT id, type, category, amount, description, created_at
            FROM transactions
            WHERE user_id = $1
            AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
        """ % days
        params = [user_id]
        
        if transaction_type:
            query += " AND type = $2"
            params.append(transaction_type)
        
        query += " ORDER BY created_at DESC"
        
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    else:
        query = """
            SELECT id, type, category, amount, description, created_at
            FROM transactions
            WHERE user_id = ?
            AND created_at >= datetime('now', ?)
        """
        params = [user_id, f'-{days} days']
        
        if transaction_type:
            query += " AND type = ?"
            params.append(transaction_type)
        
        query += " ORDER BY created_at DESC"
        
        cursor = await db._connection.execute(query, params)
        rows = await cursor.fetchall()
    
    return [
        {
            "id": row[0] if isinstance(row, (list, tuple)) else row["id"],
            "type": row[1] if isinstance(row, (list, tuple)) else row["type"],
            "category": row[2] if isinstance(row, (list, tuple)) else row["category"],
            "amount": row[3] if isinstance(row, (list, tuple)) else row["amount"],
            "description": row[4] if isinstance(row, (list, tuple)) else row["description"],
            "created_at": row[5] if isinstance(row, (list, tuple)) else row["created_at"]
        }
        for row in rows
    ]


async def get_transaction_summary(db, user_id: int, days: int = 30) -> Dict:
    """
    Tranzaksiyalar xulosasini olish
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            # Daromadlar
            income_rows = await conn.fetch("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE user_id = $1 AND type = 'income'
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                GROUP BY category
            """ % days, user_id)
            
            # Xarajatlar
            expense_rows = await conn.fetch("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE user_id = $1 AND type = 'expense'
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                GROUP BY category
            """ % days, user_id)
            
            income_by_category = {row["category"]: row["total"] for row in income_rows}
            expense_by_category = {row["category"]: row["total"] for row in expense_rows}
    else:
        # Daromadlar
        cursor = await db._connection.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = ? AND type = 'income'
            AND created_at >= datetime('now', ?)
            GROUP BY category
        """, (user_id, f'-{days} days'))
        income_rows = await cursor.fetchall()
        
        # Xarajatlar
        cursor = await db._connection.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = ? AND type = 'expense'
            AND created_at >= datetime('now', ?)
            GROUP BY category
        """, (user_id, f'-{days} days'))
        expense_rows = await cursor.fetchall()
        
        income_by_category = {row[0]: row[1] for row in income_rows}
        expense_by_category = {row[0]: row[1] for row in expense_rows}
    
    total_income = sum(income_by_category.values())
    total_expense = sum(expense_by_category.values())
    
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category
    }


def format_transaction_summary(summary: Dict, lang: str = "uz") -> str:
    """
    Tranzaksiya xulosasini formatlash
    """
    if lang == "uz":
        msg = (
            "📊 *MOLIYAVIY HISOBOT*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Umumiy daromad:* {summary['total_income']:,} so'm\n"
            f"💸 *Umumiy xarajat:* {summary['total_expense']:,} so'm\n"
            f"📈 *Balans:* {summary['balance']:,} so'm\n\n"
        )
        
        if summary['income_by_category']:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💰 *DAROMADLAR:*\n"
            for cat, amount in summary['income_by_category'].items():
                cat_name = INCOME_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                msg += f"├ {cat_name}: *{amount:,}* so'm\n"
            msg += "\n"
        
        if summary['expense_by_category']:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💸 *XARAJATLAR:*\n"
            for cat, amount in summary['expense_by_category'].items():
                cat_name = EXPENSE_CATEGORIES["uz"].get(cat, "📦 Boshqa")
                msg += f"├ {cat_name}: *{amount:,}* so'm\n"
    else:
        msg = (
            "📊 *ФИНАНСОВЫЙ ОТЧЁТ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Общий доход:* {summary['total_income']:,} сум\n"
            f"💸 *Общий расход:* {summary['total_expense']:,} сум\n"
            f"📈 *Баланс:* {summary['balance']:,} сум\n\n"
        )
        
        if summary['income_by_category']:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💰 *ДОХОДЫ:*\n"
            for cat, amount in summary['income_by_category'].items():
                cat_name = INCOME_CATEGORIES["ru"].get(cat, "📦 Прочее")
                msg += f"├ {cat_name}: *{amount:,}* сум\n"
            msg += "\n"
        
        if summary['expense_by_category']:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💸 *РАСХОДЫ:*\n"
            for cat, amount in summary['expense_by_category'].items():
                cat_name = EXPENSE_CATEGORIES["ru"].get(cat, "📦 Прочее")
                msg += f"├ {cat_name}: *{amount:,}* сум\n"
    
    return msg


# ==================== BUDGET CONTROL ====================

async def get_monthly_budget(db, user_id: int) -> Dict:
    """
    Foydalanuvchining oylik byudjetini hisoblash
    
    Byudjet formulasi:
    - Daromad (income_self + income_partner)
    - Majburiy xarajatlar (rent + kindergarten + utilities + loan_payment)
    - Bo'sh pul = Daromad - Majburiy
    - Yashash byudjeti = Bo'sh pulning 70%
    """
    # Get user profile
    profile = await db.get_financial_profile(user_id)
    
    if not profile:
        return {
            "total_income": 0,
            "mandatory_expenses": 0,
            "free_cash": 0,
            "living_budget": 0,
            "savings_budget": 0,
            "extra_debt_budget": 0,
            "has_data": False
        }
    
    # Daromadlar
    income_self = profile.get("income_self", 0) or 0
    income_partner = profile.get("income_partner", 0) or 0
    total_income = income_self + income_partner
    
    # Majburiy xarajatlar
    rent = profile.get("rent", 0) or 0
    kindergarten = profile.get("kindergarten", 0) or 0
    utilities = profile.get("utilities", 0) or 0
    loan_payment = profile.get("loan_payment", 0) or 0
    
    mandatory_expenses = rent + kindergarten + utilities + loan_payment
    
    # Bo'sh pul
    free_cash = total_income - mandatory_expenses
    
    # Aqlli taqsimlash (agar bo'sh pul bo'lsa)
    if free_cash > 0:
        savings_budget = free_cash * 0.10  # 10% boylik uchun
        extra_debt_budget = free_cash * 0.20  # 20% qo'shimcha qarz to'lovi
        living_budget = free_cash * 0.70  # 70% yashash uchun
    else:
        savings_budget = 0
        extra_debt_budget = 0
        living_budget = 0
    
    return {
        "total_income": total_income,
        "mandatory_expenses": mandatory_expenses,
        "free_cash": free_cash,
        "living_budget": living_budget,  # Bu oylik "Yashash" byudjeti
        "savings_budget": savings_budget,
        "extra_debt_budget": extra_debt_budget,
        "has_data": total_income > 0
    }


async def get_current_month_expenses(db, user_id: int) -> int:
    """
    Joriy oydagi jami xarajatlarni olish (AI orqali yozilgan)
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(amount), 0) as total
                FROM transactions
                WHERE user_id = $1 
                AND type = 'expense'
                AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
            """, user_id)
            return row['total'] if row else 0
    else:
        cursor = await db._connection.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE user_id = ? 
            AND type = 'expense'
            AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """, (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_budget_status(db, user_id: int) -> Dict:
    """
    KUCHLI BYUDJET NAZORATI
    =======================
    
    Byudjet holatini oy kunlari bilan solishtirib tahlil qiladi.
    
    Tahlil qoidalari:
    ----------------
    1. Xarajat foizi vs Oy foizi
       - Agar xarajat foizi > oy foizi → tez sarflayapti (xavfli)
       - Agar xarajat foizi ≈ oy foizi → normal
       - Agar xarajat foizi < oy foizi → yaxshi tejayapti
    
    2. Masalan:
       - Oyning 10-kuni (33%), byudjetning 50% sarflangan → XAVFLI
       - Oyning 15-kuni (50%), byudjetning 50% sarflangan → NORMAL
       - Oyning 20-kuni (67%), byudjetning 50% sarflangan → YAXSHI
    
    Returns:
        - budget: Yashash byudjeti
        - spent: Sarflangan summa
        - remaining: Qolgan summa
        - percentage_used: Foizda sarflangan
        - day_of_month: Bugungi kun
        - days_in_month: Oylik kunlar soni
        - day_percentage: Oy foizi (nechta kun o'tdi)
        - spending_rate: Sarflash tezligi (xarajat%/kun%)
        - status: 'excellent', 'good', 'normal', 'warning', 'danger', 'critical', 'over'
        - daily_budget: Kunlik byudjet
        - remaining_daily_budget: Qolgan kunlar uchun kunlik byudjet
    """
    from datetime import datetime
    import calendar
    
    budget_info = await get_monthly_budget(db, user_id)
    
    if not budget_info["has_data"]:
        return {
            "budget": 0,
            "spent": 0,
            "remaining": 0,
            "percentage_used": 0,
            "status": "no_data",
            "message": None
        }
    
    living_budget = budget_info["living_budget"]
    spent = await get_current_month_expenses(db, user_id)
    remaining = living_budget - spent
    
    # Oy haqida ma'lumot
    today = datetime.now()
    day_of_month = today.day
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - day_of_month + 1  # Bugunni ham hisobga olish
    
    # Foizlarni hisoblash
    if living_budget > 0:
        percentage_used = (spent / living_budget) * 100
    else:
        percentage_used = 0
    
    day_percentage = (day_of_month / days_in_month) * 100  # Oy qancha foiz o'tdi
    
    # Sarflash tezligi (spending rate)
    # 1.0 = normal, >1 = tez sarflayapti, <1 = sekin sarflayapti
    if day_percentage > 0:
        spending_rate = percentage_used / day_percentage
    else:
        spending_rate = 0
    
    # Kunlik byudjetlar
    daily_budget = living_budget / days_in_month if days_in_month > 0 else 0
    remaining_daily_budget = remaining / days_remaining if days_remaining > 0 else 0
    
    # Ideal sarflangan summa (shu kungacha qancha sarflash kerak edi)
    ideal_spent = daily_budget * day_of_month
    
    # Farq (ustidan yoki ostidan)
    spending_difference = spent - ideal_spent
    
    # ==================== STATUS ANIQLASH (KUCHLI ALGORITM) ====================
    
    if remaining < 0:
        status = "over"  # Byudjetdan oshib ketgan
        severity = 5
    elif spending_rate >= 2.0:
        status = "critical"  # Juda tez sarflayapti (2x tezlikda)
        severity = 4
    elif spending_rate >= 1.5:
        status = "danger"  # Tez sarflayapti (1.5x tezlikda)
        severity = 3
    elif spending_rate >= 1.2:
        status = "warning"  # Biroz tez sarflayapti
        severity = 2
    elif spending_rate >= 0.8:
        status = "normal"  # Normal tezlikda
        severity = 1
    elif spending_rate >= 0.5:
        status = "good"  # Yaxshi tejayapti
        severity = 0
    else:
        status = "excellent"  # A'lo darajada tejayapti
        severity = 0
    
    return {
        "budget": living_budget,
        "spent": spent,
        "remaining": remaining,
        "percentage_used": percentage_used,
        "day_of_month": day_of_month,
        "days_in_month": days_in_month,
        "days_remaining": days_remaining,
        "day_percentage": day_percentage,
        "spending_rate": spending_rate,
        "daily_budget": daily_budget,
        "remaining_daily_budget": remaining_daily_budget,
        "ideal_spent": ideal_spent,
        "spending_difference": spending_difference,
        "status": status,
        "severity": severity,
        "budget_info": budget_info
    }


def format_budget_warning(budget_status: Dict, lang: str = "uz") -> Optional[str]:
    """
    KUCHLI BYUDJET OGOHLANTIRISH XABARLARI
    ======================================
    
    Byudjet holati va sarflash tezligiga qarab ogohlantirish.
    """
    status = budget_status["status"]
    budget = budget_status["budget"]
    spent = budget_status["spent"]
    remaining = budget_status["remaining"]
    percentage = budget_status["percentage_used"]
    
    if status == "no_data":
        return None
    
    # Yangi ma'lumotlar
    day_of_month = budget_status.get("day_of_month", 1)
    days_in_month = budget_status.get("days_in_month", 30)
    days_remaining = budget_status.get("days_remaining", 30)
    day_percentage = budget_status.get("day_percentage", 0)
    spending_rate = budget_status.get("spending_rate", 1)
    daily_budget = budget_status.get("daily_budget", 0)
    remaining_daily_budget = budget_status.get("remaining_daily_budget", 0)
    spending_difference = budget_status.get("spending_difference", 0)
    
    if lang == "uz":
        if status == "over":
            return (
                "🚨 *XAVFLI! BYUDJETDAN OSHIB KETDINGIZ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm\n"
                f"❌ Oshib ketdi: *{abs(remaining):,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun / {days_in_month} kun\n"
                f"⏰ Qolgan kunlar: *{days_remaining}* kun\n\n"
                "🔴 *HOLAT: KRITIK*\n"
                "Siz bu oy uchun ajratilgan byudjetdan oshib ketdingiz!\n\n"
                "💡 *Maslahatlar:*\n"
                "• Faqat juda zarur xarajatlar qiling\n"
                "• Kredit kartadan foydalanmang\n"
                "• Keyingi oyda qat'iy tejash rejasini tuzing"
            )
        elif status == "critical":
            return (
                "🚨 *JUDA XAVFLI HOLAT!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (normaldan {spending_rate:.1f} marta tez!)\n\n"
                "🔴 *HOLAT: KRITIK*\n"
                f"Siz byudjetning *{percentage:.0f}%* ini sarfladingiz,\n"
                f"lekin oy faqat *{day_percentage:.0f}%* o'tdi!\n\n"
                f"⚠️ Shu tezlikda davom etsangiz, byudjet *{int(days_in_month/spending_rate)}*-kungacha tugaydi!\n\n"
                f"💡 Qolgan *{days_remaining}* kun uchun kuniga *{remaining_daily_budget:,.0f}* so'm sarflang"
            )
        elif status == "danger":
            return (
                "⚠️ *DIQQAT! TEZ SARFLAYAPSIZ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (normaldan tez)\n\n"
                "🟠 *HOLAT: XAVFLI*\n"
                f"Normalda shu kungacha *{budget*day_percentage/100:,.0f}* so'm sarflashingiz kerak edi,\n"
                f"lekin siz *{spending_difference:+,.0f}* so'm ko'p sarfladingiz.\n\n"
                f"💡 Qolgan *{days_remaining}* kun uchun kuniga *{remaining_daily_budget:,.0f}* so'm sarflang"
            )
        elif status == "warning":
            return (
                "📊 *BYUDJET OGOHLANTIRISHI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (biroz tez)\n\n"
                "🟡 *HOLAT: EHTIYOT BO'LING*\n"
                f"Siz normaldan biroz tez sarflayapsiz.\n\n"
                f"💡 Qolgan *{days_remaining}* kun uchun kuniga *{remaining_daily_budget:,.0f}* so'm sarflang"
            )
        elif status == "normal":
            return (
                "✅ *BYUDJET HOLATI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (normal)\n\n"
                "🟢 *HOLAT: NORMAL*\n"
                f"Siz to'g'ri tezlikda sarflayapsiz.\n\n"
                f"💡 Kunlik byudjet: *{daily_budget:,.0f}* so'm"
            )
        elif status == "good":
            return (
                "✅ *AJOYIB! YAXSHI TEJAYAPSIZ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (sekin - yaxshi!)\n\n"
                "💚 *HOLAT: YAXSHI*\n"
                f"Siz tejamkorlik qilayapsiz! Davom eting!\n\n"
                f"🎯 Tejagan summangiz: *{abs(spending_difference):,.0f}* so'm"
            )
        else:  # excellent
            return (
                "🌟 *MUKAMMAL! A'LO TEJAMKORLIK*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Oylik byudjet: *{budget:,.0f}* so'm\n"
                f"💸 Sarfladingiz: *{spent:,.0f}* so'm ({percentage:.0f}%)\n"
                f"💰 Qoldi: *{remaining:,.0f}* so'm\n\n"
                f"📅 Bugun: {day_of_month}-kun ({day_percentage:.0f}% oy o'tdi)\n"
                f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (juda sekin - a'lo!)\n\n"
                "🏆 *HOLAT: A'LO*\n"
                f"Siz a'lo darajada tejayapsiz!\n\n"
                f"🎯 Tejagan summangiz: *{abs(spending_difference):,.0f}* so'm\n"
                "💡 Bu pulni jamg'armaga qo'shing!"
            )
    else:  # Russian
        if status == "over":
            return (
                "🚨 *ОПАСНО! БЮДЖЕТ ПРЕВЫШЕН!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум\n"
                f"❌ Превышение: *{abs(remaining):,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день / {days_in_month} дней\n"
                f"⏰ Осталось дней: *{days_remaining}*\n\n"
                "🔴 *СТАТУС: КРИТИЧЕСКИЙ*\n"
                "Вы превысили бюджет на этот месяц!\n\n"
                "💡 *Советы:*\n"
                "• Только крайне необходимые расходы\n"
                "• Не используйте кредитные карты\n"
                "• Составьте строгий план экономии"
            )
        elif status == "critical":
            return (
                "🚨 *КРИТИЧЕСКАЯ СИТУАЦИЯ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца прошло)\n"
                f"📊 Скорость расходов: *{spending_rate:.1f}x* (в {spending_rate:.1f} раз быстрее нормы!)\n\n"
                "🔴 *СТАТУС: КРИТИЧЕСКИЙ*\n"
                f"Вы потратили *{percentage:.0f}%* бюджета,\n"
                f"а прошло только *{day_percentage:.0f}%* месяца!\n\n"
                f"💡 На оставшиеся *{days_remaining}* дней тратьте по *{remaining_daily_budget:,.0f}* сум в день"
            )
        elif status == "danger":
            return (
                "⚠️ *ВНИМАНИЕ! БЫСТРО ТРАТИТЕ!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца)\n"
                f"📊 Скорость расходов: *{spending_rate:.1f}x* (быстрее нормы)\n\n"
                "🟠 *СТАТУС: ОПАСНЫЙ*\n"
                f"💡 На оставшиеся *{days_remaining}* дней тратьте по *{remaining_daily_budget:,.0f}* сум в день"
            )
        elif status == "warning":
            return (
                "📊 *ПРЕДУПРЕЖДЕНИЕ О БЮДЖЕТЕ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца)\n"
                f"📊 Скорость: *{spending_rate:.1f}x* (немного быстрее)\n\n"
                "🟡 *СТАТУС: ОСТОРОЖНО*\n"
                f"💡 Дневной бюджет: *{remaining_daily_budget:,.0f}* сум"
            )
        elif status == "normal":
            return (
                "✅ *СОСТОЯНИЕ БЮДЖЕТА*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца)\n"
                f"📊 Скорость: *{spending_rate:.1f}x* (норма)\n\n"
                "🟢 *СТАТУС: НОРМАЛЬНО*\n"
                f"💡 Дневной бюджет: *{daily_budget:,.0f}* сум"
            )
        elif status == "good":
            return (
                "✅ *ОТЛИЧНО! ХОРОШО ЭКОНОМИТЕ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца)\n"
                f"📊 Скорость: *{spending_rate:.1f}x* (медленнее - хорошо!)\n\n"
                "💚 *СТАТУС: ХОРОШО*\n"
                f"🎯 Сэкономлено: *{abs(spending_difference):,.0f}* сум"
            )
        else:  # excellent
            return (
                "🌟 *ПРЕВОСХОДНО! ОТЛИЧНАЯ ЭКОНОМИЯ*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏠 Месячный бюджет: *{budget:,.0f}* сум\n"
                f"💸 Потрачено: *{spent:,.0f}* сум ({percentage:.0f}%)\n"
                f"💰 Осталось: *{remaining:,.0f}* сум\n\n"
                f"📅 Сегодня: {day_of_month}-й день ({day_percentage:.0f}% месяца)\n"
                f"📊 Скорость: *{spending_rate:.1f}x* (очень медленно - отлично!)\n\n"
                "🏆 *СТАТУС: ОТЛИЧНО*\n"
                f"🎯 Сэкономлено: *{abs(spending_difference):,.0f}* сум\n"
                "💡 Добавьте эти деньги в накопления!"
            )


def format_expense_saved_with_budget(transaction: Dict, budget_status: Dict, lang: str = "uz") -> str:
    """
    Xarajat saqlangandan keyin byudjet bilan birga xabar formatlash
    KUCHLI NAZORAT BILAN
    """
    type_emoji = "💰" if transaction["type"] == "income" else "💸"
    status = budget_status["status"]
    remaining = budget_status.get("remaining", 0)
    percentage = budget_status.get("percentage_used", 0)
    
    # Yangi ma'lumotlar
    day_of_month = budget_status.get("day_of_month", 1)
    days_remaining = budget_status.get("days_remaining", 30)
    spending_rate = budget_status.get("spending_rate", 1)
    remaining_daily_budget = budget_status.get("remaining_daily_budget", 0)
    
    # Progress bar yasash
    filled = min(int(percentage / 10), 10)
    empty = 10 - filled
    
    if status == "over":
        progress_bar = "🔴" * 10
    elif status == "critical":
        progress_bar = "🟢" * min(filled, 5) + "🟡" * min(max(filled - 5, 0), 3) + "🔴" * max(filled - 8, 0) + "⚪" * empty
    elif status == "danger":
        progress_bar = "🟢" * min(filled, 6) + "🟡" * min(max(filled - 6, 0), 2) + "🟠" * max(filled - 8, 0) + "⚪" * empty
    elif status == "warning":
        progress_bar = "🟢" * min(filled, 7) + "🟡" * max(filled - 7, 0) + "⚪" * empty
    else:
        progress_bar = "🟢" * filled + "⚪" * empty
    
    if lang == "uz":
        if transaction["type"] == "expense":
            msg = (
                f"✅ *XARAJAT SAQLANDI*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💸 *Kategoriya:* {transaction['category_name']}\n"
                f"💵 *Summa:* {transaction['amount']:,} so'm\n"
                f"📋 *Tavsif:* {transaction['description']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *OYLIK BYUDJET:*\n"
                f"{progress_bar} {percentage:.0f}%\n\n"
            )
            
            if status == "over":
                msg += f"🚨 *XAVF! Byudjetdan oshib ketdingiz!*\n❌ Oshib ketgan: *{abs(remaining):,}* so'm"
            elif status == "critical":
                msg += (
                    f"🚨 *KRITIK HOLAT!*\n"
                    f"📊 Sarflash tezligi: *{spending_rate:.1f}x* (juda tez!)\n"
                    f"💰 Qoldi: *{remaining:,}* so'm\n"
                    f"💡 Kuniga *{remaining_daily_budget:,.0f}* so'm sarflang"
                )
            elif status == "danger":
                msg += (
                    f"⚠️ *Tez sarflayapsiz!*\n"
                    f"📊 Tezlik: *{spending_rate:.1f}x*\n"
                    f"💰 Qoldi: *{remaining:,}* so'm\n"
                    f"💡 Kuniga *{remaining_daily_budget:,.0f}* so'm"
                )
            elif status == "warning":
                msg += (
                    f"🟡 *Ehtiyot bo'ling!*\n"
                    f"📊 Tezlik: *{spending_rate:.1f}x*\n"
                    f"💰 Qoldi: *{remaining:,}* so'm"
                )
            elif status == "normal":
                msg += f"🟢 *Normal tezlikda*\n💰 Qoldi: *{remaining:,}* so'm"
            elif status == "good":
                msg += f"💚 *Yaxshi tejayapsiz!*\n💰 Qoldi: *{remaining:,}* so'm"
            else:  # excellent
                msg += f"🌟 *A'lo tejamkorlik!*\n💰 Qoldi: *{remaining:,}* so'm"
        else:
            msg = (
                f"✅ *DAROMAD SAQLANDI*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 *Kategoriya:* {transaction['category_name']}\n"
                f"💵 *Summa:* {transaction['amount']:,} so'm\n"
                f"📋 *Tavsif:* {transaction['description']}"
            )
    else:
        if transaction["type"] == "expense":
            msg = (
                f"✅ *РАСХОД СОХРАНЁН*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💸 *Категория:* {transaction['category_name']}\n"
                f"💵 *Сумма:* {transaction['amount']:,} сум\n"
                f"📋 *Описание:* {transaction['description']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *МЕСЯЧНЫЙ БЮДЖЕТ:*\n"
                f"{progress_bar} {percentage:.0f}%\n\n"
            )
            
            if status == "over":
                msg += f"🚨 *ОПАСНО! Бюджет превышен!*\n❌ Превышение: *{abs(remaining):,}* сум"
            elif status == "critical":
                msg += (
                    f"🚨 *КРИТИЧЕСКАЯ СИТУАЦИЯ!*\n"
                    f"📊 Скорость: *{spending_rate:.1f}x* (очень быстро!)\n"
                    f"💰 Осталось: *{remaining:,}* сум\n"
                    f"💡 Тратьте *{remaining_daily_budget:,.0f}* сум в день"
                )
            elif status == "danger":
                msg += (
                    f"⚠️ *Быстро тратите!*\n"
                    f"📊 Скорость: *{spending_rate:.1f}x*\n"
                    f"💰 Осталось: *{remaining:,}* сум\n"
                    f"💡 По *{remaining_daily_budget:,.0f}* сум в день"
                )
            elif status == "warning":
                msg += (
                    f"🟡 *Будьте осторожны!*\n"
                    f"📊 Скорость: *{spending_rate:.1f}x*\n"
                    f"💰 Осталось: *{remaining:,}* сум"
                )
            elif status == "normal":
                msg += f"🟢 *Нормальная скорость*\n💰 Осталось: *{remaining:,}* сум"
            elif status == "good":
                msg += f"💚 *Хорошо экономите!*\n💰 Осталось: *{remaining:,}* сум"
            else:  # excellent
                msg += f"🌟 *Отличная экономия!*\n💰 Осталось: *{remaining:,}* сум"
        else:
            msg = (
                f"✅ *ДОХОД СОХРАНЁН*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 *Категория:* {transaction['category_name']}\n"
                f"💵 *Сумма:* {transaction['amount']:,} сум\n"
                f"📋 *Описание:* {transaction['description']}"
            )
    
    return msg

# ==================== VOICE USAGE LIMITS ====================

async def get_voice_usage(db, user_id: int) -> Dict:
    """
    Joriy oydagi ovozli xabar foydalanishini olish
    """
    current_month = datetime.now().strftime("%Y-%m")
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT voice_count, total_duration
                FROM voice_usage
                WHERE user_id = $1 AND month = $2
            """, user_id, current_month)
            
            if row:
                return {
                    "voice_count": row["voice_count"],
                    "total_duration": row["total_duration"],
                    "remaining": max(0, MONTHLY_VOICE_LIMIT - row["voice_count"])
                }
    else:
        cursor = await db._connection.execute("""
            SELECT voice_count, total_duration
            FROM voice_usage
            WHERE user_id = ? AND month = ?
        """, (user_id, current_month))
        row = await cursor.fetchone()
        
        if row:
            return {
                "voice_count": row[0],
                "total_duration": row[1],
                "remaining": max(0, MONTHLY_VOICE_LIMIT - row[0])
            }
    
    return {
        "voice_count": 0,
        "total_duration": 0,
        "remaining": MONTHLY_VOICE_LIMIT
    }


async def increment_voice_usage(db, user_id: int, duration: int = 0) -> bool:
    """
    Ovozli xabar foydalanishini oshirish
    """
    current_month = datetime.now().strftime("%Y-%m")
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO voice_usage (user_id, month, voice_count, total_duration)
                VALUES ($1, $2, 1, $3)
                ON CONFLICT(user_id, month) DO UPDATE SET
                    voice_count = voice_usage.voice_count + 1,
                    total_duration = voice_usage.total_duration + $4
            """, user_id, current_month, duration, duration)
    else:
        await db._connection.execute("""
            INSERT INTO voice_usage (user_id, month, voice_count, total_duration)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, month) DO UPDATE SET
                voice_count = voice_count + 1,
                total_duration = total_duration + ?
        """, (user_id, current_month, duration, duration))
        await db._connection.commit()
    
    return True


def get_voice_tier_limits(voice_tier: str = "basic") -> Dict:
    """Get limits for voice tier"""
    tier_config = VOICE_TIERS.get(voice_tier, VOICE_TIERS["basic"])
    return {
        "monthly_limit": tier_config["monthly_limit"],
        "max_duration": tier_config["max_duration"],
        "tier": voice_tier,
        "name_uz": tier_config["name_uz"],
        "name_ru": tier_config["name_ru"]
    }


async def check_voice_limit(db, user_id: int, voice_tier: str = "basic", bonus_voice: int = 0) -> Dict:
    """
    Ovozli xabar limitini tekshirish (YANGI TIZIM)
    
    Voice Tiers:
    - basic: 30 ta/oy, 30 soniya max
    - plus: 60 ta/oy, 60 soniya max  
    - unlimited: cheksiz, 60 soniya max
    
    Returns: {"allowed": bool, "remaining": int, "used": int, "limit": int, "max_duration": int, "tier": str}
    """
    tier_limits = get_voice_tier_limits(voice_tier)
    usage = await get_voice_usage(db, user_id)
    
    # Unlimited tier
    if tier_limits["monthly_limit"] == -1:
        return {
            "allowed": True,
            "remaining": -1,  # -1 = cheksiz
            "used": usage["voice_count"],
            "limit": -1,
            "max_duration": tier_limits["max_duration"],
            "tier": voice_tier,
            "tier_name_uz": tier_limits["name_uz"],
            "tier_name_ru": tier_limits["name_ru"]
        }
    
    # Basic or Plus tier with limit
    total_limit = tier_limits["monthly_limit"] + bonus_voice
    remaining = max(0, total_limit - usage["voice_count"])
    
    if usage["voice_count"] >= total_limit:
        return {
            "allowed": False,
            "remaining": 0,
            "used": usage["voice_count"],
            "limit": total_limit,
            "max_duration": tier_limits["max_duration"],
            "tier": voice_tier,
            "tier_name_uz": tier_limits["name_uz"],
            "tier_name_ru": tier_limits["name_ru"],
            "bonus": bonus_voice
        }
    else:
        return {
            "allowed": True,
            "remaining": remaining,
            "used": usage["voice_count"],
            "limit": total_limit,
            "max_duration": tier_limits["max_duration"],
            "tier": voice_tier,
            "tier_name_uz": tier_limits["name_uz"],
            "tier_name_ru": tier_limits["name_ru"],
            "bonus": bonus_voice
        }


def format_voice_limit_message(limit_info: Dict, lang: str = "uz") -> str:
    """
    Ovozli xabar limiti haqida xabar - limit tugaganda
    Yangi tariflar: Voice+ va Voice Unlimited
    """
    from app.languages import format_number
    
    tier = limit_info.get("tier", "basic")
    max_dur = limit_info.get("max_duration", 30)
    
    if lang == "uz":
        if not limit_info["allowed"]:
            return (
                "🔒 *OVOZLI XABAR LIMITI TUGADI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 Ishlatilgan: *{limit_info['used']}/{limit_info['limit']}*\n"
                f"⏱ Hozirgi tarif: *{limit_info.get('tier_name_uz', 'Asosiy')}* ({max_dur} sek)\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *YANGILASH UCHUN:*\n\n"
                "🎤 *Voice+* — 60 ta/oy, 60 sek\n"
                f"   └ Narxi: `{format_number(VOICE_PLUS_PRICE)} so'm/oy`\n\n"
                "♾️ *Voice Unlimited* — cheksiz, 60 sek\n"
                f"   └ Narxi: `{format_number(VOICE_UNLIMITED_PRICE)} so'm/oy`\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ *Matnli kiritish BEPUL va cheksiz!*"
            )
        else:
            if limit_info.get("limit") == -1:
                return f"🎤 *{limit_info.get('tier_name_uz', 'Cheksiz')}*: ♾️ cheksiz (max {max_dur} sek)"
            return f"🎤 Qolgan: *{limit_info['remaining']}/{limit_info['limit']}* (max {max_dur} sek)"
    else:
        if not limit_info["allowed"]:
            return (
                "🔒 *ЛИМИТ ГОЛОСОВЫХ ИСЧЕРПАН*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 Использовано: *{limit_info['used']}/{limit_info['limit']}*\n"
                f"⏱ Текущий тариф: *{limit_info.get('tier_name_ru', 'Базовый')}* ({max_dur} сек)\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *ДЛЯ ОБНОВЛЕНИЯ:*\n\n"
                "🎤 *Voice+* — 60 шт/мес, 60 сек\n"
                f"   └ Цена: `{format_number(VOICE_PLUS_PRICE)} сум/мес`\n\n"
                "♾️ *Voice Unlimited* — безлимит, 60 сек\n"
                f"   └ Цена: `{format_number(VOICE_UNLIMITED_PRICE)} сум/мес`\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ *Текстовый ввод БЕСПЛАТНО и без лимита!*"
            )
        else:
            if limit_info.get("limit") == -1:
                return f"🎤 *{limit_info.get('tier_name_ru', 'Безлимит')}*: ♾️ безлимит (max {max_dur} сек)"
            return f"🎤 Осталось: *{limit_info['remaining']}/{limit_info['limit']}* (max {max_dur} сек)"


def format_voice_duration_error(duration: int, max_duration: int = 30, lang: str = "uz") -> str:
    """
    Ovozli xabar juda uzun bo'lganda xato xabari
    """
    if lang == "uz":
        return (
            "⚠️ *OVOZ JUDA UZUN*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Ovozli xabar uzunligi: *{duration}* sekund\n"
            f"Sizning limitingiz: *{max_duration}* sekund\n\n"
            "💡 *Uzunroq ovoz uchun:*\n"
            f"├ Voice+ — 60 sekund (`{format_number(VOICE_PLUS_PRICE)} so'm/oy`)\n"
            f"└ Voice Unlimited — 60 sekund (`{format_number(VOICE_UNLIMITED_PRICE)} so'm/oy`)\n\n"
            "✍️ Yoki matnli xabar yuboring (bepul!)"
        )
    else:
        return (
            "⚠️ *СЛИШКОМ ДЛИННОЕ СООБЩЕНИЕ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Длительность: *{duration}* секунд\n"
            f"Ваш лимит: *{max_duration}* секунд\n\n"
            "💡 *Для более длинных:*\n"
            f"├ Voice+ — 60 сек (`{format_number(VOICE_PLUS_PRICE)} сум/мес`)\n"
            f"└ Voice Unlimited — 60 сек (`{format_number(VOICE_UNLIMITED_PRICE)} сум/мес`)\n\n"
            "✍️ Или напишите текстом (бесплатно!)"
        )


# ==================== TRANSACTION MANAGEMENT ====================

async def get_transaction_by_id(db, transaction_id: int) -> Optional[Dict]:
    """
    Tranzaksiyani ID bo'yicha olish
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, user_id, type, category, amount, description, original_text, created_at
                FROM transactions WHERE id = $1
            """, transaction_id)
            
            if row:
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "type": row["type"],
                    "category": row["category"],
                    "amount": row["amount"],
                    "description": row["description"],
                    "original_text": row["original_text"],
                    "created_at": row["created_at"]
                }
    else:
        cursor = await db._connection.execute("""
            SELECT id, user_id, type, category, amount, description, original_text, created_at
            FROM transactions WHERE id = ?
        """, (transaction_id,))
        row = await cursor.fetchone()
        
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "type": row[2],
                "category": row[3],
                "amount": row[4],
                "description": row[5],
                "original_text": row[6],
                "created_at": row[7]
            }
    return None


async def delete_transaction(db, transaction_id: int, user_id: int) -> bool:
    """
    Tranzaksiyani o'chirish (faqat o'z tranzaksiyasini)
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM transactions WHERE id = $1 AND user_id = $2
            """, transaction_id, user_id)
    else:
        await db._connection.execute("""
            DELETE FROM transactions WHERE id = ? AND user_id = ?
        """, (transaction_id, user_id))
        await db._connection.commit()
    return True


async def update_transaction(db, transaction_id: int, user_id: int, **kwargs) -> bool:
    """
    Tranzaksiyani yangilash
    """
    if not kwargs:
        return False
    
    if db.is_postgres:
        fields = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(kwargs.keys()))
        values = list(kwargs.values()) + [transaction_id, user_id]
        param_count = len(kwargs)
        
        async with db._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE transactions SET {fields} WHERE id = ${param_count+1} AND user_id = ${param_count+2}",
                *values
            )
    else:
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [transaction_id, user_id]
        
        await db._connection.execute(
            f"UPDATE transactions SET {fields} WHERE id = ? AND user_id = ?",
            values
        )
        await db._connection.commit()
    return True


async def get_last_transaction(db, user_id: int) -> Optional[Dict]:
    """
    Foydalanuvchining oxirgi tranzaksiyasini olish
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, user_id, type, category, amount, description, original_text, created_at
                FROM transactions 
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, user_id)
            
            if row:
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "type": row["type"],
                    "category": row["category"],
                    "amount": row["amount"],
                    "description": row["description"],
                    "original_text": row["original_text"],
                    "created_at": row["created_at"]
                }
    else:
        cursor = await db._connection.execute("""
            SELECT id, user_id, type, category, amount, description, original_text, created_at
            FROM transactions 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        row = await cursor.fetchone()
        
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "type": row[2],
                "category": row[3],
                "amount": row[4],
                "description": row[5],
                "original_text": row[6],
                "created_at": row[7]
            }
    return None


# ==================== QARZ MUNOSABATLARI ====================

def detect_debt_transaction(text: str) -> Optional[Dict]:
    """
    Matndan qarz munosabatini aniqlash
    Qaytaradi: {"type": "lent"/"borrowed", "person": "...", "date": date, "due_date": date/None}
    """
    text_lower = text.lower()
    
    # Qarz berish indikatorlari
    lent_keywords = [
        "qarz berdim", "qarz berganim", "qarz berib", "berganim bor",
        "pul berdim", "uzatdim", "berdim qarz", "qarzga berdim",
        "одолжил", "дал в долг", "дал взаймы", "lent", "gave loan"
    ]
    
    # Qarz olish indikatorlari
    borrowed_keywords = [
        "qarz oldim", "qarz olganim", "qarz olib", "olganim bor",
        "qarzga oldim", "oldim qarz", "nasiya oldim",
        "занял", "взял в долг", "взял взаймы", "borrowed", "took loan"
    ]
    
    debt_type = None
    
    # Aniq qarz turini aniqlash
    for kw in lent_keywords:
        if kw in text_lower:
            debt_type = "lent"
            break
    
    if not debt_type:
        for kw in borrowed_keywords:
            if kw in text_lower:
                debt_type = "borrowed"
                break
    
    # Agar qarz so'zi yo'q bo'lsa, None qaytarish
    if not debt_type:
        # Qo'shimcha tekshiruv: "ga ... berdim" pattern
        if re.search(r'(\w+)ga\s+.*?(berdim|berganim|berib)', text_lower):
            # Bu kontekstda "pul/qarz berdim" ekanligini tekshirish
            if any(word in text_lower for word in ['qarz', 'pul', 'so\'m', 'sum', 'ming', 'million']):
                debt_type = "lent"
        elif re.search(r'(\w+)dan\s+.*?(oldim|olganim|olib)', text_lower):
            if any(word in text_lower for word in ['qarz', 'pul', 'so\'m', 'sum', 'ming', 'million']):
                debt_type = "borrowed"
    
    if not debt_type:
        return None
    
    # Shaxs ismini aniqlash
    person_name = extract_person_name(text)
    
    # Sanani aniqlash
    given_date = extract_date_from_text(text)
    
    # Qaytarish sanasini aniqlash
    due_date = extract_due_date(text)
    
    return {
        "type": debt_type,
        "person": person_name,
        "given_date": given_date,
        "due_date": due_date
    }


def extract_person_name(text: str) -> str:
    """
    Matndan shaxs ismini ajratib olish
    Patterns: "Islomga", "Ahmeddan", "Ali uchun", "Vali bilan"
    """
    text_lower = text.lower()
    
    # Pattern 1: "ismga" (masalan: Islomga, Ahmedga)
    match = re.search(r'([A-Za-zА-Яа-яЁёʻʼ\'-]+)ga\s', text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        # Oddiy so'zlarni filtrlash
        if name.lower() not in ['qarz', 'pul', 'nasiya', 'kredit', 'bugun', 'kecha', 'ertaga']:
            return name.capitalize()
    
    # Pattern 2: "ismdan" (masalan: Islomdan, Ahmeddan)
    match = re.search(r'([A-Za-zА-Яа-яЁёʻʼ\'-]+)dan\s', text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if name.lower() not in ['qarz', 'pul', 'nasiya', 'kredit', 'bugun', 'kecha', 'ertaga']:
            return name.capitalize()
    
    # Pattern 3: "ism uchun" yoki "ism bilan"
    match = re.search(r'([A-Za-zА-Яа-яЁёʻʼ\'-]+)\s+(uchun|bilan|ga)', text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if name.lower() not in ['qarz', 'pul', 'nasiya', 'kredit', 'bugun', 'kecha', 'ertaga', 'bu', 'shu']:
            return name.capitalize()
    
    # Pattern 4: Rus tili "кому/у кого"
    match = re.search(r'(у\s+)?([А-Яа-яЁё]+)(у|а|е)?\s', text)
    if match:
        name = match.group(2).strip()
        if len(name) > 2:
            return name.capitalize()
    
    return "Noma'lum"


def extract_date_from_text(text: str) -> str:
    """
    Matndan sanani ajratib olish
    "bugun", "kecha", "10 kuni", "5-yanvar" kabi
    Returns: "YYYY-MM-DD" format
    """
    from datetime import datetime, timedelta
    
    text_lower = text.lower()
    today = datetime.now()
    
    # "bugun" / "hozir"
    if any(word in text_lower for word in ['bugun', 'hozir', 'сегодня', 'today']):
        return today.strftime("%Y-%m-%d")
    
    # "kecha" / "oldingi kun"
    if any(word in text_lower for word in ['kecha', 'oldingi kun', 'вчера', 'yesterday']):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # "N kun oldin" / "N kuni"
    match = re.search(r'(\d+)\s*(kun|kuni|день|дня|дней|day)', text_lower)
    if match:
        days = int(match.group(1))
        # Agar "kuni" bo'lsa, bu oyning shu kunini bildiradi
        if 'kuni' in text_lower or days <= 31:
            # Joriy oyning shu sanasi
            try:
                return today.replace(day=days).strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    # "N kun oldin"
    match = re.search(r'(\d+)\s*(kun|день|day)\s*(oldin|назад|ago)', text_lower)
    if match:
        days = int(match.group(1))
        return (today - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Aniq sana: "5-yanvar", "10 fevral", "2024-01-15"
    months_uz = {
        'yanvar': 1, 'fevral': 2, 'mart': 3, 'aprel': 4,
        'may': 5, 'iyun': 6, 'iyul': 7, 'avgust': 8,
        'sentabr': 9, 'oktabr': 10, 'noyabr': 11, 'dekabr': 12
    }
    months_ru = {
        'январ': 1, 'феврал': 2, 'март': 3, 'апрел': 4,
        'ма': 5, 'июн': 6, 'июл': 7, 'август': 8,
        'сентябр': 9, 'октябр': 10, 'ноябр': 11, 'декабр': 12
    }
    
    # Pattern: "5-yanvar" yoki "5 yanvar"
    for month_name, month_num in {**months_uz, **months_ru}.items():
        match = re.search(rf'(\d{{1,2}})\s*[-\s]?\s*{month_name}', text_lower)
        if match:
            day = int(match.group(1))
            try:
                return today.replace(month=month_num, day=day).strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    # Default: bugungi sana
    return today.strftime("%Y-%m-%d")


def extract_due_date(text: str) -> Optional[str]:
    """
    Qaytarish sanasini AQLLI ajratib olish
    
    MUHIM QOIDA:
    - "10-da qaytaraman" va bugun 2-sana bo'lsa → shu oyning 10-sanasi
    - "10-da qaytaraman" va bugun 26-sana bo'lsa → KEYINGI oyning 10-sanasi
    - "birinchida" → keyingi oyning 1-sanasi
    - "1 oyda" → 1 oy keyin
    """
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta
    
    text_lower = text.lower()
    today = datetime.now()
    current_day = today.day
    
    print(f"[MUDDAT] Tahlil: '{text_lower[:60]}...', Bugun: {today.strftime('%d-%m-%Y')}")
    
    # ==================== RAQAM + DA/CHI FORMATI ====================
    # "10da", "10-da", "onida", "10-chi" kabi formatlar
    
    # Pattern: raqam + (da/ga/chi/sida/sanasida) + (qaytarish so'zi)
    day_patterns = [
        r'\b(\d{1,2})\s*[-]?\s*(?:da|ga|chi|sida|sanasida|sanasi)\b',  # 10da, 10-da, 10chi
        r'\b(\d{1,2})\s*[-]?\s*(?:ida|iga)\b',  # 10ida
    ]
    
    for pattern in day_patterns:
        match = re.search(pattern, text_lower)
        if match:
            day = int(match.group(1))
            # Faqat 1-31 orasidagi kunlar uchun
            if 1 <= day <= 31:
                # Summa emas ekanligini tekshirish (ming, mln, so'm bilan emas)
                context_around = text_lower[max(0, match.start()-15):min(len(text_lower), match.end()+15)]
                if not re.search(r'ming|mln|million|so\'m|sum|dollar', context_around):
                    try:
                        # MUHIM: Agar bugungi sana katta bo'lsa, keyingi oyga o'tish
                        if day > current_day:
                            # Shu oyning o'sha sanasi
                            target = today.replace(day=day)
                        else:
                            # Keyingi oyning o'sha sanasi
                            target = (today + relativedelta(months=1)).replace(day=day)
                        
                        result = target.strftime("%Y-%m-%d")
                        print(f"[MUDDAT] ✅ '{day}-da' topildi, bugun={current_day} → {result}")
                        return result
                    except ValueError:
                        # Agar sana noto'g'ri bo'lsa (31-fevral kabi)
                        pass
    
    # ==================== SO'Z BILAN SANA (birinchida, ikkinchida, o'ninchida) ====================
    # MUHIM: Har xil yozuv usullari - o', o', ʻ, ʼ, ', '
    
    # Barcha tartib sonlar - turli apostrof variantlari bilan
    ordinal_numbers = [
        # 1-10
        (r'\bbirinchi', 1),
        (r'\bikkinchi', 2),
        (r'\buchinchi', 3),
        (r'\b(?:to[\'\'ʻʼ]?rt|tort)inchi', 4),  # to'rtinchi, tortinchi
        (r'\bbeshinchi', 5),
        (r'\boltinchi', 6),
        (r'\byettinchi', 7),
        (r'\bsakkizinchi', 8),
        (r'\b(?:to[\'\'ʻʼ]?qqiz|toqqiz)inchi', 9),  # to'qqizinchi
        (r'\b(?:o[\'\'ʻʼ]?n|on)inchi', 10),  # o'ninchi, oninchi
        # 11-19
        (r'\b(?:o[\'\'ʻʼ]?n\s*bir|on\s*bir)inchi', 11),
        (r'\b(?:o[\'\'ʻʼ]?n\s*ikki|on\s*ikki)nchi', 12),
        (r'\b(?:o[\'\'ʻʼ]?n\s*uch|on\s*uch)inchi', 13),
        (r'\b(?:o[\'\'ʻʼ]?n\s*to[\'\'ʻʼ]?rt|on\s*tort)inchi', 14),
        (r'\b(?:o[\'\'ʻʼ]?n\s*besh|on\s*besh)inchi', 15),
        # 20, 30
        (r'\byigirma(?:nchi)?', 20),
        (r'\b(?:o[\'\'ʻʼ]?ttiz|ottiz)(?:inchi)?', 30),
        # 21-29
        (r'\byigirma\s*bir(?:inchi)?', 21),
        (r'\byigirma\s*ikki(?:nchi)?', 22),
        (r'\byigirma\s*uch(?:inchi)?', 23),
        (r'\byigirma\s*besh(?:inchi)?', 25),
    ]
    
    for pattern, day in ordinal_numbers:
        # Qo'shimchalar: da, ga, chi, sida, ida, iga, dan, gacha
        full_pattern = pattern + r'(?:da|ga|chi|sida|ida|iga|dan|gacha|ni|ning)?\b'
        if re.search(full_pattern, text_lower):
            try:
                if day > current_day:
                    target = today.replace(day=day)
                else:
                    target = (today + relativedelta(months=1)).replace(day=day)
                result = target.strftime("%Y-%m-%d")
                print(f"[MUDDAT] ✅ Tartib son topildi: {day} → {result}")
                return result
            except ValueError:
                pass
    
    # ==================== OYLIK IBORALAR ====================
    
    # "N oyda" / "N oydan keyin" / "N oy ichida"
    month_patterns = [
        r'(\d+)\s*(?:oy|ойда|oyda|oydan|oy\s*ichida|месяц)',
        r'(\d+)\s*месяц',
    ]
    
    for pattern in month_patterns:
        match = re.search(pattern, text_lower)
        if match:
            months = int(match.group(1))
            result = (today + relativedelta(months=months)).strftime("%Y-%m-%d")
            print(f"[MUDDAT] ✅ '{months} oyda' topildi → {result}")
            return result
    
    # "keyingi oy" / "kelasi oy" / "boshqa oy"
    next_month_keywords = [
        'keyingi oy', 'kelasi oy', 'boshqa oy', 'ertaga oy',
        'следующий месяц', 'next month', 'через месяц'
    ]
    
    for keyword in next_month_keywords:
        if keyword in text_lower:
            result = (today + relativedelta(months=1)).strftime("%Y-%m-%d")
            print(f"[MUDDAT] ✅ '{keyword}' topildi → {result}")
            return result
    
    # ==================== HAFTALIK IBORALAR ====================
    
    # "N hafta" / "N haftada"
    week_match = re.search(r'(\d+)\s*(?:hafta|недел|week)', text_lower)
    if week_match:
        weeks = int(week_match.group(1))
        result = (today + timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        print(f"[MUDDAT] ✅ '{weeks} hafta' topildi → {result}")
        return result
    
    # "keyingi hafta" / "kelasi hafta"
    next_week_keywords = [
        'keyingi hafta', 'kelasi hafta', 'boshqa hafta',
        'следующая неделя', 'next week', 'через неделю'
    ]
    
    for keyword in next_week_keywords:
        if keyword in text_lower:
            result = (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
            print(f"[MUDDAT] ✅ '{keyword}' topildi → {result}")
            return result
    
    # ==================== KUNLIK IBORALAR ====================
    
    # "N kunda" / "N kundan keyin"
    day_match = re.search(r'(\d+)\s*(?:kun|день|day)\s*(?:da|dan|ichida|keyin|через|ga)?', text_lower)
    if day_match:
        days = int(day_match.group(1))
        if days <= 365:  # Mantiqiy chegaralash
            result = (today + timedelta(days=days)).strftime("%Y-%m-%d")
            print(f"[MUDDAT] ✅ '{days} kunda' topildi → {result}")
            return result
    
    # ==================== OY NOMLARI ====================
    
    months_dict = {
        # O'zbek
        'yanvar': 1, 'fevral': 2, 'mart': 3, 'aprel': 4,
        'may': 5, 'iyun': 6, 'iyul': 7, 'avgust': 8,
        'sentabr': 9, 'oktabr': 10, 'noyabr': 11, 'dekabr': 12,
        # Rus
        'январ': 1, 'феврал': 2, 'март': 3, 'апрел': 4,
        'май': 5, 'июн': 6, 'июл': 7, 'август': 8,
        'сентябр': 9, 'октябр': 10, 'ноябр': 11, 'декабр': 12,
    }
    
    # "N-fevral" yoki "fevralda" formatlarini tekshirish
    for month_name, month_num in months_dict.items():
        # "10-fevral" / "10 fevral"
        date_month_match = re.search(rf'(\d{{1,2}})\s*[-\s]?\s*{month_name}', text_lower)
        if date_month_match:
            day = int(date_month_match.group(1))
            try:
                year = today.year
                target = datetime(year, month_num, day)
                if target <= today:
                    target = datetime(year + 1, month_num, day)
                result = target.strftime("%Y-%m-%d")
                print(f"[MUDDAT] ✅ '{day}-{month_name}' topildi → {result}")
                return result
            except ValueError:
                pass
        
        # "fevralda" → fevralning 1-sanasi
        if re.search(rf'\b{month_name}(?:da|ga|gacha)?\b', text_lower):
            try:
                year = today.year
                target = datetime(year, month_num, 1)
                if target <= today:
                    target = datetime(year + 1, month_num, 1)
                result = target.strftime("%Y-%m-%d")
                print(f"[MUDDAT] ✅ '{month_name}da' topildi → {result}")
                return result
            except ValueError:
                pass
    
    print(f"[MUDDAT] ⚠️ Muddat topilmadi")
    return None


async def save_personal_debt(db, user_id: int, debt_info: Dict, save_as_transaction: bool = True) -> int:
    """
    Qarzni bazaga saqlash
    
    Args:
        db: Database instance
        user_id: Foydalanuvchi ID
        debt_info: Qarz ma'lumotlari
        save_as_transaction: True bo'lsa, berilgan qarzni harajat sifatida ham saqlaydi
    """
    # Convert string dates to date objects for PostgreSQL
    given_date = debt_info["given_date"]
    due_date = debt_info.get("due_date")
    debt_type = debt_info["type"]  # "given" yoki "taken"
    amount = debt_info["amount"]
    person = debt_info["person"]
    
    debt_id = 0
    
    if db.is_postgres:
        # PostgreSQL requires date objects, not strings
        from datetime import datetime as dt
        if isinstance(given_date, str):
            given_date = dt.strptime(given_date, "%Y-%m-%d").date()
        if due_date and isinstance(due_date, str):
            due_date = dt.strptime(due_date, "%Y-%m-%d").date()
        
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO personal_debts 
                (user_id, debt_type, person_name, amount, description, original_text, given_date, due_date, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
                RETURNING id
            """, 
                user_id,
                debt_type,
                person,
                amount,
                debt_info.get("description", ""),
                debt_info.get("original_text", ""),
                given_date,
                due_date
            )
            debt_id = row["id"] if row else 0
    else:
        await db._connection.execute("""
            INSERT INTO personal_debts 
            (user_id, debt_type, person_name, amount, description, original_text, given_date, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (
            user_id,
            debt_type,
            person,
            amount,
            debt_info.get("description", ""),
            debt_info.get("original_text", ""),
            given_date,
            due_date
        ))
        await db._connection.commit()
        
        cursor = await db._connection.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        debt_id = row[0] if row else 0
    
    # ========== BERILGAN QARZNI HARAJAT SIFATIDA SAQLASH ==========
    # Agar "given" (men berdim) bo'lsa - bu harajat hisoblanadi
    # Agar "taken" (menga berishdi) bo'lsa - bu daromad emas, qarz
    if save_as_transaction and debt_type == "given" and debt_id > 0:
        try:
            description = f"Qarz berildi: {person}"
            original_text = debt_info.get("original_text", f"{person}ga {amount} qarz berdim")
            
            if db.is_postgres:
                async with db._pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO transactions 
                        (user_id, type, category, amount, description, original_text, debt_id, created_at)
                        VALUES ($1, 'expense', 'qarz', $2, $3, $4, $5, NOW())
                    """, user_id, amount, description, original_text, debt_id)
            else:
                from datetime import datetime as dt
                await db._connection.execute("""
                    INSERT INTO transactions 
                    (user_id, type, category, amount, description, original_text, debt_id, created_at)
                    VALUES (?, 'expense', 'qarz', ?, ?, ?, ?, ?)
                """, (user_id, amount, description, original_text, debt_id, dt.now().isoformat()))
                await db._connection.commit()
            
            logger.info(f"[DEBT] Berilgan qarz harajat sifatida saqlandi: {amount} so'm -> {person}")
        except Exception as e:
            logger.error(f"[DEBT] Qarzni harajat sifatida saqlashda xatolik: {e}")
    
    return debt_id


async def get_user_debts(db, user_id: int, status: str = "active") -> List[Dict]:
    """
    Foydalanuvchi qarzlarini olish
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            if status == "all":
                rows = await conn.fetch("""
                    SELECT * FROM personal_debts 
                    WHERE user_id = $1
                    ORDER BY given_date DESC
                """, user_id)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM personal_debts 
                    WHERE user_id = $1 AND status = $2
                    ORDER BY given_date DESC
                """, user_id, status)
            return [dict(row) for row in rows]
    else:
        if status == "all":
            cursor = await db._connection.execute("""
                SELECT * FROM personal_debts 
                WHERE user_id = ?
                ORDER BY given_date DESC
            """, (user_id,))
        else:
            cursor = await db._connection.execute("""
                SELECT * FROM personal_debts 
                WHERE user_id = ? AND status = ?
                ORDER BY given_date DESC
            """, (user_id, status))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_debt_summary(db, user_id: int) -> Dict:
    """
    Qarz xulosasi - bergan va olgan qarzlar
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            # Bergan qarzlar (lent)
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(amount - returned_amount), 0) as total
                FROM personal_debts 
                WHERE user_id = $1 AND debt_type = 'lent' AND status != 'returned'
            """, user_id)
            total_lent = row["total"] if row else 0
            
            # Olgan qarzlar (borrowed)
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(amount - returned_amount), 0) as total
                FROM personal_debts 
                WHERE user_id = $1 AND debt_type = 'borrowed' AND status != 'returned'
            """, user_id)
            total_borrowed = row["total"] if row else 0
            
            # Soni
            rows = await conn.fetch("""
                SELECT debt_type, COUNT(*) as count
                FROM personal_debts 
                WHERE user_id = $1 AND status != 'returned'
                GROUP BY debt_type
            """, user_id)
            counts = {row["debt_type"]: row["count"] for row in rows}
    else:
        # Bergan qarzlar (lent) - menga qaytarilishi kerak
        cursor = await db._connection.execute("""
            SELECT COALESCE(SUM(amount - returned_amount), 0) as total
            FROM personal_debts 
            WHERE user_id = ? AND debt_type = 'lent' AND status != 'returned'
        """, (user_id,))
        row = await cursor.fetchone()
        total_lent = row[0] if row else 0
        
        # Olgan qarzlar (borrowed) - men qaytarishim kerak
        cursor = await db._connection.execute("""
            SELECT COALESCE(SUM(amount - returned_amount), 0) as total
            FROM personal_debts 
            WHERE user_id = ? AND debt_type = 'borrowed' AND status != 'returned'
        """, (user_id,))
        row = await cursor.fetchone()
        total_borrowed = row[0] if row else 0
        
        # Soni
        cursor = await db._connection.execute("""
            SELECT debt_type, COUNT(*) as count
            FROM personal_debts 
            WHERE user_id = ? AND status != 'returned'
            GROUP BY debt_type
        """, (user_id,))
        rows = await cursor.fetchall()
        counts = {row[0]: row[1] for row in rows}
    
    return {
        "total_lent": total_lent,  # Bergan qarzlar (menga qaytariladi)
        "total_borrowed": total_borrowed,  # Olgan qarzlar (men qaytaraman)
        "net_balance": total_lent - total_borrowed,  # Sof balans
        "lent_count": counts.get("lent", 0),
        "borrowed_count": counts.get("borrowed", 0)
    }


async def update_debt_status(db, debt_id: int, user_id: int, status: str, returned_amount: float = None) -> bool:
    """
    Qarz statusini yangilash
    """
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            if returned_amount is not None:
                # PostgreSQL requires date object, not string
                returned_date = datetime.now().date()
                await conn.execute("""
                    UPDATE personal_debts 
                    SET status = $1, returned_amount = $2, returned_date = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $4 AND user_id = $5
                """, status, returned_amount, returned_date, debt_id, user_id)
            else:
                await conn.execute("""
                    UPDATE personal_debts 
                    SET status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2 AND user_id = $3
                """, status, debt_id, user_id)
    else:
        if returned_amount is not None:
            await db._connection.execute("""
                UPDATE personal_debts 
                SET status = ?, returned_amount = ?, returned_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (status, returned_amount, datetime.now().strftime("%Y-%m-%d"), debt_id, user_id))
        else:
            await db._connection.execute("""
                UPDATE personal_debts 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (status, debt_id, user_id))
        
        await db._connection.commit()
    return True


def format_debt_saved_message(debt_info: Dict, lang: str = "uz") -> str:
    """
    Qarz saqlandi xabarini formatlash
    Valyutani ham ko'rsatadi
    """
    debt_type = debt_info["type"]
    person = debt_info["person"]
    amount = debt_info["amount"]
    currency = debt_info.get("currency", "UZS")
    amount_in_som = debt_info.get("amount_in_som", amount)
    given_date = debt_info["given_date"]
    due_date = debt_info.get("due_date")
    
    # Valyuta belgisi
    currency_symbols = {"UZS": "so'm", "USD": "$", "RUB": "₽"}
    currency_text = currency_symbols.get(currency, "so'm")
    
    if lang == "uz":
        if debt_type == "lent":
            type_text = "💸 QARZ BERDIM"
            emoji = "📤"
            direction = f"*{person}*ga bergan qarzim"
        else:
            type_text = "💰 QARZ OLDIM"
            emoji = "📥"
            direction = f"*{person}*dan olgan qarzim"
        
        msg = (
            f"✅ {type_text}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {direction}\n"
        )
        
        # Valyutaga qarab summa
        if currency == "UZS":
            msg += f"💵 Summa: *{amount:,}* so'm\n"
        else:
            msg += f"💵 Summa: *{amount:,}* {currency_text}\n"
            msg += f"   ≈ _{amount_in_som:,} so'm_\n"
        
        msg += f"📅 Sana: *{given_date}*\n"
        
        if due_date:
            msg += f"⏰ Qaytarish: *{due_date}*\n"
        else:
            msg += "⏰ Muddat: _Belgilanmagan_\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━"
        
    else:
        if debt_type == "lent":
            type_text = "💸 ДАЛ В ДОЛГ"
            emoji = "📤"
            direction = f"Дал в долг *{person}*"
        else:
            type_text = "💰 ВЗЯЛ В ДОЛГ"
            emoji = "📥"
            direction = f"Взял в долг у *{person}*"
        
        msg = (
            f"✅ {type_text}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {direction}\n"
        )
        
        if currency == "UZS":
            msg += f"💵 Сумма: *{amount:,}* сум\n"
        else:
            msg += f"💵 Сумма: *{amount:,}* {currency_text}\n"
            msg += f"   ≈ _{amount_in_som:,} сум_\n"
        
        msg += f"📅 Дата: *{given_date}*\n"
        
        if due_date:
            msg += f"⏰ Возврат: *{due_date}*\n"
        else:
            msg += "⏰ Срок: _Не указан_\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━"
    
    return msg


def format_debt_summary_message(summary: Dict, lang: str = "uz") -> str:
    """
    Qarz xulosasini formatlash
    """
    total_lent = summary["total_lent"]
    total_borrowed = summary["total_borrowed"]
    net_balance = summary["net_balance"]
    lent_count = summary["lent_count"]
    borrowed_count = summary["borrowed_count"]
    
    if lang == "uz":
        msg = (
            "📊 *QARZ HOLATI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📤 *Bergan qarzlarim:*\n"
            f"├ Jami: *{total_lent:,}* so'm\n"
            f"└ Soni: *{lent_count}* ta\n\n"
            f"📥 *Olgan qarzlarim:*\n"
            f"├ Jami: *{total_borrowed:,}* so'm\n"
            f"└ Soni: *{borrowed_count}* ta\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if net_balance > 0:
            msg += f"💚 *Sof balans:* +{net_balance:,} so'm\n"
            msg += "_Sizga qaytarilishi kerak_"
        elif net_balance < 0:
            msg += f"🔴 *Sof balans:* {net_balance:,} so'm\n"
            msg += "_Siz qaytarishingiz kerak_"
        else:
            msg += f"⚪ *Sof balans:* 0 so'm\n"
            msg += "_Qarz yo'q_"
    else:
        msg = (
            "📊 *СОСТОЯНИЕ ДОЛГОВ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📤 *Дал в долг:*\n"
            f"├ Всего: *{total_lent:,}* сум\n"
            f"└ Количество: *{lent_count}*\n\n"
            f"📥 *Взял в долг:*\n"
            f"├ Всего: *{total_borrowed:,}* сум\n"
            f"└ Количество: *{borrowed_count}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if net_balance > 0:
            msg += f"💚 *Чистый баланс:* +{net_balance:,} сум\n"
            msg += "_Вам должны вернуть_"
        elif net_balance < 0:
            msg += f"🔴 *Чистый баланс:* {net_balance:,} сум\n"
            msg += "_Вы должны вернуть_"
        else:
            msg += f"⚪ *Чистый баланс:* 0 сум\n"
            msg += "_Долгов нет_"
    
    return msg


def detect_currency(text: str) -> Tuple[str, float]:
    """
    Matndan valyutani aniqlash
    
    Returns: (currency_code, exchange_rate_to_som)
    
    Qo'llab-quvvatlanadigan valyutalar:
    - UZS (so'm) - default
    - USD (dollar)
    - RUB (rubl)
    """
    text_lower = text.lower()
    
    # Dollar tekshirish
    dollar_keywords = ['dollar', 'doller', 'долар', 'долл', 'usd', '$', 
                       'dollarga', 'dollardan', 'dollarni', 'dollarlik']
    for kw in dollar_keywords:
        if kw in text_lower:
            # O'zbekiston kursini olish (taxminiy)
            # Real loyihada API dan olish kerak
            USD_RATE = 12500  # 1 USD = 12,500 so'm (taxminiy)
            return "USD", USD_RATE
    
    # Rubl tekshirish
    rubl_keywords = ['rubl', 'ruble', 'рубл', 'rub', '₽']
    for kw in rubl_keywords:
        if kw in text_lower:
            RUB_RATE = 135  # 1 RUB = 135 so'm (taxminiy)
            return "RUB", RUB_RATE
    
    # Default - so'm
    return "UZS", 1.0


async def parse_debt_transaction(text: str, lang: str = "uz") -> Optional[Dict]:
    """
    Matndan qarz tranzaksiyasini to'liq tahlil qilish
    Valyutani ham aniqlaydi
    """
    # Avval qarz ekanligini tekshirish
    debt_info = detect_debt_transaction(text)
    
    if not debt_info:
        return None
    
    # Summani olish
    amount = extract_amount(text)
    
    if not amount:
        return None
    
    # Valyutani aniqlash
    currency, rate = detect_currency(text)
    
    debt_info["amount"] = amount
    debt_info["currency"] = currency
    debt_info["exchange_rate"] = rate
    debt_info["amount_in_som"] = int(amount * rate)  # So'mda hisoblash uchun
    debt_info["description"] = extract_description(text, amount)
    debt_info["original_text"] = text
    
    print(f"[QARZ] Summa: {amount:,} {currency}, So'mda: {debt_info['amount_in_som']:,}")
    
    return debt_info


# ==================== HISOBOTLAR (REPORTS) ====================

async def get_period_transactions(db, user_id: int, period: str = "daily") -> Dict:
    """
    Davr bo'yicha tranzaksiyalarni olish
    
    Args:
        db: Database instance
        user_id: Foydalanuvchi ID
        period: "daily", "weekly", "monthly"
    
    Returns:
        Dict: {income, expense, transactions, period_start, period_end}
    """
    from datetime import datetime, timedelta
    
    now = datetime.now()
    
    if period == "daily":
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif period == "weekly":
        # Dushanba - hafta boshi
        days_since_monday = now.weekday()
        period_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:  # monthly
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM transactions 
                    WHERE user_id = $1 AND created_at >= $2 AND created_at <= $3
                    ORDER BY created_at DESC
                """, user_id, period_start, period_end)
                transactions = [dict(row) for row in rows]
        else:
            cursor = await db._connection.execute("""
                SELECT * FROM transactions 
                WHERE user_id = ? AND created_at >= ? AND created_at <= ?
                ORDER BY created_at DESC
            """, (user_id, period_start.isoformat(), period_end.isoformat()))
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            transactions = [dict(zip(columns, row)) for row in rows]
        
        # Hisoblash
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
        total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        
        # Kategoriyalar bo'yicha
        expenses_by_category = {}
        incomes_by_category = {}
        
        for t in transactions:
            cat = t["category"]
            if t["type"] == "expense":
                expenses_by_category[cat] = expenses_by_category.get(cat, 0) + t["amount"]
            else:
                incomes_by_category[cat] = incomes_by_category.get(cat, 0) + t["amount"]
        
        return {
            "income": total_income,
            "expense": total_expense,
            "balance": total_income - total_expense,
            "transactions": transactions,
            "transaction_count": len(transactions),
            "expenses_by_category": expenses_by_category,
            "incomes_by_category": incomes_by_category,
            "period_start": period_start,
            "period_end": period_end,
            "period": period
        }
    except Exception as e:
        logger.error(f"[REPORT] Davr tranzaksiyalarini olishda xatolik: {e}")
        return {
            "income": 0,
            "expense": 0,
            "balance": 0,
            "transactions": [],
            "transaction_count": 0,
            "expenses_by_category": {},
            "incomes_by_category": {},
            "period_start": period_start,
            "period_end": period_end,
            "period": period
        }


def format_period_report(report_data: Dict, lang: str = "uz") -> str:
    """Davr hisobotini formatlash"""
    from app.languages import format_number
    
    period = report_data["period"]
    income = report_data["income"]
    expense = report_data["expense"]
    balance = report_data["balance"]
    count = report_data["transaction_count"]
    expenses_by_cat = report_data["expenses_by_category"]
    incomes_by_cat = report_data["incomes_by_category"]
    
    # Davr nomi
    if lang == "uz":
        period_names = {"daily": "KUNLIK", "weekly": "HAFTALIK", "monthly": "OYLIK"}
        period_name = period_names.get(period, "")
        
        msg = (
            f"📊 *{period_name} HISOBOT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if count == 0:
            msg += "📭 Bu davr uchun tranzaksiyalar yo'q.\n"
        else:
            msg += f"📈 *Daromad:* +{format_number(income)} so'm\n"
            msg += f"📉 *Xarajat:* -{format_number(expense)} so'm\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if balance >= 0:
                msg += f"💰 *Balans:* +{format_number(balance)} so'm ✅\n\n"
            else:
                msg += f"💰 *Balans:* {format_number(balance)} so'm ⚠️\n\n"
            
            msg += f"📝 Jami: *{count} ta* tranzaksiya\n\n"
            
            # Top xarajatlar
            if expenses_by_cat:
                msg += "📉 *Top xarajatlar:*\n"
                sorted_exp = sorted(expenses_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]
                for cat, amt in sorted_exp:
                    cat_emoji = CATEGORY_EMOJIS.get(cat, "📌")
                    msg += f"├ {cat_emoji} {cat}: {format_number(amt)} so'm\n"
                msg += "\n"
            
            # Top daromadlar
            if incomes_by_cat:
                msg += "📈 *Top daromadlar:*\n"
                sorted_inc = sorted(incomes_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]
                for cat, amt in sorted_inc:
                    cat_emoji = CATEGORY_EMOJIS.get(cat, "💵")
                    msg += f"├ {cat_emoji} {cat}: {format_number(amt)} so'm\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 _Matnli kiritish BEPUL va cheksiz!_"
        
    else:  # Russian
        period_names = {"daily": "ДНЕВНОЙ", "weekly": "НЕДЕЛЬНЫЙ", "monthly": "МЕСЯЧНЫЙ"}
        period_name = period_names.get(period, "")
        
        msg = (
            f"📊 *{period_name} ОТЧЁТ*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if count == 0:
            msg += "📭 Нет транзакций за этот период.\n"
        else:
            msg += f"📈 *Доход:* +{format_number(income)} сум\n"
            msg += f"📉 *Расход:* -{format_number(expense)} сум\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if balance >= 0:
                msg += f"💰 *Баланс:* +{format_number(balance)} сум ✅\n\n"
            else:
                msg += f"💰 *Баланс:* {format_number(balance)} сум ⚠️\n\n"
            
            msg += f"📝 Всего: *{count}* транзакций\n\n"
            
            # Top расходы
            if expenses_by_cat:
                msg += "📉 *Топ расходы:*\n"
                sorted_exp = sorted(expenses_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]
                for cat, amt in sorted_exp:
                    cat_emoji = CATEGORY_EMOJIS.get(cat, "📌")
                    msg += f"├ {cat_emoji} {cat}: {format_number(amt)} сум\n"
                msg += "\n"
            
            # Top доходы
            if incomes_by_cat:
                msg += "📈 *Топ доходы:*\n"
                sorted_inc = sorted(incomes_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]
                for cat, amt in sorted_inc:
                    cat_emoji = CATEGORY_EMOJIS.get(cat, "💵")
                    msg += f"├ {cat_emoji} {cat}: {format_number(amt)} сум\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 _Текстовый ввод БЕСПЛАТНО!_"
    
    return msg


async def get_user_real_balance(db, user_id: int) -> Dict:
    """
    Foydalanuvchining haqiqiy balansini hisoblash
    (berilgan qarzlar hisobga olingan)
    
    Returns:
        Dict: {total_income, total_expense, balance, given_debts, taken_debts, net_balance}
    """
    try:
        # Barcha tranzaksiyalar
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                # Daromadlar
                income_row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total FROM transactions 
                    WHERE user_id = $1 AND type = 'income'
                """, user_id)
                total_income = income_row["total"] if income_row else 0
                
                # Xarajatlar (qarzlar ham kiradi)
                expense_row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total FROM transactions 
                    WHERE user_id = $1 AND type = 'expense'
                """, user_id)
                total_expense = expense_row["total"] if expense_row else 0
                
                # Aktiv berilgan qarzlar
                given_row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total FROM personal_debts 
                    WHERE user_id = $1 AND debt_type = 'given' AND status = 'active'
                """, user_id)
                given_debts = given_row["total"] if given_row else 0
                
                # Aktiv olingan qarzlar
                taken_row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total FROM personal_debts 
                    WHERE user_id = $1 AND debt_type = 'taken' AND status = 'active'
                """, user_id)
                taken_debts = taken_row["total"] if taken_row else 0
        else:
            # SQLite
            cursor = await db._connection.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE user_id = ? AND type = 'income'
            """, (user_id,))
            row = await cursor.fetchone()
            total_income = row[0] if row else 0
            
            cursor = await db._connection.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE user_id = ? AND type = 'expense'
            """, (user_id,))
            row = await cursor.fetchone()
            total_expense = row[0] if row else 0
            
            cursor = await db._connection.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM personal_debts 
                WHERE user_id = ? AND debt_type = 'given' AND status = 'active'
            """, (user_id,))
            row = await cursor.fetchone()
            given_debts = row[0] if row else 0
            
            cursor = await db._connection.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM personal_debts 
                WHERE user_id = ? AND debt_type = 'taken' AND status = 'active'
            """, (user_id,))
            row = await cursor.fetchone()
            taken_debts = row[0] if row else 0
        
        # Haqiqiy balans
        balance = total_income - total_expense
        # Sof balans (qaytarilmagan qarzlarni hisobga olgan holda)
        # given_debts - men berdim, qaytib kelishi kerak (+)
        # taken_debts - menga berishdi, qaytarishim kerak (-)
        net_balance = balance + given_debts - taken_debts
        
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance,
            "given_debts": given_debts,
            "taken_debts": taken_debts,
            "net_balance": net_balance
        }
    except Exception as e:
        logger.error(f"[BALANCE] Balans hisoblashda xatolik: {e}")
        return {
            "total_income": 0,
            "total_expense": 0,
            "balance": 0,
            "given_debts": 0,
            "taken_debts": 0,
            "net_balance": 0
        }


def format_real_balance_message(balance_data: Dict, lang: str = "uz") -> str:
    """Haqiqiy balans xabarini formatlash"""
    from app.languages import format_number
    
    income = balance_data["total_income"]
    expense = balance_data["total_expense"]
    balance = balance_data["balance"]
    given = balance_data["given_debts"]
    taken = balance_data["taken_debts"]
    net = balance_data["net_balance"]
    
    if lang == "uz":
        msg = (
            "💰 *HAQIQIY BALANS*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 Jami daromad: *{format_number(income)}* so'm\n"
            f"📉 Jami xarajat: *{format_number(expense)}* so'm\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Joriy balans: *{format_number(balance)}* so'm\n\n"
        )
        
        if given > 0 or taken > 0:
            msg += "🔄 *Qarz holati:*\n"
            if given > 0:
                msg += f"├ 📤 Berilgan qarz: *{format_number(given)}* so'm\n"
                msg += f"│   _(qaytib kelishi kerak)_\n"
            if taken > 0:
                msg += f"├ 📥 Olingan qarz: *{format_number(taken)}* so'm\n"
                msg += f"│   _(qaytarishingiz kerak)_\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        
        if net >= 0:
            msg += f"🎯 *SOF BALANS: +{format_number(net)} so'm* ✅"
        else:
            msg += f"🎯 *SOF BALANS: {format_number(net)} so'm* ⚠️"
    else:
        msg = (
            "💰 *РЕАЛЬНЫЙ БАЛАНС*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 Всего доход: *{format_number(income)}* сум\n"
            f"📉 Всего расход: *{format_number(expense)}* сум\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Текущий баланс: *{format_number(balance)}* сум\n\n"
        )
        
        if given > 0 or taken > 0:
            msg += "🔄 *Долги:*\n"
            if given > 0:
                msg += f"├ 📤 Дал в долг: *{format_number(given)}* сум\n"
                msg += f"│   _(должны вернуть)_\n"
            if taken > 0:
                msg += f"├ 📥 Взял в долг: *{format_number(taken)}* сум\n"
                msg += f"│   _(нужно вернуть)_\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        
        if net >= 0:
            msg += f"🎯 *ЧИСТЫЙ БАЛАНС: +{format_number(net)} сум* ✅"
        else:
            msg += f"🎯 *ЧИСТЫЙ БАЛАНС: {format_number(net)} сум* ⚠️"
    
    return msg


# ==================== SCHEDULED REPORTS (Job Queue) ====================

async def send_scheduled_report(context, telegram_id: int, period: str = "daily") -> bool:
    """
    Foydalanuvchiga rejalashtirilgan hisobot yuborish (GIBRID USUL)
    
    - Kunlik: Faqat matn (tez, arzon)
    - Haftalik: Matn + mini grafik rasm
    - Oylik: To'liq rasm hisobot
    
    Args:
        context: Telegram context
        telegram_id: Foydalanuvchi Telegram ID
        period: "daily", "weekly", "monthly"
    """
    from app.database import get_database
    from telegram import InputFile
    
    try:
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            return False
        
        lang = user.get("language", "uz")
        
        # Hisobotni olish
        report_data = await get_period_transactions(db, user["id"], period)
        
        # Agar tranzaksiyalar bo'lmasa, yubormaslik
        if report_data["transaction_count"] == 0:
            return False
        
        # ========== GIBRID USUL ==========
        if period == "daily":
            # KUNLIK: Faqat matn
            report_msg = format_period_report(report_data, lang)
            await context.bot.send_message(
                chat_id=telegram_id,
                text=report_msg,
                parse_mode="Markdown"
            )
            
        elif period == "weekly":
            # HAFTALIK: Matn + rasm (agar mavjud bo'lsa)
            from app.report_images import generate_weekly_report_image, is_image_generation_available
            
            if is_image_generation_available():
                image_bytes = generate_weekly_report_image(report_data, lang)
                if image_bytes:
                    # Rasm yuborish
                    await context.bot.send_photo(
                        chat_id=telegram_id,
                        photo=InputFile(io.BytesIO(image_bytes), filename="weekly_report.png"),
                        caption="📆 " + ("Haftalik hisobot" if lang == "uz" else "Недельный отчёт")
                    )
                else:
                    # Rasm yaratilmadi - matn yuborish
                    report_msg = format_period_report(report_data, lang)
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=report_msg,
                        parse_mode="Markdown"
                    )
            else:
                # PIL mavjud emas - matn yuborish
                report_msg = format_period_report(report_data, lang)
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=report_msg,
                    parse_mode="Markdown"
                )
                
        elif period == "monthly":
            # OYLIK: To'liq rasm hisobot
            from app.report_images import generate_monthly_report_image, is_image_generation_available
            
            if is_image_generation_available():
                # Balans ma'lumotlarini olish
                balance_data = await get_user_real_balance(db, user["id"])
                
                image_bytes = generate_monthly_report_image(report_data, balance_data, lang)
                if image_bytes:
                    # Rasm yuborish
                    caption = "🗓 " + ("Oylik hisobot" if lang == "uz" else "Месячный отчёт")
                    caption += "\n\n💡 " + ("Batafsil: /report" if lang == "uz" else "Подробнее: /report")
                    
                    await context.bot.send_photo(
                        chat_id=telegram_id,
                        photo=InputFile(io.BytesIO(image_bytes), filename="monthly_report.png"),
                        caption=caption
                    )
                else:
                    # Rasm yaratilmadi - matn yuborish
                    report_msg = format_period_report(report_data, lang)
                    balance_msg = format_real_balance_message(balance_data, lang)
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=report_msg + "\n\n" + balance_msg,
                        parse_mode="Markdown"
                    )
            else:
                # PIL mavjud emas - matn yuborish
                report_msg = format_period_report(report_data, lang)
                balance_data = await get_user_real_balance(db, user["id"])
                balance_msg = format_real_balance_message(balance_data, lang)
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=report_msg + "\n\n" + balance_msg,
                    parse_mode="Markdown"
                )
        
        logger.info(f"[REPORT] {period} hisobot yuborildi: {telegram_id}")
        return True
        
    except Exception as e:
        logger.error(f"[REPORT] Hisobot yuborishda xatolik: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== BATCH REPORT SENDING ====================
# Server yuklanishini kamaytirish uchun hisobotlar navbat bilan yuboriladi
# Har bir userga yuborilgandan keyin kutish (delay) qo'shiladi

REPORT_BATCH_SIZE = 10  # Bir batch da nechta user
REPORT_DELAY_SECONDS = 3  # Har bir user orasida kutish (soniya)
REPORT_BATCH_DELAY = 10  # Batch orasida kutish (soniya)


async def send_daily_reports(context) -> int:
    """
    Barcha foydalanuvchilarga kunlik hisobot yuborish (BATCH MODE)
    Kunlik = faqat matn, tez yuboriladi
    """
    import asyncio
    from app.database import get_database
    
    db = await get_database()
    sent_count = 0
    failed_count = 0
    
    try:
        # Hisobot olish yoqilgan foydalanuvchilar
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT telegram_id FROM users 
                    WHERE reports_daily = true AND telegram_id IS NOT NULL
                    ORDER BY RANDOM()
                """)
        else:
            cursor = await db._connection.execute("""
                SELECT telegram_id FROM users 
                WHERE reports_daily = 1 AND telegram_id IS NOT NULL
                ORDER BY RANDOM()
            """)
            rows = await cursor.fetchall()
        
        total_users = len(rows)
        logger.info(f"[REPORT] Kunlik hisobot: {total_users} ta foydalanuvchi")
        
        for i, row in enumerate(rows):
            telegram_id = row[0] if isinstance(row, tuple) else row["telegram_id"]
            
            try:
                success = await send_scheduled_report(context, telegram_id, "daily")
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"[REPORT] Daily error for {telegram_id}: {e}")
                failed_count += 1
            
            # Delay: kunlik matn uchun 1 soniya yetarli
            if i < total_users - 1:
                await asyncio.sleep(1)
        
        logger.info(f"[REPORT] Kunlik hisobotlar: {sent_count} yuborildi, {failed_count} xatolik")
        
    except Exception as e:
        logger.error(f"[REPORT] Kunlik hisobotlar xatolik: {e}")
    
    return sent_count


async def send_weekly_reports(context) -> int:
    """
    Barcha foydalanuvchilarga haftalik hisobot yuborish (BATCH MODE)
    Haftalik = rasm bilan, sekinroq yuboriladi
    """
    import asyncio
    from app.database import get_database
    
    db = await get_database()
    sent_count = 0
    failed_count = 0
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT telegram_id FROM users 
                    WHERE reports_weekly = true AND telegram_id IS NOT NULL
                    ORDER BY RANDOM()
                """)
        else:
            cursor = await db._connection.execute("""
                SELECT telegram_id FROM users 
                WHERE reports_weekly = 1 AND telegram_id IS NOT NULL
                ORDER BY RANDOM()
            """)
            rows = await cursor.fetchall()
        
        total_users = len(rows)
        logger.info(f"[REPORT] Haftalik hisobot: {total_users} ta foydalanuvchi")
        
        for i, row in enumerate(rows):
            telegram_id = row[0] if isinstance(row, tuple) else row["telegram_id"]
            
            try:
                success = await send_scheduled_report(context, telegram_id, "weekly")
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"[REPORT] Weekly error for {telegram_id}: {e}")
                failed_count += 1
            
            # Delay: rasmli hisobot uchun 3 soniya
            if i < total_users - 1:
                await asyncio.sleep(REPORT_DELAY_SECONDS)
            
            # Har 10 ta userdan keyin qo'shimcha kutish
            if (i + 1) % REPORT_BATCH_SIZE == 0:
                logger.info(f"[REPORT] Haftalik batch {(i+1)//REPORT_BATCH_SIZE}: {sent_count} yuborildi")
                await asyncio.sleep(REPORT_BATCH_DELAY)
        
        logger.info(f"[REPORT] Haftalik hisobotlar: {sent_count} yuborildi, {failed_count} xatolik")
        
    except Exception as e:
        logger.error(f"[REPORT] Haftalik hisobotlar xatolik: {e}")
    
    return sent_count


async def send_monthly_reports(context) -> int:
    """
    Barcha foydalanuvchilarga oylik hisobot yuborish (BATCH MODE)
    Oylik = to'liq rasm, eng sekin yuboriladi
    22:00gacha yetib borishi kerak
    """
    import asyncio
    from app.database import get_database
    
    db = await get_database()
    sent_count = 0
    failed_count = 0
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT telegram_id FROM users 
                    WHERE reports_monthly = true AND telegram_id IS NOT NULL
                    ORDER BY RANDOM()
                """)
        else:
            cursor = await db._connection.execute("""
                SELECT telegram_id FROM users 
                WHERE reports_monthly = 1 AND telegram_id IS NOT NULL
                ORDER BY RANDOM()
            """)
            rows = await cursor.fetchall()
        
        total_users = len(rows)
        logger.info(f"[REPORT] Oylik hisobot: {total_users} ta foydalanuvchi")
        
        # Oylik hisobot uchun delay ni hisoblash
        # Masalan 100 user bo'lsa, 3 soat ichida yuborish kerak (19:00-22:00)
        # 3 soat = 10800 soniya, 100 user = har 108 soniyada 1 ta
        # Lekin minimum 5 soniya, maximum 60 soniya
        if total_users > 0:
            available_time = 3 * 60 * 60  # 3 soat (soniyada)
            calculated_delay = available_time / total_users
            monthly_delay = max(5, min(60, calculated_delay))  # 5-60 soniya orasida
        else:
            monthly_delay = 10
        
        logger.info(f"[REPORT] Oylik delay: {monthly_delay:.1f} soniya/user")
        
        for i, row in enumerate(rows):
            telegram_id = row[0] if isinstance(row, tuple) else row["telegram_id"]
            
            try:
                success = await send_scheduled_report(context, telegram_id, "monthly")
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"[REPORT] Monthly error for {telegram_id}: {e}")
                failed_count += 1
            
            # Dinamik delay
            if i < total_users - 1:
                await asyncio.sleep(monthly_delay)
            
            # Progress log har 20 ta userda
            if (i + 1) % 20 == 0:
                progress = ((i + 1) / total_users) * 100
                logger.info(f"[REPORT] Oylik progress: {progress:.1f}% ({sent_count} yuborildi)")
        
        logger.info(f"[REPORT] Oylik hisobotlar: {sent_count} yuborildi, {failed_count} xatolik")
        
    except Exception as e:
        logger.error(f"[REPORT] Oylik hisobotlar xatolik: {e}")
    
    return sent_count