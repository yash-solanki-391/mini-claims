# Mini Claims API — Spec-Driven Development Plan

**Document type:** Module-wise implementation specification
**Purpose:** Learning/reference project for AtlasIQ-style backend standards and future Claude Code workflows
**Status:** Draft specification — implement in phases; validate tool versions and exact AtlasIQ standards against the real repository when available
**Language:** Requirements and technical terms are in English for use by coding agents; explanatory notes are included where useful.

---

## 1. Project Overview

Build a small, production-inspired backend called **Mini Claims API**. It manages synthetic claim records through a small set of REST APIs while demonstrating the most important backend standards documented for AtlasIQ.

This is a learning project, not part of the actual AtlasIQ codebase. Do not use real patient data, production credentials, production databases, or real PHI.

### 1.1 Goals

- Build three core APIs with FastAPI.
- Separate endpoints, Pydantic schemas, SQLAlchemy models, and business services.
- Use PostgreSQL, SQLAlchemy 2.x, and Alembic migrations.
- Demonstrate tenant-scoped data access and permission checks using a clearly labelled **demo authentication mechanism**.
- Implement standard errors, structured logs, correlation IDs, pagination, and idempotent create requests.
- Demonstrate a transactional outbox and an idempotent inbox consumer in a small, testable form.
- Add automated tests, quality gates, Docker-based local development, and CI.
- Prepare repository-level instructions and optional Claude Code configuration that can later be adapted to the actual AtlasIQ repository.

### 1.2 Non-goals

Do **not** build these in the initial version:
- Real Entra ID authentication or external-user email OTP.
- Real Azure Blob Storage, Service Bus, Key Vault, or production integrations.
- Real claims adjudication, clinical decision-making, or healthcare rules.
- Frontend/UI.
- Multi-service deployment or Kubernetes.
- A production-ready identity provider, secrets platform, or PHI audit system.
- A generic framework intended to solve every possible backend problem.

Keep the first version intentionally small. Add optional features only after the core requirements and tests pass.

---

## 2. Technology and Tooling

Use compatible, supported versions and pin resolved dependency versions through `uv.lock`. Do not blindly choose latest versions if they conflict.

- Python: **3.12**
- API framework: FastAPI
- ASGI server: Uvicorn
- Validation/settings: Pydantic v2 and pydantic-settings
- ORM: SQLAlchemy 2.x, synchronous sessions
- Database: PostgreSQL
- Migrations: Alembic
- Package/workspace manager: `uv`
- Tests: pytest, FastAPI TestClient, testcontainers for PostgreSQL integration tests where Docker is available
- HTTP mocking: respx only if an outbound HTTP client is introduced
- Formatting/linting: Ruff
- Type checking: mypy
- Security checks: Bandit and/or Ruff S rules, Gitleaks, pip-audit, Trivy
- Git hooks: pre-commit
- Containers: Docker and Docker Compose
- CI: GitHub Actions
- Optional AI coding configuration: Claude Code `CLAUDE.md`, `.claude/rules/`, and settings supported by the installed Claude Code version

**Dependency rule:** Before adding a package, explain why it is required. Avoid unnecessary packages. Pin the Python minor version and keep `uv.lock` committed.

---

## 3. Repository Layout

Use a single repository with a standard service directory. This is a learning approximation of the AtlasIQ layout; the real AtlasIQ service template and `atlasiq-libs` take precedence when available.

```text
services/
└── claims/
    ├── main.py
    ├── worker.py
    ├── alembic/
    │   └── versions/
    └── app/
        ├── api/
        │   └── v1/
        │       └── endpoints/
        ├── core/
        ├── clients/
        ├── events/
        ├── jobs/
        ├── integrations/
        ├── middleware/
        ├── models/
        ├── schemas/
        ├── services/
        ├── templates/       # Only if required
        └── utils/           # Only if required
```

Create only folders that have a defined purpose. Empty `clients/`, `events/`, or `integrations/` directories may be introduced when the corresponding module is implemented. Avoid placeholder files that do not provide value.

### 3.1 Dependency direction

Allowed dependency flow:

```text
API endpoints
    ↓
Service layer
    ↓
Models / shared library / clients / integrations
```

- Endpoints must not contain business rules.
- Models must not import endpoints or service functions.
- A service must not import another service's internal Python modules.
- Shared behaviour belongs in `libs/mini_core` for this exercise.
- Actual AtlasIQ work must use approved `atlasiq-libs` APIs rather than copying this practice library.

