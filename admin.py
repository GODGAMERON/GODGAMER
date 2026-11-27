import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID
from database import (
    add_admin, remove_admin, get_admin, get_all_admins,
    set_admin_permission, get_admin_permissions,
)
from admin_permissions import PERMISSIONS, is_owner, has_permission

router = Router()
logger = logging.getLogger(__name__)


def owner_only(message: Message) -> bool:
    return bool(message.from_user and is_owner(message.from_user.id))


async def check_owner(message: Message) -> bool:
    if owner_only(message):
        return True
    await message.answer("⛔ Sirf Owner is command ko use kar sakta hai.")
    return False


@router.message(Command("myid"))
async def my_id(message: Message):
    if message.from_user:
        await message.answer(f"Your Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.message(Command("admin"))
async def admin_help(message: Message):
    await message.answer(
        "<b>ADMIN COMMANDS</b>\n\n"
        "/addadmin USER_ID - Admin add\n"
        "/removeadmin USER_ID - Admin remove\n"
        "/adminlist - Admin list\n"
        "/admininfo USER_ID - Admin permissions\n"
        "/adminpower USER_ID PERMISSION on/off\n\n"
        "Permissions: " + ", ".join(PERMISSIONS),
        parse_mode="HTML"
    )


@router.message(Command("addadmin", "Addadmin"))
async def add_admin_command(message: Message):
    if not await check_owner(message): return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Format: /addadmin USER_ID"); return
    try:
        user_id = int(parts[1])
        if user_id <= 0 or user_id == OWNER_ID: raise ValueError
        row = await add_admin(user_id, message.from_user.id)
        await message.answer("✅ Admin add/reactivate ho gaya." if row else "❌ Admin add nahi hua.")
    except ValueError:
        await message.answer("❌ Valid numeric USER_ID enter karein.")
    except Exception:
        logger.exception("Add admin failed"); await message.answer("❌ Admin add karte waqt database error.")


@router.message(Command("removeadmin", "Removeadmin"))
async def remove_admin_command(message: Message):
    if not await check_owner(message): return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Format: /removeadmin USER_ID"); return
    try:
        user_id = int(parts[1])
        removed = await remove_admin(user_id)
        await message.answer("✅ Admin deactivate kar diya." if removed else "❌ Active admin nahi mila.")
    except ValueError:
        await message.answer("❌ USER_ID number hona chahiye.")
    except Exception:
        logger.exception("Remove admin failed"); await message.answer("❌ Database error.")


@router.message(Command("adminlist"))
async def admin_list(message: Message):
    if not await check_owner(message): return
    try:
        admins = await get_all_admins()
        if not admins:
            await message.answer("Abhi koi active admin nahi hai."); return
        lines = ["<b>ACTIVE ADMINS</b>"]
        for admin in admins:
            lines.append(f"\nID: <code>{admin['user_id']}</code> | DB ID: {admin['id']}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("Admin list failed"); await message.answer("❌ Admin list load nahi hui.")


@router.message(Command("admininfo"))
async def admin_info(message: Message):
    if not await check_owner(message): return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Format: /admininfo USER_ID"); return
    try:
        admin = await get_admin(int(parts[1]))
        if not admin:
            await message.answer("❌ Active admin nahi mila."); return
        permissions = await get_admin_permissions(admin['id'])
        lines = [f"<b>ADMIN {admin['user_id']}</b>"]
        for key, desc in PERMISSIONS.items():
            lines.append(f"{'✅' if permissions.get(key, False) else '❌'} {key} — {desc}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except ValueError:
        await message.answer("❌ USER_ID number hona chahiye.")
    except Exception:
        logger.exception("Admin info failed"); await message.answer("❌ Admin info load nahi hui.")


@router.message(Command("adminpower"))
async def admin_power(message: Message):
    if not await check_owner(message): return
    parts = (message.text or "").split()
    if len(parts) != 4:
        await message.answer("Format: /adminpower USER_ID PERMISSION on/off"); return
    try:
        user_id = int(parts[1]); permission = parts[2].lower(); value = parts[3].lower()
        if permission not in PERMISSIONS or value not in ("on", "off", "true", "false", "1", "0"):
            await message.answer("❌ Permission ya on/off value galat hai."); return
        admin = await get_admin(user_id)
        if not admin:
            await message.answer("❌ Active admin nahi mila."); return
        allowed = value in ("on", "true", "1")
        await set_admin_permission(admin['id'], permission, allowed)
        await message.answer(f"✅ {permission}: {'ON' if allowed else 'OFF'} for {user_id}")
    except ValueError:
        await message.answer("❌ USER_ID number hona chahiye.")
    except Exception:
        logger.exception("Admin permission update failed"); await message.answer("❌ Permission update nahi hui.")
