# TG AI Bot - Deployment Guide

## Prerequisites

- Python 3.10+
- Telegram API credentials (API_ID, API_HASH)
- Two Telegram bots:
  - **Userbot** - your personal account (uses Telethon)
  - **Control Bot** - admin control panel (uses Aiogram)

## Environment Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `telethon>=1.24.0` - for userbot (Telegram client)
- `aiohttp>=3.8.0` - async HTTP requests
- `python-dotenv>=0.19.0` - environment variables
- `aiogram>=3.0.0` - for control bot

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Telegram API (from my.telegram.org)
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_PHONE=+1234567890

# Control Bot Token (from @BotFather)
CONTROL_BOT_TOKEN=your_bot_token

# AI Service (from kilo.ai)
KILOCODE_API_KEY=your_kilo_api_key

# Admin ID (your Telegram user ID)
ADMIN_ID=your_user_id

# Optional: Bot name (used in AI responses)
bot_name=YourBotName
```

## Running the Bot

### Development

```bash
python main.py
```

This starts both:
1. **Userbot** - connects to your Telegram account and responds to messages
2. **Control Bot** - admin interface at @YourControlBot

### Production (with systemd)

Create `/etc/systemd/system/tg-ai-bot.service`:

```ini
[Unit]
Description=TG AI Userbot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tg-ai-bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-ai-bot
sudo systemctl start tg-ai-bot
```

## Using the Control Bot

1. Start @YourControlBot in Telegram
2. Use the keyboard menu:
   - 📊 **Статус** - view current settings
   - ⚙️ **Настройки** - toggle AI features
   - 💬 **Чаты** - manage white/blacklists
   - 🗑️ **Очистить историю** - clear AI memory
   - 🔄 **Перезапустить AI** - reset AI state

### Chat Management Commands

```
/add_white 123456 - add to whitelist (only respond there)
/del_white 123456 - remove from whitelist
/add_black 123456 - add to blacklist (never respond)
/del_black 123456 - remove from blacklist
/clear_white - clear whitelist (respond everywhere)
/clear_chat 123456 - clear history for specific chat
```

## Troubleshooting

### Bot not responding
- Check `storage.json` - ensure `enabled: true`
- Verify chat is not in blacklist
- For groups: bot must be mentioned or replied to

### AI not answering
- Check KILOCODE_API_KEY is valid
- View logs for API errors

### Control bot issues
- Verify CONTROL_BOT_TOKEN is correct
- Ensure ADMIN_ID matches your Telegram ID
