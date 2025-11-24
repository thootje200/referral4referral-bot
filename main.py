import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# -------------------------------------------------------
# Load bot token
# -------------------------------------------------------
TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)

# -------------------------------------------------------
# Create PTB Application
# -------------------------------------------------------
application = Application.builder().token(TOKEN).build()

# -------------------------------------------------------
# Start command
# -------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welkom bij de Referral4Referral bot!\n\nStuur je referral link om mee te doen."
    )

# Add handler
application.add_handler(CommandHandler("start", start))

# -------------------------------------------------------
# Webhook Endpoint
# -------------------------------------------------------
@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json(force=True)
    print("Update received:", data)  # check logs
    if data:
        update = Update.de_json(data, application.bot)
        asyncio.run(application.process_update(update))
    return "ok", 200


@app.get("/")
def home():
    return "Bot running!"

# -------------------------------------------------------
# Start Flask + set webhook on startup
# -------------------------------------------------------
if __name__ == "__main__":
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"

    # Set webhook synchronously before Flask starts
    import requests
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")

    print(f"Webhook ingesteld: {WEBHOOK_URL}")

    # Belangrijk! Initialiseer de Telegram Application expliciet
    asyncio.run(application.initialize())

    app.run(host="0.0.0.0", port=10000)
