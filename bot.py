    import logging
import json
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- KONFIGURATSIYA ---
TOKEN = "YOUR_BOT_TOKEN_HERE"  # BotFather tokeningiz
MAIN_ADMIN_ID = 7020448136

FILES = {
    "movies": "movies.json",
    "users": "users.json",
    "channels": "channels.json",
    "admins": "admins.json"
}

# --- BAZA FUNKSIYALARI ---
def load_data(filename, default):
    if not os.path.exists(filename):
        return default
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(user_id: int) -> bool:
    if user_id == MAIN_ADMIN_ID:
        return True
    admins = load_data(FILES["admins"], [])
    return user_id in admins

def register_user(user_id: int):
    users = load_data(FILES["users"], [])
    if user_id not in users:
        users.append(user_id)
        save_data(FILES["users"], users)

# --- OBUNA TEKSHIRISH ---
async def check_all_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    channels = load_data(FILES["channels"], ["@kanal98766"])
    unsubbed = []
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                unsubbed.append(channel)
        except Exception:
            unsubbed.append(channel)
    return (len(unsubbed) == 0), unsubbed

def build_sub_keyboard(unsubbed_channels: list):
    keyboard = []
    for ch in unsubbed_channels:
        clean_ch = ch.replace("@", "")
        keyboard.append([InlineKeyboardButton(f"📢 {ch} ga a'zo bo'lish", url=f"https://t.me/{clean_ch}")])
    keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(keyboard)

