"""
HALOS Database Module
SQLite/PostgreSQL database with async support for user data and financial plans
Supports both local SQLite and cloud PostgreSQL (Supabase/Railway)
"""
import os
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)

# Check if we're using PostgreSQL (production - Supabase/Railway)
DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_DB_URL", "")
# Use Supabase URL if available, otherwise DATABASE_URL
POSTGRES_URL = SUPABASE_URL or DATABASE_URL
USE_POSTGRES = POSTGRES_URL.startswith("postgres")

if USE_POSTGRES:
    try:
        import asyncpg
        logger.info("Using PostgreSQL database (asyncpg)")
    except ImportError:
        logger.error("asyncpg not installed! Run: pip install asyncpg")
        USE_POSTGRES = False


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._connection = None
        self._pool = None  # For PostgreSQL connection pool
        self.is_postgres = USE_POSTGRES
    
    async def connect(self):
        """Initialize database connection and create tables"""
        if self.is_postgres:
            # PostgreSQL (Production - Supabase)
            db_url = POSTGRES_URL.replace("postgres://", "postgresql://")
            logger.info(f"Connecting to PostgreSQL (Supabase)...")
            
            # Supabase requires SSL - use 'require' mode
            # This works with Supabase pooler connections
            self._pool = await asyncpg.create_pool(
                db_url, 
                min_size=1, 
                max_size=5,
                command_timeout=60,
                ssl='require'  # Supabase requires SSL
            )
            await self._create_tables_postgres()
            logger.info("PostgreSQL (Supabase) connected and tables created")
        else:
            # SQLite (Local development)
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._create_tables_sqlite()
            await self._run_migrations()
            logger.info(f"SQLite connected: {self.db_path}")
    
    async def close(self):
        """Close database connection"""
        if self.is_postgres and self._pool:
            await self._pool.close()
            logger.info("PostgreSQL connection closed")
        elif self._connection:
            await self._connection.close()
            logger.info("SQLite connection closed")
    
    # ==================== TABLE CREATION ====================
    
    async def _create_tables_postgres(self):
        """Create all required tables for PostgreSQL"""
        async with self._pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
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
                )
            """)
            
            # Financial profiles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    income_self REAL DEFAULT 0,
                    income_partner REAL DEFAULT 0,
                    rent REAL DEFAULT 0,
                    kindergarten REAL DEFAULT 0,
                    utilities REAL DEFAULT 0,
                    loan_payment REAL DEFAULT 0,
                    total_debt REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Calculations history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS calculations (
                    id SERIAL PRIMARY KEY,
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
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # KATM parsed loans table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS katm_loans (
                    id SERIAL PRIMARY KEY,
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
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Transaction history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transaction_history (
                    id SERIAL PRIMARY KEY,
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
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Payments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
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
                    completed_at TIMESTAMP
                )
            """)
            
            # Feature usage tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_usage (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    feature TEXT NOT NULL,
                    usage_date DATE DEFAULT CURRENT_DATE,
                    usage_count INTEGER DEFAULT 1,
                    UNIQUE(user_id, feature, usage_date)
                )
            """)
            
            # Voice transactions table (AI yordamchi)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL DEFAULT 0,
                    description TEXT,
                    original_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Voice usage tracking (monthly limit)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS voice_usage (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    voice_count INTEGER DEFAULT 0,
                    total_duration INTEGER DEFAULT 0,
                    UNIQUE(user_id, month)
                )
            """)
            
            # Personal debts table (qarz munosabatlari)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS personal_debts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    debt_type TEXT NOT NULL,
                    person_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    original_text TEXT,
                    given_date DATE NOT NULL,
                    due_date DATE,
                    returned_date DATE,
                    status TEXT DEFAULT 'active',
                    returned_amount REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON financial_profiles(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_usage_user_month ON voice_usage(user_id, month)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_debts_user_id ON personal_debts(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_debts_status ON personal_debts(status)")
    
    async def _create_tables_sqlite(self):
        """Create all required tables for SQLite"""
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
            
            -- Voice transactions table (AI yordamchi)
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL DEFAULT 0,
                description TEXT,
                original_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            -- Voice usage tracking (monthly limit)
            CREATE TABLE IF NOT EXISTS voice_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                voice_count INTEGER DEFAULT 0,
                total_duration INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, month)
            );
            
            -- Personal debts table (qarz munosabatlari)
            CREATE TABLE IF NOT EXISTS personal_debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                debt_type TEXT NOT NULL,
                person_name TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                original_text TEXT,
                given_date DATE NOT NULL,
                due_date DATE,
                returned_date DATE,
                status TEXT DEFAULT 'active',
                returned_amount REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON financial_profiles(user_id);
            CREATE INDEX IF NOT EXISTS idx_calculations_user_id ON calculations(user_id);
            CREATE INDEX IF NOT EXISTS idx_katm_loans_user_id ON katm_loans(user_id);
            CREATE INDEX IF NOT EXISTS idx_transaction_history_user_id ON transaction_history(user_id);
            CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
            CREATE INDEX IF NOT EXISTS idx_feature_usage_user_id ON feature_usage(user_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
            CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
            CREATE INDEX IF NOT EXISTS idx_voice_usage_user_month ON voice_usage(user_id, month);
            CREATE INDEX IF NOT EXISTS idx_personal_debts_user_id ON personal_debts(user_id);
            CREATE INDEX IF NOT EXISTS idx_personal_debts_status ON personal_debts(status);
            CREATE INDEX IF NOT EXISTS idx_personal_debts_type ON personal_debts(debt_type);
        """)
        await self._connection.commit()
    
    async def _run_migrations(self):
        """Add new columns to existing tables (SQLite only)"""
        migrations = [
            ("users", "subscription_tier", "TEXT DEFAULT 'free'"),
            ("users", "subscription_plan", "TEXT"),
            ("users", "subscription_expires", "TIMESTAMP"),
            ("users", "subscription_auto_renew", "INTEGER DEFAULT 1"),
            ("users", "trial_used", "INTEGER DEFAULT 0"),
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
                pass  # Column already exists
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE telegram_id = $1", telegram_id
                )
                return dict(row) if row else None
        else:
            async with self._connection.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
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
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    """INSERT INTO users (telegram_id, phone_number, first_name, last_name, username, language)
                       VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                    telegram_id, phone_number, first_name, last_name, username, language
                )
        else:
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
        
        if self.is_postgres:
            # Build PostgreSQL query with $1, $2, etc.
            fields = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(kwargs.keys()))
            values = list(kwargs.values()) + [telegram_id]
            query = f"UPDATE users SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ${len(values)}"
            async with self._pool.acquire() as conn:
                await conn.execute(query, *values)
        else:
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
        return await self.update_user(telegram_id, last_active=datetime.now().isoformat())
    
    async def user_exists(self, telegram_id: int) -> bool:
        """Check if user exists"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT 1 FROM users WHERE telegram_id = $1", telegram_id
                )
                return result is not None
        else:
            async with self._connection.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                return await cursor.fetchone() is not None
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM users")
                return [dict(row) for row in rows]
        else:
            async with self._connection.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    # ==================== FINANCIAL PROFILE OPERATIONS ====================
    
    async def get_financial_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get latest financial profile for user"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM financial_profiles 
                       WHERE user_id = $1 
                       ORDER BY created_at DESC LIMIT 1""",
                    user_id
                )
                return dict(row) if row else None
        else:
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
        values = [user_id] + list(kwargs.values())
        
        if self.is_postgres:
            placeholders = ", ".join(f"${i+1}" for i in range(len(fields)))
            field_names = ", ".join(fields)
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    f"INSERT INTO financial_profiles ({field_names}) VALUES ({placeholders}) RETURNING id",
                    *values
                )
        else:
            placeholders = ", ".join(["?"] * len(fields))
            field_names = ", ".join(fields)
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
        
        if self.is_postgres:
            fields = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(kwargs.keys()))
            values = list(kwargs.values()) + [profile_id]
            query = f"UPDATE financial_profiles SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}"
            async with self._pool.acquire() as conn:
                await conn.execute(query, *values)
        else:
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
        values = (
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
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    """INSERT INTO calculations 
                       (user_id, profile_id, mode, total_income, mandatory_living, mandatory_debt,
                        free_cash, monthly_savings, monthly_debt_payment, monthly_living,
                        monthly_invest, exit_months, exit_date, savings_12_months, savings_at_exit)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                       RETURNING id""",
                    *values
                )
        else:
            cursor = await self._connection.execute(
                """INSERT INTO calculations 
                   (user_id, profile_id, mode, total_income, mandatory_living, mandatory_debt,
                    free_cash, monthly_savings, monthly_debt_payment, monthly_living,
                    monthly_invest, exit_months, exit_date, savings_12_months, savings_at_exit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values
            )
            await self._connection.commit()
            return cursor.lastrowid
    
    async def get_latest_calculation(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get most recent calculation for user"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM calculations 
                       WHERE user_id = $1 
                       ORDER BY calculated_at DESC LIMIT 1""",
                    user_id
                )
                return dict(row) if row else None
        else:
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
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        else:
            async with self._connection.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def get_users_by_language(self) -> Dict[str, int]:
        """Get user count by language"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT language, COUNT(*) as count FROM users GROUP BY language"
                )
                return {row["language"]: row["count"] for row in rows}
        else:
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
            values = (
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
            
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    loan_id = await conn.fetchval(
                        """INSERT INTO katm_loans 
                           (user_id, profile_id, bank_name, contract_number, loan_type,
                            original_amount, remaining_balance, monthly_payment,
                            currency, status, start_date, end_date, pdf_filename)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                           RETURNING id""",
                        *values
                    )
                    loan_ids.append(loan_id)
            else:
                cursor = await self._connection.execute(
                    """INSERT INTO katm_loans 
                       (user_id, profile_id, bank_name, contract_number, loan_type,
                        original_amount, remaining_balance, monthly_payment,
                        currency, status, start_date, end_date, pdf_filename)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    values
                )
                loan_ids.append(cursor.lastrowid)
        
        if not self.is_postgres:
            await self._connection.commit()
        return loan_ids
    
    async def get_user_katm_loans(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all KATM loans for user"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM katm_loans 
                       WHERE user_id = $1 AND status = 'active'
                       ORDER BY parsed_at DESC""",
                    user_id
                )
                return [dict(row) for row in rows]
        else:
            async with self._connection.execute(
                """SELECT * FROM katm_loans 
                   WHERE user_id = ? AND status = 'active'
                   ORDER BY parsed_at DESC""",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_user_katm_loans(self, user_id: int) -> bool:
        """Delete all KATM loans for user"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                await conn.execute("DELETE FROM katm_loans WHERE user_id = $1", user_id)
        else:
            await self._connection.execute("DELETE FROM katm_loans WHERE user_id = ?", (user_id,))
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
        values = (
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
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    """INSERT INTO transaction_history 
                       (user_id, source_file, source_type, total_income, total_expense,
                        income_count, expense_count, monthly_income, monthly_expense,
                        period_start, period_end)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                       RETURNING id""",
                    *values
                )
        else:
            cursor = await self._connection.execute(
                """INSERT INTO transaction_history 
                   (user_id, source_file, source_type, total_income, total_expense,
                    income_count, expense_count, monthly_income, monthly_expense,
                    period_start, period_end)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values
            )
            await self._connection.commit()
            return cursor.lastrowid
    
    async def get_user_transaction_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all transaction history records for user"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM transaction_history 
                       WHERE user_id = $1
                       ORDER BY parsed_at DESC""",
                    user_id
                )
                return [dict(row) for row in rows]
        else:
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
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM transaction_history 
                       WHERE user_id = $1 
                       ORDER BY parsed_at DESC LIMIT 1""",
                    user_id
                )
                return dict(row) if row else None
        else:
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
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                await conn.execute("DELETE FROM transaction_history WHERE user_id = $1", user_id)
        else:
            await self._connection.execute("DELETE FROM transaction_history WHERE user_id = ?", (user_id,))
            await self._connection.commit()
        return True
    
    # ==================== VOICE TRANSACTIONS (AI) ====================
    
    async def save_transaction(
        self,
        user_id: int,
        trans_type: str,
        category: str,
        amount: float,
        description: str = None,
        original_text: str = None
    ) -> int:
        """Save a voice transaction"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    """INSERT INTO transactions (user_id, type, category, amount, description, original_text)
                       VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                    user_id, trans_type, category, amount, description, original_text
                )
        else:
            cursor = await self._connection.execute(
                """INSERT INTO transactions (user_id, type, category, amount, description, original_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, trans_type, category, amount, description, original_text)
            )
            await self._connection.commit()
            return cursor.lastrowid
    
    async def get_user_transactions(
        self, 
        user_id: int, 
        trans_type: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get user's transactions with optional filters"""
        conditions = ["user_id = $1" if self.is_postgres else "user_id = ?"]
        params = [user_id]
        param_idx = 2
        
        if trans_type:
            if self.is_postgres:
                conditions.append(f"type = ${param_idx}")
                param_idx += 1
            else:
                conditions.append("type = ?")
            params.append(trans_type)
        
        if start_date:
            if self.is_postgres:
                conditions.append(f"created_at >= ${param_idx}")
                param_idx += 1
            else:
                conditions.append("created_at >= ?")
            params.append(start_date)
        
        if end_date:
            if self.is_postgres:
                conditions.append(f"created_at <= ${param_idx}")
                param_idx += 1
            else:
                conditions.append("created_at <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions)
        query = f"""SELECT * FROM transactions 
                    WHERE {where_clause} 
                    ORDER BY created_at DESC 
                    LIMIT {limit}"""
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        else:
            async with self._connection.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_transactions_summary(
        self, 
        user_id: int,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Get summary of user's transactions"""
        date_filter = ""
        params = [user_id]
        param_idx = 2
        
        if start_date:
            if self.is_postgres:
                date_filter += f" AND created_at >= ${param_idx}"
                param_idx += 1
            else:
                date_filter += " AND created_at >= ?"
            params.append(start_date)
        
        if end_date:
            if self.is_postgres:
                date_filter += f" AND created_at <= ${param_idx}"
            else:
                date_filter += " AND created_at <= ?"
            params.append(end_date)
        
        if self.is_postgres:
            query = f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(CASE WHEN type = 'income' THEN 1 END) as income_count,
                    COUNT(CASE WHEN type = 'expense' THEN 1 END) as expense_count
                FROM transactions 
                WHERE user_id = $1 {date_filter}
            """
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
                return dict(row) if row else {"total_income": 0, "total_expense": 0, "income_count": 0, "expense_count": 0}
        else:
            query = f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(CASE WHEN type = 'income' THEN 1 END) as income_count,
                    COUNT(CASE WHEN type = 'expense' THEN 1 END) as expense_count
                FROM transactions 
                WHERE user_id = ? {date_filter}
            """
            async with self._connection.execute(query, tuple(params)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {"total_income": 0, "total_expense": 0, "income_count": 0, "expense_count": 0}
    
    async def delete_transaction(self, transaction_id: int, user_id: int) -> bool:
        """Delete a transaction"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM transactions WHERE id = $1 AND user_id = $2",
                    transaction_id, user_id
                )
                return "DELETE" in result
        else:
            cursor = await self._connection.execute(
                "DELETE FROM transactions WHERE id = ? AND user_id = ?",
                (transaction_id, user_id)
            )
            await self._connection.commit()
            return cursor.rowcount > 0
    
    # ==================== VOICE USAGE TRACKING ====================
    
    async def get_voice_usage(self, user_id: int, month: str) -> Dict[str, Any]:
        """Get voice usage for a specific month"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM voice_usage WHERE user_id = $1 AND month = $2",
                    user_id, month
                )
                return dict(row) if row else {"voice_count": 0, "total_duration": 0}
        else:
            async with self._connection.execute(
                "SELECT * FROM voice_usage WHERE user_id = ? AND month = ?",
                (user_id, month)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {"voice_count": 0, "total_duration": 0}
    
    async def increment_voice_usage(self, user_id: int, month: str, duration: int = 0) -> bool:
        """Increment voice usage counter"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO voice_usage (user_id, month, voice_count, total_duration)
                    VALUES ($1, $2, 1, $3)
                    ON CONFLICT (user_id, month) 
                    DO UPDATE SET voice_count = voice_usage.voice_count + 1,
                                  total_duration = voice_usage.total_duration + $3
                """, user_id, month, duration)
        else:
            # Check if exists
            existing = await self.get_voice_usage(user_id, month)
            if existing.get("voice_count", 0) > 0:
                await self._connection.execute(
                    """UPDATE voice_usage 
                       SET voice_count = voice_count + 1, total_duration = total_duration + ?
                       WHERE user_id = ? AND month = ?""",
                    (duration, user_id, month)
                )
            else:
                await self._connection.execute(
                    """INSERT INTO voice_usage (user_id, month, voice_count, total_duration)
                       VALUES (?, ?, 1, ?)""",
                    (user_id, month, duration)
                )
            await self._connection.commit()
        return True
    
    # ==================== PERSONAL DEBTS ====================
    
    async def save_personal_debt(
        self,
        user_id: int,
        debt_type: str,
        person_name: str,
        amount: float,
        given_date: str,
        due_date: str = None,
        description: str = None,
        original_text: str = None
    ) -> int:
        """Save a personal debt record"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.fetchval("""
                    INSERT INTO personal_debts 
                    (user_id, debt_type, person_name, amount, given_date, due_date, description, original_text)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
                """, user_id, debt_type, person_name, amount, given_date, due_date, description, original_text)
        else:
            cursor = await self._connection.execute("""
                INSERT INTO personal_debts 
                (user_id, debt_type, person_name, amount, given_date, due_date, description, original_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, debt_type, person_name, amount, given_date, due_date, description, original_text))
            await self._connection.commit()
            return cursor.lastrowid
    
    async def get_user_debts(
        self, 
        user_id: int, 
        debt_type: str = None,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """Get user's personal debts"""
        conditions = ["user_id = $1" if self.is_postgres else "user_id = ?"]
        params = [user_id]
        param_idx = 2
        
        if status:
            if self.is_postgres:
                conditions.append(f"status = ${param_idx}")
                param_idx += 1
            else:
                conditions.append("status = ?")
            params.append(status)
        
        if debt_type:
            if self.is_postgres:
                conditions.append(f"debt_type = ${param_idx}")
            else:
                conditions.append("debt_type = ?")
            params.append(debt_type)
        
        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM personal_debts WHERE {where_clause} ORDER BY given_date DESC"
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        else:
            async with self._connection.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_debts_summary(self, user_id: int) -> Dict[str, Any]:
        """Get summary of user's debts"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN debt_type = 'lent' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_lent,
                        COALESCE(SUM(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_borrowed,
                        COUNT(CASE WHEN debt_type = 'lent' AND status = 'active' THEN 1 END) as lent_count,
                        COUNT(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN 1 END) as borrowed_count
                    FROM personal_debts 
                    WHERE user_id = $1
                """, user_id)
                return dict(row) if row else {"total_lent": 0, "total_borrowed": 0, "lent_count": 0, "borrowed_count": 0}
        else:
            async with self._connection.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN debt_type = 'lent' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_lent,
                    COALESCE(SUM(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN amount - returned_amount ELSE 0 END), 0) as total_borrowed,
                    COUNT(CASE WHEN debt_type = 'lent' AND status = 'active' THEN 1 END) as lent_count,
                    COUNT(CASE WHEN debt_type = 'borrowed' AND status = 'active' THEN 1 END) as borrowed_count
                FROM personal_debts 
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {"total_lent": 0, "total_borrowed": 0, "lent_count": 0, "borrowed_count": 0}
    
    async def update_debt_status(
        self, 
        debt_id: int, 
        user_id: int, 
        status: str,
        returned_amount: float = None,
        returned_date: str = None
    ) -> bool:
        """Update debt status"""
        updates = ["status = $1" if self.is_postgres else "status = ?"]
        params = [status]
        param_idx = 2
        
        if returned_amount is not None:
            if self.is_postgres:
                updates.append(f"returned_amount = ${param_idx}")
                param_idx += 1
            else:
                updates.append("returned_amount = ?")
            params.append(returned_amount)
        
        if returned_date:
            if self.is_postgres:
                updates.append(f"returned_date = ${param_idx}")
                param_idx += 1
            else:
                updates.append("returned_date = ?")
            params.append(returned_date)
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([debt_id, user_id])
        
        set_clause = ", ".join(updates)
        
        if self.is_postgres:
            query = f"UPDATE personal_debts SET {set_clause} WHERE id = ${param_idx} AND user_id = ${param_idx + 1}"
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, *params)
                return "UPDATE" in result
        else:
            query = f"UPDATE personal_debts SET {set_clause} WHERE id = ? AND user_id = ?"
            cursor = await self._connection.execute(query, tuple(params))
            await self._connection.commit()
            return cursor.rowcount > 0
    
    async def delete_debt(self, debt_id: int, user_id: int) -> bool:
        """Delete a debt record"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM personal_debts WHERE id = $1 AND user_id = $2",
                    debt_id, user_id
                )
                return "DELETE" in result
        else:
            cursor = await self._connection.execute(
                "DELETE FROM personal_debts WHERE id = ? AND user_id = ?",
                (debt_id, user_id)
            )
            await self._connection.commit()
            return cursor.rowcount > 0
    
    async def get_upcoming_debt_reminders(self, days_ahead: int = 3) -> List[Dict[str, Any]]:
        """Get debts with due dates approaching"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT pd.*, u.telegram_id, u.language
                    FROM personal_debts pd
                    JOIN users u ON pd.user_id = u.id
                    WHERE pd.status = 'active' 
                    AND pd.due_date IS NOT NULL
                    AND pd.due_date <= CURRENT_DATE + $1
                    AND pd.due_date >= CURRENT_DATE
                    ORDER BY pd.due_date ASC
                """, days_ahead)
                return [dict(row) for row in rows]
        else:
            async with self._connection.execute("""
                SELECT pd.*, u.telegram_id, u.language
                FROM personal_debts pd
                JOIN users u ON pd.user_id = u.id
                WHERE pd.status = 'active' 
                AND pd.due_date IS NOT NULL
                AND pd.due_date <= DATE('now', '+' || ? || ' days')
                AND pd.due_date >= DATE('now')
                ORDER BY pd.due_date ASC
            """, (days_ahead,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


# Singleton database instance
_db: Optional[Database] = None


async def get_database(db_path: str = None) -> Database:
    """Get or create database instance"""
    global _db
    if _db is None:
        if USE_POSTGRES:
            _db = Database()
        else:
            from app.config import DATABASE_PATH
            _db = Database(str(db_path or DATABASE_PATH))
        await _db.connect()
    return _db


async def close_database():
    """Close database connection"""
    global _db
    if _db:
        await _db.close()
        _db = None
