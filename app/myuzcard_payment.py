import logging
from app.myuzcard_api import MyUzcardAPI
from app.p2p_payment import get_pending_payment, confirm_payment

logger = logging.getLogger(__name__)

MYUZCARD_LOGIN = "ilunga"
MYUZCARD_PASSWORD = "549xb%37QDdHT90O"

api = MyUzcardAPI(MYUZCARD_LOGIN, MYUZCARD_PASSWORD)

async def check_myuzcard_payments():
    """Check all pending payments via MyUzcard API and auto-confirm if found"""
    payments = await api.get_payments(status="success")
    if not payments or "data" not in payments:
        logger.warning("MyUzcard: No successful payments found")
        return
    for payment in payments["data"]:
        amount = int(float(payment.get("amount", 0)))
        comment = payment.get("comment", "")
        # Try to find pending payment by amount (and maybe comment)
        pending = await get_pending_payment_by_amount(amount)
        if pending:
            payment_id = pending["payment_id"]
            logger.info(f"MyUzcard: Found matching payment {payment_id} for amount {amount}")
            await confirm_payment(payment_id)
            # You can notify user here if needed

# Example:
# import asyncio
# asyncio.run(check_myuzcard_payments())
