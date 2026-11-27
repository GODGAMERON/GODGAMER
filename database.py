
import logging
import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(__name__)

pool = None


# =========================================================
# DATABASE CONNECTION
# =========================================================

async def init_db():
    global pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is missing")

    if pool is not None:
        return

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60
    )

    async with pool.acquire() as conn:

        # -------------------------------------------------
        # CHANNELS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id BIGSERIAL PRIMARY KEY,
                channel_username TEXT UNIQUE,
                chat_id BIGINT UNIQUE,
                title TEXT,
                channel_type TEXT DEFAULT 'public',
                quantity BIGINT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                automation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                added_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        channel_columns = {
            "chat_id": "BIGINT",
            "title": "TEXT",
            "channel_type": "TEXT DEFAULT 'public'",
            "quantity": "BIGINT NOT NULL DEFAULT 0",
            "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
            "automation_enabled": "BOOLEAN NOT NULL DEFAULT TRUE",
            "added_by": "BIGINT",
            "created_at": "TIMESTAMPTZ DEFAULT NOW()",
            "updated_at": "TIMESTAMPTZ DEFAULT NOW()"
        }

        for column, definition in channel_columns.items():
            await conn.execute(
                f"""
                ALTER TABLE channels
                ADD COLUMN IF NOT EXISTS {column} {definition}
                """
            )

        await conn.execute("""
            ALTER TABLE channels
            ALTER COLUMN channel_username DROP NOT NULL
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_channels_chat_id
            ON channels(chat_id)
            WHERE chat_id IS NOT NULL
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_channels_username
            ON channels(LOWER(channel_username))
            WHERE channel_username IS NOT NULL
        """)

        # -------------------------------------------------
        # QUANTITY EVENTS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quantity_events (
                id BIGSERIAL PRIMARY KEY,
                channel_username TEXT,
                event_type TEXT NOT NULL,
                quantity BIGINT,
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_quantity_events_created
            ON quantity_events(created_at)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_quantity_events_channel
            ON quantity_events(channel_username)
        """)

        # -------------------------------------------------
        # ADMINS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                added_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_permissions (
                id BIGSERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL
                    REFERENCES admins(id) ON DELETE CASCADE,
                channel_management BOOLEAN DEFAULT FALSE,
                quantity_management BOOLEAN DEFAULT FALSE,
                reports BOOLEAN DEFAULT FALSE,
                panel_management BOOLEAN DEFAULT FALSE,
                service_management BOOLEAN DEFAULT FALSE,
                order_management BOOLEAN DEFAULT FALSE,
                admin_management BOOLEAN DEFAULT FALSE,
                automation_management BOOLEAN DEFAULT FALSE,
                system_management BOOLEAN DEFAULT FALSE,
                UNIQUE(admin_id)
            )
        """)

        # -------------------------------------------------
        # SMM PANELS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS panels (
                id BIGSERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                api_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                last_balance NUMERIC,
                added_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # -------------------------------------------------
        # CHANNEL SERVICES
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_services (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                panel_id BIGINT NOT NULL
                    REFERENCES panels(id),
                service_id BIGINT NOT NULL,
                service_name TEXT,
                quantity BIGINT,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                priority INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(channel_id, panel_id, service_id)
            )
        """)

        # -------------------------------------------------
        # CHANNEL POSTS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_posts (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                telegram_message_id BIGINT NOT NULL,
                post_url TEXT,
                posted_at TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(channel_id, telegram_message_id)
            )
        """)

        # -------------------------------------------------
        # ORDERS
        # -------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT
                    REFERENCES channels(id) ON DELETE SET NULL,
                post_id BIGINT
                    REFERENCES channel_posts(id) ON DELETE SET NULL,
                channel_service_id BIGINT
                    REFERENCES channel_services(id) ON DELETE SET NULL,
                panel_id BIGINT
                    REFERENCES panels(id) ON DELETE SET NULL,
                service_id BIGINT NOT NULL,
                quantity BIGINT NOT NULL,
                external_order_id TEXT,
                status TEXT NOT NULL DEFAULT 'submitting',
                charge NUMERIC,
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_orders_post_service_unique
            ON orders(post_id, channel_service_id)
            WHERE channel_service_id IS NOT NULL
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_orders_status
            ON orders(status)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_orders_created
            ON orders(created_at DESC)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_orders_external
            ON orders(external_order_id)
        """)

    logger.info("Database initialized successfully.")


async def close_db():
    global pool

    if pool is not None:
        await pool.close()
        pool = None
        logger.info("Database connection closed.")


def get_pool():
    if pool is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")

    return pool


# =========================================================
# CHANNEL HELPERS
# =========================================================

def normalize_username(username):
    if username is None:
        return None

    username = str(username).strip().lstrip("@").lower()

    return username or None


async def add_channel(
    username=None,
    chat_id=None,
    title=None,
    channel_type="public",
    added_by=None
):
    """
    Public channel:
        add_channel(username)

    Private channel:
        add_channel(
            chat_id=...,
            title=...,
            channel_type="private",
            added_by=...
        )
    """

    if username is not None:
        username = normalize_username(username)

    if chat_id is not None:
        chat_id = int(chat_id)

    if username is None and chat_id is None:
        raise ValueError("Username or chat_id is required.")

    async with get_pool().acquire() as conn:

        async with conn.transaction():

            if chat_id is not None:
                result = await conn.fetchrow("""
                    INSERT INTO channels (
                        channel_username,
                        chat_id,
                        title,
                        channel_type,
                        is_active,
                        automation_enabled,
                        added_by
                    )
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, $5)
                    ON CONFLICT DO NOTHING
                    RETURNING *
                """, username, chat_id, title, channel_type, added_by)

            else:
                result = await conn.fetchrow("""
                    INSERT INTO channels (
                        channel_username,
                        title,
                        channel_type,
                        is_active,
                        automation_enabled,
                        added_by
                    )
                    VALUES ($1, $1, 'public', TRUE, TRUE, $2)
                    ON CONFLICT DO NOTHING
                    RETURNING *
                """, username, added_by)

            if result:
                await conn.execute("""
                    INSERT INTO quantity_events (
                        channel_username,
                        event_type,
                        quantity,
                        details
                    )
                    VALUES ($1, 'ADD_CHANNEL', 0, 'Channel added')
                """, username)

            return result


async def remove_channel(identifier):
    channel = await get_channel(identifier)

    if not channel:
        return None

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                DELETE FROM channels
                WHERE id = $1
                RETURNING *
            """, channel["id"])

            if result:
                await conn.execute("""
                    INSERT INTO quantity_events (
                        channel_username,
                        event_type,
                        quantity,
                        details
                    )
                    VALUES ($1, 'REMOVE_CHANNEL', $2, 'Channel removed')
                """, result.get("channel_username"), result["quantity"])

            return result


