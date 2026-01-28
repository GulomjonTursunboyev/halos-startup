"""
HALOS Self-Learning AI System
=============================
O'z-o'zidan o'rganuvchi AI tizimi

ISHLASH TARTIBI:
1. Foydalanuvchi xabar yuboradi
2. Local AI tahlil qiladi (learned patterns + keywords)
3. Agar ishonch past bo'lsa → Gemini'dan so'raydi
4. Foydalanuvchi tasdiqlasa → Pattern saqlanadi
5. Keyingi safar shu pattern uchroganida → Local AI biladi

VAQT O'TISHI BILAN:
- Ko'proq pattern o'rganadi
- Gemini'ga kamroq murojaat qiladi
- Tezroq va aniqroq ishlaydi
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
# Agar local AI ishonchi bundan past bo'lsa, Gemini'dan so'raladi
CONFIDENCE_THRESHOLD = 70


class SelfLearningAI:
    """O'z-o'zidan o'rganuvchi AI"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.keyword_weights = self._load_keyword_weights()
        
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
        
        # Default struktura
        return {
            "patterns": [],
            "keyword_scores": {},
            "category_examples": {},
            "stats": {
                "total_learned": 0,
                "gemini_requests": 0,
                "local_success": 0
            }
        }
    
    def _save_patterns(self):
        """Patternlarni saqlash"""
        try:
            # data papkasini yaratish
            os.makedirs(os.path.dirname(LEARNED_PATTERNS_FILE), exist_ok=True)
            
            with open(LEARNED_PATTERNS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=2)
            logger.info(f"[SelfLearn] Patternlar saqlandi")
        except Exception as e:
            logger.error(f"[SelfLearn] Pattern saqlashda xato: {e}")
    
    def _load_keyword_weights(self) -> Dict:
        """Kalit so'zlar va ularning og'irliklarini yuklash"""
        return self.patterns.get("keyword_scores", {})
    
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
    
    def get_stats(self) -> Dict:
        """Statistikani olish"""
        return {
            "total_patterns": len(self.patterns.get("patterns", [])),
            "total_keywords": len(self.patterns.get("keyword_scores", {})),
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
