"""
HALOS KATM PDF Parser
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
    loan_type: str = ""  # "annuity" (bir xil) or "differentiated" (kamayib boruvchi)
    original_amount: float = 0
    remaining_balance: float = 0
    monthly_payment: float = 0
    interest_rate: float = 0  # Yillik foiz stavkasi (%)
    interest_amount: float = 0  # Oylik foiz summasi
    principal_amount: float = 0  # Oylik asosiy qarz summasi
    total_interest_paid: float = 0  # Jami to'langan foiz
    total_interest_remaining: float = 0  # Qolgan foiz summasi
    months_remaining: int = 0  # Qolgan oylar
    currency: str = "UZS"
    status: str = "active"
    start_date: str = ""
    end_date: str = ""
    payment_schedule: List[Dict] = None  # Har oylik to'lov jadvali
    
    def __post_init__(self):
        if self.payment_schedule is None:
            self.payment_schedule = []


@dataclass
class KATMParseResult:
    """Result of KATM PDF parsing"""
    success: bool
    loans: List[ParsedLoan]
    total_remaining_debt: float = 0
    total_monthly_payment: float = 0
    total_interest_monthly: float = 0  # Jami oylik foiz
    total_principal_monthly: float = 0  # Jami oylik asosiy qarz
    average_interest_rate: float = 0  # O'rtacha foiz stavkasi
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


def _extract_amount(text: str) -> float:
    """Extract numeric amount from text"""
    if not text:
        return 0
    
    # Remove non-numeric characters except dots, commas, and spaces
    cleaned = re.sub(r'[^\d,\.\s]', '', str(text))
    cleaned = cleaned.strip()
    
    if not cleaned:
        return 0
    
    # Handle different number formats
    # Remove spaces (thousand separators)
    cleaned = cleaned.replace(' ', '')
    
    # Handle comma as thousand separator or decimal
    if ',' in cleaned and '.' in cleaned:
        # Both present - comma is thousand sep, dot is decimal
        cleaned = cleaned.replace(',', '')
    elif cleaned.count(',') > 1:
        # Multiple commas - they are thousand separators
        cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Single comma - check if it's decimal (2 digits after) or thousand sep
        parts = cleaned.split(',')
        if len(parts[-1]) == 2:
            # Likely decimal
            cleaned = cleaned.replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    
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


def parse_katm_html(html_path: str) -> KATMParseResult:
    """
    Parse KATM credit history from HTML file (infokredit.uz format)
    
    Structure of infokredit.uz HTML:
    - Section "AMALDAGI SHARTNOMALAR" (Active contracts)
    - Table columns: №, QARZ BERUVCHI, SHARTNOMA RAQAMI, VALYUTA, 
                     UMUMIY QARZ QOLDIG'I, MUDDATI O'TGAN QISMI, O'RTACHA OYLIK TO'LOV
    - Last row "Jami" contains totals
    
    Args:
        html_path: Path to the HTML file
        
    Returns:
        KATMParseResult with parsed loan data
    """
    try:
        from bs4 import BeautifulSoup
        
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        loans = []
        total_debt = 0
        total_monthly = 0
        
        # Find "AMALDAGI SHARTNOMALAR" section (Active contracts)
        # This section contains current active loans
        active_section = None
        
        # Look for text containing "AMALDAGI" or "AMALDAGI SHARTNOMALAR"
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'td', 'th', 'strong', 'b']):
            text = element.get_text(strip=True).upper()
            if 'AMALDAGI SHARTNOMALAR' in text or 'AMALDAGI' in text:
                active_section = element
                break
        
        # Find the table after "AMALDAGI SHARTNOMALAR"
        target_table = None
        if active_section:
            # Look for next table after this element
            next_elem = active_section.find_next('table')
            if next_elem:
                target_table = next_elem
        
        # If no active section found, try to find table with correct headers
        if not target_table:
            for table in soup.find_all('table'):
                table_text = table.get_text().upper()
                if ('QARZ BERUVCHI' in table_text or 'КРЕДИТОР' in table_text) and \
                   ('OYLIK TO\'LOV' in table_text or 'ЕЖЕМЕС' in table_text or 'O\'RTACHA' in table_text):
                    target_table = table
                    break
        
        if target_table:
            rows = target_table.find_all('tr')
            
            # Find column indices from headers
            headers = []
            header_row = None
            
            for row in rows:
                cells = row.find_all(['th', 'td'])
                row_text = ' '.join(cell.get_text(strip=True) for cell in cells).upper()
                
                if 'QARZ BERUVCHI' in row_text or 'SHARTNOMA' in row_text or '№' in row_text:
                    header_row = row
                    headers = [cell.get_text(strip=True).upper() for cell in cells]
                    break
            
            # Identify column indices
            bank_col = None  # QARZ BERUVCHI
            balance_col = None  # UMUMIY QARZ QOLDIG'I
            monthly_col = None  # O'RTACHA OYLIK TO'LOV
            
            for i, header in enumerate(headers):
                if 'QARZ BERUVCHI' in header or 'КРЕДИТОР' in header:
                    bank_col = i
                elif 'QARZ QOLDIG' in header or 'UMUMIY QARZ' in header or 'ОСТАТОК' in header:
                    balance_col = i
                elif 'OYLIK TO\'LOV' in header or 'O\'RTACHA OYLIK' in header or 'ЕЖЕМЕС' in header:
                    monthly_col = i
            
            logger.info(f"Found columns: bank={bank_col}, balance={balance_col}, monthly={monthly_col}")
            
            # Parse data rows
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                row_text = ' '.join(cell.get_text(strip=True) for cell in cells).upper()
                
                # Skip header row
                if 'QARZ BERUVCHI' in row_text and 'SHARTNOMA' in row_text:
                    continue
                
                # Check for "Jami" (total) row
                if 'JAMI' in row_text or 'ИТОГО' in row_text or 'TOTAL' in row_text:
                    # Extract totals from Jami row
                    if balance_col is not None and balance_col < len(cells):
                        jami_debt = _extract_amount(cells[balance_col].get_text(strip=True))
                        if jami_debt > 0:
                            total_debt = jami_debt
                    
                    if monthly_col is not None and monthly_col < len(cells):
                        jami_monthly = _extract_amount(cells[monthly_col].get_text(strip=True))
                        if jami_monthly > 0:
                            total_monthly = jami_monthly
                    continue
                
                # Extract bank name
                bank_name = ""
                if bank_col is not None and bank_col < len(cells):
                    bank_text = cells[bank_col].get_text(strip=True)
                    # Extract bank name (usually contains "BANK" or ends with bank identifier)
                    bank_name = bank_text
                    # Clean up bank name - get the main part
                    if '(' in bank_name:
                        bank_name = bank_name.split('(')[0].strip()
                
                if not bank_name:
                    continue
                
                # Extract balance (UMUMIY QARZ QOLDIG'I)
                balance = 0
                if balance_col is not None and balance_col < len(cells):
                    balance = _extract_amount(cells[balance_col].get_text(strip=True))
                
                # Extract monthly payment (O'RTACHA OYLIK TO'LOV)
                monthly = 0
                if monthly_col is not None and monthly_col < len(cells):
                    monthly = _extract_amount(cells[monthly_col].get_text(strip=True))
                
                if balance > 0:
                    loan = ParsedLoan(
                        bank_name=bank_name,
                        remaining_balance=balance,
                        monthly_payment=monthly,
                        status="active"
                    )
                    loans.append(loan)
                    
                    # If Jami row wasn't found, sum up manually
                    if total_debt == 0:
                        total_debt += balance
                    if total_monthly == 0:
                        total_monthly += monthly
        
        # Fallback: try to find any table with numeric data
        if not loans:
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join(cell.get_text(strip=True) for cell in cells).upper()
                    
                    # Look for "JAMI" row with totals
                    if 'JAMI' in row_text:
                        amounts = []
                        for cell in cells:
                            amount = _extract_amount(cell.get_text(strip=True))
                            if amount >= 10000:
                                amounts.append(amount)
                        
                        if len(amounts) >= 2:
                            # Usually: larger is total debt, smaller is monthly
                            amounts.sort(reverse=True)
                            total_debt = amounts[0]
                            total_monthly = amounts[-1]  # Last one is usually monthly
                            
                            # Create a single loan entry
                            loans.append(ParsedLoan(
                                bank_name="KATM",
                                remaining_balance=total_debt,
                                monthly_payment=total_monthly,
                                status="active"
                            ))
                            break
        
        if loans or (total_debt > 0 and total_monthly > 0):
            # If we have totals but no individual loans, create summary loan
            if not loans and total_debt > 0:
                loans.append(ParsedLoan(
                    bank_name="Jami kreditlar",
                    remaining_balance=total_debt,
                    monthly_payment=total_monthly,
                    status="active"
                ))
            
            return KATMParseResult(
                success=True,
                loans=loans,
                total_remaining_debt=total_debt if total_debt > 0 else sum(l.remaining_balance for l in loans),
                total_monthly_payment=total_monthly if total_monthly > 0 else sum(l.monthly_payment for l in loans),
                raw_text=soup.get_text()[:1000]
            )
        else:
            return KATMParseResult(
                success=False,
                loans=[],
                error_message="No loan data found in HTML file"
            )
            
    except Exception as e:
        logger.error(f"Error parsing KATM HTML: {e}")
        return KATMParseResult(
            success=False,
            loans=[],
            error_message=str(e)
        )


def parse_katm_file(file_path: str) -> KATMParseResult:
    """
    Parse KATM file - automatically detect format (PDF or HTML)
    
    Args:
        file_path: Path to the file (PDF or HTML)
        
    Returns:
        KATMParseResult with parsed loan data
    """
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext == '.pdf':
        return parse_katm_pdf(file_path)
    elif file_ext in ['.html', '.htm']:
        return parse_katm_html(file_path)
    else:
        return KATMParseResult(
            success=False,
            loans=[],
            error_message=f"Unsupported file format: {file_ext}"
        )


def analyze_credit_details(
    total_debt: float,
    monthly_payment: float,
    interest_rate: float = None,
    loan_type: str = "annuity"
) -> Dict[str, Any]:
    """
    Kredit ma'lumotlarini chuqur tahlil qilish
    
    Args:
        total_debt: Jami qolgan qarz
        monthly_payment: Oylik to'lov
        interest_rate: Yillik foiz stavkasi (agar ma'lum bo'lsa)
        loan_type: "annuity" yoki "differentiated"
    
    Returns:
        Dict with detailed credit analysis
    """
    if monthly_payment <= 0 or total_debt <= 0:
        return {
            "months_remaining": 0,
            "interest_rate_estimated": 0,
            "monthly_interest": 0,
            "monthly_principal": monthly_payment,
            "total_interest_remaining": 0,
            "total_to_pay": total_debt,
            "interest_percentage": 0,
            "loan_type": loan_type
        }
    
    # Qolgan oylarni hisoblash
    months_remaining = int(total_debt / monthly_payment) if monthly_payment > 0 else 0
    
    # Agar foiz stavkasi berilmagan bo'lsa, taxmin qilish
    if interest_rate is None or interest_rate == 0:
        # Standart O'zbekiston bank kredit stavkalari: 18-36% yillik
        # Taxminiy hisoblash: umumiy to'lov va qarzni taqqoslash
        if months_remaining > 0:
            total_to_pay = monthly_payment * months_remaining
            total_interest = total_to_pay - total_debt
            if total_interest > 0:
                # Oddiy foiz formulasi orqali taxmin
                interest_rate = (total_interest / total_debt) * (12 / months_remaining) * 100
                interest_rate = min(max(interest_rate, 15), 50)  # 15-50% oralig'ida
            else:
                interest_rate = 24  # O'rtacha standart
        else:
            interest_rate = 24
    
    # Oylik foiz stavkasi
    monthly_rate = interest_rate / 100 / 12
    
    # Annuitet kredit uchun foiz va asosiy qarz taqsimoti
    if loan_type == "annuity":
        # Birinchi oylik foiz
        monthly_interest = total_debt * monthly_rate
        monthly_principal = monthly_payment - monthly_interest
        
        # Jami qolgan foiz (taxminiy)
        total_interest_remaining = 0
        remaining = total_debt
        for _ in range(months_remaining):
            interest_this_month = remaining * monthly_rate
            total_interest_remaining += interest_this_month
            principal_this_month = monthly_payment - interest_this_month
            remaining -= principal_this_month
            if remaining <= 0:
                break
    else:
        # Differensiallangan kredit
        monthly_principal = total_debt / months_remaining if months_remaining > 0 else 0
        monthly_interest = total_debt * monthly_rate
        
        # Jami qolgan foiz
        total_interest_remaining = 0
        remaining = total_debt
        for i in range(months_remaining):
            interest_this_month = remaining * monthly_rate
            total_interest_remaining += interest_this_month
            remaining -= monthly_principal
            if remaining <= 0:
                break
    
    # Jami to'lanadigan summa
    total_to_pay = total_debt + total_interest_remaining
    
    # Foiz ulushi (to'lovdagi foiz %)
    interest_percentage = (monthly_interest / monthly_payment * 100) if monthly_payment > 0 else 0
    
    return {
        "months_remaining": months_remaining,
        "interest_rate_estimated": round(interest_rate, 1),
        "monthly_interest": round(monthly_interest),
        "monthly_principal": round(monthly_principal),
        "total_interest_remaining": round(total_interest_remaining),
        "total_to_pay": round(total_to_pay),
        "interest_percentage": round(interest_percentage, 1),
        "loan_type": loan_type,
        "loan_type_name": "Annuitet (bir xil)" if loan_type == "annuity" else "Differensial (kamayib boruvchi)"
    }


def calculate_interest_impact(
    monthly_interest: float,
    monthly_income: float
) -> Dict[str, Any]:
    """
    Foizlarning daromadga ta'sirini hisoblash
    
    Args:
        monthly_interest: Oylik foiz summasi
        monthly_income: Oylik daromad
    
    Returns:
        Dict with interest impact analysis
    """
    if monthly_income <= 0:
        return {
            "interest_to_income_ratio": 0,
            "yearly_interest_loss": 0,
            "impact_level": "unknown",
            "recommendation": ""
        }
    
    # Foiz/daromad nisbati
    ratio = (monthly_interest / monthly_income) * 100
    
    # Yillik foiz yo'qotish
    yearly_loss = monthly_interest * 12
    
    # Ta'sir darajasi
    if ratio < 5:
        impact_level = "low"
        impact_emoji = "🟢"
    elif ratio < 10:
        impact_level = "moderate"
        impact_emoji = "🟡"
    elif ratio < 20:
        impact_level = "high"
        impact_emoji = "🟠"
    else:
        impact_level = "critical"
        impact_emoji = "🔴"
    
    return {
        "interest_to_income_ratio": round(ratio, 1),
        "yearly_interest_loss": round(yearly_loss),
        "impact_level": impact_level,
        "impact_emoji": impact_emoji
    }


def generate_payment_schedule(
    total_debt: float,
    monthly_payment: float,
    interest_rate: float,
    loan_type: str = "annuity",
    months: int = 12
) -> List[Dict[str, Any]]:
    """
    To'lov jadvalini generatsiya qilish
    
    Args:
        total_debt: Jami qarz
        monthly_payment: Oylik to'lov
        interest_rate: Yillik foiz
        loan_type: Kredit turi
        months: Necha oylik jadval
    
    Returns:
        List of monthly payment breakdowns
    """
    schedule = []
    monthly_rate = interest_rate / 100 / 12
    remaining = total_debt
    
    if loan_type == "annuity":
        for i in range(1, months + 1):
            if remaining <= 0:
                break
            
            interest = remaining * monthly_rate
            principal = min(monthly_payment - interest, remaining)
            remaining -= principal
            
            schedule.append({
                "month": i,
                "payment": round(monthly_payment),
                "principal": round(principal),
                "interest": round(interest),
                "remaining": round(max(0, remaining))
            })
    else:
        # Differentiated
        base_principal = total_debt / max(int(total_debt / monthly_payment), 1)
        
        for i in range(1, months + 1):
            if remaining <= 0:
                break
            
            interest = remaining * monthly_rate
            principal = min(base_principal, remaining)
            payment = principal + interest
            remaining -= principal
            
            schedule.append({
                "month": i,
                "payment": round(payment),
                "principal": round(principal),
                "interest": round(interest),
                "remaining": round(max(0, remaining))
            })
    
    return schedule

