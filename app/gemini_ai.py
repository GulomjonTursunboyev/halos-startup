"""
Google Gemini AI Integration for HALOS
======================================
Tranzaksiyalarni aqlli tahlil qilish

FREE TIER LIMITS:
- 60 so'rov/minutiga
- 1500 so'rov/kuniga
- Gemini 2.0 Flash (tez va bepul)
"""

import aiohttp
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Gemini API konfiguratsiyasi
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ==================== TIL NORMALIZATSIYASI ====================
# O'zbek tilida qo'llaniladigan chet til so'zlari va ularning tarjimalari
WORD_NORMALIZATIONS = {
    # Rus tilidan
    "arenda": "ijara",
    "arendaga": "ijaraga",
    "kvartira": "kvartira",
    "remont": "ta'mirlash",
    "zarplata": "maosh",
    "zp": "maosh",
    "pensiya": "nafaqa",
    "stipendiya": "stipendiya",
    "avans": "avans",
    "kredit": "kredit",
    "ipoteka": "ipoteka",
    "dostavka": "yetkazib berish",
    "zakaz": "buyurtma",
    "produkt": "mahsulot",
    "produkti": "mahsulotlar",
    "benzin": "benzin",
    "mashina": "mashina",
    
    # Ingliz tilidan
    "taxi": "taksi",
    "rent": "ijara",
    "food": "ovqat",
    "phone": "telefon",
    "internet": "internet",
    
    # O'zbek tilidagi variantlar (o', g', sh va hokazo)
    "go'sht": "go'sht",
    "gusht": "go'sht",
    "gosht": "go'sht",
    "go`sht": "go'sht",
    "go′sht": "go'sht",
    "tovuq": "tovuq",
    "tovuk": "tovuq",
    "to'vuk": "tovuq",
    "mol": "mol go'shti",
    "qo'y": "qo'y go'shti",
    "baliq": "baliq",
}

# O'zbek harflarini normalizatsiya qilish
CHAR_NORMALIZATIONS = {
    "o'": "o'",
    "o`": "o'",
    "o′": "o'",
    "oʻ": "o'",
    "g'": "g'",
    "g`": "g'",
    "g′": "g'",
    "gʻ": "g'",
    "sh": "sh",
    "ch": "ch",
}

def normalize_text(text: str) -> str:
    """Matnni normalizatsiya qilish - turli til va belgilarni to'g'rilash"""
    result = text.lower()
    
    # Maxsus belgilarni normalizatsiya
    for old, new in CHAR_NORMALIZATIONS.items():
        result = result.replace(old, new)
    
    # So'zlarni normalizatsiya (ixtiyoriy - description uchun)
    # for old, new in WORD_NORMALIZATIONS.items():
    #     result = re.sub(rf'\b{old}\b', new, result, flags=re.IGNORECASE)
    
    return result


def fix_spelling(text: str) -> str:
    """Imlo xatolarini tuzatish - izohlar uchun"""
    corrections = {
        # O'zbek so'zlari
        "gusht": "go'sht",
        "gosht": "go'sht", 
        "tovuk": "tovuq",
        "tuvuk": "tovuq",
        "arendaga": "ijaraga",
        "arenda": "ijara",
        "kvartiraga": "kvartirada",
        "oldm": "oldim",
        "berdm": "berdim",
        "topdm": "topdim",
        "qildm": "qildim",
        "ketdm": "ketdim",
        "keldm": "keldim",
        "yedm": "yedim",
        "ichdm": "ichdim",
        # Sonlar
        "mln": "million",
        "ming": "ming",
        "mng": "ming",
    }
    
    result = text
    for wrong, correct in corrections.items():
        result = re.sub(rf'\b{wrong}\b', correct, result, flags=re.IGNORECASE)
    
    return result


