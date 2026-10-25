"""Add anonymous search telemetry (A4)."""
from alembic import op
import sqlalchemy as sa
revision = "a4_search_events"
down_revision = "2f49a98a62a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("search_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("normalized_query", sa.String(200), nullable=False),
        sa.Column("searched_at", sa.DateTime(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sort", sa.String(20), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False))
    op.create_index("ix_search_events_searched_at", "search_events", ["searched_at"])


def downgrade():
    op.drop_index("ix_search_events_searched_at", table_name="search_events")
    op.drop_table("search_events")
