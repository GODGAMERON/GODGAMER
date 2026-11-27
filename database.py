
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
        raise RuntimeError("DATABASE_URL is missing.")

    if pool is not None:
        return

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60
    )

    try:
        async with pool.acquire() as conn:

            # -------------------------------------------------
            # CHANNELS
            # -------------------------------------------------

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id BIGSERIAL PRIMARY KEY,
                    channel_username TEXT UNIQUE,
                    username TEXT,
                    chat_id BIGINT UNIQUE,
                    title TEXT,
                    channel_type TEXT NOT NULL DEFAULT 'public',
                    invite_link TEXT,
                    quantity BIGINT NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    automation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    added_by BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            channel_columns = {
                "channel_username": "TEXT",
                "username": "TEXT",
                "chat_id": "BIGINT",
                "title": "TEXT",
                "channel_type": "TEXT NOT NULL DEFAULT 'public'",
                "invite_link": "TEXT",
                "quantity": "BIGINT NOT NULL DEFAULT 0",
                "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "automation_enabled": "BOOLEAN NOT NULL DEFAULT TRUE",
                "added_by": "BIGINT",
                "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
                "updated_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            }

            for column, definition in channel_columns.items():
                await conn.execute(
                    f"""
                    ALTER TABLE channels
                    ADD COLUMN IF NOT EXISTS {column} {definition}
                    """
                )

            # Old and new username columns compatibility.
            await conn.execute("""
                UPDATE channels
                SET channel_username = COALESCE(
                    channel_username,
                    username
                ),
                username = COALESCE(
                    username,
                    channel_username
                )
                WHERE channel_username IS NULL
                   OR username IS NULL
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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_quantity_events_created
                ON quantity_events(created_at DESC)
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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_permissions (
                    id BIGSERIAL PRIMARY KEY,
                    admin_id BIGINT NOT NULL
                        REFERENCES admins(id) ON DELETE CASCADE,
                    channel_management BOOLEAN NOT NULL DEFAULT FALSE,
                    quantity_management BOOLEAN NOT NULL DEFAULT FALSE,
                    reports BOOLEAN NOT NULL DEFAULT FALSE,
                    panel_management BOOLEAN NOT NULL DEFAULT FALSE,
                    service_management BOOLEAN NOT NULL DEFAULT FALSE,
                    order_management BOOLEAN NOT NULL DEFAULT FALSE,
                    admin_management BOOLEAN NOT NULL DEFAULT FALSE,
                    automation_management BOOLEAN NOT NULL DEFAULT FALSE,
                    system_management BOOLEAN NOT NULL DEFAULT FALSE,
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
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    last_balance NUMERIC,
                    added_by BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            panel_columns = {
                "name": "TEXT",
                "api_url": "TEXT",
                "api_key": "TEXT",
                "active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "last_balance": "NUMERIC",
                "added_by": "BIGINT",
                "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
                "updated_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            }

            for column, definition in panel_columns.items():
                await conn.execute(
                    f"""
                    ALTER TABLE panels
                    ADD COLUMN IF NOT EXISTS {column} {definition}
                    """
                )

            # -------------------------------------------------
            # CHANNEL SERVICES
            # -------------------------------------------------

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_services (
                    id BIGSERIAL PRIMARY KEY,
                    channel_id BIGINT NOT NULL
                        REFERENCES channels(id) ON DELETE CASCADE,
                    panel_id BIGINT NOT NULL
                        REFERENCES panels(id) ON DELETE RESTRICT,
                    service_id BIGINT NOT NULL,
                    service_name TEXT,
                    quantity BIGINT,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    priority INTEGER NOT NULL DEFAULT 1,
                    min_quantity BIGINT,
                    max_quantity BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(channel_id, panel_id, service_id)
                )
            """)

            service_columns = {
                "service_name": "TEXT",
                "quantity": "BIGINT",
                "active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "priority": "INTEGER NOT NULL DEFAULT 1",
                "min_quantity": "BIGINT",
                "max_quantity": "BIGINT",
                "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
                "updated_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            }

            for column, definition in service_columns.items():
                await conn.execute(
                    f"""
                    ALTER TABLE channel_services
                    ADD COLUMN IF NOT EXISTS {column} {definition}
                    """
                )

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_channel_services_channel
                ON channel_services(channel_id)
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
                    posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            order_columns = {
                "channel_id": "BIGINT REFERENCES channels(id) ON DELETE SET NULL",
                "post_id": "BIGINT REFERENCES channel_posts(id) ON DELETE SET NULL",
                "channel_service_id": "BIGINT REFERENCES channel_services(id) ON DELETE SET NULL",
                "panel_id": "BIGINT REFERENCES panels(id) ON DELETE SET NULL",
                "service_id": "BIGINT",
                "quantity": "BIGINT",
                "external_order_id": "TEXT",
                "status": "TEXT NOT NULL DEFAULT 'submitting'",
                "charge": "NUMERIC",
                "error_message": "TEXT",
                "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
                "updated_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            }

            for column, definition in order_columns.items():
                await conn.execute(
                    f"""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS {column} {definition}
                    """
                )

            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_orders_post_service_unique
                ON orders(post_id, channel_service_id)
                WHERE post_id IS NOT NULL
                  AND channel_service_id IS NOT NULL
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

    except Exception:
        await pool.close()
        pool = None
        logger.exception("Database initialization failed.")
        raise


async def close_db():
    global pool

    if pool is not None:
        await pool.close()
        pool = None
        logger.info("Database connection closed.")


def get_pool():
    if pool is None:
        raise RuntimeError(
            "Database is not initialized. Call init_db() first."
        )

    return pool


# =========================================================
# COMMON HELPERS
# =========================================================

def normalize_username(username):
    if username is None:
        return None

    value = str(username).strip()

    value = value.replace("https://t.me/", "")
    value = value.replace("http://t.me/", "")

    value = value.lstrip("@").rstrip("/").lower()

    return value or None


async def log_quantity_event(
    channel_username,
    event_type,
    quantity=None,
    details=None
):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO quantity_events (
                channel_username,
                event_type,
                quantity,
                details
            )
            VALUES ($1, $2, $3, $4)
        """,
        normalize_username(channel_username),
        event_type,
        quantity,
        details)


# =========================================================
# CHANNEL MANAGEMENT
# =========================================================

async def add_channel(
    username=None,
    chat_id=None,
    title=None,
    channel_type="public",
    added_by=None,
    invite_link=None
):
    username = normalize_username(username)

    if chat_id is not None:
        chat_id = int(chat_id)

    if username is None and chat_id is None:
        raise ValueError("Username or chat_id is required.")

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                INSERT INTO channels (
                    channel_username,
                    username,
                    chat_id,
                    title,
                    channel_type,
                    invite_link,
                    quantity,
                    is_active,
                    automation_enabled,
                    added_by
                )
                VALUES (
                    $1, $1, $2, $3, $4, $5,
                    0, TRUE, TRUE, $6
                )
                ON CONFLICT DO NOTHING
                RETURNING *
            """,
            username,
            chat_id,
            title or username,
            channel_type,
            invite_link,
            added_by)

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


async def get_channel(identifier):
    async with get_pool().acquire() as conn:

        if isinstance(identifier, int):
            return await conn.fetchrow("""
                SELECT *
                FROM channels
                WHERE chat_id = $1 OR id = $1
                ORDER BY
                    CASE WHEN chat_id = $1 THEN 0 ELSE 1 END
                LIMIT 1
            """, identifier)

        value = str(identifier).strip()

        try:
            numeric_id = int(value)
        except ValueError:
            numeric_id = None

        if numeric_id is not None:
            result = await conn.fetchrow("""
                SELECT *
                FROM channels
                WHERE chat_id = $1 OR id = $1
                ORDER BY
                    CASE WHEN chat_id = $1 THEN 0 ELSE 1 END
                LIMIT 1
            """, numeric_id)

            if result:
                return result

        username = normalize_username(value)

        return await conn.fetchrow("""
            SELECT *
            FROM channels
            WHERE LOWER(channel_username) = $1
               OR LOWER(username) = $1
               OR invite_link = $2
            LIMIT 1
        """, username, value)


async def get_all_channels(active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT *
                FROM channels
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """)

        return await conn.fetch("""
            SELECT *
            FROM channels
            ORDER BY created_at DESC
        """)


async def remove_channel(identifier):
    channel = await get_channel(identifier)

    if not channel:
        return None

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                UPDATE channels
                SET is_active = FALSE,
                    automation_enabled = FALSE,
                    updated_at = NOW()
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
                    VALUES ($1, 'REMOVE_CHANNEL', $2, 'Channel deactivated')
                """,
                result["channel_username"],
                result["quantity"])

            return result


async def update_channel_status(identifier, is_active):
    channel = await get_channel(identifier)

    if not channel:
        return None

    enabled = bool(is_active)

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            result = await conn.fetchrow("""
                UPDATE channels
                SET is_active = $2,
                    automation_enabled = $2,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, channel["id"], enabled)

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
                result["channel_username"],
                "START" if enabled else "STOP",
                result["quantity"],
                "Channel automation enabled" if enabled
                else "Channel automation disabled")

            return result


async def set_channel_automation(channel_id, enabled):
    return await update_channel_status(
        int(channel_id),
        bool(enabled)
    )


async def set_quantity(identifier, quantity, changed_by=None):
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
                    VALUES ($1, 'SET_QUANTITY', $2, $3)
                """,
                result["channel_username"],
                quantity,
                f"Quantity updated by {changed_by}" if changed_by
                else "Quantity updated")

            return result


async def get_quantity(identifier):
    channel = await get_channel(identifier)

    if not channel:
        return None

    return channel["quantity"]


# =========================================================
# ADMIN MANAGEMENT
# =========================================================

async def get_admin(user_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM admins
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
            """,
            int(user_id),
            username,
            full_name,
            added_by)

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
            SELECT *
            FROM admins
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

        return dict(row) if row else {}


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
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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


async def set_admin_permission(
    admin_id,
    permission,
    is_allowed
):
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

    if permission not in allowed:
        raise ValueError(f"Unknown permission: {permission}")

    async with get_pool().acquire() as conn:
        return await conn.fetchrow(f"""
            INSERT INTO admin_permissions (
                admin_id,
                {permission}
            )
            VALUES ($1, $2)
            ON CONFLICT (admin_id)
            DO UPDATE SET
                {permission} = EXCLUDED.{permission}
            RETURNING *
        """, int(admin_id), bool(is_allowed))


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
                active,
                is_active
            )
            VALUES ($1, $2, $3, $4, TRUE, TRUE)
            ON CONFLICT (name) DO NOTHING
            RETURNING *
        """,
        name.strip(),
        api_url.strip(),
        api_key.strip(),
        added_by)


async def get_panel(panel_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM panels
            WHERE id = $1
        """, int(panel_id))


async def get_panel_by_name(name):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM panels
            WHERE LOWER(name) = LOWER($1)
        """, name.strip())


async def get_all_panels(active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT *
                FROM panels
                WHERE active = TRUE
                  AND is_active = TRUE
                ORDER BY id DESC
            """)

        return await conn.fetch("""
            SELECT *
            FROM panels
            ORDER BY id DESC
        """)


async def remove_panel(panel_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE panels
            SET active = FALSE,
                is_active = FALSE,
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
    quantity=None,
    priority=1,
    min_quantity=None,
    max_quantity=None
):
    service_id = int(service_id)

    if quantity is not None:
        quantity = int(quantity)

        if quantity <= 0:
            raise ValueError("Service quantity must be greater than zero.")

    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channel_services (
                channel_id,
                panel_id,
                service_id,
                service_name,
                quantity,
                active,
                is_active,
                priority,
                min_quantity,
                max_quantity
            )
            VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, $6, $7, $8)
            ON CONFLICT (channel_id, panel_id, service_id)
            DO UPDATE SET
                service_name = EXCLUDED.service_name,
                quantity = COALESCE(
                    EXCLUDED.quantity,
                    channel_services.quantity
                ),
                active = TRUE,
                is_active = TRUE,
                priority = EXCLUDED.priority,
                min_quantity = EXCLUDED.min_quantity,
                max_quantity = EXCLUDED.max_quantity,
                updated_at = NOW()
            RETURNING *
        """,
        int(channel_id),
        int(panel_id),
        service_id,
        service_name,
        quantity,
        int(priority),
        min_quantity,
        max_quantity)


async def get_channel_services(channel_id, active_only=False):
    async with get_pool().acquire() as conn:

        if active_only:
            return await conn.fetch("""
                SELECT
                    cs.*,
                    COALESCE(cs.quantity, c.quantity, 0)
                        AS effective_quantity
                FROM channel_services cs
                JOIN channels c ON c.id = cs.channel_id
                WHERE cs.channel_id = $1
                  AND cs.active = TRUE
                  AND cs.is_active = TRUE
                ORDER BY cs.priority, cs.id
            """, int(channel_id))

        return await conn.fetch("""
            SELECT
                cs.*,
                COALESCE(cs.quantity, c.quantity, 0)
                    AS effective_quantity
            FROM channel_services cs
            JOIN channels c ON c.id = cs.channel_id
            WHERE cs.channel_id = $1
            ORDER BY cs.priority, cs.id
        """, int(channel_id))


async def set_channel_service_quantity(
    channel_id,
    panel_id,
    service_id,
    quantity
):
    quantity = int(quantity)

    if quantity <= 0:
        raise ValueError("Service quantity must be greater than zero.")

    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE channel_services
            SET quantity = $4,
                updated_at = NOW()
            WHERE channel_id = $1
              AND panel_id = $2
              AND service_id = $3
            RETURNING *
        """,
        int(channel_id),
        int(panel_id),
        int(service_id),
        quantity)


async def remove_channel_service(channel_id, service_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            UPDATE channel_services
            SET active = FALSE,
                is_active = FALSE,
                updated_at = NOW()
            WHERE channel_id = $1
              AND service_id = $2
              AND active = TRUE
              AND is_active = TRUE
            RETURNING *
        """, int(channel_id), int(service_id))


# =========================================================
# CHANNEL POST MANAGEMENT
# =========================================================

async def record_post(
    channel_id,
    telegram_message_id,
    post_url=None,
    posted_at=None
):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO channel_posts (
                channel_id,
                telegram_message_id,
                post_url,
                posted_at
            )
            VALUES ($1, $2, $3, COALESCE($4, NOW()))
            ON CONFLICT (channel_id, telegram_message_id)
            DO NOTHING
            RETURNING *
        """,
        int(channel_id),
        int(telegram_message_id),
        post_url,
        posted_at)


async def get_post(channel_id, telegram_message_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM channel_posts
            WHERE channel_id = $1
              AND telegram_message_id = $2
        """, int(channel_id), int(telegram_message_id))