# --- ADMIN MENYU TUGMALARI ---
def get_admin_keyboard():
    channels = load_data(FILES["channels"], [])
    keyboard = [
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="adm_add_movie"), InlineKeyboardButton("🗑 Kino o'chirish", callback_data="adm_del_movie")],
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="adm_add_chan"), InlineKeyboardButton("❌ Kanal o'chirish", callback_data="adm_del_chan")],
        [InlineKeyboardButton("📋 Kanallar", callback_data="adm_list_chan"), InlineKeyboardButton("📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton("📨 Xabar yuborish", callback_data="adm_send"), InlineKeyboardButton("👥 Admin qo'shish", callback_data="adm_add_admin")],
        [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="adm_home")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START & ADMIN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
    if is_subbed:
        await update.message.reply_text("✅ Hamma kanalga obuna bo'ldingiz! Kino kodini kiriting:")
    else:
        await update.message.reply_text("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=build_sub_keyboard(unsubbed))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    channels = load_data(FILES["channels"], [])
    text = (
        "⚙️ **Admin panel**\n\n"
        f"📣 Majburiy kanallar soni: **{len(channels)}** ta\n"
        "Boshqarish uchun quyidagi tugmalardan birini tanlang:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

# --- CALLBACK HANDLER (TUGMALAR ISHLOVI) ---
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "check_sub":
        is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
        if is_subbed:
            await query.message.edit_text("✅ Hamma kanalga obuna bo'ldingiz! Kino kodini kiriting:")
        else:
            await query.message.reply_text("Siz hali barcha kanallarga obuna bo'lmadingiz!", reply_markup=build_sub_keyboard(unsubbed))
        return

    if not is_admin(user_id): return

    if query.data == "adm_home":
        channels = load_data(FILES["channels"], [])
        await query.message.edit_text(f"⚙️ **Admin panel**\n\n📣 Majburiy kanallar soni: **{len(channels)}** ta", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    elif query.data == "adm_add_movie":
        context.user_data["step"] = "awaiting_movie_code"
        await query.message.reply_text("🎬 Qo'shmoqchi bo'lgan kino kodini yozing (Masalan: `101`):", parse_mode="Markdown")

    elif query.data == "adm_del_movie":
        context.user_data["step"] = "awaiting_del_movie_code"
        await query.message.reply_text("🗑 O'chirmoqchi bo'lgan kino kodini yozing (Masalan: `101`):", parse_mode="Markdown")

    elif query.data == "adm_add_chan":
        context.user_data["step"] = "awaiting_channel_add"
        await query.message.reply_text("📢 Qo'shmoqchi bo'lgan kanal usernamelerini yuboring (Masalan: `@kanal98766`):")

    elif query.data == "adm_del_chan":
        context.user_data["step"] = "awaiting_channel_del"
        await query.message.reply_text("❌ O'chirmoqchi bo'lgan kanal usernamesini yuboring (Masalan: `@kanal98766`):")

    elif query.data == "adm_list_chan":
        channels = load_data(FILES["channels"], [])
        txt = "📢 **Majburiy kanallar:**\n\n" + "\n".join(channels) if channels else "Hali kanallar yo'q."
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "adm_stats":
        users = load_data(FILES["users"], [])
        movies = load_data(FILES["movies"], {})
        views = sum(m.get("views", 0) for m in movies.values())
        txt = f"📊 **Statistika:**\n\n👤 Foydalanuvchilar: **{len(users)}** ta\n🎬 Kinolar: **{len(movies)}** ta\n👁 Ko'rishlar: **{views}** marta"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "adm_send":
        context.user_data["step"] = "awaiting_broadcast"
        await query.message.reply_text("📨 Barcha obunachilarga yubormoqchi bo'lgan xabar/reklamangizni yuboring:")

    elif query.data == "adm_add_admin":
        if user_id != MAIN_ADMIN_ID:
            await query.message.reply_text("Faqat Asosiy Admin yangi admin qo'sha oladi!")
            return
        context.user_data["step"] = "awaiting_admin_id"
        await query.message.reply_text("👥 Yangi adminning Telegram ID raqamini yuboring:")

# --- TEXT/MEDIA HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    step = context.user_data.get("step")

    # ADMIN QADAMLARI
    if is_admin(user_id) and step:
        if step == "awaiting_movie_code":
            context.user_data["temp_movie_code"] = update.message.text.strip()
            context.user_data["step"] = "awaiting_movie_file"
            await update.message.reply_text("Endi shu kod uchun kino faylini (video) yuboring:")
            return

        elif step == "awaiting_movie_file":
            code = context.user_data.pop("temp_movie_code", None)
            context.user_data.pop("step", None)
            movies = load_data(FILES["movies"], {})

            if update.message.video:
                movies[code] = {"type": "video", "file_id": update.message.video.file_id, "caption": update.message.caption or "", "views": 0}
            elif update.message.document:
                movies[code] = {"type": "document", "file_id": update.message.document.file_id, "caption": update.message.caption or "", "views": 0}
            else:
                movies[code] = {"type": "text", "text": update.message.text, "views": 0}

            save_data(FILES["movies"], movies)
            await update.message.reply_text(f"✅ `{code}` kodli kino saqlandi!", parse_mode="Markdown")
            return

        elif step == "awaiting_del_movie_code":
            context.user_data.pop("step", None)
            code = update.message.text.strip()
            movies = load_data(FILES["movies"], {})
            if code in movies:
                del movies[code]
                save_data(FILES["movies"], movies)
                await update.message.reply_text(f"🗑 `{code}` kodli kino o'chirildi!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Kiritilgan kod bo'yicha kino topilmadi.")
            return

        elif step == "awaiting_channel_add":
            context.user_data.pop("step", None)
            ch = update.message.text.strip()
            channels = load_data(FILES["channels"], [])
            if ch not in channels:
                channels.append(ch)
                save_data(FILES["channels"], channels)
                await update.message.reply_text(f"✅ Kanal qo'shildi: {ch}")
            else:
                await update.message.reply_text("Ushbu kanal ro'yxatda bor.")
            return

        elif step == "awaiting_channel_del":
            context.user_data.pop("step", None)
            ch = update.message.text.strip()
            channels = load_data(FILES["channels"], [])
            if ch in channels:
                channels.remove(ch)
                save_data(FILES["channels"], channels)
                await update.message.reply_text(f"🗑 Kanal o'chirildi: {ch}")
            else:
                await update.message.reply_text("Kanal topilmadi.")
            return

        elif step == "awaiting_admin_id":
            context.user_data.pop("step", None)
            try:
                aid = int(update.message.text.strip())
                admins = load_data(FILES["admins"], [])
                if aid not in admins:
                    admins.append(aid)
                    save_data(FILES["admins"], admins)
                    await update.message.reply_text(f"✅ Yangi admin qo'shildi: `{aid}`", parse_mode="Markdown")
            except ValueError:
                await update.message.reply_text("Raqamlardan iborat ID kiriting!")
            return

        elif step == "awaiting_broadcast":
            context.user_data.pop("step", None)
            users = load_data(FILES["users"], [])
            count = 0
            for uid in users:
                try:
                    await update.message.copy(chat_id=uid)
                    count += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
            await update.message.reply_text(f"✅ Post {count} ta foydalanuvchiga yuborildi!")
            return

    # FOYDALANUVCHILAR UCHUN (Kino izlash)
    is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
    if not is_subbed:
        await update.message.reply_text("Avval barcha kanallarga obuna bo'ling!", reply_markup=build_sub_keyboard(unsubbed))
        return

    code = update.message.text.strip()
    movies = load_data(FILES["movies"], {})

    if code in movies:
        m = movies[code]
        m["views"] = m.get("views", 0) + 1
        save_data(FILES["movies"], movies)

        if m["type"] == "video":
            await update.message.reply_video(video=m["file_id"], caption=m.get("caption", ""), protect_content=True)
        elif m["type"] == "document":
            await update.message.reply_document(document=m["file_id"], caption=m.get("caption", ""), protect_content=True)
        elif m["type"] == "text":
            await update.message.reply_text(text=m["text"])
    else:
        await update.message.reply_text("❌ Bunday kodli kino topilmadi.")

# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Render uchun portni band qilib turuvchi soxta server
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# Botni ishga tushirish qismi (agarda sizda if __name__ == '__main__': bo'lsa o'sha yerga qo'shing)
if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    main()  # yoki botni yurgazadigan funksiyangiz nomi (masalan: app.run_polling())