---

## 4. Domain Model and Data Rules

### 4.1 Claim entity

Implement a minimal `Claim` SQLAlchemy model with:

- `id`: internal integer primary key.
- `uuid`: unique public UUID, generated server-side.
- `tenant_id`: tenant identifier used for isolation in this learning project.
- `claim_reference`: synthetic claim reference; unique within a tenant.
- `status`: constrained string or enum, initially `received`, `in_review`, or `closed`.
- `service_date`: optional date.
- `created_at`: timezone-aware UTC timestamp.
- `updated_at`: timezone-aware UTC timestamp.
- `created_by`: demo actor identifier.
- `updated_by`: demo actor identifier.
- `row_version`: integer for optimistic-concurrency practice; it may initially be incremented on updates.

Use a database uniqueness constraint on `(tenant_id, claim_reference)`. Add an index appropriate for the tenant-scoped list query and stable sort. Do not add indexes without a query/use case.

### 4.2 Synthetic data only

Use clearly fake examples such as `DEMO-CLAIM-001`. Do not use real patient names, member IDs, dates of birth, medical notes, or production identifiers.

### 4.3 Tenant isolation

For the learning version, use a demo request context that supplies a `tenant_id`, actor ID, and permissions from a controlled test/development mechanism. Do not present a user-supplied request-body tenant as trusted identity.

- Every claim query must filter by the tenant from the authenticated request context.
- Create requests must set tenant and actor fields from server-side request context, not from the client payload.
- A user from Tenant A must not read, update, or infer the existence of Tenant B's claim.
- Return the agreed not-found response for cross-tenant resource lookups to avoid leaking existence.
- Add tests proving tenant isolation.

This demo mechanism is **not production authentication**. In the real AtlasIQ project, use the approved shared auth library, identity validation, and tenant database-routing mechanism.

---

## 5. API Contract

Base path: `/v1/claims`

All timestamps must be ISO 8601 UTC. Public resource IDs must be UUIDs. Use plural kebab-case resource names. Publish OpenAPI from FastAPI.

### 5.1 API 1 — Create claim

**Method/path:** `POST /v1/claims`
**Success status:** `201 Created`
**Required header:** `Idempotency-Key`

Example request:

```json
{
  "claim_reference": "DEMO-CLAIM-001",
  "status": "received",
  "service_date": "2026-10-01"
}
```

Rules:
- Validate input using `ClaimCreate`.
- Do not accept `id`, `uuid`, `tenant_id`, `created_by`, `updated_by`, or timestamps from the client.
- Apply authentication/permission dependency for `claim.create`.
- Derive tenant and actor from server-side request context.
- Persist the claim and an outbox event in the same database transaction.
- A retry with the same idempotency key and same request scope/payload must not create a duplicate claim; return the documented repeat-request response.
- Reuse of the same key with a different payload must return a conflict error.
- Define the idempotency key scope explicitly (at minimum tenant + actor + endpoint/key); do not use a global key namespace.
- Validate key length and reject blank keys.
- Return `ClaimOut`, never a raw ORM object.

### 5.2 API 2 — List claims

**Method/path:** `GET /v1/claims`
**Success status:** `200 OK`

Query parameters:
- `page`: integer, default `1`, minimum `1`.
- `page_size`: integer, default `50`, minimum `1`, maximum `200`.

Rules:
- Filter by the authenticated tenant.
- Use stable ordering, for example `created_at DESC, id DESC`.
- Do not use `SELECT *` if the list query can select only the required columns.
- Avoid N+1 queries.
- Return pagination metadata and a list of `ClaimOut` objects.
- Add a suitable index for the tenant filter/order pattern after checking the generated query and PostgreSQL plan.

Example response:

```json
{
  "items": [
    {
      "uuid": "00000000-0000-4000-8000-000000000001",
      "claim_reference": "DEMO-CLAIM-001",
      "status": "received",
      "service_date": "2026-10-01",
      "created_at": "2026-10-26T07:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 1
}
```

### 5.3 API 3 — Get claim details

**Method/path:** `GET /v1/claims/{claim_uuid}`
**Success status:** `200 OK`

