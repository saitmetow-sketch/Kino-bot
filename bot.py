import logging
import json
import os
import asyncio
import threading
import urllib.request
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters,
)

# --- RENDER PORT DUMMY SERVER & SELF-PING ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

def keep_alive():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    while True:
        time.sleep(420)
        try:
            urllib.request.urlopen(render_url)
            logger.info("Bot o'zini-o'zi uyg'otdi.")
        except Exception as e:
            logger.error(f"Ping xatoligi: {e}")

# --- LOGGING ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- KONFIGURATSIYA ---
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
MAIN_ADMIN_ID = 7020448136
DATABASE_CHANNEL_ID = -1004290096342  # Baza kanalingiz ID si

FILES = {
    "movies": "movies.json",
    "users": "users.json",
    "channels": "channels.json",
    "admins": "admins.json",
    "settings": "settings.json"
}

# --- BAZA FUNKSIYALARI ---
def load_data(filename, default):
    if not os.path.exists(filename):
        save_data(filename, default)
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

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

# --- ZAYAVKALARNI AVTOMATIK QABUL QILISH ---
async def auto_approve_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_join_request = update.chat_join_request
        await chat_join_request.approve()
        logger.info(f"Foydalanuvchi {chat_join_request.from_user.id} zayavkasi tasdiqlandi.")
    except Exception as e:
        logger.error(f"Zayavkani tasdiqlashda xatolik: {e}")

# --- OBUNANI TEKSHIRISH ---
async def check_all_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    channels = load_data(FILES["channels"], [])
    unsubbed = []

    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                unsubbed.append(ch)
        except Exception as e:
            logger.error(f"Kanal tekshirishda xatolik ({ch}): {e}")
            unsubbed.append(ch)

    return (len(unsubbed) == 0), unsubbed

def build_sub_keyboard(unsubbed_channels: list):
    settings = load_data(FILES["settings"], {"btn_text": "✅ Tasdiqlash"})
    keyboard = []
    
    for ch in unsubbed_channels:
        keyboard.append([InlineKeyboardButton(f"{ch['title']} ↗️", url=ch["url"])])
        
    keyboard.append([InlineKeyboardButton(settings.get("btn_text", "✅ Tasdiqlash"), callback_data="check_sub")])
    return InlineKeyboardMarkup(keyboard)

