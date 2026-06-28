<h1 align="center">⚡ Telegram File Stream Bot</h1>

<p align="center">
  <a href="https://github.com/GouthamSER/TG-FileStreamBot">
    <img src="https://socialify.git.ci/GouthamSER/TG-FileStreamBot/image?description=1&font=Source%20Code%20Pro&forks=1&issues=1&logo=https://telegra.ph/file/01385a9f4cf0419682b87.png&pattern=Circuit%20Board&pulls=1&stargazers=1&theme=Dark" alt="Cover Image" width="650">
  </a>
</p>

<p align="center">
  <b>Turn any Telegram file into an instant direct download / streaming link.</b><br>
  No waiting for the full file to download first — just send it, get the link.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10-blue?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Pyrogram-Pyrofork-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white">
  <img src="https://img.shields.io/badge/MongoDB-optional-47A248?style=for-the-badge&logo=mongodb&logoColor=white">
  <img src="https://img.shields.io/badge/license-AGPL--3.0-green?style=for-the-badge">
</p>

<p align="center">
  <a href="https://github.com/GouthamSER/TG-FileStreamBot/issues">🐞 Report a Bug</a>
  ·
  <a href="https://github.com/GouthamSER/TG-FileStreamBot/issues">✨ Request a Feature</a>
</p>

<hr>

<details open="open">
  <summary><b>📑 Table of Contents</b></summary>
  <ol>
    <li><a href="#-about-this-bot">About This Bot</a></li>
    <li>
      <a href="#-how-to-deploy">How to Deploy</a>
      <ul>
        <li><a href="#run-locally--vps">Run Locally / VPS</a></li>
        <li><a href="#deploy-using-docker">Deploy using Docker</a></li>
        <li><a href="#deploy-using-docker-compose">Deploy using docker-compose</a></li>
        <li><a href="#deploy-on-koyeb--heroku">Deploy on Koyeb / Heroku</a></li>
      </ul>
    </li>
    <li>
      <a href="#-configuration">Configuration</a>
      <ul>
        <li><a href="#mandatory-vars">Mandatory Vars</a></li>
        <li><a href="#optional-vars">Optional Vars</a></li>
        <li><a href="#mongodb--user-tracking-optional">MongoDB / User Tracking</a></li>
        <li><a href="#force-subscribe-optional">Force-Subscribe</a></li>
        <li><a href="#multi-client-support">Multi-Client Support</a></li>
      </ul>
    </li>
    <li><a href="#-how-to-use">How to Use</a></li>
    <li><a href="#-admin-commands">Admin Commands</a></li>
    <li><a href="#-contact">Contact</a></li>
    <li><a href="#-credits">Credits</a></li>
    <li><a href="#-license">License</a></li>
  </ol>
</details>

<hr>

## 🚀 About This Bot

<p align="center">
    <img src="https://telegra.ph/file/a8bb3f6b334ad1200ddb4.png" height="100" width="100" alt="Telegram Logo">
</p>

<p align="center">
    Send any file to this bot and get an instant direct download / streaming link in return.
</p>

| | |
|---|---|
| ✅ | Direct download links with original filename |
| ✅ | File size shown in the reply |
| ✅ | Multi-client support to dodge flood limits |
| ✅ | Supports documents, videos, audio, photos, stickers & more |
| ✅ | Optional MongoDB user tracking |
| ✅ | Optional Force-Subscribe (FSub) gating |
| ✅ | Built-in `/stats` and `/broadcast` for the bot owner |
| ✅ | `uvloop`-powered event loop for faster I/O |

<hr>

## 📦 How to Deploy

### Run Locally / VPS

```sh
git clone https://github.com/GouthamSER/TG-FileStreamBot
cd TG-FileStreamBot
python3 -m venv ./venv
. ./venv/bin/activate
pip3 install -r requirements.txt
python3 -m WebStreamer
```

Stop with <kbd>CTRL</kbd>+<kbd>C</kbd>.

> **Run 24/7 on a VPS with tmux:**
> ```sh
> sudo apt install tmux -y
> tmux
> python3 -m WebStreamer
> ```
> Detach with <kbd>CTRL</kbd>+<kbd>B</kbd> then <kbd>D</kbd>. Bot keeps running after you close SSH.

### Deploy using Docker

```sh
git clone https://github.com/GouthamSER/TG-FileStreamBot
cd TG-FileStreamBot
docker build . -t fsb
```

Create your `.env` file, then run:

```sh
docker run -d --restart unless-stopped --name fsb \
  -v /PATH/TO/.env:/app/.env \
  -p 8080:8080 \
  fsb
```

> `PORT` in `.env` must match the exposed port. Example: `PORT=9000` → `-p 9000:9000`

Restart after changing `.env`:
```sh
docker restart fsb
```

### Deploy using docker-compose

```sh
sudo apt install docker-compose -y
git clone https://github.com/GouthamSER/TG-FileStreamBot
cd TG-FileStreamBot
```

Edit the variables inside `docker-compose.yml`, then:

```sh
sudo docker compose up -d
```

### Deploy on Koyeb / Heroku

