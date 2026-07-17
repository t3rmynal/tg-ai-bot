# rules for contributors and agents

This file is committed on purpose: if you forked this repo and pointed a coding agent at it,
these are the house rules. AGENTS.md covers layout, commands and the locked design system.

## keep things in sync

- when behavior, endpoints or settings change, update AGENTS.md and README.md in the same
  change, and add a line to CHANGELOG.md
- config.json format stays backward compatible: new keys get defaults and arrive via
  deep-merge, old files must keep loading
- run scripts/qa.sh before calling any task done

## versioning

- semver. the single source of truth is `__version__` in tgai/__init__.py
- keep these in sync with it: pyproject.toml [project].version, desktop/package.json,
  desktop/src-tauri/tauri.conf.json
- patch for fixes, minor for features, major for breaking config or api changes

## releases

- finish CHANGELOG.md notes for the version, sync the version numbers, commit
- tag `vX.Y.Z`, push the tag, create a github release with the changelog section as notes
- the app checks the github releases of this repo (config key `update_repo`) and shows an
  update notice in settings, so releases only count if the tag follows `vX.Y.Z`
- forks: set `update_repo` in config.json (or change the default in tgai/updates.py) to your
  own `owner/repo` if you want your fork to be its own update channel

## style

- code comments lowercase, in every language
- no em or en dashes anywhere, qa.sh fails on them
- ui copy short and plain, no marketing language
