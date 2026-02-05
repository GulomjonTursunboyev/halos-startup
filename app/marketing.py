"""
HALOS Marketing Module
UTM Tracking, Welcome Flow, Re-engagement, Promo Codes, Admin Analytics
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.database import get_database
from app.languages import get_message, format_number

logger = logging.getLogger(__name__)

# Timezone for Tashkent
UZ_TZ = timezone(timedelta(hours=5))


def now_uz():
    return datetime.now(UZ_TZ)


# ==================== UTM SOURCE DEFINITIONS ====================

class UTMSource(Enum):
    """Marketing channel sources"""
    TELEGRAM_ADS = "tgads"      # Telegram Ads platformasi
    CHANNEL = "ch"              # Kanallardan
    INFLUENCER = "inf"          # Influencer'lardan
    ORGANIC = "organic"         # O'z-o'zidan
    DIRECT = "direct"           # To'g'ridan-to'g'ri
    PROMO = "promo"             # Promo kampaniyalardan


@dataclass
class UTMData:
    """UTM tracking data"""
    source: str           # tgads, ch, inf, promo
    campaign: str         # kredit, oila, biznes
    medium: str = ""      # post, story, message
    content: str = ""     # variant_a, variant_b
    term: str = ""        # additional keywords


# ==================== PROMO CODES SYSTEM ====================

PROMO_CODES: Dict[str, Dict[str, Any]] = {
    # Launch promo - 1 hafta bepul
    "HALOSWEEK": {
        "type": "free_days",
        "value": 7,
        "max_uses": -1,
        "current_uses": 0,
        "expires": "2027-12-31",
        "description_uz": "1 haftalik bepul PRO",
        "description_ru": "1 неделя бесплатно PRO",
    },
    # Yangi yil aktsiyasi - 50% chegirma
    "NEWYEAR26": {
        "type": "discount_percent",
        "value": 50,
        "max_uses": 100,
        "current_uses": 0,
        "expires": "2026-02-28",
        "description_uz": "50% chegirma",
        "description_ru": "Скидка 50%",
    },
    # Influencer promo - 1 oy bepul
    "JASUR100": {
        "type": "free_days",
        "value": 30,
        "max_uses": 100,
        "current_uses": 0,
        "expires": "2026-06-30",
        "description_uz": "1 oylik bepul PRO (Jasur)",
        "description_ru": "1 месяц бесплатно PRO (Jasur)",
    },
    # Channel partnership
    "INVESTUZ": {
        "type": "free_days",
        "value": 14,
        "max_uses": 500,
        "current_uses": 0,
        "expires": "2026-12-31",
        "description_uz": "2 haftalik bepul PRO",
        "description_ru": "2 недели бесплатно PRO",
    },
    # First 100 users
    "HALOS100": {
        "type": "free_days",
        "value": 30,
        "max_uses": 100,
        "current_uses": 0,
        "expires": "2026-03-31",
        "description_uz": "1 oylik bepul PRO (birinchi 100 user)",
        "description_ru": "1 месяц бесплатно PRO (первые 100)",
    },
    # Test promo
    "TEST123": {
        "type": "free_days",
        "value": 3,
        "max_uses": -1,
        "current_uses": 0,
        "expires": "2030-12-31",
        "description_uz": "Test promo",
        "description_ru": "Тестовый промо",
    },
}


def validate_promo_code(code: str) -> Optional[Dict[str, Any]]:
    """Validate promo code and return details"""
    code = code.upper().strip()
    
    if code not in PROMO_CODES:
        return None
    
    promo = PROMO_CODES[code]
    
    # Check expiration
    if promo.get("expires"):
        try:
            expires_date = datetime.strptime(promo["expires"], "%Y-%m-%d")
            if datetime.now() > expires_date:
                return None
        except:
            pass
    
    # Check max uses
    if promo.get("max_uses", -1) != -1:
        if promo.get("current_uses", 0) >= promo["max_uses"]:
            return None
    
    return {
        "code": code,
        "type": promo["type"],
        "value": promo["value"],
        "description_uz": promo.get("description_uz", ""),
        "description_ru": promo.get("description_ru", ""),
    }


async def apply_promo_code(telegram_id: int, code: str) -> Dict[str, Any]:
    """Apply promo code to user account"""
    promo = validate_promo_code(code)
    
    if not promo:
        return {"success": False, "error": "invalid_code"}
    
    db = await get_database()
    user = await db.get_user(telegram_id)
    
    if not user:
        return {"success": False, "error": "user_not_found"}
    
    # Check if user already used this code
    used_promos = user.get("used_promo_codes", "") or ""
    if code.upper() in used_promos.split(","):
        return {"success": False, "error": "already_used"}
    
    # Apply promo based on type
    if promo["type"] == "free_days":
        # Add free PRO days
        days = promo["value"]
        current_expires = user.get("subscription_expires")
        
        if current_expires:
            if isinstance(current_expires, str):
                current_expires = datetime.fromisoformat(current_expires)
            new_expires = current_expires + timedelta(days=days)
        else:
            new_expires = datetime.now() + timedelta(days=days)
        
        await db.update_subscription(
            telegram_id,
            tier="pro",
            plan_id="promo_" + code.lower(),
            expires=new_expires
        )
        
        # Mark promo as used
        new_used_promos = f"{used_promos},{code.upper()}" if used_promos else code.upper()
        await db.update_user(telegram_id, used_promo_codes=new_used_promos)
        
        # Increment usage counter
        if code.upper() in PROMO_CODES:
            PROMO_CODES[code.upper()]["current_uses"] += 1
        
        return {
            "success": True,
            "type": "free_days",
            "days": days,
            "expires": new_expires,
        }
    
    elif promo["type"] == "discount_percent":
        # Return discount info (to be applied at payment)
        return {
            "success": True,
            "type": "discount_percent",
            "percent": promo["value"],
        }
    
    return {"success": False, "error": "unknown_type"}


# ==================== UTM TRACKING ====================

def parse_utm_from_start(start_param: str) -> Optional[UTMData]:
    """
    Parse UTM data from /start parameter
    
    Format: source_campaign_medium_content
    Examples:
        - tgads_kredit           → Telegram Ads, kredit campaign
        - ch_invest_uz           → Channel @invest_uz
        - inf_jasur_story        → Influencer Jasur, story
        - promo_newyear          → Promo campaign
    """
    if not start_param:
        return None
    
    parts = start_param.lower().split("_")
    
    if len(parts) < 1:
        return None
    
    source = parts[0]
    campaign = parts[1] if len(parts) > 1 else ""
    medium = parts[2] if len(parts) > 2 else ""
    content = parts[3] if len(parts) > 3 else ""
    
    return UTMData(
        source=source,
        campaign=campaign,
        medium=medium,
        content=content,
    )


async def track_user_source(telegram_id: int, start_param: str) -> None:
    """Track user's marketing source"""
    db = await get_database()
    
    utm_data = parse_utm_from_start(start_param)
    
    if utm_data:
        source = utm_data.source
        campaign = utm_data.campaign
        medium = utm_data.medium
    else:
        source = "direct"
        campaign = ""
        medium = ""
    
    # Save to database
    await db.update_user(
        telegram_id,
        utm_source=source,
        utm_campaign=campaign,
        utm_medium=medium,
        utm_raw=start_param or "direct"
    )
    
    logger.info(f"User {telegram_id} tracked: source={source}, campaign={campaign}")


