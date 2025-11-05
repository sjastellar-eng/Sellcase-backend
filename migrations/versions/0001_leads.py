from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_leads'
down_revision = None

def upgrade():
    op.create_table(
        'leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ts', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('form_name', sa.String(length=100)),
        sa.Column('name', sa.String(length=200)),
        sa.Column('phone', sa.String(length=100)),
        sa.Column('email', sa.String(length=200)),
        sa.Column('utm_source', sa.String(length=100)),
        sa.Column('utm_medium', sa.String(length=100)),
        sa.Column('utm_campaign', sa.String(length=100)),
        sa.Column('utm_content', sa.String(length=100)),
        sa.Column('utm_term', sa.String(length=100)),
        sa.Column('page', sa.String(length=50)),
        sa.Column('raw', postgresql.JSONB),
        sa.Column('dedupe_hash', sa.Text(), nullable=False, unique=True),
    )
    op.create_index('ix_leads_ts', 'leads', ['ts'])
    op.create_index('ix_leads_email', 'leads', ['email'])
    op.create_index('ix_leads_phone', 'leads', ['phone'])
    op.create_index('ix_leads_utm_source', 'leads', ['utm_source'])

def downgrade():
    op.drop_table('leads')
