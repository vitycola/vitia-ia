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

## AI Setup

vitia-ia uses a provider-agnostic LLM adapter. Only the **active provider's** API key is required at startup.

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `anthropic` | LLM provider to use. Currently only `anthropic` is supported. |
| `ANTHROPIC_API_KEY` | Yes (when `LLM_PROVIDER=anthropic`) | — | Anthropic API key. Get one at [console.anthropic.com](https://console.anthropic.com/). |
| `ANTHROPIC_MODEL` | No | `claude-opus-4-8` | Anthropic model name. Override to use a different Claude model. |

### Switching provider

Set `LLM_PROVIDER` to the desired provider name. Only the active provider's key is required — you do not need to configure keys for unused providers.

> **Startup behavior:** If the active provider's API key is missing, the application fails immediately at startup with a `ValidationError`. If an unknown provider is configured, a `ValueError` is raised at the first call to the factory.

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

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Health check — returns `{"status": "ok"}` |
| `GET` | `/docs` | Public | Swagger UI — interactive API explorer |
| `POST` | `/food/match` | Bearer JWT | Match identified foods to nutritional database entries |

### `POST /food/match`

Requires a valid Supabase-issued JWT in the `Authorization: Bearer <token>` header.

**Request body**

```json
{
  "items": [
    {
      "name": "chicken breast",
      "estimated_grams": 150.0,
      "confidence": 0.9
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `items[].name` | string | Yes | Food name as identified by the AI |
| `items[].estimated_grams` | number | Yes | Estimated portion size in grams |
| `items[].confidence` | number | Yes | Confidence score from the AI (0–1) |

**Response**

```json
{
  "items": [
    {
      "query_name": "chicken breast",
      "grams": 150.0,
      "source": "supabase",
      "matched_name": "Chicken breast, cooked",
      "score": 92.5,
      "macros_per_100g": { "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6 },
      "macros_actual": { "calories": 247.5, "protein": 46.5, "carbs": 0, "fat": 5.4 },
      "low_confidence": false
    }
  ],
  "totals": { "calories": 247.5, "protein": 46.5, "carbs": 0, "fat": 5.4 },
  "degraded": false
}
```

`degraded: true` indicates the Supabase lookup failed and the OFF fallback was used.

Interactive docs: `/docs` (Swagger UI) · `/redoc` (ReDoc)
