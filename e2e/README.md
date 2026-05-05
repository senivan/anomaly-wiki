# E2E Smoke Tests

These tests exercise the deployed Docker Compose stack through `api-gateway`.
They assume the stack is already running and reachable at
`E2E_GATEWAY_BASE_URL` or `http://localhost:8000` by default.

The GitHub Actions workflow `.github/workflows/e2e-smoke.yml` owns the CI
lifecycle:

```bash
docker compose up -d --build
python -m pip install -r e2e/requirements.txt
python -m pytest e2e
docker compose down -v --remove-orphans
```

The first smoke test covers auth, encyclopedia page mutations, media upload and
metadata reads, and search-service reachability through the gateway. It does not
assert page-to-search indexing because `search-indexer` is not part of the
current `main` compose stack.
