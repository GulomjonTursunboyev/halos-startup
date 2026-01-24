"""
SOLVO Financial Engine Tests
Run: python -m pytest tests/ -v
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import calculate_finances, FinancialEngine, FinancialInput


class TestDebtMode:
    """Tests for debt mode calculations"""
    
    def test_basic_debt_calculation(self):
        """Test basic debt mode calculation"""
        result = calculate_finances(
            income_self=10_000_000,
            income_partner=0,
            rent=2_000_000,
            kindergarten=500_000,
            utilities=500_000,
            loan_payment=1_500_000,
            total_debt=50_000_000
        )
        
        assert result["mode"] == "debt"
        assert result["total_income"] == 10_000_000
        assert result["mandatory_living"] == 3_000_000
        assert result["mandatory_debt"] == 1_500_000
        
        # FreeCash = 10M - 1.5M - 3M = 5.5M
        assert result["free_cash"] == 5_500_000
        
        # Savings = 5.5M × 10% = 550,000
        assert result["monthly_savings"] == 550_000
        
        # Accelerated = 5.5M × 20% = 1.1M
        # Total debt payment = 1.5M + 1.1M = 2.6M
        assert result["monthly_debt_payment"] == 2_600_000
        
        # Exit months = 50M / 2.6M ≈ 20
        assert result["exit_months"] == 20
    
    def test_family_mode_debt(self):
        """Test family mode with combined income"""
        result = calculate_finances(
            income_self=10_000_000,
            income_partner=8_000_000,
            rent=3_000_000,
            kindergarten=1_000_000,
            utilities=500_000,
            loan_payment=2_000_000,
            total_debt=100_000_000
        )
        
        assert result["mode"] == "debt"
        assert result["total_income"] == 18_000_000
        
        # FreeCash = 18M - 2M - 4.5M = 11.5M
        assert result["free_cash"] == 11_500_000


class TestWealthMode:
    """Tests for wealth mode calculations"""
    
    def test_basic_wealth_calculation(self):
        """Test wealth mode with no debt"""
        result = calculate_finances(
            income_self=10_000_000,
            income_partner=0,
            rent=2_000_000,
            kindergarten=500_000,
            utilities=500_000,
            loan_payment=0,
            total_debt=0
        )
        
        assert result["mode"] == "wealth"
        assert result["total_income"] == 10_000_000
        
        # FreeCash = 10M - 3M = 7M
        assert result["free_cash"] == 7_000_000
        
        # Invest = 7M × 30% = 2.1M
        assert result["monthly_invest"] == 2_100_000
        
        # Savings = 7M × 20% = 1.4M
        assert result["monthly_savings"] == 1_400_000
        
        # Living = 7M × 50% = 3.5M
        assert result["monthly_living"] == 3_500_000
    
    def test_wealth_12_month_projection(self):
        """Test 12-month projections in wealth mode"""
        result = calculate_finances(
            income_self=10_000_000,
            rent=1_000_000,
            utilities=500_000,
            loan_payment=0,
            total_debt=0
        )
        
        # FreeCash = 10M - 1.5M = 8.5M
        # Monthly savings = 8.5M × 20% = 1.7M
        # 12-month savings = 1.7M × 12 = 20.4M
        assert result["savings_12_months"] == 1_700_000 * 12


class TestNegativeCash:
    """Tests for negative cash flow scenarios"""
    
    def test_expenses_exceed_income(self):
        """Test when expenses exceed income"""
        result = calculate_finances(
            income_self=5_000_000,
            rent=3_000_000,
            utilities=1_000_000,
            loan_payment=2_000_000,
            total_debt=50_000_000
        )
        
        assert result["mode"] == "negative"
        assert result["total_income"] == 5_000_000
        assert result["difference"] < 0


class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_zero_income(self):
        """Test with zero income"""
        result = calculate_finances(
            income_self=0,
            rent=1_000_000,
            loan_payment=500_000,
            total_debt=10_000_000
        )
        
        assert result["mode"] == "negative"
    
    def test_minimal_debt(self):
        """Test with very small debt"""
        result = calculate_finances(
            income_self=10_000_000,
            rent=1_000_000,
            loan_payment=100_000,
            total_debt=100_000
        )
        
        assert result["mode"] == "debt"
        assert result["exit_months"] <= 1
    
    def test_large_numbers(self):
        """Test with large numbers (billion range)"""
        result = calculate_finances(
            income_self=100_000_000,
            income_partner=100_000_000,
            rent=10_000_000,
            loan_payment=20_000_000,
            total_debt=1_000_000_000
        )
        
        assert result["mode"] == "debt"
        assert result["exit_months"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
