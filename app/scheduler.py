"""
HALOS PRO Care Scheduler
Wolt-style caring messages and progress notifications
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.database import get_database
from app.languages import get_message, format_number
from app.engine import format_exit_date

logger = logging.getLogger(__name__)

# Timezone helper for Tashkent (UTC+5)
UZ_TZ = timezone(timedelta(hours=5))


def now_uz():
    """Return current datetime in Asia/Tashkent (UTC+5)."""
    return datetime.now(UZ_TZ)


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
            asyncio.create_task(self._debt_reminder_job()),  # Qarz eslatmalari
            asyncio.create_task(self._subscription_expiry_job()),  # Obuna muddati nazorati
            asyncio.create_task(self._kotib_balance_job()),  # Kotib.ai balans nazorati
        ]
        
        logger.info("PRO Care Scheduler started with 7 jobs")
    
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
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT u.*
                    FROM users u
                    WHERE u.subscription_tier = 'pro'
                    AND (u.subscription_expires IS NULL OR u.subscription_expires > NOW())
                """)
                return [dict(row) for row in rows]
        else:
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
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT u.*
                    FROM users u
                    WHERE u.subscription_tier = 'pro'
                    AND (u.subscription_expires IS NULL OR u.subscription_expires > NOW())
                    AND (u.last_active IS NULL OR u.last_active < $1)
                """, cutoff)
                return [dict(row) for row in rows]
        else:
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
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM calculations 
                    WHERE user_id = $1 
                    ORDER BY calculated_at DESC LIMIT 1
                """, user_id)
                return dict(row) if row else None
        else:
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
                    if db.is_postgres:
                        await db.update_user(user["telegram_id"], last_active=now_uz())
                    else:
                        await db.update_user(user["telegram_id"], last_active=now_uz().isoformat())
                    
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
                now = now_uz()
                
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
                                if isinstance(last_salary_msg, str):
                                    last_date = datetime.fromisoformat(last_salary_msg).date()
                                else:
                                    last_date = last_salary_msg.date() if hasattr(last_salary_msg, 'date') else last_salary_msg
                                if last_date == now.date():
                                    continue
                            
                            lang = user.get("language", "uz")
                            message = get_message("care_salary_day", lang)
                            
                            if await self._send_message_safe(user["telegram_id"], message):
                                # Mark as sent
                                db = await get_database()
                                if db.is_postgres:
                                    await db.update_user(
                                        user["telegram_id"], 
                                        last_salary_message=now
                                    )
                                else:
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
                now = now_uz()
                
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
                now = now_uz()
                
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
    
    async def _subscription_expiry_job(self):
        """
        Job: PRO obuna muddati nazorati
        Har 1 soatda tekshiradi:
        - Muddati tugagan obunalarni FREE ga qaytaradi
        - 3 kun ichida tugaydigan obunalarga ogohlantirish yuboradi
        """
        while self._running:
            try:
                now = now_uz()
                logger.info("Checking subscription expiry...")
                
                # ==================== MUDDATI TUGAGAN OBUNALAR ====================
                expired = await get_expired_subscriptions()
                
                for user in expired:
                    try:
                        telegram_id = user["telegram_id"]
                        lang = user.get("language", "uz")
                        name = user.get("first_name", "")
                        
                        # Reset to free
                        await reset_expired_subscription(telegram_id)
                        
                        # Send notification
                        if lang == "uz":
                            message = (
                                "⚠️ *PRO OBUNA TUGADI*\n"
                                "━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"Salom {name}! Sizning PRO obunangiz muddati tugadi.\n\n"
                                "🔒 PRO imkoniyatlar endi cheklangan:\n"
                                "├ ❌ HALOS sanasi\n"
                                "├ ❌ Tezkor qutilish rejasi\n"
                                "├ ❌ AI ovozli yordamchi\n"
                                "└ ❌ Excel eksport\n\n"
                                "💎 Davom ettirish uchun PRO ni yangilang!"
                            )
                        else:
                            message = (
                                "⚠️ *PRO ПОДПИСКА ИСТЕКЛА*\n"
                                "━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"Здравствуйте {name}! Срок вашей PRO подписки истек.\n\n"
                                "🔒 PRO возможности теперь ограничены:\n"
                                "├ ❌ Дата HALOS\n"
                                "├ ❌ Быстрый план погашения\n"
                                "├ ❌ AI голосовой помощник\n"
                                "└ ❌ Excel экспорт\n\n"
                                "💎 Продлите PRO чтобы продолжить!"
                            )
                        
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "💎 PRO yangilash" if lang == "uz" else "💎 Продлить PRO",
                                callback_data="show_pricing"
                            )]
                        ])
                        
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=message,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        
                        logger.info(f"Subscription expired notification sent to {telegram_id}")
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Error processing expired subscription for {user.get('telegram_id')}: {e}")
                
                # ==================== TUZ TUGAYDIGAN OBUNALAR (3 kun ichida) ====================
                # Faqat kuniga 1 marta (soat 10:00 da)
                if now.hour == 10:
                    expiring_soon = await get_expiring_soon_subscriptions(days=3)
                    
                    for user in expiring_soon:
                        try:
                            telegram_id = user["telegram_id"]
                            lang = user.get("language", "uz")
                            name = user.get("first_name", "")
                            expires = user.get("subscription_expires")
                            
                            if isinstance(expires, str):
                                expires = datetime.fromisoformat(expires)
                            
                            days_left = (expires - now).days + 1
                            
                            if lang == "uz":
                                message = (
                                    "⏰ *PRO OBUNA TUGAYAPTI*\n"
                                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"Salom {name}! PRO obunangiz *{days_left} kun*da tugaydi.\n\n"
                                    f"📅 Tugash sanasi: *{expires.strftime('%d.%m.%Y')}*\n\n"
                                    "💡 Hozir yangilasangiz, uzilishsiz davom etasiz!"
                                )
                            else:
                                message = (
                                    "⏰ *PRO ПОДПИСКА ЗАКАНЧИВАЕТСЯ*\n"
                                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"Здравствуйте {name}! Ваша PRO подписка истекает через *{days_left} дн.*\n\n"
                                    f"📅 Дата окончания: *{expires.strftime('%d.%m.%Y')}*\n\n"
                                    "💡 Продлите сейчас для непрерывного использования!"
                                )
                            
                            keyboard = InlineKeyboardMarkup([
                                [InlineKeyboardButton(
                                    "💎 PRO yangilash" if lang == "uz" else "💎 Продлить PRO",
                                    callback_data="show_pricing"
                                )]
                            ])
                            
                            await self.bot.send_message(
                                chat_id=telegram_id,
                                text=message,
                                parse_mode="Markdown",
                                reply_markup=keyboard
                            )
                            
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error sending expiry warning to {user.get('telegram_id')}: {e}")
                
                logger.info(f"Subscription expiry check complete: {len(expired)} expired, processed")
                
            except Exception as e:
                logger.error(f"Error in subscription expiry job: {e}")
            
            # Check every hour
            await asyncio.sleep(60 * 60)
    
    async def _debt_reminder_job(self):
        """
        Job: Qarz qaytarish eslatmalari
        Har kuni ertalab 6:00 da tekshiradi
        - Bugun qaytarish sanasi bo'lganlar uchun eslatma
        - 3 kun ichida qaytarish sanasi kelayotganlar uchun oldindan ogohlantirish
        """
        while self._running:
            try:
                now = now_uz()
                
                # Faqat ertalab 6-7 oralig'ida ishlaydi (6:00 AM)
                if 6 <= now.hour < 7:
                    logger.info("Running debt reminder check at 6:00 AM...")
                    db = await get_database()
                    
                    # ==================== BUGUNGI QARZLAR ====================
                    today_debts = await get_debts_due_today(db)
                    
                    for debt in today_debts:
                        try:
                            lang = debt.get("language", "uz")
                            person = debt.get("person_name", "Noma'lum")
                            amount = debt.get("amount", 0)
                            debt_type = debt.get("debt_type")
                            debt_id = debt.get("id")
                            description = debt.get("description", "")
                            
                            # Valyuta formatlash
                            currency = debt.get("currency", "UZS")
                            if currency == "USD":
                                amount_str = f"${amount:,.0f}"
                            elif currency == "RUB":
                                amount_str = f"₽{amount:,.0f}"
                            else:
                                amount_str = f"{amount:,.0f} so'm"
                            
                            if lang == "uz":
                                if debt_type == "lent":
                                    # Men qarz berganman, menga qaytarilishi kerak
                                    message = (
                                        "🔔 *BUGUN QARZ QAYTISH KUNI!*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}* sizga qarz qaytarishi kerak\n\n"
                                        f"💰 Summa: *{amount_str}*\n"
                                        f"📅 Sana: *Bugun*\n"
                                    )
                                    if description:
                                        message += f"📝 Izoh: _{description}_\n"
                                    message += (
                                        "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "💡 _Qarz qaytarilsa, tugmani bosing_"
                                    )
                                else:
                                    # Men qarz olganman, men qaytarishim kerak
                                    message = (
                                        "⚠️ *BUGUN QARZ QAYTARISH KUNI!*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}*ga qarz qaytarishingiz kerak\n\n"
                                        f"💰 Summa: *{amount_str}*\n"
                                        f"📅 Sana: *Bugun*\n"
                                    )
                                    if description:
                                        message += f"📝 Izoh: _{description}_\n"
                                    message += (
                                        "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "💡 _Qarz qaytarganingizda tugmani bosing_"
                                    )
                            else:
                                if debt_type == "lent":
                                    message = (
                                        "🔔 *СЕГОДНЯ ДЕНЬ ВОЗВРАТА ДОЛГА!*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}* должен вернуть вам долг\n\n"
                                        f"💰 Сумма: *{amount_str}*\n"
                                        f"📅 Дата: *Сегодня*\n"
                                    )
                                    if description:
                                        message += f"📝 Заметка: _{description}_\n"
                                    message += (
                                        "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "💡 _Нажмите кнопку когда долг вернут_"
                                    )
                                else:
                                    message = (
                                        "⚠️ *СЕГОДНЯ ДЕНЬ ВОЗВРАТА ДОЛГА!*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 Вы должны вернуть долг *{person}*\n\n"
                                        f"💰 Сумма: *{amount_str}*\n"
                                        f"📅 Дата: *Сегодня*\n"
                                    )
                                    if description:
                                        message += f"📝 Заметка: _{description}_\n"
                                    message += (
                                        "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "💡 _Нажмите кнопку когда вернёте долг_"
                                    )
                            
                            # Tugmalar
                            keyboard = InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton(
                                        "✅ Qaytarildi" if lang == "uz" else "✅ Возвращён",
                                        callback_data=f"debt_reminder_returned:{debt_id}"
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "⏰ Ertaga eslatish" if lang == "uz" else "⏰ Напомнить завтра",
                                        callback_data=f"debt_reminder_snooze:{debt_id}"
                                    ),
                                    InlineKeyboardButton(
                                        "📋 Qarzlar ro'yxati" if lang == "uz" else "📋 Список долгов",
                                        callback_data="ai_debt_list"
                                    )
                                ]
                            ])
                            
                            await self.bot.send_message(
                                chat_id=debt["telegram_id"],
                                text=message,
                                parse_mode="Markdown",
                                reply_markup=keyboard
                            )
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error sending debt reminder: {e}")
                    
                    logger.info(f"Sent {len(today_debts)} debt due today reminders")
                    
                    # ==================== 3 KUN ICHIDAGI QARZLAR ====================
                    upcoming_debts = await get_debts_due_soon(db, days=3)
                    
                    for debt in upcoming_debts:
                        try:
                            lang = debt.get("language", "uz")
                            person = debt.get("person_name", "Noma'lum")
                            amount = debt.get("amount", 0)
                            debt_type = debt.get("debt_type")
                            due_date = debt.get("due_date", "")
                            debt_id = debt.get("id")
                            description = debt.get("description", "")
                            
                            # Valyuta formatlash
                            currency = debt.get("currency", "UZS")
                            if currency == "USD":
                                amount_str = f"${amount:,.0f}"
                            elif currency == "RUB":
                                amount_str = f"₽{amount:,.0f}"
                            else:
                                amount_str = f"{amount:,.0f} so'm"
                            
                            # Kun hisoblash
                            due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                            days_left = (due_dt - now).days
                            
                            # Sana formatlash
                            day_num = due_dt.day
                            months_uz = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 
                                        'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']
                            months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                                        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
                            
                            if lang == "uz":
                                date_str = f"{day_num}-{months_uz[due_dt.month - 1]}"
                                days_word = "kun" if days_left == 1 else "kun"
                                
                                if debt_type == "lent":
                                    message = (
                                        "⏰ *YAQINLASHAYOTGAN QARZ*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}* sizga qarz qaytarishi kerak\n\n"
                                        f"💰 Summa: *{amount_str}*\n"
                                        f"📅 Sana: *{date_str}* ({days_left} {days_word} qoldi)\n"
                                    )
                                else:
                                    message = (
                                        "⏰ *YAQINLASHAYOTGAN QARZ*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}*ga qarz qaytarishingiz kerak\n\n"
                                        f"💰 Summa: *{amount_str}*\n"
                                        f"📅 Sana: *{date_str}* ({days_left} {days_word} qoldi)\n"
                                    )
                                
                                if description:
                                    message += f"📝 Izoh: _{description}_\n"
                            else:
                                date_str = f"{day_num} {months_ru[due_dt.month - 1]}"
                                days_word = "день" if days_left == 1 else ("дня" if 2 <= days_left <= 4 else "дней")
                                
                                if debt_type == "lent":
                                    message = (
                                        "⏰ *ПРИБЛИЖАЕТСЯ СРОК ДОЛГА*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 *{person}* должен вернуть вам долг\n\n"
                                        f"💰 Сумма: *{amount_str}*\n"
                                        f"📅 Дата: *{date_str}* (осталось {days_left} {days_word})\n"
                                    )
                                else:
                                    message = (
                                        "⏰ *ПРИБЛИЖАЕТСЯ СРОК ДОЛГА*\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"👤 Вы должны вернуть долг *{person}*\n\n"
                                        f"💰 Сумма: *{amount_str}*\n"
                                        f"📅 Дата: *{date_str}* (осталось {days_left} {days_word})\n"
                                    )
                                
                                if description:
                                    message += f"📝 Заметка: _{description}_\n"
                            
                            # Tugma
                            keyboard = InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton(
                                        "📋 Qarzlarimni ko'rish" if lang == "uz" else "📋 Мои долги",
                                        callback_data="ai_debt_list"
                                    )
                                ]
                            ])
                            
                            await self.bot.send_message(
                                chat_id=debt["telegram_id"],
                                text=message,
                                parse_mode="Markdown",
                                reply_markup=keyboard
                            )
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error sending upcoming debt reminder: {e}")
                    
                    logger.info(f"Sent {len(upcoming_debts)} upcoming debt reminders")
                
            except Exception as e:
                logger.error(f"Error in debt reminder job: {e}")
            
            # Har 1 soatda tekshirish
            await asyncio.sleep(60 * 60)
    
    async def _kotib_balance_job(self):
        """
        Job: Kotib.ai balansini nazorat qilish
        Har 6 soatda tekshiradi va kam bo'lsa adminlarga xabar yuboradi
        """
        while self._running:
            try:
                logger.info("Checking Kotib.ai balance...")
                
                from app.ai_assistant import check_kotib_balance_and_alert
                await check_kotib_balance_and_alert(self.bot)
                
                logger.info("Kotib.ai balance check complete")
                
            except Exception as e:
                logger.error(f"Error in Kotib balance job: {e}")
            
            # Har 6 soatda tekshirish
            await asyncio.sleep(6 * 60 * 60)


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
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM calculations 
                WHERE user_id = $1 
                ORDER BY calculated_at DESC LIMIT 1
            """, user["id"])
            calc = dict(row) if row else None
    else:
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
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM calculations 
                WHERE user_id = $1 
                ORDER BY calculated_at DESC LIMIT 1
            """, user["id"])
            calc = dict(row) if row else None
    else:
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


