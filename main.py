import os
import json
import difflib
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import pytesseract
import zipfile
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
from keep_alive import keep_alive  # ← ملف السيرفر الصغير

# ✅ تحميل وفك الصور من Google Drive
def download_and_extract_zip_from_gdrive(file_id, output_dir="book_pages"):
    if os.path.exists(output_dir):
        print(f"✅ المجلد {output_dir} موجود مسبقًا")
        return

    print("⬇️ جاري تحميل ملف الصور...")
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)

    zip_path = "book_pages.zip"
    with open(zip_path, "wb") as f:
        f.write(response.content)

    print("📦 جاري فك الضغط...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)

    os.remove(zip_path)
    print(f"✅ تم التحميل والفك إلى: {output_dir}")

# 🟢 شغّل السيرفر
keep_alive()

# 🟢 تحميل التوكن
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# 🟢 تحميل الصور
download_and_extract_zip_from_gdrive("1nd9GKibJ58H4D7dN1AMCCE-GtcysQYgr")  # ← ID الخاص بك

# 🟢 تحميل الفهرسة
with open("indexed_texts.json", "r", encoding="utf-8") as f:
    indexed_data = json.load(f)

image_paths = list(indexed_data.keys())
BASE_IMAGE_DIR = "book_pages"

# 🔍 البحث
def find_best_matches(query, top_n=5):
    matches = []
    for img_path, content in indexed_data.items():
        score = difflib.SequenceMatcher(None, query, content).ratio()
        matches.append((img_path, score))
    matches.sort(key=lambda x: x[1], reverse=True)
    if matches and matches[0][1] >= 0.8:
        return [matches[0]]
    return [m for m in matches if m[1] >= 0.4][:top_n]

# 🧠 تحليل صورة
def extract_text_from_image(photo_file):
    image = Image.open(photo_file)
    text = pytesseract.image_to_string(image, lang='ara+eng')
    return text.strip()

# 🖼️ تحميل صورة
def get_image_bytes(image_path):
    full_path = os.path.join(BASE_IMAGE_DIR, *image_path.split("/")[1:])
    if not os.path.exists(full_path):
        return None
    image = Image.open(full_path)
    img_io = BytesIO()
    image.save(img_io, 'JPEG')
    img_io.seek(0)
    return img_io

# 🔄 التنقل
def navigate(current_path, direction):
    if current_path not in image_paths:
        return None
    idx = image_paths.index(current_path)
    new_idx = idx + 1 if direction == "next" else idx - 1
    if 0 <= new_idx < len(image_paths):
        return image_paths[new_idx]
    return None

# 📩 إرسال صورة
async def send_image(update, context, image_path, new_msg=True, caption=None):
    img_io = get_image_bytes(image_path)
    if not img_io:
        msg = "❌ لم أتمكن من العثور على الصورة المطلوبة."
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

# ⚙️ أوامر البوت
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 مرحبًا بك! أرسل سؤالًا أو صورة نصية للبحث داخل الكتب.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    matches = find_best_matches(query)
    if matches:
        if len(matches) == 1:
            img, score = matches[0]
            await send_image(update, context, img, caption=f"✅ تطابق قوي: {score*100:.1f}%")
        else:
            keyboard = [
                [InlineKeyboardButton(f"📄 صفحة {m[0].split('_')[-1].split('.')[0]} ({m[1]*100:.1f}%)", callback_data=f"page|{m[0]}")]
                for m in matches
            ]
            await update.message.reply_text("📚 أقرب النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ لم أجد نتائج قريبة.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    path = await photo.download_to_drive()
    text = extract_text_from_image(path)
    if not text:
        await update.message.reply_text("📸 لم أستطع استخراج نص من الصورة.")
        return
    matches = find_best_matches(text)
    if matches:
        if len(matches) == 1:
            img, score = matches[0]
            await send_image(update, context, img, caption=f"✅ تطابق قوي: {score*100:.1f}%")
        else:
            keyboard = [
                [InlineKeyboardButton(f"📄 صفحة {m[0].split('_')[-1].split('.')[0]} ({m[1]*100:.1f}%)", callback_data=f"page|{m[0]}")]
                for m in matches
            ]
            await update.message.reply_text("📚 أقرب النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ لم أجد نتائج من الصورة.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("page|"):
        await send_image(update, context, data.split("|")[1], new_msg=False)
    elif data.startswith("prev|") or data.startswith("next|"):
        direction, number = data.split("|")
        match = next((img for img in image_paths if img.endswith(f"page_{number}.jpg")), None)
        if match:
            new_path = navigate(match, direction)
            if new_path:
                await send_image(update, context, new_path, new_msg=False)
            else:
                await query.message.reply_text("🚫 لا توجد صفحات إضافية.")
    else:
        await query.message.reply_text("⚠️ خطأ في التعامل مع الزر.")

# 🟢 شغل البوت
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ البوت يعمل الآن...")
    app.run_polling()
