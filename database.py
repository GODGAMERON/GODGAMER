
import logging
import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(__name__)

pool = None


# ==========================================
# DATABASE CONNECTION
# ==========================================

async def init_db():
    """Connect to PostgreSQL and create/update database tables."""
    global pool

    if pool is not None:
        return

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing in Railway Variables.")

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60
    )

    async with pool.acquire() as conn:

        # ----------------------------------
        # CHANNELS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT UNIQUE,
                username TEXT UNIQUE,
                title TEXT,
                channel_type TEXT NOT NULL DEFAULT 'public',
                invite_link TEXT,
                quantity BIGINT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                automation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                added_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Safe additions for an older channels table.
        await conn.execute("""
            ALTER TABLE channels
                ADD COLUMN IF NOT EXISTS chat_id BIGINT,
                ADD COLUMN IF NOT EXISTS title TEXT,
                ADD COLUMN IF NOT EXISTS channel_type TEXT DEFAULT 'public',
                ADD COLUMN IF NOT EXISTS invite_link TEXT,
                ADD COLUMN IF NOT EXISTS automation_enabled BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS added_by BIGINT,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_channels_chat_id ON channels(chat_id)
            WHERE chat_id IS NOT NULL
        """)

        # ----------------------------------
        # SMM PANELS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS smm_panels (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                api_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                last_balance NUMERIC(18, 6),
                last_checked_at TIMESTAMPTZ,
                added_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ----------------------------------
        # CHANNEL SERVICE ASSIGNMENTS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_services (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                panel_id BIGINT NOT NULL
                    REFERENCES smm_panels(id) ON DELETE RESTRICT,
                service_id TEXT NOT NULL,
                service_name TEXT,
                priority INTEGER NOT NULL DEFAULT 1,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                min_quantity BIGINT,
                max_quantity BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(channel_id, panel_id, service_id)
            )
        """)

        # ----------------------------------
        # ADMINS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                added_by BIGINT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_permissions (
                id BIGSERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL
                    REFERENCES admins(id) ON DELETE CASCADE,
                permission TEXT NOT NULL,
                is_allowed BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(admin_id, permission)
            )
        """)

        # ----------------------------------
        # TELEGRAM POSTS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_posts (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                telegram_message_id BIGINT NOT NULL,
                post_url TEXT,
                posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(channel_id, telegram_message_id)
            )
        """)

        # ----------------------------------
        # ORDERS
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE RESTRICT,
                post_id BIGINT
                    REFERENCES channel_posts(id) ON DELETE SET NULL,
                channel_service_id BIGINT
                    REFERENCES channel_services(id) ON DELETE SET NULL,
                panel_id BIGINT
                    REFERENCES smm_panels(id) ON DELETE SET NULL,
                external_order_id TEXT,
                service_id TEXT NOT NULL,
                quantity BIGINT NOT NULL,
                charge NUMERIC(18, 6) DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_orders_post_service
            ON orders(post_id, channel_service_id)
            WHERE post_id IS NOT NULL
              AND channel_service_id IS NOT NULL
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_created_at
            ON orders(created_at)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_channel_id
            ON orders(channel_id)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON orders(status)
        """)

        # ----------------------------------
        # QUANTITY CHANGE HISTORY
        # ----------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quantity_logs (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                old_quantity BIGINT NOT NULL,
                new_quantity BIGINT NOT NULL,
                changed_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

    logger.info("PostgreSQL database initialized successfully.")


async def close_db():
    """Close the PostgreSQL connection pool."""
    global pool

    if pool is not None:
        await pool.close()
        pool = None
        logger.info("Database connection closed.")


def get_pool():
    """Return the active database pool."""
    if pool is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")

    return pool


async def test_db():
    """Check database connection."""
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchval("SELECT 1")


# ==========================================
# CHANNEL FUNCTIONS
# ==========================================

async def add_channel(
    username=None,
    chat_id=None,
    title=None,
    channel_type="public",
    invite_link=None,
    added_by=None
):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channels (
                username, chat_id, title, channel_type,
                invite_link, added_by
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            RETURNING *
        """, username, chat_id, title, channel_type, invite_link, added_by)


async def get_channel(identifier):
    db = get_pool()

    async with db.acquire() as conn:
        if isinstance(identifier, int):
            return await conn.fetchrow("""
                SELECT * FROM channels
                WHERE id = $1 OR chat_id = $1
                LIMIT 1
            """, identifier)

        value = str(identifier).strip().replace("@", "")

        return await conn.fetchrow("""
            SELECT * FROM channels
            WHERE LOWER(username) = LOWER($1)
               OR invite_link = $2
            LIMIT 1
        """, value, str(identifier).strip())


async def get_all_channels(active_only=False):
    db = get_pool()

    async with db.acquire() as conn:
        if active_only:
            return await conn.fetch("""
                SELECT * FROM channels
                WHERE is_active = TRUE
                ORDER BY id
            """)

        return await conn.fetch("""
            SELECT * FROM channels
            ORDER BY id
        """)


async def remove_channel(identifier):
    db = get_pool()

    async with db.acquire() as conn:
        channel = await get_channel(identifier)

        if not channel:
            return False

        # Keep historical orders; deactivate the channel.
        await conn.execute("""
            UPDATE channels
            SET is_active = FALSE,
                automation_enabled = FALSE,
                updated_at = NOW()
            WHERE id = $1
        """, channel["id"])

        return True


async def update_channel_status(identifier, is_active):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE channels
            SET is_active = $2,
                updated_at = NOW()
            WHERE id = $1
        """, identifier, is_active)

        return result.endswith("1")


