"""
Transactions Router
Income/Expense management with AI categorization
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import date, datetime, timedelta
import logging

from api.models import (
    Transaction, TransactionCreate, TransactionUpdate, 
    TransactionList, TransactionType
)
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=TransactionList)
async def list_transactions(
    type: Optional[TransactionType] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    List user's transactions with pagination and filters
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build query
        conditions = ["user_id = $1"]
        params = [current_user["id"]]
        param_idx = 2
        
        if type:
            conditions.append(f"type = ${param_idx}")
            params.append(type.value)
            param_idx += 1
        
        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1
        
        if start_date:
            conditions.append(f"date >= ${param_idx}")
            params.append(start_date)
            param_idx += 1
        
        if end_date:
            conditions.append(f"date <= ${param_idx}")
            params.append(end_date)
            param_idx += 1
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM transactions WHERE {where_clause}",
            *params
        )
        
        # Get paginated results
        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        
        rows = await conn.fetch(f"""
            SELECT * FROM transactions 
            WHERE {where_clause}
            ORDER BY date DESC, created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """, *params)
        
        transactions = [
            Transaction(
                id=row["id"],
                user_id=row["user_id"],
                amount=row["amount"],
                type=row["type"],
                category=row["category"],
                description=row.get("description"),
                date=row["date"] if isinstance(row["date"], date) else datetime.strptime(row["date"], "%Y-%m-%d").date(),
                currency=row.get("currency", "UZS"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at")
            )
            for row in rows
        ]
        
        return TransactionList(
            items=transactions,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total
        )


@router.post("/", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction: TransactionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new transaction
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO transactions 
            (user_id, amount, type, category, description, date, currency, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING *
        """, current_user["id"], transaction.amount, transaction.type.value,
            transaction.category, transaction.description, transaction.date,
            transaction.currency.value)
    
    return Transaction(
        id=row["id"],
        user_id=row["user_id"],
        amount=row["amount"],
        type=row["type"],
        category=row["category"],
        description=row.get("description"),
        date=row["date"] if isinstance(row["date"], date) else datetime.strptime(row["date"], "%Y-%m-%d").date(),
        currency=row.get("currency", "UZS"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific transaction"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM transactions WHERE id = $1 AND user_id = $2",
            transaction_id, current_user["id"]
        )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return Transaction(
        id=row["id"],
        user_id=row["user_id"],
        amount=row["amount"],
        type=row["type"],
        category=row["category"],
        description=row.get("description"),
        date=row["date"] if isinstance(row["date"], date) else datetime.strptime(row["date"], "%Y-%m-%d").date(),
        currency=row.get("currency", "UZS"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.patch("/{transaction_id}", response_model=Transaction)
async def update_transaction(
    transaction_id: int,
    update: TransactionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a transaction"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if exists
        existing = await conn.fetchrow(
            "SELECT * FROM transactions WHERE id = $1 AND user_id = $2",
            transaction_id, current_user["id"]
        )
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Build update query
        updates = []
        values = []
        param_idx = 1
        
        if update.amount is not None:
            updates.append(f"amount = ${param_idx}")
            values.append(update.amount)
            param_idx += 1
        
        if update.type is not None:
            updates.append(f"type = ${param_idx}")
            values.append(update.type.value)
            param_idx += 1
        
        if update.category is not None:
            updates.append(f"category = ${param_idx}")
            values.append(update.category)
            param_idx += 1
        
        if update.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(update.description)
            param_idx += 1
        
        if update.date is not None:
            updates.append(f"date = ${param_idx}")
            values.append(update.date)
            param_idx += 1
        
        if updates:
            updates.append("updated_at = NOW()")
            values.extend([transaction_id, current_user["id"]])
            
            query = f"""
                UPDATE transactions 
                SET {', '.join(updates)} 
                WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
                RETURNING *
            """
            row = await conn.fetchrow(query, *values)
        else:
            row = existing
    
    return Transaction(
        id=row["id"],
        user_id=row["user_id"],
        amount=row["amount"],
        type=row["type"],
        category=row["category"],
        description=row.get("description"),
        date=row["date"] if isinstance(row["date"], date) else datetime.strptime(row["date"], "%Y-%m-%d").date(),
        currency=row.get("currency", "UZS"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at")
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a transaction"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM transactions WHERE id = $1 AND user_id = $2",
            transaction_id, current_user["id"]
        )
    
    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )


@router.get("/categories/list")
async def list_categories(
    type: Optional[TransactionType] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get list of categories user has used"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if type:
            rows = await conn.fetch("""
                SELECT DISTINCT category, type, COUNT(*) as count
                FROM transactions 
                WHERE user_id = $1 AND type = $2
                GROUP BY category, type
                ORDER BY count DESC
            """, current_user["id"], type.value)
        else:
            rows = await conn.fetch("""
                SELECT DISTINCT category, type, COUNT(*) as count
                FROM transactions 
                WHERE user_id = $1
                GROUP BY category, type
                ORDER BY count DESC
            """, current_user["id"])
    
    return [
        {"category": row["category"], "type": row["type"], "count": row["count"]}
        for row in rows
    ]


@router.post("/voice")
async def create_from_voice(
    text: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Create transaction from voice/text using AI
    This endpoint processes natural language and creates a transaction
    """
    # Import AI assistant for parsing
    from app.ai_assistant import parse_financial_text
    
    # Parse the text
    result = await parse_financial_text(text, current_user["id"])
    
    if not result or not result.get("amount"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse transaction from text"
        )
    
    # Create transaction
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO transactions 
            (user_id, amount, type, category, description, date, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING *
        """, current_user["id"], result["amount"], result["type"],
            result["category"], result.get("description"), result.get("date", date.today()))
    
    return {
        "transaction": Transaction(
            id=row["id"],
            user_id=row["user_id"],
            amount=row["amount"],
            type=row["type"],
            category=row["category"],
            description=row.get("description"),
            date=row["date"],
            currency=row.get("currency", "UZS"),
            created_at=row["created_at"]
        ),
        "parsed": result
    }
