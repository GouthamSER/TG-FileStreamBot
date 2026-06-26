import hashlib
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.file_id import FileId
from typing import Any, Optional, Union
from pyrogram.raw.types.messages import Messages
from WebStreamer.server.exceptions import FIleNotFound
from datetime import datetime


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
        raise FIleNotFound
    media = get_media_from_message(message)
    if not media:
        # message exists but has no media anymore (deleted/service message) -> file gone
        raise FIleNotFound
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    if not file_id:
        raise FIleNotFound
    setattr(file_id, "file_size", getattr(media, "file_size", 0) or 0)
    setattr(file_id, "mime_type", getattr(media, "mime_type", "") or "")
    setattr(file_id, "file_name", getattr(media, "file_name", "") or "")
    setattr(file_id, "unique_id", file_unique_id)
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


def get_name(media_msg: Union[Message, FileId]) -> str:
    file_name = ""

    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        file_name = getattr(media, "file_name", "") or ""

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

        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{media_type}-{date}{ext}"

    return file_name
