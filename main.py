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
from keep_alive import keep_alive  # ← ملف السيرفر الصغير

# ✅ شغّل السيرفر أولًا (هذا يبقي Replit شغال)
keep_alive()

# تحميل التوكن من env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# تحميل الفهرسة
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
    filtered = [(p, s) for p, s in matches if s >= 0.4]
    return filtered[:top_n]

def extract_text_from_image(photo_file):
    image = Image.open(photo_file)
    text = pytesseract.image_to_string(image, lang='ara+eng')
    return text.strip()

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
        error_msg = "❌ لم أتمكن من العثور على الاجابة."
        if new_msg:
            await update.message.reply_text(error_msg)
        else:
            await update.callback_query.message.reply_text(error_msg)
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
    await update.message.reply_text("👋 مرحبًا بك في بوت البحث داخل الكتب!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    matches = find_best_matches(query)
    if matches:
        if len(matches) == 1:
            matched_img, score = matches[0]
            await send_image(update, context, matched_img, caption=f"📄 تم العثور على تطابق قوي!\n🔍 التشابه: {score*100:.2f}%")
        else:
            keyboard = []
            for matched_img, score in matches:
                page_number = matched_img.split("_")[-1].split(".")[0]
                keyboard.append([
                    InlineKeyboardButton(
                        f"📄 صفحة {page_number} ({score*100:.1f}%)",
                        callback_data=f"page|{matched_img}"
                    )
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📚 هذه أقرب الصفحات:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ لم أتمكن من العثور على الاجابة.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    photo_path = await photo.download_to_drive()
    extracted_text = extract_text_from_image(photo_path)
    if not extracted_text:
        await update.message.reply_text("❌ لم أتمكن من قراءة النص.")
        return

    matches = find_best_matches(extracted_text)
    if matches:
        if len(matches) == 1:
            matched_img, score = matches[0]
            await send_image(update, context, matched_img, caption=f"📄 تم العثور على تطابق قوي!\n🔍 التشابه: {score*100:.2f}%")
        else:
            keyboard = []
            for matched_img, score in matches:
                page_number = matched_img.split("_")[-1].split(".")[0]
                keyboard.append([
                    InlineKeyboardButton(
                        f"📄 صفحة {page_number} ({score*100:.1f}%)",
                        callback_data=f"page|{matched_img}"
                    )
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📚 أقرب الصفحات:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ لم أجد نتيجة كافية.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page|"):
        matched_img = query.data.split('|')[1]
        await send_image(update, context, matched_img, new_msg=False)
    elif query.data.startswith("prev|") or query.data.startswith("next|"):
        direction, page_number = query.data.split('|')
        matched_img = next((img for img in image_paths if img.endswith(f"page_{page_number}.jpg")), None)
        if matched_img:
            new_path = navigate(matched_img, direction)
            if new_path:
                await send_image(update, context, new_path, new_msg=False)
            else:
                await query.message.reply_text("🚫 لا توجد صفحات إضافية.")
    else:
        await query.message.reply_text("❌ حدث خطأ.")

# ✅ الآن نشغّل البوت
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ البوت يعمل الآن على Replit و UptimeRobot")
    app.run_polling()
