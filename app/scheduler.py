"""
SOLVO PRO Care Scheduler
Wolt-style caring messages and progress notifications
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from telegram import Bot
from telegram.error import TelegramError

from app.database import get_database
from app.languages import get_message, format_number
from app.engine import format_exit_date

logger = logging.getLogger(__name__)


class ProCareScheduler:
    """
    Scheduler for PRO customer care features:
    - Inactive user reminders (3 days)
    - Salary day motivation (1-5 of month)
    - Weekly progress reports
    - Monthly exit countdown
    """
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start all scheduled jobs"""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting PRO Care Scheduler...")
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._inactive_users_job()),
            asyncio.create_task(self._salary_day_job()),
            asyncio.create_task(self._weekly_progress_job()),
            asyncio.create_task(self._monthly_countdown_job()),
        ]
        
        logger.info("PRO Care Scheduler started with 4 jobs")
    
    async def stop(self):
        """Stop all scheduled jobs"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("PRO Care Scheduler stopped")
    
    # ==================== HELPER METHODS ====================
    
    async def _get_pro_users(self) -> List[Dict[str, Any]]:
        """Get all PRO users with active subscriptions"""
        db = await get_database()
        async with db._connection.execute("""
            SELECT u.*, fp.* 
            FROM users u
            LEFT JOIN financial_profiles fp ON fp.user_id = u.id
            WHERE u.subscription_tier = 'pro'
            AND (u.subscription_expires IS NULL OR u.subscription_expires > datetime('now'))
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def _get_inactive_pro_users(self, days: int = 3) -> List[Dict[str, Any]]:
        """Get PRO users who haven't been active for N days"""
        db = await get_database()
        cutoff = datetime.now() - timedelta(days=days)
        
        async with db._connection.execute("""
            SELECT u.*, fp.*
            FROM users u
            LEFT JOIN financial_profiles fp ON fp.user_id = u.id
            WHERE u.subscription_tier = 'pro'
            AND (u.subscription_expires IS NULL OR u.subscription_expires > datetime('now'))
            AND (u.last_active IS NULL OR u.last_active < ?)
        """, (cutoff.isoformat(),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def _get_user_latest_calculation(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's latest calculation result"""
        db = await get_database()
        async with db._connection.execute("""
            SELECT * FROM calculations 
            WHERE user_id = ? 
            ORDER BY calculated_at DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def _send_message_safe(self, telegram_id: int, text: str, parse_mode: str = "Markdown"):
        """Send message with error handling"""
        try:
            await self.bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode=parse_mode
            )
            logger.info(f"Sent care message to user {telegram_id}")
            return True
        except TelegramError as e:
            logger.warning(f"Failed to send message to {telegram_id}: {e}")
            return False
    
    # ==================== SCHEDULED JOBS ====================
    
    async def _inactive_users_job(self):
        """
        Job: Check for inactive PRO users every 6 hours
        Send caring message if inactive for 3+ days
        """
        while self._running:
            try:
                logger.info("Running inactive users check...")
                users = await self._get_inactive_pro_users(days=3)
                
                for user in users:
                    lang = user.get("language", "uz")
                    message = get_message("care_inactive_3days", lang)
                    await self._send_message_safe(user["telegram_id"], message)
                    
                    # Mark as notified (update last_active to prevent spam)
                    db = await get_database()
                    await db.update_user(user["telegram_id"], last_active=datetime.now().isoformat())
                    
                    # Small delay between messages
                    await asyncio.sleep(1)
                
                logger.info(f"Inactive users check complete. Sent {len(users)} messages.")
                
            except Exception as e:
                logger.error(f"Error in inactive users job: {e}")
            
            # Run every 6 hours
            await asyncio.sleep(6 * 60 * 60)
    
    async def _salary_day_job(self):
        """
        Job: Check for salary days (1-5 of month)
        Send motivation message in the morning
        """
        while self._running:
            try:
                now = datetime.now()
                
                # Only run on days 1-5 of the month
                if 1 <= now.day <= 5:
                    # Only send once per day (check if it's morning 9-10 AM)
                    if 9 <= now.hour < 10:
                        logger.info("Running salary day notification...")
                        users = await self._get_pro_users()
                        
                        for user in users:
                            # Check if we already sent today
                            last_salary_msg = user.get("last_salary_message")
                            if last_salary_msg:
                                last_date = datetime.fromisoformat(last_salary_msg).date()
                                if last_date == now.date():
                                    continue
                            
                            lang = user.get("language", "uz")
                            message = get_message("care_salary_day", lang)
                            
                            if await self._send_message_safe(user["telegram_id"], message):
                                # Mark as sent
                                db = await get_database()
                                await db.update_user(
                                    user["telegram_id"], 
                                    last_salary_message=now.isoformat()
                                )
                            
                            await asyncio.sleep(0.5)
                        
                        logger.info(f"Salary day notifications sent to {len(users)} users")
                
            except Exception as e:
                logger.error(f"Error in salary day job: {e}")
            
            # Check every hour
            await asyncio.sleep(60 * 60)
    
    async def _weekly_progress_job(self):
        """
        Job: Send weekly progress report to PRO users
        Runs every Sunday at 18:00
        """
        while self._running:
            try:
                now = datetime.now()
                
                # Only run on Sunday (weekday 6) at 18:00
                if now.weekday() == 6 and 18 <= now.hour < 19:
                    logger.info("Running weekly progress notifications...")
                    users = await self._get_pro_users()
                    
                    for user in users:
                        try:
                            # Get latest calculation
                            calc = await self._get_user_latest_calculation(user.get("id"))
                            if not calc or not calc.get("exit_date"):
                                continue
                            
                            lang = user.get("language", "uz")
                            mode = user.get("mode", "solo")
                            
                            # Calculate weekly progress (monthly payment / 4)
                            weekly_payment = (calc.get("monthly_debt_payment", 0) or 0) / 4
                            total_debt = user.get("total_debt", 0) or 0
                            remaining = total_debt - weekly_payment
                            
                            # Choose message based on mode
                            msg_key = "weekly_progress_family" if mode == "family" else "weekly_progress"
                            
                            message = get_message(msg_key, lang).format(
                                amount=format_number(weekly_payment) + " so'm",
                                paid=format_number(total_debt - remaining) + " so'm",
                                remaining=format_number(remaining) + " so'm",
                                exit_date=format_exit_date(calc.get("exit_date", ""), lang)
                            )
                            
                            await self._send_message_safe(user["telegram_id"], message)
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error sending weekly progress to {user.get('telegram_id')}: {e}")
                    
                    logger.info("Weekly progress notifications complete")
                
            except Exception as e:
                logger.error(f"Error in weekly progress job: {e}")
            
            # Check every hour
            await asyncio.sleep(60 * 60)
    
    async def _monthly_countdown_job(self):
        """
        Job: Send monthly exit date countdown
        Runs on the 1st of each month at 10:00
        """
        while self._running:
            try:
                now = datetime.now()
                
                # Only run on 1st of month at 10:00
                if now.day == 1 and 10 <= now.hour < 11:
                    logger.info("Running monthly countdown notifications...")
                    users = await self._get_pro_users()
                    
                    for user in users:
                        try:
                            # Get latest calculation
                            calc = await self._get_user_latest_calculation(user.get("id"))
                            if not calc or not calc.get("exit_date"):
                                continue
                            
                            lang = user.get("language", "uz")
                            mode = user.get("mode", "solo")
                            
                            # Parse exit date and calculate months left
                            exit_date_str = calc.get("exit_date", "")
                            if exit_date_str:
                                try:
                                    exit_parts = exit_date_str.split("-")
                                    exit_year = int(exit_parts[0])
                                    exit_month = int(exit_parts[1])
                                    
                                    months_left = (exit_year - now.year) * 12 + (exit_month - now.month)
                                    months_left = max(0, months_left)
                                except:
                                    months_left = calc.get("exit_months", 0)
                            else:
                                months_left = calc.get("exit_months", 0)
                            
                            # Choose message based on mode
                            msg_key = "monthly_countdown_family" if mode == "family" else "monthly_countdown"
                            
                            message = get_message(msg_key, lang).format(
                                exit_date=format_exit_date(exit_date_str, lang),
                                months_left=months_left,
                                remaining_debt=format_number(user.get("total_debt", 0) or 0) + " so'm",
                                savings=format_number(calc.get("savings_at_exit", 0) or 0) + " so'm"
                            )
                            
                            await self._send_message_safe(user["telegram_id"], message)
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error sending monthly countdown to {user.get('telegram_id')}: {e}")
                    
                    logger.info("Monthly countdown notifications complete")
                
            except Exception as e:
                logger.error(f"Error in monthly countdown job: {e}")
            
            # Check every hour
            await asyncio.sleep(60 * 60)


# ==================== MANUAL TRIGGER FUNCTIONS ====================

async def send_caring_message(bot: Bot, telegram_id: int, message_type: str):
    """
    Manually send a caring message to a user
    
    Args:
        bot: Telegram Bot instance
        telegram_id: User's Telegram ID
        message_type: One of 'inactive', 'salary', 'milestone'
    """
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return False
    
    lang = user.get("language", "uz")
    
    message_map = {
        "inactive": "care_inactive_3days",
        "salary": "care_salary_day",
        "first_week": "care_first_week",
        "milestone_50": "care_milestone_50",
    }
    
    msg_key = message_map.get(message_type)
    if not msg_key:
        return False
    
    message = get_message(msg_key, lang)
    
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except TelegramError as e:
        logger.error(f"Failed to send caring message: {e}")
        return False


async def send_weekly_progress(bot: Bot, telegram_id: int):
    """Manually send weekly progress to a specific user"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return False
    
    # Get user's profile and calculation
    profile = await db.get_financial_profile(user["id"])
    if not profile:
        return False
    
    async with db._connection.execute("""
        SELECT * FROM calculations 
        WHERE user_id = ? 
        ORDER BY calculated_at DESC LIMIT 1
    """, (user["id"],)) as cursor:
        row = await cursor.fetchone()
        calc = dict(row) if row else None
    
    if not calc:
        return False
    
    lang = user.get("language", "uz")
    mode = user.get("mode", "solo")
    
    weekly_payment = (calc.get("monthly_debt_payment", 0) or 0) / 4
    total_debt = profile.get("total_debt", 0) or 0
    
    msg_key = "weekly_progress_family" if mode == "family" else "weekly_progress"
    
    message = get_message(msg_key, lang).format(
        amount=format_number(weekly_payment) + " so'm",
        paid=format_number(weekly_payment) + " so'm",
        remaining=format_number(total_debt) + " so'm",
        exit_date=format_exit_date(calc.get("exit_date", ""), lang)
    )
    
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except TelegramError as e:
        logger.error(f"Failed to send weekly progress: {e}")
        return False


async def send_monthly_countdown(bot: Bot, telegram_id: int):
    """Manually send monthly countdown to a specific user"""
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return False
    
    profile = await db.get_financial_profile(user["id"])
    if not profile:
        return False
    
    async with db._connection.execute("""
        SELECT * FROM calculations 
        WHERE user_id = ? 
        ORDER BY calculated_at DESC LIMIT 1
    """, (user["id"],)) as cursor:
        row = await cursor.fetchone()
        calc = dict(row) if row else None
    
    if not calc:
        return False
    
    lang = user.get("language", "uz")
    mode = user.get("mode", "solo")
    
    # Calculate months left
    now = datetime.now()
    exit_date_str = calc.get("exit_date", "")
    months_left = calc.get("exit_months", 0)
    
    if exit_date_str:
        try:
            parts = exit_date_str.split("-")
            exit_year = int(parts[0])
            exit_month = int(parts[1])
            months_left = max(0, (exit_year - now.year) * 12 + (exit_month - now.month))
        except:
            pass
    
    msg_key = "monthly_countdown_family" if mode == "family" else "monthly_countdown"
    
    message = get_message(msg_key, lang).format(
        exit_date=format_exit_date(exit_date_str, lang),
        months_left=months_left,
        remaining_debt=format_number(profile.get("total_debt", 0) or 0) + " so'm",
        savings=format_number(calc.get("savings_at_exit", 0) or 0) + " so'm"
    )
    
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except TelegramError as e:
        logger.error(f"Failed to send monthly countdown: {e}")
        return False


# Global scheduler instance
_scheduler: Optional[ProCareScheduler] = None


async def get_scheduler(bot: Bot) -> ProCareScheduler:
    """Get or create scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ProCareScheduler(bot)
    return _scheduler


async def start_scheduler(bot: Bot):
    """Start the scheduler"""
    scheduler = await get_scheduler(bot)
    await scheduler.start()


async def stop_scheduler():
    """Stop the scheduler"""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
