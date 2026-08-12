# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import re
import time
import math
import logging
import secrets
import mimetypes
from urllib.parse import quote, unquote
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.server.exceptions import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot

logger = logging.getLogger("routes")


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": f"v{__version__}",
        }
    )


@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    # --- step 1: parse the url path itself ---
    try:
        path = request.match_info["path"]
        url_file_name = None
        match = re.search(r"^([0-9a-f]{%s})(\d+)$" % (Var.HASH_LENGTH), path)
        if match:
            # short link: /hash+msgid  — no filename in URL
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            # long link: /msgid/filename?hash=...
            parts = path.split("/", 1)
            id_match = re.search(r"(\d+)", parts[0])
            if not id_match:
                # not a real generated link (probe/crawler/favicon etc) -> bad request, not "file not found"
                raise web.HTTPBadRequest(text="400: Bad request, invalid link")
            message_id = int(id_match.group(1))
            secure_hash = request.rel_url.query.get("hash")
            if len(parts) > 1 and parts[1]:
                url_file_name = unquote(parts[1])
    except web.HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Bad/malformed url path '{request.path}': {e}")
        raise web.HTTPBadRequest(text="400: Bad request, invalid link")

    # --- step 2: actually fetch/stream the file ---
    try:
        return await media_streamer(request, message_id, secure_hash, url_file_name)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (BadStatusLine, ConnectionResetError):
        pass
    except AttributeError as e:
        # bin channel message/media is gone but wasn't caught earlier as FIleNotFound
        logger.warning(f"Treating AttributeError as file not found for message_id={message_id}: {e}")
        raise web.HTTPNotFound(text="404: File not found")
    except Exception as e:
        logger.critical(str(e), exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}

async def media_streamer(request: web.Request, message_id: int, secure_hash: str, url_file_name: str = None):
    range_header = request.headers.get("Range", 0)
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if Var.MULTI_CLIENT:
        logger.info(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logger.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logger.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    logger.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(message_id)
    logger.debug("after calling get_file_properties")
    
    
    if utils.get_hash(file_id.unique_id, Var.HASH_LENGTH) != secure_hash:
        logger.debug(f"Invalid hash for message with ID {message_id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.floor(until_bytes / chunk_size) - math.floor(offset / chunk_size) + 1
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )
    mime_type = file_id.mime_type

    # Priority: filename from URL path > filename from cached file_id
    file_name = url_file_name or utils.get_name(file_id)

    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # forced attachment for all types — no more inline play in browser

    # Some download managers (FDM, older IDM builds) don't parse the RFC5987
    # filename*= form and grab a truncated/partial name instead — sending a
    # plain ascii filename="" fallback alongside filename*= fixes that.
    ascii_fallback = file_name.encode("ascii", "ignore").decode() or "file"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(file_name)}',
            "Accept-Ranges": "bytes",
        },
    )
