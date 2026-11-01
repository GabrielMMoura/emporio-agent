# CLAUDE.md

Read and follow [AGENTS.md](AGENTS.md). Everything there applies.

Claude Code specifics:

- Commit attribution is disabled in `.claude/settings.json`; do not add `Co-Authored-By` or "Generated with" lines by hand.
- Run commands through `uv run` so the project virtualenv is used.
