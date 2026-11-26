
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ==========================================
# TELEGRAM BOT CONFIGURATION
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN missing! Add BOT_TOKEN in Railway Variables."
    )


# ==========================================
# OWNER CONFIGURATION
# ==========================================

_owner_id = os.getenv("OWNER_ID", "").strip()

if not _owner_id:
    raise RuntimeError(
        "OWNER_ID missing! Add your Telegram numeric ID in Railway Variables."
    )

try:
    OWNER_ID = int(_owner_id)
except ValueError as exc:
    raise RuntimeError(
        "OWNER_ID must contain a valid numeric Telegram user ID."
    ) from exc


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL missing! Add PostgreSQL DATABASE_URL in Railway Variables."
    )


# ==========================================
# OPTIONAL LEGACY SMM API CONFIGURATION
# ==========================================

# New multi-panel system will store each panel's
# API URL and API key separately in PostgreSQL.

SMM_API_URL = os.getenv("SMM_API_URL", "").strip()
SMM_API_KEY = os.getenv("SMM_API_KEY", "").strip()


# ==========================================
# GENERAL BOT SETTINGS
# ==========================================

TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata").strip()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

VALID_LOG_LEVELS = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL"
}

if LOG_LEVEL not in VALID_LOG_LEVELS:
    LOG_LEVEL = "INFO"


# ==========================================
# AUTOMATION SETTINGS
# ==========================================

DEFAULT_QUANTITY = 500

# A new post can trigger its own order.
# Pending orders do not block orders for new posts.

MAX_ORDER_RETRIES = 3

ORDER_STATUS_CHECK_SECONDS = 60


logger.info("Configuration loaded successfully.")
