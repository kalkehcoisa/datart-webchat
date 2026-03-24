"""fix author nullable and uploader nullable for account deletion

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make messages.author_id nullable with SET NULL on user delete
    op.alter_column('messages', 'author_id', nullable=True)
    op.drop_constraint('messages_author_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key(
        'messages_author_id_fkey', 'messages', 'users',
        ['author_id'], ['id'], ondelete='SET NULL'
    )

    # Make attachments.uploader_id nullable with SET NULL on user delete
    op.alter_column('attachments', 'uploader_id', nullable=True)
    op.drop_constraint('attachments_uploader_id_fkey', 'attachments', type_='foreignkey')
    op.create_foreign_key(
        'attachments_uploader_id_fkey', 'attachments', 'users',
        ['uploader_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.alter_column('messages', 'author_id', nullable=False)
    op.drop_constraint('messages_author_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key(
        'messages_author_id_fkey', 'messages', 'users',
        ['author_id'], ['id'], ondelete='CASCADE'
    )

    op.alter_column('attachments', 'uploader_id', nullable=False)
    op.drop_constraint('attachments_uploader_id_fkey', 'attachments', type_='foreignkey')
    op.create_foreign_key(
        'attachments_uploader_id_fkey', 'attachments', 'users',
        ['uploader_id'], ['id'], ondelete='CASCADE'
    )