# ==================== WELCOME FLOW ====================

WELCOME_MESSAGES = {
    "uz": {
        "new_user": (
            "🚀 *HALOS ga xush kelibsiz!*\n\n"
            "Men sizga qarzdan tezroq chiqishga va\n"
            "moliyaviy erkinlikka erishishga yordam beraman.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *HALOS bilan siz:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Qarzdan qachon qutulishingizni bilasiz\n"
            "✅ Xarajatlaringizni ovoz bilan yozasiz\n"
            "✅ Kunlik hisobotlarni ko'rasiz\n"
            "✅ Pul qayerga ketayotganini tushunasiz\n\n"
            "🎁 *Sizga 3 kunlik BEPUL PRO taqdim etildi!*\n\n"
            "Boshlash uchun telefon raqamingizni ulashing 👇"
        ),
        "from_ads": (
            "👋 *Salom!*\n\n"
            "Telegram reklamasidan keldingiz - to'g'ri tanlov!\n\n"
            "🎯 *HALOS* - bu qarzdan chiqish uchun eng yaxshi yordamchi.\n\n"
            "🎁 *Sizga maxsus sovg'a:*\n"
            "3 kunlik BEPUL PRO + barcha imkoniyatlar!\n\n"
            "Boshlash uchun telefon raqamingizni ulashing 👇"
        ),
        "from_channel": (
            "👋 *Xush kelibsiz!*\n\n"
            "{channel} kanalidan keldingiz!\n\n"
            "🎁 *Kanalingiz uchun maxsus:*\n"
            "Promo-kod: *{promo_code}*\n"
            "Bu kod bilan 2 hafta BEPUL PRO olasiz!\n\n"
            "Boshlash uchun telefon raqamingizni ulashing 👇"
        ),
        "from_influencer": (
            "👋 *Salom!*\n\n"
            "*{influencer}* tavsiyasi bilan keldingiz!\n\n"
            "🎁 *Sizga maxsus sovg'a:*\n"
            "{influencer} promo-kodi: *{promo_code}*\n\n"
            "Boshlash uchun telefon raqamingizni ulashing 👇"
        ),
    },
    "ru": {
        "new_user": (
            "🚀 *Добро пожаловать в HALOS!*\n\n"
            "Я помогу вам быстрее выйти из долгов и\n"
            "достичь финансовой свободы.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *С HALOS вы:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Узнаете когда освободитесь от долгов\n"
            "✅ Записываете расходы голосом\n"
            "✅ Видите ежедневные отчёты\n"
            "✅ Понимаете куда уходят деньги\n\n"
            "🎁 *Вам подарен 3-дневный БЕСПЛАТНЫЙ PRO!*\n\n"
            "Для начала поделитесь номером телефона 👇"
        ),
        "from_ads": (
            "👋 *Привет!*\n\n"
            "Вы пришли из Telegram рекламы - правильный выбор!\n\n"
            "🎯 *HALOS* - лучший помощник для выхода из долгов.\n\n"
            "🎁 *Специально для вас:*\n"
            "3 дня БЕСПЛАТНО PRO + все функции!\n\n"
            "Для начала поделитесь номером телефона 👇"
        ),
        "from_channel": (
            "👋 *Добро пожаловать!*\n\n"
            "Вы пришли из канала {channel}!\n\n"
            "🎁 *Специально для канала:*\n"
            "Промо-код: *{promo_code}*\n"
            "С этим кодом 2 недели БЕСПЛАТНО PRO!\n\n"
            "Для начала поделитесь номером телефона 👇"
        ),
        "from_influencer": (
            "👋 *Привет!*\n\n"
            "Вы пришли по рекомендации *{influencer}*!\n\n"
            "🎁 *Специальный подарок:*\n"
            "Промо-код от {influencer}: *{promo_code}*\n\n"
            "Для начала поделитесь номером телефона 👇"
        ),
    }
}

