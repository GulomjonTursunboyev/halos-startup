"""
Atmos Payment API Integration for HALOS
Handles card binding, confirmation, and recurring payments securely via Atmos in the app.
"""
import os
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Atmos API Settings (To be configured in the server)
ATMOS_API_URL = os.getenv("ATMOS_API_URL", "https://partner.atmos.uz/merchant")
ATMOS_STORE_ID = os.getenv("ATMOS_STORE_ID", "")
ATMOS_TOKEN = os.getenv("ATMOS_TOKEN", "")

# In test mode or when Atmos is unavailable during dev we can mock responses
MOCK_ATMOS = os.getenv("MOCK_ATMOS", "True").lower() == "true"

def _get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {ATMOS_TOKEN}",
        "Content-Type": "application/json"
    }

async def bind_card_init(card_number: str, expire_date: str) -> Dict[str, Any]:
    """
    Initialize card binding. Returns transaction_id to be used in confirmation.
    """
    if MOCK_ATMOS:
        import uuid
        logger.info(f"MOCK BIND INIT: {card_number} (exp {expire_date})")
        return {
            "success": True,
            "transaction_id": str(uuid.uuid4()),
            "phone_mask": "+998 ** *** ** 88"
        }

    url = f"{ATMOS_API_URL}/bind-card/init"
    payload = {
        "card_number": card_number.replace(" ", ""),
        "expiry": expire_date.replace(" ", "")
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=_get_headers())
            data = response.json()
            
            if response.status_code == 200 and data.get("result"):
                return {
                    "success": True,
                    "transaction_id": data["result"].get("transaction_id"),
                    "phone_mask": data["result"].get("phone")
                }
            else:
                logger.error(f"Atmos bind init error: {data}")
                return {
                    "success": False,
                    "error": data.get("message", "API Error")
                }
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {"success": False, "error": str(e)}

async def bind_card_confirm(transaction_id: str, otp: str) -> Dict[str, Any]:
    """
    Confirm binding with OTP SMS code. Returns bound card token.
    """
    if MOCK_ATMOS:
        import uuid
        logger.info(f"MOCK BIND CONFIRM: txn={transaction_id}, otp={otp}")
        if otp == "000000": # Specific test failure code
            return {"success": False, "error": "Invalid OTP"}
            
        return {
            "success": True,
            "token": f"atmos_mock_token_{uuid.uuid4()}",
            "card_mask": "8600 **** **** 1234"
        }

    url = f"{ATMOS_API_URL}/bind-card/confirm"
    payload = {
        "transaction_id": transaction_id,
        "otp": otp
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=_get_headers())
            data = response.json()
            
            if response.status_code == 200 and data.get("result"):
                return {
                    "success": True,
                    "token": data["result"].get("token"),
                    "card_mask": data["result"].get("card_number")
                }
            else:
                logger.error(f"Atmos bind confirm error: {data}")
                return {
                    "success": False,
                    "error": data.get("message", "Incorrect OTP")
                }
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {"success": False, "error": str(e)}

async def pay_with_token(account_id: str, amount: int, token: str) -> Dict[str, Any]:
    """
    Charge bounded card without OTP (auto payment).
    """
    if MOCK_ATMOS:
        import uuid
        logger.info(f"MOCK PAY: amt={amount}, acc={account_id}, token={token}")
        return {
            "success": True,
            "payment_id": f"atmos_pay_{uuid.uuid4().hex[:8]}"
        }

    url = f"{ATMOS_API_URL}/pay"
    payload = {
        "store_id": ATMOS_STORE_ID,
        "account": str(account_id),
        "amount": amount * 100, # Atmos takes tiyins if specified
        "token": token
    }
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=_get_headers())
            data = response.json()
            
            # Depending on Atmos documentation, success logic might vary.
            if response.status_code == 200 and data.get("result"):
                return {
                    "success": True,
                    "payment_id": data["result"].get("transaction_id")
                }
            else:
                logger.error(f"Atmos payment error: {data}")
                return {
                    "success": False,
                    "error": data.get("message", "Payment failed")
                }
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {"success": False, "error": str(e)}
