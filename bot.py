"""
SOLVO Telegram Bot
Main entry point - Click Payment Integration
"""
import os
import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN, ADMIN_IDS
from app.database import get_database, close_database
from app.scheduler import start_scheduler, stop_scheduler
from app.handlers import (
    get_conversation_handler,
    help_command,
    status_command,
    language_command,
    change_language_callback,
    error_handler,
    add_trial_handler_to_app,
    profile_command,
    show_profile_callback,
    edit_profile_field_callback,
    handle_profile_edit_input,
    profile_mode_callback,
    get_main_menu_keyboard,
    menu_plan_handler,
    menu_profile_handler,
    menu_subscription_handler,
    menu_language_handler,
    menu_help_handler,
)
from app.subscription_handlers import (
    subscription_command,
    pro_command,
    show_pricing_callback,
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


async def post_init(application: Application) -> None:
    """Initialize database and scheduler after application starts"""
    logger.info("Initializing database...")
    await get_database()
    logger.info("Database initialized successfully")
    
    # Start PRO care scheduler
    logger.info("Starting PRO Care Scheduler...")
    await start_scheduler(application.bot)
    logger.info("PRO Care Scheduler started")


async def post_shutdown(application: Application) -> None:
    """Cleanup on shutdown"""
    logger.info("Stopping PRO Care Scheduler...")
    await stop_scheduler()
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
    application.add_handler(CommandHandler("profile", profile_command))
    
    # Add callback handlers for language change
    application.add_handler(
        CallbackQueryHandler(change_language_callback, pattern="^change_lang_")
    )
    
    # Profile edit handlers
    application.add_handler(
        CallbackQueryHandler(show_profile_callback, pattern="^show_profile$")
    )
    application.add_handler(
        CallbackQueryHandler(edit_profile_field_callback, pattern="^edit_")
    )
    application.add_handler(
        CallbackQueryHandler(profile_mode_callback, pattern="^profile_mode_")
    )
    
    # Profile edit text input handler (must be before other message handlers)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_edit_input),
        group=1
    )
    
    # Main menu button handlers
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(� Qarzlarim|💳 Мои долги)$"), menu_plan_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(👤 Profil|👤 Профиль)$"), menu_profile_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(💎 Obuna|💎 Подписка)$"), menu_subscription_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(🌐 Til|🌐 Язык)$"), menu_language_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(❓ Yordam|❓ Помощь)$"), menu_help_handler),
        group=2
    )
    
    # Add subscription/payment handlers
    application.add_handler(
        CallbackQueryHandler(show_pricing_callback, pattern="^show_pricing$")
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
