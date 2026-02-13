"""
HALOS User Engagement System
Daily reports, reminders and re-engagement for active users
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.database import get_database
from app.languages import format_number

logger = logging.getLogger(__name__)

# Timezone for Tashkent (UTC+5)
UZ_TZ = timezone(timedelta(hours=5))


def now_uz():
    """Return current datetime in Asia/Tashkent."""
    return datetime.now(UZ_TZ)


# ==================== ENGAGEMENT MESSAGES ====================

MORNING_GREETINGS = [
    "🌅 Xayrli tong! Bugun Erkinlik Strategiyangizga bir qadam yaqinlashing! 🚀",
    "☀️ Yangi kun — yangi imkoniyat! Xarajatlaringizni nazorat qilishni unutmang! 📝",
    "🌞 Xayrli tong! Bugun shaxsiy kapitalingiz uchun nima qila olasiz? 💎",
    "🌄 Kuningiz xayrli bo'lsin! Moliyaviy erkinlik sari intizom bilan davom etamiz! 🎯",
    "✨ Xayrli tong! Kichik tejamlar — katta kelajak poydevoridir! 🏛",
]

EVENING_SUMMARIES = [
    "🌙 Kun yakunlandi! Bugungi xarajatlaringizni ko'rib chiqing.",
    "🌆 Ajoyib kun edi! Bugungi moliyaviy natijalaringiz:",
    "🌇 Kun tugadi! Qancha tejadingiz, bilasizmi?",
    "🌃 Bugun ham moliyaviy maqsadlarga yaqinlashdingiz!",
]

# Daily nudge messages (Urging users to input today's data)
DAILY_NUDGE_UZ = [
    "🔔 *KUNLIK ESLATMA*\n\nBugun hali xarajatlaringizni yozmadingiz. Bir daqiqa ajratib, Erkinlik Strategiyasini davom ettiring! 🚀",
    "📝 Bugun qancha sarflaganingizni hisobga oldingizmi? Har bir so'm erkinlik sari yo'l! 💎",
    "🎯 Moliyaviy intizom — muvaffaqiyat kaliti. Bugungi xarajatlarni hozirning o'zida yozib qo'ying! 📊",
    "💡 Esingizda bo'lsin: Nazorat qilinmagan xarajat — boylik dushmani. Bugungi qaydlarni kiritish yo'li: _\"15 ming tushlik\"_ shell!",
]

DAILY_NUDGE_RU = [
    "🔔 *ЕЖЕДНЕВНОЕ НАПОМИНАНИЕ*\n\nВы еще не записали расходы за сегодня. Уделите минуту Стратегии Свободы! 🚀",
    "📝 Учли ли вы сегодняшние расходы? Каждый сум — это путь к свободе! 💎",
    "🎯 Финансовая дисциплина — ключ к успеху. Запишите сегодняшние расходы прямо сейчас! 📊",
    "💡 Помните: Неконтролируемый расход — враг богатства. Запишите сегодня: _\"15 тысяч обед\"_!",
]

REMINDER_MESSAGES_UZ = [
    "📝 Salom! Bugun xarajatlaringizni kiritdingizmi? Keling, davom etamiz!",
    "💡 Xarajat yozish 30 soniya oladi, lekin oyiga minglab so'm tejashga yordam beradi!",
    "🎯 Sizni sog'indik! Keling, moliyaviy maqsadlaringizga birga erishamiz.",
    "📊 3 kun o'tdi... Xarajatlaringizni yozib, nazorat qilishni davom eting!",
    "🔔 Eslatma: Har kungi kichik qaydlar - katta tejamlarning kaliti!",
]

REMINDER_MESSAGES_RU = [
    "📝 Привет! Вы сегодня записали расходы? Давайте продолжим!",
    "💡 Запись расхода занимает 30 секунд, но помогает экономить тысячи!",
    "🎯 Мы скучали! Давайте вместе достигнем финансовых целей.",
    "📊 Прошло 3 дня... Продолжайте записывать и контролировать расходы!",
    "🔔 Напоминание: Маленькие записи каждый день = большая экономия!",
]

MOTIVATION_QUOTES = [
    "💪 \"Kichik qadamlar bilan katta marralar zabt etiladi!\"",
    "🌟 \"Bugun tejagan 1000 so'mingiz — kelajakdagi erkinligingizdir!\"",
    "🎯 \"Maqsadga erishish — har kungi intizomda!\"",
    "🚀 \"Erkinlik Strategiyasi — sizning mustaqil kelajagingiz!\"",
    "💎 \"Har bir so'm muhim — ularni o'zingizga ishlashga majbur qiling!\"",
]


class UserEngagementSystem:
    """
    User engagement system for daily reports and reminders:
    - Morning motivation (8:00)
    - Evening daily summary (21:00)
    - Inactive user reminders (after 1-3 days)
    - Weekly progress reports
    """
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start engagement system"""
        if self._running:
            return
        
        self._running = True
        logger.info("🚀 Starting User Engagement System...")
        
        self._tasks = [
            asyncio.create_task(self._morning_motivation_job()),
            asyncio.create_task(self._evening_summary_job()),
            asyncio.create_task(self._daily_nudge_job()),      # NEW: Daily nudge for inactive-today
            asyncio.create_task(self._inactive_reminder_job()),
            asyncio.create_task(self._weekly_report_job()),
        ]
        
        logger.info("✅ User Engagement System started with 5 jobs (including Daily Nudge)")
    
    async def stop(self):
        """Stop engagement system"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("User Engagement System stopped")
    
    # ==================== MORNING MOTIVATION (8:00) ====================
    
    async def _morning_motivation_job(self):
        """Send morning motivation at 8:00 AM Tashkent time"""
        while self._running:
            try:
                now = now_uz()
                
                # Calculate next 8:00 AM
                target = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if now.hour >= 8:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                logger.info(f"Morning motivation scheduled in {wait_seconds/3600:.1f} hours")
                
                await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._send_morning_motivation()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Morning motivation error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    async def _send_morning_motivation(self):
        """Send morning motivation to active users"""
        try:
            db = await get_database()
            
            # Get users who were active in last 7 days and opted in for notifications
            active_users = await self._get_active_users(days=7)
            
            import random
            sent_count = 0
            
            for user in active_users:
                try:
                    lang = user.get("language", "uz")
                    telegram_id = user["telegram_id"]
                    
                    # Get user's financial stats for personalization
                    stats = await self._get_user_quick_stats(user["id"])
                    
                    greeting = random.choice(MORNING_GREETINGS)
                    quote = random.choice(MOTIVATION_QUOTES)
                    
                    if stats and stats.get("monthly_expense", 0) > 0:
                        daily_avg = stats["monthly_expense"] / 30
                        message = (
                            f"{greeting}\n\n"
                            f"📊 O'rtacha kunlik xarajatingiz: *{format_number(int(daily_avg))}* so'm\n\n"
                            f"{quote}\n\n"
                            "💬 Bugungi xarajatni kiritish uchun shunchaki yozing!"
                        )
                    else:
                        message = (
                            f"{greeting}\n\n"
                            f"{quote}\n\n"
                            "💬 Bugungi xarajatni kiritish uchun shunchaki yozing:\n"
                            "_Masalan: \"15000 tushlik\"_"
                        )
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Xarajat kiritish", callback_data="add_expense")],
                        [InlineKeyboardButton("📊 Statistika", callback_data="pro_statistics")]
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    sent_count += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except TelegramError as e:
                    logger.warning(f"Failed to send morning message to {user.get('telegram_id')}: {e}")
                except Exception as e:
                    logger.error(f"Morning message error for user {user.get('id')}: {e}")
            
            logger.info(f"✅ Sent morning motivation to {sent_count} users")
            
        except Exception as e:
            logger.error(f"Morning motivation batch error: {e}")
    
    # ==================== EVENING SUMMARY (21:00) ====================
    
    async def _evening_summary_job(self):
        """Send evening summary at 21:00 Tashkent time"""
        while self._running:
            try:
                now = now_uz()
                
                # Calculate next 20:30
                target = now.replace(hour=20, minute=30, second=0, microsecond=0)
                if now.hour >= 20 and now.minute >= 30:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                logger.info(f"Evening summary scheduled in {wait_seconds/3600:.1f} hours")
                
                await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._send_evening_summaries()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evening summary error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_evening_summaries(self):
        """Send personalized evening summaries to users who had activity today"""
        try:
            db = await get_database()
            
            # Get users who entered transactions today
            today_active_users = await self._get_users_with_today_transactions()
            
            import random
            sent_count = 0
            
            for user in today_active_users:
                try:
                    telegram_id = user["telegram_id"]
                    user_id = user["id"]
                    
                    # Get today's stats
                    today_stats = await self._get_today_stats(user_id)
                    
                    if not today_stats:
                        continue
                    
                    greeting = random.choice(EVENING_SUMMARIES)
                    
                    income = today_stats.get("income", 0)
                    expense = today_stats.get("expense", 0)
                    tx_count = today_stats.get("count", 0)
                    balance = income - expense
                    
                    # Build message
                    message = (
                        f"{greeting}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📅 *BUGUNGI NATIJALAR*\n\n"
                        f"📝 Kiritilgan: *{tx_count}* ta tranzaksiya\n"
                    )
                    
                    if income > 0:
                        message += f"💰 Daromad: *+{format_number(int(income))}* so'm\n"
                    
                    if expense > 0:
                        message += f"💸 Xarajat: *-{format_number(int(expense))}* so'm\n"
                    
                    message += "\n"
                    
                    if balance > 0:
                        message += f"✅ Balans: *+{format_number(int(balance))}* so'm\n"
                        message += "🎉 Ajoyib! Bugun foyda oldingiz!"
                    elif balance < 0:
                        message += f"📉 Balans: *{format_number(int(balance))}* so'm\n"
                        message += "💡 Ertaga tejashga harakat qiling!"
                    else:
                        message += "⚖️ Balans: 0 so'm"
                    
                    # Get weekly comparison
                    weekly = await self._get_weekly_comparison(user_id)
                    if weekly:
                        if weekly["trend"] == "down":
                            message += f"\n\n📉 Bu hafta o'tgan haftaga nisbatan *{weekly['percent']}%* kam sarfladingiz!"
                        elif weekly["trend"] == "up":
                            message += f"\n\n📈 Diqqat: Bu hafta *{weekly['percent']}%* ko'p sarfladingiz."
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📊 Batafsil statistika", callback_data="pro_statistics")],
                        [InlineKeyboardButton("📋 Tranzaksiyalar", callback_data="view_transactions")]
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    sent_count += 1
                    
                    await asyncio.sleep(0.1)
                    
                except TelegramError as e:
                    logger.warning(f"Evening summary failed for {user.get('telegram_id')}: {e}")
                except Exception as e:
                    logger.error(f"Evening summary error: {e}")
            
            logger.info(f"✅ Sent evening summaries to {sent_count} users")
            
        except Exception as e:
            logger.error(f"Evening summary batch error: {e}")
    
    # ==================== DAILY NUDGE (19:30) ====================
    
    async def _daily_nudge_job(self):
        """Bugun harajat kiritmaganlarga soat 19:30 da eslatma yuborish"""
        while self._running:
            try:
                now = now_uz()
                
                # Nudge soat 19:30 da
                target = now.replace(hour=19, minute=30, second=0, microsecond=0)
                if now.hour >= 19 and now.minute >= 30:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                logger.info(f"Daily nudge scheduled in {wait_seconds/3600:.1f} hours")
                
                await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._send_daily_nudges()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daily nudge error: {e}")
                await asyncio.sleep(3600)

    async def _send_daily_nudges(self):
        """Bugun passiv bo'lgan userlarga nudge yuborish"""
        try:
            db = await get_database()
            import random
            
            # 1. Bugun transaction kiritganlar ID ro'yxati
            today_active_ids = await self._get_today_active_user_ids()
            
            # 2. Oxirgi 14 kunda faol bo'lgan barcha userlar
            all_active = await self._get_active_users(days=14)
            
            sent_count = 0
            for user in all_active:
                user_id = user["id"]
                if user_id in today_active_ids:
                    continue
                
                # Bugun hali nudge yuborilmaganini tekshirish (pauza uchun)
                # (aslida run_daily kabi ishlaydi, lekin ehtiyotkorlik uchun)
                
                try:
                    lang = user.get("language", "uz")
                    telegram_id = user["telegram_id"]
                    
                    messages = DAILY_NUDGE_UZ if lang == "uz" else DAILY_NUDGE_RU
                    message = random.choice(messages)
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "✍️ Xarajat kiritish" if lang == "uz" else "✍️ Записать расход",
                            callback_data="add_expense"
                        )],
                        [InlineKeyboardButton(
                            "🎤 Ovozli xabar" if lang == "uz" else "🎤 Голосовое сообщение",
                            callback_data="ai_assistant"
                        )]
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    sent_count += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Failed to nudge {user.get('telegram_id')}: {e}")
            
            logger.info(f"✅ Sent daily nudges to {sent_count} users")
            
        except Exception as e:
            logger.error(f"Daily nudge batch error: {e}")

    async def _get_today_active_user_ids(self) -> set:
        """Bugun transaction kiritgan user ID larini qaytaradi"""
        db = await get_database()
        today = now_uz().date()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("SELECT DISTINCT user_id FROM transactions WHERE DATE(created_at) = $1", today)
                return {row["user_id"] for row in rows}
        else:
            async with db._connection.execute("SELECT DISTINCT user_id FROM transactions WHERE DATE(created_at) = ?", (today.isoformat(),)) as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows}
    
    # ==================== INACTIVE USER REMINDERS ====================
    
    async def _inactive_reminder_job(self):
        """Send reminders to inactive users"""
        while self._running:
            try:
                now = now_uz()
                
                # Run at 14:00 (afternoon)
                target = now.replace(hour=14, minute=0, second=0, microsecond=0)
                if now.hour >= 14:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._send_inactive_reminders()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Inactive reminder error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_inactive_reminders(self):
        """Send reminders to users inactive for 1-3 days"""
        try:
            db = await get_database()
            
            import random
            sent_count = 0
            
            # Get users inactive for different periods
            for days, urgency in [(1, "soft"), (2, "medium"), (3, "strong")]:
                inactive_users = await self._get_inactive_users(days_min=days, days_max=days+1)
                
                for user in inactive_users:
                    try:
                        telegram_id = user["telegram_id"]
                        lang = user.get("language", "uz")
                        
                        if lang == "uz":
                            messages = REMINDER_MESSAGES_UZ
                        else:
                            messages = REMINDER_MESSAGES_RU
                        
                        message = random.choice(messages)
                        
                        # Add personalization based on inactivity level
                        if urgency == "soft" and lang == "uz":
                            message = f"👋 {message}"
                        elif urgency == "medium" and lang == "uz":
                            message = f"⏰ {message}\n\n💡 Bir daqiqa ajrating - xarajat yozing!"
                        elif urgency == "strong" and lang == "uz":
                            streak_info = await self._get_user_streak(user["id"])
                            if streak_info and streak_info > 0:
                                message = (
                                    f"🔥 *{streak_info} kunlik streak'ingiz* buzilmasin!\n\n"
                                    f"{message}"
                                )
                            else:
                                message = f"🎯 {message}\n\n*Bugun boshlang - 7 kunlik challenge!*"
                        
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "✏️ Xarajat yozish" if lang == "uz" else "✏️ Записать расход",
                                callback_data="add_expense"
                            )],
                            [InlineKeyboardButton(
                                "📊 Statistika" if lang == "uz" else "📊 Статистика",
                                callback_data="pro_statistics"
                            )]
                        ])
                        
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=message,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        sent_count += 1
                        
                        # Update reminder sent timestamp
                        await self._mark_reminder_sent(user["id"])
                        
                        await asyncio.sleep(0.1)
                        
                    except TelegramError as e:
                        if "blocked" in str(e).lower():
                            await self._mark_user_blocked(user["id"])
                        logger.warning(f"Reminder failed for {user.get('telegram_id')}: {e}")
                    except Exception as e:
                        logger.error(f"Reminder error: {e}")
            
            logger.info(f"✅ Sent inactive reminders to {sent_count} users")
            
        except Exception as e:
            logger.error(f"Inactive reminder batch error: {e}")
    
    # ==================== WEEKLY REPORT ====================
    
    async def _weekly_report_job(self):
        """Send weekly progress report on Sundays at 10:00"""
        while self._running:
            try:
                now = now_uz()
                
                # Find next Sunday at 10:00
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and now.hour >= 10:
                    days_until_sunday = 7
                
                target = now.replace(hour=10, minute=0, second=0, microsecond=0)
                target += timedelta(days=days_until_sunday)
                
                wait_seconds = (target - now).total_seconds()
                logger.info(f"Weekly report scheduled in {wait_seconds/3600/24:.1f} days")
                
                await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._send_weekly_reports()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Weekly report error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_weekly_reports(self):
        """Send weekly progress reports to all active users"""
        try:
            db = await get_database()
            
            # Get users active in last 14 days
            active_users = await self._get_active_users(days=14)
            
            sent_count = 0
            
            for user in active_users:
                try:
                    telegram_id = user["telegram_id"]
                    user_id = user["id"]
                    lang = user.get("language", "uz")
                    
                    # Get weekly stats
                    weekly_stats = await self._get_weekly_stats(user_id)
                    
                    if not weekly_stats:
                        continue
                    
                    income = weekly_stats.get("income", 0)
                    expense = weekly_stats.get("expense", 0)
                    tx_count = weekly_stats.get("count", 0)
                    top_categories = weekly_stats.get("top_categories", [])
                    
                    if lang == "uz":
                        message = (
                            "📊 *HAFTALIK HISOBOT*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📅 O'tgan 7 kun natijalari:\n\n"
                            f"📝 Tranzaksiyalar: *{tx_count}* ta\n"
                        )
                        
                        if income > 0:
                            message += f"💰 Daromad: *+{format_number(int(income))}* so'm\n"
                        
                        message += f"💸 Xarajat: *-{format_number(int(expense))}* so'm\n"
                        
                        balance = income - expense
                        if balance > 0:
                            message += f"\n✅ Balans: *+{format_number(int(balance))}* so'm\n"
                            message += "🎉 Ajoyib hafta edi!"
                        else:
                            message += f"\n📉 Balans: *{format_number(int(balance))}* so'm\n"
                        
                        if top_categories:
                            message += "\n📌 *Eng ko'p sarflangan:*\n"
                            for i, cat in enumerate(top_categories[:3], 1):
                                message += f"  {i}. {cat['category']}: {format_number(int(cat['amount']))} so'm\n"
                        
                        message += "\n💡 _Yangi hafta - yangi imkoniyat!_"
                    else:
                        message = (
                            "📊 *ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📅 Результаты за 7 дней:\n\n"
                            f"📝 Транзакций: *{tx_count}*\n"
                        )
                        
                        if income > 0:
                            message += f"💰 Доход: *+{format_number(int(income))}* сум\n"
                        
                        message += f"💸 Расход: *-{format_number(int(expense))}* сум\n"
                        
                        balance = income - expense
                        if balance > 0:
                            message += f"\n✅ Баланс: *+{format_number(int(balance))}* сум\n"
                            message += "🎉 Отличная неделя!"
                        else:
                            message += f"\n📉 Баланс: *{format_number(int(balance))}* сум\n"
                        
                        message += "\n💡 _Новая неделя - новые возможности!_"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "📊 Batafsil" if lang == "uz" else "📊 Подробнее",
                            callback_data="pro_statistics"
                        )],
                        [InlineKeyboardButton(
                            "📥 Excel yuklab olish" if lang == "uz" else "📥 Скачать Excel",
                            callback_data="pro_export_excel"
                        )]
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    sent_count += 1
                    
                    await asyncio.sleep(0.1)
                    
                except TelegramError as e:
                    logger.warning(f"Weekly report failed for {user.get('telegram_id')}: {e}")
                except Exception as e:
                    logger.error(f"Weekly report error: {e}")
            
            logger.info(f"✅ Sent weekly reports to {sent_count} users")
            
        except Exception as e:
            logger.error(f"Weekly report batch error: {e}")
    
    # ==================== HELPER METHODS ====================
    
    async def _get_active_users(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get users active in last N days"""
        db = await get_database()
        cutoff = datetime.now() - timedelta(days=days)
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT u.*
                    FROM users u
                    WHERE u.last_active > $1
                    AND u.telegram_id IS NOT NULL
                    AND COALESCE(u.notifications_blocked, false) = false
                """, cutoff)
                return [dict(row) for row in rows]
        else:
            async with db._connection.execute("""
                SELECT DISTINCT u.*
                FROM users u
                WHERE u.last_active > ?
                AND u.telegram_id IS NOT NULL
            """, (cutoff.isoformat(),)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def _get_inactive_users(self, days_min: int, days_max: int) -> List[Dict[str, Any]]:
        """Get users inactive for specified day range"""
        db = await get_database()
        cutoff_max = datetime.now() - timedelta(days=days_min)
        cutoff_min = datetime.now() - timedelta(days=days_max)
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT u.*
                    FROM users u
                    WHERE u.last_active BETWEEN $1 AND $2
                    AND u.telegram_id IS NOT NULL
                    AND COALESCE(u.notifications_blocked, false) = false
                    AND COALESCE(u.last_reminder_sent, '1970-01-01'::timestamp) < NOW() - INTERVAL '1 day'
                """, cutoff_min, cutoff_max)
                return [dict(row) for row in rows]
        else:
            async with db._connection.execute("""
                SELECT u.*
                FROM users u
                WHERE u.last_active BETWEEN ? AND ?
                AND u.telegram_id IS NOT NULL
            """, (cutoff_min.isoformat(), cutoff_max.isoformat())) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def _get_users_with_today_transactions(self) -> List[Dict[str, Any]]:
        """Get users who entered transactions today"""
        db = await get_database()
        today = now_uz().date()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT u.*
                    FROM users u
                    JOIN transactions t ON t.user_id = u.id
                    WHERE DATE(t.created_at) = $1
                    AND u.telegram_id IS NOT NULL
                """, today)
                return [dict(row) for row in rows]
        else:
            async with db._connection.execute("""
                SELECT DISTINCT u.*
                FROM users u
                JOIN transactions t ON t.user_id = u.id
                WHERE DATE(t.created_at) = ?
                AND u.telegram_id IS NOT NULL
            """, (today.isoformat(),)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def _get_today_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's today transaction stats"""
        db = await get_database()
        today = now_uz().date()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
                    FROM transactions
                    WHERE user_id = $1 AND DATE(created_at) = $2
                """, user_id, today)
                return dict(row) if row else None
        else:
            async with db._connection.execute("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
                FROM transactions
                WHERE user_id = ? AND DATE(created_at) = ?
            """, (user_id, today.isoformat())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def _get_weekly_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's weekly transaction stats"""
        db = await get_database()
        week_ago = now_uz().date() - timedelta(days=7)
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                # Get totals
                totals = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
                    FROM transactions
                    WHERE user_id = $1 AND DATE(created_at) >= $2
                """, user_id, week_ago)
                
                # Get top categories
                categories = await conn.fetch("""
                    SELECT category, SUM(amount) as amount
                    FROM transactions
                    WHERE user_id = $1 AND DATE(created_at) >= $2 AND type = 'expense'
                    GROUP BY category
                    ORDER BY amount DESC
                    LIMIT 3
                """, user_id, week_ago)
                
                if totals:
                    result = dict(totals)
                    result["top_categories"] = [dict(c) for c in categories]
                    return result
                return None
        else:
            async with db._connection.execute("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
                FROM transactions
                WHERE user_id = ? AND DATE(created_at) >= ?
            """, (user_id, week_ago.isoformat())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def _get_weekly_comparison(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Compare this week's expenses with last week"""
        db = await get_database()
        today = now_uz().date()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                this_week = await conn.fetchval("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE user_id = $1 AND type = 'expense'
                    AND DATE(created_at) BETWEEN $2 AND $3
                """, user_id, week_ago, today)
                
                last_week = await conn.fetchval("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE user_id = $1 AND type = 'expense'
                    AND DATE(created_at) BETWEEN $2 AND $3
                """, user_id, two_weeks_ago, week_ago)
                
                if last_week and last_week > 0:
                    diff = this_week - last_week
                    percent = abs(int((diff / last_week) * 100))
                    trend = "up" if diff > 0 else "down"
                    return {"trend": trend, "percent": percent}
        
        return None
    
    async def _get_user_quick_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's quick monthly stats"""
        db = await get_database()
        month_ago = now_uz().date() - timedelta(days=30)
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as monthly_expense
                    FROM transactions
                    WHERE user_id = $1 AND DATE(created_at) >= $2
                """, user_id, month_ago)
                return dict(row) if row else None
        return None
    
    async def _get_user_streak(self, user_id: int) -> int:
        """Get user's consecutive days streak"""
        db = await get_database()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                # Get distinct dates with transactions
                rows = await conn.fetch("""
                    SELECT DISTINCT DATE(created_at) as tx_date
                    FROM transactions
                    WHERE user_id = $1
                    ORDER BY tx_date DESC
                    LIMIT 30
                """, user_id)
                
                if not rows:
                    return 0
                
                dates = [row["tx_date"] for row in rows]
                today = now_uz().date()
                
                streak = 0
                check_date = today
                
                for d in dates:
                    if d == check_date:
                        streak += 1
                        check_date -= timedelta(days=1)
                    elif d < check_date:
                        break
                
                return streak
        return 0
    
    async def _mark_reminder_sent(self, user_id: int):
        """Mark that reminder was sent to user"""
        db = await get_database()
        now = datetime.now()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users SET last_reminder_sent = $1 WHERE id = $2
                """, now, user_id)
    
    async def _mark_user_blocked(self, user_id: int):
        """Mark user as blocked (can't receive messages)"""
        db = await get_database()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users SET notifications_blocked = true WHERE id = $1
                """, user_id)


# ==================== MANUAL SEND FUNCTIONS ====================

async def send_daily_report_to_user(bot: Bot, telegram_id: int, lang: str = "uz") -> bool:
    """Manually send daily report to specific user"""
    try:
        db = await get_database()
        user = await db.get_user(telegram_id)
        
        if not user:
            return False
        
        engagement = UserEngagementSystem(bot)
        today_stats = await engagement._get_today_stats(user["id"])
        
        if not today_stats or today_stats["count"] == 0:
            message = (
                "📊 *BUGUNGI HISOBOT*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📝 Bugun hali tranzaksiya kiritilmadi.\n\n"
                "💡 Xarajatlaringizni yozib, moliyaviy\n"
                "holatni nazorat qiling!"
            )
        else:
            income = today_stats.get("income", 0)
            expense = today_stats.get("expense", 0)
            balance = income - expense
            
            message = (
                "📊 *BUGUNGI HISOBOT*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 Tranzaksiyalar: *{today_stats['count']}* ta\n"
            )
            
            if income > 0:
                message += f"💰 Daromad: *+{format_number(int(income))}* so'm\n"
            if expense > 0:
                message += f"💸 Xarajat: *-{format_number(int(expense))}* so'm\n"
            
            message += f"\n💵 Balans: *{format_number(int(balance))}* so'm"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Xarajat kiritish", callback_data="add_expense")]
        ])
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return True
        
    except Exception as e:
        logger.error(f"Manual daily report error: {e}")
        return False