# Channel to promo code mapping
CHANNEL_PROMOS = {
    "invest_uz": "INVESTUZ",
    "invest": "INVESTUZ",
    "business": "HALOSWEEK",
    "pul": "HALOSWEEK",
}

# Influencer to promo code mapping
INFLUENCER_PROMOS = {
    "jasur": "JASUR100",
    "dilnoza": "HALOSWEEK",
    "aziz": "HALOSWEEK",
}


def get_welcome_message(lang: str, utm_data: Optional[UTMData]) -> str:
    """Get personalized welcome message based on UTM source"""
    messages = WELCOME_MESSAGES.get(lang, WELCOME_MESSAGES["uz"])
    
    if not utm_data:
        return messages["new_user"]
    
    if utm_data.source == "tgads":
        return messages["from_ads"]
    
    elif utm_data.source == "ch":
        channel = utm_data.campaign
        promo_code = CHANNEL_PROMOS.get(channel, "HALOSWEEK")
        return messages["from_channel"].format(
            channel=f"@{channel}",
            promo_code=promo_code
        )
    
    elif utm_data.source == "inf":
        influencer = utm_data.campaign.capitalize()
        promo_code = INFLUENCER_PROMOS.get(utm_data.campaign.lower(), "HALOSWEEK")
        return messages["from_influencer"].format(
            influencer=influencer,
            promo_code=promo_code
        )
    
    return messages["new_user"]


# ==================== RE-ENGAGEMENT SYSTEM ====================

