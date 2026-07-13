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

vitia-ia follows a hexagonal (ports-and-adapters) architecture. The HTTP layer is thin; all business logic lives in services; external systems are hidden behind adapters.

```
┌──────────────────────────────────────────────────────────────┐
│  HTTP (FastAPI routes)                                       │
│  routes/food.py · routes/health.py                          │
└────────────────────────────┬─────────────────────────────────┘
                             │ depends on
┌────────────────────────────▼─────────────────────────────────┐
│  Application layer (services)                                │
│  services/food_matcher.py  — orchestrates matching logic     │
└──────┬────────────────────────────────────┬──────────────────┘
       │ uses                               │ uses
┌──────▼──────────┐               ┌─────────▼────────────────┐
│  Adapters        │               │  Adapters                │
│  supabase_client │               │  off_client              │
│  claude_adapter  │               │  (OpenFoodFacts)         │
│  (Anthropic AI)  │               │                          │
└──────────────────┘               └──────────────────────────┘
       │                                    │
       ▼                                    ▼
  Supabase DB                         OpenFoodFacts API
  (generic_foods)                      (public REST)

Infrastructure:
  Vercel — serverless ASGI host (python runtime)
  GitHub Actions — CI (lint, test, type-check) + CD (deploy to Vercel on main push)
```

```
src/
├── main.py          # App factory — wires middleware, routers, lifespan
├── config.py        # Typed settings via pydantic-settings (fail-fast on missing vars)
├── auth/            # JWT verification (ES256 + JWKS) and FastAPI dependency
├── routes/          # HTTP layer — FastAPI routers (thin controllers)
├── services/        # Application layer — use cases and orchestration
├── adapters/        # Infrastructure layer — Supabase, OpenFoodFacts, Anthropic
└── domain/          # Pydantic domain models and validation rules
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

Copy `.env.example` to `.env` and fill in real values before running locally.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_URL` | Yes | — | Supabase project URL — e.g. `https://<project-id>.supabase.co` |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase anonymous (public) API key |
| `SUPABASE_JWKS_URL` | Yes | — | JWKS endpoint for JWT verification — `https://<project-id>.supabase.co/auth/v1/.well-known/jwks.json` |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key (required when `LLM_PROVIDER=anthropic`) |
| `LLM_PROVIDER` | No | `anthropic` | LLM provider. Currently only `anthropic` is supported. |
| `ANTHROPIC_MODEL` | No | `claude-opus-4-8` | Anthropic model name. |
| `ALLOWED_ORIGINS` | Yes (prod) | `[]` | Comma-separated CORS origins — e.g. `https://vitia.app` |
| `APP_NAME` | No | `vitia-ia` | Application display name |
| `LOG_LEVEL` | No | `INFO` | Log level: `DEBUG` · `INFO` · `WARNING` · `ERROR` |

> **Startup behavior:** The app validates all required vars at startup and raises a `ValueError` immediately if any are missing — you will not get a cryptic runtime error later.
>
> **CORS note:** `ALLOWED_ORIGINS` must be set to the exact frontend origin(s) in production. An empty list blocks all cross-origin requests.

---

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

## Supabase schema

vitia-ia reads from a single table in Supabase: `generic_foods`.

### `generic_foods`

| Column | Type | Description |
|---|---|---|
| `id` | uuid / serial | Primary key |
| `name` | text | Human-readable food name (e.g. `"Chicken breast, cooked"`) |
| `name_normalized` | text | Lowercased, accent-stripped name used for fuzzy search |
| `category` | text | Food category (e.g. `"meat"`, `"dairy"`) |
| `calories_per_100g` | numeric | Energy per 100 g in kcal |
| `protein_per_100g` | numeric | Protein per 100 g in grams |
| `carbs_per_100g` | numeric | Carbohydrates per 100 g in grams |
| `fat_per_100g` | numeric | Fat per 100 g in grams |

The service queries `name_normalized` with a case-insensitive `ilike` filter, retrieves up to 10 candidates, and uses `rapidfuzz` token-sort-ratio to pick the best match above a 70-point threshold. Rows below the threshold fall through to the OpenFoodFacts REST fallback.

---

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Health check — returns `{"status": "ok"}` |
| `GET` | `/docs` | Public | Swagger UI — interactive API explorer (FastAPI auto-generated) |
| `GET` | `/redoc` | Public | ReDoc — alternative API documentation viewer |
| `POST` | `/food/match` | Bearer JWT (Supabase) | Match identified foods against the nutritional database; returns macros per item and totals |

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