Rules:
- Validate the path parameter as UUID.
- Filter the lookup by both `uuid` and the current tenant.
- Return `404 Not Found` for a nonexistent or cross-tenant claim.
- Return `ClaimOut`; do not expose internal-only columns.

### 5.4 Optional API 4 — Update claim

Add only after APIs 1–3 pass all required tests.

**Method/path:** `PATCH /v1/claims/{claim_uuid}`

Rules:
- Use a dedicated `ClaimUpdate` schema.
- Reject unknown fields.
- Allow only explicitly approved fields, initially `status`.
- Check tenant scope and permission `claim.update`.
- Increment `row_version` or implement the chosen optimistic concurrency approach.
- Write changes in one transaction.
- Do not silently overwrite concurrent updates.

---

## 6. Schemas and Models

Create separate Pydantic schemas:

- `ClaimCreate`: only client-editable creation fields.
- `ClaimUpdate`: only updateable fields; all optional, but reject an empty update if that is the chosen contract.
- `ClaimOut`: public response fields only.
- `ClaimListOut`: `items`, `page`, `page_size`, `total`.
- `ErrorOut`: standard error shape.

Set write schemas to reject unknown fields (Pydantic v2 `extra="forbid"`). Do not use SQLAlchemy models as request or response schemas.

Use `ConfigDict(from_attributes=True)` on output schemas only where ORM-to-schema conversion is needed. Ensure UTC datetimes serialize consistently.

---

## 7. Error Handling

Implement one standard JSON error shape, for example:

```json
{
  "error": {
    "code": "CLAIM_NOT_FOUND",
    "message": "Claim was not found.",
    "correlation_id": "example-correlation-id"
  }
}
```

Define small domain exceptions such as:
- `NotFound`
- `Conflict`
- `ValidationFailed`
- `Forbidden`

Map them to appropriate HTTP statuses in a centralized exception handler. Use FastAPI/Pydantic's standard request-validation handling or normalize it to the documented error shape.

Requirements:
- Never return stack traces or internal exception details to clients.
- Do not swallow exceptions with bare `except`.
- Do not include PHI, secrets, database URLs, tokens, or raw SQL parameters in errors.
- Log unexpected failures with a correlation ID and safe diagnostic context.

---

## 8. Authentication, Permissions, and Tenant Context

Implement only a **development/test authentication adapter**. It must be clearly named and documented as non-production. It may read controlled headers in local/test mode, but must be disabled or fail closed outside those environments.

Define a request context containing:
- `tenant_id`
- `actor_id`
- `permissions`

Use explicit permission checks:
- `claim.create` for POST.
- `claim.read` for GET endpoints.
- `claim.update` if the optional PATCH endpoint is implemented.

Security requirements:
- Never trust tenant identity from the request body or arbitrary query parameter.
- Apply tenant filtering at the database query level.
- Add tests for missing permission, wrong tenant, and cross-tenant resource access.
- Do not log auth headers or tokens.
- Do not claim the demo adapter is equivalent to Entra ID or AtlasIQ's real authentication library.

---

## 9. Database, Transactions, and Migrations

### 9.1 Database sessions

- Use synchronous SQLAlchemy 2.x sessions with normal `def` endpoints.
- Use one session per request and close it reliably.
- Do not create a new engine per request.
- Keep database URL and settings in Pydantic Settings/environment variables.
- Do not commit `.env`; commit only `.env.example` with placeholders.
- Never use SQLite as a substitute for PostgreSQL integration tests.

### 9.2 Transactions

- Each write operation must use a clear transaction boundary.
- Claim creation and outbox event insertion must commit or roll back together.
- Do not publish an external message before the database transaction commits.
- Do not call external services while holding a database transaction open unless explicitly justified.

### 9.3 Alembic

- All schema changes must be represented by Alembic migrations.
- Include an initial migration.
- CI must create a fresh database and apply all migrations.
- CI must test upgrading from the baseline/current migration revision.
- Run `alembic check` where supported by the selected configuration.
- For later schema changes, follow expand → migrate → contract.
- Never automatically downgrade production schemas.

---

## 10. Idempotency, Outbox, and Inbox

Keep this module small but correct enough to demonstrate the pattern.

### 10.1 Idempotency

Persist idempotency records in the database with a unique scoped key and a request payload hash. Store the original successful response or a stable resource reference so that a repeat request can return the original result.

