# This file is a part of TG-FileStreamBot

import os
import sys
import time
import asyncio
import psutil
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from WebStreamer import StartTime
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from WebStreamer.bot.plugins.admin import owner_filter, _db_enabled

if _db_enabled:
    from WebStreamer.db import get_user_count


def get_readable_time(seconds: int) -> str:
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = []
    for name, secs in periods:
        if seconds >= secs:
            val, seconds = divmod(seconds, secs)
            result.append(f'{int(val)}{name}')
    return ' '.join(result) if result else '0s'


def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    while size > power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"


async def _build_stats_text():
    sys_uptime = get_readable_time(int(time.time() - psutil.boot_time()))
    bot_uptime = get_readable_time(int(time.time() - StartTime))
    net = await asyncio.to_thread(psutil.net_io_counters)
    cpu_percent = await asyncio.to_thread(psutil.cpu_percent, interval=0.5)
    cpu_cores = psutil.cpu_count(logical=False)
    cpu_freq = await asyncio.to_thread(psutil.cpu_freq)
    cpu_freq_ghz = f"{cpu_freq.current / 1000:.2f} GHz" if cpu_freq else "N/A"
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    users = await get_user_count() if _db_enabled else "N/A"

    return (
        "<blockquote>📊 <b>Bot System Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{users}</code>\n\n"
        f"⏰ <b>System Uptime:</b> <code>{sys_uptime}</code>\n"
        f"🤖 <b>Bot Uptime:</b> <code>{bot_uptime}</code>\n\n"
        f"⚙️ <b>CPU Usage:</b> <code>{cpu_percent}%</code>\n"
        f"🔢 <b>CPU Cores:</b> <code>{cpu_cores if cpu_cores else 'N/A'}</code>\n"
        f"⚡ <b>CPU Frequency:</b> <code>{cpu_freq_ghz}</code>\n\n"
        f"🧠 <b>RAM Usage:</b> <code>{humanbytes(ram.used)} / {humanbytes(ram.total)}</code> (<code>{ram.percent}%</code>)\n"
        f"💚 <b>RAM Free:</b> <code>{humanbytes(ram.available)}</code>\n\n"
        f"💾 <b>Disk Usage:</b> <code>{humanbytes(disk.used)} / {humanbytes(disk.total)}</code> (<code>{disk.percent}%</code>)\n"
        f"📁 <b>Disk Free:</b> <code>{humanbytes(disk.free)}</code>\n\n"
        f"📤 <b>Upload:</b> <code>{humanbytes(net.bytes_sent)}</code>\n"
        f"📥 <b>Download:</b> <code>{humanbytes(net.bytes_recv)}</code>\n\n"
        "🚀 <b>Status:</b> Bot running smoothly!</blockquote>"
    )


@StreamBot.on_message(filters.command("stats") & filters.private & filters.create(owner_filter))
async def stats_cmd(_, m: Message):
    status = await m.reply("📊 Fetching statistics...", quote=True)
    try:
        text = await _build_stats_text()
    except Exception as e:
        return await status.edit(f"❌ <b>Error:</b> <code>{e}</code>")

    await status.edit(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
            [InlineKeyboardButton("❌ Close", callback_data="close_stats")],
        ]),
    )


@StreamBot.on_callback_query(filters.regex("^(refresh_stats|close_stats)$"))
async def stats_callback(_, cq):
    if cq.from_user.id != Var.OWNER_ID:
        return await cq.answer("❌ You are not authorized!", show_alert=True)

    if cq.data == "close_stats":
        return await cq.message.delete()

    await cq.answer("🔄 Refreshing stats...")
    try:
        text = await _build_stats_text()
    except Exception as e:
        return await cq.answer(f"❌ Error: {e}", show_alert=True)

    await cq.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
            [InlineKeyboardButton("❌ Close", callback_data="close_stats")],
        ]),
    )


@StreamBot.on_message(filters.command("restart") & filters.private & filters.create(owner_filter))
async def restart_bot(_, m: Message):
    await m.reply("♻️ <b>Bot is restarting...</b>", quote=True)
    os.execv(sys.executable, ['python3'] + sys.argv)
