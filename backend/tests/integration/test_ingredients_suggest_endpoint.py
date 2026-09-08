from fastapi.testclient import TestClient

from app.main import app


def test_suggest_returns_matches():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest", params={"q": "onion"})
    assert response.status_code == 200
    body = response.json()
    assert any(s["display_name"].lower() == "onion" for s in body["suggestions"])


def test_suggest_query_too_short_is_rejected():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest", params={"q": ""})
    assert response.status_code == 422


def test_suggest_query_too_long_is_rejected():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest", params={"q": "a" * 51})
    assert response.status_code == 422


def test_suggest_limit_is_bounded():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest", params={"q": "a", "limit": 1000})
    assert response.status_code == 422


def test_suggest_missing_query_is_rejected():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest")
    assert response.status_code == 422


def test_suggest_never_exposes_database_internals():
    client = TestClient(app)
    response = client.get("/api/ingredients/suggest", params={"q": "onion"})
    body = response.json()
    for suggestion in body["suggestions"]:
        assert set(suggestion.keys()) == {"canonical_id", "display_name"}