async def get_channel(identifier):
    async with get_pool().acquire() as conn:

        if isinstance(identifier, int):
            return await conn.fetchrow("""
                SELECT * FROM channels
                WHERE chat_id = $1 OR id = $1
                ORDER BY CASE WHEN chat_id = $1 THEN 0 ELSE 1 END
                LIMIT 1
            """, identifier)

        value = str(identifier).strip()

        try:
            numeric_id = int(value)
        except ValueError:
            numeric_id = None

        if numeric_id is not None:
            result = await conn.fetchrow("""
                SELECT * FROM channels
                WHERE chat_id = $1 OR id = $1
                ORDER BY CASE WHEN chat_id = $1 THEN 0 ELSE 1 END
                LIMIT 1
            """, numeric_id)

            if result:
                return result

        username = normalize_username(value)

        return await conn.fetchrow("""
            SELECT * FROM channels
            WHERE LOWER(channel_username) = $1
        """, username)


async def get_all_channels(active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT * FROM channels
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """)

        return await conn.fetch("""
            SELECT * FROM channels
            ORDER BY created_at DESC
        """)


async def set_quantity(identifier, quantity):
    quantity = int(quantity)

    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")

    channel = await get_channel(identifier)

    if not channel:
        return None

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                UPDATE channels
                SET quantity = $2,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, channel["id"], quantity)

            if result:
                await conn.execute("""
                    INSERT INTO quantity_events (
                        channel_username,
                        event_type,
                        quantity,
                        details
                    )
                    VALUES ($1, 'SET_QUANTITY', $2, 'Quantity updated')
                """, result.get("channel_username"), quantity)

            return result


async def update_channel_status(identifier, is_active):
    channel = await get_channel(identifier)

    if not channel:
        return None

    event_type = "START" if is_active else "STOP"

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                UPDATE channels
                SET is_active = $2,
                    automation_enabled = $2,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, channel["id"], bool(is_active))

            if result:
                await conn.execute("""
                    INSERT INTO quantity_events (
                        channel_username,
                        event_type,
                        quantity,
                        details
                    )
                    VALUES ($1, $2, $3, $4)
                """,
                result.get("channel_username"),
                event_type,
                result["quantity"],
                f"Channel automation {event_type.lower()}")

            return result


async def set_channel_automation(channel_id, enabled):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE channels
            SET automation_enabled = $2,
                is_active = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """, channel_id, bool(enabled))