1. Fork [this repo](https://github.com/GouthamSER/TG-FileStreamBot)
2. Set all env vars in the platform dashboard
3. `Procfile` → `web: python3 -m WebStreamer`
4. `.python-version` → `3.10`
5. Deploy 🚀

> ⚠️ **Koyeb (Dockerfile deploy):** container `EXPOSE`s `8080`. In Koyeb's service settings, set **Port → 8080** (and protocol HTTP) to match, or set `PORT=8080` env var if you change the exposed port. Health checks hit `/`.

<hr>

## ⚙️ Configuration

Create a `.env` file in the root directory (for local/VPS):

```sh
API_ID=452525
API_HASH=esx576f8738x883f3sfzx83
BOT_TOKEN=55838383:yourbottokenhere
BIN_CHANNEL=-1001234567890
PORT=8080
FQDN=yourdomain.com
HAS_SSL=True
```

### Mandatory Vars

| Variable | Description |
|----------|-------------|
| `API_ID` | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Bot token from [@BotFather](https://telegram.dog/BotFather) |
| `BIN_CHANNEL` | Channel ID where the bot forwards & stores files. Create a channel, forward any message to [@missrose_bot](https://telegram.dog/MissRose_bot) and reply `/id` to get the ID |

### Optional Vars

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_USERS` | _(empty)_ | Comma-separated Telegram user IDs/usernames allowed to use the bot. Leave empty for public access |
| `HASH_LENGTH` | `6` | Length of the hash in generated URLs. Must be between 6 and 63 |
| `SLEEP_THRESHOLD` | `60` | Seconds to sleep on flood wait before retrying |
| `WORKERS` | `6` | Max concurrent workers for handling updates |
| `PORT` | `8080` | Port the web server listens on |
| `WEB_SERVER_BIND_ADDRESS` | `0.0.0.0` | Server bind address |
| `FQDN` | _(bind address)_ | Your domain name, used for link generation |
| `HAS_SSL` | `True` | Set `True` to generate `https://` links |
| `NO_PORT` | `True` | Set `True` to hide the port from generated links (use when port is 80/443) |
| `KEEP_ALIVE` | `False` | Ping self every `PING_INTERVAL` seconds — handy for PaaS free tiers |
| `PING_INTERVAL` | `1200` | Ping interval in seconds (default 20 min) |
| `USE_SESSION_FILE` | `False` | Use session files instead of in-memory SQLite |
| `DEBUG` | `False` | Enable debug logging |

### MongoDB / User Tracking (optional)

Set `DATABASE_URI` to enable storing user IDs — required for `/stats` and `/broadcast`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URI` | _(empty)_ | MongoDB connection string. Leave empty to disable DB features entirely |
| `DATABASE_NAME` | `FileStreamBot` | Database name |
| `USERS_COLLECTION` | `fsb_users` | Collection used to store user IDs |
| `OWNER_ID` | `0` | Your Telegram user ID — required to use `/stats` and `/broadcast` |

> Only the user ID is stored — no message content, no file data, no byte tracking.

### Force-Subscribe (optional)

Require users to join a channel before they can use the bot.

| Variable | Default | Description |
|----------|---------|-------------|
| `FSUB_CHANNEL` | _(empty)_ | Channel username (`@mychannel`) or ID (`-100xxxxxxxxxx`) users must join. Leave empty to disable |

> The bot must be an **admin** in `FSUB_CHANNEL` to check membership.

### Multi-Client Support

Multi-client spreads Telegram API requests across multiple bots to avoid flood limits and handle more concurrent streams.

To enable, add extra bot tokens as env vars:

```sh
MULTI_TOKEN1=token_of_bot_1
MULTI_TOKEN2=token_of_bot_2
MULTI_TOKEN3=token_of_bot_3
```

Add as many as you need — no upper limit tested.

> ⚠️ **Important:** Add every multi-client bot to `BIN_CHANNEL` as an admin.

<hr>

## 📲 How to Use

> ⚠️ Add all bots (including multi-client ones) to `BIN_CHANNEL` as admins before starting.

| Command | Description |
|---------|-------------|
| `/start` | Check if the bot is running (also runs the FSub check if enabled) |

Simply forward or send any media file to the bot. It instantly replies with:
- 📄 File name
- 📦 File size
- 🔗 Direct download link
- Buttons: **Shortened** link + **Download** link

Links stay valid as long as the bot is running and `BIN_CHANNEL` is intact.

<hr>

## 🛠 Admin Commands

These require `OWNER_ID` and `DATABASE_URI` to be set, and only work for the owner in a private chat.

| Command | Description |
|---------|-------------|
| `/stats` | Shows total tracked users |
| `/broadcast` | Reply to any message with this command to send it to every tracked user |

<hr>

## 📬 Contact

Developed and maintained by **[GouthamSER](https://github.com/GouthamSER)**

[![GitHub](https://img.shields.io/badge/GitHub-GouthamSER-181717?style=for-the-badge&logo=github)](https://github.com/GouthamSER)
[![Telegram](https://img.shields.io/badge/Telegram-GouthamSER-2CA5E0?style=for-the-badge&logo=telegram)](https://t.me/im_goutham_josh)

<hr>

## 🙌 Credits

- **[GouthamSER](https://github.com/GouthamSER)** — Owner, Developer & Re-Edit
- **[EverythingSuckz](https://github.com/EverythingSuckz)** — Original author of TG-FileStreamBot
- **[eyaadh](https://github.com/eyaadh)** — Original streaming core from [Megatron Bot](https://github.com/eyaadh/megadlbot_oss)
- **[BlackStone](https://github.com/eyMarv)** — Multi-client support
- **[Dan Tès](https://telegram.dog/haskell)** — [Pyrogram](https://github.com/pyrogram/pyrogram) library

<hr>

## 📄 License

Copyright (C) 2026 [GouthamSER](https://github.com/GouthamSER) under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html).

This is free software — use, study, share and improve it under the terms of the AGPL-3.0 license.
