"""performance indexes

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_messages_author_id', 'messages', ['author_id'])
    op.create_index('ix_room_members_user_id', 'room_members', ['user_id'])
    op.create_index('ix_room_members_room_id', 'room_members', ['room_id'])
    op.create_index('ix_room_bans_room_id', 'room_bans', ['room_id'])
    op.create_index('ix_friendships_user_a_id', 'friendships', ['user_a_id'])
    op.create_index('ix_friendships_user_b_id', 'friendships', ['user_b_id'])
    op.create_index('ix_friend_requests_receiver_status', 'friend_requests', ['receiver_id', 'status'])
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_refresh_token', 'sessions', ['refresh_token'])
    op.create_index('ix_attachments_message_id', 'attachments', ['message_id'])
    op.create_index('ix_room_invitations_invitee_id', 'room_invitations', ['invitee_id'])


def downgrade() -> None:
    op.drop_index('ix_messages_author_id', 'messages')
    op.drop_index('ix_room_members_user_id', 'room_members')
    op.drop_index('ix_room_members_room_id', 'room_members')
    op.drop_index('ix_room_bans_room_id', 'room_bans')
    op.drop_index('ix_friendships_user_a_id', 'friendships')
    op.drop_index('ix_friendships_user_b_id', 'friendships')
    op.drop_index('ix_friend_requests_receiver_status', 'friend_requests')
    op.drop_index('ix_sessions_user_id', 'sessions')
    op.drop_index('ix_sessions_refresh_token', 'sessions')
    op.drop_index('ix_attachments_message_id', 'attachments')
    op.drop_index('ix_room_invitations_invitee_id', 'room_invitations')