# =========================================================
# ORDER MANAGEMENT
# =========================================================

async def create_order(
    channel_id,
    service_id,
    quantity,
    panel_id=None,
    post_id=None,
    channel_service_id=None,
    external_order_id=None,
    charge=None,
    status="pending"
):
    quantity = int(quantity)

    if quantity <= 0:
        raise ValueError("Order quantity must be positive.")

    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO orders (
                channel_id,
                post_id,
                channel_service_id,
                panel_id,
                service_id,
                quantity,
                external_order_id,
                charge,
                status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (post_id, channel_service_id)
            WHERE post_id IS NOT NULL
              AND channel_service_id IS NOT NULL
            DO NOTHING
            RETURNING *
        """,
        channel_id,
        post_id,
        channel_service_id,
        panel_id,
        int(service_id),
        quantity,
        str(external_order_id) if external_order_id else None,
        charge,
        status)


async def get_order(order_id):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM orders
            WHERE id = $1
        """, int(order_id))


async def get_orders(
    channel_id=None,
    status=None,
    limit=50
):
    limit = max(1, min(int(limit), 500))

    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT *
            FROM orders
            WHERE ($1::BIGINT IS NULL OR channel_id = $1)
              AND ($2::TEXT IS NULL OR status = $2)
            ORDER BY created_at DESC
            LIMIT $3
        """,
        int(channel_id) if channel_id is not None else None,
        status,
        limit)


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
                external_order_id = COALESCE(
                    $3,
                    external_order_id
                ),
                charge = COALESCE($4, charge),
                error_message = $5,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """,
        int(order_id),
        status,
        str(external_order_id) if external_order_id else None,
        charge,
        error_message)


