import asyncpg
from config import DATABASE_URL


async def get_db_pool():
    return await asyncpg.create_pool(DATABASE_URL)


async def init_db(pool):
    """Create tables if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id                  SERIAL PRIMARY KEY,
                freshdesk_id        BIGINT UNIQUE NOT NULL,
                subject             TEXT,
                description         TEXT,
                status              INT,
                priority            INT,
                requester_email     TEXT,
                requester_name      TEXT,
                tags                TEXT[],
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW(),
                synced_at           TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id                  SERIAL PRIMARY KEY,
                freshdesk_id        BIGINT UNIQUE NOT NULL,
                ticket_freshdesk_id BIGINT NOT NULL REFERENCES tickets(freshdesk_id) ON DELETE CASCADE,
                body                TEXT,
                body_text           TEXT,
                from_email          TEXT,
                user_id             BIGINT,
                incoming            BOOLEAN DEFAULT TRUE,
                private             BOOLEAN DEFAULT FALSE,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS webhook_events (
                id                  SERIAL PRIMARY KEY,
                event_type          TEXT,
                payload             JSONB,
                processed           BOOLEAN DEFAULT FALSE,
                received_at         TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_tickets_freshdesk_id ON tickets(freshdesk_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_ticket_id ON conversations(ticket_freshdesk_id);
        """)
    print("✅ Database tables initialized.")


# ── Ticket DB helpers ────────────────────────────────────────────────────────

async def upsert_ticket(pool, ticket: dict):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO tickets (
                freshdesk_id, subject, description, status, priority,
                requester_email, requester_name, tags, created_at, updated_at, synced_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
            ON CONFLICT (freshdesk_id) DO UPDATE SET
                subject         = EXCLUDED.subject,
                description     = EXCLUDED.description,
                status          = EXCLUDED.status,
                priority        = EXCLUDED.priority,
                requester_email = EXCLUDED.requester_email,
                requester_name  = EXCLUDED.requester_name,
                tags            = EXCLUDED.tags,
                updated_at      = EXCLUDED.updated_at,
                synced_at       = NOW()
        """,
        ticket["id"],
        ticket.get("subject"),
        ticket.get("description_text") or ticket.get("description"),
        ticket.get("status"),
        ticket.get("priority"),
        ticket.get("requester", {}).get("email"),
        ticket.get("requester", {}).get("name"),
        ticket.get("tags", []),
        ticket.get("created_at"),
        ticket.get("updated_at"),
        )


async def get_ticket(pool, freshdesk_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM tickets WHERE freshdesk_id = $1", freshdesk_id
        )


async def list_tickets(pool, limit=50, offset=0):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM tickets ORDER BY updated_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )


# ── Conversation DB helpers ──────────────────────────────────────────────────

async def upsert_conversation(pool, conv: dict, ticket_freshdesk_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO conversations (
                freshdesk_id, ticket_freshdesk_id, body, body_text,
                from_email, user_id, incoming, private, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (freshdesk_id) DO UPDATE SET
                body       = EXCLUDED.body,
                body_text  = EXCLUDED.body_text,
                updated_at = EXCLUDED.updated_at
        """,
        conv["id"],
        ticket_freshdesk_id,
        conv.get("body"),
        conv.get("body_text"),
        conv.get("from_email"),
        conv.get("user_id"),
        conv.get("incoming", True),
        conv.get("private", False),
        conv.get("created_at"),
        conv.get("updated_at"),
        )


async def get_conversations(pool, ticket_freshdesk_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM conversations WHERE ticket_freshdesk_id = $1 ORDER BY created_at ASC",
            ticket_freshdesk_id
        )


# ── Webhook event log ────────────────────────────────────────────────────────

async def log_webhook_event(pool, event_type: str, payload: dict):
    import json
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO webhook_events (event_type, payload) VALUES ($1, $2)",
            event_type, json.dumps(payload)
        )