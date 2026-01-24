"""
SOLVO Financial Engine
Core calculation logic for debt freedom and wealth building
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.config import (
    DEBT_MODE_SAVINGS_RATE,
    DEBT_MODE_ACCELERATED_RATE,
    DEBT_MODE_LIVING_RATE,
    WEALTH_MODE_INVEST_RATE,
    WEALTH_MODE_SAVINGS_RATE,
    WEALTH_MODE_LIVING_RATE,
)
from app.languages import get_month_name, format_number


@dataclass
class FinancialInput:
    """Input data for financial calculations"""
    mode: str = "solo"
    income_self: float = 0
    income_partner: float = 0
    rent: float = 0
    kindergarten: float = 0
    utilities: float = 0
    loan_payment: float = 0
    total_debt: float = 0


@dataclass
class DebtModeResult:
    """Result for debt mode calculation"""
    mode: str = "debt"
    total_income: float = 0
    mandatory_living: float = 0
    mandatory_debt: float = 0
    free_cash: float = 0
    monthly_savings: float = 0
    monthly_debt_payment: float = 0
    accelerated_debt: float = 0
    monthly_living: float = 0
    exit_months: int = 0
    exit_date: str = ""
    savings_12_months: float = 0
    savings_at_exit: float = 0


@dataclass
class WealthModeResult:
    """Result for wealth mode calculation"""
    mode: str = "wealth"
    total_income: float = 0
    mandatory_living: float = 0
    free_cash: float = 0
    monthly_invest: float = 0
    monthly_savings: float = 0
    monthly_living: float = 0
    invest_12_months: float = 0
    savings_12_months: float = 0
    total_12_months: float = 0


@dataclass
class NegativeCashResult:
    """Result when expenses exceed income"""
    mode: str = "negative"
    total_income: float = 0
    total_expenses: float = 0
    difference: float = 0


class FinancialEngine:
    """
    SOLVO Financial Calculation Engine
    
    Handles all financial calculations for:
    - Debt mode: Users with loans
    - Wealth mode: Users without loans
    """
    
    def __init__(self, input_data: FinancialInput):
        self.input = input_data
        
        # Calculate totals
        self.total_income = input_data.income_self + input_data.income_partner
        self.mandatory_living = (
            input_data.rent + 
            input_data.kindergarten + 
            input_data.utilities
        )
        self.mandatory_debt = input_data.loan_payment
        
        # Calculate free cash
        self.free_cash = (
            self.total_income - 
            self.mandatory_debt - 
            self.mandatory_living
        )
    
    def calculate(self) -> Dict[str, Any]:
        """
        Main calculation method
        Returns appropriate result based on financial situation
        """
        # Check if expenses exceed income
        if self.free_cash < 0:
            return self._calculate_negative_cash()
        
        # Check if user has debt
        if self.mandatory_debt > 0 and self.input.total_debt > 0:
            return self._calculate_debt_mode()
        else:
            return self._calculate_wealth_mode()
    
    def _calculate_debt_mode(self) -> Dict[str, Any]:
        """
        Calculate debt freedom plan
        
        FREE: Simple debt payoff (just monthly payments)
        PRO: Accelerated payoff with 70-20-10 method + savings
        """
        # === FREE VERSION: Simple debt payoff calculation ===
        # Just paying monthly payment without acceleration
        if self.mandatory_debt > 0:
            simple_exit_months = int(self.input.total_debt / self.mandatory_debt) + 1
        else:
            simple_exit_months = 0
        simple_exit_date = datetime.now() + relativedelta(months=simple_exit_months)
        
        # === PRO VERSION: Accelerated 70-20-10 method ===
        # Monthly allocations from free cash
        monthly_savings = self.free_cash * DEBT_MODE_SAVINGS_RATE  # 10%
        accelerated_debt = self.free_cash * DEBT_MODE_ACCELERATED_RATE  # 20%
        monthly_living = self.free_cash * DEBT_MODE_LIVING_RATE  # 70%
        
        # Total monthly debt payment (mandatory + accelerated)
        total_debt_payment = self.mandatory_debt + accelerated_debt
        
        # Calculate PRO exit timeline (faster!)
        if total_debt_payment > 0:
            pro_exit_months = int(self.input.total_debt / total_debt_payment) + 1
        else:
            pro_exit_months = 0
        
        # Calculate PRO exit date
        pro_exit_date = datetime.now() + relativedelta(months=pro_exit_months)
        
        # Calculate savings projections
        savings_12_months = monthly_savings * 12
        savings_at_exit = monthly_savings * pro_exit_months
        
        # Calculate months saved with PRO method
        months_saved = simple_exit_months - pro_exit_months
        
        return {
            "mode": "debt",
            "total_income": self.total_income,
            "mandatory_living": self.mandatory_living,
            "mandatory_debt": self.mandatory_debt,
            "free_cash": self.free_cash,
            "monthly_savings": monthly_savings,
            "monthly_debt_payment": total_debt_payment,
            "accelerated_debt": accelerated_debt,
            "monthly_living": monthly_living,
            "monthly_invest": 0,
            # Simple (FREE) calculations
            "simple_exit_months": simple_exit_months,
            "simple_exit_date": simple_exit_date.strftime("%Y-%m"),
            "simple_exit_date_obj": simple_exit_date,
            # PRO calculations
            "exit_months": pro_exit_months,
            "exit_date": pro_exit_date.strftime("%Y-%m"),
            "exit_date_obj": pro_exit_date,
            "months_saved": months_saved,
            "savings_12_months": savings_12_months,
            "savings_at_exit": savings_at_exit,
        }
    
    def _calculate_wealth_mode(self) -> Dict[str, Any]:
        """
        Calculate wealth building plan
        
        Formula:
        - Invest = FreeCash × 30%
        - Savings = FreeCash × 20%
        - Living = FreeCash × 50%
        """
        # Monthly allocations
        monthly_invest = self.free_cash * WEALTH_MODE_INVEST_RATE
        monthly_savings = self.free_cash * WEALTH_MODE_SAVINGS_RATE
        monthly_living = self.free_cash * WEALTH_MODE_LIVING_RATE
        
        # 12-month projections
        invest_12_months = monthly_invest * 12
        savings_12_months = monthly_savings * 12
        total_12_months = invest_12_months + savings_12_months
        
        return {
            "mode": "wealth",
            "total_income": self.total_income,
            "mandatory_living": self.mandatory_living,
            "mandatory_debt": 0,
            "free_cash": self.free_cash,
            "monthly_invest": monthly_invest,
            "monthly_savings": monthly_savings,
            "monthly_living": monthly_living,
            "monthly_debt_payment": 0,
            "exit_months": 0,
            "exit_date": None,
            "invest_12_months": invest_12_months,
            "savings_12_months": savings_12_months,
            "total_12_months": total_12_months,
            "savings_at_exit": 0,
        }
    
    def _calculate_negative_cash(self) -> Dict[str, Any]:
        """Handle case where expenses exceed income"""
        total_expenses = self.mandatory_living + self.mandatory_debt
        
        return {
            "mode": "negative",
            "total_income": self.total_income,
            "total_expenses": total_expenses,
            "difference": self.free_cash,  # Will be negative
        }


def format_exit_date(date_str: str, lang: str = "uz") -> str:
    """Format exit date for display"""
    if not date_str:
        return ""
    
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m")
        month_name = get_month_name(date_obj.month, lang)
        year = date_obj.year
        
        if lang == "uz":
            return f"{year}-yil {month_name}"
        else:
            return f"{month_name} {year} года"
    except:
        return date_str


def format_result_message(result: Dict[str, Any], lang: str = "uz", is_pro: bool = True) -> str:
    """Format calculation result as user-friendly message
    
    Args:
        result: Calculation results dictionary
        lang: Language code
        is_pro: Whether user has PRO subscription (shows full or partial results)
    """
    from app.languages import get_message
    
    mode = result.get("mode")
    
    if mode == "negative":
        return get_message("result_negative_cash", lang).format(
            income=format_number(result["total_income"]),
            expenses=format_number(result["total_expenses"]),
            difference=format_number(abs(result["difference"]))
        )
    
    elif mode == "debt":
        # Simple exit date (normal payment schedule) - shown to everyone
        simple_exit_formatted = format_exit_date(result.get("simple_exit_date", result["exit_date"]), lang)
        simple_exit_months = result.get("simple_exit_months", result["exit_months"])
        
        # PRO exit date (accelerated) - only for PRO users
        pro_exit_formatted = format_exit_date(result["exit_date"], lang)
        pro_exit_months = result["exit_months"]
        months_saved = result.get("months_saved", 0)
        
        if is_pro:
            # Full results for PRO users
            return get_message("result_debt_mode", lang).format(
                exit_date=pro_exit_formatted,
                exit_months=pro_exit_months,
                debt_payment=format_number(result["monthly_debt_payment"]),
                savings=format_number(result["monthly_savings"]),
                living=format_number(result["monthly_living"]),
                savings_12=format_number(result["savings_12_months"]),
                savings_exit=format_number(result["savings_at_exit"])
            )
        else:
            # FREE users - show simple exit date + PRO teaser
            return get_message("result_debt_mode_free", lang).format(
                simple_exit_date=simple_exit_formatted,
                simple_exit_months=simple_exit_months,
                monthly_payment=format_number(result["mandatory_debt"]),
                total_debt=format_number(result.get("mandatory_debt", 0) * simple_exit_months),
                pro_exit_date=pro_exit_formatted,
                pro_exit_months=pro_exit_months,
                months_saved=months_saved,
                savings_at_exit=format_number(result["savings_at_exit"])
            )
    
    elif mode == "wealth":
        if is_pro:
            # Full results for PRO users
            return get_message("result_wealth_mode", lang).format(
                invest=format_number(result["monthly_invest"]),
                savings=format_number(result["monthly_savings"]),
                living=format_number(result["monthly_living"]),
                savings_12=format_number(result["savings_12_months"]),
                invest_12=format_number(result["invest_12_months"]),
                total_12=format_number(result["total_12_months"])
            )
        else:
            # Partial results for FREE users
            return get_message("result_wealth_mode_partial", lang).format(
                invest=format_number(result["monthly_invest"]),
                savings=format_number(result["monthly_savings"]),
                living=format_number(result["monthly_living"])
            ) + get_message("partial_results_notice", lang)
    
    return get_message("error_generic", lang)


def calculate_finances(input_data: FinancialInput) -> Dict[str, Any]:
    """
    Convenience function for financial calculation
    
    Args:
        input_data: FinancialInput object with all financial data
    
    Returns:
        Dictionary with calculation results
    """
    engine = FinancialEngine(input_data)
    return engine.calculate()