async def get_debts_due_today(db) -> List[Dict[str, Any]]:
    """Bugun qaytarish sanasi bo'lgan qarzlarni olish"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pd.*, u.telegram_id, u.language
                FROM personal_debts pd
                JOIN users u ON pd.user_id = u.id
                WHERE pd.due_date = $1 AND pd.status = 'active'
            """, today)
            return [dict(row) for row in rows]
    else:
        async with db._connection.execute("""
            SELECT pd.*, u.telegram_id, u.language
            FROM personal_debts pd
            JOIN users u ON pd.user_id = u.id
            WHERE pd.due_date = ? AND pd.status = 'active'
        """, (today,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_debts_due_soon(db, days: int = 3) -> List[Dict[str, Any]]:
    """N kun ichida qaytarish sanasi keladigan qarzlarni olish"""
    today = datetime.now()
    target_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pd.*, u.telegram_id, u.language
                FROM personal_debts pd
                JOIN users u ON pd.user_id = u.id
                WHERE pd.due_date > $1 AND pd.due_date <= $2 AND pd.status = 'active'
            """, today_str, target_date)
            return [dict(row) for row in rows]
    else:
        async with db._connection.execute("""
            SELECT pd.*, u.telegram_id, u.language
            FROM personal_debts pd
            JOIN users u ON pd.user_id = u.id
            WHERE pd.due_date > ? AND pd.due_date <= ? AND pd.status = 'active'
        """, (today_str, target_date)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_expired_subscriptions() -> List[Dict[str, Any]]:
    """Get users with expired PRO subscriptions that haven't been reset to free"""
    db = await get_database()
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT telegram_id, first_name, language, subscription_expires
                FROM users
                WHERE subscription_tier = 'pro'
                AND subscription_expires IS NOT NULL
                AND subscription_expires < NOW()
            """)
            return [dict(row) for row in rows]
    else:
        async with db._connection.execute("""
            SELECT telegram_id, first_name, language, subscription_expires
            FROM users
            WHERE subscription_tier = 'pro'
            AND subscription_expires IS NOT NULL
            AND subscription_expires < datetime('now')
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_expiring_soon_subscriptions(days: int = 3) -> List[Dict[str, Any]]:
    """Get users whose PRO subscription expires within N days"""
    db = await get_database()
    now = datetime.now()
    future = now + timedelta(days=days)
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT telegram_id, first_name, language, subscription_expires
                FROM users
                WHERE subscription_tier = 'pro'
                AND subscription_expires IS NOT NULL
                AND subscription_expires > $1
                AND subscription_expires <= $2
            """, now, future)
            return [dict(row) for row in rows]
    else:
        async with db._connection.execute("""
            SELECT telegram_id, first_name, language, subscription_expires
            FROM users
            WHERE subscription_tier = 'pro'
            AND subscription_expires IS NOT NULL
            AND subscription_expires > ?
            AND subscription_expires <= ?
        """, (now.isoformat(), future.isoformat())) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def reset_expired_subscription(telegram_id: int):
    """Reset expired subscription to free tier"""
    db = await get_database()
    
    if db.is_postgres:
        async with db._pool.acquire() as conn:
            await conn.execute("""
                UPDATE users 
                SET subscription_tier = 'free'
                WHERE telegram_id = $1
            """, telegram_id)
    else:
        await db._connection.execute("""
            UPDATE users 
            SET subscription_tier = 'free'
            WHERE telegram_id = ?
        """, (telegram_id,))
        await db._connection.commit()
    
    logger.info(f"Reset subscription to FREE for user {telegram_id}")


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