Acceptance criteria:
- Same key + same payload + same tenant/actor/scope: no duplicate claim.
- Same key + different payload in the same scope: `409 Conflict`.
- Same key in different tenant scopes: no cross-tenant collision.
- Concurrent requests do not create duplicate claims; enforce uniqueness at database level and test race behaviour where practical.

### 10.2 Outbox

Create a minimal `outbox_event` table containing:
- event UUID/ID
- event type
- occurred timestamp in UTC
- tenant identifier
- actor identifier where appropriate
- schema version
- JSON data
- publication status / attempt metadata
- created timestamp

Use a standard envelope conceptually containing `event_id`, `type`, `occurred_at`, `tenant`, `actor`, `data`, and `version`.

For the first version, persist events transactionally and add a small worker/command that reads pending records. Do not claim reliable Azure Service Bus delivery until an actual broker client, retry policy, and operational handling are implemented.

### 10.3 Inbox

Create a minimal inbox record keyed uniquely by consumer + event ID. Processing the same event twice must not repeat the business effect.

Acceptance criteria:
- Duplicate event IDs are detected.
- Event handling is tenant-aware.
- Invalid or unsupported schema versions are rejected or quarantined safely.
- No PHI is placed in event names or unsafe metadata.

---

## 11. Logging, Time, and Configuration

### 11.1 Logging

- Use structured JSON logs (stdlib JSON logging or an explicitly approved structured logging library).
- Include correlation ID, service name, environment, and safe actor/tenant identifiers where policy permits.
- Never log PHI, secrets, access tokens, request bodies, or raw claim payloads.
- Add middleware to accept a valid correlation ID or generate one; return it in the response.
- Validate and length-limit externally supplied correlation IDs.

### 11.2 Time

- Use timezone-aware UTC timestamps, e.g. `datetime.now(timezone.utc)`.
- Use PostgreSQL `timestamptz` for timestamps.
- Do not use naive `datetime.now()` for persisted event or audit times.
- Serialize timestamps in ISO 8601 UTC.

### 11.3 Configuration

Use Pydantic Settings. Read configuration from environment variables. Provide safe local defaults only where appropriate.

Example `.env.example`:

```dotenv
APP_ENV=local
DATABASE_URL=postgresql+psycopg://mini_claims:mini_claims@localhost:5432/mini_claims
LOG_LEVEL=INFO
```

These credentials are local-only examples, not production secrets. Production secrets must never be stored in source code or Docker images.

---

## 12. Performance and Reliability

- Use synchronous endpoints with synchronous SQLAlchemy sessions; do not call blocking functions inside `async def`.
- Paginate every list endpoint.
- Cap page size at 200.
- Use stable sorting.
- Select only fields required by list responses.
- Add indexes based on real query patterns; verify using `EXPLAIN ANALYZE` with representative synthetic data.
- Configure database statement timeout where appropriate.
- Reuse outbound HTTP clients if external HTTP calls are added.
- Configure connect/read timeouts for all external calls.
- Retry only safe/idempotent operations; use bounded retries and backoff.
- Keep heavy work in `worker.py` or a background job mechanism, not inside a request.
- A `202 Accepted` response must only be used after the work has been durably enqueued.
- Do not add Redis, a real message broker, or caching unless there is a demonstrated requirement.

---

## 13. Testing Specification

### 13.1 Unit tests

Test service/business logic for:
- Claim creation rules.
- Duplicate claim reference conflict within one tenant.
- Invalid status transitions if transition rules are added.
- Idempotency behaviour.
- Error mapping.
- Outbox creation as part of a successful write.

### 13.2 API tests

Test:
- `POST /v1/claims` returns 201 and a valid `ClaimOut`.
- Missing `Idempotency-Key` is rejected.
- Invalid request body is rejected.
- Unknown write fields are rejected.
- `GET /v1/claims` pagination defaults and maximum page size.
- `GET /v1/claims/{uuid}` returns 404 when absent.
- Missing permissions are denied.
- Tenant A cannot access Tenant B's claim.
- Error responses have the standard shape and correlation ID.
- API responses do not expose internal ORM-only fields.

### 13.3 PostgreSQL integration tests

Use a real PostgreSQL test instance, preferably via testcontainers when Docker is available.

Test:
- Alembic migrations on a fresh database.
- Unique constraints.
- Transaction rollback.
- Claim + outbox atomicity.
- Idempotency under repeat requests.
- Inbox duplicate event handling.

