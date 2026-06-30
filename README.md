```
████████╗ ██████╗          █████╗ ██╗
╚══██╔══╝██╔════╝         ██╔══██╗██║
   ██║   ██║  ███╗        ███████║██║     Telegram AI 
   ██║   ██║   ██║        ██╔══██║██║       Userbot
   ██║   ╚██████╔╝        ██║  ██║██║
   ╚═╝    ╚═════╝         ╚═╝  ╚═╝╚═╝
```

An AI userbot for your own Telegram account. It watches incoming messages and
replies using LLMs for you, with the persona, provider and triggers you pick from a console
menu.

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Telethon](https://img.shields.io/badge/telethon-1.24+-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

## What it does

You run it on your machine, scan a QR code to sign into your telegram account, and it starts answering
messages on your account using an AI text generation model. The console keeps running next to the
Telethon client on the same event loop, so you can flip a setting and it applies
to the next message without a reconnect.

It only replies where you tell it to: DMs, group mentions, replies to your own
messages, or a fixed whitelist of chats. A blacklist has a priority.

## Features

- QR login. No phone number, no SMS code. 2FA is handled if your account has it.
- Works with any OpenAI-compatible provider. NVIDIA, OpenRouter, Groq, Google AI
  Studio and also Local Ollama Models are preloaded, and you can add your own.
- Four built-in personas (system prompts) plus a custom prompt you can write or have the AI write
  for you (see below).
- Two-layer rate limiting so you stay under free-tier caps instead of eating 429s.
- Per-chat history that survives restarts, a live activity monitor, and a stats
  screen (AI will always get the context of the chat).
- Replies default to English. Switch to Russian per persona in the menu.

## Supported providers

| Provider | Free tier | Get a key |
|---|---|---|
| NVIDIA NIM | ~40 req/min, free models usage | [build.nvidia.com](https://build.nvidia.com) |
| OpenRouter | varies by model | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Groq | ~30 req/min | [console.groq.com/keys](https://console.groq.com/keys) |
| Google AI Studio | ~5 req/min | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Ollama | local, hardware-bound | runs on `localhost`, no key |
| OpenAI-compatible | your endpoint | any base URL you point it at |

## Quick start

```bash
git clone https://github.com/t3rmynal/tg-ai-bot.git
cd tg-ai-bot
pip install -r requirements.txt
python main.py
```

On first run a short wizard asks for your Telegram `API_ID` and `API_HASH` (from
[my.telegram.org/apps](https://my.telegram.org/apps)), then your provider, key,
model and persona. After that it shows a QR code. Open Telegram on your phone,
go to Settings, Devices, Link Desktop Device, and point the camera at the code.

Everything you enter is saved to `config.json`, which is gitignored along with the
session file and chat history.

## Personas and the AI prompt generator

Pick one of the four templates (friendly, witty, assistant, formal) from the
persona menu, or build your own. The generator asks for a name, whether it acts
human or like an AI, a tone, and any extra flavor, then sends that to your active
provider and gets back a finished system prompt. If the call fails it falls back
to a local template, so you always end up with something usable. Safety
guardrails are appended either way.

## How rate limiting works

A shared limiter spaces calls so the combined traffic stays under the provider's
requests-per-minute cap. On top of that, a 429 or a 5xx triggers a retry that
honours `Retry-After` (seconds or an HTTP date), caps the backoff and adds a bit
of jitter. If a reply still cannot go through, the bot skips it quietly. Nothing
about the limit leaks into the chat, and the next message tries again.

## Contact

Questions or ideas: [@aimwork](https://t.me/aimwork) on Telegram.

## License

MIT. See [LICENSE](LICENSE).
