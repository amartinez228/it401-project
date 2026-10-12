"""Integration tests use a real SQL database with mocked external providers."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import select

from app import create_app
from extensions import db
from models import Record, ResponseCache, utcnow
from services.cache_service import cached, CacheBusy


@pytest.fixture
def app(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "test.db"}',
        'RAPIDAPI_KEY': 'private-provider-key', 'RAPIDAPI_HOST': 'example.com',
        'RAPIDAPI_BASE_URL': 'https://example.com',
    })
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def provider(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = [{'id': 'tt1', 'title': 'Arrival', 'rating': 80, 'releaseYear': 2016,
                                   'overview': 'A linguist studies alien communication.'}]
    get = Mock(return_value=response)
    monkeypatch.setattr('services.api_service.requests.get', get)
    return get


OWNER = {'Authorization': 'Bearer test-owner-token'}


def test_crud_and_retrieval(client):
    created = client.post('/api/records', headers=OWNER, json={'title': 'New Movie', 'year': 2020, 'tags': ['space'], 'notes': 'Watch soon'})
    assert created.status_code == 201
    record = created.json
    url = created.headers['Location']
    assert client.get(url).json['title'] == 'New Movie'
    assert client.get('/api/records?q=space').json['count'] == 1
    updated = client.patch(url, headers=OWNER, json={'title': 'Updated Movie', 'tags': ['science']})
    assert updated.status_code == 200
    assert updated.json['content_hash'] != record['content_hash']
    assert client.get('/api/records?q=space').json['count'] == 0
    assert client.get('/api/records?q=science').json['count'] == 1
    assert b'Updated Movie' in client.get('/library').data
    assert client.delete(url, headers=OWNER).status_code == 204
    assert client.get(url).status_code == 404
    assert client.patch(url, headers=OWNER, json={'title': 'No'}).status_code == 404
    assert client.get('/api/records').json['count'] == 0


@pytest.mark.parametrize('payload', [None, [], {}, {'title': ' '}, {'title': 'x' * 301},
    {'title': 'Movie', 'year': True}, {'title': 'Movie', 'genres': 'Drama'},
    {'title': 'Movie', 'source': 'imdb'}, {'title': 'Movie', 'source_url': 'javascript:alert(1)'},
    {'title': 'Movie', 'tags': [3]}, {'title': 'Movie', 'media_type': 'invalid'}])
def test_invalid_records(client, payload):
    response = client.post('/api/records', headers=OWNER, json=payload)
    assert response.status_code == 400
    assert client.get('/api/records').json['count'] == 0


def test_write_authorization(client):
    assert client.post('/api/records', json={'title': 'Movie'}).status_code == 401
    client.post('/signin', data={'email': 'owner@example.com', 'password': 'anything'})
    assert client.post('/api/records', json={'title': 'Movie'}).status_code == 401
    client.application.config['ADMIN_API_TOKEN'] = None
    assert client.post('/api/records', headers=OWNER, json={'title': 'Movie'}).status_code == 503


@pytest.mark.parametrize('query', ['rating=nan', 'rating=-1', 'type=unknown', 'year=abc', 'year=0'])
def test_invalid_search_does_not_spend_quota(client, provider, query):
    assert client.get('/api/rapid/search?q=Arrival&' + query).status_code == 400
    assert client.get('/explore?q=Arrival&' + query).status_code == 400
    provider.assert_not_called()


@pytest.mark.parametrize('query', ['page=0', 'limit=101', 'limit=no', 'source=no'])
def test_invalid_pagination(client, query):
    assert client.get('/api/records?' + query).status_code == 400


def test_persistent_cache_across_app_instances(app, client, provider):
    response = client.get('/api/rapid/search?q=Arrival')
    assert response.headers['X-Data-Cache'] == 'miss'
    assert client.get('/explore?q=arrival').headers['X-Data-Cache'] == 'hit'
    second = create_app('testing', {'SQLALCHEMY_DATABASE_URI': app.config['SQLALCHEMY_DATABASE_URI'],
        'RAPIDAPI_KEY': 'private-provider-key', 'RAPIDAPI_HOST': 'example.com', 'RAPIDAPI_BASE_URL': 'https://example.com'})
    assert second.test_client().get('/api/rapid/search?q=++ARRIVAL++').headers['X-Data-Cache'] == 'hit'
    assert provider.call_count == 1
    records = client.get('/api/records?q=linguist').json
    assert records['count'] == 1
    assert records['results'][0]['source'] == 'streaming'
    assert b'private-provider-key' not in client.get('/api/records').data


def test_cache_parameters_are_isolated(client, provider):
    client.get('/api/rapid/search?q=Arrival')
    client.get('/api/rapid/search?q=Arrival&type=Movie')
    client.application.config['RAPIDAPI_COUNTRY'] = 'gb'
    client.get('/api/rapid/search?q=Arrival&type=Movie')
    assert provider.call_count == 3
    assert client.get('/api/records').json['count'] == 1


def expire(app, old=False):
    with app.app_context():
        entry = db.session.scalar(select(ResponseCache))
        entry.expires_at = utcnow() - timedelta(seconds=1)
        if old:
            entry.fetched_at = utcnow() - timedelta(days=8)
        db.session.commit()


def test_stale_fallback_and_cooldown(app, client, provider):
    client.get('/api/rapid/search?q=Arrival')
    expire(app)
    provider.side_effect = requests.Timeout()
    response = client.get('/api/rapid/search?q=Arrival')
    assert response.status_code == 200
    assert response.headers['X-Data-Cache'] == 'stale'
    assert 'Warning' in response.headers
    assert client.get('/api/rapid/search?q=Arrival').headers['X-Data-Cache'] == 'stale'
    assert provider.call_count == 2


def test_old_stale_data_is_not_served(app, client, provider):
    client.get('/api/rapid/search?q=Arrival')
    expire(app, old=True)
    provider.side_effect = requests.Timeout()
    assert client.get('/api/rapid/search?q=Arrival').status_code == 504
    assert client.get('/api/rapid/search?q=Arrival').status_code == 503
    assert provider.call_count == 2


def test_expired_data_refreshes_and_keeps_curated_changes(app, client, provider):
    client.get('/api/rapid/search?q=Arrival')
    record = client.get('/api/records').json['results'][0]
    url = f'/api/records/{record["id"]}'
    client.patch(url, headers=OWNER, json={'notes': 'My own note'})
    expire(app)
    assert client.get('/api/rapid/search?q=Arrival').headers['X-Data-Cache'] == 'miss'
    assert client.get(url).json['notes'] == 'My own note'
    client.delete(url, headers=OWNER)
    expire(app)
    client.get('/api/rapid/search?q=Arrival')
    assert client.get('/api/records').json['count'] == 0


def test_empty_results_are_cached(client, provider):
    provider.return_value.json.return_value = []
    assert client.get('/api/rapid/search?q=Empty').json['count'] == 0
    assert client.get('/api/rapid/search?q=Empty').headers['X-Data-Cache'] == 'hit'
    assert provider.call_count == 1


def test_database_failure_never_bypasses_cache(app, client, provider, monkeypatch, caplog):
    with app.app_context():
        db.drop_all()
    response = client.get('/api/rapid/search?q=Arrival')
    assert response.status_code == 503
    assert b'private-provider-key' not in response.data
    assert 'SELECT' not in caplog.text
    provider.assert_not_called()


def test_active_lease_suppresses_duplicate_fetch(app):
    with app.test_request_context():
        fetch = Mock(return_value=[])
        cached('test', {}, fetch, 60, 'https://example.com')
        entry = db.session.scalar(select(ResponseCache))
        entry.payload = None
        entry.expires_at = utcnow() - timedelta(seconds=1)
        entry.lease_until = utcnow() + timedelta(seconds=60)
        db.session.commit()
        with pytest.raises(CacheBusy):
            cached('test', {}, fetch, 60, 'https://example.com')
        assert fetch.call_count == 1


def test_sql_like_characters_are_literal(client):
    client.post('/api/records', headers=OWNER, json={'title': 'A Film'})
    assert client.get('/api/records?q=%25').json['count'] == 0
    assert client.get('/api/records?q=%27%20OR%201=1').json['count'] == 0


def test_body_limit(client):
    assert client.post('/api/records', headers=OWNER, json={'title': 'x' * 70000}).status_code == 413


def test_concurrent_refresh_only_fetches_once(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started, release = Event(), Event()
    fetch = Mock()
    def fetch_once():
        fetch()
        started.set()
        assert release.wait(5)
        return []
    def worker():
        with app.test_request_context():
            return cached('concurrent', {}, fetch_once, 60, 'https://example.com')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        assert started.wait(5)
        try:
            second = pool.submit(worker)
            with pytest.raises(CacheBusy):
                second.result(timeout=5)
        finally:
            release.set()
        assert first.result(timeout=5) == []
    assert fetch.call_count == 1


def test_scraping_is_persisted_and_reused(app, client, monkeypatch):
    from services.scraping_service import BoxOfficeService
    fetch = Mock(return_value=[{'title': 'Example', 'rank': 1, 'year': 2020,
                               'worldwide_gross_usd': 1000, 'source_url': BoxOfficeService.SOURCE_URL}])
    monkeypatch.setattr(BoxOfficeService, '_fetch', fetch)
    assert client.get('/api/box-office').headers['X-Data-Cache'] == 'miss'
    assert client.get('/box-office?q=Example').headers['X-Data-Cache'] == 'hit'
    assert fetch.call_count == 1
    record = client.get('/api/records?source=box_office').json['results'][0]
    assert record['data']['worldwide_gross_usd'] == 1000
    assert record['source_url'] == BoxOfficeService.SOURCE_URL


def test_random_recommendations_are_cached(client, provider):
    client.application.config.update(IMDB_API_KEY='private-provider-key', IMDB_API_HOST='example.com',
                                    IMDB_API_BASE_URL='https://example.com')
    provider.return_value.json.return_value = {'primaryTitle': 'Example'}
    assert client.get('/api/imdb/random?type=Movie').headers['X-Data-Cache'] == 'miss'
    assert client.get('/api/imdb/random?type=Movie').headers['X-Data-Cache'] == 'hit'
    assert provider.call_count == 1
    assert client.get('/api/records?source=imdb').json['count'] == 1


def test_distinct_titles_without_provider_ids_do_not_collide(client, provider):
    provider.return_value.json.return_value = [{'title': 'First'}]
    client.get('/api/rapid/search?q=First')
    provider.return_value.json.return_value = [{'title': 'Second'}]
    client.get('/api/rapid/search?q=Second')
    assert client.get('/api/records').json['count'] == 2


def test_cache_and_ingestion_commit_together(app, client, provider, monkeypatch):
    from sqlalchemy.exc import OperationalError
    monkeypatch.setattr('services.cache_service.ingest', Mock(side_effect=OperationalError('private SQL', {}, Exception())))
    assert client.get('/api/rapid/search?q=Arrival').status_code == 503
    with app.app_context():
        entry = db.session.scalar(select(ResponseCache))
        assert entry.payload is None
        assert entry.fetched_at is None
    assert client.get('/api/records').json['count'] == 0


def test_migrations_upgrade_and_schema_match(tmp_path):
    from flask_migrate import upgrade
    from sqlalchemy import inspect
    app = create_app('testing', {'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "migrated.db"}'})
    with app.app_context():
        upgrade()
        assert {'records', 'response_cache', 'alembic_version'} <= set(inspect(db.engine).get_table_names())
    assert app.test_client().post('/api/records', headers=OWNER, json={'title': 'Migrated'}).status_code == 201


def test_ide_script_and_import_use_same_database_folder(monkeypatch, tmp_path):
    import runpy
    from pathlib import Path
    from flask import Flask
    from config import BASE_DIR

    # IDE launches the script from the workspace root (or another working folder).
    # Migration commands import app.py. Both must resolve the same SQLite file.
    monkeypatch.chdir(tmp_path)
    launched = []
    monkeypatch.setattr(Flask, 'run', lambda self, **kwargs: launched.append(self))
    runpy.run_path(str(Path(BASE_DIR) / 'app.py'), run_name='__main__')
    imported = create_app()
    expected = str(Path(BASE_DIR) / 'instance')
    assert launched[0].instance_path == imported.instance_path == expected
    with launched[0].app_context():
        script_database = db.engine.url
    with imported.app_context():
        assert db.engine.url == script_database
