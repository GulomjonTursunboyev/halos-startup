import os
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Click to'lov ma'lumotlari (LIVE environment)
# Format: MERCHANT_USER_ID:LIVE:SERVICE_ID_SECRET_KEY
# 333605228:LIVE:13464_31ACF1A3C571667379481B13BEDCCA774AEBA199
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "333605228")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "13464")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "13464")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "31ACF1A3C571667379481B13BEDCCA774AEBA199")
CLICK_API_URL = "https://my.click.uz/services/pay"

# Webhook URL (Render serverda ishlaganda - avtomatik o'rnatiladi)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://solvo-bot.onrender.com")

def generate_click_payment_url(amount: int, order_id: str, return_url: str, description: str = "SOLVO PRO") -> str:
    """
    Generate Click payment URL for inline payment
    
    Args:
        amount: Payment amount in UZS
        order_id: Unique order identifier (format: solvo_{telegram_id}_{plan_id})
        return_url: URL to redirect after payment
        description: Payment description
    
    Returns:
        Click payment URL
    """
    params = {
        "service_id": CLICK_SERVICE_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": amount,
        "transaction_param": order_id,
        "return_url": return_url,
        "merchant_trans_id": order_id,
    }
    
    url = f"{CLICK_API_URL}?{urlencode(params)}"
    logger.info(f"Generated Click payment URL for order {order_id}, amount: {amount}")
    return url
