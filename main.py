import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # <-- verplicht in environment

app = Flask(__name__)

# --- Telegram bot setup ---
application = Application.builder().token(TOKEN).build()

# Start command
async def start(update: Update, context):
    await update.message.reply_text(
        "Welkom bij de Referral4Referral bot!\n\n"
        "Stuur je referral link om mee te doen."
    )

# Default echo handler
async def handle_message(update: Update, context):
    text = update.message.text
    await update.message.reply_text(f"Je hebt gestuurd: {text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Flask webhook endpoint ---
@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.create_update(update)
    return "ok"

# --- Home route ---
@app.get("/")
def home():
    return "Bot draait!"

if __name__ == "__main__":
    # Webhook instellen bij Telegram
    import asyncio

    async def set_webhook():
        await application.bot.delete_webhook()
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{TOKEN}")

    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=10000)
