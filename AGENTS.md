# AGENTS.md

Guide for coding agents working in this repo.

## what this is

An AI userbot for a personal Telegram account. Python core (Telethon) answers incoming
messages with an LLM. A local FastAPI server on 127.0.0.1:8471 is the only management
surface. The desktop app in `desktop/` (Tauri v2 + Next.js static export) talks to that API.

## layout

- `tgai/` - python package: config store, provider registry, personas, AI client, rate limiter
- `tgai/telegram/` - Telethon client: auth state machine (QR login), message handlers
- `tgai/api/` - FastAPI routes. keep routes thin, logic lives in the modules above
- `desktop/` - Tauri + Next.js app. pages in `src/app/`, pieces in `src/components/`, data layer in `src/lib/`
- `tests/` - pytest, no network and no real Telegram. fakes live in `tests/conftest.py`
- `scripts/qa.sh` - the QA gate. run it before finishing any task

## commands

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # first time
.venv/bin/python -m tgai            # run the bot + api server
.venv/bin/python -m pytest -q       # tests
scripts/qa.sh                       # ruff + pytest + long-dash grep + frontend lint/build
scripts/dev.sh                      # start core, wait, open the tauri window
pnpm -C desktop dev                 # ui in a browser on :3000
pnpm -C desktop tauri dev           # desktop window (needs the core running)
PYTHON=.venv/bin/python scripts/build-sidecar.sh   # bundle the core for a release build
pnpm -C desktop tauri build         # self-contained app (run build-sidecar.sh first)
```

Release binaries for macOS and Windows are built by `.github/workflows/release.yml`
on a `vX.Y.Z` tag. See rules_public.md for the release and versioning steps.

## rules

- comments lowercase everywhere, including shell and toml
- no em dashes (U+2014) or en dashes (U+2013) anywhere in the repo. qa.sh fails on them
- ui copy is short and plain. no marketing words, no exclamation points
- provider registry is data driven: a provider is a dict in `tgai/providers.py`, every
  provider speaks the OpenAI /chat/completions dialect. do not add per-provider branches
  to the http client
- api keys never leave the backend unmasked. GET responses carry `key_set` and a masked hint
- runtime files (`config.json`, `histories.json`, `userbot.session`, `bot.log`) stay
  gitignored and their formats stay backward compatible
- versioning, release and doc-sync rules live in `rules_public.md`. version source of truth
  is `__version__` in `tgai/__init__.py`
- local untracked notes may exist in `rules.md` and `handoff.md`. if present, read
  `rules.md` before committing and `handoff.md` before starting work

## design (locked)

Do not change fonts, tokens, or the green-is-success-only rule without the owner asking.

Colors (dark only, defined in `desktop/src/app/globals.css`):

```
--bg-0      #0b0e14                       app background
--bg-1      #10141c                       panels, sidebar
--bg-2      #151a24                       cards, inputs, rows
--bg-3      #1b2130                       hover, active row, overlays
--line-1    #1c2330                       default hairline border
--line-2    #28303f                       emphasized border
--line-glow rgba(140,169,204,0.22)        thin luminous rules, decoration only
--text-1    #e8edf4                       primary text
--text-2    #9aa7b8                       secondary, labels
--text-3    #5d6a7d                       muted, placeholders, timestamps
--accent    #8ca9cc                       interactive: links, active nav, focus, switches
--accent-dim rgba(140,169,204,0.12)       interactive hover/selected fills
--ok        #3ecf6e                       success only: bot-on dot, signed-in badge,
                                          reply feed rows, success toasts. nowhere else
--ok-dim    rgba(62,207,110,0.12)
--warn      #c9a05f                       rate-limit waits, expiring qr
--danger    #c56a73                       errors, blacklist, destructive actions
--danger-dim rgba(197,106,115,0.12)
```

Typography: IBM Plex Sans (ui), IBM Plex Mono (model ids, chat ids, key hints, timestamps,
stats digits, prompts, feed text; tabular-nums for digits). Bundled via @fontsource, never
a cdn. Sizes 12/13/14/16/20/26, weights 400/500/600 only. Labels: 12px, --text-2,
letter-spacing 0.04em, lowercase.

Spacing on a 4px grid (4..48), page gutter 24, sidebar 208. Radii: 4 inputs, 6 buttons and
cards, 10 dialogs. Motion: 120ms ease-out hover, 200ms dialogs, no springs, respect
prefers-reduced-motion. Primary buttons are off-white fill with #0b0e14 text. Green never
appears on generic buttons or toggles.
