"""
Budgets Router
Budget management by category
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import date, datetime
import logging

from api.models import MonthlyBudget, BudgetCategory, BudgetCreate
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def get_current_month() -> str:
    """Get current month in YYYY-MM format"""
    return date.today().strftime("%Y-%m")


@router.get("/current", response_model=MonthlyBudget)
async def get_current_budget(current_user: dict = Depends(get_current_user)):
    """Get current month's budget"""
    return await get_budget_for_month(get_current_month(), current_user)


@router.get("/{month}", response_model=MonthlyBudget)
async def get_budget_for_month(
    month: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get budget for specific month
    month format: YYYY-MM
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get budget limits for month
        budgets = await conn.fetch("""
            SELECT * FROM budgets 
            WHERE user_id = $1 AND month = $2
        """, current_user["id"], month)
        
        # Get actual spending by category for month
        year, month_num = month.split("-")
        spending = await conn.fetch("""
            SELECT category, SUM(amount) as total
            FROM transactions 
            WHERE user_id = $1 
            AND type = 'expense'
            AND EXTRACT(YEAR FROM date) = $2
            AND EXTRACT(MONTH FROM date) = $3
            GROUP BY category
        """, current_user["id"], int(year), int(month_num))
        
        spending_map = {row["category"]: float(row["total"]) for row in spending}
        
        categories = []
        total_budget = 0
        total_spent = 0
        
        for budget in budgets:
            category = budget["category"]
            limit = float(budget["limit_amount"])
            spent = spending_map.get(category, 0)
            remaining = max(0, limit - spent)
            percentage = (spent / limit * 100) if limit > 0 else 0
            
            categories.append(BudgetCategory(
                category=category,
                limit=limit,
                spent=spent,
                remaining=remaining,
                percentage_used=round(percentage, 1)
            ))
            
            total_budget += limit
            total_spent += spent
        
        # Add categories with spending but no budget
        for category, spent in spending_map.items():
            if category not in [b["category"] for b in budgets]:
                categories.append(BudgetCategory(
                    category=category,
                    limit=0,
                    spent=spent,
                    remaining=0,
                    percentage_used=100
                ))
                total_spent += spent
        
        return MonthlyBudget(
            month=month,
            total_budget=total_budget,
            total_spent=total_spent,
            remaining=max(0, total_budget - total_spent),
            categories=sorted(categories, key=lambda x: x.spent, reverse=True)
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_or_update_budget(
    budget: BudgetCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create or update budget for a category"""
    month = budget.month or get_current_month()
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow("""
            INSERT INTO budgets (user_id, category, limit_amount, month, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, category, month) DO UPDATE SET
                limit_amount = EXCLUDED.limit_amount,
                updated_at = NOW()
            RETURNING *
        """, current_user["id"], budget.category, budget.limit, month)
    
    return {
        "id": result["id"],
        "category": result["category"],
        "limit": float(result["limit_amount"]),
        "month": result["month"]
    }


@router.delete("/{category}")
async def delete_budget(
    category: str,
    month: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Delete budget for a category"""
    month = month or get_current_month()
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM budgets WHERE user_id = $1 AND category = $2 AND month = $3",
            current_user["id"], category, month
        )
    
    return {"message": "Budget deleted"}


@router.get("/alerts/list")
async def get_budget_alerts(current_user: dict = Depends(get_current_user)):
    """Get list of budget alerts (categories over limit or near limit)"""
    budget = await get_current_budget(current_user)
    
    alerts = []
    for cat in budget.categories:
        if cat.limit > 0:
            if cat.percentage_used >= 100:
                alerts.append({
                    "category": cat.category,
                    "type": "exceeded",
                    "message": f"{cat.category} budjetdan {cat.spent - cat.limit:,.0f} so'm oshib ketdi",
                    "percentage": cat.percentage_used
                })
            elif cat.percentage_used >= 80:
                alerts.append({
                    "category": cat.category,
                    "type": "warning",
                    "message": f"{cat.category} budjetning {cat.percentage_used:.0f}% ishlatildi",
                    "percentage": cat.percentage_used
                })
    
    return alerts
