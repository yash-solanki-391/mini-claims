# Mini Claims API

A learning project practicing AtlasIQ backend standards: FastAPI, PostgreSQL, SQLAlchemy 2.0, and Alembic.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.12
- Docker & Docker Compose
- `uv` (installed via `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 2. Setup
```bash
# Sync dependencies
uv sync --all-groups

# Start database
docker compose up -d db

# Run migrations
uv run alembic upgrade head
```

### 3. Run the App
```bash
uv run uvicorn services.claims.main:app --reload
```

### 4. Verify
Visit `http://localhost:8000/health` - should return `{"status": "ok"}`.

### 5. Demo authentication (NOT production auth)
Requests carry a signed demo token, accepted only when `APP_ENV` is `local` or `test`
(see [ADR 003](docs/adr/0003-demo-jwt-authentication.md)). The real AtlasIQ service uses the shared auth library.

Set `DEMO_JWT_SECRET` (at least 32 chars) in `services/claims/.env`, then mint a token:
```bash
TOKEN=$(uv run python -m services.claims.app.core.demo_auth --tenant tenant-a --actor actor-1 --role claims_submitter)

curl -X POST http://localhost:8000/v1/claims/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-001" \
  -d '{"claim_reference": "DEMO-CLAIM-001"}'
```

| Role | Permissions |
| :--- | :--- |
| `claims_reader` | `claim.read` |
| `claims_submitter` | `claim.read`, `claim.create` |

Permissions are decided by the server from the token's roles; the token cannot grant them directly.

## 🛠 Development

### Testing
```bash
uv run pytest
```

### Linting & Typing
```bash
uv run ruff format --check && uv run ruff check
uv run mypy
```

### Database Checks
```bash
uv run alembic check
```

## 🏗 Architecture
- **Dependency Flow**: `endpoints` $\to$ `services` $\to$ `models/clients`
- **Tenancy**: Every query filtered by `tenant_id` at the DB level.
- **Security**: Permissions checked at the endpoint level.
- **Data**: Timestamps in UTC, public IDs as UUIDs, internal IDs as integers.
