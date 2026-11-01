# Decisions and assumptions

One line per decision. Business rules decided by the project owner are marked **[owner]**.

## Technical

- Package manager: `uv` with a committed lockfile, for one reproducible install command; `pip install -e .` also works.
- Default model `gpt-4.1-mini`: reliable tool calling at low cost; overridable with `MODEL`.
- No `temperature` is sent to the API, so the same code works with reasoning models that reject it.
- Python 3.11+ (`requires-python`); CI runs on 3.12, development on 3.14.
- `tzdata` is a runtime dependency because Windows has no system time zone database for `zoneinfo`.
- Data lives in plain in-memory dataclasses, not SQLite/pandas: 65 products and 20 orders do not need a query engine, and there is no SQL for the LLM to get wrong. A real database would replace `data_store.py` only.
- Money uses `Decimal` rounded half-up to cents and is formatted by code as `R$ 1.234,56`; the model never formats or computes prices.
- Availability is derived in one place (`Product.availability`): `discontinued` and `coming_soon` win over stock; `active` with stock 0 is `out_of_stock`.
- Only `is_active = 1` promotions are loaded; the agent cannot see expired ones. **[owner]**
