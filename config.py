import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

SMM_API_KEY = os.getenv("SMM_API_KEY")
SMM_API_URL = os.getenv("SMM_API_URL")

DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")

if not OWNER_ID:
    raise ValueError("OWNER_ID is missing")

if not SMM_API_KEY:
    raise ValueError("SMM_API_KEY is missing")

if not SMM_API_URL:
    raise ValueError("SMM_API_URL is missing")
