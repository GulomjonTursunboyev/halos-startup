"""
HALOS Bank Transaction Parser
Parses bank card transaction history from various file formats
Supports: PDF, HTML, Excel (XLSX/XLS), TXT, CSV
Banks: Click, Payme, Uzcard, Humo, and other Uzbek banks
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    UNKNOWN = "unknown"


@dataclass
class Transaction:
    """Single transaction record"""
    date: str
    amount: float
    transaction_type: TransactionType
    description: str = ""
    category: str = ""
    merchant: str = ""
    balance_after: float = 0
    currency: str = "UZS"
    raw_text: str = ""


@dataclass
class TransactionParseResult:
    """Result of transaction parsing"""
    success: bool
    transactions: List[Transaction] = field(default_factory=list)
    total_income: float = 0
    total_expense: float = 0
    income_count: int = 0
    expense_count: int = 0
    period_start: str = ""
    period_end: str = ""
    error_message: str = ""
    source_type: str = ""  # pdf, html, excel, txt


class TransactionParser:
    """
    Universal parser for bank transaction files
    Handles multiple formats and Uzbek bank patterns
    """
    
    # Income indicators (UZ/RU/EN)
    INCOME_PATTERNS = [
        r'(kirim|пополнение|popolnenie|income|deposit|cashback|qaytarildi|vozvrat|возврат)',
        r'(o\'tkazma.*keldi|перевод.*получен|transfer.*received)',
        r'(maosh|зарплата|salary|oylik)',
        r'(bonus|mukofot|премия)',
        r'\+\s*[\d\s,\.]+',  # + sign before amount
    ]
    
    # Expense indicators
    EXPENSE_PATTERNS = [
        r'(chiqim|расход|expense|payment|to\'lov|платеж|оплата)',
        r'(xarid|покупка|purchase)',
        r'(o\'tkazma.*ketdi|перевод.*отправлен|transfer.*sent)',
        r'(yechib olish|снятие|withdrawal|naqd)',
        r'(komissiya|комиссия|fee)',
        r'\-\s*[\d\s,\.]+',  # - sign before amount
    ]
    
    # Amount patterns
    AMOUNT_PATTERNS = [
        r'([\+\-]?)\s*([\d\s,\.]+)\s*(so\'?m|сум|UZS|sum)',
        r'([\+\-]?)\s*([\d\s,\.]+)\s*(USD|\$|EUR|€)',
        r'summa[:\s]*([\d\s,\.]+)',
        r'сумма[:\s]*([\d\s,\.]+)',
        r'amount[:\s]*([\d\s,\.]+)',
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        r'(\d{2}[\./-]\d{2}[\./-]\d{4})',  # DD.MM.YYYY
        r'(\d{4}[\./-]\d{2}[\./-]\d{2})',  # YYYY-MM-DD
        r'(\d{2}[\./-]\d{2}[\./-]\d{2})',  # DD.MM.YY
        r'(\d{1,2}\s+(?:yan|fev|mar|apr|may|iyn|iyl|avg|sen|okt|noy|dek|янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[a-zа-я]*\s+\d{4})',
    ]
    
    # Known merchants/categories
    EXPENSE_CATEGORIES = {
        'food': ['supermarket', 'magazin', 'market', 'korzinka', 'makro', 'havas', 'restaurant', 'cafe', 'oshxona'],
        'transport': ['yandex', 'uber', 'taxi', 'avto', 'benzin', 'gas station', 'azs'],
        'utilities': ['kommunal', 'elektr', 'gaz', 'suv', 'water', 'hududgaz', 'toshshahargaz'],
        'mobile': ['ucell', 'beeline', 'uzmobile', 'mobiuz', 'humans', 'telefon'],
        'internet': ['internet', 'uztelecom', 'sarkor', 'turon'],
        'shopping': ['texnomart', 'mediapark', 'samsung', 'iphone', 'kiyim', 'clothes'],
        'health': ['apteka', 'pharmacy', 'dorixona', 'clinic', 'hospital', 'shifoxona'],
        'education': ['kurs', 'school', 'maktab', 'university', 'talim'],
        'entertainment': ['kino', 'cinema', 'concert', 'park', 'oyin'],
    }
    
    INCOME_CATEGORIES = {
        'salary': ['maosh', 'oylik', 'зарплата', 'salary', 'ish haqi'],
        'transfer': ['otkazma', 'perevod', 'перевод', 'transfer'],
        'cashback': ['cashback', 'qaytarildi', 'vozvrat'],
        'bonus': ['bonus', 'mukofot', 'премия', 'prize'],
    }
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.extension = self.file_path.suffix.lower()
        self.transactions: List[Transaction] = []
    
    def parse(self) -> TransactionParseResult:
        """Parse file based on extension"""
        try:
            if self.extension == '.pdf':
                return self._parse_pdf()
            elif self.extension in ['.html', '.htm']:
                return self._parse_html()
            elif self.extension in ['.xlsx', '.xls']:
                return self._parse_excel()
            elif self.extension == '.csv':
                return self._parse_csv()
            elif self.extension == '.txt':
                return self._parse_txt()
            else:
                return TransactionParseResult(
                    success=False,
                    error_message=f"Unsupported file format: {self.extension}"
                )
        except Exception as e:
            logger.error(f"Transaction parsing error: {e}")
            return TransactionParseResult(
                success=False,
                error_message=str(e)
            )
    
    def _parse_pdf(self) -> TransactionParseResult:
        """Parse PDF bank statement"""
        import pdfplumber
        
        text_parts = []
        tables = []
        
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                
                page_tables = page.extract_tables() or []
                tables.extend(page_tables)
        
        full_text = "\n".join(text_parts)
        
        # Try table parsing first
        transactions = self._parse_tables(tables)
        
        # Fallback to text parsing
        if not transactions:
            transactions = self._parse_text(full_text)
        
        return self._create_result(transactions, "pdf")
    
    def _parse_html(self) -> TransactionParseResult:
        """Parse HTML bank statement"""
        from bs4 import BeautifulSoup
        
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'lxml')
        transactions = []
        
        # Find tables
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            transactions.extend(self._parse_html_table(rows))
        
        # If no tables, try parsing text content
        if not transactions:
            text = soup.get_text(separator='\n')
            transactions = self._parse_text(text)
        
        # Try parsing div-based layouts (Click, Payme style)
        if not transactions:
            transactions = self._parse_html_divs(soup)
        
        return self._create_result(transactions, "html")
    
    def _parse_html_table(self, rows) -> List[Transaction]:
        """Parse HTML table rows"""
        transactions = []
        headers = []
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Detect headers
            if row.find('th') or not headers:
                headers = [c.lower() for c in cell_texts]
                continue
            
            if len(cell_texts) < 2:
                continue
            
            # Try to extract transaction
            tx = self._extract_transaction_from_row(cell_texts, headers)
            if tx:
                transactions.append(tx)
        
        return transactions
    
    def _parse_html_divs(self, soup) -> List[Transaction]:
        """Parse div-based transaction layouts"""
        transactions = []
        
        # Common class patterns for transaction items
        tx_patterns = [
            {'class': re.compile(r'transaction|history|item|row', re.I)},
            {'class': re.compile(r'операция|транзакция', re.I)},
        ]
        
        for pattern in tx_patterns:
            items = soup.find_all('div', pattern)
            for item in items:
                text = item.get_text(separator=' ')
                tx = self._parse_single_transaction(text)
                if tx:
                    transactions.append(tx)
        
        return transactions
    
    def _parse_excel(self) -> TransactionParseResult:
        """Parse Excel bank statement"""
        import pandas as pd
        
        df = pd.read_excel(self.file_path)
        transactions = self._parse_dataframe(df)
        
        return self._create_result(transactions, "excel")
    
    def _parse_csv(self) -> TransactionParseResult:
        """Parse CSV bank statement"""
        import pandas as pd
        
        # Try different encodings and delimiters
        for encoding in ['utf-8', 'cp1251', 'latin-1']:
            for delimiter in [',', ';', '\t']:
                try:
                    df = pd.read_csv(self.file_path, encoding=encoding, delimiter=delimiter)
                    if len(df.columns) > 1:
                        transactions = self._parse_dataframe(df)
                        if transactions:
                            return self._create_result(transactions, "csv")
                except:
                    continue
        
        # Fallback to text parsing
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        transactions = self._parse_text(text)
        return self._create_result(transactions, "csv")
    
    def _parse_txt(self) -> TransactionParseResult:
        """Parse TXT bank statement"""
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        transactions = self._parse_text(text)
        return self._create_result(transactions, "txt")
    
    def _parse_dataframe(self, df) -> List[Transaction]:
        """Parse pandas DataFrame"""
        import pandas as pd
        
        transactions = []
        
        # Normalize column names
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Find relevant columns
        date_col = self._find_column(df.columns, ['date', 'sana', 'дата', 'vaqt', 'время'])
        amount_col = self._find_column(df.columns, ['amount', 'summa', 'сумма', 'miqdor'])
        income_col = self._find_column(df.columns, ['kirim', 'приход', 'credit', 'income', 'debet'])
        expense_col = self._find_column(df.columns, ['chiqim', 'расход', 'debit', 'expense', 'kredit'])
        desc_col = self._find_column(df.columns, ['description', 'tavsif', 'описание', 'detail', 'comment'])
        type_col = self._find_column(df.columns, ['type', 'tur', 'тип', 'operation'])
        
        for _, row in df.iterrows():
            tx = Transaction(
                date="",
                amount=0,
                transaction_type=TransactionType.UNKNOWN,
                description=""
            )
            
            # Extract date
            if date_col:
                tx.date = str(row.get(date_col, ""))
            
            # Extract amount and type
            if income_col and expense_col:
                income = self._parse_amount(row.get(income_col, 0))
                expense = self._parse_amount(row.get(expense_col, 0))
                
                if income > 0:
                    tx.amount = income
                    tx.transaction_type = TransactionType.INCOME
                elif expense > 0:
                    tx.amount = expense
                    tx.transaction_type = TransactionType.EXPENSE
            elif amount_col:
                amount = self._parse_amount(row.get(amount_col, 0))
                tx.amount = abs(amount)
                
                # Determine type from amount sign or type column
                if type_col:
                    type_text = str(row.get(type_col, "")).lower()
                    if self._is_income(type_text):
                        tx.transaction_type = TransactionType.INCOME
                    elif self._is_expense(type_text):
                        tx.transaction_type = TransactionType.EXPENSE
                elif amount < 0:
                    tx.transaction_type = TransactionType.EXPENSE
                else:
                    tx.transaction_type = TransactionType.INCOME
            
            # Extract description
            if desc_col:
                tx.description = str(row.get(desc_col, ""))
            
            # Categorize
            if tx.transaction_type == TransactionType.EXPENSE:
                tx.category = self._categorize_expense(tx.description)
            elif tx.transaction_type == TransactionType.INCOME:
                tx.category = self._categorize_income(tx.description)
            
            if tx.amount > 0:
                transactions.append(tx)
        
        return transactions
    
    def _parse_tables(self, tables) -> List[Transaction]:
        """Parse PDF/extracted tables"""
        transactions = []
        
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            headers = [str(cell).lower() if cell else "" for cell in table[0]]
            
            for row in table[1:]:
                if not row or len(row) < 2:
                    continue
                
                tx = self._extract_transaction_from_row(row, headers)
                if tx:
                    transactions.append(tx)
        
        return transactions
    
    def _extract_transaction_from_row(self, row, headers) -> Optional[Transaction]:
        """Extract transaction from a table row"""
        row_text = " ".join(str(cell) for cell in row if cell)
        
        # Find indices
        date_idx = self._find_index(headers, ['date', 'sana', 'дата', 'vaqt'])
        amount_idx = self._find_index(headers, ['amount', 'summa', 'сумма', 'miqdor'])
        income_idx = self._find_index(headers, ['kirim', 'приход', 'credit', 'debet'])
        expense_idx = self._find_index(headers, ['chiqim', 'расход', 'debit', 'kredit'])
        desc_idx = self._find_index(headers, ['description', 'tavsif', 'описание', 'detail'])
        
        tx = Transaction(
            date="",
            amount=0,
            transaction_type=TransactionType.UNKNOWN,
            raw_text=row_text
        )
        
        # Extract date
        if date_idx is not None and date_idx < len(row):
            tx.date = str(row[date_idx] or "")
        else:
            # Try to find date in row text
            for pattern in self.DATE_PATTERNS:
                match = re.search(pattern, row_text, re.IGNORECASE)
                if match:
                    tx.date = match.group(1)
                    break
        
        # Extract amount
        if income_idx is not None and expense_idx is not None:
            if income_idx < len(row):
                income = self._parse_amount(row[income_idx])
                if income > 0:
                    tx.amount = income
                    tx.transaction_type = TransactionType.INCOME
            
            if expense_idx < len(row) and tx.amount == 0:
                expense = self._parse_amount(row[expense_idx])
                if expense > 0:
                    tx.amount = expense
                    tx.transaction_type = TransactionType.EXPENSE
        elif amount_idx is not None and amount_idx < len(row):
            amount = self._parse_amount(row[amount_idx])
            tx.amount = abs(amount)
            tx.transaction_type = TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME
        else:
            # Try to find amount in text
            amount, is_expense = self._extract_amount_from_text(row_text)
            tx.amount = amount
            if is_expense:
                tx.transaction_type = TransactionType.EXPENSE
            elif amount > 0:
                tx.transaction_type = TransactionType.INCOME
        
        # Extract description
        if desc_idx is not None and desc_idx < len(row):
            tx.description = str(row[desc_idx] or "")
        else:
            tx.description = row_text
        
        # Determine type from description if still unknown
        if tx.transaction_type == TransactionType.UNKNOWN:
            if self._is_income(tx.description):
                tx.transaction_type = TransactionType.INCOME
            elif self._is_expense(tx.description):
                tx.transaction_type = TransactionType.EXPENSE
        
        # Categorize
        if tx.transaction_type == TransactionType.EXPENSE:
            tx.category = self._categorize_expense(tx.description)
        elif tx.transaction_type == TransactionType.INCOME:
            tx.category = self._categorize_income(tx.description)
        
        return tx if tx.amount > 0 else None
    
    def _parse_text(self, text: str) -> List[Transaction]:
        """Parse transactions from raw text"""
        transactions = []
        
        # Split into potential transaction blocks
        lines = text.split('\n')
        
        current_block = []
        for line in lines:
            line = line.strip()
            if not line:
                if current_block:
                    tx = self._parse_single_transaction("\n".join(current_block))
                    if tx:
                        transactions.append(tx)
                    current_block = []
            else:
                current_block.append(line)
                
                # Check if this line contains a complete transaction
                if self._contains_amount(line):
                    tx = self._parse_single_transaction(line)
                    if tx:
                        transactions.append(tx)
                    current_block = []
        
        # Process last block
        if current_block:
            tx = self._parse_single_transaction("\n".join(current_block))
            if tx:
                transactions.append(tx)
        
        return transactions
    
    def _parse_single_transaction(self, text: str) -> Optional[Transaction]:
        """Parse a single transaction from text block"""
        if not text or len(text) < 5:
            return None
        
        tx = Transaction(
            date="",
            amount=0,
            transaction_type=TransactionType.UNKNOWN,
            description=text[:200],
            raw_text=text
        )
        
        # Extract date
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                tx.date = match.group(1)
                break
        
        # Extract amount and determine type
        amount, is_expense = self._extract_amount_from_text(text)
        tx.amount = amount
        
        if is_expense:
            tx.transaction_type = TransactionType.EXPENSE
        elif self._is_income(text):
            tx.transaction_type = TransactionType.INCOME
        elif self._is_expense(text):
            tx.transaction_type = TransactionType.EXPENSE
        elif amount > 0:
            # Default based on context or assume expense
            tx.transaction_type = TransactionType.EXPENSE
        
        # Categorize
        if tx.transaction_type == TransactionType.EXPENSE:
            tx.category = self._categorize_expense(text)
        elif tx.transaction_type == TransactionType.INCOME:
            tx.category = self._categorize_income(text)
        
        return tx if tx.amount > 0 else None
    
    def _extract_amount_from_text(self, text: str) -> Tuple[float, bool]:
        """Extract amount and sign from text"""
        is_expense = False
        amount = 0
        
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    sign = groups[0] if groups[0] else ""
                    amount_str = groups[1]
                else:
                    sign = ""
                    amount_str = groups[0]
                
                amount = self._parse_amount(amount_str)
                is_expense = sign == '-'
                break
        
        # Check for explicit minus in text
        if re.search(r'-\s*[\d\s,\.]+\s*(so\'?m|сум|UZS)', text, re.IGNORECASE):
            is_expense = True
        
        return amount, is_expense
    
    def _contains_amount(self, text: str) -> bool:
        """Check if text contains an amount"""
        for pattern in self.AMOUNT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _is_income(self, text: str) -> bool:
        """Check if text indicates income"""
        text_lower = text.lower()
        for pattern in self.INCOME_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _is_expense(self, text: str) -> bool:
        """Check if text indicates expense"""
        text_lower = text.lower()
        for pattern in self.EXPENSE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _categorize_expense(self, text: str) -> str:
        """Categorize expense based on description"""
        text_lower = text.lower()
        for category, keywords in self.EXPENSE_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        return "other"
    
    def _categorize_income(self, text: str) -> str:
        """Categorize income based on description"""
        text_lower = text.lower()
        for category, keywords in self.INCOME_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        return "other"
    
    def _parse_amount(self, value) -> float:
        """Parse amount from various formats"""
        if value is None:
            return 0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        text = str(value)
        
        # Remove currency and text
        text = re.sub(r'[^\d,\.\-\+]', '', text)
        
        # Handle formats
        if ',' in text and '.' in text:
            # Determine which is decimal separator
            if text.rfind(',') > text.rfind('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            # Check if comma is thousands or decimal
            parts = text.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                text = text.replace(',', '.')
            else:
                text = text.replace(',', '')
        
        text = text.replace(' ', '')
        
        try:
            return abs(float(text))
        except ValueError:
            return 0
    
    def _find_column(self, columns, keywords) -> Optional[str]:
        """Find column name by keywords"""
        for col in columns:
            for kw in keywords:
                if kw in str(col).lower():
                    return col
        return None
    
    def _find_index(self, items, keywords) -> Optional[int]:
        """Find index by keywords"""
        for i, item in enumerate(items):
            for kw in keywords:
                if kw in str(item).lower():
                    return i
        return None
    
    def _create_result(self, transactions: List[Transaction], source: str) -> TransactionParseResult:
        """Create parse result from transactions"""
        total_income = sum(t.amount for t in transactions if t.transaction_type == TransactionType.INCOME)
        total_expense = sum(t.amount for t in transactions if t.transaction_type == TransactionType.EXPENSE)
        income_count = sum(1 for t in transactions if t.transaction_type == TransactionType.INCOME)
        expense_count = sum(1 for t in transactions if t.transaction_type == TransactionType.EXPENSE)
        
        # Get period
        dates = [t.date for t in transactions if t.date]
        period_start = min(dates) if dates else ""
        period_end = max(dates) if dates else ""
        
        return TransactionParseResult(
            success=len(transactions) > 0,
            transactions=transactions,
            total_income=total_income,
            total_expense=total_expense,
            income_count=income_count,
            expense_count=expense_count,
            period_start=period_start,
            period_end=period_end,
            source_type=source
        )


def parse_transactions(file_path: str) -> TransactionParseResult:
    """
    Convenience function to parse bank transactions
    
    Args:
        file_path: Path to the transaction file (PDF, HTML, Excel, TXT, CSV)
        
    Returns:
        TransactionParseResult with parsed data
    """
    parser = TransactionParser(file_path)
    return parser.parse()


def calculate_monthly_averages(result: TransactionParseResult) -> Dict[str, float]:
    """Calculate monthly averages from transactions"""
    if not result.transactions:
        return {"monthly_income": 0, "monthly_expense": 0}
    
    # Try to determine period length
    try:
        from dateutil import parser as date_parser
        
        dates = [t.date for t in result.transactions if t.date]
        if len(dates) >= 2:
            parsed_dates = []
            for d in dates:
                try:
                    parsed_dates.append(date_parser.parse(d, dayfirst=True))
                except:
                    pass
            
            if parsed_dates:
                min_date = min(parsed_dates)
                max_date = max(parsed_dates)
                days = (max_date - min_date).days
                months = max(days / 30, 1)
                
                return {
                    "monthly_income": result.total_income / months,
                    "monthly_expense": result.total_expense / months,
                    "period_months": months
                }
    except:
        pass
    
    # Default to assuming 1 month of data
    return {
        "monthly_income": result.total_income,
        "monthly_expense": result.total_expense,
        "period_months": 1
    }