RE_ENGAGEMENT_MESSAGES = {
    "uz": {
        # 3 kun inaktiv
        "inactive_3_days": (
            "👋 *Salom, {name}!*\n\n"
            "3 kun davomida sizni ko'rmadik.\n"
            "Bugungi xarajatlaringizni yozib qo'ying!\n\n"
            "🎤 Ovoz bilan: _\"15 ming choy\"_\n"
            "✍️ Matn bilan: _\"choy 15000\"_\n\n"
            "Moliyaviy muvaffaqiyat har kungi nazoratda! 📊"
        ),
        # 7 kun inaktiv
        "inactive_7_days": (
            "😔 *{name}, sizni sog'indik!*\n\n"
            "1 haftadir HALOS dan foydalanmadingiz.\n\n"
            "📊 Esingizda bo'lsin:\n"
            "• Kunlik xarajatlarni yozish = nazorat\n"
            "• Nazorat = qarzdan tezroq chiqish\n\n"
            "🎁 Qaytib kelganingiz uchun +3 kun PRO sovg'a!\n"
            "Promo-kod: *WELCOME3*"
        ),
        # Trial tugashidan 1 kun oldin
        "trial_ending_soon": (
            "⏰ *{name}, trial muddatingiz tugamoqda!*\n\n"
            "Sizda 3 kunlik bepul PRO ertaga tugaydi.\n\n"
            "📊 Bu vaqt ichida siz:\n"
            "• {voice_count} ta ovozli xabar yubordingiz\n"
            "• {tx_count} ta tranzaksiya qo'shdingiz\n\n"
            "PRO ga o'ting va davom eting! 💎"
        ),
        # Trial tugadi
        "trial_ended": (
            "⚠️ *{name}, trial muddatingiz tugadi*\n\n"
            "Endi ovozli AI va batafsil hisobotlardan\n"
            "foydalanish uchun PRO kerak.\n\n"
            "🎁 *Maxsus taklif:*\n"
            "Bugun PRO olsangiz — 20% chegirma!\n"
            "Kod: *COMEBACK20*"
        ),
        # PRO tugashidan 3 kun oldin
        "pro_expiring_soon": (
            "⏰ *{name}, PRO muddatingiz tugamoqda!*\n\n"
            "3 kun ichida PRO obunangiz tugaydi.\n\n"
            "📊 PRO bilan siz bu oyda:\n"
            "• {savings} so'm tejashni aniqladingiz\n"
            "• {tx_count} ta tranzaksiya qayd qildingiz\n\n"
            "Obunani yangilang va davom eting! 💎"
        ),
        # Haftalik progress
        "weekly_progress": (
            "📊 *Haftalik hisobotingiz tayyor!*\n\n"
            "💰 Bu hafta:\n"
            "• Kirim: +{income} so'm\n"
            "• Chiqim: -{expense} so'm\n"
            "• Balans: {balance} so'm\n\n"
            "🎯 Maqsad: Keyingi haftada 10% kam sarflang!"
        ),
    },
    "ru": {
        "inactive_3_days": (
            "👋 *Привет, {name}!*\n\n"
            "Мы не видели вас 3 дня.\n"
            "Запишите сегодняшние расходы!\n\n"
            "🎤 Голосом: _\"15 тысяч чай\"_\n"
            "✍️ Текстом: _\"чай 15000\"_\n\n"
            "Финансовый успех в ежедневном контроле! 📊"
        ),
        "inactive_7_days": (
            "😔 *{name}, мы скучали!*\n\n"
            "Вы не использовали HALOS неделю.\n\n"
            "📊 Помните:\n"
            "• Записывать расходы = контроль\n"
            "• Контроль = быстрее выход из долгов\n\n"
            "🎁 За возвращение +3 дня PRO!\n"
            "Промо-код: *WELCOME3*"
        ),
        "trial_ending_soon": (
            "⏰ *{name}, ваш trial заканчивается!*\n\n"
            "3-дневный бесплатный PRO заканчивается завтра.\n\n"
            "📊 За это время вы:\n"
            "• Отправили {voice_count} голосовых\n"
            "• Добавили {tx_count} транзакций\n\n"
            "Перейдите на PRO и продолжайте! 💎"
        ),
        "trial_ended": (
            "⚠️ *{name}, trial закончился*\n\n"
            "Для голосового AI и детальных отчётов\n"
            "теперь нужен PRO.\n\n"
            "🎁 *Специальное предложение:*\n"
            "PRO сегодня — скидка 20%!\n"
            "Код: *COMEBACK20*"
        ),
        "pro_expiring_soon": (
            "⏰ *{name}, ваш PRO заканчивается!*\n\n"
            "Через 3 дня PRO подписка истекает.\n\n"
            "📊 С PRO в этом месяце вы:\n"
            "• Выявили {savings} сум экономии\n"
            "• Записали {tx_count} транзакций\n\n"
            "Обновите подписку и продолжайте! 💎"
        ),
        "weekly_progress": (
            "📊 *Ваш недельный отчёт готов!*\n\n"
            "💰 На этой неделе:\n"
            "• Доход: +{income} сум\n"
            "• Расход: -{expense} сум\n"
            "• Баланс: {balance} сум\n\n"
            "🎯 Цель: На следующей неделе тратить на 10% меньше!"
        ),
    }
}


