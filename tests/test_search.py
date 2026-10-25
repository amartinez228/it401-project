"""A4 retrieval contracts, failure isolation, and relevance evaluation."""
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app import create_app
from extensions import db
from models import Record, SearchEvent
from services.record_service import create_record, delete_record
from services.retrieval import SearchOptions, retrieve


@pytest.fixture
def app(tmp_path):
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'search.db'}"})
    with app.app_context():
        db.create_all()
        for title, synopsis, kind in [
            ("Arrival", "A linguist studies alien communication.", "Movie"),
            ("Arrival Stories", "A documentary about migration.", "Show"),
            ("Contact", "An alien signal changes a scientist's life.", "Movie"),
            ("The Visitor", "An arrival sparks a family reunion.", "Movie"),
            ("Music Room", "Musicians prepare a concert.", "Movie"),
            ("Silent Stage", "A musician rehearses a concert.", "Movie"),
        ]:
            create_record(dict(title=title, synopsis=synopsis, media_type=kind))
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_ranking_normalization_and_telemetry(app, client, monkeypatch):
    external = Mock(side_effect=AssertionError("Search must never fetch external sources"))
    monkeypatch.setattr("requests.get", external)
    response = client.get("/search?q=++ArRiVaL++")
    assert response.status_code == 200
    assert b'value="ArRiVaL"' in response.data
    assert response.data.index(b'>Arrival</a>') < response.data.index(b'>Arrival Stories</a>') < response.data.index(b'>The Visitor</a>')
    with app.app_context():
        event = db.session.scalar(select(SearchEvent))
        assert (event.query, event.normalized_query, event.result_count) == ("ArRiVaL", "arrival", 3)
        assert event.searched_at is not None
    external.assert_not_called()


def test_boolean_filters_and_deletion(app, client):
    assert b'1 results found' in client.get('/search?q=arrival&type=Show&source=manual').data
    assert b'No matching records' in client.get('/search?q=arrival&type=Show&source=streaming').data
    assert b'1 results found' in client.get('/search?q=alien+communication').data
    with app.app_context():
        delete_record(db.session.scalar(select(Record).where(Record.title == 'Arrival')))
    assert b'2 results found' in client.get('/search?q=arrival').data


@pytest.mark.parametrize('query', ['page=0', 'page=bad', 'source=bad', 'type=bad', 'sort=bad', 'q='+'x'*201, 'q='+'a+'*21])
def test_validation_retains_form(client, query):
    response = client.get('/search?' + query)
    assert response.status_code == 400
    assert b'Keyword or phrase' in response.data
    assert b'Traceback' not in response.data


def test_empty_literal_wildcards_and_sql_input(client, app):
    for q in ['', '+++']:
        assert b'Enter a keyword to begin' in client.get('/search?q=' + q).data
    for q in ['%25', '_', "%27+OR+1%3D1--"]:
        assert b'No matching records' in client.get('/search?q=' + q).data
    with app.app_context():
        assert db.session.scalar(select(db.func.count()).select_from(SearchEvent)) == 3


def test_pagination_sort_and_detail(app, client):
    with app.app_context():
        for i in range(23):
            create_record(dict(title=f'Space {i:02}', media_type='Movie'))
    response = client.get('/search?q=space&type=Movie&source=manual&sort=title&page=2')
    assert b'11' in response.data and b'20 of 23' in response.data
    assert response.data.count(b'class="catalog-card search-result"') == 10
    assert b'q=space&amp;source=manual&amp;type=Movie&amp;sort=title&amp;page=3' in response.data
    assert b'Page 3 of 3' in client.get('/search?q=space&page=9999').data
    for sort in ['newest', 'oldest', 'title', 'relevance']:
        assert client.get('/search?q=space&sort='+sort).status_code == 200
    assert b'Synopsis' in client.get('/library/1').data
    assert client.get('/library/9999').status_code == 404


def test_database_and_telemetry_failure(app, client, monkeypatch):
    with app.app_context():
        SearchEvent.__table__.drop(db.engine)
    response = client.get('/search?q=arrival')
    assert response.status_code == 200 and b'3 results found' in response.data
    with app.app_context():
        Record.__table__.drop(db.engine)
    response = client.get('/search?q=arrival')
    assert response.status_code == 503
    assert b'Search is temporarily unavailable' in response.data
    assert b'SELECT' not in response.data


@pytest.mark.parametrize('query,expected', [
    ('arrival', ['Arrival', 'Arrival Stories', 'The Visitor']),
    ('alien communication', ['Arrival']),
    ('concert', ['Silent Stage', 'Music Room']),
    ('music', ['Music Room', 'Silent Stage']),
    ('musicians', ['Music Room']),
])
def test_evaluation_queries(app, query, expected):
    with app.app_context():
        result = retrieve(SearchOptions(q=query))
        assert [r['title'] for r in result['results']] == expected
