import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"BetterBoxd" in response.data
    assert b"Made by Adrian Martinez" in response.data


def test_explore_filters_json_catalog(client):
    response = client.get("/explore?type=Movie&genre=Science+Fiction&rating=4.5")
    assert response.status_code == 200
    assert b"Afterlight" in response.data
    assert b"Borrowed Time" not in response.data
    assert b"The Small Hours" not in response.data


def test_media_api_returns_filtered_json(client):
    response = client.get("/api/media?q=music")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["count"] == 2
    assert {item["title"] for item in payload["results"]} == {
        "Greenroom Summer",
        "Deep Cut",
    }


def test_rapid_api_requires_configuration(client):
    response = client.get("/api/rapid/search?q=arrival")
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["error"] == "RapidAPI is not configured."
    assert "RAPIDAPI_KEY" in payload["missing"]


def test_rapid_api_search_keeps_credentials_server_side(client, monkeypatch):
    client.application.config.update(
        RAPIDAPI_KEY="private-test-key",
        RAPIDAPI_HOST="movies.example.rapidapi.com",
        RAPIDAPI_BASE_URL="https://movies.example.rapidapi.com",
        RAPIDAPI_SEARCH_PATH="/titles/search",
        RAPIDAPI_QUERY_PARAMETER="title",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"title": "Arrival"}]}

    def fake_get(url, headers, params, timeout):
        captured.update(url=url, headers=headers, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("services.api_service.requests.get", fake_get)

    response = client.get("/api/rapid/search?q=Arrival")

    assert response.status_code == 200
    assert response.get_json()["results"][0]["title"] == "Arrival"
    assert captured["url"] == "https://movies.example.rapidapi.com/titles/search"
    assert captured["headers"]["X-RapidAPI-Key"] == "private-test-key"
    assert captured["headers"]["X-RapidAPI-Host"] == "movies.example.rapidapi.com"
    assert captured["params"] == {"title": "Arrival"}
    assert b"private-test-key" not in response.data


def test_signin_and_signout(client):
    response = client.post(
        "/signin",
        data={"email": "adrian@example.com", "password": "demo"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Hi, Adrian" in response.data

    response = client.post("/signout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign in" in response.data
