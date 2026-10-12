"""Record CRUD, idempotent ingestion, and local text retrieval."""
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Record, utcnow


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def prepare(record):
    record.retrieval_text = "\n".join(filter(None, [record.title, str(record.year or ""), record.media_type,
        record.synopsis, ", ".join(record.genres or []), ", ".join(record.tags or []), record.notes]))
    record.content_hash = digest({"text": record.retrieval_text, "data": record.data or {}, "source_url": record.source_url})
    record.updated_at = utcnow()


def create_record(values):
    record = Record(source="manual", source_key=digest(str(uuid4())), curated=True,
                    synopsis="", media_type="Movie", genres=[], tags=[], notes="", data={})
    for key, value in values.items():
        setattr(record, key, value)
    prepare(record)
    db.session.add(record)
    db.session.commit()
    return record


def update_record(record, values):
    for key, value in values.items():
        setattr(record, key, value)
    record.curated = True
    prepare(record)
    db.session.commit()
    return record


def delete_record(record):
    # A tombstone prevents the next provider refresh from recreating a deleted record.
    record.deleted_at = utcnow()
    record.updated_at = utcnow()
    db.session.commit()


def list_records(query="", source=None, page=1, limit=20):
    stmt = select(Record).where(Record.deleted_at.is_(None))
    if source:
        stmt = stmt.where(Record.source == source)
    for term in query.split()[:10]:
        stmt = stmt.where(Record.retrieval_text.icontains(term, autoescape=True))
    from sqlalchemy import func
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.session.scalars(stmt.order_by(Record.updated_at.desc(), Record.id.desc()).offset((page - 1) * limit).limit(limit)).all()
    return {"count": total, "page": page, "limit": limit, "results": [row.to_dict() for row in rows]}


def ingest(provider, items, source_url):
    """Called inside the cache transaction; preserve owner edits and deletions."""
    for item in items:
        title = item.get("title") or item.get("primaryTitle")
        if not isinstance(title, str) or not title.strip():
            continue
        title = title.strip()[:300]
        identity = item.get("id") or [title.casefold(), item.get("year")]
        source_key = digest([provider, identity])
        record = db.session.scalar(select(Record).where(Record.source_key == source_key).with_for_update())
        if record is None:
            try:
                with db.session.begin_nested():
                    record = Record(source=provider, source_key=source_key, title=title, synopsis="", media_type="Movie",
                                    genres=[], tags=[], notes="", data={}, retrieval_text="", content_hash=digest(title))
                    db.session.add(record)
                    db.session.flush()
            except IntegrityError:
                record = db.session.scalar(select(Record).where(Record.source_key == source_key).with_for_update())
        if record.curated or record.deleted_at:
            continue
        record.title = title
        record.source_url = source_url
        record.synopsis = item.get("synopsis") if isinstance(item.get("synopsis"), str) else ""
        record.year = item.get("year") if type(item.get("year")) is int else None
        record.media_type = "Show" if item.get("type") == "Show" else "Movie"
        record.genres = [g for g in item.get("genres", []) if isinstance(g, str)]
        record.data = item
        record.fetched_at = utcnow()
        prepare(record)
