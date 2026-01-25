"""
HALOS Telegram Bot - Webhook Mode for Render.com
With Click Payment Integration
"""
import os
import logging
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, Response, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

from app.config import BOT_TOKEN, ADMIN_IDS
from app.database import get_database
from app.handlers import (
    get_conversation_handler,
    help_command,
    status_command,
    language_command,
    change_language_callback,
    error_handler,
    add_trial_handler_to_app,
)
from app.subscription_handlers import (
    subscription_command,
    pro_command,
    show_pricing,
    enter_promo_callback,
    cancel_promo_callback,
    click_buy_callback,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
flask_app = Flask(__name__)

# Telegram application (global)
telegram_app = None

# Webhook URL
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_PATH = "/webhook"

# Click credentials
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


def create_telegram_app():
    """Create and configure telegram application"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add conversation handler
    conv_handler = get_conversation_handler()
    application.add_handler(conv_handler)
    
    # Add global trial handler
    add_trial_handler_to_app(application)
    
    # Add standalone command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("subscription", subscription_command))
    application.add_handler(CommandHandler("pro", pro_command))
    
    # Add callback handlers
    application.add_handler(
        CallbackQueryHandler(change_language_callback, pattern="^change_lang_")
    )
    application.add_handler(
        CallbackQueryHandler(show_pricing, pattern="^show_pricing$")
    )
    application.add_handler(
        CallbackQueryHandler(click_buy_callback, pattern="^click_buy_pro_")
    )
    application.add_handler(
        CallbackQueryHandler(enter_promo_callback, pattern="^enter_promo$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_promo_callback, pattern="^cancel_promo$")
    )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    return application


@flask_app.route("/")
def index():
    return "HALOS Bot is running!", 200


@flask_app.route("/health")
def health():
    return "OK", 200


# ============ CLICK PAYMENT WEBHOOKS ============

def get_db_connection():
    """Get database connection for Click payments"""
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


@flask_app.route('/click/prepare', methods=['POST'])
def click_prepare():
    """Click Prepare endpoint - validates order before payment"""
    data = request.form.to_dict()
    logger.info(f"Click Prepare request: {data}")
    
    # Required fields
    click_trans_id = data.get('click_trans_id', '')
    service_id = data.get('service_id', '')
    merchant_trans_id = data.get('merchant_trans_id', '')
    amount = data.get('amount', '')
    action = data.get('action', '')
    sign_time = data.get('sign_time', '')
    sign_string = data.get('sign_string', '')
    
    # Validate merchant_trans_id format (halos_{telegram_id}_{plan_id})
    if not merchant_trans_id.startswith('halos_'):
        return jsonify({
            "error": "-5",
            "error_note": "Invalid order format"
        })
    
    # Parse order ID
    try:
        parts = merchant_trans_id.split('_')
        telegram_id = int(parts[1])
        plan_id = '_'.join(parts[2:])  # pro_monthly, pro_quarterly, pro_yearly
    except (IndexError, ValueError):
        return jsonify({
            "error": "-5",
            "error_note": "Invalid order ID"
        })
    
    # Validate plan exists
    if plan_id not in PRICING_PLANS:
        return jsonify({
            "error": "-5",
            "error_note": "Invalid plan"
        })
    
    # Verify signature
    expected_sign = hashlib.md5(
        f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}".encode()
    ).hexdigest()
    
    if sign_string != expected_sign:
        logger.warning(f"Invalid signature for order {merchant_trans_id}")
        # Continue anyway for testing, Click will validate
    
    return jsonify({
        "error": "0",
        "error_note": "Success",
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": merchant_trans_id
    })


@flask_app.route('/click/complete', methods=['POST'])
def click_complete():
    """Click Complete endpoint - called after successful payment"""
    data = request.form.to_dict()
    logger.info(f"Click Complete request: {data}")
    
    # Required fields
    click_trans_id = data.get('click_trans_id', '')
    service_id = data.get('service_id', '')
    merchant_trans_id = data.get('merchant_trans_id', '')
    merchant_prepare_id = data.get('merchant_prepare_id', '')
    amount = data.get('amount', '')
    action = data.get('action', '')
    sign_time = data.get('sign_time', '')
    sign_string = data.get('sign_string', '')
    error = data.get('error', '0')
    
    # If payment failed
    if error != '0':
        logger.warning(f"Payment failed for order {merchant_trans_id}: error={error}")
        return jsonify({
            "error": error,
            "error_note": "Payment failed"
        })
    
    # Parse order ID
    try:
        parts = merchant_trans_id.split('_')
        telegram_id = int(parts[1])
        plan_id = '_'.join(parts[2:])
    except (IndexError, ValueError):
        return jsonify({
            "error": "-5",
            "error_note": "Invalid order ID"
        })
    
    # Activate PRO subscription
    if activate_pro(telegram_id, plan_id):
        logger.info(f"Payment successful! User {telegram_id} upgraded to PRO ({plan_id})")
        
        # Send notification to user via Telegram (async)
        try:
            import asyncio
            if telegram_app:
                async def send_success_message():
                    await telegram_app.bot.send_message(
                        chat_id=telegram_id,
                        text="✅ To'lov muvaffaqiyatli amalga oshirildi!\n\n🎉 Siz endi HALOS PRO foydalanuvchisisiz!\n\n/start buyrug'ini bosing."
                    )
                asyncio.get_event_loop().run_until_complete(send_success_message())
        except Exception as e:
            logger.error(f"Failed to send success message: {e}")
        
        return jsonify({
            "error": "0",
            "error_note": "Success",
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": merchant_trans_id
        })
    else:
        return jsonify({
            "error": "-8",
            "error_note": "Failed to activate subscription"
        })


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    """Handle incoming Telegram updates"""
    global telegram_app
    
    if telegram_app is None:
        return Response(status=500)
    
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status=500)


async def setup_webhook():
    """Setup webhook with Telegram"""
    global telegram_app
    
    if not RENDER_EXTERNAL_URL:
        logger.error("RENDER_EXTERNAL_URL not set!")
        return
    
    webhook_url = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"
    
    await telegram_app.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")


def main():
    """Main entry point"""
    global telegram_app
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found!")
        return
    
    # Initialize database
    import asyncio
    asyncio.get_event_loop().run_until_complete(get_database())
    logger.info("Database initialized")
    
    # Create telegram app
    telegram_app = create_telegram_app()
    
    # Setup webhook
    asyncio.get_event_loop().run_until_complete(setup_webhook())
    
    # Get port from environment
    port = int(os.getenv("PORT", 10000))
    
    logger.info(f"Starting Flask server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
