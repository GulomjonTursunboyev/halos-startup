"""
Analytics Router
Financial analytics and insights
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import date, datetime, timedelta
from calendar import monthrange
import logging

from api.models import MonthlyAnalytics, CategoryStats, DailyStats, FinancialHealth
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/monthly/{month}", response_model=MonthlyAnalytics)
async def get_monthly_analytics(
    month: str,  # YYYY-MM format
    current_user: dict = Depends(get_current_user)
):
    """Get detailed monthly analytics"""
    pool = await get_pool()
    
    try:
        year, month_num = map(int, month.split("-"))
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid month format. Use YYYY-MM"
        )
    
    async with pool.acquire() as conn:
        # Total income and expense for month
        totals = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
            FROM transactions 
            WHERE user_id = $1 
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
        """, current_user["id"], year, month_num)
        
        total_income = float(totals["total_income"])
        total_expense = float(totals["total_expense"])
        savings = total_income - total_expense
        savings_rate = (savings / total_income * 100) if total_income > 0 else 0
        
        # Top expense categories
        expense_cats = await conn.fetch("""
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions 
            WHERE user_id = $1 
            AND type = 'expense'
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
            GROUP BY category
            ORDER BY total DESC
            LIMIT 10
        """, current_user["id"], year, month_num)
        
        top_expense_categories = [
            CategoryStats(
                category=row["category"],
                total=float(row["total"]),
                percentage=round(float(row["total"]) / total_expense * 100, 1) if total_expense > 0 else 0,
                transaction_count=row["count"]
            )
            for row in expense_cats
        ]
        
        # Top income categories
        income_cats = await conn.fetch("""
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions 
            WHERE user_id = $1 
            AND type = 'income'
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
            GROUP BY category
            ORDER BY total DESC
            LIMIT 10
        """, current_user["id"], year, month_num)
        
        top_income_categories = [
            CategoryStats(
                category=row["category"],
                total=float(row["total"]),
                percentage=round(float(row["total"]) / total_income * 100, 1) if total_income > 0 else 0,
                transaction_count=row["count"]
            )
            for row in income_cats
        ]
        
        # Daily stats
        daily = await conn.fetch("""
            SELECT 
                date,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
            FROM transactions 
            WHERE user_id = $1 
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
            GROUP BY date
            ORDER BY date
        """, current_user["id"], year, month_num)
        
        daily_stats = [
            DailyStats(
                date=row["date"],
                income=float(row["income"]),
                expense=float(row["expense"]),
                net=float(row["income"]) - float(row["expense"])
            )
            for row in daily
        ]
        
        # Last month comparison
        last_month = month_num - 1 if month_num > 1 else 12
        last_year = year if month_num > 1 else year - 1
        
        last_totals = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
            FROM transactions 
            WHERE user_id = $1 
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
        """, current_user["id"], last_year, last_month)
        
        last_income = float(last_totals["total_income"])
        last_expense = float(last_totals["total_expense"])
        
        comparison = {
            "income_change": total_income - last_income,
            "income_change_percent": round((total_income - last_income) / last_income * 100, 1) if last_income > 0 else 0,
            "expense_change": total_expense - last_expense,
            "expense_change_percent": round((total_expense - last_expense) / last_expense * 100, 1) if last_expense > 0 else 0
        }
        
        return MonthlyAnalytics(
            month=month,
            total_income=total_income,
            total_expense=total_expense,
            savings=savings,
            savings_rate=round(savings_rate, 1),
            top_expense_categories=top_expense_categories,
            top_income_categories=top_income_categories,
            daily_stats=daily_stats,
            comparison_with_last_month=comparison
        )


@router.get("/current-month", response_model=MonthlyAnalytics)
async def get_current_month_analytics(current_user: dict = Depends(get_current_user)):
    """Get current month analytics"""
    current_month = date.today().strftime("%Y-%m")
    return await get_monthly_analytics(current_month, current_user)


@router.get("/overview")
async def get_financial_overview(current_user: dict = Depends(get_current_user)):
    """Get quick financial overview"""
    pool = await get_pool()
    
    today = date.today()
    month_start = today.replace(day=1)
    
    async with pool.acquire() as conn:
        # This month stats
        month_stats = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as month_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as month_expense
            FROM transactions 
            WHERE user_id = $1 AND date >= $2
        """, current_user["id"], month_start)
        
        # Today's stats
        today_stats = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as today_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as today_expense
            FROM transactions 
            WHERE user_id = $1 AND date = $2
        """, current_user["id"], today)
        
        # Active debts
        debts = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN debt_type = 'lent' THEN amount - returned_amount ELSE 0 END), 0) as total_lent,
                COALESCE(SUM(CASE WHEN debt_type = 'borrowed' THEN amount - returned_amount ELSE 0 END), 0) as total_borrowed
            FROM personal_debts 
            WHERE user_id = $1 AND status = 'active'
        """, current_user["id"])
        
        # Upcoming debt payments
        upcoming_debts = await conn.fetchval("""
            SELECT COUNT(*) FROM personal_debts 
            WHERE user_id = $1 AND status = 'active' 
            AND due_date IS NOT NULL AND due_date <= CURRENT_DATE + 7
        """, current_user["id"])
        
        return {
            "today": {
                "income": float(today_stats["today_income"]),
                "expense": float(today_stats["today_expense"]),
                "net": float(today_stats["today_income"]) - float(today_stats["today_expense"])
            },
            "month": {
                "income": float(month_stats["month_income"]),
                "expense": float(month_stats["month_expense"]),
                "savings": float(month_stats["month_income"]) - float(month_stats["month_expense"])
            },
            "debts": {
                "total_lent": float(debts["total_lent"]),
                "total_borrowed": float(debts["total_borrowed"]),
                "net": float(debts["total_lent"]) - float(debts["total_borrowed"]),
                "upcoming_payments": upcoming_debts
            }
        }


