# changelog

## 3.0.0 - 2026-07-17

- the terminal tui is gone, the bot now runs headless with a local management api on
  127.0.0.1:8471
- new desktop app (tauri + next.js): dashboard with a live activity feed, qr sign in,
  providers, personas, chat lists, behavior settings and a test chat
- desktop ui redesigned around the operation zero visual language: electric blue accent,
  beveled corners, light and dark by system with a manual toggle
- new providers: willow (willowapi.digital) and opencode zen
- live model discovery: fetch the model list from any openai compatible provider
- update check against github releases, shown in settings
- optional outbound proxy: manual socks5/http pool or mullvad exit nodes, with
  rotation (off, per call, every n calls) and a connectivity test. can also route
  the telegram connection
- python package restructure into tgai/, pyproject packaging, scripts/qa.sh gate
- self-contained desktop builds for macos and windows, python core bundled as a
  pyinstaller sidecar, release ci on tagged versions
- design polish pass: real depth in light mode, page mastheads with an outlined index
  number, one shared segmented control, fixed contrast on the missing api key state

## 2.0.0

- english rewrite, qr only login, ai personas, provider registry, two layer rate limiting
