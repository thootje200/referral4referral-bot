import os
import threading
import atexit
import asyncio
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)
from database import Database, UserStatus
from queue_manager import QueueManager

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# --- Functie: Foutmelding - gebruiker is nog niet in de groep ---
def get_not_member_buttons():
    keyboard = [
        [InlineKeyboardButton("Join Channel ➡️", url="https://t.me/ref4refupdates")],
        [InlineKeyboardButton("Refresh 🔄", callback_data="refresh_membership")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Functie: Welkomstbericht /start ---
def get_welcome_buttons():
    keyboard = [
        [InlineKeyboardButton("Send Referral Link 📤", callback_data="send_link")],
        [InlineKeyboardButton("Help ❓", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Functie: Queue toegevoegd / referral link geaccepteerd ---
def get_queue_buttons():
    keyboard = [
        [InlineKeyboardButton("Cancel ❌", callback_data="cancel_queue")],
        [InlineKeyboardButton("Switch 🔄", callback_data="switch_link")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Functie: Help pagina knoppen ---
def get_help_buttons():
    keyboard = [
        [InlineKeyboardButton("Send Referral Link 📤", callback_data="send_link")],
        [InlineKeyboardButton("My Info ℹ️", callback_data="my_info")],
        [InlineKeyboardButton("Back 🔙", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)


CHANNEL_USERNAME = "@ref4refupdates"  # channel users must join

async def check_membership(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        else:
            return False
    except:
        return False
# --- End force join check ---


TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Set in environment
app = Flask(__name__)

# Initialize database and queue manager
db = Database("referral_bot.db")
queue_manager = QueueManager(db)

# Create the Telegram Application
application = Application.builder().token(TOKEN).build()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Send Referral Link 📤", "My Info ℹ️"],
        ["Done Referral ✅", "Queue Status 📋"],
        ["Help ❓"],
    ],
    resize_keyboard=True
)

# Start a background event loop for async PTB updates
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_membership(update, context):
        await update.message.reply_text(
            f"❌ You must join our channel {CHANNEL_USERNAME} first!\n"
            f"Join here: https://t.me/{CHANNEL_USERNAME.strip('@')}"
        )
        return

    welcome_message = (
        "🎉 Welcome to Referral4Referral Bot!\n\n"
        "Here's how it works:\n"
        "1️⃣ Send your referral link\n"
        "2️⃣ You'll be placed in a queue\n"
        "3️⃣ When it's your turn, you'll receive another user's referral link\n"
        "4️⃣ Complete the referral and click '✅ Done'\n"
        "5️⃣ You'll earn credit and rejoin the queue\n\n"
        "📤 Send your referral link now to get started!"
    )
    await update.message.reply_text(welcome_message, reply_markup=get_welcome_buttons())

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

# Handler for plain text (referral links)
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle referral link submission"""
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    if not text:
        return

    if text == "Send Referral Link 📤":
        await update.message.reply_text(
            "Send your referral link so we can add you to the queue.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if text == "My Info ℹ️":
        info_text = queue_manager.get_user_info(user_id)
        if info_text:
            await update.message.reply_text(info_text, reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text(
                "🚫 You are no longer a member of our channel.\n"
                "After joining, please send your referral link again.",
                reply_markup=get_not_member_buttons() 
)

        return

    if text == "Done Referral ✅":
        await done(update, context)
        return

    if text == "Queue Status 📋":
        await update.message.reply_text(queue_manager.get_queue_status(), reply_markup=MAIN_KEYBOARD)
        return

    if text == "Help ❓":
        help_text = (
            "Use the buttons to quickly access actions:\n"
            "📤 Send Referral Link: submit your link and join the queue\n"
            "ℹ️ My Info: view your status and credits\n"
            "✅ Done Referral: confirm a completed referral\n"
            "📋 Queue Status: check the current queue\n"
            "❓ Help: short explanation"
        )
        await update.message.reply_text(help_text, reply_markup=get_help_buttons())  # regel 307

        return

    link = text

    if not await check_membership(update, context):
        if queue_manager.get_queue_position(user_id) is not None:
            queue_manager.remove_user_from_queue(user_id)

        await update.message.reply_text(
            "🚫 You are no longer a member of our channel.\n"
            "➡️ Join here: https://t.me/ref4refupdates\n\n"
            "After joining, please send your referral link again.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if not is_valid_link(link):
        await update.message.reply_text(
            "❌ Invalid link format. Please send a valid URL starting with http:// or https://",
            reply_markup=MAIN_KEYBOARD
        )
        return
    
    success, message = queue_manager.add_user_to_queue(user_id, link)
    await update.message.reply_text(message, reply_markup=get_queue_buttons()) 

    
    if success:
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # acknowledge the callback

    if query.data == "refresh_membership":
        await start(update, context)
    elif query.data == "send_link":
        await query.message.reply_text("Send your referral link now.", reply_markup=MAIN_KEYBOARD)
    elif query.data == "help":
        help_text = (
            "Use the buttons to quickly access actions:\n"
            "📤 Send Referral Link: submit your link and join the queue\n"
            "ℹ️ My Info: view your status and credits\n"
            "✅ Done Referral: confirm a completed referral\n"
            "📋 Queue Status: check the current queue\n"
            "❓ Help: short explanation"
        )
        await query.message.reply_text(help_text, reply_markup=get_help_buttons())
    elif query.data == "cancel_queue":
        user_id = query.from_user.id
        queue_manager.remove_user_from_queue(user_id)
        await query.message.reply_text("You have been removed from the queue.", reply_markup=MAIN_KEYBOARD)
    elif query.data == "switch_link":
        await query.message.reply_text("Send your new referral link.", reply_markup=MAIN_KEYBOARD)
    elif query.data == "my_info":
        user_id = query.from_user.id
        info_text = queue_manager.get_user_info(user_id)
        await query.message.reply_text(info_text or "❌ You're not in the queue.", reply_markup=MAIN_KEYBOARD)
    elif query.data == "back":
        await query.message.reply_text("Back to main menu.", reply_markup=MAIN_KEYBOARD)

application.add_handler(CallbackQueryHandler(button_callback))  # regel 404

@app.post(f"/webhook/{TOKEN}")
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)

    # Schedule the async update in the background loop
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)

    return "OK"


@app.get("/")
def home():
    return "Bot running!"


if __name__ == "__main__":
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"

    # Set webhook with Telegram
    import requests
    resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print("SetWebhook response:", resp.status_code, resp.text)
    print(f"Webhook configured: {WEBHOOK_URL}")

    # Start Flask (ontwikkelserver). Render draait dit script als process.
    app.run(host="0.0.0.0", port=10000)
