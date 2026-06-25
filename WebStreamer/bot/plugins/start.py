# This file is a part of TG-FileStreamBot

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot

# db import is optional — graceful if DATABASE_URI not set
try:
    from WebStreamer.db import add_user
    _db_enabled = bool(Var.DATABASE_URI)
except Exception:
    _db_enabled = False
    add_user = None


async def check_fsub(bot, user_id: int) -> bool:
    """Return True if user is member of FSUB_CHANNEL (or FSub disabled)."""
    if not Var.FSUB_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(Var.FSUB_CHANNEL, user_id)
        from pyrogram.enums import ChatMemberStatus
        return member.status not in (
            ChatMemberStatus.BANNED,
            ChatMemberStatus.LEFT,
        )
    except Exception:
        return False  # treat errors as not-joined so we prompt


def fsub_keyboard():
    channel = Var.FSUB_CHANNEL
    if isinstance(channel, int):
        url = f"https://t.me/c/{str(channel).replace('-100', '')}"
    else:
        url = f"https://t.me/{channel.lstrip('@')}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Join Channel 📢", url=url),
        InlineKeyboardButton("✅ Joined", callback_data="fsub_check"),
    ]])


@StreamBot.on_message(filters.command(["start", "help"]) & filters.private)
async def start(bot, m: Message):
    uid = m.from_user.id

    # ALLOWED_USERS gate
    if Var.ALLOWED_USERS and not (
        (str(uid) in Var.ALLOWED_USERS) or
        (m.from_user.username in Var.ALLOWED_USERS)
    ):
        return await m.reply(
            "You are not in the allowed list of users who can use me. "
            "Check <a href='https://github.com/GouthamSER/TG-FileStreamBot#optional-vars'>this link</a> for more info.",
            disable_web_page_preview=True, quote=True
        )

    # FSub gate
    if not await check_fsub(bot, uid):
        return await m.reply(
            "📢 <b>Join our channel first to use this bot!</b>\n\nAfter joining, tap ✅ Joined below.",
            reply_markup=fsub_keyboard(),
            quote=True,
        )

    # Save user
    if _db_enabled and add_user:
        await add_user(uid, m.from_user.first_name or "", m.from_user.username or "")

    await m.reply(
        f"👋 Hi {m.from_user.mention(style='md')}!\n\n"
        "**Send me any file and I'll give you an instant stream/download link. 🔗**",
    )


@StreamBot.on_callback_query(filters.regex("^fsub_check$"))
async def fsub_recheck(bot, cb):
    if await check_fsub(bot, cb.from_user.id):
        uid = cb.from_user.id
        if _db_enabled and add_user:
            await add_user(uid, cb.from_user.first_name or "", cb.from_user.username or "")
        await cb.message.edit_text(
            f"✅ Thanks for joining, {cb.from_user.mention(style='md')}!\n\n"
            "__Now send me any file to get a stream link. 🔗__"
        )
    else:
        await cb.answer("You haven't joined yet!", show_alert=True)
