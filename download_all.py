import os
import gdown

FOLDER_ID = "1EqZtec2tPkXkkqHx8hIkRYcHpP1l99iD"  # هذا هو ID مجلدك من الرابط

OUTPUT_DIR = "book_pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# تحميل جميع الملفات من المجلد
gdown.download_folder(
    id=FOLDER_ID,
    output=OUTPUT_DIR,
    quiet=False,
    use_cookies=False
)

print("✅ تم تحميل جميع الصور من Google Drive")
