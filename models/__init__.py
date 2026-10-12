"""Persistent provider responses and a source-aware retrieval library."""
from datetime import datetime, timezone

from sqlalchemy.dialects.mysql import MEDIUMTEXT

from extensions import db


def utcnow():
    # MySQL DATETIME stores UTC without a timezone; serialize with Z explicitly.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.isoformat() + "Z" if value else None


class ResponseCache(db.Model):
    __tablename__ = "response_cache"
    key = db.Column(db.String(64), primary_key=True)
    provider = db.Column(db.String(32), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    fetched_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    lease_until = db.Column(db.DateTime, nullable=False)
    lease_token = db.Column(db.String(36))
    retry_after = db.Column(db.DateTime, nullable=False)


class Record(db.Model):
    __tablename__ = "records"
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(64), nullable=False, unique=True)
    source = db.Column(db.String(32), nullable=False, index=True)
    source_url = db.Column(db.String(2048))
    title = db.Column(db.String(300), nullable=False, index=True)
    synopsis = db.Column(db.Text, nullable=False, default="")
    year = db.Column(db.Integer, index=True)
    media_type = db.Column(db.String(16), nullable=False, default="Movie")
    genres = db.Column(db.JSON, nullable=False, default=list)
    tags = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=False, default="")
    data = db.Column(db.JSON, nullable=False, default=dict)
    retrieval_text = db.Column(db.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    schema_version = db.Column(db.Integer, nullable=False, default=1)
    curated = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    fetched_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)

    def to_dict(self):
        fields = ("id", "source", "source_url", "title", "synopsis", "year", "media_type", "genres",
                  "tags", "notes", "data", "retrieval_text", "content_hash", "schema_version", "curated")
        return {**{field: getattr(self, field) for field in fields},
                **{field: iso(getattr(self, field)) for field in ("created_at", "updated_at", "fetched_at")}}
