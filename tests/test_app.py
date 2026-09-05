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
