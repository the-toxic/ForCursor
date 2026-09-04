from fastapi.testclient import TestClient


def test_health_and_sources(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "demo"

    sources = client.get("/api/sources")
    assert sources.status_code == 200
    usernames = {item["username"] for item in sources.json()}
    assert {"demo_alpha", "demo_beta", "demo_gamma"} <= usernames


def test_add_invalid_source(client: TestClient) -> None:
    response = client.post("/api/sources", json={"username": "ab"})
    assert response.status_code == 400


def test_fetch_and_stats(client: TestClient) -> None:
    fetch = client.post("/api/fetch")
    assert fetch.status_code == 200
    body = fetch.json()
    assert body["published"] >= 4
    assert body["duplicates"] >= 1

    stats = client.get("/api/stats").json()
    assert stats["published"] == body["published"]
    assert stats["duplicates"] == body["duplicates"]

    items = client.get("/api/items").json()
    assert items
    assert any(item["status"] == "published" for item in items)
    assert any(item["status"] == "duplicate" for item in items)
