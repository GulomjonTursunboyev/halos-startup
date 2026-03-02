"""
HALOS User Engagement System v2
MUKAMMAL QAYTA YOZILGAN - restart da spam qilmaydi!

Asosiy tuzatishlar:
1. wait_seconds < 0 bo'lsa, ERTAGA ga o'tadi (restart spam yo'q)
2. Bugun allaqachon jo'natilganini tekshiradi (dublikat yo'q)
3. Barcha /start bosgan userlarga ishlaydi (faqat aktiv emas)
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

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


def _next_time(hour: int, minute: int = 0) -> float:
    """
    Keyingi belgilangan vaqtgacha qancha sekund kutish kerakligini hisoblaydi.
    AGAR vaqt o'tgan bo'lsa — ERTAGA ga o'tadi (restart spam yo'q!)
    """
    now = now_uz()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if now >= target:
        # Vaqt o'tgan — ERTAGA shu vaqtga
        target += timedelta(days=1)
    
    wait = (target - now).total_seconds()
    # Minimal 60 sekund kutish (0 yoki manfiy bo'lmaslik uchun)
    return max(wait, 60)


# ==================== ENGAGEMENT MESSAGES ====================

DAILY_NUDGE_UZ = [
    "🔔 *KUNLIK ESLATMA*\n\nBugun hali xarajatlaringizni yozmadingiz. Erkinlik Strategiyasini davom ettiring! 🚀",
    "📝 Bugun qancha sarfladingiz? Har bir so'm erkinlik sari yo'l! 💎",
    "🎯 Moliyaviy intizom — muvaffaqiyat kaliti. Bugungi xarajatlarni yozib qo'ying! 📊",
    "💡 Nazorat qilinmagan xarajat — boylik dushmani. Hoziroq yozing: _\"15 ming tushlik\"_ 🍽",
    "🌟 Halosda xarajat yozish 30 soniya oladi, lekin oyiga minglab so'm tejashga yordam beradi!",
]

DAILY_NUDGE_RU = [
    "🔔 *НАПОМИНАНИЕ*\n\nВы ещё не записали расходы за сегодня. Продолжайте путь к финансовой свободе! 🚀",
    "📝 Сколько потратили сегодня? Каждый сум — шаг к свободе! 💎",
    "🎯 Финансовая дисциплина — ключ к успеху. Запишите расходы! 📊",
    "💡 Запись занимает 30 секунд: _\"15000 обед\"_ 🍽",
]

EVENING_SUMMARIES_UZ = [
    "🌙 Kun yakunlandi! Bugungi moliyaviy natijalaringiz:",
    "🌆 Ajoyib kun edi! Bugungi hisobot:",
    "🌇 Kun tugadi! Tejamkor bo'ldingizmi?",
]

MORNING_GREETINGS_UZ = [
    "🌅 Xayrli tong! Bugun moliyaviy erkinlikka bir qadam yaqinlashing!",
    "☀️ Yangi kun — yangi imkoniyat! Xarajatlarni nazorat qiling!",
    "🌞 Xayrli tong! Bugun Halos bilan pul boshqaring! 💎",
]

PRO_TEASERS_UZ = [
    "\n\n💎 *PRO imkoniyat:* Ovozli xabar bilan xarajat yozish tezroq! 🎤",
    "\n\n📊 *PRO fakt:* PRO foydalanuvchilar 25% ko'proq tejashadi!",
    "\n\n📅 *PRO:* Qachon qarzdan qutulishingiz sanasini bilasizmi?",
    "\n\n📥 *PRO:* Barcha ma'lumotlarni Excelga yuklab olish mumkin!",
    "\n\n🧠 *PRO:* AI buxgalter 24/7 ishlaydi — sizning shaxsiy moliyaviy maslahatchi!",
]


class UserEngagementSystem:
    """
    User Engagement System v2 - RESTART XAVFSIZ
    
    Xususiyatlari:
    - Kunlik eslatma soat 15:00 (bugun tx kiritmaganlarga)
    - Kechki hisobot soat 21:00 (bugun tx kiritganlarga)
    - Ertalabki motivatsiya soat 8:00
    - Haftalik hisobot yakshanba 10:00
    - Har bir habar faqat 1 MARTA yuboriladi (restart da takrorlanmaydi)
    """
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._running = False
        self._tasks: List[asyncio.Task] = []
        # Bugun jo'natilgan habarlarni kuzatish (restart himoyasi)
        self._sent_today: Dict[str, set] = {
            "nudge": set(),
            "evening": set(), 
            "morning": set(),
        }
        self._last_sent_date = now_uz().date()
    
    async def start(self):
        """Start engagement system"""
        if self._running:
            return
        
        self._running = True
        logger.info("🚀 Starting User Engagement System v2 (restart-safe)...")
        
        self._tasks = [
            asyncio.create_task(self._daily_nudge_job()),       # 15:00 - eslatma
            asyncio.create_task(self._evening_summary_job()),    # 21:00 - kechki hisobot
            asyncio.create_task(self._morning_motivation_job()), # 08:00 - ertalabki
        ]
        
        logger.info("✅ Engagement System v2 started with 3 scheduled jobs")
    
    async def stop(self):
        """Stop engagement system"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("Engagement System stopped")
    
    def _reset_daily_tracking(self):
        """Yangi kun bo'lsa tracking ni tozalash"""
        today = now_uz().date()
        if today != self._last_sent_date:
            self._sent_today = {"nudge": set(), "evening": set(), "morning": set()}
            self._last_sent_date = today
    
    # ==================== DAILY NUDGE (15:00) ====================
    
    async def _daily_nudge_job(self):
        """Bugun harajat kiritmaganlarga soat 15:00 da eslatma"""
        while self._running:
            try:
                wait = _next_time(15, 0)
                logger.info(f"📝 Daily nudge {wait/3600:.1f} soatdan keyin (15:00)")
                
                await asyncio.sleep(wait)
                
                if not self._running:
                    break
                
                self._reset_daily_tracking()
                await self._send_daily_nudges()
                
                # Keyingi kunga o'tish uchun kutish
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daily nudge error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_daily_nudges(self):
        """Bugun passiv bo'lgan userlarga nudge yuborish"""
        try:
            db = await get_database()
            
            # Bugun transaction kiritganlar
            today_active_ids = await self._get_today_active_user_ids()
            
            # BARCHA /start bosgan userlar (faqat blocked bo'lmaganlar)
            all_users = await self._get_all_users()
            
            sent_count = 0
            failed_count = 0
            
            for user in all_users:
                user_id = user.get("id")
                telegram_id = user.get("telegram_id")
                
                if not telegram_id:
                    continue
                
                # Bugun allaqachon jo'natilgan bo'lsa — o'tkazib yubor
                if telegram_id in self._sent_today["nudge"]:
                    continue
                
                # Bugun faol bo'lsa — nudge kerak emas
                if user_id in today_active_ids:
                    continue
                
                try:
                    lang = user.get("language", "uz")
                    messages = DAILY_NUDGE_UZ if lang == "uz" else DAILY_NUDGE_RU
                    message = random.choice(messages)
                    
                    # PRO bo'lmagan userlarga PRO teaser
                    try:
                        from app.subscription_handlers import is_user_pro
                        is_pro = await is_user_pro(telegram_id)
                    except:
                        is_pro = False
                    
                    if not is_pro:
                        message += random.choice(PRO_TEASERS_UZ)
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "✍️ Xarajat kiritish" if lang == "uz" else "✍️ Записать расход",
                            callback_data="add_expense"
                        )],
                    ])
                    
                    if not is_pro:
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "✍️ Xarajat kiritish" if lang == "uz" else "✍️ Записать расход",
                                callback_data="add_expense"
                            )],
                            [InlineKeyboardButton("💎 PRO ga o'tish", callback_data="show_pricing")]
                        ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    
                    self._sent_today["nudge"].add(telegram_id)
                    sent_count += 1
                    await asyncio.sleep(0.15)  # Rate limiting
                    
                except TelegramError as e:
                    if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                        await self._mark_user_blocked(user_id)
                    failed_count += 1
                except Exception as e:
                    failed_count += 1
            
            logger.info(f"✅ Daily nudge: {sent_count} yuborildi, {failed_count} xato, {len(today_active_ids)} bugun faol")
            
        except Exception as e:
            logger.error(f"Daily nudge batch error: {e}")
    
    # ==================== EVENING SUMMARY (21:00) ====================
    
    async def _evening_summary_job(self):
        """Kechki hisobot soat 21:00"""
        while self._running:
            try:
                wait = _next_time(21, 0)
                logger.info(f"🌙 Evening summary {wait/3600:.1f} soatdan keyin (21:00)")
                
                await asyncio.sleep(wait)
                
                if not self._running:
                    break
                
                self._reset_daily_tracking()
                await self._send_evening_summaries()
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evening summary error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_evening_summaries(self):
        """Bugun faol bo'lgan userlarga kechki hisobot"""
        try:
            today_users = await self._get_users_with_today_transactions()
            
            sent_count = 0
            for user in today_users:
                telegram_id = user.get("telegram_id")
                user_id = user.get("id")
                
                if not telegram_id or telegram_id in self._sent_today["evening"]:
                    continue
                
                try:
                    today_stats = await self._get_today_stats(user_id)
                    if not today_stats:
                        continue
                    
                    income = today_stats.get("income", 0)
                    expense = today_stats.get("expense", 0)
                    tx_count = today_stats.get("count", 0)
                    balance = income - expense
                    
                    greeting = random.choice(EVENING_SUMMARIES_UZ)
                    
                    message = (
                        f"{greeting}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📝 Kiritilgan: *{tx_count}* ta tranzaksiya\n"
                    )
                    
                    if income > 0:
                        message += f"💰 Daromad: *+{format_number(int(income))}* so'm\n"
                    if expense > 0:
                        message += f"💸 Xarajat: *-{format_number(int(expense))}* so'm\n"
                    
                    if balance > 0:
                        message += f"\n✅ Balans: *+{format_number(int(balance))}* so'm\n🎉 Ajoyib!"
                    elif balance < 0:
                        message += f"\n📉 Balans: *{format_number(int(balance))}* so'm\n💡 Ertaga tejashga harakat qiling!"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📊 Statistika", callback_data="pro_statistics")],
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    
                    self._sent_today["evening"].add(telegram_id)
                    sent_count += 1
                    await asyncio.sleep(0.15)
                    
                except TelegramError as e:
                    if "blocked" in str(e).lower():
                        await self._mark_user_blocked(user_id)
                except Exception:
                    pass
            
            logger.info(f"✅ Evening summaries: {sent_count} yuborildi")
            
        except Exception as e:
            logger.error(f"Evening summary error: {e}")
    
    # ==================== MORNING MOTIVATION (08:00) ====================
    
    async def _morning_motivation_job(self):
        """Ertalabki motivatsiya soat 08:00"""
        while self._running:
            try:
                wait = _next_time(8, 0)
                logger.info(f"☀️ Morning motivation {wait/3600:.1f} soatdan keyin (08:00)")
                
                await asyncio.sleep(wait)
                
                if not self._running:
                    break
                
                self._reset_daily_tracking()
                await self._send_morning_motivation()
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Morning motivation error: {e}")
                await asyncio.sleep(3600)
    
    async def _send_morning_motivation(self):
        """Ertalabki motivatsiya - BARCHA userlarga"""
        try:
            all_users = await self._get_all_users()
            
            sent_count = 0
            for user in all_users:
                telegram_id = user.get("telegram_id")
                
                if not telegram_id or telegram_id in self._sent_today["morning"]:
                    continue
                
                try:
                    greeting = random.choice(MORNING_GREETINGS_UZ)
                    message = f"{greeting}\n\n💬 Bugungi xarajatni kiritish uchun shunchaki yozing!"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Xarajat kiritish", callback_data="add_expense")],
                    ])
                    
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    
                    self._sent_today["morning"].add(telegram_id)
                    sent_count += 1
                    await asyncio.sleep(0.15)
                    
                except TelegramError as e:
                    if "blocked" in str(e).lower():
                        await self._mark_user_blocked(user.get("id"))
                except Exception:
                    pass
            
            logger.info(f"✅ Morning motivation: {sent_count} yuborildi")
            
        except Exception as e:
            logger.error(f"Morning motivation error: {e}")
    
    # ==================== HELPER METHODS ====================
    
    async def _get_all_users(self) -> List[Dict[str, Any]]:
        """BARCHA /start bosgan userlarni olish (blocked bo'lmaganlar)"""
        db = await get_database()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, telegram_id, language, first_name
                    FROM users
                    WHERE telegram_id IS NOT NULL
                    AND COALESCE(notifications_blocked, false) = false
                """)
                return [dict(row) for row in rows]
        return []
    
    async def _get_today_active_user_ids(self) -> set:
        """Bugun transaction kiritgan user ID larini qaytaradi"""
        db = await get_database()
        today = now_uz().date()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT user_id FROM transactions WHERE DATE(created_at) = $1", 
                    today
                )
                return {row["user_id"] for row in rows}
        return set()
    
    async def _get_users_with_today_transactions(self) -> List[Dict[str, Any]]:
        """Bugun transaction kiritgan userlarni olish"""
        db = await get_database()
        today = now_uz().date()
        
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT u.id, u.telegram_id, u.language
                    FROM users u
                    JOIN transactions t ON t.user_id = u.id
                    WHERE DATE(t.created_at) = $1
                    AND u.telegram_id IS NOT NULL
                """, today)
                return [dict(row) for row in rows]
        return []
    
    async def _get_today_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Bugungi tranzaksiya statistikasi"""
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
        return None
    
    async def _mark_user_blocked(self, user_id: int):
        """User botni bloklagan"""
        if not user_id:
            return
        db = await get_database()
        if db.is_postgres:
            try:
                async with db._pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE users SET notifications_blocked = true WHERE id = $1", 
                        user_id
                    )
            except Exception:
                pass


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
                "💡 Xarajatlaringizni yozib borish\n"
                "moliyaviy erkinlikning birinchi qadami!"
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
