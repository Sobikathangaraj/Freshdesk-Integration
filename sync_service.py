"""
Full bidirectional sync:
  Freshdesk → PostgreSQL  (pull all tickets + conversations)
  PostgreSQL → Freshdesk  (push local updates back)
"""

import asyncio
from database import upsert_ticket, upsert_conversation, get_ticket as db_get_ticket
import freshdesk_client as fd


async def sync_all_tickets(pool, max_pages: int = 10):
    """Pull all tickets from Freshdesk and store in DB."""
    print("🔄 Starting full ticket sync from Freshdesk...")
    for page in range(1, max_pages + 1):
        tickets = await fd.list_tickets(page=page, per_page=100)
        if not tickets:
            break
        for ticket in tickets:
            await upsert_ticket(pool, ticket)
        print(f"  ✅ Synced page {page} ({len(tickets)} tickets)")
        if len(tickets) < 100:
            break
        await asyncio.sleep(0.3)   # respect rate limits
    print("✅ Full ticket sync complete.")


async def sync_ticket_with_conversations(pool, ticket_id: int):
    """Sync a single ticket + all its conversations."""
    ticket = await fd.get_ticket(ticket_id)
    await upsert_ticket(pool, ticket)

    conversations = await fd.get_conversations(ticket_id)
    for conv in conversations:
        await upsert_conversation(pool, conv, ticket_id)

    print(f"✅ Synced ticket #{ticket_id} with {len(conversations)} conversations.")
    return ticket


async def push_ticket_update(pool, freshdesk_id: int, updates: dict):
    """
    Push a local update to Freshdesk, then re-sync the ticket.
    updates: dict with fields like {'status': 4, 'priority': 2}
    """
    updated = await fd.update_ticket(freshdesk_id, updates)
    await upsert_ticket(pool, updated)
    return updated


async def push_reply_and_sync(pool, ticket_id: int, body: str, from_email: str = None):
    """Send a reply to Freshdesk and sync conversations back."""
    reply = await fd.send_reply(ticket_id, body, from_email)
    # Sync conversations after reply
    conversations = await fd.get_conversations(ticket_id)
    for conv in conversations:
        await upsert_conversation(pool, conv, ticket_id)
    return reply