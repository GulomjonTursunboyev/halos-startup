"""Simple test bot to verify Telegram connection"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8504981935:AAEqLmWRaTRG7BnQYzgrNlOfEDnvF4Z5n_M"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.effective_user.id}")
    await update.message.reply_text("Salom! Bot ishlayapti! ✅")

def main():
    print("Starting test bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot is running! Send /start to @Solvoappbot")
    app.run_polling()

if __name__ == "__main__":
    main()
