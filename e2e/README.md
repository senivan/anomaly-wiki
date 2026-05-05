# E2E Smoke Tests

These tests exercise the deployed Docker Compose stack through `api-gateway`.
They assume the stack is already running and reachable at
`E2E_GATEWAY_BASE_URL` or `http://localhost:8000` by default.

The GitHub Actions workflow `.github/workflows/e2e-smoke.yml` owns the CI
lifecycle:

```bash
COMPOSE_PROJECT_NAME=anomaly-wiki-e2e docker compose up -d --build
python -m pip install -r e2e/requirements.txt
python -m pytest -ra e2e --e2e-report-path e2e-artifacts/e2e-smoke-report.md
COMPOSE_PROJECT_NAME=anomaly-wiki-e2e docker compose down -v --remove-orphans
```

Coverage includes auth, encyclopedia page mutations, media upload and metadata
reads, gateway negative-auth checks, readiness checks, and search-service
reachability through the gateway.

Page-to-search indexing coverage is present but skipped by default because
`search-indexer` is not part of the current `main` compose stack. Enable it with:

```bash
E2E_ENABLE_SEARCH_INDEXING=1 python -m pytest -ra e2e/test_search_indexing_e2e.py
```

Each E2E run can emit a markdown summary report (pass/fail per test) via
`--e2e-report-path`:

```bash
python -m pytest -ra e2e --e2e-report-path e2e-artifacts/e2e-smoke-report.md
```

Report contract:
- includes suite metadata (start/end time, collected/executed counts, exit status)
- summarizes passed/failed/skipped counts
- lists every executed test with outcome, phase, and duration
- includes failure details for failed tests
