from alembic import op
import sqlalchemy as sa

# если у тебя есть auto-сгенерированные revision/dow_revision — оставь их как есть
# revision = '0001_leads'
# down_revision = None

def upgrade():
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        # базовые поля (как в app/models.py)
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=True),

        # новое — всё nullable, чтобы не ломать существующие данные
        sa.Column('form_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('page', sa.String(), nullable=True),

        sa.Column('utm_source', sa.String(), nullable=True),
        sa.Column('utm_medium', sa.String(), nullable=True),
        sa.Column('utm_campaign', sa.String(), nullable=True),
        sa.Column('utm_content', sa.String(), nullable=True),
        sa.Column('utm_term', sa.String(), nullable=True),

        sa.Column('raw', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                 server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('dedupe_hash', sa.String(), nullable=True)
    )

def downgrade():
    op.drop_table('leads')
