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
- An empty `OPENAI_BASE_URL` falls back to the official URL; the OpenAI SDK would otherwise treat `""` as the endpoint.
- Policies: the 8-page PDF is split by its 10 top-level section titles into `policies.json`, served by `get_policy(topic)`. No embeddings or vector DB: the model picks a topic from an enum, which is exact and debuggable at this size.
- PDF parsing uses `pdfplumber` (dev-only); `pypdf` returned one word per line for this file. The JSON is committed so runtime needs no PDF parser.
- Official contact: (67) 3341-4444 and contato@emporiodamusica.com.br (cover + section 1.2). The build script rewrites the conflicting (67) 3321-4500 (section 7) and the accented e-mail (section 1.2 table). **[owner]**
- Product search: accent/case-insensitive substring match on name, category, specs and description, with light plural handling (violões/violão). All terms must match; otherwise partial matches are returned and flagged. No fuzzy/embedding search: 65 products.
- `search_products` returns unavailable products too, flagged by `availability`, so asking for a sold-out model by name gets "esgotado" plus alternatives instead of "not found". `available_only` is for browsing.
- Price filters use the price the customer pays (promotional price when a promotion is active).
- Alternatives for unavailable products: same category, available, within ±30% of the price, closest first, top 3 (computed by the tool, not the model). **[owner]** rule, range is a technical choice.
- Descriptions that mention a brand absent from the product name (rows 135, 137, 139, 140, 142, 144) are withheld from answers and search; name and specs are treated as authoritative.
- Order lookup requires order number + e-mail or phone of that order's customer (LGPD). Unknown order and wrong identity return the same message, so the tool does not reveal which orders exist. **[owner]**
- Phone matching ignores formatting and accepts the number with or without +55 and area code (at least 8 digits); e-mail matching is case-insensitive.
- After-sales windows (7-day regret and preference exchange, 30-day defect exchange from purchase, 90-day legal warranty) are computed by the tool from today's system date, with `estimated_delivery` as the receipt date. **[owner]**
- Shipped orders past their estimated delivery get `delivery_overdue_days`, so the agent can acknowledge the delay instead of repeating a past date.
- "Today" comes from `clock.now()` in America/Campo_Grande; tests freeze it.
