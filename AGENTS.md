# AGENTS.md

Instructions for coding agents working in this repository.

## Project

Prototype customer service agent for Empório da Música (fictional musical instrument store).
Python, OpenAI-compatible function calling with a hand-written loop, no agent framework.
The agent answers customers in Brazilian Portuguese; code, commits and docs are in English.

## Stack

- Python 3.11+, managed with `uv` (`pyproject.toml`, `uv.lock`)
- `openai` SDK (any OpenAI-compatible endpoint via `OPENAI_BASE_URL`)
- Data: CSVs in `data/` loaded into in-memory Python objects (`data_store.py`)
- Policies: `data/processed/policies.json`, generated from the PDF by `scripts/build_policies.py`

## Commands

```bash
uv sync                          # install
uv run ruff check                # lint
uv run ruff format               # format
uv run pytest                    # tests (no network, no LLM)
uv run emporio-agent             # interactive CLI (needs OPENAI_API_KEY in .env)
uv run python scripts/run_examples.py   # regenerate examples/ (calls the API)
```

## Conventions

- Prices, stock, promotions and order data come only from tools. Never from the prompt.
- The LLM never writes queries: tools take typed parameters and return JSON.
- Business rules (PIX, installments, return windows, store hours) are computed in Python, not by the model.
- Every tool has a unit test that runs without the LLM.
- Conventional Commits in English. No tool attribution lines in commits.
- Technical choices and assumptions go in `docs/decisions.md` (one line each).

## Definition of done

- `uv run ruff check`, `uv run ruff format --check` and `uv run pytest` pass.
- A fixed bug comes with a test that reproduces it.
- Never make a test pass by deleting it, skipping it, loosening assertions or mocking the behavior under test.

## When to stop and ask the human

- A secret is missing (`OPENAI_API_KEY`).
- A change alters what the agent tells customers and is not covered by the policy manual or `docs/decisions.md`.
- An irreversible or external action: push, creating repositories, global installs, significant API spend.
