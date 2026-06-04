import os
from dotenv import load_dotenv

load_dotenv()

FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")         
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")            
FRESHDESK_BASE_URL = f"https://{FRESHDESK_DOMAIN}/api/v2"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/freshdesk_db"
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-webhook-secret")