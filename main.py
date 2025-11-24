import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

# Telegram App bouwen
application = Application.builder().token(TOKEN).build()

# /start-commando
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welkom bij de Referral4Referral bot!\n\nStuur je referral link om mee te doen."
    )

application.add_handler(CommandHandler("start", start))

# Referral link handler (voor alle gewone tekstberichten)
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    # Hier kun je nog validatie doen, voor nu alleen echo
    await update.message.reply_text(f"Dank voor je referral link: {link}")

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, referral_handler))

# Webhook endpoint
@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json(force=True)
    print("Update received:", data)
    if data:
        update = Update.de_json(data, application.bot)
        # BELANGRIJK: Gebruik asyncio.run() in Flask!
        asyncio.run(application.process_update(update))
    return "ok", 200

@app.get("/")
def home():
    return "Bot running!"

if __name__ == "__main__":
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"

    # Zet webhook bij Telegram
    import requests
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print(f"Webhook ingesteld: {WEBHOOK_URL}")

    # Init Telegram app (async!)
    asyncio.run(application.initialize())

    # Start Flask app!
    app.run(host="0.0.0.0", port=10000)
