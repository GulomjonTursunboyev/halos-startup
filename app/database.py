"""
HALOS Database Module
SQLite/PostgreSQL database with async support for user data and financial plans
Supports both local SQLite and cloud PostgreSQL (Supabase/Railway)
"""
import os
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import logging
import ssl

logger = logging.getLogger(__name__)

# Check if we're using PostgreSQL (production - Supabase/Railway)
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    try:
        import asyncpg
        logger.info("Using PostgreSQL database (asyncpg)")
    except ImportError:
        logger.error("asyncpg not installed! Run: pip install asyncpg")
        USE_POSTGRES = False


def parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL into connection parameters"""
    # Replace postgres:// with postgresql://
    url = url.replace("postgres://", "postgresql://")
    
    # Parse URL
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    
    params = {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
    }
    
    # Log connection info (without password)
    logger.info(f"Database: host={params['host']}, port={params['port']}, user={params['user']}, db={params['database']}")
    
    return params


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._connection = None
        self._pool = None  # For PostgreSQL connection pool
        self.is_postgres = USE_POSTGRES
    
    async def connect(self):
        """Initialize database connection and create tables"""
        if self.is_postgres:
            logger.info("Connecting to PostgreSQL (Supabase/Railway)...")
            
            # Format URL for asyncpg
            db_url = DATABASE_URL
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            # Mask password for logging
            from urllib.parse import urlparse
            p = urlparse(db_url)
            masked_url = f"{p.scheme}://{p.username}:****@{p.hostname}:{p.port}{p.path}"
            logger.info(f"Connecting to: {masked_url}")
            
            # Retry logic for connection
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # Supabase free tier limits - use minimal pool size
                    self._pool = await asyncpg.create_pool(
                        dsn=db_url,
                        min_size=2,      # Minimal connections to avoid hitting limit
                        max_size=10,     # Max 10 concurrent (Supabase free tier limit ~15-20)
                        command_timeout=60,  # Longer timeout for reliability
                        timeout=30,      # Connection acquire timeout
                        ssl='require',
                        max_inactive_connection_lifetime=60  # Close idle connections faster
                    )
                    await self._create_tables_postgres()
                    logger.info("PostgreSQL connected and tables created!")
                    return
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"PostgreSQL connection attempt {attempt + 1}/{max_retries} failed: {e}")
                    
                    if "Max client connections" in error_msg:
                        # Wait before retry - connections might be released
                        wait_time = (attempt + 1) * 3  # 3, 6, 9, 12, 15 seconds
                        logger.info(f"Max connections reached, waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # SSL error - try without explicit SSL
                    if ("SSL" in error_msg or "terminal" in error_msg) and attempt == 0:
                        try:
                            logger.info("Retrying without explicit SSL requirement...")
                            self._pool = await asyncpg.create_pool(
                                dsn=db_url,
                                min_size=2,
                                max_size=10,
                                command_timeout=60,
                                timeout=30,
                                max_inactive_connection_lifetime=60
                            )
                            await self._create_tables_postgres()
                            logger.info("PostgreSQL connected (No SSL)!")
                            return
                        except Exception as e2:
                            logger.error(f"PostgreSQL retry without SSL failed: {e2}")
                    
                    if attempt == max_retries - 1:
                        raise
                    
                    await asyncio.sleep(2)
        else:
            # SQLite (Local development)
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._create_tables_sqlite()
            await self._run_migrations()
            logger.info(f"SQLite connected: {self.db_path}")
    
    async def ensure_connection(self):
        """Ensure database connection is active, reconnect if needed"""
        if self.is_postgres:
            if self._pool is None or self._pool._closed:
                logger.warning("PostgreSQL pool is None or closed, reconnecting...")
                await self.connect()
        else:
            if self._connection is None:
                logger.warning("SQLite connection is None, reconnecting...")
                await self.connect()
    
    async def execute_update(self, query: str, *args):
        """Execute an UPDATE/INSERT query safely with auto-reconnect"""
        await self.ensure_connection()
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                await conn.execute(query, *args)
        else:
            await self._connection.execute(query, args)
            await self._connection.commit()
    
    async def fetch_one(self, query: str, *args):
        """Fetch one row safely with auto-reconnect"""
        await self.ensure_connection()
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        else:
            cursor = await self._connection.execute(query, args)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args):
        """Fetch all rows safely with auto-reconnect"""
        await self.ensure_connection()
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        else:
            cursor = await self._connection.execute(query, args)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
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
                    bonus_voice_count INTEGER DEFAULT 0,
                    voice_tier TEXT DEFAULT 'basic',
                    voice_tier_expires TIMESTAMP,
                    reports_daily BOOLEAN DEFAULT FALSE,
                    reports_weekly BOOLEAN DEFAULT FALSE,
                    reports_monthly BOOLEAN DEFAULT TRUE,
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
                    category_key TEXT,
                    amount REAL DEFAULT 0,
                    description TEXT,
                    original_text TEXT,
                    debt_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add category_key column if it doesn't exist (migration)
            try:
                await conn.execute("""
                    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_key TEXT
                """)
            except Exception:
                pass  # Column already exists
            
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
            
            # AI Learning table - foydalanuvchi tuzatishlaridan o'rganish
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_learning (
                    id SERIAL PRIMARY KEY,
                    pattern TEXT NOT NULL,
                    wrong_type TEXT NOT NULL,
                    correct_type TEXT NOT NULL,
                    wrong_category TEXT,
                    correct_category TEXT,
                    context_keywords TEXT,
                    correction_count INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pattern, correct_type, correct_category)
                )
            """)
            
            # Marketing events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS marketing_events (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add marketing columns to users table
            try:
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_source TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_campaign TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_medium TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_raw TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS used_promo_codes TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_reengagement TIMESTAMP")
                # User engagement columns
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_reminder_sent TIMESTAMP")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_blocked BOOLEAN DEFAULT FALSE")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS engagement_streak INTEGER DEFAULT 0")
            except Exception:
                pass  # Columns already exist
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON financial_profiles(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_usage_user_month ON voice_usage(user_id, month)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_debts_user_id ON personal_debts(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_debts_status ON personal_debts(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_pattern ON ai_learning(pattern)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_marketing_events_telegram_id ON marketing_events(telegram_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_marketing_events_type ON marketing_events(event_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_utm_source ON users(utm_source)")
    
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
                bonus_voice_count INTEGER DEFAULT 0,
                voice_tier TEXT DEFAULT 'basic',
                voice_tier_expires TIMESTAMP,
                reports_daily INTEGER DEFAULT 0,
                reports_weekly INTEGER DEFAULT 0,
                reports_monthly INTEGER DEFAULT 1,
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
                category_key TEXT,
                amount REAL DEFAULT 0,
                description TEXT,
                original_text TEXT,
                debt_id INTEGER,
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
            
            -- AI Learning table - foydalanuvchi tuzatishlaridan o'rganish
            CREATE TABLE IF NOT EXISTS ai_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                wrong_type TEXT NOT NULL,
                correct_type TEXT NOT NULL,
                wrong_category TEXT,
                correct_category TEXT,
                context_keywords TEXT,
                correction_count INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pattern, correct_type, correct_category)
            );
            
            -- Marketing events table
            CREATE TABLE IF NOT EXISTS marketing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
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
            CREATE INDEX IF NOT EXISTS idx_ai_learning_pattern ON ai_learning(pattern);
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
            # Marketing columns
            ("users", "utm_source", "TEXT"),
            ("users", "utm_campaign", "TEXT"),
            ("users", "utm_medium", "TEXT"),
            ("users", "utm_raw", "TEXT"),
            ("users", "used_promo_codes", "TEXT"),
            ("users", "last_reengagement", "TIMESTAMP"),
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
        """Get user by Telegram ID with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.is_postgres:
                    async with self._pool.acquire(timeout=15) as conn:
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
            except (asyncio.TimeoutError, TimeoutError) as e:
                logger.warning(f"get_user timeout attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"get_user error: {e}")
                raise
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by database ID"""
        try:
            if self.is_postgres:
                async with self._pool.acquire(timeout=15) as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM users WHERE id = $1", user_id
                    )
                    return dict(row) if row else None
            else:
                async with self._connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_user_by_id error: {e}")
            return None
    
    async def create_user(
        self,
        telegram_id: int,
        phone_number: str,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        language: str = "uz"
    ) -> int:
        """Create a new user and return user ID (id = telegram_id)"""
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                # id = telegram_id bo'lishi kerak (bizning DB strukturamiz)
                return await conn.fetchval(
                    """INSERT INTO users (id, telegram_id, phone_number, first_name, last_name, username, language)
                       VALUES ($1, $1, $2, $3, $4, $5, $6) RETURNING id""",
                    telegram_id, phone_number, first_name, last_name, username, language
                )
        else:
            cursor = await self._connection.execute(
                """INSERT INTO users (id, telegram_id, phone_number, first_name, last_name, username, language)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, telegram_id, phone_number, first_name, last_name, username, language)
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
        if self.is_postgres:
            # PostgreSQL: use datetime object directly
            return await self.update_user(telegram_id, last_active=datetime.now())
        else:
            # SQLite: use ISO format string
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

    # ==================== ADMIN STATISTICS ====================
    
    async def get_admin_statistics(self) -> dict:
        """Admin panel uchun to'liq statistikani olish"""
        stats = {}
        
        if self.is_postgres:
            async with self._pool.acquire() as conn:
                # Jami foydalanuvchilar
                row = await conn.fetchrow("SELECT COUNT(*) as total FROM users")
                stats["total_users"] = row["total"] if row else 0
                
                # Bugungi yangi foydalanuvchilar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as today FROM users 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                stats["today_users"] = row["today"] if row else 0
                
                # Haftalik yangi foydalanuvchilar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as week FROM users 
                    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                """)
                stats["week_users"] = row["week"] if row else 0
                
                # Oylik yangi foydalanuvchilar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as month FROM users 
                    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                """)
                stats["month_users"] = row["month"] if row else 0
                
                # ==================== PRO STATISTIKASI ====================
                
                # Jami aktiv PRO foydalanuvchilar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as pro FROM users 
                    WHERE subscription_tier = 'pro' 
                    AND (subscription_expires IS NULL OR subscription_expires > NOW())
                """)
                stats["active_pro"] = row["pro"] if row else 0
                
                # Haftalik PRO sotib olganlar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as weekly FROM users 
                    WHERE subscription_plan = 'pro_weekly'
                    AND subscription_tier = 'pro'
                """)
                stats["pro_weekly"] = row["weekly"] if row else 0
                
                # Oylik PRO sotib olganlar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as monthly FROM users 
                    WHERE subscription_plan = 'pro_monthly'
                    AND subscription_tier = 'pro'
                """)
                stats["pro_monthly"] = row["monthly"] if row else 0
                
                # Yillik PRO sotib olganlar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as yearly FROM users 
                    WHERE subscription_plan = 'pro_yearly'
                    AND subscription_tier = 'pro'
                """)
                stats["pro_yearly"] = row["yearly"] if row else 0
                
                # Promo orqali PRO olganlar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as promo FROM users 
                    WHERE subscription_plan = 'promo'
                    AND subscription_tier = 'pro'
                """)
                stats["pro_promo"] = row["promo"] if row else 0
                
                # Trial PRO
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as trial FROM users 
                    WHERE subscription_plan = 'trial'
                    AND subscription_tier = 'pro'
                """)
                stats["pro_trial"] = row["trial"] if row else 0
                
                # Muddati tugagan PRO
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as expired FROM users 
                    WHERE subscription_tier = 'pro' 
                    AND subscription_expires IS NOT NULL 
                    AND subscription_expires <= NOW()
                """)
                stats["pro_expired"] = row["expired"] if row else 0
                
                # ==================== MOLIYAVIY STATISTIKA ====================
                
                # Jami tranzaksiyalar
                row = await conn.fetchrow("SELECT COUNT(*) as total FROM transactions")
                stats["total_transactions"] = row["total"] if row else 0
                
                # Bugungi tranzaksiyalar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as today FROM transactions 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                stats["today_transactions"] = row["today"] if row else 0
                
                # Jami qarzlar
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as total, COALESCE(SUM(amount), 0) as sum 
                    FROM personal_debts WHERE status = 'active'
                """)
                stats["active_debts"] = row["total"] if row else 0
                stats["total_debt_amount"] = row["sum"] if row else 0
                
                # ==================== TIL STATISTIKASI ====================
                
                rows = await conn.fetch("""
                    SELECT language, COUNT(*) as count FROM users 
                    GROUP BY language
                """)
                stats["languages"] = {row["language"]: row["count"] for row in rows}
                
        else:
            # SQLite versiyasi
            cursor = await self._connection.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            stats["total_users"] = row[0] if row else 0
            
            cursor = await self._connection.execute("""
                SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')
            """)
            row = await cursor.fetchone()
            stats["today_users"] = row[0] if row else 0
            
            # ... boshqa statistikalar ham shu formatda
            stats["week_users"] = 0
            stats["month_users"] = 0
            stats["active_pro"] = 0
            stats["pro_weekly"] = 0
            stats["pro_monthly"] = 0
            stats["pro_yearly"] = 0
            stats["pro_promo"] = 0
            stats["pro_trial"] = 0
            stats["pro_expired"] = 0
            stats["total_transactions"] = 0
            stats["today_transactions"] = 0
            stats["active_debts"] = 0
            stats["total_debt_amount"] = 0
            stats["languages"] = {}
        
        return stats

    # ==================== AI LEARNING METHODS ====================
    
    async def save_ai_correction(self, pattern: str, wrong_type: str, correct_type: str,
                                  wrong_category: str = None, correct_category: str = None,
                                  context_keywords: str = None) -> int:
        """
        Foydalanuvchi tuzatishini saqlash - AI o'rganishi uchun
        Agar pattern mavjud bo'lsa, correction_count ni oshirish
        """
        if USE_POSTGRES:
            async with self._pool.acquire() as conn:
                # Avval mavjudligini tekshirish
                existing = await conn.fetchrow("""
                    SELECT id, correction_count FROM ai_learning 
                    WHERE pattern = $1 AND correct_type = $2 AND correct_category = $3
                """, pattern, correct_type, correct_category or '')
                
                if existing:
                    # Mavjud bo'lsa - counter va confidence ni oshirish
                    new_count = existing["correction_count"] + 1
                    new_confidence = min(1.0, 0.5 + (new_count * 0.1))  # Max 1.0
                    await conn.execute("""
                        UPDATE ai_learning 
                        SET correction_count = $1, confidence = $2, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $3
                    """, new_count, new_confidence, existing["id"])
                    return existing["id"]
                else:
                    # Yangi yozuv
                    row = await conn.fetchrow("""
                        INSERT INTO ai_learning 
                        (pattern, wrong_type, correct_type, wrong_category, correct_category, context_keywords)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id
                    """, pattern, wrong_type, correct_type, wrong_category, correct_category, context_keywords)
                    return row["id"]
        else:
            cursor = await self._connection.execute("""
                SELECT id, correction_count FROM ai_learning 
                WHERE pattern = ? AND correct_type = ? AND correct_category = ?
            """, (pattern, correct_type, correct_category or ''))
            existing = await cursor.fetchone()
            
            if existing:
                new_count = existing[1] + 1
                new_confidence = min(1.0, 0.5 + (new_count * 0.1))
                await self._connection.execute("""
                    UPDATE ai_learning 
                    SET correction_count = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_count, new_confidence, existing[0]))
                await self._connection.commit()
                return existing[0]
            else:
                cursor = await self._connection.execute("""
                    INSERT INTO ai_learning 
                    (pattern, wrong_type, correct_type, wrong_category, correct_category, context_keywords)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pattern, wrong_type, correct_type, wrong_category, correct_category, context_keywords))
                await self._connection.commit()
                return cursor.lastrowid
    
    async def get_ai_learned_patterns(self, min_confidence: float = 0.5) -> list:
        """
        AI o'rgangan patternlarni olish
        Faqat yuqori confidence bo'lganlarni qaytaradi
        """
        if USE_POSTGRES:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT pattern, correct_type, correct_category, context_keywords, 
                           correction_count, confidence
                    FROM ai_learning 
                    WHERE confidence >= $1
                    ORDER BY correction_count DESC, confidence DESC
                """, min_confidence)
                return [dict(row) for row in rows]
        else:
            cursor = await self._connection.execute("""
                SELECT pattern, correct_type, correct_category, context_keywords,
                       correction_count, confidence
                FROM ai_learning 
                WHERE confidence >= ?
                ORDER BY correction_count DESC, confidence DESC
            """, (min_confidence,))
            rows = await cursor.fetchall()
            return [
                {
                    "pattern": row[0],
                    "correct_type": row[1],
                    "correct_category": row[2],
                    "context_keywords": row[3],
                    "correction_count": row[4],
                    "confidence": row[5]
                }
                for row in rows
            ]
    
    async def check_ai_pattern(self, text: str) -> dict:
        """
        Matnni AI o'rgangan patternlar bilan solishtirish
        Agar mos pattern topilsa, to'g'ri type/category ni qaytarish
        """
        text_lower = text.lower()
        patterns = await self.get_ai_learned_patterns(min_confidence=0.6)
        
        best_match = None
        best_score = 0
        
        for p in patterns:
            pattern = p["pattern"].lower()
            # Pattern matnda borligini tekshirish
            if pattern in text_lower:
                # Score = confidence * correction_count
                score = p["confidence"] * p["correction_count"]
                if score > best_score:
                    best_score = score
                    best_match = p
        
        return best_match

    # ==================== ADMIN USER MANAGEMENT ====================
    
    async def admin_delete_user(self, telegram_id: int) -> dict:
        """
        Admin: Foydalanuvchini va uning barcha ma'lumotlarini o'chirish
        
        Returns:
            {
                "success": True/False,
                "user_deleted": True/False,
                "transactions_deleted": int,
                "debts_deleted": int,
                "voice_usage_deleted": int,
                "feature_usage_deleted": int,
                "error": str (agar xato bo'lsa)
            }
        """
        result = {
            "success": False,
            "user_deleted": False,
            "transactions_deleted": 0,
            "debts_deleted": 0,
            "voice_usage_deleted": 0,
            "feature_usage_deleted": 0,
            "financial_profile_deleted": False,
            "ai_learning_deleted": 0,
        }
        
        try:
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    # Avval user mavjudligini tekshirish
                    user = await conn.fetchrow(
                        "SELECT id, telegram_id, username, first_name FROM users WHERE telegram_id = $1",
                        telegram_id
                    )
                    if not user:
                        result["error"] = f"User topilmadi: {telegram_id}"
                        return result
                    
                    user_id = user["id"]  # id = telegram_id
                    
                    # 1. Transactions o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM transactions WHERE user_id = $1", user_id
                    )
                    result["transactions_deleted"] = int(deleted.split()[-1]) if deleted else 0
                    
                    # 2. Personal debts o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM personal_debts WHERE user_id = $1", user_id
                    )
                    result["debts_deleted"] = int(deleted.split()[-1]) if deleted else 0
                    
                    # 3. Voice usage o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM voice_usage WHERE user_id = $1", user_id
                    )
                    result["voice_usage_deleted"] = int(deleted.split()[-1]) if deleted else 0
                    
                    # 4. Feature usage o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM feature_usage WHERE user_id = $1", user_id
                    )
                    result["feature_usage_deleted"] = int(deleted.split()[-1]) if deleted else 0
                    
                    # 5. Financial profile o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM financial_profiles WHERE user_id = $1", user_id
                    )
                    result["financial_profile_deleted"] = "DELETE 1" in str(deleted)
                    
                    # 6. AI learning data o'chirish (agar user_id bo'lsa)
                    try:
                        deleted = await conn.execute(
                            "DELETE FROM ai_learning WHERE user_id = $1", user_id
                        )
                        result["ai_learning_deleted"] = int(deleted.split()[-1]) if deleted else 0
                    except:
                        pass  # ai_learning da user_id bo'lmasligi mumkin
                    
                    # 7. KATM loans o'chirish
                    try:
                        deleted = await conn.execute(
                            "DELETE FROM katm_loans WHERE user_id = $1", user_id
                        )
                    except:
                        pass
                    
                    # 8. Payments o'chirish
                    try:
                        deleted = await conn.execute(
                            "DELETE FROM payments WHERE user_id = $1", user_id
                        )
                    except:
                        pass
                    
                    # 9. Transaction history o'chirish
                    try:
                        deleted = await conn.execute(
                            "DELETE FROM transaction_history WHERE user_id = $1", user_id
                        )
                    except:
                        pass
                    
                    # 10. Calculations o'chirish
                    try:
                        deleted = await conn.execute(
                            "DELETE FROM calculations WHERE user_id = $1", user_id
                        )
                    except:
                        pass
                    
                    # OXIRIDA: User o'chirish
                    deleted = await conn.execute(
                        "DELETE FROM users WHERE telegram_id = $1", telegram_id
                    )
                    result["user_deleted"] = "DELETE 1" in str(deleted)
                    result["success"] = result["user_deleted"]
                    result["user_info"] = {
                        "telegram_id": telegram_id,
                        "username": user["username"],
                        "first_name": user["first_name"]
                    }
                    
            else:
                # SQLite
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT id, telegram_id, username, first_name FROM users WHERE telegram_id = ?",
                        (telegram_id,)
                    )
                    user = await cursor.fetchone()
                    if not user:
                        result["error"] = f"User topilmadi: {telegram_id}"
                        return result
                    
                    user_id = user[0]
                    
                    # O'chirish
                    await db.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
                    await db.execute("DELETE FROM personal_debts WHERE user_id = ?", (user_id,))
                    await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
                    await db.commit()
                    
                    result["user_deleted"] = True
                    result["success"] = True
                    
            logger.info(f"[Admin] User o'chirildi: {telegram_id}, natija: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[Admin] User o'chirishda xato: {e}")
            result["error"] = str(e)
            return result

    async def admin_clear_all_transactions(self, telegram_id: int = None) -> dict:
        """
        Admin: Barcha tranzaksiyalarni o'chirish
        
        Args:
            telegram_id: Agar berilsa, faqat shu userni tranzaksiyalarini o'chiradi
                        Agar None bo'lsa, BARCHA tranzaksiyalarni o'chiradi
        
        Returns:
            {"success": True/False, "deleted_count": int, "error": str}
        """
        result = {"success": False, "deleted_count": 0}
        
        try:
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    if telegram_id:
                        # Faqat bitta user
                        deleted = await conn.execute(
                            "DELETE FROM transactions WHERE user_id = $1", telegram_id
                        )
                    else:
                        # BARCHA tranzaksiyalar
                        deleted = await conn.execute("DELETE FROM transactions")
                    
                    result["deleted_count"] = int(deleted.split()[-1]) if deleted else 0
                    result["success"] = True
            else:
                async with aiosqlite.connect(self.db_path) as db:
                    if telegram_id:
                        cursor = await db.execute(
                            "DELETE FROM transactions WHERE user_id = ?", (telegram_id,)
                        )
                    else:
                        cursor = await db.execute("DELETE FROM transactions")
                    result["deleted_count"] = cursor.rowcount
                    await db.commit()
                    result["success"] = True
                    
            logger.info(f"[Admin] Tranzaksiyalar o'chirildi: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[Admin] Tranzaksiya o'chirishda xato: {e}")
            result["error"] = str(e)
            return result

    async def admin_get_user_info(self, telegram_id: int) -> Optional[dict]:
        """Admin: User haqida to'liq ma'lumot olish"""
        try:
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    user = await conn.fetchrow("""
                        SELECT u.*, 
                            (SELECT COUNT(*) FROM transactions WHERE user_id = u.id) as transaction_count,
                            (SELECT COUNT(*) FROM personal_debts WHERE user_id = u.id) as debt_count,
                            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = u.id AND type = 'income') as total_income,
                            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = u.id AND type = 'expense') as total_expense
                        FROM users u WHERE u.telegram_id = $1
                    """, telegram_id)
                    
                    if user:
                        return dict(user)
            return None
        except Exception as e:
            logger.error(f"[Admin] User info olishda xato: {e}")
            return None

    async def admin_list_users(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """Admin: Userlar ro'yxatini olish"""
        try:
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT telegram_id, username, first_name, subscription_tier, 
                               created_at, last_active,
                               (SELECT COUNT(*) FROM transactions WHERE user_id = users.id) as tx_count
                        FROM users 
                        ORDER BY created_at DESC
                        LIMIT $1 OFFSET $2
                    """, limit, offset)
                    return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"[Admin] Userlar ro'yxati olishda xato: {e}")
            return []

    # ==================== MARKETING OPERATIONS ====================
    
    async def log_marketing_event(
        self, 
        telegram_id: int, 
        event_type: str, 
        event_data: dict = None
    ) -> bool:
        """Log marketing event for analytics"""
        try:
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO marketing_events (telegram_id, event_type, event_data)
                        VALUES ($1, $2, $3)
                    """, telegram_id, event_type, json.dumps(event_data or {}))
            else:
                await self._connection.execute("""
                    INSERT INTO marketing_events (telegram_id, event_type, event_data)
                    VALUES (?, ?, ?)
                """, (telegram_id, event_type, json.dumps(event_data or {})))
                await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error logging marketing event: {e}")
            return False
    
    async def get_inactive_users(self, days: int = 3) -> List[Dict[str, Any]]:
        """Get users who have been inactive for X days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT telegram_id, first_name, language, last_active, 
                               subscription_tier, last_reengagement
                        FROM users 
                        WHERE last_active < $1 
                        AND (last_reengagement IS NULL OR last_reengagement < $2)
                        AND subscription_tier != 'free'
                    """, cutoff_date, cutoff_date)
                    return [dict(row) for row in rows]
            else:
                async with self._connection.execute("""
                    SELECT telegram_id, first_name, language, last_active, 
                           subscription_tier, last_reengagement
                    FROM users 
                    WHERE last_active < ? 
                    AND (last_reengagement IS NULL OR last_reengagement < ?)
                    AND subscription_tier != 'free'
                """, (cutoff_date.isoformat(), cutoff_date.isoformat())) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting inactive users: {e}")
            return []
    
    async def get_expiring_trials(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get users whose trial is expiring within X hours"""
        try:
            now = datetime.now()
            cutoff = now + timedelta(hours=hours)
            
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT telegram_id, first_name, language, subscription_expires
                        FROM users 
                        WHERE subscription_tier = 'trial'
                        AND subscription_expires BETWEEN $1 AND $2
                    """, now, cutoff)
                    return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"Error getting expiring trials: {e}")
            return []
    
    async def get_expiring_pro(self, days: int = 3) -> List[Dict[str, Any]]:
        """Get PRO users whose subscription is expiring within X days"""
        try:
            now = datetime.now()
            cutoff = now + timedelta(days=days)
            
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT telegram_id, first_name, language, subscription_expires
                        FROM users 
                        WHERE subscription_tier = 'pro'
                        AND subscription_expires BETWEEN $1 AND $2
                    """, now, cutoff)
                    return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"Error getting expiring pro users: {e}")
            return []
    
    async def mark_reengagement_sent(self, telegram_id: int) -> bool:
        """Mark that re-engagement message was sent to user"""
        try:
            return await self.update_user(telegram_id, last_reengagement=datetime.now())
        except Exception as e:
            logger.error(f"Error marking reengagement: {e}")
            return False
    
    async def get_user_transaction_stats(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get user's transaction statistics for period"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            stats = {"income": 0, "expense": 0, "count": 0}
            
            if self.is_postgres:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow("""
                        SELECT 
                            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense,
                            COUNT(*) as count
                        FROM transactions 
                        WHERE user_id = $1 AND created_at >= $2
                    """, user_id, cutoff)
                    if row:
                        stats = dict(row)
            return stats
        except Exception as e:
            logger.error(f"Error getting transaction stats: {e}")
            return {"income": 0, "expense": 0, "count": 0}


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
