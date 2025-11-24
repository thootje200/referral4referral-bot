import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if TOKEN is None:
    raise RuntimeError("BOT_TOKEN is not set!")
if WEBHOOK_URL is None:
    raise RuntimeError("WEBHOOK_URL is not set!")

app = Flask(__name__)

# Build bot with PTB 21.x (no Updater anymore)
application = Application.builder().token(TOKEN).updater(None).build()


# ------------------ BOT COMMANDS ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online 🔥 Stuur iets!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Je stuurde: {update.message.text}")


application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# ------------------ WEBHOOK ENDPOINT ------------------
@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json(force=True)
    if data:
        update = Update.de_json(data, application.bot)

        # Ensure the event loop exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run PTB asynchronously inside Flask
        loop.create_task(application.process_update(update))

    return "ok", 200


@app.get("/")
def home():
    return "Bot running!"


# ------------------ STARTUP ------------------

if __name__ == "__main__":
    import asyncio

    async def setup():
        await application.initialize()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook/{TOKEN}")
        await application.start()
        print("Webhook ingesteld:", f"{WEBHOOK_URL}/webhook/{TOKEN}")

    asyncio.run(setup())

    app.run(host="0.0.0.0", port=10000)
