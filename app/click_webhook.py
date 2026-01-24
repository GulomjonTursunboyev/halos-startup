import os
from flask import Flask, request, jsonify
import hmac
import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Click credentials (LIVE environment)
# Format: MERCHANT_USER_ID:LIVE:SERVICE_ID_SECRET_KEY
# 333605228:LIVE:13464_31ACF1A3C571667379481B13BEDCCA774AEBA199
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "333605228")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "13464")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "31ACF1A3C571667379481B13BEDCCA774AEBA199")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/solvo.db")

# Pricing plans
PRICING_PLANS = {
    "pro_monthly": {"days": 30, "price": 15000},
    "pro_quarterly": {"days": 90, "price": 40500},
    "pro_yearly": {"days": 365, "price": 135000},
}

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def activate_pro(telegram_id: int, plan_id: str):
    """Activate PRO subscription for user"""
    plan = PRICING_PLANS.get(plan_id)
    if not plan:
        logger.error(f"Unknown plan: {plan_id}")
        return False
    
    expires_at = datetime.now() + timedelta(days=plan["days"])
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'pro', 
                subscription_expires = ?, 
                subscription_plan = ?, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE telegram_id = ?
        """, (expires_at.isoformat(), plan_id, telegram_id))
        conn.commit()
        conn.close()
        logger.info(f"PRO activated for user {telegram_id}, plan: {plan_id}, expires: {expires_at}")
        return True
    except Exception as e:
        logger.error(f"Database error activating PRO: {e}")
        return False

# CLICK Prepare URL
@app.route('/click/prepare', methods=['POST'])
def click_prepare():
    """Click Prepare endpoint - validates order before payment"""
    data = request.form.to_dict()
    logger.info(f"Click Prepare request: {data}")
    
    # Validate merchant_trans_id format
    merchant_trans_id = data.get('merchant_trans_id', '')
    if not merchant_trans_id.startswith('solvo_'):
        return jsonify({"error": "-5", "error_note": "Invalid order format"})
    
    return jsonify({"error": "0", "error_note": "Success"})

# CLICK Complete URL
@app.route('/click/complete', methods=['POST'])
def click_complete():
    """Click Complete endpoint - called after successful payment"""
    data = request.form.to_dict()
    logger.info(f"Click Complete request: {data}")
    
    # Verify signature
    sign_string = (
        f"{data.get('click_trans_id')}"
        f"{data.get('service_id')}"
        f"{CLICK_SECRET_KEY}"
        f"{data.get('merchant_trans_id')}"
        f"{data.get('amount')}"
        f"{data.get('action')}"
        f"{data.get('sign_time')}"
    )
    expected_sign = hashlib.md5(sign_string.encode()).hexdigest()
    
    if data.get('sign_string') and data.get('sign_string') != expected_sign:
        logger.warning("Invalid signature in Click Complete")
        return jsonify({"error": "-1", "error_note": "Invalid signature"})
    
    # Process successful payment
    if data.get('error') == '0':
        order_id = data.get('merchant_trans_id', '')
        try:
            # Parse order_id format: solvo_{telegram_id}_{plan_id}
            parts = order_id.split('_', 2)
            if len(parts) >= 3:
                telegram_id = int(parts[1])
                plan_id = parts[2]
                
                if activate_pro(telegram_id, plan_id):
                    logger.info(f"Successfully activated PRO for user {telegram_id}")
                else:
                    logger.error(f"Failed to activate PRO for user {telegram_id}")
        except Exception as e:
            logger.error(f"Error processing Click Complete: {e}")
    
    return jsonify({"error": "0", "error_note": "Success"})

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check for Render"""
    return jsonify({"status": "ok", "service": "solvo-click"})

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({"status": "ok", "service": "SOLVO Click Payment Webhook"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
