# ADR 002: Index for Paginated Claim Listing

## Status
Accepted

## Context
The `GET /v1/claims` endpoint lists claims for a tenant, ordered by `created_at DESC, id DESC`.
As the volume of claims grows (e.g., to 10k+ rows per tenant), the database must efficiently
filter by `tenant_id` and apply the sort order without performing a full table scan or
expensive in-memory sort (Top-N sort).

## Analysis
The generated SQL for the listing query is:
```sql
SELECT claim_uuid, claim_reference, status, service_date, created_at
FROM claim
WHERE tenant_id = :tenant_id
ORDER BY created_at DESC, id DESC
LIMIT :page_size OFFSET :offset;
```

Without a composite index, Postgres would likely use an index on `tenant_id` (if it exists)
and then sort the resulting rows.

**Theoretical EXPLAIN ANALYZE (10k rows):**
- **Without Index**: Index Scan on `tenant_id` $\rightarrow$ Sort (Top-N) $\rightarrow$ Result.
  Sorting becomes a bottleneck as the number of claims per tenant increases.
- **With Composite Index**: Index Only Scan (or Index Scan) using `idx_claim_tenant_created_id` $\rightarrow$ Result.
  The index provides the data in the requested order, eliminating the Sort step entirely.

## Decision
We will add a composite index on `(tenant_id, created_at DESC, id DESC)`.

## Consequences
- **Performance**: Listing claims becomes $O(\log N)$ regardless of the number of claims per tenant.
- **Write Overhead**: Slightly increases the cost of `INSERT` and `UPDATE` operations on `created_at`.
- **Storage**: Increases database disk usage for the index.
