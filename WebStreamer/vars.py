# This file is a part of TG-FileStreamBot
# Coding : Goutham Josh [ GouthamSER ]

import sys
from os import environ
from dotenv import load_dotenv

load_dotenv()


class Var(object):
    MULTI_CLIENT = str(environ.get("MULTI_CLIENT", True))
    API_ID = int(environ.get("API_ID"))
    API_HASH = str(environ.get("API_HASH"))
    BOT_TOKEN = str(environ.get("BOT_TOKEN"))
    SLEEP_THRESHOLD = int(environ.get("SLEEP_THRESHOLD", "60"))  # 1 minte
    WORKERS = int(environ.get("WORKERS", "6"))  # 6 workers = 6 commands at once
    _bin_channel_raw = environ.get("BIN_CHANNEL")
    if not _bin_channel_raw:
        sys.exit("BIN_CHANNEL is required — set it to your log/bin channel ID")
    BIN_CHANNEL = int(
        _bin_channel_raw
    )  # you NEED to use a CHANNEL when you're using MULTI_CLIENT
    PORT = int(environ.get("PORT", 8080))
    BIND_ADDRESS = str(environ.get("WEB_SERVER_BIND_ADDRESS", "0.0.0.0"))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
    HAS_SSL = str(environ.get("HAS_SSL", "true").lower()) in ("1", "true", "t", "yes", "y")
    NO_PORT = str(environ.get("NO_PORT", "true").lower()) in ("1", "true", "t", "yes", "y")
    HASH_LENGTH = int(environ.get("HASH_LENGTH", 6))
    if not 5 < HASH_LENGTH < 64:
        sys.exit("Hash length should be greater than 5 and less than 64")
    FQDN = str(environ.get("FQDN", BIND_ADDRESS))
    URL = "http{}://{}{}/".format(
            "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
        )
    KEEP_ALIVE = str(environ.get("KEEP_ALIVE", "0").lower()) in  ("1", "true", "t", "yes", "y")
    DEBUG = str(environ.get("DEBUG", "0").lower()) in ("1", "true", "t", "yes", "y")
    USE_SESSION_FILE = str(environ.get("USE_SESSION_FILE", "0").lower()) in ("1", "true", "t", "yes", "y")
    ALLOWED_USERS = [x.strip("@ ") for x in str(environ.get("ALLOWED_USERS", "") or "").split(",") if x.strip("@ ")]
    # MongoDB
    DATABASE_URI = str(environ.get("DATABASE_URI", ""))
    DATABASE_NAME = str(environ.get("DATABASE_NAME", "FileStreamBot"))
    USERS_COLLECTION = str(environ.get("USERS_COLLECTION", "fsb_users"))
    # Force-subscribe channel username or ID (e.g. "@mychannel" or "-100xxx")
    # Leave empty to disable.
    _fsub_raw = environ.get("FSUB_CHANNEL", "").strip()
    FSUB_CHANNEL = int(_fsub_raw) if _fsub_raw.lstrip("-").isdigit() else (_fsub_raw or None)
    # Bot owner user_id (for /stats and /broadcast)
    OWNER_ID = int(environ.get("OWNER_ID", "0"))
