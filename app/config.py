"""
HALOS Bot Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/solvo.db")
DATABASE_URL = BASE_DIR / DATABASE_PATH

# Admin IDs
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# Financial constants
DEBT_MODE_SAVINGS_RATE = 0.10      # 10% to savings
DEBT_MODE_ACCELERATED_RATE = 0.20  # 20% to accelerated debt payment
DEBT_MODE_LIVING_RATE = 0.70       # 70% to living

WEALTH_MODE_INVEST_RATE = 0.30     # 30% to investments
WEALTH_MODE_SAVINGS_RATE = 0.20    # 20% to savings
WEALTH_MODE_LIVING_RATE = 0.50     # 50% to living

# Supported languages
LANGUAGES = ["uz", "ru"]
DEFAULT_LANGUAGE = "uz"

# Upload directories
PDF_UPLOAD_DIR = BASE_DIR / "data" / "uploads"
TRANSACTION_UPLOAD_DIR = BASE_DIR / "data" / "transactions"

# Supported transaction file extensions
TRANSACTION_EXTENSIONS = ['.pdf', '.html', '.htm', '.xlsx', '.xls', '.csv', '.txt']

# Conversation states
class States:
    LANGUAGE = 0
    MODE = 1
    TRANSACTION_CHOICE = 2   # Ask about transaction history upload
    TRANSACTION_UPLOAD = 3   # Waiting for transaction file(s)
    TRANSACTION_SUMMARY = 4  # Show multi-card summary
    INCOME_SELF = 5
    INCOME_PARTNER = 6
    RENT = 7
    KINDERGARTEN = 8
    UTILITIES = 9
    KATM_CHOICE = 10         # Ask about KATM upload
    KATM_UPLOAD = 11         # Waiting for PDF
    LOAN_PAYMENT = 12        # Manual entry
    TOTAL_DEBT = 13          # Manual entry
    CONFIRM = 14
