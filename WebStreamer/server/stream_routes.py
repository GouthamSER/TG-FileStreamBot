# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import re
import time
import math
import asyncio
import logging
import secrets
import mimetypes
from urllib.parse import quote, unquote
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.server.exceptions import FIleNotFound, InvalidHash, StreamError
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
        dl_match = re.search(r"^dl/(\d+)([0-9a-f]{%s})$" % (Var.HASH_LENGTH), path)
        if dl_match:
            # dl link: /dl/msgid+hash — no filename in URL
            message_id = int(dl_match.group(1))
            secure_hash = dl_match.group(2)
        elif match:
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
    except web.HTTPException:
        raise
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (BadStatusLine, ConnectionError):
        # client went away: nothing to send, but aiohttp needs a response object back
        return web.Response(status=499)
    except AttributeError as e:
        # bin channel message/media is gone but wasn't caught earlier as FIleNotFound
        logger.warning(f"Treating AttributeError as file not found for message_id={message_id}: {e}")
        raise web.HTTPNotFound(text="404: File not found")
    except Exception as e:
        logger.critical(str(e), exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}

CHUNK_SIZE = 1024 * 1024  # Telegram GetFile max limit


class RangeNotSatisfiable(Exception):
    pass


def parse_range(header, file_size: int):
    """
    Parse an HTTP Range header against `file_size` (RFC 7233).
    Returns (start, end) inclusive, or None when the header is absent / not a
    single valid bytes range (then the whole file is served with 200).
    Raises RangeNotSatisfiable when it is valid but outside the file.
    Handles `a-b`, `a-`, suffix `-n`, and clamps `b` past EOF instead of
    rejecting it (download managers often ask for huge end offsets).
    """
    if not header:
        return None
    header = header.strip()
    if not header.lower().startswith("bytes="):
        return None
    spec = header[6:].strip()
    if "," in spec or "-" not in spec:
        return None  # multi-range unsupported -> ignore, serve full body
    first, _, last = spec.partition("-")
    first, last = first.strip(), last.strip()
    try:
        if first == "":
            if last == "":
                return None
            suffix = int(last)
            if suffix <= 0:
                raise RangeNotSatisfiable
            return max(file_size - suffix, 0), file_size - 1
        start = int(first)
        end = int(last) if last != "" else file_size - 1
    except ValueError:
        return None
    if start < 0 or (last != "" and end < start):
        return None  # syntactically invalid -> ignore
    if start >= file_size:
        raise RangeNotSatisfiable
    return start, min(end, file_size - 1)


def _if_range_ok(request: web.Request, etag: str) -> bool:
    """If-Range present and not matching our ETag -> client's partial copy is stale, send full file."""
    val = request.headers.get("If-Range")
    if not val:
        return True
    return val.strip() == etag


async def media_streamer(request: web.Request, message_id: int, secure_hash: str, url_file_name: str = None):
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if Var.MULTI_CLIENT:
        logger.debug(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logger.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logger.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    file_id = await tg_connect.get_file_properties(message_id)
    
    if utils.get_hash(file_id.unique_id, Var.HASH_LENGTH) != secure_hash:
        logger.debug(f"Invalid hash for message with ID {message_id}")
        raise InvalidHash
    
    file_size = file_id.file_size
    if not file_size or file_size <= 0:
        # never answer with an empty 200 for a real file: that is a silent "file loss"
        logger.error(f"Unknown/zero file size for message {message_id}")
        raise web.HTTPBadGateway(text="502: File size unavailable")

    etag = f'"{file_id.unique_id}"'
    try:
        byte_range = parse_range(request.headers.get("Range"), file_size)
    except RangeNotSatisfiable:
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    if byte_range is not None and not _if_range_ok(request, etag):
        byte_range = None

    partial = byte_range is not None
    from_bytes, until_bytes = byte_range if partial else (0, file_size - 1)

    chunk_size = CHUNK_SIZE
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = until_bytes // chunk_size - offset // chunk_size + 1
    mime_type = file_id.mime_type

    # Priority: filename from URL path > filename from cached file_id
    file_name = utils.file_properties.sanitize_filename(url_file_name) if url_file_name else utils.get_name(file_id)

    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # forced attachment for all types — no more inline play in browser

    # Some download managers (FDM, older IDM builds) don't parse the RFC5987
    # filename*= form and grab a truncated/partial name instead — sending a
    # plain ascii filename="" fallback alongside filename*= fixes that.
    ascii_fallback = "".join(c if (c.isascii() and c.isprintable() and c not in '"\\') else "_" for c in file_name) or "file"

    encoded_name = quote(file_name, safe="")
    headers = {
        "Content-Type": f"{mime_type}",
        "Content-Disposition": f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_name}',
        "Accept-Ranges": "bytes",
        "ETag": etag,
    }
    if partial:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"

    resp = web.StreamResponse(status=206 if partial else 200, headers=headers)
    resp.content_length = req_length
    await resp.prepare(request)
    if request.method == "HEAD":
        return resp

    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size, message_id
    )
    try:
        async for chunk in body:
            await resp.write(chunk)
    except (ConnectionError, asyncio.CancelledError):
        # client closed / cancelled: just stop (generator cleanup runs in finally)
        raise
    except Exception as e:
        # Unrecoverable upstream failure AFTER headers went out. Drop the TCP
        # connection so the client sees an incomplete body (-> resumes via Range)
        # rather than a complete-looking but truncated file.
        logger.error(f"Aborting stream of message {message_id}: {e!r}", exc_info=not isinstance(e, StreamError))
        if request.transport is not None:
            request.transport.close()
        return resp
    finally:
        await body.aclose()
    await resp.write_eof()
    return resp
