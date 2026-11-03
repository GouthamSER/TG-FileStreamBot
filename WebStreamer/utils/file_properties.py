import re
import hashlib
import logging
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.file_id import FileId
from typing import Any, Optional, Union
from pyrogram.raw.types.messages import Messages
from WebStreamer.server.exceptions import FIleNotFound
from datetime import datetime

logger = logging.getLogger("file_properties")


async def parse_file_id(message: "Message") -> Optional[FileId]:
    media = get_media_from_message(message)
    if media:
        return FileId.decode(media.file_id)

async def parse_file_unique_id(message: "Messages") -> Optional[str]:
    media = get_media_from_message(message)
    if media:
        return media.file_unique_id

async def get_file_ids(client: Client, chat_id: int, message_id: int) -> Optional[FileId]:
    message = await client.get_messages(chat_id, message_id)
    if not message or message.empty:
        logger.warning(f"[404 cause] message_id={message_id} chat_id={chat_id}: message missing/empty (message={message!r}, empty={getattr(message, 'empty', None)})")
        raise FIleNotFound
    media = get_media_from_message(message)
    if not media:
        # message exists but has no media anymore (deleted/service message) -> file gone
        logger.warning(f"[404 cause] message_id={message_id} chat_id={chat_id}: message exists but has no media (media_type={message.media})")
        raise FIleNotFound
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    if not file_id:
        logger.warning(f"[404 cause] message_id={message_id} chat_id={chat_id}: media present but file_id decode failed")
        raise FIleNotFound
    setattr(file_id, "file_size", getattr(media, "file_size", 0) or 0)
    setattr(file_id, "mime_type", getattr(media, "mime_type", "") or "")
    setattr(file_id, "unique_id", file_unique_id)
    # full name (caption-aware) so links WITHOUT a filename in the URL still
    # download under the complete name via Content-Disposition
    setattr(file_id, "file_name", get_name(message))
    return file_id

def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_hash(media_msg: Union[str, Message], length: int) -> str:
    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        unique_id = getattr(media, "file_unique_id", "")
    else:
        unique_id = media_msg
    long_hash = hashlib.sha256(unique_id.encode("UTF-8")).hexdigest()
    return long_hash[:length]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _full_name_from_caption(file_name: str, caption) -> str:
    """
    Telegram cuts long document file names (uploaders like PSA end up with
    "...10bit.WEBR.mkv"), while the caption's first line still holds the full
    release name ("...10bit.WEBRip.6CH.x265.HEVC-PSA"). If that caption line
    clearly is the longer version of the same name (same start, just more),
    return it with the real extension; otherwise keep file_name untouched.
    """
    if not file_name or not caption:
        return file_name
    lines = str(caption).strip().splitlines()
    if not lines:
        return file_name
    line = lines[0].strip()
    stem, dot, ext = file_name.rpartition(".")
    if not dot or not stem or not re.fullmatch(r"[A-Za-z0-9]{1,5}", ext):
        stem, ext = file_name, ""
    else:
        ext = "." + ext
    if ext and line.lower().endswith(ext.lower()):
        line = line[: -len(ext)].rstrip()
    n_line, n_stem = _norm(line), _norm(stem)
    if n_stem and len(n_line) > len(n_stem) and n_line.startswith(n_stem):
        return f"{line}{ext}"
    return file_name


def get_name(media_msg: Union[Message, FileId]) -> str:
    file_name = ""

    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        file_name = getattr(media, "file_name", "") or ""
        if file_name:
            file_name = _full_name_from_caption(file_name, getattr(media_msg, "caption", None))
        if not file_name and getattr(media_msg, "caption", None):
            # compressed video/photo sends strip file_name entirely — Telegram
            # only preserves it when sent as Document/File. caption's first
            # line usually holds the real name, so use it before falling
            # back to a generic "video-2026-08-19..." placeholder.
            first_line = str(media_msg.caption).strip().splitlines()[0].strip()
            if first_line:
                file_name = first_line
                # caption text often has no real "." extension (people type
                # "... Atmos mkv" instead of "...Atmos.mkv") — attach one
                # from mime_type so the downloaded file still plays properly.
                if not re.search(r"\.[A-Za-z0-9]{2,4}$", file_name):
                    mime_type = getattr(media, "mime_type", "") or getattr(media_msg, "mime_type", "") or ""
                    ext = ""
                    if mime_type:
                        import mimetypes
                        ext = mimetypes.guess_extension(mime_type) or ""
                        ext = {".jpe": ".jpg", ".jpeg": ".jpg", ".jfif": ".jpg"}.get(ext, ext)
                    if not ext:
                        media_type = media_msg.media.value if media_msg.media else "file"
                        ext = {
                            "photo": ".jpg", "audio": ".mp3", "voice": ".ogg",
                            "video": ".mp4", "animation": ".mp4", "video_note": ".mp4",
                            "sticker": ".webp",
                        }.get(media_type, "")
                    if ext:
                        file_name = f"{file_name}{ext}"

    elif isinstance(media_msg, FileId):
        file_name = getattr(media_msg, "file_name", "") or ""

    if not file_name:
        # Determine media_type label
        if isinstance(media_msg, Message) and media_msg.media:
            media_type = media_msg.media.value
        elif hasattr(media_msg, "file_type") and media_msg.file_type:
            media_type = media_msg.file_type.name.lower()
        else:
            media_type = "file"

        # Try to get extension from mime_type first (most accurate)
        mime_type = getattr(media_msg, "mime_type", "") or ""
        if mime_type:
            import mimetypes
            ext = mimetypes.guess_extension(mime_type) or ""
            # mimetypes can return odd ones like .jpe for jpeg — normalize
            ext = {".jpe": ".jpg", ".jpeg": ".jpg", ".jfif": ".jpg"}.get(ext, ext)
        else:
            # fallback map by media_type label
            formats = {
                "photo": ".jpg", "audio": ".mp3", "voice": ".ogg",
                "video": ".mp4", "animation": ".mp4", "video_note": ".mp4",
                "sticker": ".webp"
            }
            ext = formats.get(media_type, "")

        # stable per-file stamp: a timestamp would give every request (and every
        # resume) a different filename, which confuses download managers.
        stamp = getattr(media_msg, "unique_id", None)
        if not stamp and isinstance(media_msg, Message):
            stamp = getattr(get_media_from_message(media_msg), "file_unique_id", None)
        stamp = stamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{media_type}-{stamp}{ext}"

    return sanitize_filename(file_name)


def sanitize_filename(name: str) -> str:
    """
    Keep the filename EXACTLY as the user sent it (spaces, unicode, symbols,
    full length). Only what can break a download is touched:
      - path separators "/" and "\\" -> "_" (no directory tricks)
      - control chars (incl. newlines, NUL) removed
      - surrounding whitespace trimmed
    """
    if not name:
        return name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.replace("/", "_").replace("\\", "_").strip()
    return name or "file"
