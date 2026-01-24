"""
Database Tests
"""
import pytest
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database


@pytest.fixture
async def test_db():
    """Create a test database"""
    db = Database(":memory:")
    await db.connect()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_create_user(test_db):
    """Test user creation"""
    user_id = await test_db.create_user(
        telegram_id=123456789,
        phone_number="+998901234567",
        first_name="Test",
        last_name="User",
        username="testuser",
        language="uz"
    )
    
    assert user_id is not None
    assert user_id > 0


@pytest.mark.asyncio
async def test_get_user(test_db):
    """Test getting user by telegram_id"""
    await test_db.create_user(
        telegram_id=123456789,
        phone_number="+998901234567",
        first_name="Test",
        language="ru"
    )
    
    user = await test_db.get_user(123456789)
    
    assert user is not None
    assert user["telegram_id"] == 123456789
    assert user["phone_number"] == "+998901234567"
    assert user["language"] == "ru"


@pytest.mark.asyncio
async def test_update_user(test_db):
    """Test updating user"""
    await test_db.create_user(
        telegram_id=123456789,
        phone_number="+998901234567",
        language="uz"
    )
    
    await test_db.update_user(123456789, language="ru", mode="family")
    
    user = await test_db.get_user(123456789)
    assert user["language"] == "ru"
    assert user["mode"] == "family"


@pytest.mark.asyncio
async def test_create_financial_profile(test_db):
    """Test creating financial profile"""
    user_id = await test_db.create_user(
        telegram_id=123456789,
        phone_number="+998901234567"
    )
    
    profile_id = await test_db.create_financial_profile(
        user_id=user_id,
        income_self=10_000_000,
        rent=2_000_000,
        loan_payment=1_500_000,
        total_debt=50_000_000
    )
    
    assert profile_id is not None
    
    profile = await test_db.get_financial_profile(user_id)
    assert profile["income_self"] == 10_000_000
    assert profile["rent"] == 2_000_000


@pytest.mark.asyncio
async def test_save_calculation(test_db):
    """Test saving calculation"""
    user_id = await test_db.create_user(
        telegram_id=123456789,
        phone_number="+998901234567"
    )
    
    profile_id = await test_db.create_financial_profile(
        user_id=user_id,
        income_self=10_000_000
    )
    
    calc_id = await test_db.save_calculation(
        user_id=user_id,
        profile_id=profile_id,
        calculation_data={
            "mode": "debt",
            "total_income": 10_000_000,
            "free_cash": 5_000_000,
            "monthly_savings": 500_000,
            "exit_months": 24,
            "exit_date": "2028-01"
        }
    )
    
    assert calc_id is not None
    
    calc = await test_db.get_latest_calculation(user_id)
    assert calc["mode"] == "debt"
    assert calc["exit_months"] == 24


@pytest.mark.asyncio
async def test_user_count(test_db):
    """Test user count"""
    count = await test_db.get_user_count()
    assert count == 0
    
    await test_db.create_user(telegram_id=1, phone_number="+1")
    await test_db.create_user(telegram_id=2, phone_number="+2")
    
    count = await test_db.get_user_count()
    assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
