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
    "settings": "settings.json",
    "requests": "join_requests.json",
    "auto_msg": "auto_msg.json"
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

# --- LOG KANALGA XABAR YUBORISH ---
async def send_log(context: ContextTypes.DEFAULT_TYPE, text: str):
    settings = load_data(FILES["settings"], {})
    log_channel = settings.get("log_channel")
    if log_channel:
        try:
            await context.bot.send_message(chat_id=log_channel, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Log kanalga xabar yuborishda xatolik: {e}")

# --- ZAYAVKANI ESMATIB QOLISH (AVTO-APPROVE QILMAYDI!) ---
async def track_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        req = update.chat_join_request
        user_id = req.from_user.id
        chat_id = req.chat.id

        requests_data = load_data(FILES["requests"], {})
        user_key = str(user_id)

        if user_key not in requests_data:
            requests_data[user_key] = []
        
        if chat_id not in requests_data[user_key]:
            requests_data[user_key].append(chat_id)
            save_data(FILES["requests"], requests_data)
            
        logger.info(f"Foydalanuvchi {user_id} {chat_id} kanaliga zayavka yubordi.")
        await send_log(context, f"📥 **Yangi zayavka!**\n👤 User ID: `{user_id}`\n📢 Kanal ID: `{chat_id}`")
    except Exception as e:
        logger.error(f"Zayavkani saqlashda xatolik: {e}")

# --- OBUNANI TEKSHIRISH ---
async def check_all_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    channels = load_data(FILES["channels"], [])
    requests_data = load_data(FILES["requests"], {})
    user_requests = requests_data.get(str(user_id), [])
    
    unsubbed = []

    for ch in channels:
        try:
            chat_id = ch["chat_id"]
            if isinstance(chat_id, str) and (chat_id.startswith("-") or chat_id.isdigit()):
                chat_id = int(chat_id)

            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ["creator", "administrator", "member"]:
                continue

            if chat_id in user_requests or str(chat_id) in user_requests:
                continue

            unsubbed.append(ch)
        except Exception as e:
            logger.error(f"Kanal tekshirishda xatolik ({ch['chat_id']}): {e}")
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
        [InlineKeyboardButton("📜 Log kanal sozlash", callback_data="adm_set_log"), InlineKeyboardButton("⏰ Avto-xabar", callback_data="adm_auto_msg")],
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
        await query.message.reply_text("📢 **1-qadam:** Kanal Chat ID raqamini yoki Username'ini yuboring:", parse_mode="Markdown")

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
        await query.message.reply_text("✏️ Pastdagi tasdiqlash tugmasi matnini yuboring:")

    elif query.data == "adm_set_log":
        context.user_data["step"] = "awaiting_log_channel"
        await query.message.reply_text("📜 **Log kanalini ulash:**\n\nLoglar borib tushishi kerak bo'lgan yopiq kanalingiz ID sini yuboring (Masalan: `-1001234567890`).\n\n*(Eslatma: Bot o'sha kanalda ADMIN bo'lishi shart!)*", parse_mode="Markdown")

    elif query.data == "adm_auto_msg":
        auto_data = load_data(FILES["auto_msg"], {"status": "off", "interval": 10, "text": ""})
        st = "✅ Yoqilgan" if auto_data["status"] == "on" else "❌ O'chirilgan"
        msg = auto_data.get("text", "O'rnatilmagan")
        
        txt = f"⏰ **AVTOMATIK XABAR SOZLAMALARI**\n\n📊 Holati: **{st}**\n⏱ Interval: **Har {auto_data['interval']} soatda**\n📝 Xabar: `{msg}`"
        kb = [
            [InlineKeyboardButton("🟢 Yoqish" if auto_data["status"] == "off" else "🔴 O'chirish", callback_data="toggle_auto_msg")],
            [InlineKeyboardButton("✏️ Xabarni o'rnatish", callback_data="set_auto_msg_text")],
            [InlineKeyboardButton("⏱ Vaqt oraliqini o'zgartirish", callback_data="set_auto_msg_time")],
            [InlineKeyboardButton("🏠 Admin panel", callback_data="adm_home")]
        ]
        await query.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "toggle_auto_msg":
        auto_data = load_data(FILES["auto_msg"], {"status": "off", "interval": 10, "text": ""})
        auto_data["status"] = "on" if auto_data["status"] == "off" else "off"
        save_data(FILES["auto_msg"], auto_data)
        await query.message.reply_text(f"Avto-xabar holati o'zgartirildi: **{auto_data['status']}**")

    elif query.data == "set_auto_msg_text":
        context.user_data["step"] = "awaiting_auto_text"
        await query.message.reply_text(" Avto-xabar sifatida har intervalda barchaga yuborilishi kerak bo'lgan matnni yuboring:")

    elif query.data == "set_auto_msg_time":
        context.user_data["step"] = "awaiting_auto_time"
        await query.message.reply_text("⏱ Necha soatda bir xabar yuborilsin? Soat miqdorini raqamda yuboring (Masalan: `10`):", parse_mode="Markdown")

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
                await send_log(context, f"🎬 **Yangi kino qo'shildi!**\n🆔 Kod: `{code}`")
            except Exception as e:
                logger.error(f"Kanalga saqlashda xatolik: {e}")
                await update.message.reply_text("❌ Videoni baza kanaliga saqlashda xatolik bo'ldi.")
            return

        elif step == "awaiting_chan_chatid":
            context.user_data["temp_chan_id"] = text
            context.user_data["step"] = "awaiting_chan_title"
            await update.message.reply_text("📝 **2-qadam:** Tugmada ko'rinadigan nomni yozing:")
            return

        elif step == "awaiting_chan_title":
            context.user_data["temp_chan_title"] = text
            context.user_data["step"] = "awaiting_chan_url"
            await update.message.reply_text("🔗 **3-qadam:** Kanal havolasini yuboring:")
            return

        elif step == "awaiting_chan_url":
            cid = context.user_data.pop("temp_chan_id")
            title = context.user_data.pop("temp_chan_title")
            url = text
            context.user_data.pop("step", None)

            try:
                cid_val = int(cid) if str(cid).startswith("-") else cid
            except ValueError:
                cid_val = cid

            channels = load_data(FILES["channels"], [])
            channels.append({"chat_id": cid_val, "title": title, "url": url})
            save_data(FILES["channels"], channels)

            await update.message.reply_text(f"✅ Kanal qo'shildi!\n📌 **Nomi:** {title}\n🆔 **ID:** `{cid_val}`", parse_mode="Markdown")
            return

        elif step == "awaiting_log_channel":
            context.user_data.pop("step", None)
            try:
                log_id = int(text)
                settings = load_data(FILES["settings"], {})
                settings["log_channel"] = log_id
                save_data(FILES["settings"], settings)
                await update.message.reply_text(f"✅ Log kanali o'rnatildi: `{log_id}`", parse_mode="Markdown")
            except ValueError:
                await update.message.reply_text("To'g'ri Kanal ID raqamini kiriting (Masalan: `-1001234567890`)!")
            return

        elif step == "awaiting_auto_text":
            context.user_data.pop("step", None)
            auto_data = load_data(FILES["auto_msg"], {})
            auto_data["text"] = text
            save_data(FILES["auto_msg"], auto_data)
            await update.message.reply_text("✅ Avto-xabar matni saqlandi!")
            return

        elif step == "awaiting_auto_time":
            context.user_data.pop("step", None)
            try:
                hours = float(text)
                auto_data = load_data(FILES["auto_msg"], {})
                auto_data["interval"] = hours
                save_data(FILES["auto_msg"], auto_data)
                await update.message.reply_text(f"✅ Avto-xabar vaqti {hours} soatga o'zgartirildi!")
            except ValueError:
                await update.message.reply_text("Raqam kiritishingiz kerak!")
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
            save_data(FILES["channels"], new_channels)
            await update.message.reply_text(f"🗑 Kanal o'chirildi: {text}")
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
            
            await send_log(context, f"👁 **Kino ko'rildi!**\n👤 User: `{user_id}`\n🎬 Kod: `{code}`")
        except Exception as e:
            logger.error(f"Kino yuborishda xatolik: {e}")
            await update.message.reply_text("❌ Kinoni yuklashda xatolik yuz berdi.")
    else:
        await update.message.reply_text("❌ Bunday kodli kino topilmadi.")

# --- AVTO-XABAR TIZIMI (BACKGROUND TASK) ---
async def auto_message_loop(app):
    while True:
        try:
            auto_data = load_data(FILES["auto_msg"], {"status": "off", "interval": 10, "text": ""})
            if auto_data.get("status") == "on" and auto_data.get("text"):
                users = load_data(FILES["users"], [])
                for uid in users:
                    try:
                        await app.bot.send_message(chat_id=uid, text=auto_data["text"], parse_mode="Markdown")
                        await asyncio.sleep(0.05)
                    except Exception:
                        pass
            interval_seconds = float(auto_data.get("interval", 10)) * 3600
            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Avto-xabar siklida xatolik: {e}")
            await asyncio.sleep(3600)

# --- MAIN ---
def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(ChatJoinRequestHandler(track_join_request))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u, c: send_admin_panel(u.message, u.effective_user.id)))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Avto xabarni ishga tushirish
    loop = asyncio.get_event_loop()
    loop.create_task(auto_message_loop(app))

    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