async def send_reengagement_message(
    bot: Bot,
    telegram_id: int,
    message_type: str,
    lang: str = "uz",
    **kwargs
) -> bool:
    """Send re-engagement message to user"""
    messages = RE_ENGAGEMENT_MESSAGES.get(lang, RE_ENGAGEMENT_MESSAGES["uz"])
    
    if message_type not in messages:
        logger.error(f"Unknown re-engagement message type: {message_type}")
        return False
    
    message = messages[message_type]
    
    # Format message with kwargs
    try:
        message = message.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing key in re-engagement message: {e}")
        return False
    
    # Add appropriate buttons
    keyboard = []
    
    if message_type in ["inactive_3_days", "inactive_7_days"]:
        keyboard.append([InlineKeyboardButton(
            "💰 Balans" if lang == "uz" else "💰 Баланс",
            callback_data="menu_balance"
        )])
    
    elif message_type in ["trial_ending_soon", "trial_ended", "pro_expiring_soon"]:
        keyboard.append([InlineKeyboardButton(
            "💎 PRO olish" if lang == "uz" else "💎 Получить PRO",
            callback_data="show_pricing"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Log the engagement
        db = await get_database()
        await db.log_marketing_event(
            telegram_id=telegram_id,
            event_type="reengagement_sent",
            event_data={"message_type": message_type}
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to send re-engagement message to {telegram_id}: {e}")
        return False


# ==================== ADMIN ANALYTICS ====================

async def get_marketing_stats(days: int = 30) -> Dict[str, Any]:
    """Get marketing analytics for admin dashboard"""
    db = await get_database()
    
    # Calculate date range
    end_date = now_uz()
    start_date = end_date - timedelta(days=days)
    
    stats = {
        "period_days": days,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_users": 0,
        "new_users": 0,
        "active_users": 0,
        "pro_users": 0,
        "trial_users": 0,
        "conversion_rate": 0.0,
        "sources": {},
        "campaigns": {},
        "daily_signups": [],
        "promo_usage": {},
    }
    
    try:
        # Total users
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                # Total users
                row = await conn.fetchrow("SELECT COUNT(*) as count FROM users")
                stats["total_users"] = row["count"] if row else 0
                
                # New users in period
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM users WHERE created_at >= $1",
                    start_date
                )
                stats["new_users"] = row["count"] if row else 0
                
                # Active users (last 7 days)
                active_date = end_date - timedelta(days=7)
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM users WHERE last_active >= $1",
                    active_date
                )
                stats["active_users"] = row["count"] if row else 0
                
                # PRO users
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM users WHERE subscription_tier = 'pro'"
                )
                stats["pro_users"] = row["count"] if row else 0
                
                # Trial users
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM users WHERE subscription_tier = 'trial'"
                )
                stats["trial_users"] = row["count"] if row else 0
                
                # Sources breakdown
                rows = await conn.fetch("""
                    SELECT utm_source, COUNT(*) as count 
                    FROM users 
                    WHERE created_at >= $1 AND utm_source IS NOT NULL
                    GROUP BY utm_source
                    ORDER BY count DESC
                """, start_date)
                stats["sources"] = {row["utm_source"]: row["count"] for row in rows}
                
                # Campaigns breakdown
                rows = await conn.fetch("""
                    SELECT utm_campaign, COUNT(*) as count 
                    FROM users 
                    WHERE created_at >= $1 AND utm_campaign IS NOT NULL AND utm_campaign != ''
                    GROUP BY utm_campaign
                    ORDER BY count DESC
                """, start_date)
                stats["campaigns"] = {row["utm_campaign"]: row["count"] for row in rows}
                
                # Daily signups
                rows = await conn.fetch("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= $1
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """, start_date)
                stats["daily_signups"] = [
                    {"date": str(row["date"]), "count": row["count"]} 
                    for row in rows
                ]
                
        # Calculate conversion rate
        if stats["new_users"] > 0:
            stats["conversion_rate"] = round(
                (stats["pro_users"] / stats["new_users"]) * 100, 2
            )
        
        # Promo code usage
        for code, promo in PROMO_CODES.items():
            stats["promo_usage"][code] = promo.get("current_uses", 0)
        
    except Exception as e:
        logger.error(f"Error getting marketing stats: {e}")
    
    return stats


def format_marketing_stats_message(stats: Dict[str, Any], lang: str = "uz") -> str:
    """Format marketing stats for admin message"""
    if lang == "uz":
        msg = (
            "📊 *MARKETING STATISTIKASI*\n"
            f"📅 Davr: {stats['start_date']} — {stats['end_date']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "👥 *FOYDALANUVCHILAR:*\n"
            f"├ Jami: *{stats['total_users']:,}*\n"
            f"├ Yangi ({stats['period_days']} kun): *{stats['new_users']:,}*\n"
            f"├ Faol (7 kun): *{stats['active_users']:,}*\n"
            f"├ PRO: *{stats['pro_users']:,}*\n"
            f"└ Trial: *{stats['trial_users']:,}*\n\n"
            
            f"📈 *Konversiya:* {stats['conversion_rate']}%\n\n"
        )
        
        if stats["sources"]:
            msg += "📡 *MANBALAR:*\n"
            for source, count in stats["sources"].items():
                source_name = {
                    "tgads": "Telegram Ads",
                    "ch": "Kanallar",
                    "inf": "Influencer",
                    "direct": "To'g'ridan-to'g'ri",
                    "organic": "Organik",
                    "promo": "Promo",
                }.get(source, source)
                msg += f"├ {source_name}: *{count:,}*\n"
            msg += "\n"
        
        if stats["campaigns"]:
            msg += "🎯 *KAMPANIYALAR:*\n"
            for campaign, count in list(stats["campaigns"].items())[:5]:
                msg += f"├ {campaign}: *{count:,}*\n"
            msg += "\n"
        
        if any(v > 0 for v in stats["promo_usage"].values()):
            msg += "🎁 *PROMO KODLAR:*\n"
            for code, uses in stats["promo_usage"].items():
                if uses > 0:
                    msg += f"├ {code}: *{uses}* marta\n"
            msg += "\n"
        
    else:
        msg = (
            "📊 *МАРКЕТИНГ СТАТИСТИКА*\n"
            f"📅 Период: {stats['start_date']} — {stats['end_date']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            "👥 *ПОЛЬЗОВАТЕЛИ:*\n"
            f"├ Всего: *{stats['total_users']:,}*\n"
            f"├ Новых ({stats['period_days']} дн): *{stats['new_users']:,}*\n"
            f"├ Активных (7 дн): *{stats['active_users']:,}*\n"
            f"├ PRO: *{stats['pro_users']:,}*\n"
            f"└ Trial: *{stats['trial_users']:,}*\n\n"
            
            f"📈 *Конверсия:* {stats['conversion_rate']}%\n\n"
        )
        
        if stats["sources"]:
            msg += "📡 *ИСТОЧНИКИ:*\n"
            for source, count in stats["sources"].items():
                source_name = {
                    "tgads": "Telegram Ads",
                    "ch": "Каналы",
                    "inf": "Инфлюенсеры",
                    "direct": "Прямой",
                    "organic": "Органика",
                    "promo": "Промо",
                }.get(source, source)
                msg += f"├ {source_name}: *{count:,}*\n"
            msg += "\n"
    
    return msg


# ==================== SOCIAL PROOF ====================

async def get_social_proof_stats() -> Dict[str, Any]:
    """Get real-time social proof statistics"""
    db = await get_database()
    
    stats = {
        "total_users": 0,
        "today_signups": 0,
        "today_transactions": 0,
        "total_transactions": 0,
        "recent_pro_user": None,
    }
    
    try:
        if db.is_postgres:
            async with db._pool.acquire() as conn:
                # Total users
                row = await conn.fetchrow("SELECT COUNT(*) as count FROM users")
                stats["total_users"] = row["count"] if row else 0
                
                # Today signups
                today = now_uz().date()
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = $1",
                    today
                )
                stats["today_signups"] = row["count"] if row else 0
                
                # Today transactions
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM transactions WHERE DATE(created_at) = $1",
                    today
                )
                stats["today_transactions"] = row["count"] if row else 0
                
                # Total transactions
                row = await conn.fetchrow("SELECT COUNT(*) as count FROM transactions")
                stats["total_transactions"] = row["count"] if row else 0
                
                # Recent PRO user (last 24h)
                yesterday = now_uz() - timedelta(days=1)
                row = await conn.fetchrow("""
                    SELECT first_name, created_at 
                    FROM users 
                    WHERE subscription_tier = 'pro' 
                    AND updated_at >= $1
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, yesterday)
                if row:
                    stats["recent_pro_user"] = {
                        "name": row["first_name"],
                        "time": row["created_at"],
                    }
                    
    except Exception as e:
        logger.error(f"Error getting social proof stats: {e}")
    
    return stats


