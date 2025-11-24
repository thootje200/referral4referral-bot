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

    if data:
        update = Update.de_json(data, application.bot)

        # event loop fix for Flask
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.create_task(application.process_update(update))

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

    app.run(host="0.0.0.0", port=10000)
