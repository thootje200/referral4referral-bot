import os
import threading
import atexit
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

# Maak de Telegram Application
application = Application.builder().token(TOKEN).build()

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welkom bij de Referral4Referral bot!\n\nStuur je referral link om mee te doen."
    )

application.add_handler(CommandHandler("start", start))

# Handler voor gewone tekst (referral links)
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    # TODO: validatie / opslag / matching
    await update.message.reply_text(f"Dank voor je referral link: {link}")

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, referral_handler))

# ---- Maak één permanente event loop in een achtergrondthread ----
loop = asyncio.new_event_loop()

def _start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop_thread = threading.Thread(target=_start_loop, daemon=True)
loop_thread.start()

# Initialiseer de Telegram Application op die loop
init_future = asyncio.run_coroutine_threadsafe(application.initialize(), loop)
# Optioneel wachten totdat initialize klaar is (handig bij startup)
try:
    init_future.result(timeout=15)
except Exception as e:
    # Als initialize faalt: log en ga door (Flask blijft draaien)
    print("Fout bij initialisatie van Application:", repr(e))

# Webhook endpoint: schedule het verwerken van de update op de achtergrondloop
@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json(force=True)
    print("Update received:", data)
    if data:
        update = Update.de_json(data, application.bot)
        # Plan de verwerking op de background loop (niet blokkeren)
        try:
            asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        except Exception as e:
            print("Fout bij schedule process_update:", repr(e))
    return "ok", 200

@app.get("/")
def home():
    return "Bot running!"

# Netjes afsluiten bij exit
def _shutdown():
    try:
        # Eerst de Application netjes afsluiten
        fut = asyncio.run_coroutine_threadsafe(application.shutdown(), loop)
        try:
            fut.result(timeout=15)
        except Exception as e:
            print("Fout bij application.shutdown:", repr(e))
    finally:
        # Stop de loop en join thread
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=5)

atexit.register(_shutdown)

if __name__ == "__main__":
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"

    # Zet webhook bij Telegram
    import requests
    resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print("SetWebhook response:", resp.status_code, resp.text)
    print(f"Webhook ingesteld: {WEBHOOK_URL}")

    # Start Flask (ontwikkelserver). Render draait dit script als process.
    app.run(host="0.0.0.0", port=10000)