def format_social_proof_message(stats: Dict[str, Any], lang: str = "uz") -> str:
    """Format social proof for display"""
    if lang == "uz":
        parts = []
        
        if stats["total_users"] >= 100:
            parts.append(f"👥 *{stats['total_users']:,}+* foydalanuvchi ishonadi")
        
        if stats["today_signups"] > 0:
            parts.append(f"🆕 Bugun *{stats['today_signups']}* kishi qo'shildi")
        
        if stats["today_transactions"] > 0:
            parts.append(f"📝 Bugun *{stats['today_transactions']}* xarajat yozildi")
        
        if stats["recent_pro_user"]:
            name = stats["recent_pro_user"]["name"] or "Foydalanuvchi"
            parts.append(f"🎉 *{name}* hozirgina PRO ga o'tdi!")
        
        return "\n".join(parts)
    else:
        parts = []
        
        if stats["total_users"] >= 100:
            parts.append(f"👥 *{stats['total_users']:,}+* пользователей доверяют")
        
        if stats["today_signups"] > 0:
            parts.append(f"🆕 Сегодня присоединились *{stats['today_signups']}*")
        
        if stats["today_transactions"] > 0:
            parts.append(f"📝 Сегодня записано *{stats['today_transactions']}* расходов")
        
        if stats["recent_pro_user"]:
            name = stats["recent_pro_user"]["name"] or "Пользователь"
            parts.append(f"🎉 *{name}* только что перешёл на PRO!")
        
        return "\n".join(parts)


