# Decisions and assumptions

One line per decision. Business rules decided by the project owner are marked **[owner]**.

## Technical

- Package manager: `uv` with a committed lockfile, for one reproducible install command; `pip install -e .` also works.
- Default model `gpt-4.1-mini`: reliable tool calling at low cost; overridable with `MODEL`.
- No `temperature` is sent to the API, so the same code works with reasoning models that reject it.
- Python 3.11+ (`requires-python`); CI runs on 3.12, development on 3.14.
- `tzdata` is a runtime dependency because Windows has no system time zone database for `zoneinfo`.