### 13.4 Coverage

Start with a reasonable threshold such as 80% for the service and 90% for shared helper code if the small scope makes that meaningful. Coverage alone is not proof of correctness; prioritize important branches and security boundaries.

---

## 14. Quality Gates and CI

Configure GitHub Actions to run on pull requests and relevant pushes.

Required checks:
1. `ruff format --check`
2. `ruff check`
3. `mypy`
4. `pytest` with coverage
5. Fresh PostgreSQL database + Alembic upgrade
6. Migration consistency check (`alembic check`, if configured)
7. Security scan: Bandit and/or Ruff S, Gitleaks, `pip-audit`
8. Docker image build and Trivy scan
9. Contract checks for OpenAPI/schema compatibility if a baseline contract is maintained

The single-repository learning project has only one service. The AtlasIQ rule “run all service tests when `libs/` changes” becomes meaningful only when multiple services exist. Document this limitation instead of pretending it is fully tested.

Add a pre-commit configuration for Ruff, Mypy, Gitleaks, and end-of-file checks. CI remains authoritative because local hooks can be bypassed.

---

## 15. Docker and Local Development

Provide:
- A Dockerfile using Python 3.12.
- `compose.yaml` with PostgreSQL and the API if practical.
- Health checks for database readiness.
- Non-root container user where practical.
- No secrets baked into the image.
- `.dockerignore` excluding `.env`, `.git`, caches, test artifacts, and local secrets.

README commands should be tested and documented, for example:

