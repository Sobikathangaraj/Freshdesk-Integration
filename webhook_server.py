"""
FastAPI app exposing:
  POST /webhook/freshdesk   → receives Freshdesk events
  POST /tickets             → create a ticket
  PUT  /tickets/{id}        → update a ticket
  POST /tickets/{id}/reply  → send a reply
  GET  /tickets             → list tickets from DB
  GET  /tickets/{id}        → get ticket + conversations from DB
  POST /sync                → trigger full sync
"""

import json
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from config import WEBHOOK_SECRET
from database import (
    get_db_pool, init_db,
    upsert_ticket, upsert_conversation,
    get_ticket as db_get_ticket,
    list_tickets as db_list_tickets,
    get_conversations as db_get_conversations,
    log_webhook_event,
)
from models import CreateTicketRequest, UpdateTicketRequest, ReplyRequest
import freshdesk_client as fd
from sync_service import (
    sync_all_tickets,
    sync_ticket_with_conversations,
    push_ticket_update,
    push_reply_and_sync,
)


# ── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await get_db_pool()
    await init_db(app.state.db_pool)
    yield
    await app.state.db_pool.close()


app = FastAPI(title="Freshdesk Integration", lifespan=lifespan)


def get_pool(request: Request):
    return request.app.state.db_pool


# ── Webhook endpoint ─────────────────────────────────────────────────────────

@app.post("/webhook/freshdesk")
async def freshdesk_webhook(request: Request, pool=Depends(get_pool)):
    """
    Freshdesk sends events here.
    Configure in Freshdesk: Admin → Automation → Webhooks → URL = https://yourdomain.com/webhook/freshdesk
    """
    # Optional: verify shared secret header
    secret = request.headers.get("X-Freshdesk-Secret")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event_type", "unknown")
    await log_webhook_event(pool, event_type, payload)

    # Handle different event types Freshdesk sends
    ticket_data = payload.get("ticket") or payload.get("freshdesk_webhook", {}).get("ticket")

    if ticket_data:
        ticket_id = ticket_data.get("id")
        if ticket_id:
            # Pull fresh data from Freshdesk API and sync
            asyncio.create_task(sync_ticket_with_conversations(pool, ticket_id))

    return {"status": "received", "event_type": event_type}


# ── Ticket endpoints ─────────────────────────────────────────────────────────

@app.post("/tickets")
async def create_ticket(body: CreateTicketRequest, pool=Depends(get_pool)):
    payload = {
        "subject": body.subject,
        "description": body.description,
        "email": body.email,
        "priority": body.priority,
        "status": body.status,
        "tags": body.tags,
    }
    if body.name:
        payload["name"] = body.name

    ticket = await fd.create_ticket(payload)
    await upsert_ticket(pool, ticket)
    return {"freshdesk_id": ticket["id"], "ticket": ticket}


@app.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: int, body: UpdateTicketRequest, pool=Depends(get_pool)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await push_ticket_update(pool, ticket_id, updates)
    return {"freshdesk_id": ticket_id, "ticket": updated}


@app.post("/tickets/{ticket_id}/reply")
async def reply_to_ticket(ticket_id: int, body: ReplyRequest, pool=Depends(get_pool)):
    reply = await push_reply_and_sync(pool, ticket_id, body.body, body.from_email)
    return {"status": "sent", "conversation_id": reply.get("id")}


@app.get("/tickets")
async def list_tickets(limit: int = 50, offset: int = 0, pool=Depends(get_pool)):
    rows = await db_list_tickets(pool, limit, offset)
    return [dict(r) for r in rows]


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, pool=Depends(get_pool)):
    ticket = await db_get_ticket(pool, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found in DB")
    conversations = await db_get_conversations(pool, ticket_id)
    return {
        "ticket": dict(ticket),
        "conversations": [dict(c) for c in conversations],
    }


# ── Sync endpoint ────────────────────────────────────────────────────────────

@app.post("/sync")
async def trigger_sync(pool=Depends(get_pool)):
    """Manually trigger a full pull from Freshdesk → DB."""
    asyncio.create_task(sync_all_tickets(pool))
    return {"status": "sync started in background"}


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("webhook_server:app", host="127.0.0.1", port=8080, reload=True)