
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID

from database import (
    add_admin,
    remove_admin,
    get_admin,
    get_all_admins,
    set_admin_permission,
    get_admin_permissions,
)

from admin_permissions import (
    is_owner,
    is_admin,
    has_permission,
    PERMISSIONS,
    get_user_permissions,
)

logger = logging.getLogger(__name__)

router = Router()


# ==========================================
# ACCESS HELPERS
# ==========================================

async def owner_only(message: Message) -> bool:
    if not message.from_user:
        return False

    if is_owner(message.from_user.id):
        return True

    await message.answer(
        "❌ Ye command sirf Owner use kar sakta hai."
    )
    return False


async def permission_required(
    message: Message,
    permission: str
) -> bool:

    if not message.from_user:
        return False

    if await has_permission(
        message.from_user.id,
        permission
    ):
        return True

    await message.answer(
        "❌ Aapko is command ki permission nahi hai."
    )
    return False


# ==========================================
# BASIC COMMANDS
# ==========================================

@router.message(Command("myid"))
async def myid_command(message: Message):

    if not message.from_user:
        return

    await message.answer(
        f"🆔 <b>Your Telegram ID:</b>\n"
        f"<code>{message.from_user.id}</code>",
        parse_mode="HTML"
    )


@router.message(Command("admin"))
async def admin_command(message: Message):

    if not message.from_user:
        return

    user_id = message.from_user.id

    if not await is_admin(user_id):
        await message.answer(
            "❌ Aap Admin nahi hain."
        )
        return

    permissions = await get_user_permissions(user_id)

    if is_owner(user_id):
        role = "👑 Owner"
    else:
        role = "🛡 Admin"

    enabled = [
        name for name, allowed in permissions.items()
        if allowed
    ]

    text = (
        f"{role} <b>Control Panel</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"<b>Available Permissions:</b>\n"
    )

    if enabled:
        for permission in enabled:
            description = PERMISSIONS.get(
                permission,
                permission
            )
            text += f"\n✅ {description}"
    else:
        text += "\n❌ Koi permission assigned nahi hai."

    await message.answer(
        text,
        parse_mode="HTML"
    )


# ==========================================
# ADD ADMIN
# ==========================================

@router.message(Command("Addadmin"))
async def add_admin_command(message: Message):

    if not await owner_only(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "❌ Command format:\n"
            "<code>/Addadmin USER_ID</code>\n\n"
            "Example:\n"
            "<code>/Addadmin 123456789</code>",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Valid numeric Telegram ID enter karein."
        )
        return

    if user_id <= 0:
        await message.answer("❌ Invalid Telegram ID.")
        return

    if user_id == OWNER_ID:
        await message.answer(
            "❌ Owner ko Admin banane ki zaroorat nahi hai."
        )
        return

    try:
        admin = await add_admin(
            user_id,
            added_by=message.from_user.id
        )

        if not admin:
            await message.answer(
                "❌ Admin add nahi ho saka."
            )
            return

        await message.answer(
            "✅ <b>Admin successfully added!</b>\n\n"
            f"🆔 Admin ID: <code>{user_id}</code>\n\n"
            "⚠️ Abhi is Admin ko koi permission nahi di gayi hai.\n"
            "Owner /adminpower se permissions set kar sakta hai.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Add admin failed")
        await message.answer(
            "❌ Admin add karte waqt database error aaya."
        )


# ==========================================
# REMOVE ADMIN
# ==========================================

@router.message(Command("Removeadmin"))
async def remove_admin_command(message: Message):

    if not await owner_only(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/Removeadmin USER_ID</code>",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Valid numeric Telegram ID enter karein."
        )
        return

    if user_id == OWNER_ID:
        await message.answer(
            "❌ Owner ko remove nahi kiya ja sakta."
        )
        return

    try:
        removed = await remove_admin(user_id)

        if removed:
            await message.answer(
                f"✅ Admin <code>{user_id}</code> remove ho gaya.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ye Admin database mein nahi mila."
            )

    except Exception:
        logger.exception("Remove admin failed")
        await message.answer(
            "❌ Admin remove karte waqt error aaya."
        )


