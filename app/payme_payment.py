"""
HALOS Payme Payment Integration
Payme checkout URL generation
Documentation: https://developer.help.paycom.uz/
"""
import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Payme merchant credentials
# TEST mode - o'zgartiring production uchun
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")  # Merchant ID from Payme
PAYME_CHECKOUT_URL = "https://checkout.paycom.uz"

# Test mode flag
PAYME_TEST_MODE = os.getenv("PAYME_TEST_MODE", "true").lower() == "true"


def generate_payme_payment_url(
    amount: int,
    order_id: str,
    return_url: Optional[str] = None,
    lang: str = "uz"
) -> str:
    """
    Generate Payme checkout URL using GET method
    
    URL Format: https://checkout.paycom.uz/base64(params)
    
    Args:
        amount: Payment amount in UZS (will be converted to tiyin)
        order_id: Unique order identifier (format: halos_{telegram_id}_{plan_id})
        return_url: URL to redirect after payment (optional)
        lang: Language code (uz, ru, en)
    
    Returns:
        Payme checkout URL
    """
    # Convert UZS to tiyin (1 UZS = 100 tiyin)
    amount_tiyin = amount * 100
    
    # Build parameters string
    # Format: key=value separated by ;
    params_list = [
        f"m={PAYME_MERCHANT_ID}",
        f"ac.order_id={order_id}",
        f"a={amount_tiyin}",
        f"l={lang}",
    ]
    
    # Add return URL if provided
    if return_url:
        params_list.append(f"c={return_url}")
        params_list.append("ct=15000")  # 15 seconds wait after success
    
    # Join parameters with ;
    params_string = ";".join(params_list)
    
    # Base64 encode
    params_encoded = base64.b64encode(params_string.encode()).decode()
    
    # Build final URL
    url = f"{PAYME_CHECKOUT_URL}/{params_encoded}"
    
    logger.info(f"Generated Payme payment URL for order {order_id}, amount: {amount} UZS ({amount_tiyin} tiyin)")
    logger.debug(f"Payme URL params: {params_string}")
    
    return url


def verify_payme_signature(data: dict, signature: str) -> bool:
    """
    Verify Payme webhook signature
    
    Args:
        data: Request data from Payme
        signature: Signature from header
    
    Returns:
        True if signature is valid
    """
    # TODO: Implement signature verification when webhook is set up
    # This requires PAYME_KEY from merchant settings
    return True


def parse_payme_order_id(order_id: str) -> dict:
    """
    Parse order_id to extract telegram_id and plan
    
    Args:
        order_id: Format: halos_{telegram_id}_{plan}_{timestamp}
    
    Returns:
        Dict with telegram_id and plan
    """
    try:
        parts = order_id.split("_")
        if len(parts) >= 3 and parts[0] == "halos":
            return {
                "telegram_id": int(parts[1]),
                "plan": parts[2],
                "timestamp": parts[3] if len(parts) > 3 else None
            }
    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse order_id {order_id}: {e}")
    
    return {}


# Payme transaction states
class PaymeTransactionState:
    CREATED = 1
    COMPLETED = 2
    CANCELLED = -1
    CANCELLED_AFTER_COMPLETE = -2


def get_payme_test_card() -> str:
    """
    Get test card info for Payme sandbox testing
    
    Returns:
        Test card information string
    """
    return """
🧪 *PAYME TEST KARTA:*
━━━━━━━━━━━━━━━━━━━━
Karta raqami: `8600 0691 9540 6311`
Amal qilish: `03/99`
SMS kod: `666666`
━━━━━━━━━━━━━━━━━━━━
    """
