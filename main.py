from flask import Flask, request
import telegram
import os
import asyncio

TOKEN = os.environ.get("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
async def respond():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.message:
        chat_id = update.message.chat.id
        text = update.message.text

        if text == "/start":
            await bot.send_message(chat_id, "Welkom bij de Referral4Referral bot!\n\nStuur je referral link om mee te doen.")
        elif text:
            await bot.send_message(chat_id, f"Je hebt gestuurd: {text}")

    return "ok"

@app.route("/")
def home():
    return "Bot draait!"

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    app.run(host="0.0.0.0", port=10000)