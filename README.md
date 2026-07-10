# vitia-ia

> AI-powered backend for the [vitia](https://github.com/vitycola/vitia) platform — a dedicated Python service handling intelligent features, deployed as a serverless ASGI function on Vercel.

---

## Tech stack

| Layer | Technology |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Runtime | Python 3.12+ |
| Validation | [Pydantic v2](https://docs.pydantic.dev/latest/) |
| Config | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Linting | [ruff](https://docs.astral.sh/ruff/) |
| Type checking | [pyright](https://github.com/microsoft/pyright) |
| Testing | [pytest](https://docs.pytest.org/) + [httpx](https://www.python-httpx.org/) |
| Deployment | [Vercel](https://vercel.com/) (serverless) |
| CI/CD | GitHub Actions |

---

## Architecture

Clean layered architecture with a clear separation of concerns:

```
src/
├── main.py          # App factory — wires middleware, routers, lifespan
├── config.py        # Typed settings via pydantic-settings
├── routes/          # HTTP layer — FastAPI routers
├── services/        # Application layer — use cases and orchestration
├── adapters/        # Infrastructure layer — external integrations
└── domain/          # Domain models and business rules
```

The app is exposed as a single ASGI callable (`app = create_app()`) that Vercel picks up and runs as a serverless function — no server management required.

---

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — `brew install uv`

### Local development

```bash
# Clone and install dependencies
git clone https://github.com/vitycola/vitia-ia.git
cd vitia-ia
uv sync --all-groups

# Copy env vars and configure
cp .env.example .env

# Start the dev server
uv run uvicorn src.main:app --reload
```

API available at `http://localhost:8000` · Docs at `http://localhost:8000/docs`

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ALLOWED_ORIGINS` | Yes (prod) | `[]` | Comma-separated CORS origins — e.g. `https://vitia.app` |
| `APP_NAME` | No | `vitia-ia` | Application display name |
| `LOG_LEVEL` | No | `INFO` | Log level: `DEBUG` · `INFO` · `WARNING` · `ERROR` |

> **CORS note:** `ALLOWED_ORIGINS` must be set to the exact frontend origin(s) in production. An empty list blocks all cross-origin requests.

---

## Development

```bash
# Run tests
uv run pytest -v

# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Type check
uv run pyright
```

---

## Deployment

The service deploys automatically to Vercel on every merge to `main` via GitHub Actions.

For a manual first-time setup:
1. Import the repo in the [Vercel dashboard](https://vercel.com/new)
2. Set `ALLOWED_ORIGINS` (and any other env vars) in the Vercel project settings
3. Push — Vercel handles the rest

> **Note:** Vercel's free tier enforces a **10-second** execution limit per request. Keep handlers fast.

### Keeping `requirements.txt` in sync

Vercel uses `requirements.txt` (not `uv.lock`) to install dependencies. After any change to `pyproject.toml`, regenerate it:

```bash
uv export --no-hashes --no-dev -o requirements.txt
```

Commit the updated file alongside `uv.lock`. CI will catch any drift automatically.

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |

Interactive docs: `/docs` (Swagger UI) · `/redoc` (ReDoc)
