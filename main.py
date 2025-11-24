from flask import Flask, request
import telegram
import os

TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

# Webhook endpoint
@app.route(f"/{TOKEN}", methods=["POST"])
def respond():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    chat_id = update.message.chat.id
    text = update.message.text

    if text == "/start":
        bot.send_message(chat_id, "Welkom bij de Referral4Referral bot!\n\nStuur je referral link om mee te doen.")
    else:
        bot.send_message(chat_id, f"Je hebt gestuurd: {text}")

    return "ok"

@app.route("/")
def home():
    return "Bot draait!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
