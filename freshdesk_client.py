import httpx
import base64
from config import FRESHDESK_API_KEY, FRESHDESK_BASE_URL


def _auth_headers():
    """Freshdesk uses HTTP Basic Auth: API_KEY as username, 'X' as password."""
    token = base64.b64encode(f"{FRESHDESK_API_KEY}:X".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


# ── Tickets ──────────────────────────────────────────────────────────────────

async def create_ticket(data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FRESHDESK_BASE_URL}/tickets",
            json=data,
            headers=_auth_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def update_ticket(ticket_id: int, data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{FRESHDESK_BASE_URL}/tickets/{ticket_id}",
            json=data,
            headers=_auth_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_ticket(ticket_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FRESHDESK_BASE_URL}/tickets/{ticket_id}",
            headers=_auth_headers(),
            params={"include": "requester,conversations"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def list_tickets(page: int = 1, per_page: int = 30) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FRESHDESK_BASE_URL}/tickets",
            headers=_auth_headers(),
            params={"page": page, "per_page": per_page, "include": "requester"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# ── Replies / Conversations ──────────────────────────────────────────────────

async def send_reply(ticket_id: int, body: str, from_email: str = None) -> dict:
    payload = {"body": body}
    if from_email:
        payload["from_email"] = from_email

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FRESHDESK_BASE_URL}/tickets/{ticket_id}/reply",
            json=payload,
            headers=_auth_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_conversations(ticket_id: int) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FRESHDESK_BASE_URL}/tickets/{ticket_id}/conversations",
            headers=_auth_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()