"""
SOLVO Telegram Bot
Main entry point - Click Payment Integration
"""
import os
import asyncio
import logging
import aiohttp
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN, ADMIN_IDS
from app.database import get_database, close_database
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

# Webhook URL for keep-alive ping
WEBHOOK_URL = os.getenv("WEBHOOK_BASE_URL", "https://solvo-click.onrender.com")


async def keep_alive_ping():
    """Ping webhook service every 10 minutes to prevent Render sleep"""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{WEBHOOK_URL}/health", timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("Keep-alive ping successful")
                    else:
                        logger.warning(f"Keep-alive ping status: {resp.status}")
        except Exception as e:
            logger.error(f"Keep-alive ping failed: {e}")
        
        # Wait 10 minutes before next ping
        await asyncio.sleep(600)


async def post_init(application: Application) -> None:
    """Initialize database after application starts"""
    logger.info("Initializing database...")
    await get_database()
    logger.info("Database initialized successfully")
    
    # Start keep-alive ping task
    application.create_task(keep_alive_ping())
    logger.info("Keep-alive ping task started")


async def post_shutdown(application: Application) -> None:
    """Cleanup on shutdown"""
    logger.info("Closing database connection...")
    await close_database()
    logger.info("Shutdown complete")


def main() -> None:
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with BOT_TOKEN=your_token")
        return
    
    logger.info("Starting SOLVO Bot...")
    
    # Create application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
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
    
    # Add callback handlers for language change
    application.add_handler(
        CallbackQueryHandler(change_language_callback, pattern="^change_lang_")
    )
    
    # Add subscription/payment handlers
    application.add_handler(
        CallbackQueryHandler(show_pricing, pattern="^show_pricing$")
    )
    
    # Click Payment handlers
    application.add_handler(
        CallbackQueryHandler(click_buy_callback, pattern="^click_buy_pro_")
    )
    
    # Promo code handlers
    application.add_handler(
        CallbackQueryHandler(enter_promo_callback, pattern="^enter_promo$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_promo_callback, pattern="^cancel_promo$")
    )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
