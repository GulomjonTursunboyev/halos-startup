"""
SOLVO KATM PDF Parser
Parses credit history PDFs from infokredit.uz
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class ParsedLoan:
    """Represents a single parsed loan"""
    bank_name: str
    contract_number: str = ""
    loan_type: str = ""
    original_amount: float = 0
    remaining_balance: float = 0
    monthly_payment: float = 0
    currency: str = "UZS"
    status: str = "active"
    start_date: str = ""
    end_date: str = ""


@dataclass
class KATMParseResult:
    """Result of KATM PDF parsing"""
    success: bool
    loans: List[ParsedLoan]
    total_remaining_debt: float = 0
    total_monthly_payment: float = 0
    error_message: str = ""
    raw_text: str = ""


class KATMPDFParser:
    """
    Parser for KATM (infokredit.uz) credit history PDFs
    
    KATM PDFs typically contain:
    - Personal information
    - List of current and past loans
    - Loan details: bank, amount, balance, payments
    """
    
    # Common patterns in KATM PDFs (both UZ and RU versions)
    PATTERNS = {
        # Bank names commonly found in Uzbekistan
        "banks": [
            "XALQ BANKI", "AGROBANK", "ASAKA BANK", "IPOTEKA BANK", 
            "HAMKORBANK", "KAPITALBANK", "UZPROMSTROYBANK", "ALOQABANK",
            "TURONBANK", "SAVDOGARBANK", "QISHLOQ QURILISH BANK",
            "INFINBANK", "TURKISTON BANK", "ORIENT FINANS BANK",
            "RAVNAQ BANK", "TRUSTBANK", "POYTAXT BANK", "MADAD INVEST BANK",
            "ZIRAAT BANK", "KDB BANK", "TBC BANK", "ANOR BANK",
            "IPAK YO'LI BANK", "UNIVERSAL BANK", "DAVR BANK",
            # Russian variations
            "НАРОДНЫЙ БАНК", "АГРОБАНК", "ИПОТЕКА БАНК",
            "КАПИТАЛБАНК", "ХАМКОРБАНК"
        ],
        
        # Amount patterns (Uzbek sum)
        "amount": r'([\d\s,\.]+)\s*(so\'?m|сум|UZS|sum)',
        
        # Balance/debt patterns
        "balance_uz": r'(qoldiq|qarz|balans)[:\s]*([\d\s,\.]+)',
        "balance_ru": r'(остаток|долг|баланс)[:\s]*([\d\s,\.]+)',
        
        # Monthly payment patterns
        "monthly_uz": r'(oylik|oyiga|har oy)[:\s]*([\d\s,\.]+)',
        "monthly_ru": r'(ежемесячн|платеж|в месяц)[:\s]*([\d\s,\.]+)',
        
        # Contract/loan number
        "contract": r'(shartnoma|договор|kontrakt|contract)[:\s#№]*(\d+[\d\-/]*)',
        
        # Dates
        "date": r'(\d{2}[\./-]\d{2}[\./-]\d{4})',
        
        # Active loan indicators
        "active_uz": r'(faol|joriy|ochiq|to\'lanmagan)',
        "active_ru": r'(активн|текущ|открыт|непогашен)',
        
        # Closed loan indicators  
        "closed_uz": r'(yopilgan|tugallangan|to\'langan)',
        "closed_ru": r'(закрыт|погашен|завершен)',
    }
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.text = ""
        self.tables = []
    
    def parse(self) -> KATMParseResult:
        """
        Parse the KATM PDF and extract loan information
        """
        try:
            # Extract text and tables from PDF
            self._extract_content()
            
            if not self.text:
                return KATMParseResult(
                    success=False,
                    loans=[],
                    error_message="PDF bo'sh yoki o'qib bo'lmadi / PDF пустой или не читается"
                )
            
            # Try table-based parsing first (more accurate)
            loans = self._parse_tables()
            
            # If no loans from tables, try text-based parsing
            if not loans:
                loans = self._parse_text()
            
            # Filter to active loans only
            active_loans = [l for l in loans if l.status == "active"]
            
            # Calculate totals
            total_debt = sum(l.remaining_balance for l in active_loans)
            total_monthly = sum(l.monthly_payment for l in active_loans)
            
            # If we found loans but no monthly payment, estimate it
            if active_loans and total_monthly == 0 and total_debt > 0:
                # Estimate: assume average 24-month loan term
                total_monthly = total_debt / 24
            
            return KATMParseResult(
                success=len(active_loans) > 0,
                loans=active_loans,
                total_remaining_debt=total_debt,
                total_monthly_payment=total_monthly,
                raw_text=self.text[:2000]  # Store first 2000 chars for debugging
            )
            
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            return KATMParseResult(
                success=False,
                loans=[],
                error_message=f"Xatolik / Ошибка: {str(e)}"
            )
    
    def _extract_content(self):
        """Extract text and tables from PDF"""
        with pdfplumber.open(self.pdf_path) as pdf:
            text_parts = []
            
            for page in pdf.pages:
                # Extract text
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                
                # Extract tables
                page_tables = page.extract_tables() or []
                self.tables.extend(page_tables)
            
            self.text = "\n".join(text_parts)
    
    def _parse_tables(self) -> List[ParsedLoan]:
        """Parse loans from extracted tables"""
        loans = []
        
        for table in self.tables:
            if not table or len(table) < 2:
                continue
            
            # Try to identify loan table by headers
            headers = [str(cell).lower() if cell else "" for cell in table[0]]
            
            # Check if this looks like a loan table
            is_loan_table = any(
                keyword in " ".join(headers)
                for keyword in ["kredit", "кредит", "qarz", "долг", "bank", "банк", "summa", "сумма"]
            )
            
            if not is_loan_table:
                continue
            
            # Find column indices
            bank_col = self._find_column(headers, ["bank", "банк", "kreditor", "кредитор"])
            amount_col = self._find_column(headers, ["summa", "сумма", "miqdor", "amount"])
            balance_col = self._find_column(headers, ["qoldiq", "остаток", "balance", "qarz"])
            payment_col = self._find_column(headers, ["oylik", "ежемес", "payment", "to'lov"])
            status_col = self._find_column(headers, ["holat", "статус", "status"])
            
            # Parse rows
            for row in table[1:]:
                if not row or len(row) < 2:
                    continue
                
                loan = ParsedLoan(bank_name="")
                
                # Extract bank name
                if bank_col is not None and bank_col < len(row):
                    loan.bank_name = str(row[bank_col] or "").strip()
                
                # Extract amounts
                if balance_col is not None and balance_col < len(row):
                    loan.remaining_balance = self._parse_amount(row[balance_col])
                elif amount_col is not None and amount_col < len(row):
                    loan.remaining_balance = self._parse_amount(row[amount_col])
                
                if payment_col is not None and payment_col < len(row):
                    loan.monthly_payment = self._parse_amount(row[payment_col])
                
                # Determine status
                if status_col is not None and status_col < len(row):
                    status_text = str(row[status_col] or "").lower()
                    if any(re.search(p, status_text) for p in [self.PATTERNS["closed_uz"], self.PATTERNS["closed_ru"]]):
                        loan.status = "closed"
                    else:
                        loan.status = "active"
                
                # Only add if we got meaningful data
                if loan.bank_name and loan.remaining_balance > 0:
                    loans.append(loan)
        
        return loans
    
    def _parse_text(self) -> List[ParsedLoan]:
        """Parse loans from raw text (fallback method)"""
        loans = []
        text_lower = self.text.lower()
        
        # Find bank mentions and associated amounts
        for bank in self.PATTERNS["banks"]:
            bank_lower = bank.lower()
            
            if bank_lower in text_lower:
                # Find the position of bank mention
                pos = text_lower.find(bank_lower)
                
                # Get surrounding context (500 chars after bank name)
                context = self.text[pos:pos + 500]
                
                loan = ParsedLoan(bank_name=bank)
                
                # Try to find remaining balance
                for pattern in [self.PATTERNS["balance_uz"], self.PATTERNS["balance_ru"]]:
                    match = re.search(pattern, context, re.IGNORECASE)
                    if match:
                        loan.remaining_balance = self._parse_amount(match.group(2))
                        break
                
                # Try to find monthly payment
                for pattern in [self.PATTERNS["monthly_uz"], self.PATTERNS["monthly_ru"]]:
                    match = re.search(pattern, context, re.IGNORECASE)
                    if match:
                        loan.monthly_payment = self._parse_amount(match.group(2))
                        break
                
                # Check if loan is active
                context_lower = context.lower()
                if any(re.search(p, context_lower) for p in [self.PATTERNS["closed_uz"], self.PATTERNS["closed_ru"]]):
                    loan.status = "closed"
                else:
                    loan.status = "active"
                
                if loan.remaining_balance > 0:
                    loans.append(loan)
        
        # If no bank-specific loans found, try to find general amounts
        if not loans:
            loan = ParsedLoan(bank_name="KATM")
            
            # Find all amounts in document
            amounts = []
            amount_matches = re.findall(self.PATTERNS["amount"], self.text, re.IGNORECASE)
            for match in amount_matches:
                amount = self._parse_amount(match[0])
                if amount > 100000:  # Filter small amounts
                    amounts.append(amount)
            
            if amounts:
                # Assume largest amount is total debt
                loan.remaining_balance = max(amounts)
                loan.status = "active"
                loans.append(loan)
        
        return loans
    
    def _find_column(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by keywords"""
        for i, header in enumerate(headers):
            if any(kw in header for kw in keywords):
                return i
        return None
    
    def _parse_amount(self, value) -> float:
        """Parse amount from various formats"""
        if not value:
            return 0
        
        text = str(value)
        
        # Remove non-numeric characters except dots and commas
        cleaned = re.sub(r'[^\d,\.]', '', text)
        
        # Handle thousands separators
        # If there's a comma followed by 3 digits at the end, it's decimal
        # Otherwise commas are thousands separators
        if re.search(r',\d{3}$', cleaned):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '').replace(' ', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return 0


def parse_katm_pdf(pdf_path: str) -> KATMParseResult:
    """
    Convenience function to parse KATM PDF
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        KATMParseResult with parsed loan data
    """
    parser = KATMPDFParser(pdf_path)
    return parser.parse()