# --- ADMIN MENYU TUGMALARI ---
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="adm_add_movie"), InlineKeyboardButton("🗑 Kino o'chirish", callback_data="adm_del_movie")],
        [InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="adm_list_movies")],
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="adm_add_chan"), InlineKeyboardButton("❌ Kanal o'chirish", callback_data="adm_del_chan")],
        [InlineKeyboardButton("📋 Kanallar", callback_data="adm_list_chan"), InlineKeyboardButton("✏️ Tugma matnini o'zgartirish", callback_data="adm_edit_btn")],
        [InlineKeyboardButton("📊 Statistika", callback_data="adm_stats"), InlineKeyboardButton("📨 Xabar yuborish", callback_data="adm_send")],
        [InlineKeyboardButton("👥 Admin qo'shish", callback_data="adm_add_admin"), InlineKeyboardButton("🏠 Bosh sahifa", callback_data="adm_home")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_reply_keyboard():
    keyboard = [[KeyboardButton("⚙️ Admin Panel")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    
    reply_markup_custom = get_admin_reply_keyboard() if is_admin(user_id) else None

    is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
    if is_subbed:
        await update.message.reply_text(
            "✅ Siz barcha kanallarga obuna bo'lgansiz!\n\n🔞 Kino kodini kiriting:",
            reply_markup=reply_markup_custom
        )
    else:
        await update.message.reply_text(
            "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak.",
            reply_markup=build_sub_keyboard(unsubbed)
        )

async def send_admin_panel(message, user_id):
    if not is_admin(user_id): return
    channels = load_data(FILES["channels"], [])
    text = f"⚙️ **Admin panel**\n\n📢 Kanallar soni: **{len(channels)}** ta"
    await message.reply_text(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

# --- CALLBACKS ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "check_sub":
        is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
        reply_markup_custom = get_admin_reply_keyboard() if is_admin(user_id) else None
        if is_subbed:
            await query.message.edit_text("✅ Siz barcha kanallarga obuna bo'ldingiz!\n\n🔞 Kino kodini kiriting:")
            if reply_markup_custom:
                await query.message.reply_text("⚙️ Admin boshqaruvi yoqilgan.", reply_markup=reply_markup_custom)
        else:
            await query.message.reply_text(
                "❌ Kechirasiz, siz hali barcha kanallarga a'zo bo'lmadingiz!",
                reply_markup=build_sub_keyboard(unsubbed)
            )
        return

    if not is_admin(user_id): return

    if query.data == "adm_home":
        channels = load_data(FILES["channels"], [])
        await query.message.edit_text(f"⚙️ **Admin panel**\n\n📢 Kanallar soni: **{len(channels)}** ta", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    elif query.data == "adm_add_movie":
        context.user_data["step"] = "awaiting_movie_code"
        await query.message.reply_text("🎬 Qo'shmoqchi bo'lgan kino kodini kiriting (Masalan: `101`):", parse_mode="Markdown")

    elif query.data == "adm_del_movie":
        context.user_data["step"] = "awaiting_del_movie_code"
        await query.message.reply_text("🗑 O'chirmoqchi bo'lgan kino kodini kiriting (Masalan: `101`):", parse_mode="Markdown")

    elif query.data == "adm_list_movies":
        movies = load_data(FILES["movies"], {})
        if not movies:
            txt = "📜 Hali hech qanday kino qo'shilmagan."
        else:
            txt = f"🎬 **Mavjud kinolar ro'yxati** (Jami: **{len(movies)}** ta):\n\n"
            for code, data in movies.items():
                views = data.get("views", 0)
                txt += f"• **Kodi:** `{code}` | 👁 **Ko'rilgan:** {views} marta\n"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "adm_add_chan":
        context.user_data["step"] = "awaiting_chan_chatid"
        await query.message.reply_text(
            "📢 **1-qadam:** Kanal Chat ID raqamini yoki Username'ini yuboring:\n\n"
            "• Ochiq kanal bo'lsa: `@kanal_username`\n"
            "• Yopiq (zayavka) kanal bo'lsa ID raqami: `-100123456789`\n\n"
            "*(Eslatma: Bot ushbu kanalda ADMIN bo'lishi va foydalanuvchilarni qo'shish huquqi berilgan bo'lishi shart!)*", parse_mode="Markdown"
        )

    elif query.data == "adm_del_chan":
        context.user_data["step"] = "awaiting_channel_del"
        await query.message.reply_text("❌ O'chirmoqchi bo'lgan kanal Chat ID yoki Username'ini yuboring:")

    elif query.data == "adm_list_chan":
        channels = load_data(FILES["channels"], [])
        if not channels:
            txt = "Hali kanallar qo'shilmagan."
        else:
            txt = "📢 **Majburiy kanallar:**\n\n"
            for c in channels:
                txt += f"• **Nomi:** {c['title']}\n  **ID:** `{c['chat_id']}`\n  **Link:** {c['url']}\n\n"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "adm_edit_btn":
        context.user_data["step"] = "awaiting_btn_text"
        await query.message.reply_text("✏️ Pastdagi tasdiqlash tugmasi matnini yuboring (Masalan: `✅ Tekshirish`):")

    elif query.data == "adm_stats":
        users = load_data(FILES["users"], [])
        movies = load_data(FILES["movies"], {})
        views = sum(m.get("views", 0) for m in movies.values())
        txt = f"📊 **Statistika:**\n\n👤 Foydalanuvchilar: **{len(users)}** ta\n🎬 Kinolar: **{len(movies)}** ta\n👁 Ko'rishlar: **{views}** marta"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "adm_send":
        context.user_data["step"] = "awaiting_broadcast"
        await query.message.reply_text("📨 Barcha obunachilarga yubormoqchi bo'lgan xabaringizni yuboring:")

    elif query.data == "adm_add_admin":
        if user_id != MAIN_ADMIN_ID:
            await query.message.reply_text("Faqat Asosiy Admin yangi admin qo'sha oladi!")
            return
        context.user_data["step"] = "awaiting_admin_id"
        await query.message.reply_text("👥 Yangi adminning Telegram ID raqamini yuboring:")

# --- TEXT/MEDIA MESSAGES ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    text = update.message.text.strip() if update.message.text else ""

    if is_admin(user_id) and text == "⚙️ Admin Panel":
        await send_admin_panel(update.message, user_id)
        return

    step = context.user_data.get("step")

    if is_admin(user_id) and step:
        if step == "awaiting_movie_code":
            context.user_data["temp_movie_code"] = text
            context.user_data["step"] = "awaiting_movie_file"
            await update.message.reply_text("Endi shu kod uchun kino video faylini yuboring:")
            return

        elif step == "awaiting_movie_file":
            code = context.user_data.pop("temp_movie_code", None)
            context.user_data.pop("step", None)
            movies = load_data(FILES["movies"], {})

            try:
                forwarded_msg = await update.message.forward(chat_id=DATABASE_CHANNEL_ID)
                msg_id = forwarded_msg.message_id

                movies[code] = {
                    "msg_id": msg_id,
                    "caption": update.message.caption or "",
                    "views": 0
                }
                save_data(FILES["movies"], movies)
                await update.message.reply_text(f"✅ `{code}` kodli kino muvaffaqiyatli saqlandi!", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Kanalga saqlashda xatolik: {e}")
                await update.message.reply_text("❌ Videoni baza kanaliga saqlashda xatolik bo'ldi.")
            return

        elif step == "awaiting_chan_chatid":
            context.user_data["temp_chan_id"] = text
            context.user_data["step"] = "awaiting_chan_title"
            await update.message.reply_text("📝 **2-qadam:** Tugmada ko'rinadigan nomni yozing (Masalan: `1 - kanal`):", parse_mode="Markdown")
            return

        elif step == "awaiting_chan_title":
            context.user_data["temp_chan_title"] = text
            context.user_data["step"] = "awaiting_chan_url"
            await update.message.reply_text("🔗 **3-qadam:** Kanal havolasini yuboring:", parse_mode="Markdown")
            return

        elif step == "awaiting_chan_url":
            cid = context.user_data.pop("temp_chan_id")
            title = context.user_data.pop("temp_chan_title")
            url = text
            context.user_data.pop("step", None)

            try:
                cid_val = int(cid) if cid.startswith("-") else cid
            except ValueError:
                cid_val = cid

            channels = load_data(FILES["channels"], [])
            channels.append({"chat_id": cid_val, "title": title, "url": url})
            save_data(FILES["channels"], channels)

            await update.message.reply_text(f"✅ Kanal qo'shildi!\n📌 **Nomi:** {title}\n🆔 **ID:** `{cid_val}`", parse_mode="Markdown")
            return

        elif step == "awaiting_btn_text":
            context.user_data.pop("step", None)
            settings = load_data(FILES["settings"], {})
            settings["btn_text"] = text
            save_data(FILES["settings"], settings)
            await update.message.reply_text(f"✅ Tasdiqlash tugmasi matni `{text}` ga o'zgartirildi!", parse_mode="Markdown")
            return

        elif step == "awaiting_channel_del":
            context.user_data.pop("step", None)
            channels = load_data(FILES["channels"], [])
            new_channels = [c for c in channels if str(c["chat_id"]) != text and str(c.get("url")) != text]
            
            if len(new_channels) < len(channels):
                save_data(FILES["channels"], new_channels)
                await update.message.reply_text(f"🗑 Kanal o'chirildi: {text}")
            else:
                await update.message.reply_text("❌ Bunday kanal topilmadi.")
            return

        elif step == "awaiting_del_movie_code":
            context.user_data.pop("step", None)
            movies = load_data(FILES["movies"], {})
            if text in movies:
                del movies[text]
                save_data(FILES["movies"], movies)
                await update.message.reply_text(f"🗑 `{text}` kodli kino o'chirildi!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Kiritilgan kod bo'yicha kino topilmadi.")
            return

        elif step == "awaiting_admin_id":
            context.user_data.pop("step", None)
            try:
                aid = int(text)
                admins = load_data(FILES["admins"], [])
                if aid not in admins:
                    admins.append(aid)
                    save_data(FILES["admins"], admins)
                    await update.message.reply_text(f"✅ Yangi admin qo'shildi: `{aid}`", parse_mode="Markdown")
            except ValueError:
                await update.message.reply_text("Raqamli Telegram ID kiriting!")
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

    is_subbed, unsubbed = await check_all_subscriptions(user_id, context)
    if not is_subbed:
        await update.message.reply_text(
            "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak.",
            reply_markup=build_sub_keyboard(unsubbed)
        )
        return

    code = text
    movies = load_data(FILES["movies"], {})

    if code in movies:
        m = movies[code]
        m["views"] = m.get("views", 0) + 1
        save_data(FILES["movies"], movies)

        try:
            if "msg_id" in m:
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=DATABASE_CHANNEL_ID,
                    message_id=m["msg_id"],
                    protect_content=True
                )
            elif "file_id" in m:
                await update.message.reply_video(video=m["file_id"], caption=m.get("caption", ""), protect_content=True)
        except Exception as e:
            logger.error(f"Kino yuborishda xatolik: {e}")
            await update.message.reply_text("❌ Kinoni yuklashda xatolik yuz berdi.")
    else:
        await update.message.reply_text("❌ Bunday kodli kino topilmadi.")

# --- MAIN ---
def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(ChatJoinRequestHandler(auto_approve_join_request))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u, c: send_admin_panel(u.message, u.effective_user.id)))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
