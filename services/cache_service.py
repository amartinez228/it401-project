"""Database-backed cache with atomic refresh leases shared across workers."""
from datetime import timedelta
from uuid import uuid4

import requests
from flask import current_app, g
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ResponseCache, iso, utcnow
from services.record_service import digest, ingest


class CacheBusy(Exception):
    pass


def cached(provider, parameters, fetch, ttl, source_url, *, refresh=False):
    key = digest({"schema": 1, "provider": provider, "parameters": parameters})
    now = utcnow()
    entry = db.session.get(ResponseCache, key)
    if entry is None:
        try:
            # MySQL DATETIME(0) rounds fractional seconds, possibly into the
            # future. Start expired so a new row is immediately claimable.
            expired = now - timedelta(seconds=1)
            entry = ResponseCache(key=key, provider=provider, expires_at=expired,
                                  lease_until=expired, retry_after=expired)
            db.session.add(entry)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            entry = db.session.get(ResponseCache, key)

    def result(state):
        g.cache_info = {"status": state, "fetched_at": iso(entry.fetched_at), "expires_at": iso(entry.expires_at)}
        return entry.payload

    def stale_or_busy():
        if entry.payload is not None and entry.fetched_at and entry.fetched_at >= now - timedelta(seconds=current_app.config["CACHE_MAX_STALE_SECONDS"]):
            return result("stale")
        raise CacheBusy("The source is refreshing or temporarily unavailable. Try again shortly.")

    if not refresh and entry.payload is not None and entry.expires_at > now:
        return result("hit")
    if entry.retry_after > now or entry.lease_until > now:
        return stale_or_busy()

    token = str(uuid4())
    conditions = [ResponseCache.key == key, ResponseCache.lease_until <= now,
                  ResponseCache.retry_after <= now]
    if not refresh:
        conditions.append(ResponseCache.expires_at <= now)
    claimed = db.session.execute(update(ResponseCache).where(*conditions).values(
        lease_token=token, lease_until=now + timedelta(seconds=60)))
    db.session.commit()
    if not claimed.rowcount:
        db.session.refresh(entry)
        if entry.payload is not None and entry.expires_at > now:
            return result("hit")
        return stale_or_busy()

    try:
        payload = fetch()
    except (requests.RequestException, ValueError):
        db.session.execute(update(ResponseCache).where(ResponseCache.key == key, ResponseCache.lease_token == token).values(
            lease_until=now, lease_token=None, retry_after=utcnow() + timedelta(seconds=60)))
        db.session.commit()
        if entry.payload is not None and entry.fetched_at and entry.fetched_at >= now - timedelta(seconds=current_app.config["CACHE_MAX_STALE_SECONDS"]):
            return result("stale")
        raise

    fetched_at = utcnow()
    # Cache response and extracted library records commit together. No paid request
    # is attempted when the database is unavailable, and raw provider data is never stored.
    saved = db.session.execute(update(ResponseCache).where(ResponseCache.key == key, ResponseCache.lease_token == token).values(
        payload=payload, fetched_at=fetched_at, expires_at=fetched_at + timedelta(seconds=ttl),
        # Released deadlines must stay in the past after MySQL rounding.
        lease_until=fetched_at - timedelta(seconds=1), lease_token=None,
        retry_after=fetched_at - timedelta(seconds=1)))
    if not saved.rowcount:
        db.session.rollback()
        raise CacheBusy("The source is refreshing. Try again shortly.")
    ingest(provider, payload, source_url)
    db.session.commit()
    db.session.refresh(entry)
    return result("miss")
