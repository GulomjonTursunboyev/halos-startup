"""
HALOS Self-Learning AI System v2.0
===================================
O'z-o'zidan o'rganuvchi AI tizimi - KUCHAYTIRILGAN

YANGI XUSUSIYATLAR:
- Xatolardan xulosa chiqarish
- Multi-transaction patternlarni o'rganish
- Kontekstli o'rganish (oldingi/keyingi so'zlar)
- Ishonch darajasini dinamik boshqarish
- Tuzatishlardan chuqur o'rganish

ISHLASH TARTIBI:
1. Foydalanuvchi xabar yuboradi
2. O'rganilgan patternlarni tekshirish (yuqori ustuvorlik)
3. Local AI tahlil qiladi (learned patterns + keywords)
4. Agar ishonch past bo'lsa → Gemini'dan so'raydi
5. Foydalanuvchi tasdiqlasa yoki tuzatsa → Pattern saqlanadi
6. Keyingi safar shu pattern uchroganida → Local AI biladi

O'RGANISH TURLARI:
- confirmation_learning: Foydalanuvchi ✅ bosganda
- correction_learning: Foydalanuvchi tuzatganda (eng qimmatli!)
- multi_transaction_learning: Ko'p tranzaksiyali xabarlardan
- context_learning: So'z birikmalari (masalan: "arendaga berdim")
"""

import json
import os
import re
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# O'rganilgan patternlar fayli
LEARNED_PATTERNS_FILE = "data/learned_patterns.json"

# Ishonch darajasi chegarasi (0-100)
CONFIDENCE_THRESHOLD = 70

# Xatolardan xulosa chiqarish - KUCHLI O'RGANISH
CORRECTION_BOOST = 30  # Tuzatilgan patternlarga qo'shimcha ishonch