@router.get("/health", response_model=FinancialHealth)
async def get_financial_health(current_user: dict = Depends(get_current_user)):
    """Calculate financial health score"""
    pool = await get_pool()
    
    today = date.today()
    month_start = today.replace(day=1)
    three_months_ago = today - timedelta(days=90)
    
    async with pool.acquire() as conn:
        # Get 3-month average
        stats = await conn.fetchrow("""
            SELECT 
                COALESCE(AVG(CASE WHEN type = 'income' THEN amount END), 0) as avg_income,
                COALESCE(AVG(CASE WHEN type = 'expense' THEN amount END), 0) as avg_expense,
                COUNT(DISTINCT date) as active_days
            FROM transactions 
            WHERE user_id = $1 AND date >= $2
        """, current_user["id"], three_months_ago)
        
        # Get debt info
        debts = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_debts,
                COUNT(CASE WHEN due_date < CURRENT_DATE THEN 1 END) as overdue_debts
            FROM personal_debts 
            WHERE user_id = $1 AND status = 'active'
        """, current_user["id"])
    
    # Calculate score (0-100)
    score = 50  # Base score
    strengths = []
    improvements = []
    tips = []
    
    avg_income = float(stats["avg_income"] or 0)
    avg_expense = float(stats["avg_expense"] or 0)
    
    # Savings rate impact
    if avg_income > 0:
        savings_rate = (avg_income - avg_expense) / avg_income
        if savings_rate >= 0.2:
            score += 20
            strengths.append("Yaxshi jamg'arma darajasi (20%+)")
        elif savings_rate >= 0.1:
            score += 10
            strengths.append("O'rtacha jamg'arma darajasi")
        elif savings_rate < 0:
            score -= 20
            improvements.append("Xarajatlar daromaddan oshib ketgan")
            tips.append("Ortiqcha xarajatlarni kamaytiring")
    
    # Tracking consistency
    if stats["active_days"] >= 60:
        score += 15
        strengths.append("Muntazam moliyaviy kuzatuv")
    elif stats["active_days"] >= 30:
        score += 10
    else:
        improvements.append("Moliyalarni muntazam kuzatish kerak")
        tips.append("Har kuni xarajatlarni yozib boring")
    
    # Debt management
    if debts["total_debts"] == 0:
        score += 10
        strengths.append("Qarzlar yo'q")
    elif debts["overdue_debts"] > 0:
        score -= 15
        improvements.append(f"{debts['overdue_debts']} ta muddati o'tgan qarz")
        tips.append("Muddati o'tgan qarzlarni tezroq uzating")
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Determine grade
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "F"
    
    return FinancialHealth(
        score=score,
        grade=grade,
        strengths=strengths,
        improvements=improvements,
        tips=tips
    )


@router.get("/trends/spending")
async def get_spending_trends(
    months: int = Query(6, ge=1, le=12),
    current_user: dict = Depends(get_current_user)
):
    """Get spending trends over last N months"""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                TO_CHAR(date, 'YYYY-MM') as month,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
            FROM transactions 
            WHERE user_id = $1 
            AND date >= CURRENT_DATE - INTERVAL '%s months'
            GROUP BY TO_CHAR(date, 'YYYY-MM')
            ORDER BY month
        """ % months, current_user["id"])
        
        return [
            {
                "month": row["month"],
                "income": float(row["income"]),
                "expense": float(row["expense"]),
                "savings": float(row["income"]) - float(row["expense"])
            }
            for row in rows
        ]
