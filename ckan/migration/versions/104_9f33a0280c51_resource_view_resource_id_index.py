
"""resource_view resource_id index

Revision ID: 9f33a0280c51
Revises: 353aaf2701f0
Create Date: 2022-10-11 02:31:35.941858

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9f33a0280c51'
down_revision = '353aaf2701f0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'idx_view_resource_id', 'resource_view', ['resource_id']
    )


def downgrade():
    op.drop_index('idx_view_resource_id')
