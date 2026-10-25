"""Reproducible A4 evaluation and optional browser screenshots; no live API calls.

Run: python scripts/verify_search.py [--screenshots]
Screenshot capture additionally requires: pip install -r requirements-dev.txt
Uses a disposable SQLite database, with the real Alembic migrations and UI.
"""
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import render_template_string
from flask_migrate import upgrade, check
from sqlalchemy import select
from werkzeug.serving import make_server

from app import create_app
from extensions import db
from models import SearchEvent
from services.record_service import create_record, ingest
from services.retrieval import SearchOptions, retrieve


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = create_app('testing', {'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(Path(directory) / 'preview.db')})
        with app.app_context():
            upgrade(directory=str(ROOT / 'migrations'))
            check(directory=str(ROOT / 'migrations'))
            for title, synopsis, kind in [
                ('Arrival', 'A linguist studies alien communication.', 'Movie'),
                ('Arrival Stories', 'A documentary about migration.', 'Show'),
                ('Contact', "An alien signal changes a scientist's life.", 'Movie'),
                ('The Visitor', 'An arrival sparks a family reunion.', 'Movie'),
                ('Music Room', 'Musicians prepare a concert.', 'Movie'),
                ('Silent Stage', 'A musician rehearses a concert.', 'Movie'),
            ]:
                create_record(dict(title=title, synopsis=synopsis, media_type=kind))
            judgments = [
                ('arrival', ['Arrival'], 'Find the film titled Arrival'),
                ('alien communication', ['Arrival'], 'Find films about alien communication'),
                ('concert', ['Music Room', 'Silent Stage'], 'Find concert stories'),
                ('music', ['Music Room', 'Silent Stage'], 'Find stories about music or musicians'),
                ('musicians', ['Music Room', 'Silent Stage'], 'Find stories about musicians'),
            ]
            reports = []
            for query, relevant, intent in judgments:
                rows = retrieve(SearchOptions(q=query))['results']
                actual = [r['title'] for r in rows]
                useful = set(actual) & set(relevant)
                reports.append(dict(query=query, intent=intent, expected=relevant, actual=actual,
                    false_positives=sorted(set(actual)-set(relevant)), missed=sorted(set(relevant)-set(actual)),
                    first_useful_rank=next((i+1 for i,t in enumerate(actual) if t in relevant), None),
                    precision=len(useful)/len(actual) if actual else None, recall=len(useful)/len(relevant)))
            target = ROOT / 'docs/search-evaluation.json'
            target.write_text(json.dumps({'database': 'Disposable SQLite; not live MySQL validation', 'queries': reports}, indent=2), encoding='utf-8')
            # Exercise the A3 ingestion pipeline using clearly labeled synthetic data.
            ingest('streaming', [dict(id='preview-space-' + str(i), title=f'Space Journal {i:02}',
                synopsis='A fictional expedition explores space and distant worlds.', year=2024, type='Movie', genres=['Science Fiction'])
                for i in range(1, 24)], 'https://example.com/synthetic-preview')
            db.session.commit()
        if '--screenshots' not in sys.argv:
            print(target)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
            return
        # Preview-only telemetry view; never registered by the real application.
        @app.get('/preview-telemetry')
        def telemetry():
            events = db.session.scalars(select(SearchEvent).order_by(SearchEvent.id.desc())).all()
            return render_template_string('''{% extends 'base.html' %}{% block content %}
<section class="explore-hero"><div class="content-shell"><p class="eyebrow light">A4 verification</p><h1>Search telemetry.</h1><p>Actual persisted events from synthetic screenshot searches. No user identity is stored.</p></div></section>
<section class="catalog-section"><div class="content-shell"><table style="width:100%;text-align:left;line-height:3"><tr><th>Query</th><th>UTC time</th><th>Matches</th><th>Filters</th><th>Sort</th><th>Page</th></tr>{% for e in events %}<tr><td>{{ e.query }}</td><td>{{ e.searched_at }}</td><td>{{ e.result_count }}</td><td>{{ e.filters }}</td><td>{{ e.sort }}</td><td>{{ e.page }}</td></tr>{% endfor %}</table></div></section>{% endblock %}''', events=events)
        server = make_server('127.0.0.1', 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
                base = f'http://127.0.0.1:{server.server_port}'
                for name, path in [
                    ('01-search-form', '/search'),
                    ('02-ranked-results', '/search?q=arrival'),
                    ('03-filtered-results', '/search?q=arrival&type=Show&source=manual'),
                    ('04-sorted-results', '/search?q=arrival&sort=title'),
                    ('05-pagination', '/search?q=space&type=Movie&source=streaming&sort=title&page=2'),
                    ('06-no-results', '/search?q=unicorn'),
                    ('07-search-telemetry', '/preview-telemetry'),
                ]:
                    response = page.goto(base+path)
                    assert response.status == 200
                    page.screenshot(path=str(ROOT / 'docs/screenshots' / (name+'.png')), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.goto(base+'/search?q=arrival')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(ROOT / 'docs/screenshots/08-mobile-search.png'), full_page=True)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        print('Evaluation and screenshots saved under docs/.')


if __name__ == '__main__':
    main()
