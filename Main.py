# main.py
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import os
import asyncio

# ---------------------
# In-memory database
# ---------------------
waiting_users = {}  # {user_id: link}
queue = []          # links die gepromoot moeten worden

# ---------------------
# Telegram bot commands
# ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welkom bij Referral4Referral!\nStuur je referral link om mee te doen."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    link = update.message.text.strip()
    waiting_users[user_id] = link

    if queue:
        other = queue.pop(0)
        await update.message.reply_text(
            f"Klik op deze referral link:\n{other}\nStuur daarna: GEKLIKT"
        )
    else:
        await update.message.reply_text(
            "Je staat in de wachtrij… zodra er iemand beschikbaar is krijg je een link."
        )

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in waiting_users:
        await update.message.reply_text("Je hebt nog geen link ingestuurd.")
        return

    link = waiting_users[user_id]
    queue.append(link)
    del waiting_users[user_id]

    await update.message.reply_text("Top! Je bent bevestigd. Jouw link wordt nu gedeeld met de volgende gebruiker.")

# ---------------------
# Flask keep-alive server
# ---------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot draait!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ---------------------
# Run Telegram bot
# ---------------------
async def main():
    bot_token = os.getenv("BOT_TOKEN")  # je token uit Render Environment Variable
    app2 = ApplicationBuilder().token(bot_token).build()

    app2.add_handler(CommandHandler("start", start))
    app2.add_handler(MessageHandler(filters.Regex("http"), handle_link))
    app2.add_handler(MessageHandler(filters.Regex("GEKLIKT"), confirm))

    print("Bot draait…")
    await app2.run_polling()

asyncio.run(main())
