# AtlasIQ Backend: Python Standards (Short)

## 1. Coding

**Tools**
- Python 3.12 (pinned in Dockerfile + pyproject). `ruff format` (120 cols) and `ruff check` (E, F, I, B, UP, S, SIM, N, DTZ).
- `mypy`: strict for `libs/`, standard for services; all functions fully type-hinted.
- One `uv` workspace + one lock file at root; each service has its own `pyproject.toml`; `libs/` used from workspace; Renovate for upgrades.
- Pre-commit: ruff, ruff-format, mypy, gitleaks, end-of-file.

**Structure**
- One repo; each service in `services/<service>/`: `main.py`, `worker.py`, `alembic/`, `app/{api/v1/endpoints, core, middleware, models, schemas, services, clients, events, jobs, integrations}` (`integrations` only if vendors are called).
- Thin endpoints: parse request, check permission, call a service. Business rules only in `app/services/`.
- Pydantic schemas (`app/schemas`) for API I/O; SQLAlchemy models (`app/models`) for tables; never return or accept a model directly.
- One file per feature in `endpoints/`, `schemas/`, `services/`, `models/`.
- Vendors only in `integrations/<vendor>/` behind `base.py`; other AtlasIQ services only via `clients/` (REST) or `events/` (async).
- Import direction: `endpoints → services → models/clients/integrations`, never reverse. A service imports only `libs/` and its own folder, never another service (import-linter in CI).

**Naming**
| What | Convention | Example |
|---|---|---|
| Modules, functions, variables | `snake_case` | `get_claim_line()` |
| Classes / schemas | `PascalCase`; schemas end `Create`/`Update`/`Out` | `ClaimLineOut` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| Tables / columns | `snake_case`, singular table, FK `<table>_id` | `claim_line.claim_id` |
| API paths | plural kebab-case, version first | `/v1/claim-lines/{id}` |
| Events / commands | `evt.<service>.<fact>` (past tense), `cmd.<service>.<action>` | `evt.claims.determination_released` |
| Booleans | `is_`/`has_`/`can_` | `is_late` |

**Endpoint pattern**
```python
@router.post("/v1/letters", response_model=LetterOut, status_code=201)
def create_letter(
    payload: LetterCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ctx: RequestContext = Depends(require_permission("letter.create")),
    db: Session = Depends(get_tenant_db),  # never a global engine
) -> LetterOut:
    return letter_service.create(db, ctx, payload, idempotency_key)
```

**Code rules**
- **Transactions:** one `with db.begin():` per write; business change + outbox event in the same block.
- **Queries:** SQLAlchemy 2.0 (`select()`, `session.scalars()`); no raw SQL (only `text()` with bound params if unavoidable).
- **Migrations:** Alembic revision per schema change in the owning service; expand → migrate → contract; no prod downgrade; reviewed like code.
- **Time:** `timestamptz` in UTC (`datetime.now(timezone.utc)`); convert only for display.
- **Money:** integer cents or `Decimal`, never `float`.
- **IDs:** internal `bigint`; `uuid` in APIs, URLs, events, other systems.
- **Errors:** raise `NotFound`/`Conflict`/`ValidationFailed`/`Forbidden`; shared handler formats them. No bare `except`, never swallow.
- **Logging:** `structlog` JSON with correlation id, tenant code, user id. Log events, not data (no PHI).
- **Config:** `pydantic-settings` from env vars; defaults for local dev only.
- **Docs:** docstring on every public function/endpoint (becomes OpenAPI text); comments explain *why*.
- **Testing:** `pytest`; unit tests for `services/`; API tests with `TestClient`; Postgres via testcontainers (no SQLite); `respx` for outside HTTP. Coverage ≥ 80% per service, ≥ 90% `libs/`.

## 2. Security (PHI: applies to every service and PR)

- **Auth:** only the shared auth library (Entra ID staff, email OTP external). No custom token handling.
- **Authorisation:** every endpoint declares `require_permission`; every query filtered server-side by caller scope (tenant always; provider/program where relevant). External users reach only `/v1/external/…`.
- **Tenant isolation:** tenant from token only (never URL/body); sessions from `get_tenant_db()`, no global engine; events/jobs carry tenant and switch to its DB first.
- **DB rights:** own login per service; app login reads/writes rows only, migration login alone changes tables.
- **Input:** Pydantic with explicit types, lengths, ranges; reject unknown fields on write models.
- **SQL injection:** ORM or bound params only; no f-string/concatenated SQL.
- **Uploads:** short-lived signed links to blob storage, never via the API; check type/size, virus scan, keep "pending" until clean.
- **Secrets:** Azure Key Vault via managed identity only; none in code, Git, images, `.env` in images, logs, errors.
- **PHI:** minimum necessary; never in logs, URLs, query strings, errors or event names; every PHI read goes to `phi_access_log`; no prod PHI in dev/test/UAT.
- **Transport/storage:** TLS everywhere (also between services); encryption at rest for DBs, storage, backups, logs.
- **HTTP hardening:** CORS allow-list of AtlasIQ web domains (never `*` with credentials), security headers, rate limits on sign-up/OTP/public endpoints, debug and docs UI off in prod, no stack traces to clients.
- **Webhooks:** verify vendor signature or mTLS; reject replays by event id + timestamp.
- **Dependencies:** `pip-audit`, licence check (no AGPL/SSPL, e.g. PyMuPDF), SBOM per release, Renovate.
- **CI security:** ruff S/bandit, gitleaks, trivy; DAST + pen test before launch.

