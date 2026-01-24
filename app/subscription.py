"""
SOLVO Subscription & Monetization System
P2P Card-to-Card Payment Integration
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import datetime


# ==================== ENUMS ====================

class SubscriptionTier(Enum):
    """User subscription tiers"""
    FREE = "free"
    PRO = "pro"


class SubscriptionPeriod(Enum):
    """Subscription period in days"""
    MONTHLY = 30
    QUARTERLY = 90
    YEARLY = 365


# ==================== DATA CLASSES ====================

@dataclass
class PricingPlan:
    """Pricing plan details"""
    id: str
    tier: SubscriptionTier
    period: SubscriptionPeriod
    price_uzs: int  # Price in Uzbek Som
    description_uz: str
    description_ru: str


# ==================== PRICING CONFIGURATION ====================

PRICING_PLANS: Dict[str, PricingPlan] = {
    "pro_monthly": PricingPlan(
        id="pro_monthly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.MONTHLY,
        price_uzs=15000,
        description_uz="SOLVO PRO - 1 oylik obuna",
        description_ru="SOLVO PRO - подписка на 1 месяц",
    ),
    "pro_quarterly": PricingPlan(
        id="pro_quarterly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.QUARTERLY,
        price_uzs=40500,  # 10% discount
        description_uz="SOLVO PRO - 3 oylik obuna (10% chegirma)",
        description_ru="SOLVO PRO - подписка на 3 месяца (скидка 10%)",
    ),
    "pro_yearly": PricingPlan(
        id="pro_yearly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.YEARLY,
        price_uzs=135000,  # 25% discount
        description_uz="SOLVO PRO - 1 yillik obuna (25% chegirma)",
        description_ru="SOLVO PRO - подписка на 1 год (скидка 25%)",
    ),
}



# ==================== FEATURE LIMITS ====================

FEATURE_LIMITS = {
    SubscriptionTier.FREE: {
        "calculations_per_day": 0,  # No free calculations - must be PRO
        "katm_analysis": False,
        "card_import": False,
        "ai_advice": False,
        "pdf_reports": False,
        "priority_support": False,
    },
    SubscriptionTier.PRO: {
        "calculations_per_day": -1,  # Unlimited
        "katm_analysis": True,
        "card_import": True,
        "ai_advice": True,
        "pdf_reports": True,
        "priority_support": True,
    },
}


# ==================== PROMO CODES ====================

PROMO_CODES = {
    "SOLVO2024": {
        "type": "free_days",
        "value": 7,
        "max_uses": 1000,
        "current_uses": 0,
        "expires": "2027-12-31",
    },
    "LAUNCH50": {
        "type": "discount",
        "value": 50,  # 50% discount
        "max_uses": 100,
        "current_uses": 0,
        "expires": "2027-06-30",
    },
    "FRIEND20": {
        "type": "discount",
        "value": 20,  # 20% discount
        "max_uses": -1,  # Unlimited
        "current_uses": 0,
        "expires": None,
    },
}


# ==================== HELPER FUNCTIONS ====================

def validate_promo_code(code: str) -> Optional[Dict[str, Any]]:
    """Validate a promo code and return its details if valid"""
    code = code.upper().strip()
    
    if code not in PROMO_CODES:
        return None
    
    promo = PROMO_CODES[code]
    
    # Check expiration
    if promo.get("expires"):
        expires_date = datetime.strptime(promo["expires"], "%Y-%m-%d")
        if datetime.now() > expires_date:
            return None
    
    # Check max uses
    if promo.get("max_uses", -1) != -1:
        if promo.get("current_uses", 0) >= promo["max_uses"]:
            return None
    
    return {
        "code": code,
        "type": promo["type"],
        "value": promo["value"],
    }


def get_plan_by_id(plan_id: str) -> Optional[PricingPlan]:
    """Get pricing plan by ID"""
    return PRICING_PLANS.get(plan_id)