# =========================================================
# REPORTS
# =========================================================

async def get_report(hours=None, channel_username=None):
    channel_username = normalize_username(channel_username)

    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT
                channel_username,
                event_type,
                quantity,
                details,
                created_at
            FROM quantity_events
            WHERE (
                $1::INTEGER IS NULL
                OR created_at >= NOW() - ($1 * INTERVAL '1 hour')
            )
            AND (
                $2::TEXT IS NULL
                OR channel_username = $2
            )
            ORDER BY created_at DESC
        """, hours, channel_username)


# =========================================================
# ADMIN MANAGEMENT
# =========================================================

async def get_admin(user_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM admins
            WHERE user_id = $1
              AND is_active = TRUE
        """, int(user_id))


async def add_admin(
    user_id,
    username=None,
    full_name=None,
    added_by=None
):
    async with get_pool().acquire() as conn:

        async with conn.transaction():

            admin = await conn.fetchrow("""
                INSERT INTO admins (
                    user_id,
                    username,
                    full_name,
                    added_by,
                    is_active
                )
                VALUES ($1, $2, $3, $4, TRUE)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    is_active = TRUE
                RETURNING *
            """, int(user_id), username, full_name, added_by)

            await conn.execute("""
                INSERT INTO admin_permissions (admin_id)
                VALUES ($1)
                ON CONFLICT (admin_id) DO NOTHING
            """, admin["id"])

            return admin


async def remove_admin(user_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE admins
            SET is_active = FALSE
            WHERE user_id = $1
            RETURNING *
        """, int(user_id))


async def get_all_admins():
    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM admins
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """)


async def get_admin_permissions(admin_id):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT *
            FROM admin_permissions
            WHERE admin_id = $1
        """, int(admin_id))

        if not row:
            return {}

        return dict(row)


async def set_admin_permissions(admin_id, permissions):
    allowed = {
        "channel_management",
        "quantity_management",
        "reports",
        "panel_management",
        "service_management",
        "order_management",
        "admin_management",
        "automation_management",
        "system_management"
    }

    values = {
        key: bool(permissions.get(key, False))
        for key in allowed
    }

    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO admin_permissions (
                admin_id,
                channel_management,
                quantity_management,
                reports,
                panel_management,
                service_management,
                order_management,
                admin_management,
                automation_management,
                system_management
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
            ON CONFLICT (admin_id)
            DO UPDATE SET
                channel_management = EXCLUDED.channel_management,
                quantity_management = EXCLUDED.quantity_management,
                reports = EXCLUDED.reports,
                panel_management = EXCLUDED.panel_management,
                service_management = EXCLUDED.service_management,
                order_management = EXCLUDED.order_management,
                admin_management = EXCLUDED.admin_management,
                automation_management = EXCLUDED.automation_management,
                system_management = EXCLUDED.system_management
            RETURNING *
        """,
        int(admin_id),
        values["channel_management"],
        values["quantity_management"],
        values["reports"],
        values["panel_management"],
        values["service_management"],
        values["order_management"],
        values["admin_management"],
        values["automation_management"],
        values["system_management"])


