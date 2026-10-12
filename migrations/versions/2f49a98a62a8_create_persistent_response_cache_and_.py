"""Create persistent response cache and retrieval records

Revision ID: 2f49a98a62a8
Revises:
Create Date: 2026-10-10 14:12:47.677452

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


# revision identifiers, used by Alembic.
revision = '2f49a98a62a8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_key', sa.String(length=64), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('source_url', sa.String(length=2048), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('synopsis', sa.Text(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('media_type', sa.String(length=16), nullable=False),
    sa.Column('genres', sa.JSON(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('retrieval_text', sa.Text().with_variant(MEDIUMTEXT(), 'mysql'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('curated', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_records')),
    sa.UniqueConstraint('source_key', name=op.f('uq_records_source_key'))
    )
    with op.batch_alter_table('records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_records_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_records_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_records_title'), ['title'], unique=False)
        batch_op.create_index(batch_op.f('ix_records_updated_at'), ['updated_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_records_year'), ['year'], unique=False)

    op.create_table('response_cache',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=True),
    sa.Column('fetched_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('lease_until', sa.DateTime(), nullable=False),
    sa.Column('lease_token', sa.String(length=36), nullable=True),
    sa.Column('retry_after', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_response_cache'))
    )
    with op.batch_alter_table('response_cache', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_response_cache_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_response_cache_provider'), ['provider'], unique=False)



def downgrade():
    with op.batch_alter_table('response_cache', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_response_cache_provider'))
        batch_op.drop_index(batch_op.f('ix_response_cache_expires_at'))

    op.drop_table('response_cache')
    with op.batch_alter_table('records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_records_year'))
        batch_op.drop_index(batch_op.f('ix_records_updated_at'))
        batch_op.drop_index(batch_op.f('ix_records_title'))
        batch_op.drop_index(batch_op.f('ix_records_source'))
        batch_op.drop_index(batch_op.f('ix_records_content_hash'))

    op.drop_table('records')
