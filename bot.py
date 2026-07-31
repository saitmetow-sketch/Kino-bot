import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 7020448136
DEFAULT_CHANNEL = "@kanal98766"

db = sqlite3.connect("kino_bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)")
cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
)
""")

cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (OWNER_ID,))
cur.execute("INSERT OR IGNORE INTO channels VALUES (?)", (DEFAULT_CHANNEL,))
db.commit()


def is_admin(user_id):
    cur.execute(
        "SELECT 1 FROM admins WHERE user_id=?",
        (user_id,)
    )
    return cur.fetchone() is not None


def is_owner(user_id):
    return user_id == OWNER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (user_id,)
    )
    db.commit()

    await show_subscription(update, context)


async def show_subscription(update, context):
    cur.execute("SELECT username FROM channels")
    channels = cur.fetchall()

    buttons = []

    for (channel,) in channels:
        buttons.append([
            InlineKeyboardButton(
                f"📢 {channel}",
                url=f"https://t.me/{channel.lstrip('@')}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        )
    ])

    text = (
        "👋 Assalomu alaykum!\n\n"
        "🎬 Kino botdan foydalanish uchun "
        "quyidagi kanallarga obuna bo'ling.\n\n"
        "Obuna bo'lgach, "
        "«✅ Tekshirish» tugmasini bosing."
    )

    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=markup
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=markup
        )


async def check_sub(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    cur.execute("SELECT username FROM channels")
    channels = cur.fetchall()

    for (channel,) in channels:
        try:
            member = await context.bot.get_chat_member(
                channel,
                user_id
            )

            if member.status in ("left", "kicked"):
                await query.answer(
                    "❌ Hali barcha kanallarga obuna bo'lmagansiz!",
                    show_alert=True
                )
                return

        except Exception:
            await query.answer(
                f"⚠️ {channel} kanalini tekshirib bo'lmadi.",
                show_alert=True
            )
            return

    await query.edit_message_text(
        "✅ Hamma kanalga obuna bo'ldingiz!\n\n"
        "🔢 Kino kodini kiriting.\n"
        "Masalan: 12"
    )


async def admin(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ Siz admin emassiz."
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                "🎬 Kino boshqaruvi",
                callback_data="movies"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Kanal boshqaruvi",
                callback_data="channels"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Admin boshqaruvi",
                callback_data="admins"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="stats"
            )
        ],
        [
            InlineKeyboardButton(
                "📣 Reklama",
                callback_data="broadcast"
            )
        ]
    ]

    await update.message.reply_text(
        "👑 ADMIN PANEL",
        reply_markup=InlineKeyboardMarkup(buttons)
)async def callbacks(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        await check_sub(update, context)
        return

    if not is_admin(user_id):
        await query.answer(
            "❌ Siz admin emassiz!",
            show_alert=True
        )
        return

    if data == "movies":
        buttons = [
            [InlineKeyboardButton(
                "➕ Kino qo'shish",
                callback_data="add_movie"
            )],
            [InlineKeyboardButton(
                "🗑 Kino o'chirish",
                callback_data="delete_movie"
            )],
            [InlineKeyboardButton(
                "📋 Kinolar ro'yxati",
                callback_data="movie_list"
            )],
            [InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back"
            )]
        ]

        await query.edit_message_text(
            "🎬 KINO BOSHQARUVI",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "add_movie":
        context.user_data["action"] = "movie_code"

        await query.edit_message_text(
            "➕ Kino kodini yuboring.\n\n"
            "Masalan: 12"
        )

    elif data == "delete_movie":
        context.user_data["action"] = "delete_movie"

        await query.edit_message_text(
            "🗑 O'chiriladigan kino kodini yuboring."
        )

    elif data == "movie_list":
        cur.execute(
            "SELECT code FROM movies ORDER BY code"
        )

        movies = cur.fetchall()

        if movies:
            text = "📋 KINOLAR:\n\n"

            for movie in movies:
                text += f"🎬 Kod: {movie[0]}\n"
        else:
            text = "❌ Hozircha kinolar yo'q."

        await query.edit_message_text(text)

    elif data == "channels":
        buttons = [
            [InlineKeyboardButton(
                "➕ Kanal qo'shish",
                callback_data="add_channel"
            )],
            [InlineKeyboardButton(
                "🗑 Kanal o'chirish",
                callback_data="delete_channel"
            )],
            [InlineKeyboardButton(
                "📋 Kanallar ro'yxati",
                callback_data="channel_list"
            )],
            [InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back"
            )]
        ]

        await query.edit_message_text(
            "📢 KANAL BOSHQARUVI",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "add_channel":
        context.user_data["action"] = "add_channel"

        await query.edit_message_text(
            "➕ Kanal username'ini yuboring.\n\n"
            "Masalan: @kanal"
        )

    elif data == "delete_channel":
        context.user_data["action"] = "delete_channel"

        await query.edit_message_text(
            "🗑 O'chiriladigan kanal username'ini yuboring."
        )

    elif data == "channel_list":
        cur.execute(
            "SELECT username FROM channels"
        )

        channels = cur.fetchall()

        text = "📢 KANALLAR:\n\n"

        for channel in channels:
            text += f"📢 {channel[0]}\n"

        await query.edit_message_text(text)

    elif data == "admins":

        if not is_owner(user_id):
            await query.answer(
                "❌ Faqat bosh admin bu bo'limga kira oladi!",
                show_alert=True
            )
            return

        buttons = [
            [InlineKeyboardButton(
                "➕ Admin qo'shish",
                callback_data="add_admin"
            )],
            [InlineKeyboardButton(
                "🗑 Admin o'chirish",
                callback_data="delete_admin"
            )],
            [InlineKeyboardButton(
                "📋 Adminlar",
                callback_data="admin_list"
            )],
            [InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back"
            )]
        ]

        await query.edit_message_text(
            "👥 ADMIN BOSHQARUVI",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "add_admin":

        if not is_owner(user_id):
            return

        context.user_data["action"] = "add_admin"

        await query.edit_message_text(
            "➕ Yangi adminning Telegram ID raqamini yuboring."
        )

    elif data == "delete_admin":

        if not is_owner(user_id):
            return

        context.user_data["action"] = "delete_admin"

        await query.edit_message_text(
            "🗑 O'chiriladigan admin ID raqamini yuboring."
        )

    elif data == "admin_list":

        cur.execute(
            "SELECT user_id FROM admins"
        )

        admins = cur.fetchall()

        text = "👥 ADMINLAR:\n\n"

        for admin_id in admins:
            if admin_id[0] == OWNER_ID:
                text += f"👑 {admin_id[0]} — Bosh admin\n"
            else:
                text += f"👤 {admin_id[0]} — Admin\n"

        await query.edit_message_text(text)

    elif data == "stats":

        cur.execute(
            "SELECT COUNT(*) FROM users"
        )
        users = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM movies"
        )
        movies = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM channels"
        )
        channels = cur.fetchone()[0]

        await query.edit_message_text(
            f"📊 STATISTIKA\n\n"
            f"👤 Foydalanuvchilar: {users}\n"
            f"🎬 Kinolar: {movies}\n"
            f"📢 Kanallar: {channels}"
        )

    elif data == "broadcast":

        context.user_data["action"] = "broadcast"

        await query.edit_message_text(
            "📣 Reklama uchunasync def receive_video(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    action = context.user_data.get("action")

    if action != "waiting_video":
        return

    code = context.user_data.get("movie_code")

    if not code:
        await update.message.reply_text(
            "❌ Kino kodi topilmadi."
        )
        return

    file_id = update.message.video.file_id

    cur.execute(
        "INSERT OR REPLACE INTO movies (code, file_id) VALUES (?, ?)",
        (code, file_id)
    )

    db.commit()

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ Kino muvaffaqiyatli saqlandi!\n\n"
        f"🔢 Kino kodi: {code}"
    )


async def text_handler(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    action = context.user_data.get("action")

    # =========================
    # KINO QO'SHISH
    # =========================

    if is_admin(user_id) and action == "movie_code":

        context.user_data["movie_code"] = text
        context.user_data["action"] = "waiting_video"

        await update.message.reply_text(
            f"🔢 Kod: {text}\n\n"
            "🎬 Endi shu kino uchun to'liq videoni yuboring."
        )

        return


    # =========================
    # KINO O'CHIRISH
    # =========================

    if is_admin(user_id) and action == "delete_movie":

        cur.execute(
            "DELETE FROM movies WHERE code=?",
            (text,)
        )

        db.commit()

        if cur.rowcount > 0:
            await update.message.reply_text(
                f"✅ {text} kodli kino o'chirildi."
            )
        else:
            await update.message.reply_text(
                "❌ Bunday kodli kino topilmadi."
            )

        context.user_data.clear()

        return


    # =========================
    # KANAL QO'SHISH
    # =========================

    if is_admin(user_id) and action == "add_channel":

        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Kanal username'i @ bilan boshlanishi kerak.\n\n"
                "Masalan: @kanal98766"
            )
            return

        cur.execute(
            "INSERT OR IGNORE INTO channels (username) VALUES (?)",
            (text,)
        )

        db.commit()

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ {text} majburiy obuna kanaliga qo'shildi."
        )

        return


    # =========================
    # KANAL O'CHIRISH
    # =========================

    if is_admin(user_id) and action == "delete_channel":

        if text == DEFAULT_CHANNEL:
            await update.message.reply_text(
                "❌ Boshlang'ich kanalni o'chirib bo'lmaydi."
            )
            return

        cur.execute(
            "DELETE FROM channels WHERE username=?",
            (text,)
        )

        db.commit()

        if cur.rowcount > 0:
            await update.message.reply_text(
                f"✅ {text} kanali o'chirildi."
            )
        else:
            await update.message.reply_text(
                "❌ Bunday kanal topilmadi."
            )

        context.user_data.clear()

        return


    # =========================
    # ADMIN QO'SHISH
    # =========================

    if is_admin(user_id) and is_owner(user_id):

        if action == "add_admin":

            try:
                new_admin = int(text)

                cur.execute(
                    "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                    (new_admin,)
                )

                db.commit()

                await update.message.reply_text(
                    f"✅ {new_admin} admin qilindi."
                )

            except ValueError:

                await update.message.reply_text(
                    "❌ Telegram ID faqat raqam bo'lishi kerak."
                )

            context.user_data.clear()

            return


    # =========================
    # ADMIN O'CHIRISH
    # =========================

    if is_admin(user_id) and is_owner(user_id):

        if action == "delete_admin":

            try:
                delete_id = int(text)

                if delete_id == OWNER_ID:

                    await update.message.reply_text(
                        "❌ Bosh adminni o'chirib bo'lmaydi."
                    )

                else:

                    cur.execute(
                        "DELETE FROM admins WHERE user_id=?",
                        (delete_id,)
                    )

                    db.commit()

                    if cur.rowcount > 0:

                        await update.message.reply_text(
                            "✅ Admin o'chirildi."
                        )

                    else:

                        await update.message.reply_text(
                            "❌ Bunday admin topilmadi."
                        )

            except ValueError:

                await update.message.reply_text(
                    "❌ Noto'g'ri Telegram ID."
                )

            context.user_data.clear()

            return


    # =========================
    # REKLAMA
    # =========================

    if is_admin(user_id) and action == "broadcast":

        cur.execute(
            "SELECT user_id FROM users"
        )

        users = cur.fetchall()

        sent = 0

        for (target_id,) in users:

            try:

                await context.bot.send_message(
                    chat_id=target_id,
                    text=text
                )

                sent += 1

            except Exception:

                pass

        context.user_data.clear()

        await update.message.reply_text(
            f"📣 Reklama yuborildi!\n\n"
            f"✅ Yuborildi: {sent} ta foydalanuvchi."
        )

        return


    # =========================
    # KINO KODINI QIDIRISH
    # =========================

    cur.execute(
        "SELECT file_id FROM movies WHERE code=?",
        (text,)
    )

    movie = cur.fetchone()

    if movie:

        await update.message.reply_video(
            video=movie[0],
            caption=(
                f"🎬 Kino kodi: {text}\n\n"
                "🍿 Yoqimli tomosha!"
            ),
            protect_content=True
        )

    else:

        await update.message.reply_text(
            "❌ Bunday kino kodi topilmadi.\n\n"
            "🔢 Kino kodini to'g'ri kiriting."
          )# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi! "
            "Render Environment Variables ichiga BOT_TOKEN qo'shing."
        )

    app = Application.builder().token(
        BOT_TOKEN
    ).build()

    # START
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # ADMIN PANEL
    app.add_handler(
        CommandHandler(
            "admin",
            admin
        )
    )

    # TUGMALAR
    app.add_handler(
        CallbackQueryHandler(
            callbacks
        )
    )

    # VIDEO QABUL QILISH
    app.add_handler(
        MessageHandler(
            filters.VIDEO,
            receive_video
        )
    )

    # MATN QABUL QILISH
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print(
        "🤖 Kino bot ishga tushdi!"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
