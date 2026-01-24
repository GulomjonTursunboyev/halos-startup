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
    WEEKLY = 7
    MONTHLY = 30
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
    is_recommended: bool = False


# ==================== PRICING CONFIGURATION ====================

PRICING_PLANS: Dict[str, PricingPlan] = {
    "pro_weekly": PricingPlan(
        id="pro_weekly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.WEEKLY,
        price_uzs=4990,
        description_uz="SOLVO PRO - 1 haftalik",
        description_ru="SOLVO PRO - 1 неделя",
        is_recommended=False,
    ),
    "pro_monthly": PricingPlan(
        id="pro_monthly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.MONTHLY,
        price_uzs=14990,
        description_uz="SOLVO PRO - 1 oylik",
        description_ru="SOLVO PRO - 1 месяц",
        is_recommended=True,
    ),
    "pro_yearly": PricingPlan(
        id="pro_yearly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.YEARLY,
        price_uzs=119990,  # 33% discount
        description_uz="SOLVO PRO - 1 yillik (33% tejash)",
        description_ru="SOLVO PRO - 1 год (скидка 33%)",
        is_recommended=False,
    ),
}



# ==================== FEATURE LIMITS ====================

FEATURE_LIMITS = {
    SubscriptionTier.FREE: {
        "calculations_per_day": 0,  # No free calculations - must be PRO
        "can_use_bot": False,       # Cannot use bot at all without subscription
        "katm_analysis": False,
        "card_import": False,
        "ai_advice": False,
        "pdf_reports": False,
        "priority_support": False,
    },
    SubscriptionTier.PRO: {
        "calculations_per_day": -1,  # Unlimited
        "can_use_bot": True,         # Full bot access
        "katm_analysis": True,
        "card_import": True,
        "ai_advice": True,
        "pdf_reports": True,
        "priority_support": True,
    },
}


# ==================== PROMO CODES ====================

PROMO_CODES = {
    "SOLVOWEEK": {
        "type": "free_days",
        "value": 7,  # 7 days free (1 week PRO)
        "max_uses": -1,  # Unlimited
        "current_uses": 0,
        "expires": "2027-12-31",
    },
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
    "FREEWEEK": {
        "type": "free_days",
        "value": 7,  # 7 days free (100% 1 week)
        "max_uses": -1,  # Unlimited
        "current_uses": 0,
        "expires": "2027-12-31",
    },
    "SOLVO100": {
        "type": "free_days",
        "value": 7,  # 7 days free (100% 1 week)
        "max_uses": 500,
        "current_uses": 0,
        "expires": "2027-12-31",
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