# Kategoriyalar (AI uchun yo'riqnoma) - KENGAYTIRILGAN
EXPENSE_CATEGORIES_AI = {
    "oziq_ovqat": "Ovqat, restoran, kafe, bozor, go'sht (mol, qo'y, tovuq), meva, sabzavot, non, ichimlik, tushlik, kechki ovqat, nonushta",
    "transport": "Taksi, avtobus, metro, benzin, yo'l kira, Yandex, Uber, Bolt, mashina ta'miri",
    "uy_joy": "Ijara, arenda, kvartira, uy, remont, mebel, uy-ro'zg'or buyumlari",
    "kommunal": "Gaz, suv, elektr, tok, issiqlik, internet to'lov, kommunal xizmatlar",
    "sog'liq": "Dori, shifoxona, doktor, apteka, davolash, tibbiy xizmatlar",
    "kiyim": "Kiyim, oyoq kiyim, ko'ylak, shim, kurtka, palto, ust kiyim",
    "ta'lim": "Kurs, kitob, maktab, universitet, o'qish, ta'lim to'lovlari",
    "ko'ngilochar": "Kino, teatr, dam olish, sayohat, o'yin, konsert",
    "aloqa": "Telefon, mobil, internet, SIM karta, aloqa xizmatlari",
    "kredit": "Kredit to'lovi, bank to'lovi, nasiya to'lovi, ipoteka",
    "qarz_berdim": "Qarzga berdim, qarz berdim, odam qarzga oldi, kimgadir berdim",
    "boshqa": "Boshqa xarajatlar"
}

