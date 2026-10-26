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
