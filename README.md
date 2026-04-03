<![CDATA[<div align="center">

```
╔════════════════════════════════════════╗
║         🤖  TG AI USERBOT             ║
║   Your Telegram account, AI-powered   ║
╚════════════════════════════════════════╝
```

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Telethon](https://img.shields.io/badge/Telethon-1.24+-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-009CDE?style=flat-square&logo=telegram&logoColor=white)](https://aiogram.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**An AI userbot that responds to Telegram messages on behalf of your account.**  
Controlled through a separate admin bot. No servers required — runs on your machine.

</div>

---

## ✨ Features

- 🤖 **AI responses** — powered by KiloCode API (free models available)
- 💬 **Smart triggers** — responds to DMs, @mentions, and replies to bot messages
- 🎛️ **Admin control bot** — manage everything without touching code
- 📊 **Stats & monitoring** — uptime, AI calls, error counters
- 🚦 **Rate limiting** — per-chat cooldown to prevent spam
- 🔁 **Retry logic** — automatic retries with exponential backoff on API errors
- 💾 **Persistent history** — chat context survives restarts
- 📝 **Rotating logs** — `bot.log` with automatic rotation (5 MB × 3 files)
- 🛡️ **Atomic writes** — storage never gets corrupted mid-write
- ⚡ **Graceful shutdown** — handles SIGTERM cleanly (systemd-friendly)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                   main.py                        │
│  (logging setup · env validation · SIGTERM)      │
└──────────────┬──────────────┬───────────────────┘
               │              │
       ┌───────▼──────┐ ┌────▼──────────┐
       │  userbot.py  │ │control_bot.py │
       │  (Telethon)  │ │  (aiogram)    │
       │  your acct   │ │  admin UI     │
       └───────┬──────┘ └────┬──────────┘
               │              │
       ┌───────▼──────────────▼──────────┐
       │         ai_service.py            │
       │  (KiloCode API · retry · history)│
       └───────────────┬─────────────────┘
                       │
              ┌────────▼────────┐
              │   storage.py    │
              │ (JSON · locks)  │
              └─────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/yourname/tg-ai-bot.git
cd tg-ai-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .envexample .env
nano .env  # fill in your credentials
```

### 4. Run

```bash
python main.py
```

On first run, Telethon will prompt you to enter the SMS code from Telegram.

---

## ⚙️ Configuration

All environment variables go in `.env`:

| Variable | Description | Where to get |
|---|---|---|
| `TG_API_ID` | Telegram API ID | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TG_API_HASH` | Telegram API Hash | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TG_PHONE` | Your phone number | e.g. `+79001234567` |
| `CONTROL_BOT_TOKEN` | Admin bot token | [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | Your Telegram user ID | [@userinfobot](https://t.me/userinfobot) |
| `KILOCODE_API_KEY` | KiloCode API key | [kilo.codes](https://kilo.codes) |
| `BOT_NAME` | Bot's display name | Anything you like |

Runtime settings (managed via control bot, stored in `storage.json`):

| Setting | Default | Description |
|---|---|---|
| `enabled` | `true` | Master on/off switch |
| `reply_in_dm` | `true` | Respond to private messages |
| `reply_to_mentions` | `true` | Respond when mentioned in groups |
| `reply_to_replies` | `true` | Respond to replies to bot's messages |
| `response_delay` | `1.5` | Typing delay before response (sec) |
| `rate_limit_seconds` | `3.0` | Minimum time between replies per chat |
| `ai_model` | `minimax/minimax-m2.5:free` | AI model to use |
| `ai_temperature` | `0.85` | Creativity (0.0–2.0) |
| `ai_max_tokens` | `500` | Max response length |

---

## 🎛️ Control Bot Commands

Start the control bot with `/start`. You'll get a keyboard with:

| Button | Action |
|---|---|
| 📊 Статус | Full status overview |
| ⚙️ Настройки | Toggle settings, change name/delay/model |
| 💬 Чаты | Manage white/blacklists |
| 🗑️ Очистить историю | Wipe all AI context |
| 🔄 Перезапустить AI | Same as clearing history |
| 📈 Статистика | Uptime + API stats |

**Slash commands:**

```
/ping               — check if bot is alive
/add_white <id>     — add chat to whitelist
/del_white <id>     — remove from whitelist
/add_black <id>     — add chat to blacklist
/del_black <id>     — remove from blacklist
/clear_white        — clear entire whitelist
/clear_chat <id>    — clear history for one chat
```

---

## 📦 Available AI Models

Switch models anytime from ⚙️ Настройки → 🤖 Сменить модель:

- `minimax/minimax-m2.5:free` *(default)*
- `google/gemini-2.0-flash-exp:free`
- `meta-llama/llama-3.3-70b-instruct:free`
- `deepseek/deepseek-r1:free`
- `qwen/qwen3-235b-a22b:free`

All via [KiloCode](https://kilo.codes) free tier.

---

## 📁 Project Structure

```
tg-ai-bot/
├── main.py           # Entry point: logging, env check, SIGTERM
├── userbot.py        # Telethon userbot logic
├── control_bot.py    # aiogram admin bot
├── ai_service.py     # KiloCode API client
├── storage.py        # Thread-safe JSON settings
├── requirements.txt
├── .envexample       # Environment template
├── storage.json      # Runtime settings (auto-created)
├── histories.json    # Chat history persistence (auto-created)
└── bot.log           # Rotating log file (auto-created)
```

---

## 🔧 Running as a systemd service

```ini
# /etc/systemd/system/tg-ai-bot.service
[Unit]
Description=TG AI Userbot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/tg-ai-bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable tg-ai-bot
sudo systemctl start tg-ai-bot
sudo journalctl -u tg-ai-bot -f
```

---

## 📄 License

MIT — do whatever you want.
]]>
