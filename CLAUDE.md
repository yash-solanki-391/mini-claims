# Mini Claims API

Learning project that practises AtlasIQ backend standards: FastAPI + PostgreSQL + SQLAlchemy 2 (sync) + Alembic.
**Synthetic data only.** No real PHI, secrets or production access. Demo auth is **NOT** production auth.
Real AtlasIQ repo, `atlasiq-libs` and team decisions always override this project.

Full standards: @docs/atlasiq_python_standards.md. Spec: @docs/mini_claims_api_spec_driven_development.md.

## Scope
- MVP: `POST /v1/claims`, `GET /v1/claims`, `GET /v1/claims/{uuid}`. `PATCH` only after these pass all tests.
- Tables: `claim`, `idempotency_record`, `outbox_event`, `inbox_event`.
- Non-goals: Entra/OTP auth, Azure services, UI, Kubernetes, Redis, real broker, claims adjudication.

## Commands
```bash
uv sync --all-groups
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn services.claims.main:app --reload
uv run pytest
uv run ruff format --check && uv run ruff check
uv run mypy
uv run alembic check
```

## Structure
```text
```text
├── .opencode/
├── docs/
├── services/
│   └── claims/
│       └── app/
│           ├── api/
│           │   └── v1/
│           │       └── endpoints/
│           ├── core/
│           ├── middleware/
│           ├── models/
│           ├── schemas/
│           ├── services/
│           └── utils/
└── tests/

```
Create folders only when they have content. Dependency direction: `endpoints → services → models/clients`. Never reverse.
A service never imports another service's internals.

## Rules (always)
**Layers**
- Endpoints are thin: parse, check permission, call a service. Business logic lives in `app/services/`.
- Pydantic schemas for I/O (`ClaimCreate`, `ClaimOut`, `ClaimListOut`, `ErrorOut`), `extra="forbid"` on write schemas. Never return or accept ORM models.
- One file per feature. Naming: snake_case, PascalCase classes, plural kebab-case paths with `/v1`, singular snake_case tables, `is_/has_` booleans.

**Security and tenancy**
- Tenant and actor come from `RequestContext` only, never from body, path or query.
- Every query filters by tenant at DB level. Cross-tenant lookup returns 404, never 403.
- Every endpoint declares `require_permission(...)` (`claim.create`, `claim.read`, `claim.update`).
- Demo auth works only when `APP_ENV` is `local` or `test`; fail closed otherwise. Never log auth headers.
- No secrets in code, Git, images or logs. Commit only `.env.example`.

**Data and DB**
- One `with db.begin():` per write. Claim + idempotency record + outbox event commit or roll back together.
- SQLAlchemy 2.0 `select()` only. No raw SQL, no f-string SQL. No SQLite, not even in tests.
- Every schema change is an Alembic migration (expand → migrate → contract). Add an index only for a verified query (`EXPLAIN ANALYZE`).
- Timestamps: `timestamptz`, `datetime.now(timezone.utc)`, ISO 8601 UTC. Public ids are UUIDs, internal ids are ints.
- Money (if ever added): integer cents or `Decimal`, never `float`.

**API behaviour**
- Create requires `Idempotency-Key` (non-blank, max 128). Scope: tenant + actor + endpoint + key, plus payload hash.
  Same key + same payload returns the original result. Same key + different payload returns 409.
- Lists: `page` default 1, `page_size` default 50, max 200, stable order `created_at DESC, id DESC`, select needed columns only, no N+1.
- Errors use one shape `{"error": {"code","message","correlation_id"}}` via domain exceptions
  (`NotFound`, `Conflict`, `ValidationFailed`, `Forbidden`) and one central handler. No bare `except`, no stack traces to clients.

**Logging and events**
- JSON logs with correlation id (validated, length-limited, returned in response header). Never log payloads, headers, tokens or PHI.
- Events: envelope `event_id, type, occurred_at, tenant, actor, data, version`; names like `evt.claims.created`; no PHI in names or data.
  Publish only via outbox, consume only via inbox (unique `consumer + event_id`). Do not claim real broker delivery.

**Performance**
- Endpoints are plain `def` with sync sessions. Never block inside `async def`.
- One engine for the app, one session per request, always closed. DB `statement_timeout` set.
- Work over ~1 s goes to `worker.py`. Return `202` only after work is durably enqueued.

## Dependencies
Ask before adding any package and say why. Keep `uv.lock` committed. Python stays pinned to 3.12.

## Testing
- pytest; unit tests for services, API tests with `TestClient`, Postgres via testcontainers.
- Coverage at least 80%, but prioritise security boundaries over the number.
- Every feature needs tests for: success, validation failure, permission failure, tenant isolation (and idempotency, rollback or inbox dedupe where relevant).
- Run targeted tests first, then ruff, mypy and the full suite.

## Workflow (every task)
1. Read README, this file and `docs/standard-practice-mapping.md`. Inspect the current code and patterns.
2. Restate requirement and acceptance criteria. List affected files, migration needs and risks. Propose a short plan and wait for approval.
3. Implement one small module at a time. Follow existing patterns. Do not touch unrelated files.
4. Add tests, run checks, report exact commands and results. Never claim a check passed if it was not run.
5. Update `docs/standard-practice-mapping.md`: practice, source section (only if verified, never invent), file/function, test, status.
6. Add an ADR in `docs/adr/` for meaningful decisions.
7. Final report: behaviour, files changed, standards applied, tests run, standards not applied (with reason), limitations.


### Linting
- Use Ruff for Python linting.
- Run `uv run ruff check .` before completing code changes.
- Fix relevant lint errors instead of suppressing rules unnecessarily.
- Use `uv run ruff format --check .` to verify formatting.
- Explain any remaining lint violations.

Comments explain *why* a standard is applied and where it is non-obvious. Do not restate the code.
Never run destructive DB commands, fetch secrets, deploy, or use unverified Claude Code or tool syntax.

## Definition of done
Layers respected, schemas used, permissions + tenant filter present, transaction correct, errors and logs standard, no PHI/secrets logged,
tests (unit, API, Postgres) pass, ruff + mypy + security checks pass, README/OpenAPI/mapping updated, diff reviewed with no unrelated changes.
