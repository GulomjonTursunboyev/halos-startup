"""
HALOS Telegram Bot
Main entry point - Telegram Payments Integration (Click Terminal)
"""
import os
import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters,
)

from app.config import BOT_TOKEN, ADMIN_IDS, States
from app.database import get_database, close_database
from app.scheduler import start_scheduler, stop_scheduler
from app.app_login_handler import handle_app_login, app_login_confirm_callback, app_login_cancel_callback
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
    # YANGI PROFESSIONAL UX MENYU HANDLERS
    menu_balance_handler,
    menu_reports_handler,
    # Yangi soddalashtirilgan menyu handler'lari
    menu_today_handler,
    menu_debts_handler,
    # NEW: Debt dashboard callbacks
    show_katm_credits_callback,
    back_to_debts_menu_callback,
    # Legacy
    menu_plan_handler,
    menu_profile_handler,
    menu_subscription_handler,
    menu_language_handler,
    menu_help_handler,
    text_expense_handler,
    cancel_expense_mode_callback,
    add_more_expense_callback,
    show_expense_report_callback,
    # NEW: Transaction confirmation/edit handlers
    confirm_transaction_save_callback,
    cancel_pending_transaction_callback,
    swap_pending_type_callback,
    edit_pending_transaction_callback,
    edit_single_tx_callback,
    set_category_callback,
    back_to_pending_preview_callback,
    debt_plan_free_callback,
    debt_plan_pro_callback,
    # menu_mode_callback - now handled by ConversationHandler
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
    credit_show_schedule_callback,
    # AI Assistant handlers
    ai_assistant_callback,
    ai_voice_handler,
    ai_text_handler,
    ai_report_callback,
    ai_recent_callback,
    ai_budget_callback,
    ai_real_balance_callback,
    # AI Correction handlers
    ai_confirm_ok_callback,
    ai_confirm_learn_callback,  # O'rganish bilan tasdiqlash
    ai_correct_callback,
    ai_correct_multi_callback,
    ai_swap_type_callback,
    ai_reanalyze_callback,      # Gemini bilan qayta tahlil
    ai_change_category_callback,  # Kategoriya tanlash
    ai_new_category_callback,   # Yangi kategoriya yaratish
    ai_set_category_callback,   # Kategoriyani o'rnatish
    ai_clarify_category_callback,  # Kategoriyani aniqlashtirish (ixtiyoriy)
    ai_clarify_multi_callback,  # Ko'p tranzaksiya aniqlashtirish
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
    # Report handlers
    detailed_report_callback,
    report_weekly_callback,
    report_monthly_callback,
    back_to_report_callback,
    show_halos_status_callback,
    # Admin handlers
    admin_command,
    admin_callback,
    admin_broadcast_message,
    admin_activate_pro,
    admin_payments,
    # Admin user management
    admin_manage_user_start,
    admin_delete_user_start,
    admin_clear_user_tx_start,
    admin_clear_all_tx_confirm,
    admin_confirm_clear_all,
    admin_handle_input,
    admin_confirm_delete_user,
    admin_confirm_clear_tx,
    admin_give_pro_to_user,
    admin_remove_pro_from_user,
    admin_stats,
    admin_list_users,
    admin_search_user_start,
    admin_back,
    admin_close,
    admin_cancel,
    # Admin marketing handlers
    admin_marketing_stats,
    admin_marketing_period,
)
from app.subscription_handlers import (
    subscription_command,
    pro_command,
    show_pricing_callback,
    enter_promo_callback,
    cancel_promo_callback,
    click_buy_callback,
    handle_promo_code_input,
    buy_voice_pack_callback,
    cancel_voice_pack_callback,
    activate_trial_callback,
    # Voice Tier callbacks
    buy_voice_plus_callback,
    buy_voice_unlimited_callback,
    cancel_voice_tier_callback,
    # Payment method selection
    payment_method_payme_callback,
    payment_method_click_callback,
    payme_buy_callback,
)
from app.telegram_payments import (
    pre_checkout_handler,
    successful_payment_handler,
    telegram_pay_callback,
)
from app.pro_features import (
    show_pro_menu,
    pro_statistics_callback,
    pro_reminders_callback,
    pro_debt_monitor_callback,
    pro_export_excel_callback,
    pro_menu_callback,
    toggle_reminders_callback,
    # Report settings
    report_settings_callback,
    toggle_report_callback,
)
from app.ai_assistant import (
    send_daily_reports,
    send_weekly_reports,
    send_monthly_reports,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ========== SCHEDULED REPORT JOBS ==========
async def daily_report_job(context) -> None:
    """Kunlik hisobot yuborish job"""
    logger.info("рџ”” Running daily report job...")
    try:
        count = await send_daily_reports(context)
        logger.info(f"вњ… Daily reports sent to {count} users")
    except Exception as e:
        logger.error(f"вќЊ Daily report job error: {e}")


async def weekly_report_job(context) -> None:
    """Haftalik hisobot yuborish job"""
    logger.info("рџ”” Running weekly report job...")
    try:
        count = await send_weekly_reports(context)
        logger.info(f"вњ… Weekly reports sent to {count} users")
    except Exception as e:
        logger.error(f"вќЊ Weekly report job error: {e}")


async def monthly_report_job(context) -> None:
    """Oylik hisobot yuborish job"""
    logger.info("рџ”” Running monthly report job...")
    try:
        count = await send_monthly_reports(context)
        logger.info(f"вњ… Monthly reports sent to {count} users")
    except Exception as e:
        logger.error(f"вќЊ Monthly report job error: {e}")


async def post_init(application: Application) -> None:
    """Initialize database and scheduler after application starts"""
    logger.info("=" * 50)
    logger.info("POST_INIT CALLED - Initializing services...")
    logger.info("=" * 50)
    
    logger.info("Initializing database...")
    await get_database()
    logger.info("Database initialized successfully")
    
    # Start PRO care scheduler
    logger.info("Starting PRO Care Scheduler...")
    try:
        await start_scheduler(application.bot)
        logger.info("PRO Care Scheduler started successfully!")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    # ========== SCHEDULED REPORTS ==========
    # Setup JobQueue for daily/weekly/monthly reports
    job_queue = application.job_queue
    
    if job_queue is None:
        logger.warning("вљ пёЏ JobQueue is not available. Scheduled reports will not work.")
        logger.warning("Install with: pip install python-telegram-bot[job-queue]")
    else:
        from datetime import time as dt_time
        import pytz
        
        # Toshkent vaqt zonasi
        tz = pytz.timezone("Asia/Tashkent")
        
        # Kunlik hisobot - har kuni soat 21:00 da
        job_queue.run_daily(
            daily_report_job,
            time=dt_time(hour=21, minute=0, tzinfo=tz),
            name="daily_report"
        )
        logger.info("рџ“Љ Daily report job scheduled at 21:00 Tashkent time")
        
        # Haftalik hisobot - har yakshanba soat 20:00 da
        job_queue.run_daily(
            weekly_report_job,
            time=dt_time(hour=20, minute=0, tzinfo=tz),
            days=(6,),  # 6 = Sunday
            name="weekly_report"
        )
        logger.info("рџ“Љ Weekly report job scheduled on Sundays at 20:00")
        
        # Oylik hisobot - har oyning 1-sanasi soat 19:00 da
        job_queue.run_monthly(
            monthly_report_job,
            when=dt_time(hour=19, minute=0, tzinfo=tz),
            day=1,  # Har oyning 1-sanasi
            name="monthly_report"
        )
        logger.info("рџ“Љ Monthly report job scheduled on 1st of each month at 19:00")


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
    
    logger.info("Starting HALOS Bot...")
    
    # Create application with MAXIMUM SPEED settings
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)  # Allow concurrent update processing
        .connection_pool_size(64)  # Large connection pool
        .read_timeout(5)  # Fast timeout
        .write_timeout(5)
        .connect_timeout(5)
        .pool_timeout(1)  # Minimal pool wait
        .get_updates_read_timeout(5)  # Fast polling timeout
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
    
    # Admin command handler
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("activate", admin_activate_pro))
    application.add_handler(CommandHandler("payments", admin_payments))
    
    # Admin user management ConversationHandler
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_manage_user_start, pattern="^admin_manage_user$"),
            CallbackQueryHandler(admin_delete_user_start, pattern="^admin_delete_user$"),
            CallbackQueryHandler(admin_clear_user_tx_start, pattern="^admin_clear_user_tx$"),
            CallbackQueryHandler(admin_search_user_start, pattern="^admin_search_user$"),
        ],
        states={
            States.ADMIN_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handle_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_cancel),
            CallbackQueryHandler(admin_close, pattern="^admin_close$"),
        ],
        allow_reentry=True,
        name="admin_conv",
    )
    application.add_handler(admin_conv_handler)
    
    # Admin callback handlers (for other admin actions)
    application.add_handler(
        CallbackQueryHandler(admin_callback, pattern="^admin_")
    )
    
    # ==================== TELEGRAM PAYMENTS HANDLERS ====================
    # Pre-checkout query handler (MUST respond within 10 seconds)
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    
    # Successful payment handler
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )
    
    # Telegram Pay callback handler (tg_pay_{plan_id})
    application.add_handler(
        CallbackQueryHandler(telegram_pay_callback, pattern="^tg_pay_")
    )
    
    # Promo code input handler - HIGHEST PRIORITY (must be before admin broadcast)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_promo_code_input),
        group=-1  # Highest priority
    )
    
    # Admin broadcast message handler - supports text, photo, video, document
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND, 
            admin_broadcast_message
        ),
        group=0
    )
    
    # App Login callbacks for mobile app authentication
    application.add_handler(
        CallbackQueryHandler(app_login_confirm_callback, pattern=r"^app_login_confirm:")
    )
    application.add_handler(
        CallbackQueryHandler(app_login_cancel_callback, pattern=r"^app_login_cancel$")
    )
    
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
    
    # Main menu button handlers - YANGI PROFESSIONAL UX MENYU
    # 💰 Balans - Primary Action (full width)
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(💰 Balans|💰 Баланс)$"), menu_balance_handler),
        group=2
    )
    # 📊 Hisobotlar - All reports centralized
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(📊 Hisobotlar|📊 Отчёты)$"), menu_reports_handler),
        group=2
    )
    # 💳 Qarzlar - Debts dashboard
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(💳 Qarzlar|💳 Долги|💰 Qarzlar|💰 Долги)$"), menu_debts_handler),
        group=2
    )
    # 👤 Profil
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(👤 Profil|👤 Профиль)$"), menu_profile_handler),
        group=2
    )
    # 💎 PRO
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(💎 PRO)$"), menu_subscription_handler),
        group=2
    )
    # ❓ Yordam
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(❓ Yordam|❓ Помощь)$"), menu_help_handler),
        group=2
    )
    # Legacy support for old menu buttons
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(📊 Bugun|📊 Сегодня)$"), menu_today_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(📊 Hisobotlarim|📊 Мои отчёты)$"), menu_plan_handler),
        group=2
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("^(🌐 Til|🌐 Язык)$"), menu_language_handler),
        group=2
    )

    # Text expense handler (for expense_text_mode)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_expense_handler),
        group=4  # Lower priority than menu handlers
    )
    
    # Expense mode callbacks
    application.add_handler(
        CallbackQueryHandler(cancel_expense_mode_callback, pattern="^cancel_expense_mode$")
    )
    application.add_handler(
        CallbackQueryHandler(add_more_expense_callback, pattern="^add_more_expense$")
    )
    application.add_handler(
        CallbackQueryHandler(show_expense_report_callback, pattern="^show_expense_report$")
    )
    
    # Transaction confirmation/edit callbacks (SMART INPUT)
    application.add_handler(
        CallbackQueryHandler(confirm_transaction_save_callback, pattern="^confirm_transaction_save$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_pending_transaction_callback, pattern="^cancel_pending_transaction$")
    )
    application.add_handler(
        CallbackQueryHandler(swap_pending_type_callback, pattern="^swap_pending_type$")
    )
    application.add_handler(
        CallbackQueryHandler(edit_pending_transaction_callback, pattern="^edit_pending_transaction$")
    )
    application.add_handler(
        CallbackQueryHandler(edit_single_tx_callback, pattern="^edit_tx_")
    )
    application.add_handler(
        CallbackQueryHandler(set_category_callback, pattern="^set_cat_")
    )
    application.add_handler(
        CallbackQueryHandler(back_to_pending_preview_callback, pattern="^back_to_pending_preview$")
    )
    
    # NOTE: mode_solo/mode_family callbacks are now handled by ConversationHandler entry_points
    # Menu mode selection moved to handlers.py get_conversation_handler()
    
    # Menu credit history choice callbacks
    application.add_handler(
        CallbackQueryHandler(menu_credit_choice_callback, pattern="^menu_credit_(upload|manual|none)$")
    )
    
    # Credit confirmation callbacks
    application.add_handler(
        CallbackQueryHandler(credit_confirm_callback, pattern="^credit_confirm_(yes|no)$")
    )
    
    # Menu KATM confirm callbacks
    application.add_handler(
        CallbackQueryHandler(menu_katm_confirm_callback, pattern="^menu_katm_confirm_(yes|no)$")
    )
    
    # Credit schedule callback
    application.add_handler(
        CallbackQueryHandler(credit_show_schedule_callback, pattern="^credit_show_schedule$")
    )
    
    # ========== DEBT DASHBOARD CALLBACKS ==========
    application.add_handler(
        CallbackQueryHandler(show_katm_credits_callback, pattern="^show_katm_credits$")
    )
    application.add_handler(
        CallbackQueryHandler(back_to_debts_menu_callback, pattern="^back_to_debts_menu$")
    )
    
    # Menu credit file upload handler
    application.add_handler(
        MessageHandler(filters.Document.ALL, menu_credit_file_handler),
        group=3
    )
    
    # Smart credit input handler - MUST be before other text handlers
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, smart_credit_input_handler),
        group=2  # Lower group number = higher priority
    )
    
    # Menu data input handlers (lower priority)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, menu_income_handler),
        group=3
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, menu_partner_income_handler),
        group=3
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, menu_loan_payment_handler),
        group=3
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, menu_total_debt_handler),
        group=3
    )
    
    # Add subscription/payment handlers
    application.add_handler(
        CallbackQueryHandler(show_pricing_callback, pattern="^show_pricing$")
    )
    
    # Payment method selection handlers
    application.add_handler(
        CallbackQueryHandler(payment_method_payme_callback, pattern="^payment_method_payme$")
    )
    application.add_handler(
        CallbackQueryHandler(payment_method_click_callback, pattern="^payment_method_click$")
    )
    
    # Payme Payment handlers
    application.add_handler(
        CallbackQueryHandler(payme_buy_callback, pattern="^payme_buy_pro_")
    )
    
    # Click Payment handlers
    application.add_handler(
        CallbackQueryHandler(click_buy_callback, pattern="^click_buy_pro_")
    )
    
    # NOTE: Payment method selection handlers disabled - using direct Telegram Payment
    # application.add_handler(
    #     CallbackQueryHandler(pay_telegram_callback, pattern="^pay_tg_")
    # )
    # application.add_handler(
    #     CallbackQueryHandler(pay_link_callback, pattern="^pay_link_")
    # )
    
    # Promo code handlers
    application.add_handler(
        CallbackQueryHandler(enter_promo_callback, pattern="^enter_promo$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_promo_callback, pattern="^cancel_promo$")
    )
    
    # Trial activation handler
    application.add_handler(
        CallbackQueryHandler(activate_trial_callback, pattern="^activate_trial$")
    )
    
    # Voice Pack handlers
    application.add_handler(
        CallbackQueryHandler(buy_voice_pack_callback, pattern="^buy_voice_pack$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_voice_pack_callback, pattern="^cancel_voice_pack$")
    )
    
    # Voice Tier handlers (Voice+, Voice Unlimited)
    application.add_handler(
        CallbackQueryHandler(buy_voice_plus_callback, pattern="^buy_voice_plus$")
    )
    application.add_handler(
        CallbackQueryHandler(buy_voice_unlimited_callback, pattern="^buy_voice_unlimited$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_voice_tier_callback, pattern="^cancel_voice_tier$")
    )
    
    # PRO Features handlers
    application.add_handler(
        CallbackQueryHandler(pro_menu_callback, pattern="^pro_menu$")
    )
    application.add_handler(
        CallbackQueryHandler(pro_statistics_callback, pattern="^pro_statistics$")
    )
    application.add_handler(
        CallbackQueryHandler(pro_reminders_callback, pattern="^pro_reminders$")
    )
    application.add_handler(
        CallbackQueryHandler(pro_debt_monitor_callback, pattern="^pro_debt_monitor$")
    )
    application.add_handler(
        CallbackQueryHandler(pro_export_excel_callback, pattern="^pro_export_excel$")
    )
    application.add_handler(
        CallbackQueryHandler(toggle_reminders_callback, pattern="^toggle_reminders_")
    )
    
    # Report handlers (new UX)
    application.add_handler(
        CallbackQueryHandler(detailed_report_callback, pattern="^detailed_report$")
    )
    application.add_handler(
        CallbackQueryHandler(report_weekly_callback, pattern="^report_weekly$")
    )
    application.add_handler(
        CallbackQueryHandler(report_monthly_callback, pattern="^report_monthly$")
    )
    application.add_handler(
        CallbackQueryHandler(back_to_report_callback, pattern="^back_to_report$")
    )
    
    # HALOS usuli status handler
    application.add_handler(
        CallbackQueryHandler(show_halos_status_callback, pattern="^show_halos_status$")
    )
    
    # Report settings handlers
    application.add_handler(
        CallbackQueryHandler(report_settings_callback, pattern="^report_settings$")
    )
    application.add_handler(
        CallbackQueryHandler(toggle_report_callback, pattern="^toggle_report_")
    )
    
    # Debt Plan handlers (FREE vs PRO)
    application.add_handler(
        CallbackQueryHandler(debt_plan_free_callback, pattern="^debt_plan_free$")
    )
    application.add_handler(
        CallbackQueryHandler(debt_plan_pro_callback, pattern="^debt_plan_pro$")
    )
    
    # Recalculate handler
    application.add_handler(
        CallbackQueryHandler(recalculate_callback, pattern="^recalculate$")
    )
    
    # AI Assistant handlers
    application.add_handler(
        CallbackQueryHandler(ai_assistant_callback, pattern="^ai_assistant$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_report_callback, pattern="^ai_report$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_recent_callback, pattern="^ai_recent$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_budget_callback, pattern="^ai_budget$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_real_balance_callback, pattern="^ai_real_balance$")
    )
    
    # AI Correction handlers
    application.add_handler(
        CallbackQueryHandler(ai_confirm_ok_callback, pattern="^ai_confirm_ok$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_confirm_learn_callback, pattern="^ai_confirm_learn$")
    )
    # MUHIM: ai_correct_multi_ OLDIN ro'yxatdan o'tishi kerak!
    application.add_handler(
        CallbackQueryHandler(ai_correct_multi_callback, pattern="^ai_correct_multi_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_correct_callback, pattern="^ai_correct_\\d+$")
    )
    # Gemini bilan qayta tahlil
    application.add_handler(
        CallbackQueryHandler(ai_reanalyze_callback, pattern="^ai_reanalyze_")
    )
    # Kategoriya o'zgartirish
    application.add_handler(
        CallbackQueryHandler(ai_change_category_callback, pattern="^ai_change_category_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_new_category_callback, pattern="^ai_new_category_")
    )
    # Ko'p tranzaksiya aniqlashtirish
    application.add_handler(
        CallbackQueryHandler(ai_clarify_multi_callback, pattern="^ai_clarify_multi_")
    )
    # Kategoriyani aniqlashtirish (ixtiyoriy)
    application.add_handler(
        CallbackQueryHandler(ai_clarify_category_callback, pattern="^ai_clarify_category_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_set_category_callback, pattern="^ai_set_category_")
    )
    # MUHIM: ai_delete_all_ OLDIN ro'yxatdan o'tishi kerak!
    application.add_handler(
        CallbackQueryHandler(ai_delete_all_callback, pattern="^ai_delete_all_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_delete_callback, pattern="^ai_delete_\\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_rewrite_callback, pattern="^ai_rewrite_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_edit_amount_callback, pattern="^ai_edit_amount_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_cancel_correct_callback, pattern="^ai_cancel_correct$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_swap_type_callback, pattern="^ai_swap_type_")
    )
    
    # AI Debt handlers
    application.add_handler(
        CallbackQueryHandler(ai_debt_list_callback, pattern="^ai_debt_list$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_debt_mark_returned_callback, pattern="^ai_debt_mark_returned$")
    )
    application.add_handler(
        CallbackQueryHandler(ai_debt_return_callback, pattern="^ai_debt_return_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_debt_correct_callback, pattern="^ai_debt_correct_")
    )
    application.add_handler(
        CallbackQueryHandler(ai_debt_delete_callback, pattern="^ai_debt_delete_")
    )
    
    # Debt Reminder handlers
    application.add_handler(
        CallbackQueryHandler(debt_reminder_returned_callback, pattern="^debt_reminder_returned:")
    )
    application.add_handler(
        CallbackQueryHandler(debt_reminder_snooze_callback, pattern="^debt_reminder_snooze:")
    )
    
    # Amount input handler for corrections (before AI text handler)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_amount_input_handler),
        group=4
    )
    
    # Voice message handler for AI assistant
    application.add_handler(
        MessageHandler(filters.VOICE, ai_voice_handler),
        group=4
    )
    
    # Text message handler for AI assistant (lowest priority - group 5)
    # This catches any text that looks like expense/income and auto-saves it
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_text_handler),
        group=5
    )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start webhook server for Click payments
    # Railway assigns PORT env var, we use it for webhook server
    port = os.getenv("PORT")
    if port:
        logger.info(f"Starting webhook server on port {port}...")
        from webhook_server import start_webhook_server_async
        
        # Create event loop and start webhook server before polling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run_bot_with_webhook():
            """Run bot with webhook server for Railway/Render deployment"""
            import signal
            from telegram.error import Conflict, NetworkError
            
            # Start webhook server for Click payments
            from webhook_server import start_webhook_server_async
            webhook_runner = await start_webhook_server_async()
            logger.info("Webhook server started successfully")
            
            # Initialize and start the bot
            await application.initialize()
            await application.start()
            
            # ========== CONFLICT PREVENTION FOR RAILWAY/RENDER ==========
            # Delete webhook and wait for old instance to die
            logger.info("Clearing old connections...")
            
            for attempt in range(5):
                try:
                    await application.bot.delete_webhook(drop_pending_updates=True)
                    logger.info(f"Webhook deleted, waiting for old instance to stop (attempt {attempt + 1}/5)...")
                    
                    # Longer wait on first deploy to let old instance die
                    wait_time = 5 if attempt == 0 else 3
                    await asyncio.sleep(wait_time)
                    
                    # Try to start polling
                    logger.info("Starting polling...")
                    await application.updater.start_polling(
                        allowed_updates=["message", "callback_query", "pre_checkout_query"],
                        drop_pending_updates=True,
                        poll_interval=2.0,
                        read_timeout=30,
                        write_timeout=30,
                    )
                    logger.info("Polling started successfully!")
                    break
                    
                except Conflict as e:
                    logger.warning(f"Conflict detected (attempt {attempt + 1}/5): {e}")
                    if attempt < 4:
                        logger.info(f"Waiting 10 seconds before retry...")
                        await asyncio.sleep(10)
                    else:
                        logger.error("Max retries reached. Old instance may still be running.")
                        raise
                        
                except NetworkError as e:
                    logger.warning(f"Network error (attempt {attempt + 1}/5): {e}")
                    if attempt < 4:
                        await asyncio.sleep(5)
                    else:
                        raise
            
            # Start PRO Care Scheduler
            try:
                from app.scheduler import get_scheduler
                scheduler = await get_scheduler(application.bot)
                await scheduler.start()
                logger.info("PRO Care Scheduler started successfully")
            except Exception as e:
                logger.error(f"Failed to start scheduler: {e}")
            
            logger.info("="*50)
            logger.info("вњ… HALOS Bot is running on Railway/Render!")
            logger.info("="*50)
            
            # Graceful shutdown handler
            shutdown_event = asyncio.Event()
            
            def handle_shutdown(signum, frame):
                logger.info(f"Received signal {signum}, initiating graceful shutdown...")
                shutdown_event.set()
            
            # Register signal handlers for Railway/Render
            try:
                signal.signal(signal.SIGTERM, handle_shutdown)
                signal.signal(signal.SIGINT, handle_shutdown)
            except Exception as e:
                logger.warning(f"Could not set signal handlers: {e}")
            
            # Keep running until shutdown signal
            try:
                await shutdown_event.wait()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("Shutting down gracefully...")
                try:
                    await application.updater.stop()
                    await application.stop()
                    await application.shutdown()
                    await webhook_runner.cleanup()
                    logger.info("Shutdown complete!")
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}")
        
        try:
            loop.run_until_complete(run_bot_with_webhook())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
    else:
        # No PORT - run without webhook server (local development)
        logger.info("Bot is running (no webhook server)! Press Ctrl+C to stop.")
        application.run_polling(
            allowed_updates=["message", "callback_query", "pre_checkout_query"],
            drop_pending_updates=True,
            poll_interval=0.0,
        )


if __name__ == "__main__":
    main()
