
import logging

from config import OWNER_ID
from database import (
    get_admin,
    get_admin_permissions,
)

logger = logging.getLogger(__name__)


# ==========================================
# AVAILABLE PERMISSIONS
# ==========================================

PERMISSIONS = {
    "channel_management": "Channel add, remove aur manage karna",
    "quantity_management": "Channel quantity change karna",
    "reports": "Reports dekhna",
    "panel_management": "SMM panels add aur remove karna",
    "service_management": "Service IDs manage karna",
    "order_management": "Orders manage karna",
    "admin_management": "Admins aur unki permissions manage karna",
    "automation_management": "Automatic ordering start aur stop karna",
    "system_management": "System status aur settings manage karna",
}


# ==========================================
# OWNER CHECK
# ==========================================

def is_owner(user_id: int) -> bool:
    """Check whether a Telegram user is the bot Owner."""

    return user_id == OWNER_ID


# ==========================================
# ADMIN CHECK
# ==========================================

async def is_admin(user_id: int) -> bool:
    """Check whether a user is an active Admin."""

    if is_owner(user_id):
        return True

    admin = await get_admin(user_id)

    return admin is not None


# ==========================================
# GET USER PERMISSIONS
# ==========================================

async def get_user_permissions(user_id: int) -> dict:
    """Return all permissions available to a user."""

    if is_owner(user_id):
        return {
            permission: True
            for permission in PERMISSIONS
        }

    admin = await get_admin(user_id)

    if not admin:
        return {}

    permissions = await get_admin_permissions(admin["id"])

    return {
        permission: permissions.get(permission, False)
        for permission in PERMISSIONS
    }


# ==========================================
# CHECK SPECIFIC PERMISSION
# ==========================================

async def has_permission(
    user_id: int,
    permission: str
) -> bool:
    """Check whether a user has a particular permission."""

    if permission not in PERMISSIONS:
        logger.warning(
            "Unknown permission requested: %s",
            permission
        )
        return False

    # Owner always has full access.
    if is_owner(user_id):
        return True

    admin = await get_admin(user_id)

    if not admin:
        return False

    permissions = await get_admin_permissions(admin["id"])

    return permissions.get(permission, False) is True


# ==========================================
# CHECK MULTIPLE PERMISSIONS
# ==========================================

async def has_any_permission(
    user_id: int,
    permissions: list
) -> bool:
    """Return True if the user has at least one permission."""

    for permission in permissions:
        if await has_permission(user_id, permission):
            return True

    return False


async def has_all_permissions(
    user_id: int,
    permissions: list
) -> bool:
    """Return True only if the user has every permission."""

    for permission in permissions:
        if not await has_permission(user_id, permission):
            return False

    return True


# ==========================================
# PERMISSION DETAILS
# ==========================================

def get_available_permissions() -> dict:
    """Return the available permission names and descriptions."""

    return PERMISSIONS.copy()


# ==========================================
# USER ACCESS INFORMATION
# ==========================================

async def get_access_info(user_id: int) -> dict:
    """Return user role and permission information."""

    if is_owner(user_id):
        return {
            "user_id": user_id,
            "role": "Owner",
            "is_owner": True,
            "is_admin": True,
            "permissions": await get_user_permissions(user_id),
        }

    admin = await get_admin(user_id)

    if not admin:
        return {
            "user_id": user_id,
            "role": "User",
            "is_owner": False,
            "is_admin": False,
            "permissions": {},
        }

    return {
        "user_id": user_id,
        "role": "Admin",
        "is_owner": False,
        "is_admin": True,
        "permissions": await get_user_permissions(user_id),
    }


# ==========================================
# PERMISSION MESSAGE
# ==========================================

def permission_denied_message() -> str:
    """Return a standard access-denied message."""

    return (
        "❌ <b>Permission Denied!</b>\n\n"
        "Aapko is command ko use karne ki permission nahi hai.\n"
        "Owner se permission lene ke liye contact karein."
    )


logger.info("Admin permissions module loaded.")
