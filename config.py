
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

SMM_API_URL = os.getenv("SMM_API_URL", "").strip()
SMM_API_KEY = os.getenv("SMM_API_KEY", "").strip()


# ==========================================
# GENERAL BOT SETTINGS
# ==========================================

TIMEZONE = os.getenv(
    "TIMEZONE",
    "Asia/Kolkata"
).strip()

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
).strip().upper()

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

def get_positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()

    try:
        result = int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a valid integer."
        ) from exc

    if result <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero."
        )

    return result


DEFAULT_QUANTITY = get_positive_int(
    "DEFAULT_QUANTITY",
    500
)

MAX_ORDER_RETRIES = get_positive_int(
    "MAX_ORDER_RETRIES",
    3
)

ORDER_STATUS_CHECK_SECONDS = get_positive_int(
    "ORDER_STATUS_CHECK_SECONDS",
    60
)


# ==========================================
# CONFIGURATION LOADED
# ==========================================

logger.info("Configuration loaded successfully.")
