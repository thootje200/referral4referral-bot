from flask import Flask, request
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Bijvoorbeeld: https://jouw-service.onrender.com

app = Flask(__name__)

# --- Telegram application ---
application = Application.builder().token(TOKEN).build()

# /start command
async def start(update: Update, context):
    await update.message.reply_text(
        "Welkom bij de Referral4Referral bot! 🎉\n\n"
        "Stuur je referral link om mee te doen."
    )

# Alle andere berichten
async def echo(update: Update, context):
    await update.message.reply_text(f"Je stuurde: {update.message.text}")

# Handlers registreren
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# --- Flask webhook route ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.create_task(application.process_update(update))
    return "ok"


@app.route("/")
def home():
    return "Bot draait!"


if __name__ == "__main__":
    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
    )
