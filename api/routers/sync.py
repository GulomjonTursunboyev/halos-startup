"""
Sync Router
Cross-platform data synchronization
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime, date
import logging

from api.models import SyncRequest, SyncResponse, SyncStatus, Transaction, Debt
from api.database import get_pool
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(current_user: dict = Depends(get_current_user)):
    """Get current sync status"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get last sync timestamp from user
        user = await conn.fetchrow(
            "SELECT last_sync, last_active FROM users WHERE id = $1",
            current_user["id"]
        )
        
        # Count changes since last sync
        last_sync = user.get("last_sync") or datetime(2020, 1, 1)
        
        pending_transactions = await conn.fetchval("""
            SELECT COUNT(*) FROM transactions 
            WHERE user_id = $1 AND (created_at > $2 OR updated_at > $2)
        """, current_user["id"], last_sync)
        
        pending_debts = await conn.fetchval("""
            SELECT COUNT(*) FROM personal_debts 
            WHERE user_id = $1 AND (created_at > $2 OR updated_at > $2)
        """, current_user["id"], last_sync)
        
        return SyncStatus(
            last_sync=user.get("last_sync"),
            pending_changes=pending_transactions + pending_debts,
            is_synced=pending_transactions + pending_debts == 0
        )


@router.post("/pull")
async def pull_changes(
    last_sync: datetime = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Pull changes from server since last sync
    Used when app comes online after being offline
    """
    pool = await get_pool()
    last_sync = last_sync or datetime(2020, 1, 1)
    
    async with pool.acquire() as conn:
        # Get new/updated transactions
        transactions = await conn.fetch("""
            SELECT * FROM transactions 
            WHERE user_id = $1 AND (created_at > $2 OR updated_at > $2)
            ORDER BY created_at
        """, current_user["id"], last_sync)
        
        # Get new/updated debts
        debts = await conn.fetch("""
            SELECT * FROM personal_debts 
            WHERE user_id = $1 AND (created_at > $2 OR updated_at > $2)
            ORDER BY created_at
        """, current_user["id"], last_sync)
        
        # Get deleted items (if we track deletions)
        # For now, return empty lists
        deleted_transactions = []
        deleted_debts = []
        
        return {
            "transactions": [dict(t) for t in transactions],
            "debts": [dict(d) for d in debts],
            "deleted_transaction_ids": deleted_transactions,
            "deleted_debt_ids": deleted_debts,
            "sync_timestamp": datetime.utcnow()
        }


@router.post("/push")
async def push_changes(
    request: SyncRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Push local changes to server
    Used when app was offline and now syncing
    """
    pool = await get_pool()
    
    created_transactions = []
    created_debts = []
    conflicts = []
    
    async with pool.acquire() as conn:
        # Insert new transactions
        for tx in request.local_transactions:
            try:
                row = await conn.fetchrow("""
                    INSERT INTO transactions 
                    (user_id, amount, type, category, description, date, currency, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    RETURNING id
                """, current_user["id"], tx.amount, tx.type.value,
                    tx.category, tx.description, tx.date, tx.currency.value)
                created_transactions.append(row["id"])
            except Exception as e:
                logger.error(f"Error syncing transaction: {e}")
                conflicts.append({"type": "transaction", "data": tx.dict(), "error": str(e)})
        
        # Insert new debts
        for debt in request.local_debts:
            try:
                row = await conn.fetchrow("""
                    INSERT INTO personal_debts 
                    (user_id, debt_type, person_name, amount, description, given_date, due_date, currency, status, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', NOW())
                    RETURNING id
                """, current_user["id"], debt.debt_type.value, debt.person_name,
                    debt.amount, debt.description, debt.given_date, debt.due_date,
                    debt.currency.value)
                created_debts.append(row["id"])
            except Exception as e:
                logger.error(f"Error syncing debt: {e}")
                conflicts.append({"type": "debt", "data": debt.dict(), "error": str(e)})
        
        # Delete transactions
        for tx_id in request.deleted_transaction_ids:
            await conn.execute(
                "DELETE FROM transactions WHERE id = $1 AND user_id = $2",
                tx_id, current_user["id"]
            )
        
        # Delete debts
        for debt_id in request.deleted_debt_ids:
            await conn.execute(
                "DELETE FROM personal_debts WHERE id = $1 AND user_id = $2",
                debt_id, current_user["id"]
            )
        
        # Update last sync timestamp
        await conn.execute(
            "UPDATE users SET last_sync = NOW() WHERE id = $1",
            current_user["id"]
        )
    
    return {
        "created_transaction_ids": created_transactions,
        "created_debt_ids": created_debts,
        "conflicts": conflicts,
        "sync_timestamp": datetime.utcnow()
    }


@router.post("/full")
async def full_sync(
    request: SyncRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Full two-way sync
    1. Push local changes
    2. Pull server changes
    """
    # First push local changes
    push_result = await push_changes(request, current_user)
    
    # Then pull server changes
    pull_result = await pull_changes(request.last_sync_timestamp, current_user)
    
    return {
        "pushed": push_result,
        "pulled": pull_result,
        "sync_timestamp": datetime.utcnow()
    }


@router.get("/export")
async def export_all_data(current_user: dict = Depends(get_current_user)):
    """
    Export all user data (for backup or migration)
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Get all transactions
        transactions = await conn.fetch(
            "SELECT * FROM transactions WHERE user_id = $1 ORDER BY date",
            current_user["id"]
        )
        
        # Get all debts
        debts = await conn.fetch(
            "SELECT * FROM personal_debts WHERE user_id = $1 ORDER BY given_date",
            current_user["id"]
        )
        
        # Get financial profile
        profile = await conn.fetchrow(
            "SELECT * FROM financial_profiles WHERE user_id = $1",
            current_user["id"]
        )
        
        # Get budgets
        budgets = await conn.fetch(
            "SELECT * FROM budgets WHERE user_id = $1",
            current_user["id"]
        )
    
    return {
        "export_date": datetime.utcnow().isoformat(),
        "user_id": current_user["id"],
        "transactions": [dict(t) for t in transactions],
        "debts": [dict(d) for d in debts],
        "financial_profile": dict(profile) if profile else None,
        "budgets": [dict(b) for b in budgets]
    }