```bash
uv sync --all-groups
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn services.claims.main:app --reload
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

Adjust commands to the final package layout. Do not leave README commands that have not been verified.

---

## 16. Claude Code Preparation

The initial project should be usable without Claude Code. AI configuration is an optional layer, not a runtime dependency.

### 16.1 `CLAUDE.md`

Keep root instructions concise and actionable. Include:
- Project purpose and non-goals.
- Folder structure and allowed dependency direction.
- Commands to run/test/lint/type-check/migrate.
- API/schema/model/service separation.
- Tenant isolation and permission requirements.
- UTC, logging, and no-PHI rules.
- Transaction/idempotency/outbox requirements.
- Dependency policy.
- Definition of done for a code change.
- Explicit statement that the demo authentication is not production authentication.

### 16.2 `.claude/rules/`

Suggested focused rules:
- `python.md`: Python 3.12, Ruff, Mypy, typing and naming.
- `api-design.md`: versioned paths, Pydantic schemas, error format, pagination.
- `database.md`: SQLAlchemy, transactions, Alembic, tenant-scoped queries.
- `security.md`: permissions, no secrets/PHI in logs, safe external calls.
- `testing.md`: unit/API/PostgreSQL tests and required commands.

Use path-scoped rules only when supported by the installed Claude Code version. Avoid duplicating the entire `CLAUDE.md` in every rule file.

### 16.3 Optional workflows

After the core project is stable, add reusable workflows/skills for:
- `add-api`: inspect patterns, propose plan, implement schema/service/endpoint/tests.
- `add-migration`: explain schema change, generate Alembic revision, test fresh upgrade.
- `review-change`: inspect security, tenant isolation, error handling, performance, tests, docs.
- `debug-test`: reproduce failure, isolate cause, make minimal fix, rerun targeted and full tests.

Do not assume a particular custom command format until checking the installed Claude Code version and its official configuration format.

### 16.4 Safe AI workflow

For each task, ask Claude Code to:
1. Inspect relevant files and existing patterns.
2. Summarize the intended change and affected modules.
3. Identify security/data/migration risks.
4. Propose a small implementation plan.
5. Implement only after the plan is clear.
6. Add or update tests.
7. Run required checks and report exact results.
8. Summarize changed files, decisions, limitations, and any checks not run.

Do not permit unattended production access, secret retrieval, destructive database commands, or deployment. Review all diffs before committing.

---


## 17. Code-Level Standard Practice Traceability

### 17.1 Objective

The purpose of this section is to ensure that every significant implementation follows the relevant engineering standard and makes it easy for developers to understand which standard practice is being applied and why.

### 17.2 Requirements

1. Before implementing a feature, identify the relevant standards from the project specification and available engineering standards documentation.
2. Apply the standards in the actual code. Comments alone do not count as implementation.
3. Add concise comments or docstrings to significant modules, classes, functions, or non-obvious design decisions when they help explain the standard practice being followed.
4. Reference the exact standard section or identifier when verified in the source document. Do not invent section numbers.
5. Avoid comments that merely repeat what the code already says.
6. Add tests to verify important practices, including input validation, tenant isolation, authorization, idempotency, error handling, and database constraints, wherever applicable.
7. After each implementation task, report:
   - Standard practices applied
   - Files and functions where they are implemented
   - Tests or checks used to verify them
   - Any standards not applied and the reason

### 17.3 Standard Practice Mapping

Maintain `docs/standard-practice-mapping.md` with these columns:

| Standard Practice | Source Reference | Implementation Location | Verification | Status |
|---|---|---|---|---|
| Configuration management | Verified source section | `app/core/config.py` | Configuration tests | Pending |
| Input validation | Verified source section | `app/schemas/claims.py` | Invalid payload tests | Pending |
| Error handling | Verified source section | Shared error handlers | API error tests | Pending |
| Tenant isolation | Verified source section | Service/data-access layer | Cross-tenant access tests | Pending |
| Logging and correlation IDs | Verified source section | Middleware and logging modules | Request tracing tests | Pending |

Update this mapping whenever a standard practice is implemented or changed. Use `Not Applicable` or `Pending` where appropriate instead of claiming a practice is complete without evidence.

### 17.4 Claude Code Compliance

Claude Code must follow the rules in this section when generating or modifying code. It must explain which standard practices it applied and identify the corresponding implementation locations and verification tests. Detailed AI coding instructions belong in `CLAUDE.md`.

### 17.5 Important Principle

The objective is not to add comments everywhere. The objective is to make important engineering decisions understandable, traceable to the source standards, implemented correctly, and verifiable through tests.

## 18. Module-wise Implementation Roadmap

Implement in this order. Each phase must pass its acceptance criteria before moving on.

### Phase 0 — Repository foundation

**Scope**
- Create repository, `uv` workspace, service package, Python version pin.
- Configure Ruff, Mypy, pytest, `.gitignore`, `.env.example`, README.
- Add Docker Compose PostgreSQL.
- Add minimal FastAPI health endpoint if needed for setup.

**Acceptance criteria**
- Clean environment can install dependencies from lock file.
- App starts locally.
- PostgreSQL becomes healthy.
- No secrets are committed.
- Ruff and Mypy run successfully.

### Phase 1 — Database and migrations

**Scope**
- Configure SQLAlchemy engine/session.
- Implement Claim model.
- Configure Alembic and initial migration.
- Add required constraints/indexes.

**Acceptance criteria**
- Fresh PostgreSQL database upgrades successfully.
- ORM metadata and migration are consistent.
- Database sessions close reliably.
- No SQLite integration-test fallback.

### Phase 2 — Schemas and standard errors

**Scope**
- Add `ClaimCreate`, `ClaimOut`, `ClaimListOut`, and `ErrorOut`.
- Add domain exceptions and centralized handlers.
- Add correlation ID middleware.

**Acceptance criteria**
- Unknown write fields are rejected.
- ORM models are not returned directly.
- Errors follow the standard format.
- Correlation ID is present in logs and response headers.
- Logs contain no request payload or PHI.

### Phase 3 — Demo identity and tenant isolation

**Scope**
- Add development/test-only authentication adapter.
- Add `RequestContext` and permission dependencies.
- Add tenant-scoped repository/service query patterns.

**Acceptance criteria**
- Missing permissions are denied.
- Every claim read is tenant-scoped.
- Cross-tenant reads return 404.
- Tenant is never trusted from the client body.
- Production configuration refuses to use the demo identity adapter.

### Phase 4 — Core APIs

**Scope**
- Implement POST create, GET list, GET details.
- Add pagination, stable sorting, conflict handling.
- Add idempotency key storage and request hashing.

**Acceptance criteria**
- All documented request/response contracts pass tests.
- Same idempotency key and same payload do not create duplicates.
- Same key with different payload returns conflict.
- Page size over 200 is rejected or validated according to the documented contract.
- Queries filter by tenant.

### Phase 5 — Transactions and events

**Scope**
- Add outbox model and event envelope.
- Write claim and outbox event in one transaction.
- Add minimal worker/command for pending outbox records.
- Add inbox deduplication helper and tests.

**Acceptance criteria**
- Failed transaction leaves neither claim nor outbox event.
- Successful creation persists both.
- Duplicate inbox event is not processed twice.
- Unsupported event versions fail safely.
- No claim details/PHI appear in event names or logs.

### Phase 6 — Testing and quality gates

**Scope**
- Unit, API, and PostgreSQL integration tests.
- Coverage configuration.
- Pre-commit and GitHub Actions CI.
- Security and image scanning.

**Acceptance criteria**
- Required CI checks pass.
- Migration tests pass on fresh PostgreSQL.
- Tenant isolation and idempotency tests are present.
- Any skipped checks are documented with reasons.

### Phase 7 — Docker and documentation hardening

**Scope**
- Finalize Dockerfile, Compose, health checks, non-root user, `.dockerignore`.
- Update root and service READMEs.
- Add ADRs for meaningful architectural decisions.

**Acceptance criteria**
- Documented setup works from a clean checkout.
- Container builds reproducibly.
- Image contains no `.env` or secrets.
- README commands have been verified.

### Phase 8 — Claude Code configuration

**Scope**
- Add `CLAUDE.md` and focused rules.
- Optionally add workflows/skills after confirming supported syntax.
- Test AI workflow on a small, bounded change.

**Acceptance criteria**
- AI instructions match actual repository rules.
- AI is instructed to inspect before editing and run tests.
- AI does not treat demo authentication as production-ready.
- All AI-generated diffs are reviewed.
- No unverified tool or permission syntax is included.

---

## 19. Definition of Done

A module is complete only when all applicable items are true:

- [ ] Requirements and acceptance criteria are clear.
- [ ] Code follows the approved folder and dependency structure.
- [ ] Request/response use Pydantic schemas.
- [ ] Business logic is in the service layer.
- [ ] Permissions and tenant isolation are enforced.
- [ ] Writes use correct transaction boundaries.
- [ ] Events use outbox/inbox where applicable.
- [ ] Errors and logs follow the common format.
- [ ] No PHI, secrets, tokens, or sensitive payloads are logged.
- [ ] Unit and API tests cover success and failure cases.
- [ ] PostgreSQL integration/migration tests pass where applicable.
- [ ] Ruff, Mypy, pytest, and security checks pass.
- [ ] API documentation and README are updated.
- [ ] New architectural decisions have an ADR when appropriate.
- [ ] The PR diff has been reviewed; no unrelated changes are included.

---

## 20. Working Agreement for AI-Assisted Development

Use this task template for each phase or module:

```text
Read the repository README, CLAUDE.md, and applicable rules first.

