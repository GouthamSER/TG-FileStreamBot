# This file is a part of TG-FileStreamBot
# Coding : Goutham Josh [@GouthamSER]

import sys
import asyncio
import logging
from .vars import Var
from aiohttp import web
from pyrogram import idle
from WebStreamer import utils
from WebStreamer import StreamBot
from WebStreamer.server import web_server
from WebStreamer.bot.clients import initialize_clients
from WebStreamer.bot import multi_clients


logging.basicConfig(
    level=logging.DEBUG if Var.DEBUG else logging.INFO,
    datefmt="%d/%m/%Y %H:%M:%S",
    format="[%(asctime)s][%(name)s][%(levelname)s] ==> %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout),
              logging.FileHandler("streambot.log", mode="a", encoding="utf-8")],)

logging.getLogger("aiohttp").setLevel(logging.DEBUG if Var.DEBUG else logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.INFO if Var.DEBUG else logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.DEBUG if Var.DEBUG else logging.ERROR)

server = web.AppRunner(web_server())

try:
    loop = asyncio.get_event_loop()
except RuntimeError:  # Python 3.12+/3.14: no implicit loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)



async def start_services():
    logging.info("Initializing Telegram Bot")
    await StreamBot.start()
    bot_info = await StreamBot.get_me()
    logging.debug(bot_info)
    StreamBot.username = bot_info.username
    logging.info("Initialized Telegram Bot")
    await initialize_clients()
    if Var.KEEP_ALIVE:
        asyncio.create_task(utils.ping_server())
    await server.setup()
    await web.TCPSite(server, Var.BIND_ADDRESS, Var.PORT).start()
    logging.info("Service Started")
    logging.info("bot =>> {}".format(bot_info.first_name))
    if bot_info.dc_id:
        logging.info("DC ID =>> {}".format(str(bot_info.dc_id)))
    logging.info("URL =>> {}".format(Var.URL))
    await idle()

async def cleanup():
    try:
        await server.cleanup()
    except Exception:
        logging.error("Error cleaning web server", exc_info=True)
    for client_id, client in multi_clients.items():
        if client_id == 0:
            continue
        try:
            await client.stop()
        except Exception:
            logging.error(f"Error stopping client {client_id}", exc_info=True)
    try:
        await StreamBot.stop()
    except Exception:
        logging.error("Error stopping main client", exc_info=True)

if __name__ == "__main__":
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
    except Exception as err:
        logging.error("Fatal error", exc_info=True)
    finally:
        loop.run_until_complete(cleanup())
        loop.stop()
        logging.info("Stopped Services")
