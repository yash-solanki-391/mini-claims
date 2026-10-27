# Standard Practice Mapping

| Practice | Source Section | File/Function | Test | Status |
| :--- | :--- | :--- | :--- | :--- |
| Single Engine | Data and DB | `app/core/db.py:engine` | N/A | Verified |
| Request-scoped Session | Data and DB | `app/core/db.py:get_db` | N/A | Verified |
| Synchronous SQLAlchemy 2.0 | Data and DB | `app/models/claim.py` | N/A | Verified |
| Tenant-filtered DB level | Security and tenancy | `app/models/claim.py` | `test_claim_unique_constraint` | Implemented |
| UUIDs for public IDs | Data and DB | `app/models/claim.py:Claim.uuid` | N/A | Verified |
| Timestamptz / UTC | Data and DB | `app/models/claim.py:Claim.created_at` | N/A | Verified |
|- Idempotency (Phase 2) | API behaviour | TBD | TBD | Pending |
| Permission per endpoint | CLAUDE.md: Security and tenancy | `app/api/deps.py:require_permission`, `app/api/v1/endpoints/claims.py` | `tests/test_auth.py::test_role_without_permission_is_denied` | Verified |
| Tenant/user from verified context only | CLAUDE.md: Security and tenancy | `app/api/deps.py:get_request_context`, `app/core/demo_auth.py:verify_demo_token` | `tests/test_auth.py::test_valid_token_identity_comes_from_claims` | Verified |
| Demo auth fails closed outside local/test | CLAUDE.md: Security and tenancy | `app/core/demo_auth.py:_secret` | `tests/test_auth.py::test_valid_token_is_refused_outside_local_and_test` | Verified |
| Custom demo token (deviation from "no custom token handling") | `docs/atlasiq_python_standards (1).md`: Auth | `app/core/demo_auth.py`, ADR 0003 | `tests/test_auth.py` | Deviation (learning only) |
| Correlation id validated, returned, logged | CLAUDE.md: Logging and events | `app/middleware/correlation.py` | `tests/test_logging.py` | Verified |
| No headers/tokens/PHI in logs | CLAUDE.md: Logging and events | `app/middleware/correlation.py`, `app/core/error_handlers.py:generic_exception_handler` | `tests/test_logging.py::test_request_log_omits_headers_and_query`, `test_unhandled_exception_logs_type_not_message` | Verified |
