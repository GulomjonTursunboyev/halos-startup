"""
HALOS Telegram Bot - Webhook Mode for Render.com
With Supabase PostgreSQL Database and Click Payment Integration
"""
import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
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
    # Smart input handlers - transaction confirmation
    menu_expense_input_handler,
    text_expense_handler,
    cancel_expense_mode_callback,
    add_more_expense_callback,
    show_expense_report_callback,
    confirm_transaction_save_callback,
    cancel_pending_transaction_callback,
    swap_pending_type_callback,
    edit_pending_transaction_callback,
    edit_single_tx_callback,
    set_category_callback,
    back_to_pending_preview_callback,
    debt_plan_free_callback,
    debt_plan_pro_callback,
    menu_mode_callback,
    menu_income_handler,
    menu_partner_income_handler,
    menu_loan_payment_handler,
    menu_total_debt_handler,
    recalculate_callback,
    menu_credit_choice_callback,
    menu_credit_file_handler,
    menu_katm_confirm_callback,
    smart_credit_input_handler,
    credit_confirm_callback,
    # AI Assistant handlers
    ai_assistant_callback,
    ai_voice_handler,
    ai_text_handler,
    ai_report_callback,
    ai_recent_callback,
    ai_budget_callback,
    # AI Correction handlers
    ai_confirm_ok_callback,
    ai_confirm_learn_callback,
    ai_correct_callback,
    ai_correct_multi_callback,
    ai_swap_type_callback,
    ai_reanalyze_callback,      # Gemini bilan qayta tahlil
    ai_change_category_callback,  # Kategoriya tanlash
    ai_new_category_callback,   # Yangi kategoriya yaratish
    ai_set_category_callback,   # Kategoriyani o'rnatish
    ai_clarify_category_callback,  # Kategoriyani aniqlashtirish (ixtiyoriy)
    ai_delete_all_callback,
    ai_delete_callback,
    ai_rewrite_callback,
    ai_edit_amount_callback,
    ai_amount_input_handler,
    ai_cancel_correct_callback,
    # AI Debt handlers
    ai_debt_list_callback,
    ai_debt_mark_returned_callback,
    ai_debt_return_callback,
    ai_debt_correct_callback,
    ai_debt_delete_callback,
    # Debt Reminder handlers
    debt_reminder_returned_callback,
    debt_reminder_snooze_callback,
)
from app.subscription_handlers import (
    subscription_command,
    pro_command,
    show_pricing_callback,
    enter_promo_callback,
    cancel_promo_callback,
    click_buy_callback,
    handle_promo_code_input,
    activate_trial_callback,
)
from app.pro_features import (
    show_pro_menu,
    pro_statistics_callback,
    pro_reminders_callback,
    pro_debt_monitor_callback,
    pro_export_excel_callback,
    pro_menu_callback,
    toggle_reminders_callback,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("PORT", 8080))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
FLY_APP_NAME = os.getenv("FLY_APP_NAME", "")
WEBHOOK_PATH = "/webhook"

# Auto-detect external URL
def get_external_url():
    if RENDER_EXTERNAL_URL:
        return RENDER_EXTERNAL_URL
    if FLY_APP_NAME:
        return f"https://{FLY_APP_NAME}.fly.dev"
    return ""

EXTERNAL_URL = get_external_url()

# Global application
application = None


async def health_handler(request):
    """Health check endpoint for Render"""
    return web.Response(text="OK", status=200)


async def index_handler(request):
    """Root endpoint"""
    return web.Response(text="HALOS Bot is running!", status=200)


async def webhook_handler(request):
    """Handle incoming Telegram updates via webhook"""
    global application
    
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return web.Response(status=500)