class SelfLearningAI:
    """O'z-o'zidan o'rganuvchi AI - KUCHAYTIRILGAN v2.0"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.keyword_weights = self._load_keyword_weights()
        self.corrections_history = self._load_corrections_history()
        self.multi_tx_patterns = self._load_multi_transaction_patterns()
        self.context_patterns = self._load_context_patterns()
        
    def _load_patterns(self) -> Dict:
        """Saqlangan patternlarni yuklash"""
        try:
            if os.path.exists(LEARNED_PATTERNS_FILE):
                with open(LEARNED_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"[SelfLearn] {len(data.get('patterns', []))} ta pattern yuklandi")
                    return data
        except Exception as e:
            logger.error(f"[SelfLearn] Pattern yuklashda xato: {e}")
        
        # Default struktura - KENGAYTIRILGAN
        return {
            "patterns": [],
            "keyword_scores": {},
            "category_examples": {},
            "corrections_history": [],  # Tuzatishlar tarixi
            "multi_tx_patterns": [],    # Ko'p tranzaksiya patternlari
            "context_patterns": [],      # Kontekstli patternlar
            "learned_mistakes": {},      # Xatolardan xulosalar
            "stats": {
                "total_learned": 0,
                "gemini_requests": 0,
                "local_success": 0,
                "corrections_learned": 0,  # Tuzatishlardan o'rganilganlar
                "multi_tx_learned": 0,     # Ko'p tranzaksiyadan o'rganilganlar
            }
        }
    
    def _save_patterns(self):
        """Patternlarni saqlash"""
        try:
            os.makedirs(os.path.dirname(LEARNED_PATTERNS_FILE), exist_ok=True)
            
            with open(LEARNED_PATTERNS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=2)
            logger.info(f"[SelfLearn] Patternlar saqlandi")
        except Exception as e:
            logger.error(f"[SelfLearn] Pattern saqlashda xato: {e}")
    
    def _load_keyword_weights(self) -> Dict:
        """Kalit so'zlar va ularning og'irliklarini yuklash"""
        return self.patterns.get("keyword_scores", {})
    
    def _load_corrections_history(self) -> List:
        """Tuzatishlar tarixini yuklash"""
        return self.patterns.get("corrections_history", [])
    
    def _load_multi_transaction_patterns(self) -> List:
        """Ko'p tranzaksiya patternlarini yuklash"""
        return self.patterns.get("multi_tx_patterns", [])
    
    def _load_context_patterns(self) -> List:
        """Kontekstli patternlarni yuklash"""
        return self.patterns.get("context_patterns", [])
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Matndan kalit so'zlarni ajratish"""
        text_lower = text.lower()
        
        # Stop words (o'tkazib yuboriladigan so'zlar)
        stop_words = {'va', 'ham', 'uchun', 'ga', 'da', 'dan', 'ni', 'ning', 
                      'bu', 'shu', 'u', 'men', 'bilan', 'keyin', 'oldin',
                      'so\'m', 'sum', 'ming', 'million', 'mln'}
        
        # So'zlarni ajratish
        words = re.findall(r'[a-zA-Zа-яА-ЯўқғҳЎҚҒҲ\']+', text_lower)
        
        # Filtr
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        
        return keywords
    
    def _find_matching_patterns(self, text: str) -> List[Dict]:
        """Matnga mos patternlarni topish"""
        text_lower = text.lower()
        keywords = set(self._extract_keywords(text))
        
        matches = []
        
        for pattern in self.patterns.get("patterns", []):
            pattern_keywords = set(pattern.get("keywords", []))
            
            # Umumiy kalit so'zlar
            common = keywords & pattern_keywords
            
            if common:
                # Match score hisoblash
                score = len(common) / max(len(pattern_keywords), 1) * 100
                
                # Asosiy so'z tekshirish (masalan: "non", "taksi")
                if pattern.get("main_keyword") in text_lower:
                    score += 30
                
                matches.append({
                    "pattern": pattern,
                    "score": min(score, 100),
                    "matched_keywords": list(common)
                })
        
        # Score bo'yicha tartiblash
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        return matches
    
    def analyze(self, text: str) -> Dict:
        """
        Matnni tahlil qilish
        
        Returns:
            {
                "type": "expense" | "income",
                "category": "oziq_ovqat",
                "amount": 50000,
                "description": "non",
                "confidence": 85,
                "source": "local" | "gemini" | "learned",
                "needs_confirmation": True/False
            }
        """
        text_lower = text.lower()
        
        # 1. O'rganilgan patternlardan qidirish
        matches = self._find_matching_patterns(text)
        
        if matches and matches[0]["score"] >= CONFIDENCE_THRESHOLD:
            best_match = matches[0]
            pattern = best_match["pattern"]
            
            logger.info(f"[SelfLearn] Pattern topildi: {pattern['main_keyword']} (score: {best_match['score']:.0f}%)")
            
            # Summani ajratish
            amount = self._extract_amount(text)
            
            self.patterns["stats"]["local_success"] = self.patterns["stats"].get("local_success", 0) + 1
            
            return {
                "type": pattern["type"],
                "category": pattern["category"],
                "amount": amount,
                "description": pattern.get("description", pattern["main_keyword"]),
                "confidence": best_match["score"],
                "source": "learned",
                "needs_confirmation": False
            }
        
        # 2. Keyword-based tahlil (boshlang'ich)
        result = self._keyword_analysis(text)
        
        if result["confidence"] >= CONFIDENCE_THRESHOLD:
            self.patterns["stats"]["local_success"] = self.patterns["stats"].get("local_success", 0) + 1
            return result
        
        # 3. Ishonch past - Gemini kerak
        result["needs_confirmation"] = True
        result["source"] = "low_confidence"
        
        return result
    
    def _keyword_analysis(self, text: str) -> Dict:
        """Kalit so'zlar asosida tahlil"""
        from app.ai_assistant import (
            detect_transaction_type, detect_category, 
            extract_amount, extract_description,
            EXPENSE_CATEGORIES, INCOME_CATEGORIES
        )
        
        # Bazaviy tahlil
        tx_type = detect_transaction_type(text)
        category = detect_category(text, tx_type)
        amount = extract_amount(text)
        description = extract_description(text, amount)
        
        # Ishonch darajasini hisoblash
        confidence = self._calculate_confidence(text, tx_type, category)
        
        # Kategoriya nomi
        if tx_type == "income":
            category_name = INCOME_CATEGORIES.get("uz", {}).get(category, "📦 Boshqa")
        else:
            category_name = EXPENSE_CATEGORIES.get("uz", {}).get(category, "📦 Boshqa")
        
        return {
            "type": tx_type,
            "category": category,
            "category_name": category_name,
            "amount": amount,
            "description": description,
            "confidence": confidence,
            "source": "local",
            "needs_confirmation": confidence < CONFIDENCE_THRESHOLD
        }
    
    def _calculate_confidence(self, text: str, tx_type: str, category: str) -> int:
        """Ishonch darajasini hisoblash"""
        text_lower = text.lower()
        confidence = 50  # Bazaviy ishonch
        
        # 1. Aniq fe'llar bo'lsa +20
        strong_expense_verbs = ["to'ladim", "berdim", "sarfladim", "sotib oldim", "harid qildim"]
        strong_income_verbs = ["sotdim", "ishladim", "topdim", "maosh", "oylik"]
        
        if tx_type == "expense" and any(v in text_lower for v in strong_expense_verbs):
            confidence += 20
        elif tx_type == "income" and any(v in text_lower for v in strong_income_verbs):
            confidence += 20
        
        # 2. Kategoriya kalit so'zlari bo'lsa +15
        category_keywords = {
            "oziq_ovqat": ["non", "ovqat", "yedim", "ichdim", "restoran", "kafe"],
            "transport": ["taksi", "avtobus", "metro", "benzin", "yol", "yo'l"],
            "uy_joy": ["ijara", "kvartira", "uy", "remont"],
            "kommunal": ["gaz", "suv", "elektr", "tok"],
            "ish_haqi": ["maosh", "oylik", "ish haqi", "ishladim"],
            "biznes": ["sotdim", "savdo", "do'kon", "foyda"],
        }
        
        if category in category_keywords:
            if any(kw in text_lower for kw in category_keywords[category]):
                confidence += 15
        
        # 3. Summa aniq bo'lsa +10
        if self._extract_amount(text):
            confidence += 10
        
        # 4. O'rganilgan keyword bo'lsa +bonus
        for keyword, data in self.keyword_weights.items():
            if keyword in text_lower:
                if data.get("category") == category:
                    confidence += data.get("weight", 5)
        
        return min(confidence, 100)
    
    def _extract_amount(self, text: str) -> Optional[int]:
        """Summani ajratish (ai_assistant dan import qilish)"""
        try:
            from app.ai_assistant import extract_amount
            return extract_amount(text)
        except:
            return None
    
    def learn_from_confirmation(self, text: str, confirmed_result: Dict) -> bool:
        """
        Foydalanuvchi tasdiqlagan natijadan o'rganish
        
        Args:
            text: Original matn
            confirmed_result: Tasdiqlangan natija {type, category, amount, description}
        """
        try:
            keywords = self._extract_keywords(text)
            
            if not keywords:
                return False
            
            # Asosiy kalit so'zni topish (eng muhim so'z)
            main_keyword = self._find_main_keyword(text, confirmed_result)
            
            # Yangi pattern yaratish
            new_pattern = {
                "id": len(self.patterns.get("patterns", [])) + 1,
                "main_keyword": main_keyword,
                "keywords": keywords,
                "type": confirmed_result["type"],
                "category": confirmed_result["category"],
                "description": confirmed_result.get("description", main_keyword),
                "examples": [text],
                "learned_at": datetime.now().isoformat(),
                "usage_count": 1
            }
            
            # Mavjud pattern bormi tekshirish
            existing = self._find_existing_pattern(main_keyword, confirmed_result["category"])
            
            if existing:
                # Mavjud patternni yangilash
                existing["examples"].append(text)
                existing["keywords"] = list(set(existing["keywords"] + keywords))
                existing["usage_count"] = existing.get("usage_count", 0) + 1
                logger.info(f"[SelfLearn] Pattern yangilandi: {main_keyword}")
            else:
                # Yangi pattern qo'shish
                if "patterns" not in self.patterns:
                    self.patterns["patterns"] = []
                self.patterns["patterns"].append(new_pattern)
                logger.info(f"[SelfLearn] Yangi pattern o'rganildi: {main_keyword} -> {confirmed_result['category']}")
            
            # Keyword weight yangilash
            self._update_keyword_weights(keywords, confirmed_result)
            
            # Statistika
            self.patterns["stats"]["total_learned"] = self.patterns["stats"].get("total_learned", 0) + 1
            
            # Saqlash
            self._save_patterns()
            
            return True
            
        except Exception as e:
            logger.error(f"[SelfLearn] O'rganishda xato: {e}")
            return False
    
    def _find_main_keyword(self, text: str, result: Dict) -> str:
        """Asosiy kalit so'zni topish"""
        text_lower = text.lower()
        
        # Kategoriyaga xos so'zlarni qidirish
        category_main_words = {
            "oziq_ovqat": ["non", "ovqat", "go'sht", "meva", "sabzavot", "restoran", "kafe", "osh", "palov", "somsa"],
            "transport": ["taksi", "avtobus", "metro", "benzin", "mashina", "yol", "yo'l"],
            "uy_joy": ["ijara", "kvartira", "uy", "remont"],
            "kommunal": ["gaz", "suv", "elektr", "tok"],
            "kiyim": ["kiyim", "ko'ylak", "shim", "oyoq kiyim"],
            "sog'liq": ["dori", "shifoxona", "doktor", "apteka"],
            "ta'lim": ["kurs", "kitob", "maktab", "o'qish"],
            "ish_haqi": ["maosh", "oylik", "ish"],
            "biznes": ["savdo", "do'kon", "sotdim"],
        }
        
        category = result.get("category", "boshqa")
        
        if category in category_main_words:
            for word in category_main_words[category]:
                if word in text_lower:
                    return word
        
        # Agar topilmasa, eng uzun so'zni qaytarish
        keywords = self._extract_keywords(text)
        if keywords:
            return max(keywords, key=len)
        
        return result.get("description", "unknown")[:20]
    
    def _find_existing_pattern(self, main_keyword: str, category: str) -> Optional[Dict]:
        """Mavjud patternni topish"""
        for pattern in self.patterns.get("patterns", []):
            if pattern.get("main_keyword") == main_keyword and pattern.get("category") == category:
                return pattern
        return None
    
    def _update_keyword_weights(self, keywords: List[str], result: Dict):
        """Keyword og'irliklarini yangilash"""
        if "keyword_scores" not in self.patterns:
            self.patterns["keyword_scores"] = {}
        
        for keyword in keywords:
            if keyword not in self.patterns["keyword_scores"]:
                self.patterns["keyword_scores"][keyword] = {
                    "category": result["category"],
                    "type": result["type"],
                    "weight": 5,
                    "count": 1
                }
            else:
                data = self.patterns["keyword_scores"][keyword]
                # Agar bir xil kategoriya bo'lsa, og'irlikni oshirish
                if data["category"] == result["category"]:
                    data["weight"] = min(data["weight"] + 2, 30)
                    data["count"] += 1
        
        self.keyword_weights = self.patterns["keyword_scores"]
    
    # ==================== YANGI: XATOLARDAN O'RGANISH ====================
    
    def learn_from_correction(self, original_text: str, wrong_result: Dict, correct_result: Dict) -> bool:
        """
        XATOLARDAN XULOSA CHIQARISH - ENG QIMMATLI O'RGANISH!
        
        Foydalanuvchi tuzatganda:
        1. Xato natijani saqlash (qayerda xato qildik?)
        2. To'g'ri natijani o'rganish (qanday bo'lishi kerak edi?)
        3. Kontekstni tahlil qilish (qaysi so'zlar chalg'itdi?)
        4. Keyingi safar uchun qoida yaratish
        
        Args:
            original_text: Asl matn
            wrong_result: AI ning xato natijasi
            correct_result: Foydalanuvchi tuzatgan to'g'ri natija
        """
        try:
            logger.info(f"[SelfLearn] XATADAN O'RGANISH: '{original_text[:50]}...'")
            logger.info(f"  XATO: type={wrong_result.get('type')}, category={wrong_result.get('category')}")
            logger.info(f"  TO'G'RI: type={correct_result.get('type')}, category={correct_result.get('category')}")
            
            keywords = self._extract_keywords(original_text)
            
            # 1. Xato tarixini saqlash (analitika uchun)
            correction_record = {
                "id": len(self.patterns.get("corrections_history", [])) + 1,
                "text": original_text,
                "wrong": {
                    "type": wrong_result.get("type"),
                    "category": wrong_result.get("category"),
                    "description": wrong_result.get("description", "")
                },
                "correct": {
                    "type": correct_result.get("type"),
                    "category": correct_result.get("category"),
                    "description": correct_result.get("description", "")
                },
                "keywords": keywords,
                "timestamp": datetime.now().isoformat()
            }
            
            if "corrections_history" not in self.patterns:
                self.patterns["corrections_history"] = []
            self.patterns["corrections_history"].append(correction_record)
            
            # 2. "learned_mistakes" ga qo'shish - xato qilgan patternlarni eslab qolish
            if "learned_mistakes" not in self.patterns:
                self.patterns["learned_mistakes"] = {}
            
            # Xato qilgan kalit so'zlarni belgilash
            mistake_key = f"{wrong_result.get('type', 'unknown')}_{wrong_result.get('category', 'unknown')}"
            if mistake_key not in self.patterns["learned_mistakes"]:
                self.patterns["learned_mistakes"][mistake_key] = {
                    "avoid_keywords": [],
                    "correct_mapping": [],
                    "count": 0
                }
            
            mistake_data = self.patterns["learned_mistakes"][mistake_key]
            mistake_data["count"] += 1
            
            # Agar type yoki category o'zgargan bo'lsa, kontekst so'zlarini saqlash
            if wrong_result.get("type") != correct_result.get("type") or \
               wrong_result.get("category") != correct_result.get("category"):
                
                # Bu so'zlar chalg'itgan - keyingi safar ehtiyot bo'lish kerak
                for kw in keywords:
                    if kw not in mistake_data["avoid_keywords"]:
                        mistake_data["avoid_keywords"].append(kw)
                
                # To'g'ri mapping
                mistake_data["correct_mapping"].append({
                    "from_type": wrong_result.get("type"),
                    "from_category": wrong_result.get("category"),
                    "to_type": correct_result.get("type"),
                    "to_category": correct_result.get("category"),
                    "context_keywords": keywords
                })
            
            # 3. To'g'ri natijadan KUCHLI pattern yaratish (CORRECTION_BOOST bilan)
            main_keyword = self._find_main_keyword(original_text, correct_result)
            
            # Kuchli pattern (tuzatilganligi uchun yuqori ustuvorlik)
            strong_pattern = {
                "id": len(self.patterns.get("patterns", [])) + 1,
                "main_keyword": main_keyword,
                "keywords": keywords,
                "type": correct_result["type"],
                "category": correct_result["category"],
                "description": correct_result.get("description", main_keyword),
                "examples": [original_text],
                "learned_at": datetime.now().isoformat(),
                "usage_count": 1,
                "from_correction": True,  # Tuzatishdan o'rganilgan - yuqori ustuvorlik!
                "priority_boost": CORRECTION_BOOST,  # +30 ishonch
                "original_wrong": {
                    "type": wrong_result.get("type"),
                    "category": wrong_result.get("category")
                }
            }
            
            # Mavjud patternni yangilash yoki yangi qo'shish
            existing = self._find_existing_pattern(main_keyword, correct_result["category"])
            
            if existing:
                existing["examples"].append(original_text)
                existing["keywords"] = list(set(existing.get("keywords", []) + keywords))
                existing["usage_count"] = existing.get("usage_count", 0) + 1
                existing["from_correction"] = True
                existing["priority_boost"] = max(existing.get("priority_boost", 0), CORRECTION_BOOST)
                logger.info(f"[SelfLearn] Mavjud pattern kuchaytirildi: {main_keyword}")
            else:
                if "patterns" not in self.patterns:
                    self.patterns["patterns"] = []
                self.patterns["patterns"].append(strong_pattern)
                logger.info(f"[SelfLearn] Yangi KUCHLI pattern yaratildi: {main_keyword} -> {correct_result['category']}")
            
            # 4. Kontekstli pattern yaratish
            self._learn_context_pattern(original_text, correct_result)
            
            # 5. Keyword og'irliklarini TO'G'RI kategoriya uchun yangilash
            self._update_keyword_weights(keywords, correct_result)
            
            # 6. Statistika
            self.patterns["stats"]["corrections_learned"] = self.patterns["stats"].get("corrections_learned", 0) + 1
            
            # Saqlash
            self._save_patterns()
            
            logger.info(f"[SelfLearn] Xatadan muvaffaqiyatli o'rganildi!")
            return True
            
        except Exception as e:
            logger.error(f"[SelfLearn] Xatadan o'rganishda xato: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _learn_context_pattern(self, text: str, result: Dict):
        """
        Kontekstli pattern o'rganish - so'z birikmalari
        
        Masalan: "arendaga berdim" = ijara to'lovi (expense/uy_joy)
                 "qarzimga berdim" = qarz berish (expense/qarz_berdim)
                 "oylik tushdi" = maosh (income/ish_haqi)
        """
        text_lower = text.lower()
        
        # Kontekst patternlarini qidirish
        context_rules = [
            # (pattern, type, category, description)
            (r'arenda\w*\s+ber', 'expense', 'uy_joy', 'Ijara to\'lovi'),
            (r'ijara\w*\s+ber', 'expense', 'uy_joy', 'Ijara to\'lovi'),
            (r'qarz\w*\s+ber', 'expense', 'qarz_berdim', 'Qarzga berdim'),
            (r'qarz\w*\s+old', 'expense', 'qarz_oldim', 'Qarz oldim'),
            (r'oylik\s+tush', 'income', 'ish_haqi', 'Oylik maosh'),
            (r'maosh\s+tush', 'income', 'ish_haqi', 'Maosh'),
            (r'maosh\s+old', 'income', 'ish_haqi', 'Maosh oldim'),
            (r"go'sht\s+old", 'expense', 'oziq_ovqat', "Go'sht"),
            (r'tovuq\s+old', 'expense', 'oziq_ovqat', 'Tovuq'),
            (r'non\s+old', 'expense', 'oziq_ovqat', 'Non'),
            (r'taksi\s+ber', 'expense', 'transport', 'Taksi'),
            (r'taksi\s+qil', 'expense', 'transport', 'Taksi'),
        ]
        
        for pattern_regex, tx_type, category, description in context_rules:
            if re.search(pattern_regex, text_lower):
                # Bu kontekst patternini saqlash
                context_pattern = {
                    "regex": pattern_regex,
                    "type": tx_type,
                    "category": category,
                    "description": description,
                    "examples": [text],
                    "count": 1,
                    "learned_at": datetime.now().isoformat()
                }
                
                # Mavjudmi tekshirish
                if "context_patterns" not in self.patterns:
                    self.patterns["context_patterns"] = []
                
                existing_ctx = None
                for ctx in self.patterns["context_patterns"]:
                    if ctx.get("regex") == pattern_regex:
                        existing_ctx = ctx
                        break
                
                if existing_ctx:
                    existing_ctx["examples"].append(text)
                    existing_ctx["count"] = existing_ctx.get("count", 0) + 1
                else:
                    self.patterns["context_patterns"].append(context_pattern)
                
                logger.info(f"[SelfLearn] Kontekst pattern: '{pattern_regex}' -> {category}")
                break
    
    def learn_from_multi_transaction(self, text: str, transactions: List[Dict]) -> bool:
        """
        Ko'p tranzaksiyali xabarlardan o'rganish
        
        Masalan: "3 million tushdi, 1 million qarzga berdim, 500 ming ijaraga"
        Bu xabardan har bir tranzaksiya patternini alohida o'rganish
        """
        try:
            logger.info(f"[SelfLearn] Ko'p tranzaksiyadan o'rganish: {len(transactions)} ta")
            
            # Har bir tranzaksiyadan o'rganish
            for tx in transactions:
                # Alohida pattern yaratish
                description = tx.get("description", "")
                if description:
                    self.learn_from_confirmation(description, tx)
            
            # Ko'p tranzaksiya patternini saqlash
            multi_pattern = {
                "text_sample": text[:100],
                "transaction_count": len(transactions),
                "types": [tx.get("type") for tx in transactions],
                "categories": [tx.get("category") for tx in transactions],
                "learned_at": datetime.now().isoformat()
            }
            
            if "multi_tx_patterns" not in self.patterns:
                self.patterns["multi_tx_patterns"] = []
            self.patterns["multi_tx_patterns"].append(multi_pattern)
            
            # Statistika
            self.patterns["stats"]["multi_tx_learned"] = self.patterns["stats"].get("multi_tx_learned", 0) + 1
            
            self._save_patterns()
            return True
            
        except Exception as e:
            logger.error(f"[SelfLearn] Ko'p tranzaksiyadan o'rganishda xato: {e}")
            return False
    
    def check_learned_patterns_first(self, text: str) -> Optional[Dict]:
        """
        Avval o'rganilgan patternlarni tekshirish (USTUVORLIK BILAN)
        
        Bu funksiya parse_multiple_transactions da BIRINCHI chaqiriladi
        Agar o'rganilgan pattern topilsa, Gemini ga murojaat qilmaslik mumkin
        """
        text_lower = text.lower()
        
        # 1. Kontekst patternlarini tekshirish (eng yuqori ustuvorlik)
        for ctx_pattern in self.patterns.get("context_patterns", []):
            regex = ctx_pattern.get("regex", "")
            if regex and re.search(regex, text_lower):
                logger.info(f"[SelfLearn] Kontekst pattern topildi: {regex}")
                return {
                    "type": ctx_pattern["type"],
                    "category": ctx_pattern["category"],
                    "description": ctx_pattern.get("description", ""),
                    "confidence": 95,  # Yuqori ishonch
                    "source": "learned_context"
                }
        
        # 2. Tuzatishdan o'rganilgan patternlarni tekshirish (yuqori ustuvorlik)
        for pattern in self.patterns.get("patterns", []):
            if pattern.get("from_correction"):
                main_kw = pattern.get("main_keyword", "").lower()
                if main_kw and main_kw in text_lower:
                    boost = pattern.get("priority_boost", 0)
                    logger.info(f"[SelfLearn] Tuzatilgan pattern topildi: {main_kw} (boost: +{boost})")
                    return {
                        "type": pattern["type"],
                        "category": pattern["category"],
                        "description": pattern.get("description", main_kw),
                        "confidence": 85 + boost,
                        "source": "learned_correction"
                    }
        
        # 3. Oddiy patternlarni tekshirish
        matches = self._find_matching_patterns(text)
        if matches and matches[0]["score"] >= CONFIDENCE_THRESHOLD:
            best = matches[0]
            pattern = best["pattern"]
            return {
                "type": pattern["type"],
                "category": pattern["category"],
                "description": pattern.get("description", ""),
                "confidence": best["score"],
                "source": "learned"
            }
        
        return None
    
    def get_stats(self) -> Dict:
        """Statistikani olish - KENGAYTIRILGAN"""
        return {
            "total_patterns": len(self.patterns.get("patterns", [])),
            "total_keywords": len(self.patterns.get("keyword_scores", {})),
            "context_patterns": len(self.patterns.get("context_patterns", [])),
            "corrections_learned": self.patterns.get("stats", {}).get("corrections_learned", 0),
            "multi_tx_learned": self.patterns.get("stats", {}).get("multi_tx_learned", 0),
            "learned_mistakes_count": len(self.patterns.get("learned_mistakes", {})),
            **self.patterns.get("stats", {})
        }
    
    def increment_gemini_requests(self):
        """Gemini so'rovlari sonini oshirish"""
        self.patterns["stats"]["gemini_requests"] = self.patterns["stats"].get("gemini_requests", 0) + 1
        self._save_patterns()


# Global instance
_self_learning_ai = None

def get_self_learning_ai() -> SelfLearningAI:
    """Singleton instance olish"""
    global _self_learning_ai
    if _self_learning_ai is None:
        _self_learning_ai = SelfLearningAI()
    return _self_learning_ai
