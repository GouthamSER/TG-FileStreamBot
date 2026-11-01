import asyncio
import collections
import itertools
import logging
from WebStreamer import Var
from typing import Dict, List, Optional, Union
from WebStreamer.bot import work_loads
from pyrogram import Client, utils, raw, errors
from .file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from WebStreamer.server.exceptions import FIleNotFound, StreamError
from pyrogram.file_id import FileId, FileType, ThumbnailSource

logger = logging.getLogger("streamer")


class _FetchState:
    """Mutable per-download state shared by the in-flight part fetches."""

    __slots__ = ("file_id", "location", "message_id", "lock")

    def __init__(self, file_id, location, message_id):
        self.file_id = file_id
        self.location = location
        self.message_id = message_id
        self.lock = asyncio.Lock()


class ByteStreamer:
    def __init__(self, client: Client):
        """A custom class that holds the cache of a specific client and class functions.
        attributes:
            client: the client that the cache is for.
            cached_file_ids: a dict of cached file IDs.
            cached_file_properties: a dict of cached file properties.
        
        functions:
            generate_file_properties: returns the properties for a media of a specific message contained in Tuple.
            generate_media_session: returns a media session for the DC that contains the media file.
            yield_file: yield a file from telegram servers for streaming.
            
        This is a modified version of the <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        self.session_locks: Dict[int, asyncio.Lock] = {}
        self._pools: Dict[int, List[Session]] = {}
        self._rr = itertools.count()
        self._inflight: Dict[int, "asyncio.Future"] = {}
        # keep a strong reference: the loop only holds weak refs to tasks, an
        # unreferenced clean_cache task can be garbage collected and die silently.
        self._clean_task = asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, message_id: int) -> FileId:
        """
        Returns the properties of a media of a specific message in a FIleId class.
        if the properties are cached, then it'll return the cached results.
        or it'll generate the properties from the Message ID and cache them.
        Concurrent callers for the same message share one lookup (download
        managers open many connections at once; without this each one hits
        get_messages and trips flood limits).
        """
        cached = self.cached_file_ids.get(message_id)
        if cached is not None:
            return cached
        fut = self._inflight.get(message_id)
        if fut is None:
            fut = asyncio.ensure_future(self.generate_file_properties(message_id))
            self._inflight[message_id] = fut

            def _done(f, mid=message_id):
                self._inflight.pop(mid, None)
                if not f.cancelled():
                    f.exception()  # mark retrieved, waiters still get it via shield

            fut.add_done_callback(_done)
        return await asyncio.shield(fut)

    async def refresh_file_properties(self, message_id: int) -> FileId:
        """Drop cached properties and re-read the message (fresh file_reference)."""
        self.cached_file_ids.pop(message_id, None)
        return await self.get_file_properties(message_id)
    
    async def generate_file_properties(self, message_id: int) -> FileId:
        """
        Generates the properties of a media file on a specific message.
        returns ths properties in a FIleId class.
        """
        file_id = await get_file_ids(self.client, Var.BIN_CHANNEL, message_id)
        logger.debug(f"Generated file ID and Unique ID for message with ID {message_id}")
        if not file_id:
            logger.debug(f"Message with ID {message_id} not found")
            raise FIleNotFound
        self.cached_file_ids[message_id] = file_id
        logger.debug(f"Cached media message with ID {message_id}")
        return self.cached_file_ids[message_id]

    async def _create_media_session(self, client: Client, dc_id: int) -> Session:
        """Build and start one fresh media session for `dc_id`."""
        if dc_id != await client.storage.dc_id():
            media_session = Session(
                client,
                dc_id,
                await Auth(client, dc_id, await client.storage.test_mode()).create(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()

            for _ in range(6):
                exported_auth = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                )

                try:
                    await media_session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported_auth.id, bytes=exported_auth.bytes
                        )
                    )
                    break
                except AuthBytesInvalid:
                    logger.debug(f"Invalid authorization bytes for DC {dc_id}")
                    continue
            else:
                await media_session.stop()
                raise AuthBytesInvalid
        else:
            media_session = Session(
                client,
                dc_id,
                await client.storage.auth_key(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()
        logger.debug(f"Created media session for DC {dc_id}")
        return media_session

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Returns a media session for the DC that contains the media file.
        This is required for getting the bytes from Telegram servers.

        A small pool of sessions per DC (Var.MEDIA_SESSIONS_PER_DC) is kept and
        handed out round-robin: one MTProto session caps how many GetFile
        requests it runs at once, so a pool is what lets one download (or many
        parallel connections of a download manager) reach full line speed.
        The pool grows by one session per call until full, so the first byte
        is never delayed by building several sessions.

        Creation is guarded by a per-DC lock so concurrent requests can't race
        and stomp on each other's Session objects ("read() called while another
        coroutine is already waiting for incoming data" crashes).
        """
        dc_id = file_id.dc_id
        target = max(1, Var.MEDIA_SESSIONS_PER_DC)

        pool = self._pools.get(dc_id)
        if pool and len(pool) >= target:  # fast path, no lock
            return pool[next(self._rr) % len(pool)]

        lock = self.session_locks.setdefault(dc_id, asyncio.Lock())
        async with lock:
            pool = self._pools.setdefault(dc_id, [])
            if not pool:
                # adopt a session another component already cached
                existing = client.media_sessions.get(dc_id)
                if existing is not None:
                    pool.append(existing)
            if len(pool) < target:
                session = await self._create_media_session(client, dc_id)
                pool.append(session)
                client.media_sessions.setdefault(dc_id, session)
                return session
            return pool[next(self._rr) % len(pool)]

    def _evict_session(self, dc_id: int, session: Session) -> None:
        """Forget a dead media session so the next request builds a fresh one."""
        pool = self._pools.get(dc_id)
        if pool and session in pool:
            pool.remove(session)
        if self.client.media_sessions.get(dc_id) is session:
            self.client.media_sessions.pop(dc_id, None)
            if pool:
                self.client.media_sessions[dc_id] = pool[0]
        try:
            asyncio.get_running_loop().create_task(session.stop())
        except Exception:
            pass


    @staticmethod
    async def get_location(file_id: FileId) -> Union[raw.types.InputPhotoFileLocation,
                                                     raw.types.InputDocumentFileLocation,
                                                     raw.types.InputPeerPhotoFileLocation,]:
        """
        Returns the file location for the media file.
        """
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )

            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return location

    async def _fetch_part(self, state: _FetchState, off: int, limit: int, need: int) -> bytes:
        """
        Fetch one `limit`-sized part at `off`, retrying on every transient
        failure. Returns at least `need` bytes or raises StreamError - it never
        returns short data, so the response can't end up silently truncated.
        """
        retries = max(0, Var.STREAM_RETRIES)
        last_exc: Optional[BaseException] = None
        for attempt in range(retries + 1):
            session = None
            fid = state.file_id
            try:
                session = await self.generate_media_session(self.client, fid)
                r = await session.invoke(
                    raw.functions.upload.GetFile(
                        location=state.location, offset=off, limit=limit
                    ),
                )
                if not isinstance(r, raw.types.upload.File):
                    raise StreamError(f"unexpected GetFile result {type(r).__name__} at offset {off}")
                data = r.bytes
                if len(data) < need:
                    raise StreamError(f"short read at offset {off}: got {len(data)}, need {need}")
                return data
            except asyncio.CancelledError:
                raise
            except (errors.FileReferenceExpired, errors.FileReferenceEmpty, errors.FileReferenceInvalid) as e:
                last_exc = e
                # file_reference went stale (long download / old link): re-read the message.
                if state.message_id is None:
                    break
                async with state.lock:
                    if state.file_id is fid:
                        logger.info(f"file_reference expired for message {state.message_id}, refreshing")
                        new_fid = await self.refresh_file_properties(state.message_id)
                        state.location = await self.get_location(new_fid)
                        state.file_id = new_fid
                continue  # retry immediately with the new reference
            except errors.FloodWait as e:
                last_exc = e
                await asyncio.sleep(min(float(e.value), 30.0) + 0.5)
            except (OSError, ConnectionError, AttributeError) as e:
                # TimeoutError is an OSError. Session/TCP link to the DC died:
                # evict so the retry builds a fresh one instead of re-using a corpse.
                last_exc = e
                logger.warning(f"Media session DC {fid.dc_id} failed at offset {off}: {e!r}. Evicting.")
                if session is not None:
                    self._evict_session(fid.dc_id, session)
            except Exception as e:  # incl. StreamError, other RPC errors
                last_exc = e
                logger.warning(f"GetFile failed at offset {off} (attempt {attempt + 1}): {e!r}")
            if attempt < retries:
                await asyncio.sleep(min(0.25 * (2 ** attempt), 3.0))
        raise StreamError(f"giving up on offset {off} after {retries + 1} attempts: {last_exc!r}") from last_exc

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
        message_id: Optional[int] = None,
    ):
        """
        Custom generator that yields the bytes of the media file.
        Keeps Var.STREAM_PREFETCH parts in flight so Telegram latency overlaps
        with sending to the client, every part is retried on failure, and any
        unrecoverable error is RAISED (never swallowed) so the caller can abort
        the connection instead of delivering a short file.
        Modded from <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py#L20>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        work_loads[index] += 1
        pending: collections.deque = collections.deque()
        try:
            logger.debug(f"Starting to yielding file with client {index}.")
            state = _FetchState(file_id, await self.get_location(file_id), message_id)
            file_size = getattr(file_id, "file_size", 0) or 0
            depth = max(1, Var.STREAM_PREFETCH)
            next_part = 0

            def need_for(part: int) -> int:
                n = last_part_cut if part == part_count - 1 else chunk_size
                if file_size:
                    n = min(n, file_size - (offset + part * chunk_size))
                return max(n, 1)

            def schedule() -> None:
                nonlocal next_part
                while len(pending) < depth and next_part < part_count:
                    pending.append(asyncio.ensure_future(
                        self._fetch_part(state, offset + next_part * chunk_size, chunk_size, need_for(next_part))
                    ))
                    next_part += 1

            for part in range(part_count):
                schedule()
                chunk = await pending.popleft()
                schedule()  # refill the window before we hand the chunk out

                start = first_part_cut if part == 0 else 0
                end = last_part_cut if part == part_count - 1 else None
                if start == 0 and end is None:
                    yield chunk
                else:
                    yield memoryview(chunk)[start:end]
            logger.debug(f"Finished yielding file with {part_count} parts.")
        finally:
            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            work_loads[index] -= 1

    
    async def clean_cache(self) -> None:
        """
        function to clean the cache to reduce memory usage
        """
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logger.debug("Cleaned the cache")