Task:
<one small module or acceptance criterion>

Before coding:
1. Inspect the current structure and relevant code.
2. Restate the requirement and acceptance criteria.
3. Identify affected files, dependencies, migration needs, and security risks.
4. Propose a short implementation plan.
5. Ask before introducing a new dependency or changing an API contract.

Implementation:
- Follow existing project patterns.
- Keep endpoints thin and business logic in services.
- Use Pydantic schemas, SQLAlchemy 2.x, and tenant-scoped queries.
- Add tests for success, validation failure, permission failure, and tenant isolation as relevant.
- Never add real PHI or secrets.
- Do not edit unrelated files.

Validation:
- Run the relevant tests first.
- Run Ruff, Mypy, full tests, and migration checks where applicable.
- Report exact commands and whether each passed.
- Do not claim a check passed if it was not run.

Final response:
- Summarize behaviour and files changed.
- List tests and checks with results.
- Explain any limitations, assumptions, or follow-up work.
```

Keep each task small enough to review. For example, implement configuration first, then database setup, then schemas, then one API at a time. Avoid asking an AI agent to generate the entire repository in one large unreviewed change.

---

## 21. Final Principles

1. The actual AtlasIQ repository, service template, approved libraries, and team decisions override this learning specification.
2. Keep the practice project small; implement a pattern only when it has a defined requirement and a test.
3. Security rules must be enforced in code and tests, not just documented.
4. Do not call a demo implementation production-ready.
5. Prefer clear, tested code over premature abstraction.
6. Use Claude Code as a supervised implementation assistant: inspect, plan, implement, test, review.
7. Keep this document updated as implementation decisions change. Record meaningful decisions in `docs/adr/` rather than silently changing the specification.
