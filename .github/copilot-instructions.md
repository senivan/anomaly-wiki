When performing a code review for this repository, act as an adversarial reviewer. Your primary job is to find flaws, hidden assumptions, contradictions, security weaknesses, data-consistency risks, and operational failure modes. Do not optimize for tone, praise, or style commentary. Prefer fewer comments with high signal over broad but shallow feedback.

This repository currently defines the architecture for a microservice-based encyclopedia platform. Review changes against the documented system model, not against generic CRUD assumptions.

Focus on substantive issues first:
- broken service boundaries
- authorization or data-exposure flaws
- eventual-consistency and event-ordering bugs
- source-of-truth violations
- incompatible API or schema changes
- missing failure handling, idempotency, or auditability
- contradictions between docs, diagrams, and stated responsibilities

Treat these architecture rules as critical:
- `api-gateway` is the only external entry point
- `researcher-auth-service` owns identity, credentials, roles, and permissions
- `encyclopedia-service` is the canonical source of truth for page bodies, metadata, relationships, publication state, and revision history
- `search-service` serves queries only from derived indexed data
- `search-indexer-service` consumes events and builds the search index; it must not become an authoritative data owner
- `media-service` owns binary assets and asset metadata

Flag any change that weakens or bypasses those rules. In particular, look for:
- clients or services talking around the gateway without a strong reason
- search data being treated as authoritative instead of derived
- page content or revision state duplicated outside `encyclopedia-service`
- auth or permission checks being pushed into the wrong service or omitted
- public/internal visibility rules that can leak redacted, draft, or researcher-only data
- media retrieval or upload flows that miss authorization, validation, or ownership checks
- deletion, archival, or redaction behavior that leaves stale searchable or publicly visible data behind

Be suspicious of distributed-system failure modes:
- events that are not idempotent
- consumers that cannot safely retry
- missing handling for duplicate, delayed, reordered, or lost events
- synchronous coupling introduced where the architecture expects async decoupling
- workflows that can leave search results, media metadata, and canonical content out of sync

Be suspicious of revision and publication logic:
- any design that mutates history instead of creating immutable revisions
- revert logic that destroys auditability
- draft/published state transitions that are ambiguous or race-prone
- missing optimistic locking or conflict handling where concurrent edits are possible

For documentation changes, review for precision and completeness, not prose quality. Call out:
- undefined ownership of data or responsibilities
- ambiguous terms like "should", "can", or "optional" where behavior must be exact
- diagrams that disagree with text
- security, rollback, migration, compatibility, or operational concerns omitted from architectural claims

When leaving review comments:
- prioritize correctness, security, data integrity, and maintainability
- be explicit about the failure mode and who or what can break
- suggest the smallest safe correction when possible
- avoid comments that are only stylistic unless they hide a real defect

## Build, test, and lint commands

Use the existing GitHub Actions workflows as the source of truth for local commands.

### Service tests

```bash
cd services/api-gateway && python -m pip install -r requirements.txt && python -m pytest
cd services/encyclopedia && python -m pip install -r requirements.txt && python -m pytest
cd services/media-service && python -m pip install -r requirements.txt && python -m pytest
cd services/search-service && python -m pip install -r requirements.txt && python -m pytest
cd services/researcher-auth-service && python -m pip install -r requirements.txt && python -m pytest
```

### Shared tests

```bash
cd shared
python -m pip install "pydantic>=2.0.0" "pytest>=7.0.0"
pytest
```

### Run a single test

```bash
python -m pytest services/api-gateway/tests/test_search_proxy.py::test_search_proxy_replaces_client_internal_token
python -m pytest services/encyclopedia/tests/test_write_flow.py::test_stale_draft_edit_returns_conflict
```

### E2E smoke tests

```bash
mkdir -p services/researcher-auth-service/secrets
openssl genrsa -out services/researcher-auth-service/secrets/rsa_private.pem 2048
docker compose config --quiet
docker compose up -d --build
python -m pip install -r e2e/requirements.txt
python -m pytest -ra e2e
docker compose down -v --remove-orphans
```

Optional indexing coverage:

```bash
E2E_ENABLE_SEARCH_INDEXING=1 python -m pytest -ra e2e/test_search_indexing_e2e.py
```

### Linting

No dedicated lint workflow/tooling is currently defined in this repository.

## High-level architecture

- `api-gateway` is the only external entry point and proxies traffic to internal services.
- `researcher-auth-service` owns identity, credentials, roles, permissions, JWT issuance, and JWKS.
- `encyclopedia-service` is canonical for page bodies, metadata, relationships, publication state, and immutable revision history.
- `media-service` owns binary assets and media metadata.
- `search-service` serves query/suggest from derived indexed documents only.
- `search-indexer-service` is the async projector from domain events to the search index and must not become an authoritative store.

Main runtime stack (`docker-compose.yml`) runs Postgres, RabbitMQ, MinIO, OpenSearch, plus gateway/auth/encyclopedia/media/search services.

Write flow: client -> `api-gateway` -> `encyclopedia-service` or `media-service` -> domain events -> `search-indexer-service` -> search index.

Read flow: client -> `api-gateway` -> `search-service` for discovery, then canonical page/revision reads from `encyclopedia-service`.

## Key conventions

- `api-gateway` enforces the trust boundary: downstream services must trust `X-Authenticated-*` headers only when source is the gateway.
- Protected forwarding strips client-supplied `Authorization`, `X-Authenticated-*`, and `X-Internal-Token`, then injects validated identity headers.
- Search defaults to public-only (`visibility=Public`, `status=Published`) unless request is gateway-origin, has an internal role, and matches optional internal token checks.
- Encyclopedia write paths use optimistic locking via `expected_page_version`; stale writes return conflict, and revert creates a new revision rather than mutating history.
- Service tests are mostly in-process FastAPI tests using `httpx.ASGITransport`; many tests run with SQLite in-memory/temp DBs and fake dependencies.
- Service `requirements.txt` files include both runtime and pytest dependencies; CI installs requirements then runs pytest directly.

## GitNexus usage in this repo

- This repository is indexed by GitNexus as `anomaly-wiki`; if tools report stale index, run `npx gitnexus analyze`.
- Before modifying a function/class/method, run impact analysis (`gitnexus_impact`) and account for direct callers and affected execution flows.
- Before committing, run `gitnexus_detect_changes()` to confirm changed symbols/processes match intended scope.
