from flask import Flask, request, jsonify
import hmac
import hashlib
import logging
from app.click_payment import CLICK_SECRET_KEY
from app.database import get_database
from app.subscription import PRICING_PLANS
from datetime import datetime, timedelta

app = Flask(__name__)
logger = logging.getLogger(__name__)

# CLICK Prepare URL (test uchun oddiy javob)
@app.route('/click/prepare', methods=['POST'])
def click_prepare():
    # Click serverdan kelgan so'rovni tekshirish va javob qaytarish
    data = request.form.to_dict()
    # Bu yerda siz order_id va summani tekshirishingiz mumkin
    return jsonify({"error": "0", "error_note": "Success"})

# CLICK Complete URL (to'lovdan so'ng chaqiriladi)
@app.route('/click/complete', methods=['POST'])
def click_complete():
    data = request.form.to_dict()
    # Imzo (signature) ni tekshirish
    sign_string = f"{data.get('click_trans_id')}{data.get('service_id')}{CLICK_SECRET_KEY}{data.get('merchant_trans_id')}{data.get('amount')}{data.get('action')}{data.get('sign_time')}"
    sign = hmac.new(CLICK_SECRET_KEY.encode(), sign_string.encode(), hashlib.md5).hexdigest()
    if data.get('sign_string') and data.get('sign_string') != sign:
        return jsonify({"error": "-1", "error_note": "Invalid signature"})

    # To'lov muvaffaqiyatli bo'lsa, PRO ni ochamiz
    if data.get('action') == '1' and data.get('error') == '0':
        order_id = data.get('merchant_trans_id')
        # order_id format: solvo_{telegram_id}_{plan_id}
        try:
            _, telegram_id, plan_id = order_id.split('_', 2)
            telegram_id = int(telegram_id)
            plan = PRICING_PLANS.get(plan_id)
            if plan:
                expires_at = datetime.now() + timedelta(days=plan.period.value)
                db = get_database()
                db._connection.execute("""
                    UPDATE users SET subscription_tier = 'pro', subscription_expires = ?, subscription_plan = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?
                """, (expires_at.isoformat(), plan_id, telegram_id))
                db._connection.commit()
                logger.info(f"PRO activated for user {telegram_id} via Click payment.")
        except Exception as e:
            logger.error(f"Click complete error: {e}")
    return jsonify({"error": "0", "error_note": "Success"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