## 3. Performance

- **Sync/async:** endpoints are plain `def` with sync SQLAlchemy; `async def` only if everything inside is async; never block (paramiko, pyodbc, OCR, `time.sleep`) in `async def`.
- **Heavy work** (parsing, OCR, PDF, SFTP, bulk updates, anything > ~1 s): `worker.py`/jobs triggered by events; API returns `202` + pollable status.
- **N+1:** `selectinload`/`joinedload`, never query in a loop; tests assert query counts on lists.
- **Pagination:** all lists (`page`, `size`; default 50, max 200) with stable sort.
- **Indexes:** every `WHERE`/`JOIN`/`ORDER BY` column on large tables; check heavy queries with `EXPLAIN ANALYZE`.
- **Columns:** select only what is needed; no `SELECT *` on wide tables; no large text/JSON in lists.
- **Timeouts:** DB `statement_timeout`, shared `httpx` client with connect/read timeouts, circuit breaker for services/vendors.
- **Connections:** small pool per tenant via built-in PgBouncer; reuse HTTP client.
- **Caching:** in-memory short TTL for tenant catalog, roles/permissions, lookups, code sets, config; Redis only if instances must share.
- **Files:** browser ↔ blob storage via signed links; API handles metadata only.
- **Measure:** OpenTelemetry on every endpoint/job, p95 + error-rate dashboards per service and tenant, k6/Locust load test before go-live.

| Operation | Target |
|---|---|
| Screen reads | ≤ 300 ms p95 |
| Saves | ≤ 500 ms p95 |
| Search, dashboards | ≤ 2 s p95 |
| Job start after event | ≤ 5 s |

## 4. Consistency

- **Shared library first:** auth, tenant routing/DB session, errors, logging, pagination, idempotency keys, outbox/inbox, broker client, HTTP client (retries + circuit breaker), migration runner always from `atlasiq-libs`; never copy.
- **Service template:** new services from the Copier template in `tools/`.
- **Pipelines:** per-service pipeline runs on its folder or `libs/` changes; `libs/` change runs all services' tests.
- **API:** `/v1` path, plural kebab-case, uuid ids, ISO 8601 UTC, one error format, same paging params, `Idempotency-Key` on creates, OpenAPI per service.
- **Events:** envelope (`event_id`, `type`, `occurred_at`, `tenant`, `actor`, `data`, `version`); publish via outbox, consume via inbox; schemas versioned in `contracts/`; only add optional fields, never remove/rename.
- **Database:** standard columns (`id`, `uuid`, created/updated at/by, `row_version`), schema per service, no `customer_id`, FKs only within one DB, migrations only via Alembic.
- **Azure:** Blob, Service Bus, Key Vault, Entra ID only via `atlasiq-libs` clients (emulators locally); no direct Azure SDK in business code.
- **Git:** short-lived branches from `main`, PR for every change, conventional commits with scope (`feat(claims):`), squash merge, CODEOWNERS, ≥ 1 reviewer (2 for `libs/`).
- **Releases:** one image per service tagged with git SHA (never `:latest`) + release tag (`claims-v1.4.0`); changelog per service.
- **Docs:** README at root and per service (run, test, deploy), ADRs in `docs/adr`, runbooks for alerts, OpenAPI as API reference.

**CI gates (failure blocks merge)**
| Gate | Check | When |
|---|---|---|
| Format/lint | `ruff format --check`, `ruff check` | Every PR |
| Types | `mypy` | Every PR |
| Tests | `pytest` + coverage thresholds | Every PR |
| Migrations | fresh build, upgrade from prod revision, old code vs new schema, `alembic check` | Every PR |
| Contracts | OpenAPI + event schema compatibility vs `contracts/` | Every PR |
| Security | bandit/ruff S, gitleaks, pip-audit, licence check | Every PR |
| Image | trivy | Every build |
| Performance | load test on UAT | Before go-live / major releases |

**Review checklist**
- [ ] Thin endpoint; logic in `services/` with unit tests
- [ ] Pydantic I/O; no ORM model leaves the service
- [ ] Permission declared; query filtered by tenant (+ provider/program)
- [ ] One transaction per write; events via outbox; consumers idempotent
- [ ] No PHI/secrets in logs, URLs, errors, events
- [ ] Lists paginated; no N+1; indexes for new filters
- [ ] Heavy/blocking work in a worker
- [ ] Timeouts on outside calls; retries only when safe
- [ ] Migration follows expand → contract and passes tests
- [ ] Shared behaviour from `atlasiq-libs`
- [ ] OpenAPI docstrings + README updated; ADR for new decisions
- [ ] CI green: lint, types, tests, migrations, contracts, security
