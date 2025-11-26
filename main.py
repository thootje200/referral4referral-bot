import os
import threading
import atexit
import asyncio
import re
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext
)
from database import Database, UserStatus
from queue_manager import QueueManager

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Set in environment
app = Flask(__name__)

# Initialize database and queue manager
db = Database("referral_bot.db")
queue_manager = QueueManager(db)

# Maak de Telegram Application
application = Application.builder().token(TOKEN).build()

# Start een achtergrond event loop voor async PTB updates
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

async def start_bot():
    await application.initialize()
    await application.start()
    print("BOT STARTED")

asyncio.run_coroutine_threadsafe(start_bot(), loop)

def is_valid_link(text: str) -> bool:
    """Validate if text contains a valid URL"""
    url_pattern = r"https?://[^\s]+"
    return bool(re.search(url_pattern, text))

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome and instructions"""
    welcome_message = (
        "🎉 Welcome to Referral4Referral Bot!\n\n"
        "Here's how it works:\n"
        "1️⃣ Send your referral link\n"
        "2️⃣ You'll be placed in a queue\n"
        "3️⃣ When it's your turn, you'll receive another user's referral link\n"
        "4️⃣ Complete the referral and send /done\n"
        "5️⃣ You'll earn credit and rejoin the queue\n\n"
        "📤 Send your referral link now to get started!"
    )
    await update.message.reply_text(welcome_message)

application.add_handler(CommandHandler("start", start))

# /done handler - mark referral as completed
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /done command - mark referral as completed"""
    user_id = update.effective_user.id
    success, message = queue_manager.mark_referral_completed(user_id)
    await update.message.reply_text(message)
    
    # Try to assign next referral
    next_user_id, next_link = queue_manager.get_next_assignment()
    if next_user_id:
        try:
            await context.bot.send_message(
                chat_id=next_user_id,
                text=f"🎯 Your turn! Please complete this referral:\n\n{next_link}"
            )
        except Exception as e:
            print(f"Error sending referral to {next_user_id}: {e}")

application.add_handler(CommandHandler("done", done))

# /queue handler - show current queue (admin only)
async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /queue command - show queue list (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    queue_list = queue_manager.get_full_queue_list()
    await update.message.reply_text(f"📋 Current Queue:\n\n{queue_list}")

application.add_handler(CommandHandler("queue", queue_command))

# /stats handler - show statistics (admin only)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show bot statistics (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    stats_data = db.get_stats()
    status_msg = queue_manager.get_queue_status()
    
    stats_text = (
        f"📊 Bot Statistics\n\n"
        f"{status_msg}\n\n"
        f"Completed referrals: {stats_data['completed_referrals']}"
    )
    await update.message.reply_text(stats_text)

application.add_handler(CommandHandler("stats", stats))

# /reset handler - remove user from queue (admin only)
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command - remove user from queue (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /reset <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        success, message = queue_manager.remove_user_from_queue(target_user_id)
        await update.message.reply_text(message)
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

application.add_handler(CommandHandler("reset", reset))

# /broadcast handler - send message to all users (admin only)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command - send message to all users (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message_text = " ".join(context.args)
    all_users = db.get_all_users()
    
    sent = 0
    failed = 0
    
    for user in all_users:
        try:
            await context.bot.send_message(
                chat_id=user.user_id,
                text=f"📢 Announcement:\n\n{message_text}"
            )
            sent += 1
        except Exception as e:
            print(f"Failed to send to {user.user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(f"✅ Broadcast complete!\nSent: {sent}, Failed: {failed}")

application.add_handler(CommandHandler("broadcast", broadcast))

# /info handler - get user info
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command - show user's info"""
    user_id = update.effective_user.id
    info_text = queue_manager.get_user_info(user_id)
    
    if info_text:
        await update.message.reply_text(info_text)
    else:
        await update.message.reply_text("❌ You're not in the system. Send /start to get started.")

application.add_handler(CommandHandler("info", info))

# Handler voor gewone tekst (referral links)
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle referral link submission"""
    user_id = update.effective_user.id
    link = update.message.text
    
    # Validate link
    if not is_valid_link(link):
        await update.message.reply_text(
            "❌ Invalid link format. Please send a valid URL starting with http:// or https://"
        )
        return
    
    # Add user to queue
    success, message = queue_manager.add_user_to_queue(user_id, link)
    await update.message.reply_text(message)
    
    if success:
        # Try to assign referral to the newly added user
        next_user_id, next_link = queue_manager.get_next_assignment()
        if next_user_id:
            try:
                await context.bot.send_message(
                    chat_id=next_user_id,
                    text=f"🎯 Your turn! Please complete this referral:\n\n{next_link}"
                )
            except Exception as e:
                print(f"Error sending referral to {next_user_id}: {e}")

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, referral_handler))

@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)

    # Plan het async update in de background loop
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)

    return "OK"


@app.get("/")
def home():
    return "Bot running!"


if __name__ == "__main__":
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"

    # Zet webhook bij Telegram
    import requests
    resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print("SetWebhook response:", resp.status_code, resp.text)
    print(f"Webhook ingesteld: {WEBHOOK_URL}")

    # Start Flask (ontwikkelserver). Render draait dit script als process.
    app.run(host="0.0.0.0", port=10000)