async def set_channel_automation(channel_id, enabled):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE channels
            SET automation_enabled = $2,
                updated_at = NOW()
            WHERE id = $1
        """, channel_id, enabled)

        return result.endswith("1")


# ==========================================
# QUANTITY FUNCTIONS
# ==========================================

async def set_quantity(channel_id, quantity, changed_by=None):
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Quantity must be a positive integer.")

    db = get_pool()

    async with db.acquire() as conn:
        async with conn.transaction():

            channel = await conn.fetchrow("""
                SELECT quantity FROM channels
                WHERE id = $1
                FOR UPDATE
            """, channel_id)

            if not channel:
                return False

            old_quantity = channel["quantity"]

            await conn.execute("""
                UPDATE channels
                SET quantity = $2,
                    updated_at = NOW()
                WHERE id = $1
            """, channel_id, quantity)

            await conn.execute("""
                INSERT INTO quantity_logs (
                    channel_id, old_quantity, new_quantity, changed_by
                )
                VALUES ($1, $2, $3, $4)
            """, channel_id, old_quantity, quantity, changed_by)

        return True


async def get_quantity(channel_id):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchval("""
            SELECT quantity FROM channels
            WHERE id = $1
        """, channel_id)


# ==========================================
# SMM PANEL FUNCTIONS
# ==========================================

async def add_panel(name, api_url, api_key, added_by=None):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO smm_panels (
                name, api_url, api_key, added_by
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (name) DO NOTHING
            RETURNING *
        """, name.strip(), api_url.strip(), api_key.strip(), added_by)


async def get_panel(panel_id):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM smm_panels
            WHERE id = $1
        """, panel_id)


async def get_panel_by_name(name):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM smm_panels
            WHERE LOWER(name) = LOWER($1)
        """, name.strip())


async def get_all_panels(active_only=False):
    db = get_pool()

    async with db.acquire() as conn:
        if active_only:
            return await conn.fetch("""
                SELECT id, name, api_url, is_active,
                       last_balance, last_checked_at, created_at
                FROM smm_panels
                WHERE is_active = TRUE
                ORDER BY name
            """)

        return await conn.fetch("""
            SELECT id, name, api_url, is_active,
                   last_balance, last_checked_at, created_at
            FROM smm_panels
            ORDER BY name
        """)


async def remove_panel(panel_id):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE smm_panels
            SET is_active = FALSE
            WHERE id = $1
        """, panel_id)

        return result.endswith("1")


async def update_panel_balance(panel_id, balance):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE smm_panels
            SET last_balance = $2,
                last_checked_at = NOW()
            WHERE id = $1
        """, panel_id, balance)

        return result.endswith("1")


# ==========================================
# CHANNEL SERVICE FUNCTIONS
# ==========================================

async def add_channel_service(
    channel_id,
    panel_id,
    service_id,
    service_name=None,
    priority=1,
    min_quantity=None,
    max_quantity=None
):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channel_services (
                channel_id, panel_id, service_id, service_name,
                priority, min_quantity, max_quantity
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (channel_id, panel_id, service_id)
            DO UPDATE SET
                service_name = EXCLUDED.service_name,
                priority = EXCLUDED.priority,
                min_quantity = EXCLUDED.min_quantity,
                max_quantity = EXCLUDED.max_quantity,
                is_active = TRUE
            RETURNING *
        """, channel_id, panel_id, str(service_id), service_name,
             priority, min_quantity, max_quantity)


async def get_channel_services(channel_id, active_only=True):
    db = get_pool()

    async with db.acquire() as conn:
        if active_only:
            return await conn.fetch("""
                SELECT
                    cs.*,
                    sp.name AS panel_name,
                    sp.is_active AS panel_is_active
                FROM channel_services cs
                JOIN smm_panels sp ON sp.id = cs.panel_id
                WHERE cs.channel_id = $1
                  AND cs.is_active = TRUE
                  AND sp.is_active = TRUE
                ORDER BY cs.priority ASC, cs.id ASC
            """, channel_id)

        return await conn.fetch("""
            SELECT cs.*, sp.name AS panel_name
            FROM channel_services cs
            JOIN smm_panels sp ON sp.id = cs.panel_id
            WHERE cs.channel_id = $1
            ORDER BY cs.priority ASC, cs.id ASC
        """, channel_id)


async def remove_channel_service(channel_id, service_id):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE channel_services
            SET is_active = FALSE
            WHERE channel_id = $1
              AND service_id = $2
        """, channel_id, str(service_id))

        return result.endswith("1")


