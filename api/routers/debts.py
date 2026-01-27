"""
Debts Router
Personal debt management (lent/borrowed)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import date, datetime
import logging

from api.models import (
    Debt, DebtCreate, DebtUpdate, DebtSummary, 
    DebtType, DebtStatus
)
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[Debt])
async def list_debts(
    debt_type: Optional[DebtType] = None,
    status: Optional[DebtStatus] = DebtStatus.ACTIVE,
    current_user: dict = Depends(get_current_user)
):
    """List user's debts"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conditions = ["user_id = $1"]
        params = [current_user["id"]]
        param_idx = 2
        
        if debt_type:
            conditions.append(f"debt_type = ${param_idx}")
            params.append(debt_type.value)
            param_idx += 1
        
        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
        
        where_clause = " AND ".join(conditions)
        
        rows = await conn.fetch(f"""
            SELECT * FROM personal_debts 
            WHERE {where_clause}
            ORDER BY due_date ASC NULLS LAST, created_at DESC
        """, *params)
        
        return [
            Debt(
                id=row["id"],
                user_id=row["user_id"],
                debt_type=row["debt_type"],
                person_name=row["person_name"],
                amount=row["amount"],
                description=row.get("description"),
                given_date=row["given_date"] if isinstance(row["given_date"], date) else datetime.strptime(row["given_date"], "%Y-%m-%d").date(),
                due_date=row["due_date"] if row["due_date"] and isinstance(row["due_date"], date) else (datetime.strptime(row["due_date"], "%Y-%m-%d").date() if row["due_date"] else None),
                currency=row.get("currency", "UZS"),
                status=row["status"],
                returned_amount=row.get("returned_amount", 0) or 0,
                returned_date=row.get("returned_date"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at")
            )
            for row in rows
        ]


@router.get("/summary", response_model=DebtSummary)
async def get_debt_summary(current_user: dict = Depends(get_current_user)):
    """Get debt summary - total lent vs borrowed"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN debt_type = 'lent' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_lent,
                COALESCE(SUM(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_borrowed,
                COUNT(CASE WHEN debt_type = 'lent' AND status = 'active' THEN 1 END) as lent_count,
                COUNT(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN 1 END) as borrowed_count
            FROM personal_debts 
            WHERE user_id = $1
        """, current_user["id"])
    
    total_lent = float(row["total_lent"] or 0)
    total_borrowed = float(row["total_borrowed"] or 0)
    
    return DebtSummary(
        total_lent=total_lent,
        total_borrowed=total_borrowed,
        lent_count=row["lent_count"] or 0,
        borrowed_count=row["borrowed_count"] or 0,
        net_balance=total_lent - total_borrowed
    )


