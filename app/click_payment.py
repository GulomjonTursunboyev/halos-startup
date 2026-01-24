import logging
import requests

logger = logging.getLogger(__name__)


# Click to'lov ma'lumotlari
CLICK_MERCHANT_ID = "18870"  # Sizning Service ID
CLICK_MERCHANT_USER_ID = "18870"  # Odatda Service ID bilan bir xil
CLICK_SECRET_KEY = "wgqetRCPLPQV2oYd1I"
CLICK_API_URL = "https://my.click.uz/services/pay"

# Webhook URL-lar (botga to'lov statusini tekshirish uchun)
CLICK_PREPARE_URL = "https://YOUR_DOMAIN/click/prepare"   # Bu URL ni Click kabinetida ko'rsating
CLICK_COMPLETE_URL = "https://YOUR_DOMAIN/click/complete" # Bu URL ni Click kabinetida ko'rsating

# Click payment link generator (for inline/mini app)
def generate_click_payment_url(amount, order_id, return_url, description="SOLVO PRO"):
    params = {
        "service_id": CLICK_MERCHANT_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": amount,
        "transaction_param": order_id,
        "return_url": return_url,
        "merchant_trans_id": order_id,
        "merchant_trans_note": description,
    }
    # Imzo va boshqa parametrlar kerak bo'lsa, shu yerda qo'shing
    from urllib.parse import urlencode
    return f"{CLICK_API_URL}?{urlencode(params)}"
