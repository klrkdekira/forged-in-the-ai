# server

FastAPI app, rules engine, and (later) AI GM loop. See the root
[CLAUDE.md](../CLAUDE.md) for layout and hard rules, and
[SPECIFICATION.md](../SPECIFICATION.md) §7 for the layering.

## Dev

```
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
```

## Layout

```
app/     FastAPI routes and server wiring
engine/  pure rules engine (no web or LLM imports)
tests/
```