@router.post("/", response_model=Debt, status_code=status.HTTP_201_CREATED)
async def create_debt(
    debt: DebtCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new debt record"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO personal_debts 
            (user_id, debt_type, person_name, amount, description, given_date, due_date, currency, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', NOW())
            RETURNING *
        """, current_user["id"], debt.debt_type.value, debt.person_name,
            debt.amount, debt.description, debt.given_date, debt.due_date,
            debt.currency.value)
    
    return Debt(
        id=row["id"],
        user_id=row["user_id"],
        debt_type=row["debt_type"],
        person_name=row["person_name"],
        amount=row["amount"],
        description=row.get("description"),
        given_date=row["given_date"],
        due_date=row.get("due_date"),
        currency=row.get("currency", "UZS"),
        status=row["status"],
        returned_amount=row.get("returned_amount", 0) or 0,
        created_at=row["created_at"]
    )


@router.get("/{debt_id}", response_model=Debt)
async def get_debt(
    debt_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific debt"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, current_user["id"]
        )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found"
        )
    
    return Debt(
        id=row["id"],
        user_id=row["user_id"],
        debt_type=row["debt_type"],
        person_name=row["person_name"],
        amount=row["amount"],
        description=row.get("description"),
        given_date=row["given_date"],
        due_date=row.get("due_date"),
        currency=row.get("currency", "UZS"),
        status=row["status"],
        returned_amount=row.get("returned_amount", 0) or 0,
        returned_date=row.get("returned_date"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.patch("/{debt_id}", response_model=Debt)
async def update_debt(
    debt_id: int,
    update: DebtUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a debt"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if exists
        existing = await conn.fetchrow(
            "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, current_user["id"]
        )
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Debt not found"
            )
        
        # Build update query
        updates = []
        values = []
        param_idx = 1
        
        if update.person_name is not None:
            updates.append(f"person_name = ${param_idx}")
            values.append(update.person_name)
            param_idx += 1
        
        if update.amount is not None:
            updates.append(f"amount = ${param_idx}")
            values.append(update.amount)
            param_idx += 1
        
        if update.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(update.description)
            param_idx += 1
        
        if update.due_date is not None:
            updates.append(f"due_date = ${param_idx}")
            values.append(update.due_date)
            param_idx += 1
        
        if update.status is not None:
            updates.append(f"status = ${param_idx}")
            values.append(update.status.value)
            param_idx += 1
            
            if update.status == DebtStatus.RETURNED:
                updates.append(f"returned_date = ${param_idx}")
                values.append(date.today())
                param_idx += 1
        
        if update.returned_amount is not None:
            updates.append(f"returned_amount = ${param_idx}")
            values.append(update.returned_amount)
            param_idx += 1
        
        if updates:
            updates.append("updated_at = NOW()")
            values.extend([debt_id, current_user["id"]])
            
            query = f"""
                UPDATE personal_debts 
                SET {', '.join(updates)} 
                WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
                RETURNING *
            """
            row = await conn.fetchrow(query, *values)
        else:
            row = existing
    
    return Debt(
        id=row["id"],
        user_id=row["user_id"],
        debt_type=row["debt_type"],
        person_name=row["person_name"],
        amount=row["amount"],
        description=row.get("description"),
        given_date=row["given_date"],
        due_date=row.get("due_date"),
        currency=row.get("currency", "UZS"),
        status=row["status"],
        returned_amount=row.get("returned_amount", 0) or 0,
        returned_date=row.get("returned_date"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.post("/{debt_id}/mark-returned", response_model=Debt)
async def mark_debt_returned(
    debt_id: int,
    partial_amount: Optional[float] = None,
    current_user: dict = Depends(get_current_user)
):
    """Mark a debt as returned (fully or partially)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, current_user["id"]
        )
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Debt not found"
            )
        
        if partial_amount:
            # Partial return
            new_returned = (existing["returned_amount"] or 0) + partial_amount
            remaining = existing["amount"] - new_returned
            
            if remaining <= 0:
                new_status = "returned"
            else:
                new_status = "partial"
            
            row = await conn.fetchrow("""
                UPDATE personal_debts 
                SET returned_amount = $1, status = $2, updated_at = NOW()
                WHERE id = $3 AND user_id = $4
                RETURNING *
            """, new_returned, new_status, debt_id, current_user["id"])
        else:
            # Full return
            row = await conn.fetchrow("""
                UPDATE personal_debts 
                SET status = 'returned', returned_amount = amount, 
                    returned_date = CURRENT_DATE, updated_at = NOW()
                WHERE id = $1 AND user_id = $2
                RETURNING *
            """, debt_id, current_user["id"])
    
    return Debt(
        id=row["id"],
        user_id=row["user_id"],
        debt_type=row["debt_type"],
        person_name=row["person_name"],
        amount=row["amount"],
        description=row.get("description"),
        given_date=row["given_date"],
        due_date=row.get("due_date"),
        currency=row.get("currency", "UZS"),
        status=row["status"],
        returned_amount=row.get("returned_amount", 0) or 0,
        returned_date=row.get("returned_date"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(
    debt_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a debt"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM personal_debts WHERE id = $1 AND user_id = $2",
            debt_id, current_user["id"]
        )
    
    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found"
        )


@router.get("/upcoming/list")
async def get_upcoming_debts(
    days: int = Query(7, ge=1, le=30),
    current_user: dict = Depends(get_current_user)
):
    """Get debts due within N days"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM personal_debts 
            WHERE user_id = $1 
            AND status = 'active'
            AND due_date IS NOT NULL
            AND due_date <= CURRENT_DATE + $2
            ORDER BY due_date ASC
        """, current_user["id"], days)
        
        return [
            {
                "id": row["id"],
                "debt_type": row["debt_type"],
                "person_name": row["person_name"],
                "amount": row["amount"],
                "due_date": row["due_date"].isoformat() if row["due_date"] else None,
                "days_left": (row["due_date"] - date.today()).days if row["due_date"] else None
            }
            for row in rows
        ]
