# This file is a part of TG-FileStreamBot

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from WebStreamer.vars import Var

logger = logging.getLogger("db")

_client: AsyncIOMotorClient = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(Var.DATABASE_URI)
        _db = _client[Var.DATABASE_NAME]
    return _db


def users_col():
    return get_db()[Var.USERS_COLLECTION]


# ── Users ──────────────────────────────────────────────────────────────────────

async def add_user(user_id: int, first_name: str = "", username: str = ""):
    await users_col().update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "first_name": first_name,
            "username": username,
        }},
        upsert=True,
    )


async def get_all_users():
    return await users_col().find({}, {"_id": 1}).to_list(length=None)


async def get_user_count() -> int:
    return await users_col().count_documents({})
