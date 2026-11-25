
import logging
import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(__name__)

pool = None


async def init_db():
    """Initialize PostgreSQL connection and create tables."""
    global pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is missing")

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60
    )

    async with pool.acquire() as conn:

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id BIGSERIAL PRIMARY KEY,
                channel_username TEXT UNIQUE NOT NULL,
                quantity BIGINT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quantity_events (
                id BIGSERIAL PRIMARY KEY,
                channel_username TEXT NOT NULL,
                event_type TEXT NOT NULL,
                quantity BIGINT,
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quantity_events_created
            ON quantity_events(created_at);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quantity_events_channel
            ON quantity_events(channel_username);
        """)

    logger.info("PostgreSQL database initialized successfully.")


async def close_db():
    """Close database connection pool."""
    global pool

    if pool:
        await pool.close()
        pool = None


def get_pool():
    if pool is None:
        raise RuntimeError("Database is not initialized")

    return pool


async def add_channel(username):
    username = username.strip().lstrip("@").lower()

    async with get_pool().acquire() as conn:

        result = await conn.fetchrow("""
            INSERT INTO channels (channel_username)
            VALUES ($1)
            ON CONFLICT (channel_username) DO NOTHING
            RETURNING *
        """, username)

        if result:
            await conn.execute("""
                INSERT INTO quantity_events
                (channel_username, event_type, details)
                VALUES ($1, 'ADD_CHANNEL', 'Channel added')
            """, username)

        return result


async def remove_channel(username):
    username = username.strip().lstrip("@").lower()

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            channel = await conn.fetchrow("""
                DELETE FROM channels
                WHERE channel_username = $1
                RETURNING *
            """, username)

            if channel:
                await conn.execute("""
                    INSERT INTO quantity_events
                    (channel_username, event_type, quantity, details)
                    VALUES ($1, 'REMOVE_CHANNEL', $2, 'Channel removed')
                """, username, channel["quantity"])

            return channel


async def get_channel(username):
    username = username.strip().lstrip("@").lower()

    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM channels
            WHERE channel_username = $1
        """, username)


async def get_all_channels():
    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM channels
            ORDER BY created_at DESC
        """)


async def set_quantity(username, quantity):
    username = username.strip().lstrip("@").lower()

    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            channel = await conn.fetchrow("""
                UPDATE channels
                SET quantity = $2,
                    updated_at = NOW()
                WHERE channel_username = $1
                RETURNING *
            """, username, quantity)

            if channel:
                await conn.execute("""
                    INSERT INTO quantity_events
                    (channel_username, event_type, quantity, details)
                    VALUES ($1, 'SET_QUANTITY', $2, 'Quantity updated')
                """, username, quantity)

            return channel


async def update_channel_status(username, is_active):
    username = username.strip().lstrip("@").lower()

    event_type = "START" if is_active else "STOP"

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            channel = await conn.fetchrow("""
                UPDATE channels
                SET is_active = $2,
                    updated_at = NOW()
                WHERE channel_username = $1
                RETURNING *
            """, username, is_active)

            if channel:
                await conn.execute("""
                    INSERT INTO quantity_events
                    (channel_username, event_type, quantity, details)
                    VALUES ($1, $2, $3, $4)
                """,
                username,
                event_type,
                channel["quantity"],
                f"Channel service {event_type.lower()}")

            return channel


async def get_report(hours=None, channel_username=None):
    """
    Fetch channel activity report.

    hours=None means all available history.
    """

    async with get_pool().acquire() as conn:

        query = """
            SELECT
                channel_username,
                event_type,
                quantity,
                details,
                created_at
            FROM quantity_events
            WHERE ($1::INTEGER IS NULL
                   OR created_at >= NOW() - ($1 * INTERVAL '1 hour'))
            AND ($2::TEXT IS NULL
                 OR channel_username = $2)
            ORDER BY created_at DESC
        """

        if channel_username:
            channel_username = (
                channel_username.strip().lstrip("@").lower()
            )

        return await conn.fetch(
            query,
            hours,
            channel_username
        )


async def test_db():
    async with get_pool().acquire() as conn:
        return await conn.fetchval("SELECT 1")