# ==========================================
# ADMIN FUNCTIONS
# ==========================================

async def add_admin(user_id, added_by=None):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO admins (user_id, added_by)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET is_active = TRUE
            RETURNING *
        """, user_id, added_by)


async def remove_admin(user_id):
    db = get_pool()

    async with db.acquire() as conn:
        result = await conn.execute("""
            UPDATE admins
            SET is_active = FALSE
            WHERE user_id = $1
        """, user_id)

        return result.endswith("1")


async def get_admin(user_id):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM admins
            WHERE user_id = $1 AND is_active = TRUE
        """, user_id)


async def get_all_admins():
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM admins
            WHERE is_active = TRUE
            ORDER BY created_at
        """)


async def set_admin_permission(admin_id, permission, is_allowed):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO admin_permissions (
                admin_id, permission, is_allowed
            )
            VALUES ($1, $2, $3)
            ON CONFLICT (admin_id, permission)
            DO UPDATE SET
                is_allowed = EXCLUDED.is_allowed,
                updated_at = NOW()
            RETURNING *
        """, admin_id, permission, is_allowed)


async def get_admin_permissions(admin_id):
    db = get_pool()

    async with db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT permission, is_allowed
            FROM admin_permissions
            WHERE admin_id = $1
        """, admin_id)

        return {
            row["permission"]: row["is_allowed"]
            for row in rows
        }


# ==========================================
# TELEGRAM POST FUNCTIONS
# ==========================================

async def record_post(
    channel_id,
    telegram_message_id,
    post_url=None,
    posted_at=None
):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channel_posts (
                channel_id, telegram_message_id, post_url, posted_at
            )
            VALUES (
                $1, $2, $3, COALESCE($4, NOW())
            )
            ON CONFLICT (channel_id, telegram_message_id)
            DO NOTHING
            RETURNING *
        """, channel_id, telegram_message_id, post_url, posted_at)


async def get_post(channel_id, telegram_message_id):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM channel_posts
            WHERE channel_id = $1
              AND telegram_message_id = $2
        """, channel_id, telegram_message_id)


# ==========================================
# ORDER FUNCTIONS
# ==========================================

async def create_order(
    channel_id,
    service_id,
    quantity,
    panel_id=None,
    post_id=None,
    channel_service_id=None,
    external_order_id=None,
    charge=0,
    status="pending"
):
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Order quantity must be a positive integer.")

    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO orders (
                channel_id, post_id, channel_service_id,
                panel_id, service_id, quantity,
                external_order_id, charge, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (post_id, channel_service_id)
            WHERE post_id IS NOT NULL
              AND channel_service_id IS NOT NULL
            DO NOTHING
            RETURNING *
        """, channel_id, post_id, channel_service_id,
             panel_id, str(service_id), quantity,
             external_order_id, charge, status)


async def update_order_status(
    order_id,
    status,
    external_order_id=None,
    charge=None,
    error_message=None
):
    db = get_pool()

    async with db.acquire() as conn:
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
        """, order_id, status, external_order_id,
             charge, error_message)


async def get_order(order_id):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM orders
            WHERE id = $1
        """, order_id)


async def get_orders(channel_id=None, status=None, limit=50):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetch("""
            SELECT *
            FROM orders
            WHERE ($1::BIGINT IS NULL OR channel_id = $1)
              AND ($2::TEXT IS NULL OR status = $2)
            ORDER BY created_at DESC
            LIMIT $3
        """, channel_id, status, limit)


# ==========================================
# REPORT FUNCTIONS
# ==========================================

async def get_report_summary(hours, channel_id=None):
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetchrow("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(quantity), 0) AS total_quantity,
                COALESCE(SUM(charge), 0) AS total_spend
            FROM orders
            WHERE created_at >= NOW() - ($1 * INTERVAL '1 hour')
              AND ($2::BIGINT IS NULL OR channel_id = $2)
        """, hours, channel_id)


async def get_report(hours, channel_id=None):
    """Return individual orders for the requested report period."""
    db = get_pool()

    async with db.acquire() as conn:
        return await conn.fetch("""
            SELECT *
            FROM orders
            WHERE created_at >= NOW() - ($1 * INTERVAL '1 hour')
              AND ($2::BIGINT IS NULL OR channel_id = $2)
            ORDER BY created_at DESC
        """, hours, channel_id)


logger.info("Database module loaded.")
