from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, Dispatcher, CallbackQueryHandler
)
from flask import Flask, request
import telegram
import os

TOKEN = os.environ["7295837680:AAHoyemM8trkOzeUvlWNDC7VZu8WoCKv4P0"]
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

# قائمة البوتات الدراسية
bots = {
    "💡 الكهرباء": "https://t.me/moreng7_bot",
    "📶 الاتصالات": "https://t.me/moreng1_bot",
    "⚙️ التحكم": "https://t.me/moreng5_bot",
    "📊 تحليل النظم": "https://t.me/moreng3_bot",
    "🧠 الآلات الخاصة": "https://t.me/moreng4_bot",
    "📚 إلكترونيات": "https://t.me/moreng6_bot",
    "🖥 الشبكات": "https://t.me/moreng2_bot"
}

contact_url = "https://t.me/Hisok88"  # ضع رابط التواصل معك

def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton(name, url=url)] for name, url in bots.items()]
    keyboard.append([InlineKeyboardButton("📩 تواصل معنا", url=contact_url)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("اختر المادة الدراسية:", reply_markup=reply_markup)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "بوت تيليجرام شغال ✅"

if __name__ == "__main__":
    from telegram.ext import Dispatcher

    updater = Updater(token=TOKEN, use_context=True)
    dispatcher: Dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))

    # لتشغيل على Heroku/Railway على المنفذ المناسب
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
