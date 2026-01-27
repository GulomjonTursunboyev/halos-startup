"""
Pydantic Models for API Request/Response
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


# ==================== ENUMS ====================

class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class DebtType(str, Enum):
    LENT = "lent"      # Men qarz berdim
    BORROWED = "borrowed"  # Men qarz oldim


class DebtStatus(str, Enum):
    ACTIVE = "active"
    RETURNED = "returned"
    PARTIAL = "partial"


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"


class Currency(str, Enum):
    UZS = "UZS"
    USD = "USD"
    RUB = "RUB"


# ==================== AUTH MODELS ====================

class PhoneLoginRequest(BaseModel):
    """Phone number login request"""
    phone_number: str = Field(..., pattern=r'^\+998\d{9}$', example="+998901234567")


class OTPVerifyRequest(BaseModel):
    """OTP verification request"""
    phone_number: str = Field(..., pattern=r'^\+998\d{9}$')
    otp_code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """JWT Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class TelegramLinkRequest(BaseModel):
    """Link Telegram account"""
    telegram_id: int
    verification_code: str


# ==================== USER MODELS ====================

class UserBase(BaseModel):
    """Base user model"""
    phone_number: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language: str = "uz"


class UserCreate(UserBase):
    """User creation model"""
    pass


class UserUpdate(BaseModel):
    """User update model"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfile(UserBase):
    """Full user profile"""
    id: int
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    subscription_expires: Optional[datetime] = None
    created_at: datetime
    last_active: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FinancialProfile(BaseModel):
    """User's financial profile"""
    monthly_income: float = 0
    monthly_expenses: float = 0
    savings_goal: float = 0
    savings_current: float = 0
    currency: Currency = Currency.UZS
    
    class Config:
        from_attributes = True


# ==================== TRANSACTION MODELS ====================

class TransactionBase(BaseModel):
    """Base transaction model"""
    amount: float = Field(..., gt=0)
    type: TransactionType
    category: str
    description: Optional[str] = None
    date: date = Field(default_factory=date.today)
    currency: Currency = Currency.UZS


class TransactionCreate(TransactionBase):
    """Create transaction request"""
    pass


class TransactionUpdate(BaseModel):
    """Update transaction request"""
    amount: Optional[float] = Field(None, gt=0)
    type: Optional[TransactionType] = None
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[date] = None


class Transaction(TransactionBase):
    """Full transaction model"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TransactionList(BaseModel):
    """Paginated transaction list"""
    items: List[Transaction]
    total: int
    page: int
    page_size: int
    has_more: bool


# ==================== DEBT MODELS ====================

class DebtBase(BaseModel):
    """Base debt model"""
    debt_type: DebtType
    person_name: str
    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    given_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    currency: Currency = Currency.UZS


class DebtCreate(DebtBase):
    """Create debt request"""
    pass


class DebtUpdate(BaseModel):
    """Update debt request"""
    person_name: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[DebtStatus] = None
    returned_amount: Optional[float] = None


class Debt(DebtBase):
    """Full debt model"""
    id: int
    user_id: int
    status: DebtStatus = DebtStatus.ACTIVE
    returned_amount: float = 0
    returned_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DebtSummary(BaseModel):
    """Debt summary"""
    total_lent: float  # Men bergan qarzlar
    total_borrowed: float  # Men olgan qarzlar
    lent_count: int
    borrowed_count: int
    net_balance: float  # total_lent - total_borrowed


# ==================== BUDGET MODELS ====================

class BudgetCategory(BaseModel):
    """Budget category"""
    category: str
    limit: float
    spent: float = 0
    remaining: float = 0
    percentage_used: float = 0


class MonthlyBudget(BaseModel):
    """Monthly budget"""
    month: str  # "2026-01"
    total_budget: float
    total_spent: float
    remaining: float
    categories: List[BudgetCategory]


class BudgetCreate(BaseModel):
    """Create/Update budget"""
    category: str
    limit: float = Field(..., gt=0)
    month: Optional[str] = None  # Default: current month


# ==================== ANALYTICS MODELS ====================

class DailyStats(BaseModel):
    """Daily statistics"""
    date: date
    income: float
    expense: float
    net: float


class CategoryStats(BaseModel):
    """Category statistics"""
    category: str
    total: float
    percentage: float
    transaction_count: int


class MonthlyAnalytics(BaseModel):
    """Monthly analytics"""
    month: str
    total_income: float
    total_expense: float
    savings: float
    savings_rate: float  # percentage
    top_expense_categories: List[CategoryStats]
    top_income_categories: List[CategoryStats]
    daily_stats: List[DailyStats]
    comparison_with_last_month: dict


class FinancialHealth(BaseModel):
    """Financial health score"""
    score: int  # 0-100
    grade: str  # A, B, C, D, F
    strengths: List[str]
    improvements: List[str]
    tips: List[str]


# ==================== SYNC MODELS ====================

class SyncStatus(BaseModel):
    """Sync status"""
    last_sync: Optional[datetime] = None
    pending_changes: int = 0
    is_synced: bool = True


class SyncRequest(BaseModel):
    """Sync request with local changes"""
    last_sync_timestamp: Optional[datetime] = None
    local_transactions: List[TransactionCreate] = []
    local_debts: List[DebtCreate] = []
    deleted_transaction_ids: List[int] = []
    deleted_debt_ids: List[int] = []


class SyncResponse(BaseModel):
    """Sync response with server changes"""
    server_transactions: List[Transaction]
    server_debts: List[Debt]
    deleted_transaction_ids: List[int]
    deleted_debt_ids: List[int]
    sync_timestamp: datetime
    conflicts: List[dict] = []


# ==================== NOTIFICATION MODELS ====================

class NotificationSettings(BaseModel):
    """User notification settings"""
    debt_reminders: bool = True
    budget_alerts: bool = True
    weekly_report: bool = True
    monthly_report: bool = True
    push_enabled: bool = True
    reminder_time: str = "09:00"  # HH:MM


class PushTokenRequest(BaseModel):
    """Register push notification token"""
    token: str
    platform: str  # "android" or "ios"
    device_id: Optional[str] = None