def setup_handlers(app: Application) -> None:
    """Setup all bot handlers"""
    # Add conversation handler
    conv_handler = get_conversation_handler()
    app.add_handler(conv_handler)
    
    # Add global trial handler
    add_trial_handler_to_app(app)
    
    # Add standalone command handlers
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("subscription", subscription_command))
    app.add_handler(CommandHandler("pro", pro_command))
    app.add_handler(CommandHandler("profile", profile_command))
    
    # Add callback handlers
    app.add_handler(
        CallbackQueryHandler(change_language_callback, pattern="^change_lang_")
    )
    app.add_handler(
        CallbackQueryHandler(show_pricing_callback, pattern="^show_pricing$")
    )
    app.add_handler(
        CallbackQueryHandler(click_buy_callback, pattern="^click_buy_pro_")
    )
    app.add_handler(
        CallbackQueryHandler(enter_promo_callback, pattern="^enter_promo$")
    )
    app.add_handler(
        CallbackQueryHandler(cancel_promo_callback, pattern="^cancel_promo$")
    )
    
    # Trial activation handler
    app.add_handler(
        CallbackQueryHandler(activate_trial_callback, pattern="^activate_trial$")
    )
    
    # Profile handlers
    app.add_handler(
        CallbackQueryHandler(show_profile_callback, pattern="^show_profile$")
    )
    app.add_handler(
        CallbackQueryHandler(edit_profile_field_callback, pattern="^edit_profile_")
    )
    app.add_handler(
        CallbackQueryHandler(profile_mode_callback, pattern="^profile_mode_")
    )
    
    # Menu handlers
    app.add_handler(
        CallbackQueryHandler(menu_plan_handler, pattern="^menu_plan$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_profile_handler, pattern="^menu_profile$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_subscription_handler, pattern="^menu_subscription$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_language_handler, pattern="^menu_language$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_help_handler, pattern="^menu_help$")
    )
    
    # Expense mode handlers
    app.add_handler(
        CallbackQueryHandler(cancel_expense_mode_callback, pattern="^cancel_expense_mode$")
    )
    app.add_handler(
        CallbackQueryHandler(add_more_expense_callback, pattern="^add_more_expense$")
    )
    app.add_handler(
        CallbackQueryHandler(show_expense_report_callback, pattern="^show_expense_report$")
    )
    
    # Debt plan callbacks
    app.add_handler(
        CallbackQueryHandler(debt_plan_free_callback, pattern="^debt_plan_free$")
    )
    app.add_handler(
        CallbackQueryHandler(debt_plan_pro_callback, pattern="^debt_plan_pro$")
    )
    
    # Mode callback
    app.add_handler(
        CallbackQueryHandler(menu_mode_callback, pattern="^menu_mode$")
    )
    
    # Smart input - transaction confirmation handlers
    app.add_handler(
        CallbackQueryHandler(confirm_transaction_save_callback, pattern="^confirm_transaction_save$")
    )
    app.add_handler(
        CallbackQueryHandler(cancel_pending_transaction_callback, pattern="^cancel_pending_transaction$")
    )
    app.add_handler(
        CallbackQueryHandler(swap_pending_type_callback, pattern="^swap_pending_type$")
    )
    app.add_handler(
        CallbackQueryHandler(edit_pending_transaction_callback, pattern="^edit_pending_transaction$")
    )
    app.add_handler(
        CallbackQueryHandler(edit_single_tx_callback, pattern="^edit_single_tx_")
    )
    app.add_handler(
        CallbackQueryHandler(set_category_callback, pattern="^set_category_")
    )
    app.add_handler(
        CallbackQueryHandler(back_to_pending_preview_callback, pattern="^back_to_pending_preview$")
    )
    
    # Income/debt handlers
    app.add_handler(
        CallbackQueryHandler(menu_income_handler, pattern="^menu_income$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_partner_income_handler, pattern="^menu_partner_income$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_loan_payment_handler, pattern="^menu_loan_payment$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_total_debt_handler, pattern="^menu_total_debt$")
    )
    app.add_handler(
        CallbackQueryHandler(recalculate_callback, pattern="^recalculate$")
    )
    
    # Credit handlers
    app.add_handler(
        CallbackQueryHandler(menu_credit_choice_callback, pattern="^menu_credit_(upload|manual|none)$")
    )
    app.add_handler(
        CallbackQueryHandler(credit_confirm_callback, pattern="^credit_confirm_(yes|no)$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_katm_confirm_callback, pattern="^menu_katm_confirm_(yes|no)$")
    )
    
    # PRO feature handlers
    app.add_handler(
        CallbackQueryHandler(pro_menu_callback, pattern="^pro_menu$")
    )
    app.add_handler(
        CallbackQueryHandler(pro_statistics_callback, pattern="^pro_statistics$")
    )
    app.add_handler(
        CallbackQueryHandler(pro_reminders_callback, pattern="^pro_reminders$")
    )
    app.add_handler(
        CallbackQueryHandler(pro_debt_monitor_callback, pattern="^pro_debt_monitor$")
    )
    app.add_handler(
        CallbackQueryHandler(pro_export_excel_callback, pattern="^pro_export_excel$")
    )
    app.add_handler(
        CallbackQueryHandler(toggle_reminders_callback, pattern="^toggle_reminders_")
    )
    
    # AI Assistant handlers
    app.add_handler(
        CallbackQueryHandler(ai_assistant_callback, pattern="^ai_assistant$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_report_callback, pattern="^ai_report$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_recent_callback, pattern="^ai_recent$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_budget_callback, pattern="^ai_budget$")
    )
    
    # AI Correction handlers
    app.add_handler(
        CallbackQueryHandler(ai_confirm_ok_callback, pattern="^ai_confirm_ok$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_confirm_learn_callback, pattern="^ai_confirm_learn$")
    )
    # MUHIM: ai_correct_multi_ OLDIN ro'yxatdan o'tishi kerak!
    app.add_handler(
        CallbackQueryHandler(ai_correct_multi_callback, pattern="^ai_correct_multi_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_correct_callback, pattern="^ai_correct_\\d+$")
    )
    # Gemini bilan qayta tahlil
    app.add_handler(
        CallbackQueryHandler(ai_reanalyze_callback, pattern="^ai_reanalyze_")
    )
    # Kategoriya o'zgartirish
    app.add_handler(
        CallbackQueryHandler(ai_change_category_callback, pattern="^ai_change_category_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_new_category_callback, pattern="^ai_new_category_")
    )
    # Kategoriyani aniqlashtirish (ixtiyoriy)
    app.add_handler(
        CallbackQueryHandler(ai_clarify_category_callback, pattern="^ai_clarify_category_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_set_category_callback, pattern="^ai_set_category_")
    )
    # MUHIM: ai_delete_all_ OLDIN ro'yxatdan o'tishi kerak!
    app.add_handler(
        CallbackQueryHandler(ai_delete_all_callback, pattern="^ai_delete_all_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_delete_callback, pattern="^ai_delete_\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_rewrite_callback, pattern="^ai_rewrite_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_edit_amount_callback, pattern="^ai_edit_amount_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_cancel_correct_callback, pattern="^ai_cancel_correct$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_swap_type_callback, pattern="^ai_swap_type_")
    )
    
    # AI Debt handlers
    app.add_handler(
        CallbackQueryHandler(ai_debt_list_callback, pattern="^ai_debt_list$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_debt_mark_returned_callback, pattern="^ai_debt_mark_returned$")
    )
    app.add_handler(
        CallbackQueryHandler(ai_debt_return_callback, pattern="^ai_debt_return_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_debt_correct_callback, pattern="^ai_debt_correct_")
    )
    app.add_handler(
        CallbackQueryHandler(ai_debt_delete_callback, pattern="^ai_debt_delete_")
    )
    
    # Debt Reminder handlers
    app.add_handler(
        CallbackQueryHandler(debt_reminder_returned_callback, pattern="^debt_reminder_returned:")
    )
    app.add_handler(
        CallbackQueryHandler(debt_reminder_snooze_callback, pattern="^debt_reminder_snooze:")
    )
    
    # PROMO CODE INPUT HANDLER - HIGHEST PRIORITY
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_promo_code_input),
        group=-1  # Highest priority - runs first
    )
    
    # Smart credit input handler - MUST be before other text handlers
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, smart_credit_input_handler),
        group=3  # Lower group number = higher priority
    )
    
    # Amount input handler for corrections
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_amount_input_handler),
        group=4
    )
    
    # Credit file handler
    app.add_handler(
        MessageHandler(filters.Document.ALL, menu_credit_file_handler),
        group=4
    )
    
    # Voice message handler for AI assistant
    app.add_handler(
        MessageHandler(filters.VOICE, ai_voice_handler),
        group=4
    )
    
    # Text message handler for AI assistant
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_text_handler),
        group=5
    )
    
    # Add error handler
    app.add_error_handler(error_handler)


async def on_startup(web_app):
    """Initialize bot on startup"""
    global application
    
    logger.info("Starting HALOS Bot (Webhook Mode)...")
    
    # Initialize database
    logger.info("Connecting to Supabase database...")
    await get_database()
    logger.info("Database connected")
    
    # Create telegram application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Setup handlers
    setup_handlers(application)
    
    # Initialize application
    await application.initialize()
    
    # Start scheduler
    logger.info("Starting PRO Care Scheduler...")
    await start_scheduler(application.bot)
    
    # Set webhook
    if EXTERNAL_URL:
        webhook_url = f"{EXTERNAL_URL}{WEBHOOK_PATH}"
        await application.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        logger.info(f"Webhook set: {webhook_url}")
    else:
        logger.warning("EXTERNAL_URL not set - webhook not configured!")
    
    # Start application
    await application.start()
    logger.info("Bot started successfully!")


async def on_shutdown(web_app):
    """Cleanup on shutdown"""
    global application
    
    logger.info("Shutting down...")
    
    if application:
        # Stop scheduler
        await stop_scheduler()
        
        # Stop application
        await application.stop()
        await application.shutdown()
    
    # Close database
    await close_database()
    
    logger.info("Shutdown complete")


def main():
    """Main entry point"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found!")
        return
    
    # Create aiohttp web app
    web_app = web.Application()
    
    # Add routes
    web_app.router.add_get("/", index_handler)
    web_app.router.add_get("/health", health_handler)
    web_app.router.add_post(WEBHOOK_PATH, webhook_handler)
    
    # Add startup/shutdown handlers
    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)
    
    logger.info(f"Starting web server on port {PORT}")
    web.run_app(web_app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
