"""Database-only retrieval: normalize, match, filter, score, paginate, record."""
from dataclasses import dataclass

from flask import current_app
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Record, SearchEvent
from services.validation import ValidationError, integer, text

SOURCES = ("manual", "streaming", "imdb", "box_office")
SORTS = {"relevance": "Relevance", "newest": "Newest saved", "oldest": "Oldest saved", "title": "Title A-Z"}
PAGE_SIZE = 10


@dataclass
class SearchOptions:
    q: str = ""
    source: str = "all"
    media_type: str = "all"
    sort: str = "relevance"
    page: int = 1

    @property
    def normalized(self):
        return " ".join(self.q.lower().split())

    def parameters(self, page=1):
        return dict(q=self.q, source=self.source, type=self.media_type, sort=self.sort, page=page)


def parse_options(args):
    # Keep original capitalization for display; matching normalizes whitespace/case.
    q = text(args.get("q", ""), "Search query", 200)
    source = args.get("source", "all")
    media_type = args.get("type", "all")
    sort = args.get("sort", "relevance")
    if source not in ("all", *SOURCES):
        raise ValidationError("Choose a listed source or All sources.")
    if media_type not in ("all", "Movie", "Show"):
        raise ValidationError("Choose Movies, Shows, or All formats.")
    if sort not in SORTS:
        raise ValidationError("Choose a listed sorting option.")
    page = integer(args.get("page", "1"), "Page", 1, 10000)
    if len(q.split()) > 20:
        raise ValidationError("Use at most 20 search terms.")
    return SearchOptions(q, source, media_type, sort, page)


def retrieve(options):
    """Every term must occur in title OR synopsis OR retrieval_text (Boolean AND)."""
    stmt = select(Record).where(Record.deleted_at.is_(None))
    terms = options.normalized.split()
    score = case((func.lower(Record.title) == options.normalized, 5), else_=0)
    for term in terms:
        title = Record.title.icontains(term, autoescape=True)
        synopsis = Record.synopsis.icontains(term, autoescape=True)
        other = Record.retrieval_text.icontains(term, autoescape=True)
        stmt = stmt.where(or_(title, synopsis, other))
        score = score + case((title, 3), else_=0) + case((synopsis, 1), else_=0)
    if options.source != "all":
        stmt = stmt.where(Record.source == options.source)
    if options.media_type != "all":
        stmt = stmt.where(Record.media_type == options.media_type)
    count = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
    options.page = min(options.page, pages)
    ordering = {
        "relevance": (score.desc(), Record.updated_at.desc()),
        "newest": (Record.created_at.desc(),),
        "oldest": (Record.created_at.asc(),),
        "title": (func.lower(Record.title).asc(),),
    }[options.sort]
    rows = db.session.execute(stmt.add_columns(score.label("score")).order_by(
        *ordering, Record.id.asc()).offset((options.page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    # Materialize before telemetry commits/rollbacks can expire ORM objects.
    results = [dict(record.to_dict(), score=int(value)) for record, value in rows]
    return dict(results=results, count=count, pages=pages, page=options.page,
                start=(options.page - 1) * PAGE_SIZE + 1 if count else 0,
                end=min(options.page * PAGE_SIZE, count))


def record_search(options, count):
    try:
        db.session.add(SearchEvent(query=options.q, normalized_query=options.normalized,
            result_count=count, filters={"source": options.source, "type": options.media_type},
            sort=options.sort, page=options.page))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Search telemetry could not be saved")
