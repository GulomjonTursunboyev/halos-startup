"""
Google Gemini AI Integration for HALOS
======================================
Tranzaksiyalarni aqlli tahlil qilish

FREE TIER LIMITS:
- 60 so'rov/minutiga
- 1500 so'rov/kuniga
- Gemini 1.5 Flash (tez va bepul)
"""

import aiohttp
import json
import logging
import os
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Gemini API konfiguratsiyasi
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Kategoriyalar (AI uchun yo'riqnoma)
EXPENSE_CATEGORIES_AI = {
    "oziq_ovqat": "Ovqat, restoran, kafe, bozor, go'sht, meva, sabzavot, non, ichimlik",
    "transport": "Taksi, avtobus, metro, benzin, yo'l kira, Yandex, Uber",
    "uy_joy": "Ijara, kvartira, uy, remont, mebel",
    "kommunal": "Gaz, suv, elektr, tok, issiqlik, internet to'lov",
    "sog'liq": "Dori, shifoxona, doktor, apteka, davolash",
    "kiyim": "Kiyim, oyoq kiyim, ko'ylak, shim, kurtka",
    "ta'lim": "Kurs, kitob, maktab, universitet, o'qish",
    "ko'ngilochar": "Kino, teatr, dam olish, sayohat, o'yin",
    "aloqa": "Telefon, mobil, internet, SIM karta",
    "kredit": "Kredit, qarz, bank to'lovi, nasiya",
    "boshqa": "Boshqa xarajatlar"
}

INCOME_CATEGORIES_AI = {
    "ish_haqi": "Maosh, oylik, ish haqi, avans, bonus",
    "biznes": "Biznes daromadi, savdo, sotish, do'kon tushumi",
    "investitsiya": "Dividend, foiz, aksiya, depozit",
    "freelance": "Frilanserlik, buyurtma, loyiha, IT ish",
    "sovg'a": "Sovg'a, hadya, tug'ilgan kun, tortiq",
    "qarz_qaytarish": "Qarz qaytarish, qarzimni berdi",
    "boshqa": "Boshqa daromadlar"
}


async def analyze_with_gemini(text: str, lang: str = "uz") -> Optional[Dict]:
    """
    Gemini AI yordamida matnni tahlil qilish
    
    Returns:
        {
            "type": "expense" | "income",
            "category": "oziq_ovqat" | "transport" | ...,
            "amount": 50000,
            "description": "non olish",
            "confidence": 0.95
        }
    """
    if not GEMINI_API_KEY:
        logger.warning("[Gemini] API key topilmadi, oddiy algoritm ishlatiladi")
        return None
    
    # Kategoriyalar ro'yxati
    expense_cats = ", ".join([f"{k}: {v}" for k, v in EXPENSE_CATEGORIES_AI.items()])
    income_cats = ", ".join([f"{k}: {v}" for k, v in INCOME_CATEGORIES_AI.items()])
    
    prompt = f"""Sen moliyaviy tranzaksiyalarni tahlil qiluvchi AI assistantisin.

Quyidagi matnni tahlil qil va JSON formatida javob ber.

MATN: "{text}"

VAZIFA:
1. Bu XARAJAT (expense) yoki DAROMAD (income) ekanini aniqla
2. Qaysi kategoriyaga tegishli
3. Summani aniqla (faqat raqam, valyutasiz)
4. Qisqa tavsif yoz

XARAJAT KATEGORIYALARI:
{expense_cats}

DAROMAD KATEGORIYALARI:
{income_cats}

QOIDALAR:
- "oldim", "sotib oldim", "to'ladim", "berdim", "sarfladim" = XARAJAT
- "sotdim", "topdim", "ishladim", "maosh", "oylik" = DAROMAD
- "pul oldim", "qarz oldim" = DAROMAD (pul keldi)
- "non oldim", "go'sht oldim" = XARAJAT (narsa oldim)

JAVOB FORMATI (faqat JSON, boshqa hech narsa yo'q):
{{"type": "expense|income", "category": "kategoriya_nomi", "amount": 12345, "description": "qisqa tavsif", "confidence": 0.95}}

MUHIM: Faqat JSON qaytaring, boshqa hech qanday matn yo'q!"""

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 256
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            
            async with session.post(url, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Javobdan textni olish
                    if "candidates" in result and result["candidates"]:
                        text_response = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        
                        # JSON ni parse qilish
                        # Markdown code block ichidan chiqarish
                        text_response = text_response.strip()
                        if text_response.startswith("```json"):
                            text_response = text_response[7:]
                        if text_response.startswith("```"):
                            text_response = text_response[3:]
                        if text_response.endswith("```"):
                            text_response = text_response[:-3]
                        text_response = text_response.strip()
                        
                        try:
                            parsed = json.loads(text_response)
                            logger.info(f"[Gemini] Muvaffaqiyat: {parsed}")
                            return parsed
                        except json.JSONDecodeError as e:
                            logger.error(f"[Gemini] JSON parse xato: {e}, response: {text_response[:200]}")
                            return None
                    
                elif response.status == 429:
                    logger.warning("[Gemini] Rate limit, oddiy algoritm ishlatiladi")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"[Gemini] API xato {response.status}: {error_text[:200]}")
                    return None
                    
    except Exception as e:
        logger.error(f"[Gemini] So'rov xatosi: {e}")
        return None


async def analyze_multiple_transactions(text: str, lang: str = "uz") -> Optional[List[Dict]]:
    """
    Bir xabarda bir nechta tranzaksiyalarni tahlil qilish
    
    Misol: "bugun 100 ming ishlab topdim, 20 mingga ovqat oldim, 10 ming taksi"
    
    Returns:
        [
            {"type": "income", "category": "ish_haqi", "amount": 100000, ...},
            {"type": "expense", "category": "oziq_ovqat", "amount": 20000, ...},
            {"type": "expense", "category": "transport", "amount": 10000, ...}
        ]
    """
    if not GEMINI_API_KEY:
        logger.warning("[Gemini] API key topilmadi")
        return None
    
    expense_cats = ", ".join([f"{k}: {v}" for k, v in EXPENSE_CATEGORIES_AI.items()])
    income_cats = ", ".join([f"{k}: {v}" for k, v in INCOME_CATEGORIES_AI.items()])
    
    prompt = f"""Sen moliyaviy tranzaksiyalarni tahlil qiluvchi AI assistantisin.

Quyidagi matnda BIR NECHTA tranzaksiya bo'lishi mumkin. Har birini alohida aniqla.

MATN: "{text}"

XARAJAT KATEGORIYALARI:
{expense_cats}

DAROMAD KATEGORIYALARI:
{income_cats}

QOIDALAR:
- Har bir summani alohida tranzaksiya sifatida ajrat
- "oldim", "to'ladim", "berdim" = XARAJAT
- "sotdim", "topdim", "ishladim", "maosh" = DAROMAD
- "pul oldim" = DAROMAD, "non oldim" = XARAJAT
- ming = 1000, million = 1000000

JAVOB FORMATI (faqat JSON array):
[{{"type": "expense|income", "category": "kategoriya", "amount": 12345, "description": "tavsif"}}]

Agar faqat 1 ta tranzaksiya bo'lsa, array ichida 1 ta element qaytaring.
MUHIM: Faqat JSON array qaytaring!"""

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "topP": 0.8,
                    "maxOutputTokens": 1024
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            
            async with session.post(url, headers=headers, json=data, timeout=15) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        text_response = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        
                        # Clean up
                        text_response = text_response.strip()
                        if text_response.startswith("```json"):
                            text_response = text_response[7:]
                        if text_response.startswith("```"):
                            text_response = text_response[3:]
                        if text_response.endswith("```"):
                            text_response = text_response[:-3]
                        text_response = text_response.strip()
                        
                        try:
                            parsed = json.loads(text_response)
                            if isinstance(parsed, list):
                                logger.info(f"[Gemini] Multi-tranzaksiya: {len(parsed)} ta topildi")
                                return parsed
                            else:
                                return [parsed]
                        except json.JSONDecodeError as e:
                            logger.error(f"[Gemini] JSON parse xato: {e}")
                            return None
                            
                elif response.status == 429:
                    logger.warning("[Gemini] Rate limit")
                    return None
                else:
                    logger.error(f"[Gemini] API xato {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"[Gemini] So'rov xatosi: {e}")
        return None


async def smart_categorize(text: str, transaction_type: str) -> Optional[str]:
    """
    Faqat kategoriyani aniqlash uchun tez so'rov
    """
    if not GEMINI_API_KEY:
        return None
    
    if transaction_type == "expense":
        cats = list(EXPENSE_CATEGORIES_AI.keys())
        cats_desc = "\n".join([f"- {k}: {v}" for k, v in EXPENSE_CATEGORIES_AI.items()])
    else:
        cats = list(INCOME_CATEGORIES_AI.keys())
        cats_desc = "\n".join([f"- {k}: {v}" for k, v in INCOME_CATEGORIES_AI.items()])
    
    prompt = f"""Quyidagi matnni eng mos kategoriyaga ajrat.

MATN: "{text}"

KATEGORIYALAR:
{cats_desc}

Faqat kategoriya nomini qaytaring (masalan: oziq_ovqat yoki transport).
Boshqa hech narsa yo'q, faqat bitta so'z!"""

    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 50
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            
            async with session.post(url, json=data, timeout=5) as response:
                if response.status == 200:
                    result = await response.json()
                    if "candidates" in result and result["candidates"]:
                        category = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "").strip().lower()
                        
                        # Kategoriya nomini tozalash
                        category = category.replace("'", "").replace('"', '').strip()
                        
                        if category in cats:
                            logger.info(f"[Gemini] Kategoriya: {category}")
                            return category
                        
                        # Partial match
                        for cat in cats:
                            if cat in category:
                                return cat
                                
    except Exception as e:
        logger.error(f"[Gemini] Kategoriya xatosi: {e}")
    
    return None


def is_gemini_available() -> bool:
    """Gemini API mavjudligini tekshirish"""
    return bool(GEMINI_API_KEY)
