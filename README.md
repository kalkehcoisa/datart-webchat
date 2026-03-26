# WebChat

A classic web-based online chat application built with FastAPI, Vue 3, PostgreSQL, Redis, and Celery. Fully containerised — runs with a single command.

## Quick Start

```bash
git clone <your-repo-url>
cd dataart-webchat
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

To run the test suite:

```bash
cd backend
pip install -r requirements.txt -r requirements-test.txt
pytest tests/ -v
```

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [API Reference](#api-reference)
- [WebSocket Protocol](#websocket-protocol)
- [Configuration](#configuration)
- [Database Migrations](#database-migrations)
- [Performance & Scalability](#performance--scalability)
- [Caching Strategy](#caching-strategy)
- [Message Queue](#message-queue)
- [Testing](#testing)
- [Spec Compliance](#spec-compliance)

---

## Architecture

```
Browser
  │
  ▼
Nginx (port 80)
  ├── /api/*       → FastAPI (uvicorn, 4 workers)
  ├── /ws          → FastAPI WebSocket
  ├── /uploads/*   → Static file serving
  └── /*           → Vue 3 (Vite dev server)

FastAPI workers
  ├── PostgreSQL   (async via asyncpg + SQLAlchemy)
  ├── Redis        (pub/sub fan-out + cache + rate limiting + presence)
  └── Celery       (message broadcast, presence, file processing)

Celery worker
  ├── Queue: messages      (room/chat broadcast fan-out)
  ├── Queue: presence      (online/afk/offline propagation)
  ├── Queue: files         (image thumbnail generation)
  └── Queue: notifications (friend requests, invites)
```

**Key design decisions:**

- **Redis pub/sub for WebSocket fan-out** — each uvicorn worker subscribes to Redis channels (`room:<id>`, `chat:<id>`, `user:<id>`). Messages published by any worker are delivered to WebSocket clients connected to any other worker. This makes horizontal scaling of the backend straightforward.
- **Celery for async broadcast** — HTTP endpoints persist to the database and enqueue a Celery task, returning immediately. The actual fan-out happens asynchronously. Tasks have `acks_late=True` so no message is lost if a worker crashes mid-delivery.
- **Presence in Redis** — presence state is written to a Redis key with a 90s TTL. The database is only updated when the status *changes* (online → afk, afk → offline, etc.), avoiding write amplification from repeated AFK heartbeats.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI 0.115 |
| ASGI server | Uvicorn + uvloop (4 workers) |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Cache / Pub-sub | Redis 7 |
| Message queue | Celery 5 + Kombu |
| Auth | JWT (access + refresh tokens via python-jose) |
| Password hashing | argon2 via passlib |
| File processing | Pillow (thumbnail generation) |
| Frontend | Vue 3 + Vite + Pinia |
| HTTP client (FE) | Axios (with automatic token refresh interceptor) |
| Reverse proxy | Nginx |
| Containerisation | Docker Compose |

---

## Project Structure

```
dataart-webchat/
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       ├── 0002_performance_indexes.py
│   │       ├── 0003_fix_author_nullable.py
│   │       └── 0004_personal_chat_fks_set_null.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_rooms.py
│   │   ├── test_messages.py
│   │   ├── test_friends.py
│   │   ├── test_security.py
│   │   └── test_edge_cases.py
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py        # Pydantic settings
│       │   ├── security.py      # JWT + argon2 helpers
│       │   └── cache.py         # Redis cache layer
│       ├── db/
│       │   ├── session.py       # SQLAlchemy async engine
│       │   └── redis.py         # Redis client singleton
│       ├── models/
│       │   └── models.py        # All SQLAlchemy models
│       ├── schemas/
│       │   └── schemas.py       # All Pydantic schemas
│       ├── api/v1/
│       │   ├── deps.py          # get_current_user dependency
│       │   └── endpoints/
│       │       ├── auth.py
│       │       ├── rooms.py
│       │       ├── messages.py
│       │       ├── friends.py
│       │       ├── files.py
│       │       └── users.py
│       ├── websocket/
│       │   ├── manager.py       # ConnectionManager with Redis pub/sub
│       │   └── handler.py       # WebSocket endpoint logic
│       └── worker/
│           ├── celery_app.py    # Celery configuration + queues
│           └── tasks.py         # broadcast_message, broadcast_presence, notify_user, process_attachment
└── frontend/
    ├── Dockerfile
    ├── vite.config.js
    └── src/
        ├── api/client.js        # Axios instance with refresh interceptor
        ├── stores/
        │   ├── auth.js          # Pinia: user session
        │   ├── socket.js        # Pinia: WebSocket + AFK tracking
        │   ├── chat.js          # Pinia: rooms, messages, unread counts
        │   └── friends.js       # Pinia: contacts, requests, presence
        ├── views/
        │   ├── LoginView.vue
        │   ├── RegisterView.vue
        │   ├── ChatLayout.vue   # Main shell, socket bootstrap
        │   ├── RoomsView.vue    # Public room catalog
        │   ├── RoomView.vue     # Room chat + member panel
        │   ├── PersonalChatView.vue
        │   └── SettingsView.vue
        └── components/
            ├── chat/
            │   ├── MessageList.vue   # Infinite scroll, reply, edit, delete
            │   ├── MessageInput.vue  # Multiline, file attach, reply bar
            │   └── SidebarPanel.vue # Accordion: rooms, DMs, friends
            ├── rooms/
            │   ├── MemberList.vue
            │   ├── CreateRoomModal.vue
            │   └── RoomAdminModal.vue  # Ban list, invite, settings, delete
            ├── contacts/
            │   ├── AddFriendModal.vue
            │   └── PendingRequestsModal.vue
            └── common/
                └── NotificationToast.vue  # Toasts with Accept button for invites
```

---

## Features

### Authentication & Sessions (spec §2.1, §2.2)

- Self-registration with unique email + username. Username is immutable after registration.
- Login with email + password. Persistent login via refresh tokens stored in `localStorage`.
- Token rotation on refresh — each refresh invalidates the old refresh token and issues a new pair.
- Sign out invalidates only the current browser session; other devices remain logged in.
- Active session list: view browser/IP of each session, revoke any session individually.
- Password change (requires current password) and password reset (requires current password; no unauthenticated reset endpoint).
- Account deletion: removes the account and all owned rooms with their messages and files. Messages in other users' rooms are preserved with author shown as `[deleted]`.

### Presence (spec §2.2)

- Three states: **online**, **afk**, **offline**.
- AFK triggered by 60 seconds of inactivity (no mouse/keyboard/scroll/touch events) across all tabs.
- Multi-tab aware: if any tab is active, the user is online. AFK is only set when all tabs have been idle.
- Offline only when all tabs are closed or the WebSocket disconnects with no remaining connections.
- Presence changes propagate to friends via Redis pub/sub with sub-2-second latency.
- Presence state written to Redis with 90s TTL; database updated only on state change to avoid write amplification.

### Contacts / Friends (spec §2.3)

- Send friend request by username (with optional message).
- Accept or reject incoming requests.
- Remove friends.
- User-to-user ban: terminates friendship, blocks all future messaging. Existing conversation history remains visible but read-only (frozen). The frontend hides the message input and shows a "Conversation blocked" label.
- Ban is bidirectional: either party blocking prevents messaging from both sides.
- Unban allows friendship requests again.

### Chat Rooms (spec §2.4)

- Any user can create a public or private room.
- Public rooms appear in the catalog with member count and description. Catalog supports text search (case-insensitive).
- Private rooms are invisible in the catalog; join only by invitation.
- Room owner cannot leave — must delete the room instead.
- Roles: **owner** (permanent admin, cannot be demoted) → **admin** → **member**.
- Admin actions: delete messages, ban/unban members, manage admins, view ban list with who banned whom.
- Owner actions: all admin actions + remove any admin + delete room.
- Room ban is permanent until explicitly removed: banned users cannot rejoin, lose access to messages and files.
- Room invitations: any member can invite others to a private room. Invitee receives a toast notification with an Accept button.

### Messaging (spec §2.5)

- Room messages and personal messages share the same feature set.
- Plain text, multiline text, emoji.
- Reply to any message — quoted preview shown inline.
- Edit own messages — gray "edited" indicator shown.
- Delete own messages (or any message for room admins) — soft delete, shown as `[message deleted]`.
- Infinite scroll: older messages load as the user scrolls up, with scroll position preserved.
- Pagination uses a `(created_at, id)` composite cursor to avoid skipping messages at identical timestamps.
- Messages to offline users are persisted and appear when they reconnect.

### Attachments (spec §2.6)

- Upload via button or paste from clipboard.
- Images (JPEG, PNG, GIF, WebP) and arbitrary file types.
- Image size limit: 3 MB. General file size limit: 20 MB.
- Original filename preserved. Optional comment per attachment.
- Images rendered inline in the chat; files shown as download links.
- Thumbnails generated asynchronously by a Celery worker (400×400, quality 80).
- Access control enforced on every download: only current room members or personal chat participants can download. Losing room access immediately revokes file access.

### Notifications (spec §2.7)

- Unread badge on room and DM entries in the sidebar — cleared when the chat is opened.
- Toast notifications for: friend requests, accepted friend requests, room invitations (with Accept button).
- Typing indicator broadcast via WebSocket (not persisted).

---

## API Reference

All endpoints are prefixed with `/api/v1`. Authentication uses `Authorization: Bearer <access_token>`.

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Register new user |
| POST | `/auth/login` | — | Login, returns token pair |
| POST | `/auth/refresh` | — | Rotate refresh token |
| POST | `/auth/logout` | — | Invalidate current session |
| GET | `/auth/me` | ✓ | Current user profile |
| POST | `/auth/password/change` | ✓ | Change password (requires current) |
| POST | `/auth/password/reset` | ✓ | Reset password (requires current) |
| GET | `/auth/sessions` | ✓ | List active sessions |
| DELETE | `/auth/sessions/{id}` | ✓ | Revoke a session |
| DELETE | `/auth/account` | ✓ | Delete account |

### Rooms

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/rooms` | ✓ | Create room |
| GET | `/rooms` | ✓ | List public rooms (supports `?search=`) |
| GET | `/rooms/my` | ✓ | Rooms the current user belongs to |
| GET | `/rooms/invitations/pending` | ✓ | Pending room invitations |
| GET | `/rooms/{id}` | ✓ | Get room details |
| PATCH | `/rooms/{id}` | ✓ | Update room (owner only) |
| DELETE | `/rooms/{id}` | ✓ | Delete room (owner only) |
| POST | `/rooms/{id}/join` | ✓ | Join public room |
| POST | `/rooms/{id}/leave` | ✓ | Leave room |
| POST | `/rooms/{id}/invite` | ✓ | Invite user to private room |
| POST | `/rooms/{id}/accept-invite` | ✓ | Accept a room invitation |
| GET | `/rooms/{id}/members` | ✓ | List members with presence |
| POST | `/rooms/{id}/members/{uid}/ban` | ✓ | Ban member (admin) |
| DELETE | `/rooms/{id}/members/{uid}/ban` | ✓ | Unban member (admin) |
| GET | `/rooms/{id}/bans` | ✓ | List bans (admin only) |
| POST | `/rooms/{id}/members/{uid}/admin` | ✓ | Grant admin (owner) |
| DELETE | `/rooms/{id}/members/{uid}/admin` | ✓ | Revoke admin (admin/owner) |
| POST | `/rooms/{id}/members/{uid}/remove` | ✓ | Remove + ban member (admin) |

### Messages

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/rooms/{id}/messages` | ✓ | Paginated room history (`?before=<uuid>&limit=50`) |
| POST | `/rooms/{id}/messages` | ✓ | Send room message |
| GET | `/chats` | ✓ | List personal chats |
| POST | `/chats/{username}` | ✓ | Open or get personal chat |
| GET | `/chats/{id}/messages` | ✓ | Paginated chat history |
| POST | `/chats/{id}/messages` | ✓ | Send personal message |
| PATCH | `/messages/{id}` | ✓ | Edit message (author only) |
| DELETE | `/messages/{id}` | ✓ | Delete message (author or room admin) |
| POST | `/upload` | ✓ | Upload attachment (multipart, linked to message) |

### Friends

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/friends/requests` | ✓ | Send friend request |
| GET | `/friends/requests/pending` | ✓ | Incoming pending requests |
| POST | `/friends/requests/{id}/accept` | ✓ | Accept request |
| POST | `/friends/requests/{id}/reject` | ✓ | Reject request |
| GET | `/friends` | ✓ | Friend list |
| DELETE | `/friends/{username}` | ✓ | Remove friend |
| POST | `/friends/ban/{username}` | ✓ | Ban user |
| DELETE | `/friends/ban/{username}` | ✓ | Unban user |

### Files & Users

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/files/{id}` | ✓ | Download attachment (access-controlled) |
| GET | `/users/search?q=` | ✓ | Search users by username (min 2 chars) |
| GET | `/users/{id}` | ✓ | Get public user profile |

---

## WebSocket Protocol

Connect to `ws://host/ws?token=<access_token>`.

### Client → Server events

```json
{ "type": "join_room",  "room_id": "<uuid>" }
{ "type": "leave_room", "room_id": "<uuid>" }
{ "type": "join_chat",  "chat_id": "<uuid>" }
{ "type": "typing",     "room_id": "<uuid>" }
{ "type": "typing",     "chat_id": "<uuid>" }
{ "type": "afk" }
{ "type": "active" }
{ "type": "pong" }
```

### Server → Client events

```json
{ "type": "ping" }
{ "type": "message",        ...message_object }
{ "type": "message_edited", ...message_object }
{ "type": "message_deleted","message_id": "<uuid>" }
{ "type": "member_joined",  "user_id": "<uuid>", "username": "..." }
{ "type": "member_left",    "user_id": "<uuid>" }
{ "type": "member_banned",  "user_id": "<uuid>" }
{ "type": "room_deleted",   "room_id": "<uuid>" }
{ "type": "presence",       "user_id": "<uuid>", "status": "online|afk|offline" }
{ "type": "typing",         "user_id": "<uuid>", "username": "..." }
{ "type": "friend_request", "from": "username",  "request_id": "<uuid>" }
{ "type": "friend_accepted","by": "username" }
{ "type": "room_invitation","room_id": "<uuid>", "room_name": "...", "inviter": "username" }
```

The server sends a `ping` every 30 seconds. The client must respond with `pong`. Connections that fail to respond are cleaned up on the next send attempt.

---

## Configuration

All configuration is via environment variables, set in `docker-compose.yml`:

| Variable | Default (Docker) | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://chat:chatpass@db:5432/chatdb` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `SECRET_KEY` | `supersecretkey_change_in_production` | **Change this in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
| `UPLOAD_DIR` | `/app/uploads` | File storage directory |
| `MAX_FILE_SIZE_MB` | `20` | Max file upload size |
| `MAX_IMAGE_SIZE_MB` | `3` | Max image upload size |

---

## Database Migrations

Migrations run automatically on startup (`alembic upgrade head` in the backend entrypoint).

| Migration | Description |
|---|---|
| `0001_initial` | All tables: users, sessions, rooms, members, bans, invitations, friendships, user bans, personal chats, messages, attachments, message reads |
| `0002_performance_indexes` | Indexes on all foreign keys and frequent filter columns |
| `0003_fix_author_nullable` | `messages.author_id` and `attachments.uploader_id` → `SET NULL` on user delete (spec §2.1.5) |
| `0004_personal_chat_fks_set_null` | `personal_chats.user_a_id` / `user_b_id` → `SET NULL` so frozen chats survive account deletion (spec §2.3.5) |

---

## Performance & Scalability

The system is designed to support 300 simultaneous users comfortably:

**Database**
- PostgreSQL tuned: `shared_buffers=256MB`, `work_mem=4MB`, `checkpoint_completion_target=0.9`
- SQLAlchemy async connection pool: `pool_size=20`, `max_overflow=10`, `pool_recycle=3600`
- Composite indexes on `(room_id, created_at)` and `(personal_chat_id, created_at)` for O(log n) message pagination even at 10k+ messages
- Indexes on all FK columns used in frequent queries

**Redis**
- `allkeys-lru` eviction policy — OOM-safe
- `maxmemory 256mb`
- Dual role: pub/sub channel bus + application cache + rate limiting + presence TTL

**Nginx**
- `gzip` for JS/CSS/JSON (level 5)
- `tcp_nopush`, `tcp_nodelay`
- `keepalive 32` to backend upstream
- Static file cache headers: uploads get `Cache-Control: public, max-age=31536000, immutable`

**Backend**
- `uvloop` event loop (~20% faster than default asyncio)
- 4 uvicorn workers — horizontal within a single container
- All I/O is async (asyncpg, aiofiles, redis.asyncio)
- Rate limiting on `/api/v1/auth/*`: 20 requests/minute/IP via Redis pipeline (atomic INCR + EXPIRE)

---

## Caching Strategy

Cache is implemented as a thin Redis wrapper in `app/core/cache.py`. All cache failures are silent (log warning, return `None`), so the system degrades gracefully if Redis is unavailable.

| What | TTL | Invalidated on |
|---|---|---|
| Public room catalog | 30s | Room create / update / delete |
| Room info (`GET /rooms/{id}`) | 5min | Room update / delete / join / leave / ban |
| Room members list | 60s | Join / leave / ban / admin change / invite accept |
| Friend list | 2min | Accept / remove / ban |
| User public profile | 5min | Account delete |

Cache keys are prefixed with `cache:` to avoid collisions with the pub/sub channel namespace (`room:*`, `chat:*`, `user:*`).

---

## Message Queue

Celery uses Redis as both broker and result backend. Four named queues with different priorities:

| Queue | Tasks | Purpose |
|---|---|---|
| `messages` | `broadcast_message` | Fan-out chat messages via Redis pub/sub |
| `presence` | `broadcast_presence` | Propagate online/afk/offline to friends |
| `notifications` | `notify_user` | Friend requests, accepted requests, room invitations |
| `files` | `process_attachment` | Generate image thumbnails asynchronously |

Task configuration:
- `task_acks_late=True` — task is only acknowledged after successful completion
- `task_reject_on_worker_lost=True` — re-queued automatically if worker crashes
- `worker_prefetch_multiplier=1` — prevents workers from starving each other
- `max_retries=3` with exponential backoff for all tasks

---

## Testing

81 tests across 6 files, all passing. Tests use SQLite in-memory (via `aiosqlite`) — no external services required.

```
tests/
├── conftest.py          # Fixtures: in-memory DB, mocked Redis + Celery, test client
├── test_auth.py         # Registration, login, token lifecycle, password change, account deletion
├── test_rooms.py        # CRUD, join/leave, ban, admin roles, invitations, route ordering
├── test_messages.py     # Send, edit, delete, reply, pagination, personal chat, frozen chat
├── test_friends.py      # Request flow, accept/reject, remove, ban, mutual block
├── test_security.py     # Token validation, authorization, account deletion cascade, search
└── test_edge_cases.py   # Invite flow, file access control, size limits, search, admin edge cases
```

Run:

```bash
cd backend
pip install -r requirements.txt -r requirements-test.txt
pytest tests/ -v
```

---

## Spec Compliance

### Implemented

| Spec | Feature | Notes |
|---|---|---|
| §2.1.1–2.1.2 | Registration with unique email + username | Username immutable |
| §2.1.3 | Login, logout, persistent login | Refresh token rotation |
| §2.1.4 | Password change + reset | Both require current password (no unauthenticated reset) |
| §2.1.5 | Account deletion | Only owned rooms deleted; messages in other rooms preserved (`[deleted]`) |
| §2.2.1–2.2.3 | Presence: online / afk / offline | Multi-tab aware via WS connection count |
| §2.2.4 | Active session list + selective revocation | Browser/IP shown per session |
| §2.3.1–2.3.4 | Friend list, requests, confirmation, removal | Bidirectional |
| §2.3.5 | User-to-user ban | Chat frozen (visible, read-only); friendship terminated |
| §2.3.6 | Personal messaging requires friendship + no ban | Enforced on send |
| §2.4.1–2.4.2 | Room creation with all properties | Name uniqueness enforced |
| §2.4.3 | Public room catalog with search + member count | Case-insensitive search |
| §2.4.4 | Private rooms invisible in catalog | Invite-only join |
| §2.4.5 | Join/leave rules; owner cannot leave | Owner must delete |
| §2.4.6 | Room deletion cascades to messages + files | On-disk files removed when room deleted |
| §2.4.7 | Owner + admin roles with correct permissions | Owner admin status irrevocable |
| §2.4.8 | Room ban blocks rejoin + file access | Access enforced on every file download |
| §2.4.9 | Room invitations | Toast with Accept button; pending invitations API |
| §2.5.1 | Personal and room chats share same feature set | Unified message model |
| §2.5.2 | Text, multiline, emoji, attachments, replies | 3KB UTF-8 limit enforced |
| §2.5.3 | Reply with quoted preview | Shown inline |
| §2.5.4 | Message editing with "edited" indicator | Deleted messages cannot be edited |
| §2.5.5 | Message deletion by author or room admin | Soft delete |
| §2.5.6 | Chronological order, infinite scroll, offline delivery | Composite cursor pagination |
| §2.6.1–2.6.3 | Images + arbitrary files, filename preserved, optional comment | |
| §2.6.2 | Upload via button + paste | Paste handled in `MessageInput.vue` |
| §2.6.4 | File access enforced per download | Room membership / chat participation checked |
| §2.6.5 | Files persist after uploader loses access | Only the ability to download is revoked |
| §2.7.1 | Unread badges on rooms and DMs | Cleared on open |
| §2.7.2 | Presence updates < 2s | Redis pub/sub, no polling |
| §3.1 | 300 simultaneous users | 4 uvicorn workers + Celery + Redis fan-out |
| §3.2 | Message delivery < 3s | Celery async fan-out, typically < 500ms |
| §3.3 | Persistent history, infinite scroll | Composite-cursor pagination, indexed |
| §3.4 | Local file storage, 20MB / 3MB limits | Stored in Docker volume |
| §3.5 | No forced logout, persistent login, multi-tab | Refresh tokens, WS connection count |
| §4.1 | Top bar + message area + input + sidebar | Accordion rooms/DMs/friends |
| §4.2 | Auto-scroll, no forced scroll, infinite scroll | `atBottom` flag in `MessageList` |
| §4.3 | Multiline, emoji, attachments, reply | All in `MessageInput.vue` |
| §4.4 | Unread indicators near room/contact names | Badge counts in sidebar |
| §4.5 | Admin actions via modal dialogs | `RoomAdminModal.vue`, `MemberList.vue` |

### Notes

- **Email verification (§2.1.2):** The spec explicitly states email verification is not required. Registration is immediate.
- **Password reset (§2.1.4):** The spec mentions "password reset" without specifying a mechanism. Since no email delivery is configured, the reset endpoint requires the current password (identical to change password). An email-based flow can be added by integrating an SMTP service.
- **Emoji (§2.5.2):** The spec requires emoji support in messages. The text input accepts any UTF-8 including emoji. A dedicated emoji picker was not implemented — users can paste emoji from their OS or use keyboard shortcuts.
