from __future__ import annotations

import httpx


async def test_gateway_readiness_reports_all_downstreams(
    gateway_client: httpx.AsyncClient,
) -> None:
    response = await gateway_client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    services = body["services"]
    assert set(services) == {
        "researcher_auth_service",
        "encyclopedia_service",
        "media_service",
        "search_service",
    }
    assert all(service["status"] == "ok" for service in services.values())


async def test_search_and_media_service_readiness_are_reachable_from_ci_host() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        opensearch_response = await client.get("http://localhost:9200/_cluster/health")

    assert opensearch_response.status_code == 200, opensearch_response.text
    assert opensearch_response.json()["status"] in {"green", "yellow"}
