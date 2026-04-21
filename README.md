# TG AI Userbot

An AI bot that replies to your Telegram messages on connected Telegram Account. Managed via a admin bot.

## Stack

Python 3.11+, Telethon, aiogram, [KiloCode API](https://kilo.codes) (free model).

## Setup

```bash
git clone https://github.com/t3rmynal/tg-ai-bot.git
cd tg-ai-bot
pip install -r requirements.txt
cp .envexample .env   # fill in credentials
python main.py
```

## .env

| Variable | Where to get |
|---|---|
| `TG_API_ID`, `TG_API_HASH` | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TG_PHONE` | your number |
| `CONTROL_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | [@userinfobot](https://t.me/userinfobot) |
| `KILOCODE_API_KEY` | [kilo.codes](https://kilo.codes) |
| `BOT_NAME` | any name |

## Usage

Send `/start` to the admin bot

## License

MIT
