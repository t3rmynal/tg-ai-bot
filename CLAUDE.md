# CLAUDE.md

Read AGENTS.md first, it is the source of truth for layout, commands, rules, and the
locked design section.

Claude specific notes:

- if the untracked files `rules.md` and `handoff.md` exist in the repo root, read them
  before doing anything else: `rules.md` governs commits and copy, `handoff.md` carries
  the state of ongoing work between sessions
- run `scripts/qa.sh` before claiming a task is done
- readme and docs prose goes through the humanizer skill before committing
- keep changes surgical: this codebase is small on purpose, do not add speculative
  abstractions or dependencies