INCOME_CATEGORIES_AI = {
    "ish_haqi": "Maosh, oylik, ish haqi, avans, bonus, zarplata, ish puli",
    "biznes": "Biznes daromadi, savdo, sotish, do'kon tushumi, foyda",
    "investitsiya": "Dividend, foiz, aksiya, depozit daromadi",
    "freelance": "Frilanserlik, buyurtma, loyiha, IT ish, zakaz",
    "sovg'a": "Sovg'a, hadya, tug'ilgan kun, tortiq, pul sovg'asi",
    "qarz_qaytarish": "Qarz qaytarish, qarzni qaytarishdi, pul qaytardi",
    "ijara_daromad": "Ijara daromadi, kvartirani ijaraga berdim, uy ijarasi",
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
    expense_cats = ", ".join([f"{k}" for k in EXPENSE_CATEGORIES_AI.keys()])
    income_cats = ", ".join([f"{k}" for k in INCOME_CATEGORIES_AI.keys()])
    
    prompt = f"""Moliyaviy tranzaksiyani tahlil qil.

MATN: "{text}"

QOIDALAR:
- "oldim" + narsa (non, go'sht, kiyim) = expense
- "oldim" + pul (pul oldim, maosh oldim) = income
- "to'ladim", "berdim", "sarfladim" = expense
- "sotdim", "topdim", "ishladim" = income
- ming = 1000, million = 1000000

EXPENSE kategoriyalari: {expense_cats}
INCOME kategoriyalari: {income_cats}

Faqat JSON qaytar:
{{"type":"expense","category":"oziq_ovqat","amount":50000,"description":"non"}}"""

    try:
        timeout = aiohttp.ClientTimeout(total=8, connect=3)  # Fast timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 150
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Javobdan textni olish
                    if "candidates" in result and result["candidates"]:
                        text_response = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        
                        # JSON ni ajratib olish
                        text_response = text_response.strip()
                        
                        # Markdown code block olib tashlash
                        if "```json" in text_response:
                            text_response = text_response.split("```json")[-1]
                        if "```" in text_response:
                            text_response = text_response.split("```")[0]
                        text_response = text_response.strip()
                        
                        # JSON objectni topish - nested bo'lmagan
                        import re
                        json_match = re.search(r'\{[^{}]+\}', text_response, re.DOTALL)
                        if json_match:
                            text_response = json_match.group()
                        
                        # Newlines olib tashlash
                        text_response = text_response.replace('\n', ' ').replace('\r', '')
                        text_response = ' '.join(text_response.split())
                        
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


async def analyze_multiple_transactions(text: str, lang: str = "uz", user_context: Dict = None) -> Optional[List[Dict]]:
    """
    Bir xabarda bir nechta tranzaksiyalarni tahlil qilish - KENGAYTIRILGAN v2.0
    
    Misol: "bugun 3 million oylik tushdi, 1 million qarzimga berdim, 
           500 ming arendaga berdim, 300 mingga go'sht oldim, 100 mingga tovuq oldim"
    
    Natija:
    [
        {"type": "income", "category": "ish_haqi", "amount": 3000000, "description": "Oylik maosh"},
        {"type": "expense", "category": "qarz_berdim", "amount": 1000000, "description": "Qarzga berdim", "needs_clarification": true, "clarification_type": "debt_recipient"},
        {"type": "expense", "category": "uy_joy", "amount": 500000, "description": "Ijara to'lovi", "is_rent_payment": true},
        {"type": "expense", "category": "oziq_ovqat", "amount": 300000, "description": "Go'sht"},
        {"type": "expense", "category": "oziq_ovqat", "amount": 100000, "description": "Tovuq", "needs_clarification": true, "clarification_type": "chicken_type"}
    ]
    """
    if not GEMINI_API_KEY:
        logger.warning("[Gemini] API key topilmadi")
        return None
    
    # Matnni normalizatsiya qilish
    normalized_text = normalize_text(text)
    
    expense_cats = "\n".join([f"- {k}: {v}" for k, v in EXPENSE_CATEGORIES_AI.items()])
    income_cats = "\n".join([f"- {k}: {v}" for k, v in INCOME_CATEGORIES_AI.items()])
    
    # Foydalanuvchi konteksti (ijara summasi va hokazo)
    context_info = ""
    if user_context:
        if user_context.get("rent_amount"):
            context_info += f"\n- Foydalanuvchi oylik ijara summasi: {user_context['rent_amount']} so'm"
        if user_context.get("loan_payment"):
            context_info += f"\n- Foydalanuvchi oylik kredit to'lovi: {user_context['loan_payment']} so'm"
    
    prompt = f"""Sen o'zbek tilida moliyaviy tranzaksiyalarni tahlil qiluvchi AI assistantisin.

MATN: "{text}"

FOYDALANUVCHI KONTEKSTI:{context_info if context_info else " (ma'lumot yo'q)"}

XARAJAT KATEGORIYALARI:
{expense_cats}

DAROMAD KATEGORIYALARI:
{income_cats}

MUHIM QOIDALAR:
1. HAR BIR SUMMA = ALOHIDA TRANZAKSIYA. Bitta gap ichida 5 ta summa bo'lsa, 5 ta tranzaksiya bo'ladi.

2. DAROMAD BELGILARI:
   - "oylik tushdi", "maosh tushdi/oldim", "ishlab topdim" = income (ish_haqi)
   - "sotdim", "pul tushdi", "biznesdan" = income
   
3. XARAJAT BELGILARI:
   - "oldim" + NARSA (go'sht, non, kiyim) = expense (oziq_ovqat yoki kiyim)
   - "berdim", "to'ladim" = expense
   - "arendaga/ijaraga berdim" = expense (uy_joy), ijara to'lovi
   - "qarzimga berdim" = expense (qarz_berdim), kimgadir qarz berish

4. ANIQLASHTIRISH KERAK BO'LGAN HOLATLAR:
   - "tovuq oldim" - bu go'shtmi yoki jonli hayvonmi? needs_clarification: true, clarification_type: "chicken_type"
   - "qarzimga berdim" - kimga berildi? needs_clarification: true, clarification_type: "debt_recipient"
   - "pul berdim" - nima uchun? needs_clarification: true, clarification_type: "payment_reason"

5. SUMMALAR:
   - "ming" = 1,000
   - "million" / "mln" = 1,000,000
   - "3 million" = 3,000,000
   - "500 ming" = 500,000

6. TIL NORMALIZATSIYASI:
   - "arenda" = "ijara" (rus tilidan)
   - "go'sht", "gusht", "gosht" = hammasi bir xil
   - "tovuq", "tovuk" = hammasi bir xil
   - O'zbek va rus so'zlari aralash bo'lishi mumkin

7. DESCRIPTION (IZOH):
   - To'g'ri imlo bilan yozing
   - Qisqa va aniq bo'lsin
   - Masalan: "Go'sht sotib olish", "Ijara to'lovi", "Oylik maosh"

8. MAXSUS FLAGLAR:
   - is_rent_payment: true - agar ijara to'lovi bo'lsa
   - is_debt_payment: true - agar qarz qaytarish/berish bo'lsa
   - needs_clarification: true - agar aniqlashtirish kerak bo'lsa

JAVOB FORMATI (faqat JSON array, hech qanday izoh yo'q):
[
  {{"type": "income", "category": "ish_haqi", "amount": 3000000, "description": "Oylik maosh"}},
  {{"type": "expense", "category": "qarz_berdim", "amount": 1000000, "description": "Qarzga berdim", "needs_clarification": true, "clarification_type": "debt_recipient"}},
  {{"type": "expense", "category": "uy_joy", "amount": 500000, "description": "Ijara to'lovi", "is_rent_payment": true}},
  {{"type": "expense", "category": "oziq_ovqat", "amount": 300000, "description": "Go'sht"}},
  {{"type": "expense", "category": "oziq_ovqat", "amount": 100000, "description": "Tovuq go'shti", "needs_clarification": true, "clarification_type": "chicken_type"}}
]

MUHIM: Faqat JSON array qaytaring, hech qanday qo'shimcha matn yo'q!"""

    logger.info(f"[Gemini Multi] analyze_multiple_transactions boshlandi: '{text[:100]}...'")
    
    try:
        timeout = aiohttp.ClientTimeout(total=12, connect=3)  # Optimized timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "topP": 0.9,
                    "maxOutputTokens": 2048
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            logger.info(f"[Gemini Multi] API so'rov yuborilmoqda...")
            
            async with session.post(url, headers=headers, json=data) as response:
                logger.info(f"[Gemini Multi] API javob: status={response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        text_response = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        logger.info(f"[Gemini Multi] Raw response: {text_response[:500]}")
                        
                        # Clean up JSON
                        text_response = text_response.strip()
                        if "```json" in text_response:
                            text_response = text_response.split("```json")[-1]
                        if "```" in text_response:
                            text_response = text_response.split("```")[0]
                        text_response = text_response.strip()
                        
                        # JSON array ni topish
                        json_match = re.search(r'\[[\s\S]*\]', text_response)
                        if json_match:
                            text_response = json_match.group()
                        
                        try:
                            parsed = json.loads(text_response)
                            if isinstance(parsed, list):
                                # Imlo tuzatish va vaqt qo'shish
                                for item in parsed:
                                    if "description" in item:
                                        item["description"] = fix_spelling(item["description"])
                                    item["created_at"] = datetime.now().isoformat()
                                
                                logger.info(f"[Gemini Multi] Muvaffaqiyat! {len(parsed)} ta tranzaksiya topildi")
                                return parsed
                            else:
                                logger.info(f"[Gemini Multi] Bitta dict qaytdi, arrayga o'girildi")
                                return [parsed]
                        except json.JSONDecodeError as e:
                            logger.error(f"[Gemini Multi] JSON parse xato: {e}, response: {text_response[:300]}")
                            return None
                    else:
                        logger.error(f"[Gemini Multi] candidates topilmadi: {result}")
                        return None
                            
                elif response.status == 429:
                    logger.warning("[Gemini Multi] Rate limit!")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"[Gemini Multi] API xato {response.status}: {error_text[:300]}")
                    logger.error(f"[Gemini] API xato {response.status}: {error_text[:200]}")
                    return None
                    
    except Exception as e:
        logger.error(f"[Gemini] So'rov xatosi: {e}")
        import traceback
        traceback.print_exc()
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
        timeout = aiohttp.ClientTimeout(total=4, connect=2)  # Fast timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 50
                }
            }
            
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            
            async with session.post(url, json=data) as response:
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
