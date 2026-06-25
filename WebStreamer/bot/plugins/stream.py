# This file is a part of TG-FileStreamBot
# Coding : Jyothis Jayanth [@EverythingSuckz]

import logging
from pyrogram import filters, errors
from WebStreamer.vars import Var
from urllib.parse import quote
from WebStreamer.bot import StreamBot, logger
from WebStreamer.utils import get_hash, get_name
from WebStreamer.utils.file_properties import get_media_from_message
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

try:
    from WebStreamer.db import add_user
    from WebStreamer.bot.plugins.start import check_fsub
    _db_enabled = bool(Var.DATABASE_URI)
except Exception:
    _db_enabled = False
    add_user = None
    check_fsub = None


def get_size_readable(size: int) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PiB"


@StreamBot.on_message(
    filters.private
    & (
        filters.document
        | filters.video
        | filters.audio
        | filters.animation
        | filters.voice
        | filters.video_note
        | filters.photo
        | filters.sticker
    ),
    group=4,
)
async def media_receive_handler(_, m: Message):
    if Var.ALLOWED_USERS and not ((str(m.from_user.id) in Var.ALLOWED_USERS) or (m.from_user.username in Var.ALLOWED_USERS)):
        return await m.reply("You are not <b>allowed to use</b> this <a href='https://github.com/GouthamSER/TG-FileStreamBot'>bot</a>.", quote=True)

    # FSub check
    if check_fsub and not await check_fsub(_, m.from_user.id):
        from WebStreamer.bot.plugins.start import fsub_keyboard
        return await m.reply(
            "📢 <b>Please join our channel first!</b>",
            reply_markup=fsub_keyboard(),
            quote=True,
        )

    # Ensure user saved
    if _db_enabled and add_user:
        await add_user(m.from_user.id, m.from_user.first_name or "", m.from_user.username or "")

    log_msg = await m.forward(chat_id=Var.BIN_CHANNEL)
    file_hash = get_hash(log_msg, Var.HASH_LENGTH)
    file_name = get_name(m)
    stream_link = f"{Var.URL}{log_msg.id}/{quote(file_name)}?hash={file_hash}"
    short_link = f"{Var.URL}{file_hash}{log_msg.id}"
    logger.info(f"Generated link: {stream_link} for {m.from_user.first_name}")

    media = get_media_from_message(m)
    file_size = getattr(media, "file_size", 0) or 0
    size_str = get_size_readable(file_size) if file_size else "Unknown"

    reply_text = (
        "__<b>Your Link Generated !</b>__\n\n"
        "📄 <b>File Name :</b>\n"
        f"<code>{file_name}</code>\n\n"
        "📦 <b>File size :</b> <code>{}</code>\n\n"
        "🔗 <b>Download Link:</b> <a href='{}'>{}</a>\n\n"
        "⏰ <b>Link Expires In 24hrs</b>\n\n"
        "__📌 <b>Note :-</b> Use FDM (For PC) or FDM (For Mobile) To Download With Maximum Speed__"
    ).format(size_str, stream_link, stream_link)

    try:
        await m.reply_text(
            text=reply_text,
            quote=True,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[
                    #InlineKeyboardButton("Shortened 🔗", url=short_link),
                    InlineKeyboardButton("Download 📥", url=stream_link),
                ]]
            ),
        )
    except errors.ButtonUrlInvalid:
        await m.reply_text(
            text=reply_text,
            quote=True,
            parse_mode=ParseMode.HTML,
        )
