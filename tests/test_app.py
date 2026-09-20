import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app("development")
    app.config.update(
        TESTING=True,
        RAPIDAPI_KEY=None,
        RAPIDAPI_HOST=None,
        RAPIDAPI_BASE_URL=None,
        IMDB_API_KEY=None,
        IMDB_API_HOST=None,
        IMDB_API_BASE_URL=None,
    )
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
        RAPIDAPI_COUNTRY="us",
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
    assert captured["params"] == {"title": "Arrival", "country": "us"}
    assert b"private-test-key" not in response.data


def test_explore_uses_streaming_api_for_title_search(client, monkeypatch):
    client.application.config.update(
        RAPIDAPI_KEY="private-test-key",
        RAPIDAPI_HOST="streaming.example.rapidapi.com",
        RAPIDAPI_BASE_URL="https://streaming.example.rapidapi.com",
        RAPIDAPI_SEARCH_PATH="/shows/search/title",
        RAPIDAPI_QUERY_PARAMETER="title",
        RAPIDAPI_COUNTRY="us",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "id": "movie/123",
                "title": "Batman Begins",
                "showType": "movie",
                "releaseYear": 2005,
                "runtime": 140,
                "rating": 84,
                "genres": [{"id": "action", "name": "Action"}],
                "directors": ["Christopher Nolan"],
                "cast": ["Christian Bale"],
                "overview": "Bruce Wayne becomes Batman.",
                "imageSet": {
                    "verticalPoster": {"w480": "https://images.example/batman.jpg"},
                },
                "streamingOptions": {
                    "us": [{
                        "service": {"name": "Prime Video"},
                        "type": "rent",
                        "link": "https://watch.example/batman",
                    }],
                },
            }]

    def fake_get(url, headers, params, timeout):
        captured.update(url=url, headers=headers, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("services.api_service.requests.get", fake_get)

    response = client.get("/explore?q=batman&type=Movie")

    assert response.status_code == 200
    assert b"Batman Begins" in response.data
    assert b"Prime Video" in response.data
    assert b"https://images.example/batman.jpg" in response.data
    assert b"Live movie and streaming data" in response.data
    assert captured["params"] == {
        "title": "batman",
        "country": "us",
        "show_type": "movie",
    }


def test_imdb_api_requires_configuration(client):
    response = client.get("/api/imdb/random")

    assert response.status_code == 503
    assert response.get_json()["error"] == "IMDb236 is not configured."


def test_imdb_random_api_uses_shared_secret_server_side(client, monkeypatch):
    client.application.config.update(
        IMDB_API_KEY="private-test-key",
        IMDB_API_HOST="imdb236.p.rapidapi.com",
        IMDB_API_BASE_URL="https://imdb236.p.rapidapi.com",
        IMDB_RANDOM_PATH="/api/imdb/random",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "id": "tt-test",
                "primaryTitle": "A Surprise Movie",
                "type": "movie",
            }]

    def fake_get(url, headers, params, timeout):
        captured.update(url=url, headers=headers, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("services.api_service.requests.get", fake_get)

    response = client.get("/api/imdb/random?type=Movie&genre=Science+Fiction")

    assert response.status_code == 200
    assert response.get_json()[0]["primaryTitle"] == "A Surprise Movie"
    assert captured["url"] == "https://imdb236.p.rapidapi.com/api/imdb/random"
    assert captured["params"] == {"type": "movie", "genre": "Sci-Fi"}
    assert captured["headers"]["X-RapidAPI-Key"] == "private-test-key"
    assert b"private-test-key" not in response.data


def test_surprise_me_redirects_to_streaming_search(client, monkeypatch):
    client.application.config.update(
        IMDB_API_KEY="private-test-key",
        IMDB_API_HOST="imdb236.p.rapidapi.com",
        IMDB_API_BASE_URL="https://imdb236.p.rapidapi.com",
        IMDB_RANDOM_PATH="/api/imdb/random",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"primaryTitle": "A Surprise Movie"}

    monkeypatch.setattr(
        "services.api_service.requests.get",
        lambda url, headers, params, timeout: FakeResponse(),
    )

    response = client.get("/explore?action=surprise&type=Movie")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/explore?q=A+Surprise+Movie&type=Movie"
    )


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
