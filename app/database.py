"""
SOLVO Database Module
SQLite database with async support for user data and financial plans
"""
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import json


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Initialize database connection and create tables"""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
    
    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
    
    async def _create_tables(self):
        """Create all required tables"""
        await self._connection.executescript("""
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language TEXT DEFAULT 'uz',
                mode TEXT DEFAULT 'solo',
                subscription_tier TEXT DEFAULT 'free',
                subscription_plan TEXT,
                subscription_expires TIMESTAMP,
                subscription_auto_renew INTEGER DEFAULT 1,
                trial_used INTEGER DEFAULT 0,
                referral_code TEXT,
                referred_by INTEGER,
                last_active TIMESTAMP,
                last_salary_message TIMESTAMP,
                last_weekly_message TIMESTAMP,
                last_monthly_message TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Financial profiles table
            CREATE TABLE IF NOT EXISTS financial_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                income_self REAL DEFAULT 0,
                income_partner REAL DEFAULT 0,
                rent REAL DEFAULT 0,
                kindergarten REAL DEFAULT 0,
                utilities REAL DEFAULT 0,
                loan_payment REAL DEFAULT 0,
                total_debt REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            -- Calculations history table
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                total_income REAL,
                mandatory_living REAL,
                mandatory_debt REAL,
                free_cash REAL,
                monthly_savings REAL,
                monthly_debt_payment REAL,
                monthly_living REAL,
                monthly_invest REAL,
                exit_months INTEGER,
                exit_date TEXT,
                savings_12_months REAL,
                savings_at_exit REAL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES financial_profiles(id) ON DELETE CASCADE
            );
            
            -- KATM parsed loans table
            CREATE TABLE IF NOT EXISTS katm_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_id INTEGER,
                bank_name TEXT NOT NULL,
                contract_number TEXT,
                loan_type TEXT,
                original_amount REAL DEFAULT 0,
                remaining_balance REAL DEFAULT 0,
                monthly_payment REAL DEFAULT 0,
                currency TEXT DEFAULT 'UZS',
                status TEXT DEFAULT 'active',
                start_date TEXT,
                end_date TEXT,
                pdf_filename TEXT,
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES financial_profiles(id) ON DELETE CASCADE
            );
            
            -- Transaction history table
            CREATE TABLE IF NOT EXISTS transaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_file TEXT,
                source_type TEXT,
                total_income REAL DEFAULT 0,
                total_expense REAL DEFAULT 0,
                income_count INTEGER DEFAULT 0,
                expense_count INTEGER DEFAULT 0,
                monthly_income REAL DEFAULT 0,
                monthly_expense REAL DEFAULT 0,
                period_start TEXT,
                period_end TEXT,
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            -- Payments table
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_id TEXT NOT NULL,
                amount_uzs REAL DEFAULT 0,
                amount_stars INTEGER DEFAULT 0,
                payment_method TEXT NOT NULL,
                payment_id TEXT,
                promo_code TEXT,
                discount_percent INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            -- Feature usage tracking
            CREATE TABLE IF NOT EXISTS feature_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                usage_date DATE DEFAULT (DATE('now')),
                usage_count INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, feature, usage_date)
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON financial_profiles(user_id);
            CREATE INDEX IF NOT EXISTS idx_calculations_user_id ON calculations(user_id);
            CREATE INDEX IF NOT EXISTS idx_katm_loans_user_id ON katm_loans(user_id);
            CREATE INDEX IF NOT EXISTS idx_transaction_history_user_id ON transaction_history(user_id);
            CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
            CREATE INDEX IF NOT EXISTS idx_feature_usage_user_id ON feature_usage(user_id);
        """)
        await self._connection.commit()
        
        # Run migrations for existing databases
        await self._run_migrations()
    
    async def _run_migrations(self):
        """Add new columns to existing tables"""
        migrations = [
            ("users", "last_active", "TIMESTAMP"),
            ("users", "last_salary_message", "TIMESTAMP"),
            ("users", "last_weekly_message", "TIMESTAMP"),
            ("users", "last_monthly_message", "TIMESTAMP"),
        ]
        
        for table, column, col_type in migrations:
            try:
                await self._connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                )
                await self._connection.commit()
            except Exception:
                # Column already exists
                pass
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID"""
        async with self._connection.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_user(
        self,
        telegram_id: int,
        phone_number: str,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        language: str = "uz"
    ) -> int:
        """Create a new user and return user ID"""
        cursor = await self._connection.execute(
            """INSERT INTO users (telegram_id, phone_number, first_name, last_name, username, language)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (telegram_id, phone_number, first_name, last_name, username, language)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def update_user(self, telegram_id: int, **kwargs) -> bool:
        """Update user fields"""
        if not kwargs:
            return False
        
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [telegram_id]
        
        await self._connection.execute(
            f"UPDATE users SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            values
        )
        await self._connection.commit()
        return True
    
    async def update_user_activity(self, telegram_id: int) -> bool:
        """Update user's last_active timestamp"""
        from datetime import datetime
        return await self.update_user(telegram_id, last_active=datetime.now().isoformat())
    
    async def user_exists(self, telegram_id: int) -> bool:
        """Check if user exists"""
        async with self._connection.execute(
            "SELECT 1 FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ) as cursor:
            return await cursor.fetchone() is not None
    
    # ==================== FINANCIAL PROFILE OPERATIONS ====================
    
    async def get_financial_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get latest financial profile for user"""
        async with self._connection.execute(
            """SELECT * FROM financial_profiles 
               WHERE user_id = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_financial_profile(self, user_id: int, **kwargs) -> int:
        """Create new financial profile"""
        fields = ["user_id"] + list(kwargs.keys())
        placeholders = ", ".join(["?"] * len(fields))
        field_names = ", ".join(fields)
        values = [user_id] + list(kwargs.values())
        
        cursor = await self._connection.execute(
            f"INSERT INTO financial_profiles ({field_names}) VALUES ({placeholders})",
            values
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def update_financial_profile(self, profile_id: int, **kwargs) -> bool:
        """Update financial profile"""
        if not kwargs:
            return False
        
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [profile_id]
        
        await self._connection.execute(
            f"UPDATE financial_profiles SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values
        )
        await self._connection.commit()
        return True
    
    # ==================== CALCULATIONS OPERATIONS ====================
    
    async def save_calculation(
        self,
        user_id: int,
        profile_id: int,
        calculation_data: Dict[str, Any]
    ) -> int:
        """Save calculation result"""
        cursor = await self._connection.execute(
            """INSERT INTO calculations 
               (user_id, profile_id, mode, total_income, mandatory_living, mandatory_debt,
                free_cash, monthly_savings, monthly_debt_payment, monthly_living,
                monthly_invest, exit_months, exit_date, savings_12_months, savings_at_exit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, profile_id,
                calculation_data.get("mode"),
                calculation_data.get("total_income"),
                calculation_data.get("mandatory_living"),
                calculation_data.get("mandatory_debt"),
                calculation_data.get("free_cash"),
                calculation_data.get("monthly_savings"),
                calculation_data.get("monthly_debt_payment"),
                calculation_data.get("monthly_living"),
                calculation_data.get("monthly_invest"),
                calculation_data.get("exit_months"),
                calculation_data.get("exit_date"),
                calculation_data.get("savings_12_months"),
                calculation_data.get("savings_at_exit")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_latest_calculation(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get most recent calculation for user"""
        async with self._connection.execute(
            """SELECT * FROM calculations 
               WHERE user_id = ? 
               ORDER BY calculated_at DESC LIMIT 1""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== STATISTICS ====================
    
    async def get_user_count(self) -> int:
        """Get total number of users"""
        async with self._connection.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def get_users_by_language(self) -> Dict[str, int]:
        """Get user count by language"""
        async with self._connection.execute(
            "SELECT language, COUNT(*) as count FROM users GROUP BY language"
        ) as cursor:
            rows = await cursor.fetchall()
            return {row["language"]: row["count"] for row in rows}
    
    # ==================== KATM LOANS OPERATIONS ====================
    
    async def save_katm_loans(
        self,
        user_id: int,
        loans: list,
        pdf_filename: str = None,
        profile_id: int = None
    ) -> List[int]:
        """Save parsed KATM loans"""
        loan_ids = []
        
        for loan in loans:
            cursor = await self._connection.execute(
                """INSERT INTO katm_loans 
                   (user_id, profile_id, bank_name, contract_number, loan_type,
                    original_amount, remaining_balance, monthly_payment,
                    currency, status, start_date, end_date, pdf_filename)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    profile_id,
                    loan.bank_name,
                    getattr(loan, 'contract_number', ''),
                    getattr(loan, 'loan_type', ''),
                    getattr(loan, 'original_amount', 0),
                    loan.remaining_balance,
                    loan.monthly_payment,
                    getattr(loan, 'currency', 'UZS'),
                    loan.status,
                    getattr(loan, 'start_date', ''),
                    getattr(loan, 'end_date', ''),
                    pdf_filename
                )
            )
            loan_ids.append(cursor.lastrowid)
        
        await self._connection.commit()
        return loan_ids
    
    async def get_user_katm_loans(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all KATM loans for user"""
        async with self._connection.execute(
            """SELECT * FROM katm_loans 
               WHERE user_id = ? AND status = 'active'
               ORDER BY parsed_at DESC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def delete_user_katm_loans(self, user_id: int) -> bool:
        """Delete all KATM loans for user (before re-upload)"""
        await self._connection.execute(
            "DELETE FROM katm_loans WHERE user_id = ?",
            (user_id,)
        )
        await self._connection.commit()
        return True

    # ==================== TRANSACTION HISTORY OPERATIONS ====================
    
    async def save_transaction_summary(
        self,
        user_id: int,
        source_file: str,
        source_type: str,
        summary: Dict[str, Any]
    ) -> int:
        """Save transaction history summary"""
        cursor = await self._connection.execute(
            """INSERT INTO transaction_history 
               (user_id, source_file, source_type, total_income, total_expense,
                income_count, expense_count, monthly_income, monthly_expense,
                period_start, period_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                source_file,
                source_type,
                summary.get("total_income", 0),
                summary.get("total_expense", 0),
                summary.get("income_count", 0),
                summary.get("expense_count", 0),
                summary.get("monthly_income", 0),
                summary.get("monthly_expense", 0),
                summary.get("period_start", ""),
                summary.get("period_end", "")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_user_transaction_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all transaction history records for user"""
        async with self._connection.execute(
            """SELECT * FROM transaction_history 
               WHERE user_id = ?
               ORDER BY parsed_at DESC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_latest_transaction_summary(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get most recent transaction summary for user"""
        async with self._connection.execute(
            """SELECT * FROM transaction_history 
               WHERE user_id = ? 
               ORDER BY parsed_at DESC LIMIT 1""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def delete_user_transaction_history(self, user_id: int) -> bool:
        """Delete all transaction history for user"""
        await self._connection.execute(
            "DELETE FROM transaction_history WHERE user_id = ?",
            (user_id,)
        )
        await self._connection.commit()
        return True


# Singleton database instance
_db: Optional[Database] = None


async def get_database(db_path: str = None) -> Database:
    """Get or create database instance"""
    global _db
    if _db is None:
        from app.config import DATABASE_URL
        _db = Database(str(db_path or DATABASE_URL))
        await _db.connect()
    return _db


async def close_database():
    """Close database connection"""
    global _db
    if _db:
        await _db.close()
        _db = None
