# SOLVO Bot 🚀

**Debt → Freedom → Wealth Operating System**

SOLVO is a Telegram bot that helps users escape debt, remove financial stress, and build savings. Available in Uzbek and Russian.

## Features

- 📱 User registration via Telegram contact sharing
- 🌐 Bilingual support (Uzbek / Russian)
- 👤 Solo and Family modes
- 💰 Comprehensive financial planning
- 📊 Debt freedom date calculation
- 🎯 Savings projections
- 💎 Wealth mode for debt-free users

---

## Quick Start

### 1. Create Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `SOLVO`
4. Choose a username: `solvo_uz_bot` (must end with `bot`)
5. Copy the token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Set Bot Commands

Send to BotFather:
```
/setcommands
```

Select your bot, then paste:
```
start - Boshlash / Начать
help - Yordam / Помощь
status - Joriy reja / Текущий план
language - Tilni o'zgartirish / Сменить язык
```

### 3. Set Bot Description

Send to BotFather:
```
/setdescription
```

Paste:
```
🚀 SOLVO - Qarzdan ozodlik tizimi

Qarzdan qutulish va boylik yaratish yo'lida sizga yordam beraman.

🇷🇺 Система финансовой свободы. Помогу выйти из долгов и начать создавать богатство.
```

### 4. Set Bot About

Send to BotFather:
```
/setabouttext
```

Paste:
```
Moliyaviy erkinlik yo'lida ishonchli hamkor.
Ваш надёжный партнёр на пути к финансовой свободе.
```

---

## Installation

### Local Development

```bash
# Clone or create project directory
cd solvo

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac

# Edit .env and add your BOT_TOKEN
notepad .env  # Windows
nano .env     # Linux/Mac

# Run the bot
python bot.py
```

### Using Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Project Structure

```
solvo/
├── app/
│   ├── __init__.py
│   ├── config.py       # Configuration and constants
│   ├── database.py     # SQLite database layer
│   ├── engine.py       # Financial calculation engine
│   ├── handlers.py     # Telegram bot handlers
│   └── languages.py    # UZ/RU translations
├── data/
│   └── solvo.db        # SQLite database (created automatically)
├── bot.py              # Main entry point
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── .env.example        # Example environment file
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
├── pyproject.toml      # Python project metadata
└── README.md           # This file
```

---

## Database Schema

### users
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| telegram_id | INTEGER | Telegram user ID (unique) |
| phone_number | TEXT | User's phone number |
| first_name | TEXT | First name |
| last_name | TEXT | Last name |
| username | TEXT | Telegram username |
| language | TEXT | Language preference (uz/ru) |
| mode | TEXT | solo/family |
| created_at | TIMESTAMP | Registration date |
| updated_at | TIMESTAMP | Last update |

### financial_profiles
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users |
| income_self | REAL | User's monthly income |
| income_partner | REAL | Partner's income |
| rent | REAL | Monthly rent |
| kindergarten | REAL | Childcare costs |
| utilities | REAL | Utility bills |
| loan_payment | REAL | Monthly loan payment |
| total_debt | REAL | Total remaining debt |

### calculations
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users |
| profile_id | INTEGER | Foreign key to profiles |
| mode | TEXT | debt/wealth |
| free_cash | REAL | Available cash after essentials |
| monthly_savings | REAL | Monthly savings amount |
| exit_months | INTEGER | Months to debt freedom |
| exit_date | TEXT | Projected debt-free date |
| savings_at_exit | REAL | Total savings at exit |

---

## Financial Engine

### Debt Mode (has loans)
```
FreeCash = Income - LoanPayment - LivingCosts

Allocation:
- 10% → Savings
- 20% → Accelerated debt payment
- 70% → Living expenses

TotalDebtPayment = MandatoryPayment + AcceleratedPayment
ExitMonths = TotalDebt / TotalDebtPayment
```

### Wealth Mode (no loans)
```
FreeCash = Income - LivingCosts

Allocation:
- 30% → Investments
- 20% → Savings
- 50% → Living expenses
```

---

## Deployment

### Railway

1. Create account at [railway.app](https://railway.app)
2. Connect GitHub repository
3. Add environment variable: `BOT_TOKEN`
4. Deploy automatically

**railway.json:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Render

1. Create account at [render.com](https://render.com)
2. Create new "Background Worker"
3. Connect repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python bot.py`
6. Add environment variable: `BOT_TOKEN`

### VPS (Ubuntu)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3.11 python3.11-venv python3-pip -y

# Create project directory
mkdir -p /opt/solvo
cd /opt/solvo

# Upload files or clone from git
# ...

# Create venv and install
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/solvo.service
```

**solvo.service:**
```ini
[Unit]
Description=SOLVO Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/solvo
Environment=BOT_TOKEN=your_token_here
ExecStart=/opt/solvo/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable solvo
sudo systemctl start solvo

# Check status
sudo systemctl status solvo

# View logs
sudo journalctl -u solvo -f
```

---

## Testing

### Manual Testing Flow

1. Open bot in Telegram
2. Send `/start`
3. Share your phone number
4. Select language (UZ/RU)
5. Select mode (Solo/Family)
6. Enter test data:
   - Income: `10000000`
   - Partner income (if family): `8000000`
   - Rent: `2000000`
   - Kindergarten: `500000`
   - Utilities: `500000`
   - Loan payment: `1500000`
   - Total debt: `50000000`
7. Verify calculation results

### Test Scenarios

**Debt Mode Test:**
- Income: 10,000,000 UZS
- Living costs: 3,000,000 UZS
- Loan payment: 1,500,000 UZS
- Total debt: 50,000,000 UZS

Expected:
- FreeCash = 10M - 1.5M - 3M = 5.5M
- Savings = 5.5M × 10% = 550,000/month
- Accelerated = 5.5M × 20% = 1.1M
- Total debt payment = 1.5M + 1.1M = 2.6M
- Exit months = 50M / 2.6M ≈ 20 months

**Wealth Mode Test:**
- Income: 10,000,000 UZS
- Living costs: 3,000,000 UZS
- Loan payment: 0
- Total debt: 0

Expected:
- FreeCash = 10M - 3M = 7M
- Invest = 7M × 30% = 2.1M/month
- Savings = 7M × 20% = 1.4M/month

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start registration or restart |
| `/help` | Show help message |
| `/status` | Show current financial plan |
| `/language` | Change language |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token from BotFather |
| `DATABASE_PATH` | No | Path to SQLite database (default: data/solvo.db) |
| `ADMIN_IDS` | No | Comma-separated admin Telegram IDs |

---

## Troubleshooting

### Bot not responding
1. Check if token is correct in `.env`
2. Check logs: `python bot.py` or `docker-compose logs`
3. Ensure bot is not running elsewhere (conflicts)

### Database errors
1. Delete `data/solvo.db` and restart
2. Check file permissions
3. Ensure `data/` directory exists

### Contact sharing not working
1. User must share their OWN contact
2. Must be mobile Telegram (not web)
3. Contact button must be clicked, not typed

---

## Support

- Telegram: @solvo_support
- GitHub Issues: [Create Issue](https://github.com/your-repo/issues)

---

## License

MIT License - Free for commercial and personal use.

---

**Built with ❤️ for financial freedom**
