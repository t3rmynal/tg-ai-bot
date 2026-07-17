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

Do not change fonts, tokens, or the light+dark parity without the owner asking.

Visual language: operation-zero (opzero.ru). Electric blue accent, beveled top-right
corners on cards and panels, thin rules with a diagonal notch under page titles and
dialog titles, heavy uppercase display type, mono digits everywhere. Light and dark
both follow the system by default (`prefers-color-scheme`), a header toggle can pin
one via `data-theme` + localStorage. Both themes are first class, never dark-only.

Colors (defined in `desktop/src/app/globals.css`, light values first, dark in parens):

```
--bg-0      #edf1f7 (#070a0f)   page background, tinted in light, near-black in dark
--bg-1      #ffffff (#0d121a)   panels, sidebar, cards
--bg-2      #f5f8fb (#121826)   inputs, nested rows
--bg-3      #e7edf4 (#1a2231)   hover, active row, overlays
--line-1    #dde4ee (#1d2634)   default hairline border
--line-2    #c7d2e0 (#2c3849)   emphasized border, input border
--line-glow rgba(*, 0.28-0.32)  thin luminous rules, decoration only
--text-1    #0a1119 (#eaf0f7)   primary text
--text-2    #42536a (#93a3b5)   secondary, labels, hints
--text-3    #5d7085 (#64758a)   muted, placeholders, timestamps
--accent    #0a84ff (#3ea0ff)   interactive: links, active nav, focus, switches, primary buttons
--accent-2  #4db5ff (#6bc1ff)   accent gradient partner (hero-grad, qr countdown)
--accent-dim rgba(*, 0.1-0.12)  interactive hover/selected fills
--accent-fg #ffffff (#05080d)   text on solid accent fills
--warn      #a86c15 (#d0a24a)   rate-limit waits, expiring qr, unsupported features
--danger    #c93a46 (#d97078)   errors, blacklist, destructive actions, missing keys
```

no green anywhere. success is communicated with the accent color or plain text, not a
separate ok token.

Typography: Space Grotesk (display: page titles, stat digits, dialog titles, uppercase),
IBM Plex Sans (ui body), IBM Plex Mono (model ids, chat ids, key hints, timestamps, ghost
index numbers, prompts, feed text; tabular-nums for digits). Bundled via @fontsource,
never a cdn. Sizes 12/13/14/16/22/30/44, weights 400/500/600 only. Labels: 12px, --text-2,
letter-spacing 0.08em, lowercase. Eyebrows: 12px, --text-3, letter-spacing 0.18em, uppercase.

Signature elements: `.bevel` / `.bevel-lg` / `.bevel-sm` clip the top-right corner (14px,
22px, 8px). `.notch-rule` draws the accent rule with a diagonal drop under page and dialog
titles. Page masthead (`PageHeader`) pairs an eyebrow + big display title with an outlined
`.ghost-num` page index (01..07) matching the sidebar nav numbers. Card headers carry a
small accent tick before the label. One shared `Segmented` component for every mode picker,
do not hand-roll another button-row toggle.

Spacing on a 4px grid (4..48), page gutter 24, sidebar 220. Radii: 4 inputs, 6 buttons and
cards, 10 dialogs. Motion: 150ms ease-out hover/press, 200ms dialogs, no springs, respect
prefers-reduced-motion. Primary buttons are accent fill with a small bevel and a 1px press
translate. Switches are bordered tracks with a white thumb, accent fill when on.
