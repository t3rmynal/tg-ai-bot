# changelog

## 3.0.0 - unreleased

- the terminal tui is gone, the bot now runs headless with a local management api on
  127.0.0.1:8471
- new desktop app (tauri + next.js): dashboard with a live activity feed, qr sign in,
  providers, personas, chat lists, behavior settings and a test chat
- new providers: willow (willowapi.digital) and opencode zen
- live model discovery: fetch the model list from any openai compatible provider
- update check against github releases, shown in settings
- python package restructure into tgai/, pyproject packaging, scripts/qa.sh gate

## 2.0.0

- english rewrite, qr only login, ai personas, provider registry, two layer rate limiting
