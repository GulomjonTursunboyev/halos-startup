"""
Report Image Generator - Hisobotlarni rasm ko'rinishida yaratish
Gibrid usul: Kunlik=matn, Haftalik=matn+grafik, Oylik=to'liq rasm
"""

import io
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import PIL (Pillow)
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available - image reports will be disabled")

# Constants
REPORT_WIDTH = 800
REPORT_HEIGHT = 1000
WEEKLY_HEIGHT = 600
MONTHLY_HEIGHT = 1200

# Colors
COLORS = {
    "background": "#1a1a2e",
    "card_bg": "#16213e",
    "primary": "#0f3460",
    "accent": "#e94560",
    "success": "#00d9a5",
    "warning": "#ffc107",
    "text_white": "#ffffff",
    "text_gray": "#a0a0a0",
    "income": "#00d9a5",
    "expense": "#e94560",
    "debt_given": "#ffc107",
    "debt_taken": "#ff6b6b",
}

# Category colors for pie chart
CATEGORY_COLORS = [
    "#e94560", "#00d9a5", "#ffc107", "#3498db", "#9b59b6",
    "#1abc9c", "#e74c3c", "#2ecc71", "#f39c12", "#8e44ad"
]


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_font(size: int = 20, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get font with fallback for different systems"""
    font_paths = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        # Mac
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
    
    # Fallback to default
    return ImageFont.load_default()


def format_number_short(num: float) -> str:
    """Format number in short form: 1.5M, 500K, etc."""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.0f}K"
    else:
        return f"{num:.0f}"


def draw_rounded_rect(draw: ImageDraw, coords: Tuple, radius: int, fill: str):
    """Draw a rounded rectangle"""
    x1, y1, x2, y2 = coords
    fill_rgb = hex_to_rgb(fill)
    
    # Draw rectangles
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill_rgb)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill_rgb)
    
    # Draw corners
    draw.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill_rgb)
    draw.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill_rgb)
    draw.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill_rgb)
    draw.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill_rgb)


def draw_progress_bar(draw: ImageDraw, x: int, y: int, width: int, height: int, 
                      progress: float, color: str, bg_color: str = "#333333"):
    """Draw a progress bar"""
    # Background
    draw.rectangle([x, y, x + width, y + height], fill=hex_to_rgb(bg_color))
    # Progress
    progress_width = int(width * min(progress, 1.0))
    if progress_width > 0:
        draw.rectangle([x, y, x + progress_width, y + height], fill=hex_to_rgb(color))


def draw_mini_bar_chart(draw: ImageDraw, x: int, y: int, width: int, height: int,
                        data: Dict[str, float], max_items: int = 5):
    """Draw a mini horizontal bar chart"""
    if not data:
        return
    
    # Sort and limit items
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    max_value = max(v for _, v in sorted_data) if sorted_data else 1
    
    bar_height = height // (len(sorted_data) + 1)
    font_small = get_font(14)
    
    for i, (label, value) in enumerate(sorted_data):
        bar_y = y + i * (bar_height + 5)
        bar_width = int((width - 100) * (value / max_value))
        
        # Label
        draw.text((x, bar_y), label[:12], fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Bar
        draw.rectangle(
            [x + 100, bar_y, x + 100 + bar_width, bar_y + bar_height - 5],
            fill=hex_to_rgb(CATEGORY_COLORS[i % len(CATEGORY_COLORS)])
        )
        
        # Value
        draw.text(
            (x + 105 + bar_width, bar_y),
            format_number_short(value),
            fill=hex_to_rgb(COLORS["text_white"]),
            font=font_small
        )


# ==================== WEEKLY REPORT IMAGE ====================

def generate_weekly_report_image(report_data: Dict, lang: str = "uz") -> Optional[bytes]:
    """
    Generate weekly report image with mini charts
    Returns PNG image bytes
    """
    if not PIL_AVAILABLE:
        logger.warning("PIL not available, cannot generate image")
        return None
    
    try:
        # Create image
        img = Image.new('RGB', (REPORT_WIDTH, WEEKLY_HEIGHT), hex_to_rgb(COLORS["background"]))
        draw = ImageDraw.Draw(img)
        
        # Fonts
        font_title = get_font(32, bold=True)
        font_large = get_font(24, bold=True)
        font_medium = get_font(18)
        font_small = get_font(14)
        
        # Extract data
        income = report_data.get("income", 0)
        expense = report_data.get("expense", 0)
        balance = report_data.get("balance", 0)
        count = report_data.get("transaction_count", 0)
        expenses_by_cat = report_data.get("expenses_by_category", {})
        
        y_offset = 30
        
        # Title
        title = "📆 HAFTALIK HISOBOT" if lang == "uz" else "📆 НЕДЕЛЬНЫЙ ОТЧЁТ"
        draw.text((30, y_offset), title, fill=hex_to_rgb(COLORS["text_white"]), font=font_title)
        y_offset += 50
        
        # Date range
        period_start = report_data.get("period_start", datetime.now())
        period_end = report_data.get("period_end", datetime.now())
        date_text = f"{period_start.strftime('%d.%m')} - {period_end.strftime('%d.%m.%Y')}"
        draw.text((30, y_offset), date_text, fill=hex_to_rgb(COLORS["text_gray"]), font=font_medium)
        y_offset += 40
        
        # Summary cards
        card_width = 230
        card_height = 80
        card_y = y_offset
        
        # Income card
        draw_rounded_rect(draw, (30, card_y, 30 + card_width, card_y + card_height), 10, COLORS["card_bg"])
        draw.text((45, card_y + 10), "📈 " + ("Daromad" if lang == "uz" else "Доход"), 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        draw.text((45, card_y + 35), f"+{format_number_short(income)}", 
                  fill=hex_to_rgb(COLORS["income"]), font=font_large)
        
        # Expense card
        draw_rounded_rect(draw, (280, card_y, 280 + card_width, card_y + card_height), 10, COLORS["card_bg"])
        draw.text((295, card_y + 10), "📉 " + ("Xarajat" if lang == "uz" else "Расход"), 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        draw.text((295, card_y + 35), f"-{format_number_short(expense)}", 
                  fill=hex_to_rgb(COLORS["expense"]), font=font_large)
        
        # Balance card
        draw_rounded_rect(draw, (530, card_y, 530 + card_width, card_y + card_height), 10, COLORS["card_bg"])
        draw.text((545, card_y + 10), "💰 " + ("Balans" if lang == "uz" else "Баланс"), 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        balance_color = COLORS["income"] if balance >= 0 else COLORS["expense"]
        balance_text = f"+{format_number_short(balance)}" if balance >= 0 else f"{format_number_short(balance)}"
        draw.text((545, card_y + 35), balance_text, fill=hex_to_rgb(balance_color), font=font_large)
        
        y_offset = card_y + card_height + 30
        
        # Expense breakdown chart
        if expenses_by_cat:
            draw.text((30, y_offset), "📊 " + ("Top xarajatlar" if lang == "uz" else "Топ расходы"), 
                      fill=hex_to_rgb(COLORS["text_white"]), font=font_medium)
            y_offset += 30
            
            draw_mini_bar_chart(draw, 30, y_offset, REPORT_WIDTH - 60, 200, expenses_by_cat)
            y_offset += 220
        
        # Transaction count
        count_text = f"📝 {count} ta tranzaksiya" if lang == "uz" else f"📝 {count} транзакций"
        draw.text((30, y_offset), count_text, fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Footer
        footer_text = "HALOS - Moliyaviy yordamchi" if lang == "uz" else "HALOS - Финансовый помощник"
        draw.text((30, WEEKLY_HEIGHT - 40), footer_text, fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating weekly report image: {e}")
        return None


# ==================== MONTHLY REPORT IMAGE ====================

def generate_monthly_report_image(report_data: Dict, balance_data: Dict, lang: str = "uz") -> Optional[bytes]:
    """
    Generate full monthly report image with charts and balance
    Returns PNG image bytes
    """
    if not PIL_AVAILABLE:
        logger.warning("PIL not available, cannot generate image")
        return None
    
    try:
        # Create image
        img = Image.new('RGB', (REPORT_WIDTH, MONTHLY_HEIGHT), hex_to_rgb(COLORS["background"]))
        draw = ImageDraw.Draw(img)
        
        # Fonts
        font_title = get_font(36, bold=True)
        font_large = get_font(28, bold=True)
        font_medium = get_font(20)
        font_small = get_font(16)
        
        # Extract data
        income = report_data.get("income", 0)
        expense = report_data.get("expense", 0)
        balance = report_data.get("balance", 0)
        count = report_data.get("transaction_count", 0)
        expenses_by_cat = report_data.get("expenses_by_category", {})
        incomes_by_cat = report_data.get("incomes_by_category", {})
        
        # Balance data
        total_income = balance_data.get("total_income", 0)
        total_expense = balance_data.get("total_expense", 0)
        given_debts = balance_data.get("given_debts", 0)
        taken_debts = balance_data.get("taken_debts", 0)
        net_balance = balance_data.get("net_balance", 0)
        
        y_offset = 40
        
        # Header with logo effect
        draw_rounded_rect(draw, (20, 20, REPORT_WIDTH - 20, 120), 15, COLORS["primary"])
        
        title = "🗓 OYLIK HISOBOT" if lang == "uz" else "🗓 МЕСЯЧНЫЙ ОТЧЁТ"
        draw.text((40, 35), title, fill=hex_to_rgb(COLORS["text_white"]), font=font_title)
        
        # Month name
        period_start = report_data.get("period_start", datetime.now())
        month_names_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", 
                         "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
        month_names_ru = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                         "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        month_names = month_names_uz if lang == "uz" else month_names_ru
        month_text = f"{month_names[period_start.month - 1]} {period_start.year}"
        draw.text((40, 80), month_text, fill=hex_to_rgb(COLORS["text_gray"]), font=font_medium)
        
        y_offset = 140
        
        # Main stats section
        card_width = 370
        card_height = 100
        
        # Income card
        draw_rounded_rect(draw, (30, y_offset, 30 + card_width, y_offset + card_height), 12, COLORS["card_bg"])
        draw.text((50, y_offset + 15), "📈 " + ("DAROMAD" if lang == "uz" else "ДОХОД"), 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        draw.text((50, y_offset + 45), f"+{format_number_short(income)} so'm", 
                  fill=hex_to_rgb(COLORS["income"]), font=font_large)
        
        # Expense card
        draw_rounded_rect(draw, (410, y_offset, 410 + card_width, y_offset + card_height), 12, COLORS["card_bg"])
        draw.text((430, y_offset + 15), "📉 " + ("XARAJAT" if lang == "uz" else "РАСХОД"), 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        draw.text((430, y_offset + 45), f"-{format_number_short(expense)} so'm", 
                  fill=hex_to_rgb(COLORS["expense"]), font=font_large)
        
        y_offset += card_height + 20
        
        # Balance section
        draw_rounded_rect(draw, (30, y_offset, REPORT_WIDTH - 30, y_offset + 120), 12, COLORS["card_bg"])
        
        balance_title = "💰 OYLIK BALANS" if lang == "uz" else "💰 МЕСЯЧНЫЙ БАЛАНС"
        draw.text((50, y_offset + 15), balance_title, fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        balance_color = COLORS["income"] if balance >= 0 else COLORS["expense"]
        balance_sign = "+" if balance >= 0 else ""
        draw.text((50, y_offset + 50), f"{balance_sign}{format_number_short(balance)} so'm", 
                  fill=hex_to_rgb(balance_color), font=font_large)
        
        # Progress bar (income vs expense)
        if income > 0:
            expense_ratio = min(expense / income, 1.5)
            draw_progress_bar(draw, 50, y_offset + 95, REPORT_WIDTH - 100, 15, expense_ratio, 
                            COLORS["expense"] if expense_ratio > 1 else COLORS["income"])
        
        y_offset += 140
        
        # Expense breakdown
        if expenses_by_cat:
            section_title = "📊 XARAJATLAR BO'YICHA" if lang == "uz" else "📊 ПО КАТЕГОРИЯМ РАСХОДОВ"
            draw.text((30, y_offset), section_title, fill=hex_to_rgb(COLORS["text_white"]), font=font_medium)
            y_offset += 35
            
            draw_mini_bar_chart(draw, 30, y_offset, REPORT_WIDTH - 60, 180, expenses_by_cat, max_items=6)
            y_offset += 200
        
        # Debt section
        if given_debts > 0 or taken_debts > 0:
            draw_rounded_rect(draw, (30, y_offset, REPORT_WIDTH - 30, y_offset + 140), 12, COLORS["card_bg"])
            
            debt_title = "🔄 QARZ HOLATI" if lang == "uz" else "🔄 СОСТОЯНИЕ ДОЛГОВ"
            draw.text((50, y_offset + 15), debt_title, fill=hex_to_rgb(COLORS["text_white"]), font=font_medium)
            
            if given_debts > 0:
                given_text = f"📤 {'Berilgan' if lang == 'uz' else 'Дал'}: {format_number_short(given_debts)} so'm"
                draw.text((50, y_offset + 50), given_text, fill=hex_to_rgb(COLORS["debt_given"]), font=font_small)
            
            if taken_debts > 0:
                taken_text = f"📥 {'Olingan' if lang == 'uz' else 'Взял'}: {format_number_short(taken_debts)} so'm"
                draw.text((50, y_offset + 80), taken_text, fill=hex_to_rgb(COLORS["debt_taken"]), font=font_small)
            
            # Net balance
            net_color = COLORS["income"] if net_balance >= 0 else COLORS["expense"]
            net_sign = "+" if net_balance >= 0 else ""
            net_text = f"🎯 {'Sof balans' if lang == 'uz' else 'Чистый баланс'}: {net_sign}{format_number_short(net_balance)} so'm"
            draw.text((50, y_offset + 110), net_text, fill=hex_to_rgb(net_color), font=font_small)
            
            y_offset += 160
        
        # Transaction count
        count_text = f"📝 Jami: {count} ta tranzaksiya" if lang == "uz" else f"📝 Всего: {count} транзакций"
        draw.text((30, y_offset), count_text, fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Footer
        draw.line([(30, MONTHLY_HEIGHT - 60), (REPORT_WIDTH - 30, MONTHLY_HEIGHT - 60)], 
                  fill=hex_to_rgb(COLORS["primary"]), width=2)
        
        footer = "HALOS - Shaxsiy moliyaviy yordamchi" if lang == "uz" else "HALOS - Личный финансовый помощник"
        draw.text((30, MONTHLY_HEIGHT - 45), footer, fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Watermark date
        date_text = datetime.now().strftime("%d.%m.%Y %H:%M")
        draw.text((REPORT_WIDTH - 150, MONTHLY_HEIGHT - 45), date_text, 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True, quality=85)
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating monthly report image: {e}")
        import traceback
        traceback.print_exc()
        return None


# ==================== BALANCE CARD IMAGE ====================

def generate_balance_card_image(balance_data: Dict, lang: str = "uz") -> Optional[bytes]:
    """
    Generate a balance card image
    Returns PNG image bytes
    """
    if not PIL_AVAILABLE:
        return None
    
    try:
        width, height = 600, 400
        img = Image.new('RGB', (width, height), hex_to_rgb(COLORS["background"]))
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(28, bold=True)
        font_large = get_font(32, bold=True)
        font_medium = get_font(18)
        font_small = get_font(14)
        
        # Card background
        draw_rounded_rect(draw, (20, 20, width - 20, height - 20), 20, COLORS["card_bg"])
        
        # Title
        title = "💰 HAQIQIY BALANS" if lang == "uz" else "💰 РЕАЛЬНЫЙ БАЛАНС"
        draw.text((40, 40), title, fill=hex_to_rgb(COLORS["text_white"]), font=font_title)
        
        y = 90
        
        # Income
        income = balance_data.get("total_income", 0)
        draw.text((40, y), f"📈 {'Daromad' if lang == 'uz' else 'Доход'}:", 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_medium)
        draw.text((200, y), f"+{format_number_short(income)}", 
                  fill=hex_to_rgb(COLORS["income"]), font=font_medium)
        y += 35
        
        # Expense
        expense = balance_data.get("total_expense", 0)
        draw.text((40, y), f"📉 {'Xarajat' if lang == 'uz' else 'Расход'}:", 
                  fill=hex_to_rgb(COLORS["text_gray"]), font=font_medium)
        draw.text((200, y), f"-{format_number_short(expense)}", 
                  fill=hex_to_rgb(COLORS["expense"]), font=font_medium)
        y += 45
        
        # Debts
        given = balance_data.get("given_debts", 0)
        taken = balance_data.get("taken_debts", 0)
        
        if given > 0:
            draw.text((40, y), f"📤 {'Berilgan qarz' if lang == 'uz' else 'Дал в долг'}:", 
                      fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
            draw.text((200, y), f"{format_number_short(given)}", 
                      fill=hex_to_rgb(COLORS["debt_given"]), font=font_small)
            y += 30
        
        if taken > 0:
            draw.text((40, y), f"📥 {'Olingan qarz' if lang == 'uz' else 'Взял в долг'}:", 
                      fill=hex_to_rgb(COLORS["text_gray"]), font=font_small)
            draw.text((200, y), f"{format_number_short(taken)}", 
                      fill=hex_to_rgb(COLORS["debt_taken"]), font=font_small)
            y += 30
        
        y += 20
        
        # Net balance (big)
        draw.line([(40, y), (width - 40, y)], fill=hex_to_rgb(COLORS["primary"]), width=2)
        y += 20
        
        net = balance_data.get("net_balance", 0)
        net_color = COLORS["income"] if net >= 0 else COLORS["expense"]
        net_sign = "+" if net >= 0 else ""
        
        net_label = "🎯 SOF BALANS" if lang == "uz" else "🎯 ЧИСТЫЙ БАЛАНС"
        draw.text((40, y), net_label, fill=hex_to_rgb(COLORS["text_white"]), font=font_medium)
        y += 35
        
        draw.text((40, y), f"{net_sign}{format_number_short(net)} so'm", 
                  fill=hex_to_rgb(net_color), font=font_large)
        
        # Save
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating balance card: {e}")
        return None


def is_image_generation_available() -> bool:
    """Check if image generation is available"""
    return PIL_AVAILABLE