# ==========================================
# ADMIN POWER / PERMISSIONS
# ==========================================

@router.message(Command("adminpower"))
async def admin_power_command(message: Message):

    if not await owner_only(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 4:
        permission_list = "\n".join(
            f"• <code>{key}</code> — {value}"
            for key, value in PERMISSIONS.items()
        )

        await message.answer(
            "<b>Admin Permission Management</b>\n\n"
            "Command format:\n"
            "<code>/adminpower USER_ID PERMISSION on/off</code>\n\n"
            "Example:\n"
            "<code>/adminpower 123456789 reports on</code>\n\n"
            "<b>Available permissions:</b>\n"
            f"{permission_list}",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Invalid Telegram ID."
        )
        return

    permission = parts[2].lower()
    value = parts[3].lower()

    if user_id == OWNER_ID:
        await message.answer(
            "❌ Owner ki permissions change nahi ki ja sakti."
        )
        return

    if permission not in PERMISSIONS:
        await message.answer(
            "❌ Invalid permission name."
        )
        return

    if value not in ("on", "off"):
        await message.answer(
            "❌ Permission value on ya off honi chahiye."
        )
        return

    try:
        admin = await get_admin(user_id)

        if not admin:
            await message.answer(
                "❌ Pehle is user ko /Addadmin se Admin banayein."
            )
            return

        allowed = value == "on"

        await set_admin_permission(
            admin["id"],
            permission,
            allowed
        )

        status = "ENABLED ✅" if allowed else "DISABLED ❌"

        await message.answer(
            "<b>Admin Permission Updated</b>\n\n"
            f"🆔 Admin: <code>{user_id}</code>\n"
            f"🔑 Permission: <code>{permission}</code>\n"
            f"📌 Status: {status}",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Admin permission update failed")
        await message.answer(
            "❌ Permission update karte waqt error aaya."
        )


# ==========================================
# ADMIN LIST
# ==========================================

@router.message(Command("adminlist"))
async def admin_list_command(message: Message):

    if not await permission_required(
        message,
        "admin_management"
    ):
        return

    try:
        admins = await get_all_admins()

        if not admins:
            await message.answer(
                "📋 Abhi koi Admin add nahi hai."
            )
            return

        text = "<b>📋 Admin List</b>\n\n"

        for index, admin in enumerate(admins, start=1):
            text += (
                f"{index}. "
                f"<code>{admin['user_id']}</code>\n"
            )

        await message.answer(
            text,
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Admin list failed")
        await message.answer(
            "❌ Admin list load nahi ho saki."
        )


# ==========================================
# ADMIN INFORMATION
# ==========================================

@router.message(Command("admininfo"))
async def admin_info_command(message: Message):

    if not await permission_required(
        message,
        "admin_management"
    ):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/admininfo USER_ID</code>",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Invalid Telegram ID."
        )
        return

    if user_id == OWNER_ID:
        await message.answer(
            "👑 Ye Bot Owner hai aur iske paas full permissions hain."
        )
        return

    try:
        admin = await get_admin(user_id)

        if not admin:
            await message.answer(
                "❌ Active Admin nahi mila."
            )
            return

        permissions = await get_admin_permissions(
            admin["id"]
        )

        text = (
            "<b>🛡 Admin Information</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            "<b>Permissions:</b>\n"
        )

        for key, description in PERMISSIONS.items():
            enabled = permissions.get(key, False)
            status = "✅" if enabled else "❌"

            text += f"\n{status} {description}"

        await message.answer(
            text,
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Admin information failed")
        await message.answer(
            "❌ Admin information load nahi ho saki."
        )


logger.info("Admin command module loaded.")
