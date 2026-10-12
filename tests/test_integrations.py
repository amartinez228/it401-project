from unittest.mock import Mock

import pytest
import requests

from app import create_app
from extensions import db
from services.api_service import RapidApiService
from services.scraping_service import BoxOfficeService
from services.streaming_service import StreamingAvailabilityService


HTML = '''<table><tr><th>Rank</th><th>Peak</th><th>Title</th><th>Worldwide gross</th><th>Year</th></tr>
<tr><td>1</td><td>1</td><th><i>A &amp; B</i><sup>[1]</sup> †</th><td>$1,234,567</td><td>2020</td></tr>
<tr><td>2</td><td>2</td><th>Another Movie</th><td></td><td>Unknown</td></tr>
<tr><td>3</td></tr></table>'''


@pytest.fixture
def client():
    app = create_app("testing")
    app.config.update(TESTING=True, RAPIDAPI_KEY="secret-test-value", RAPIDAPI_HOST="example.com", RAPIDAPI_BASE_URL="https://example.com")
    with app.app_context():
        db.create_all()
    return app.test_client()


def test_json_fields_are_selected_and_links_are_safe(client, monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = [{"title": "Movie", "rating": "80", "genres": None, "imageSet": [],
        "cast": [None, "Actor"], "private": "secret-test-value", "streamingOptions": {"us": [None,
        {"service": {"name": "Bad"}, "link": "javascript:alert(1)"}]}}]
    get = Mock(return_value=response)
    monkeypatch.setattr("services.api_service.requests.get", get)
    result = client.get('/api/rapid/search?q=Movie')
    assert result.status_code == 200
    film = result.json['results'][0]
    assert film['rating'] == 4
    assert film['talent'] == ['Actor']
    assert film['streaming_options'] == []
    assert b'secret-test-value' not in result.data
    assert get.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('payload', [None, 'bad', {"error": "secret-test-value"}, [None, 2]])
def test_unexpected_json_is_failure(client, monkeypatch, payload):
    response = Mock(status_code=200)
    response.json.return_value = payload
    monkeypatch.setattr('services.api_service.requests.get', Mock(return_value=response))
    result = client.get('/api/rapid/search?q=Movie')
    assert result.status_code == 502
    assert b'secret-test-value' not in result.data


@pytest.mark.parametrize('failure,status', [(requests.Timeout('secret-test-value'), 504), (requests.ConnectionError('secret-test-value'), 502), (ValueError('invalid JSON'), 502)])
def test_api_failures_are_safe(client, monkeypatch, failure, status, caplog):
    monkeypatch.setattr('services.api_service.requests.get', Mock(side_effect=failure))
    result = client.get('/api/rapid/search?q=Movie')
    assert result.status_code == status
    assert b'secret-test-value' not in result.data
    assert 'secret-test-value' not in caplog.text


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_unsuccessful_provider_status(client, monkeypatch, status):
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    monkeypatch.setattr('services.api_service.requests.get', Mock(return_value=response))
    assert client.get('/api/rapid/search?q=Movie').status_code == 502


def test_redirect_rejected(client, monkeypatch):
    monkeypatch.setattr('services.api_service.requests.get', Mock(return_value=Mock(status_code=302)))
    assert client.get('/api/rapid/search?q=Movie').status_code == 502


def test_insecure_api_url_rejected():
    with pytest.raises(ValueError):
        RapidApiService('http://example.com', 'key', 'example.com')


def test_scraped_records_clean_and_typed():
    rows = BoxOfficeService.parse(HTML)
    assert len(rows) == 2
    assert rows[0] == {'rank': 1, 'title': 'A & B', 'year': 2020, 'worldwide_gross_usd': 1234567, 'source_url': BoxOfficeService.SOURCE_URL}
    assert rows[1]['year'] is None
    assert rows[1]['worldwide_gross_usd'] is None


@pytest.mark.parametrize('html', ['<html>Blocked</html>', '<table></table>', ''])
def test_missing_table_is_explicit_failure(html):
    with pytest.raises(ValueError):
        BoxOfficeService.parse(html)


def test_scraper_routes_and_display(client, monkeypatch):
    monkeypatch.setattr(BoxOfficeService, '_fetch', lambda self: self.parse(HTML))
    response = client.get('/api/box-office?q=another')
    assert response.status_code == 200
    assert response.json['count'] == 1
    page = client.get('/box-office')
    assert page.status_code == 200
    assert b'$1,234,567' in page.data
    assert b'q=A+%26+B' in page.data


def test_scraper_outage(client, monkeypatch):
    monkeypatch.setattr(BoxOfficeService, '_fetch', Mock(side_effect=requests.Timeout()))
    assert client.get('/api/box-office').status_code == 504
    assert client.get('/box-office').status_code == 503


def test_scraper_http_fetch(monkeypatch):
    response = Mock(status_code=200, headers={'Content-Type': 'text/html; charset=utf-8'})
    response.iter_content.return_value = [HTML.encode()]
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    get = Mock(return_value=context)
    monkeypatch.setattr('services.scraping_service.requests.get', get)
    assert len(BoxOfficeService()._fetch()) == 2
    assert get.call_args.args[0] == BoxOfficeService.SOURCE_URL
    assert get.call_args.kwargs['timeout'] == (3.05, 10)


def test_invalid_json_body(client, monkeypatch):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError('not JSON')
    monkeypatch.setattr('services.api_service.requests.get', Mock(return_value=response))
    assert client.get('/api/rapid/search?q=Movie').status_code == 502


@pytest.mark.parametrize('status,content_type,chunks', [
    (302, 'text/html', []), (200, 'application/json', []),
    (200, 'text/html', [b'x' * (BoxOfficeService.MAX_BYTES + 1)])])
def test_scraper_rejects_redirects_non_html_and_large_pages(monkeypatch, status, content_type, chunks):
    response = Mock(status_code=status, headers={'Content-Type': content_type})
    response.iter_content.return_value = chunks
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('services.scraping_service.requests.get', Mock(return_value=context))
    with pytest.raises(ValueError):
        BoxOfficeService()._fetch()


def test_search_validation_avoids_provider_request(client, monkeypatch):
    get = Mock()
    monkeypatch.setattr('services.api_service.requests.get', get)
    assert client.get('/api/rapid/search?q=+++').status_code == 400
    assert client.get('/api/rapid/search', query_string={'q': 'a' * 201}).status_code == 400
    get.assert_not_called()