# =========================================================
# PANEL MANAGEMENT
# =========================================================

async def add_panel(
    name,
    api_url,
    api_key,
    added_by=None
):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO panels (
                name,
                api_url,
                api_key,
                added_by,
                active
            )
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (name) DO NOTHING
            RETURNING *
        """, name.strip(), api_url.strip(), api_key.strip(), added_by)


async def get_panel(panel_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM panels
            WHERE id = $1
        """, int(panel_id))


async def get_panel_by_name(name):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM panels
            WHERE LOWER(name) = LOWER($1)
        """, name.strip())


async def get_all_panels(active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT * FROM panels
                WHERE active = TRUE
                ORDER BY id DESC
            """)

        return await conn.fetch("""
            SELECT * FROM panels
            ORDER BY id DESC
        """)


async def remove_panel(panel_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE panels
            SET active = FALSE,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """, int(panel_id))


async def update_panel_balance(panel_id, balance):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE panels
            SET last_balance = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """, int(panel_id), balance)


# =========================================================
# CHANNEL SERVICE MANAGEMENT
# =========================================================

async def add_channel_service(
    channel_id,
    panel_id,
    service_id,
    service_name=None,
    quantity=None
):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channel_services (
                channel_id,
                panel_id,
                service_id,
                service_name,
                quantity,
                active
            )
            VALUES ($1, $2, $3, $4, $5, TRUE)
            ON CONFLICT (channel_id, panel_id, service_id)
            DO UPDATE SET
                service_name = EXCLUDED.service_name,
                active = TRUE,
                updated_at = NOW()
            RETURNING *
        """,
        int(channel_id),
        int(panel_id),
        int(service_id),
        service_name,
        quantity)


async def get_channel_services(channel_id, active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT * FROM channel_services
                WHERE channel_id = $1
                  AND active = TRUE
                ORDER BY priority, id
            """, int(channel_id))

        return await conn.fetch("""
            SELECT * FROM channel_services
            WHERE channel_id = $1
            ORDER BY priority, id
        """, int(channel_id))


async def remove_channel_service(channel_id, service_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE channel_services
            SET active = FALSE,
                updated_at = NOW()
            WHERE channel_id = $1
              AND service_id = $2
              AND active = TRUE
            RETURNING *
        """, int(channel_id), int(service_id))


# =========================================================
# ORDER MANAGEMENT
# =========================================================

async def get_order(order_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM orders
            WHERE id = $1
        """, int(order_id))


async def get_orders(status=None, limit=20):
    limit = max(1, min(int(limit), 500))

    async with get_pool().acquire() as conn:

        if status:
            return await conn.fetch("""
                SELECT * FROM orders
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, status, limit)

        return await conn.fetch("""
            SELECT * FROM orders
            ORDER BY created_at DESC
            LIMIT $1
        """, limit)


async def update_order_status(
    order_id,
    status,
    external_order_id=None,
    charge=None,
    error_message=None
):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE orders
            SET status = $2,
                external_order_id =
                    COALESCE($3, external_order_id),
                charge = COALESCE($4, charge),
                error_message = $5,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """,
        int(order_id),
        status,
        external_order_id,
        charge,
        error_message)


# =========================================================
# DATABASE HEALTH
# =========================================================

async def test_db():
    async with get_pool().acquire() as conn:
        return await conn.fetchval("SELECT 1")


logger.info("Database module loaded.")
