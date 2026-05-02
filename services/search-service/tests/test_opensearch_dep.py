from unittest.mock import MagicMock
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from opensearch import get_opensearch_client


def test_opensearch_client_is_injected():
    app = FastAPI()
    fake_client = MagicMock()

    @app.get("/ping")
    def ping(client=Depends(get_opensearch_client)):
        return {"injected": id(client)}

    app.state.opensearch = fake_client
    http = TestClient(app)
    response = http.get("/ping")
    assert response.status_code == 200
    assert response.json()["injected"] == id(fake_client)
