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
