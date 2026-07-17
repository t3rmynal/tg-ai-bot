```
████████╗ ██████╗          █████╗ ██╗
╚══██╔══╝██╔════╝         ██╔══██╗██║
   ██║   ██║  ███╗        ███████║██║     Telegram AI
   ██║   ██║   ██║        ██╔══██║██║       Userbot
   ██║   ╚██████╔╝        ██║  ██║██║
   ╚═╝    ╚═════╝         ╚═╝  ╚═╝╚═╝
```

An AI userbot for your own Telegram account. It watches incoming messages and
answers them for you with an LLM, using the persona, provider and triggers you
pick. A dark desktop app drives everything, and the bot itself runs headless.

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Telethon](https://img.shields.io/badge/telethon-1.24+-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

## What it does

You run it on your own machine and scan a QR code to sign into your Telegram
account. From then on it answers messages on your account with an AI model. A
local management server runs on the same event loop as the Telethon client, so a
setting you change applies to the next message with no reconnect.

It only replies where you tell it to: dms, group mentions, replies to your own
messages, or a fixed whitelist of chats. A blacklist wins over everything.

## Two parts

- **The core** (`tgai/`) is a headless Python process: the Telethon client plus a
  local API on `127.0.0.1:8471`. It has no terminal ui.
- **The desktop app** (`desktop/`) is a Tauri and Next.js window that talks to
  that API. It handles qr login, providers, personas, chats, settings, a live
  activity feed and a test chat.

## Features

- QR login. No phone number, no SMS code. 2FA is handled if your account has it.
- Works with any OpenAI-compatible provider. NVIDIA, Willow, OpenCode Zen,
  OpenRouter, Groq, Google AI Studio and local Ollama come preloaded, and you can
  add your own. Model lists can be fetched live from the provider.
- Four built-in personas plus a custom prompt you write yourself or have the AI
  write for you.
- Optional outbound proxy: a manual socks5 or http pool, or Mullvad exit nodes,
  with rotation. The Telegram connection can use it too.
- Two-layer rate limiting so you stay under free-tier caps instead of eating 429s.
- Per-chat history that survives restarts, a live activity feed and stats.
- Light and dark themes that follow the system, with a manual toggle.
- Replies default to English, switchable to Russian per persona.

## Supported providers

| Provider | Notes | Get a key |
|---|---|---|
| NVIDIA NIM | free models, about 40 req/min | [build.nvidia.com](https://build.nvidia.com) |
| Willow | one key, many frontier models | [willowapi.digital](https://willowapi.digital) |
| OpenCode Zen | multi-model gateway | [opencode.ai/zen](https://opencode.ai/zen) |
| OpenRouter | varies by model | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Groq | about 30 req/min | [console.groq.com/keys](https://console.groq.com/keys) |
| Google AI Studio | about 5 req/min | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Ollama | local, hardware-bound | runs on `localhost`, no key |
| OpenAI-compatible | your endpoint | any base url you point it at |

## Quick start

Run the core:

```bash
git clone https://github.com/canary443/tg-ai-bot.git
cd tg-ai-bot
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m tgai
```

Then open the desktop app. For development it runs against the core you just
started:

```bash
pnpm -C desktop install
pnpm -C desktop tauri dev
```

`scripts/dev.sh` starts the core, waits for it, and opens the window in one step.

The app walks you through setup: your Telegram `API_ID` and `API_HASH` from
[my.telegram.org/apps](https://my.telegram.org/apps), then the QR code. Open
Telegram on your phone, go to Settings, Devices, Link Desktop Device, and point
the camera at the code. Everything you enter is saved to `config.json`, which is
gitignored along with the session file and chat history.

## Desktop builds

Tagged releases (`vX.Y.Z`) build self-contained apps for macOS and Windows
through GitHub Actions and attach them to the release. The Python core is bundled
as a sidecar, so a released build needs nothing else installed.

To build locally on macOS:

```bash
PYTHON=.venv/bin/python scripts/build-sidecar.sh
pnpm -C desktop tauri build
```

## Proxy and Mullvad

Turn on the proxy in the app to send provider traffic through a socks5 or http
proxy. Add proxies by hand, or switch the source to Mullvad: connect the Mullvad
app first, then pull the socks5 exit list and the bot routes through those
servers. Rotation can move to a new exit on every call or every n calls.

## Personas and the AI prompt generator

Pick one of the four templates (friendly, witty, assistant, formal), or write
your own. The generator asks for a name, whether it acts human or like an AI, a
tone, and any extra flavor, then asks your active provider for a finished system
prompt. If the call fails it falls back to a local template, so you always end up
with something usable. Safety guardrails are appended either way.

## How rate limiting works

A shared limiter spaces calls so the combined traffic stays under the provider's
requests-per-minute cap. On top of that, a 429 or a 5xx triggers a retry that
honours `Retry-After` (seconds or an HTTP date), caps the backoff and adds a bit
of jitter. If a reply still cannot go through, the bot skips it quietly, and the
next message tries again.

## Contact

Questions or ideas: [@aimwork](https://t.me/aimwork) on Telegram.

## License

MIT. See [LICENSE](LICENSE).
