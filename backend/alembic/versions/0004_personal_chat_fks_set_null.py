"""personal chat fks set null

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('personal_chats', 'user_a_id', nullable=True)
    op.drop_constraint('personal_chats_user_a_id_fkey', 'personal_chats', type_='foreignkey')
    op.create_foreign_key(
        'personal_chats_user_a_id_fkey', 'personal_chats', 'users',
        ['user_a_id'], ['id'], ondelete='SET NULL'
    )

    op.alter_column('personal_chats', 'user_b_id', nullable=True)
    op.drop_constraint('personal_chats_user_b_id_fkey', 'personal_chats', type_='foreignkey')
    op.create_foreign_key(
        'personal_chats_user_b_id_fkey', 'personal_chats', 'users',
        ['user_b_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.alter_column('personal_chats', 'user_a_id', nullable=False)
    op.drop_constraint('personal_chats_user_a_id_fkey', 'personal_chats', type_='foreignkey')
    op.create_foreign_key(
        'personal_chats_user_a_id_fkey', 'personal_chats', 'users',
        ['user_a_id'], ['id'], ondelete='CASCADE'
    )

    op.alter_column('personal_chats', 'user_b_id', nullable=False)
    op.drop_constraint('personal_chats_user_b_id_fkey', 'personal_chats', type_='foreignkey')
    op.create_foreign_key(
        'personal_chats_user_b_id_fkey', 'personal_chats', 'users',
        ['user_b_id'], ['id'], ondelete='CASCADE'
    )
