"""
SOLVO Telegram Bot - Webhook Mode for Render.com
"""
import os
import logging
from flask import Flask, request, Response
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
    return "SOLVO Bot is running!", 200


@flask_app.route("/health")
def health():
    return "OK", 200


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
