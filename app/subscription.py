"""
HALOS Subscription & Monetization System
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
    TRIAL = "trial"  # 3 kunlik bepul sinov
    PRO = "pro"


class SubscriptionPeriod(Enum):
    """Subscription period in days"""
    TRIAL = 3       # Sinov muddati
    WEEKLY = 7
    MONTHLY = 30
    YEARLY = 365


# ==================== TRIAL CONFIGURATION ====================
# Bepul 3 kunlik PRO sinov - cheklangan limitlar bilan

TRIAL_CONFIG = {
    "duration_days": 3,           # 3 kun
    "voice_limit": 10,            # 10 ta ovozli xabar
    "max_voice_duration": 10,     # 10 soniya audio
    "all_pro_features": True,     # Barcha PRO imkoniyatlar
    "one_time_only": True,        # Faqat bir marta
}


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
        price_uzs=14990,
        description_uz="HALOS PRO - 1 haftalik",
        description_ru="HALOS PRO - 1 неделя",
        is_recommended=False,
    ),
    "pro_monthly": PricingPlan(
        id="pro_monthly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.MONTHLY,
        price_uzs=29990,
        description_uz="HALOS PRO - 1 oylik",
        description_ru="HALOS PRO - 1 месяц",
        is_recommended=True,
    ),
    "pro_yearly": PricingPlan(
        id="pro_yearly",
        tier=SubscriptionTier.PRO,
        period=SubscriptionPeriod.YEARLY,
        price_uzs=249990,  # 30% discount
        description_uz="HALOS PRO - 1 yillik (30% tejash)",
        description_ru="HALOS PRO - 1 год (скидка 30%)",
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
    SubscriptionTier.TRIAL: {
        "calculations_per_day": -1,  # Unlimited
        "can_use_bot": True,         # Full bot access
        "katm_analysis": True,
        "card_import": True,
        "ai_advice": True,
        "pdf_reports": True,
        "priority_support": False,   # No priority support in trial
        # Trial-specific limits
        "voice_limit": 10,           # 10 ta ovozli xabar
        "max_voice_duration": 10,    # 10 soniya audio
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
    "HALOSWEEK": {
        "type": "free_days",
        "value": 7,  # 7 days free (1 week PRO)
        "max_uses": -1,  # Unlimited
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