# =========================================================
# REPORTS
# =========================================================

async def get_report(
    hours=None,
    channel_username=None,
    channel_id=None
):
    username = normalize_username(channel_username)

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
                OR created_at >= NOW() - (
                    $1 * INTERVAL '1 hour'
                )
            )
            AND (
                $2::TEXT IS NULL
                OR LOWER(channel_username) = $2
            )
            AND (
                $3::BIGINT IS NULL
                OR channel_username IN (
                    SELECT channel_username
                    FROM channels
                    WHERE id = $3
                )
            )
            ORDER BY created_at DESC
        """,
        int(hours) if hours is not None else None,
        username,
        int(channel_id) if channel_id is not None else None)


async def get_report_summary(hours, channel_id=None):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(quantity), 0) AS total_quantity,
                COALESCE(SUM(charge), 0) AS total_spend
            FROM orders
            WHERE created_at >= NOW() - (
                $1 * INTERVAL '1 hour'
            )
            AND (
                $2::BIGINT IS NULL
                OR channel_id = $2
            )
        """,
        int(hours),
        int(channel_id) if channel_id is not None else None)


# =========================================================
# DATABASE HEALTH
# =========================================================

async def test_db():
    async with get_pool().acquire() as conn:
        return await conn.fetchval("SELECT 1")


logger.info("Database module loaded.")
