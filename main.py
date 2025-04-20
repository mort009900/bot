import os
import json
import difflib
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import pytesseract
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
from keep_alive import keep_alive
import download_all  # تحميل الصور من Drive تلقائيًا

keep_alive()
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

with open("indexed_texts.json", "r", encoding="utf-8") as f:
    indexed_data = json.load(f)

image_paths = list(indexed_data.keys())
BASE_IMAGE_DIR = "book_pages"

def find_best_matches(query, top_n=5):
    matches = []
    for img_path, content in indexed_data.items():
        score = difflib.SequenceMatcher(None, query, content).ratio()
        matches.append((img_path, score))
    matches.sort(key=lambda x: x[1], reverse=True)
    if matches and matches[0][1] >= 0.8:
        return [matches[0]]
    return [m for m in matches if m[1] >= 0.4][:top_n]

def extract_text_from_image(photo_file):
    image = Image.open(photo_file)
    return pytesseract.image_to_string(image, lang='ara+eng').strip()

def get_image_bytes(image_path):
    full_path = os.path.join(BASE_IMAGE_DIR, *image_path.split("/")[1:])
    if not os.path.exists(full_path):
        return None
    image = Image.open(full_path)
    img_io = BytesIO()
    image.save(img_io, 'JPEG')
    img_io.seek(0)
    return img_io

def navigate(current_path, direction):
    if current_path not in image_paths:
        return None
    idx = image_paths.index(current_path)
    new_idx = idx + 1 if direction == "next" else idx - 1
    if 0 <= new_idx < len(image_paths):
        return image_paths[new_idx]
    return None

async def send_image(update, context, image_path, new_msg=True, caption=None):
    img_io = get_image_bytes(image_path)
    if not img_io:
        msg = "❌ لم أتمكن من العثور على الصورة."
        if new_msg:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.message.reply_text(msg)
        return
    page_number = image_path.split("_")[-1].split(".")[0]
    keyboard = [
        [
            InlineKeyboardButton("⬅️ السابق", callback_data=f"prev|{page_number}"),
            InlineKeyboardButton("التالي ➡️", callback_data=f"next|{page_number}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if new_msg:
        await update.message.reply_photo(photo=img_io, caption=caption or f"📄 الصفحة: {image_path}", reply_markup=reply_markup)
    else:
        await update.callback_query.message.edit_media(
            media=InputMediaPhoto(media=img_io),
            reply_markup=reply_markup
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك! أرسل أي نص أو صورة من كتاب، وسأبحث لك.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    matches = find_best_matches(query)
    if matches:
        if len(matches) == 1:
            matched_img, score = matches[0]
            await send_image(update, context, matched_img, caption=f"📄 تطابق عالي! 🔍 {score*100:.2f}%")
        else:
            keyboard = [[
                InlineKeyboardButton(
                    f"📄 صفحة {img.split('_')[-1].split('.')[0]} ({score*100:.1f}%)",
                    callback_data=f"page|{img}"
                )
            ] for img, score in matches]
            await update.message.reply_text("🔍 أقرب النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ لم أجد نتيجة مناسبة.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    photo_path = await photo.download_to_drive()
    text = extract_text_from_image(photo_path)
    if not text:
        await update.message.reply_text("❌ لم أتمكن من قراءة النص من الصورة.")
        return
    matches = find_best_matches(text)
    if matches:
        if len(matches) == 1:
            matched_img, score = matches[0]
            await send_image(update, context, matched_img, caption=f"📄 تطابق عالي! 🔍 {score*100:.2f}%")
        else:
            keyboard = [[
                InlineKeyboardButton(
                    f"📄 صفحة {img.split('_')[-1].split('.')[0]} ({score*100:.1f}%)",
                    callback_data=f"page|{img}"
                )
            ] for img, score in matches]
            await update.message.reply_text("🔍 أقرب النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ لم أجد نتيجة مناسبة.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page|"):
        img = query.data.split('|')[1]
        await send_image(update, context, img, new_msg=False)
    elif query.data.startswith("prev|") or query.data.startswith("next|"):
        direction, page_num = query.data.split('|')
        matched_img = next((img for img in image_paths if img.endswith(f"page_{page_num}.jpg")), None)
        if matched_img:
            new_path = navigate(matched_img, direction)
            if new_path:
                await send_image(update, context, new_path, new_msg=False)
            else:
                await query.message.reply_text("🚫 لا توجد صفحات إضافية.")
    else:
        await query.message.reply_text("❌ خطأ في البيانات.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ البوت يعمل الآن...")
    app.run_polling()