# ==================== MARKETING EVENT HANDLERS ====================

async def on_user_registered(telegram_id: int, utm_data: Optional[UTMData]) -> None:
    """Called when new user registers - for analytics"""
    db = await get_database()
    
    await db.log_marketing_event(
        telegram_id=telegram_id,
        event_type="user_registered",
        event_data={
            "source": utm_data.source if utm_data else "direct",
            "campaign": utm_data.campaign if utm_data else "",
        }
    )


async def on_trial_activated(telegram_id: int) -> None:
    """Called when trial is activated"""
    db = await get_database()
    
    await db.log_marketing_event(
        telegram_id=telegram_id,
        event_type="trial_activated",
        event_data={}
    )


async def on_pro_purchased(telegram_id: int, plan_id: str, amount: float) -> None:
    """Called when PRO is purchased"""
    db = await get_database()
    
    await db.log_marketing_event(
        telegram_id=telegram_id,
        event_type="pro_purchased",
        event_data={
            "plan_id": plan_id,
            "amount": amount,
        }
    )


async def on_promo_used(telegram_id: int, promo_code: str) -> None:
    """Called when promo code is used"""
    db = await get_database()
    
    await db.log_marketing_event(
        telegram_id=telegram_id,
        event_type="promo_used",
        event_data={"promo_code": promo_code}
    )
