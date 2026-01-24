"""
SOLVO Telegram Bot
Main entry point
"""
import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN
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
    p2p_buy_callback,
    enter_promo_callback,
    cancel_promo_callback,
)
from app.p2p_payment import (
    p2p_confirm_callback,
    p2p_cancel_callback,
    p2p_check_callback,
    manual_confirm_payment,
    process_card_xabar_notification,
    list_pending_payments,
    admin_help,
    start_payment_checker,
    stop_payment_checker,
    payme_setup_command,
    payme_status_command,
)
from app.config import ADMIN_IDS

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initialize database after application starts"""
    logger.info("Initializing database...")
    await get_database()
    logger.info("Database initialized successfully")
    
    # Start MyUzcard payment checker (background task)
    from app.myuzcard_payment import check_myuzcard_payments
    async def myuzcard_checker():
        while True:
            try:
                await check_myuzcard_payments()
            except Exception as e:
                logger.error(f"MyUzcard checker error: {e}")
            await asyncio.sleep(15)  # check every 15 seconds
    application.create_task(myuzcard_checker())


async def post_shutdown(application: Application) -> None:
    """Cleanup on shutdown"""
    # Stop payment checker
    await stop_payment_checker()
    
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
    
    # MyUzcard Payment handlers
    from app.subscription_handlers import myuzcard_buy_callback
    application.add_handler(
        CallbackQueryHandler(myuzcard_buy_callback, pattern="^myuzcard_buy_pro_")
    )
    # Promo code handlers
    application.add_handler(
        CallbackQueryHandler(enter_promo_callback, pattern="^enter_promo$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_promo_callback, pattern="^cancel_promo$")
    )
    
    # Admin command to manually confirm payment
    application.add_handler(CommandHandler("confirm_payment", manual_confirm_payment))
    
    # Admin command to list pending payments
    application.add_handler(CommandHandler("pending_payments", list_pending_payments))
    
    # Admin help command
    application.add_handler(CommandHandler("admin", admin_help))
    
    # Payme API commands
    application.add_handler(CommandHandler("payme_setup", payme_setup_command))
    application.add_handler(CommandHandler("payme_status", payme_status_command))
    
    # Handler for @CardXabarBot notifications (forwarded messages from admin)
    async def handle_card_xabar(update, context):
        """Process forwarded messages from CardXabarBot or any payment notification"""
        if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
            return
        
        if update.message and update.message.text:
            text = update.message.text.lower()
            
            # Check if message contains payment-related keywords
            payment_keywords = ["kirim", "tushdi", "o'tkazildi", "5614", "1731", 
                               "sum", "сум", "uzs", "получен", "поступ", "credited", "пополнение"]
            
            if any(keyword in text for keyword in payment_keywords):
                await process_card_xabar_notification(update, context)
                return
        
        # Also handle forwarded messages from any source
        if update.message and update.message.forward_date:
            await process_card_xabar_notification(update, context)
    
    # Add handler for admin messages (forwarded or direct with payment info)
    for admin_id in ADMIN_IDS:
        application.add_handler(
            MessageHandler(
                (filters.FORWARDED | filters.TEXT) & filters.User(admin_id) & ~filters.COMMAND,
                handle_card_xabar
            )
        )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
