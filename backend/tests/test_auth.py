from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Auth-Key": ""})
    assert response.status_code == 200


def test_api_rejects_wrong_key(client: TestClient) -> None:
    response = client.get("/api/stats", headers={"X-Auth-Key": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Нужен ключ доступа"


def test_api_accepts_access_key(client: TestClient) -> None:
    response = client.get("/api/stats")
    assert response.status_code == 200
