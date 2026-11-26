
import os
from dotenv import load_dotenv

load_dotenv()


def get_required_env(name):
    value = os.getenv(name)

    if not value:
        raise ValueError(
            f"Required environment variable is missing: {name}"
        )

    return value.strip()


# Telegram Bot Configuration
BOT_TOKEN = get_required_env("BOT_TOKEN")

# Owner Configuration
OWNER_ID = int(get_required_env("OWNER_ID"))

# SMM Panel Configuration
SMM_API_KEY = get_required_env("SMM_API_KEY")
SMM_API_URL = get_required_env("SMM_API_URL")

# PostgreSQL Configuration
DATABASE_URL = get_required_env("DATABASE_URL")
