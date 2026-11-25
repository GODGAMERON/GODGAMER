import logging
import aiohttp

from config import SMM_API_KEY, SMM_API_URL

logger = logging.getLogger(name)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class SMMAPIError(Exception):
    """Raised when SMM API returns an error."""
    pass


async def api_request(payload: dict):
    """Send authenticated request to SMM panel."""

    data = {
        "key": SMM_API_KEY,
        **payload
    }

    try:
        async with aiohttp.ClientSession(
            timeout=TIMEOUT
        ) as session:

            async with session.post(
                SMM_API_URL,
                data=data
            ) as response:

                if response.status != 200:
                    raise SMMAPIError(
                        f"Panel HTTP error: {response.status}"
                    )

                try:
                    result = await response.json(
                        content_type=None
                    )
                except (ValueError, aiohttp.ContentTypeError):
                    raise SMMAPIError(
                        "Panel returned invalid JSON."
                    )

                if isinstance(result, dict) and result.get("error"):
                    raise SMMAPIError(
                        str(result["error"])
                    )

                return result

    except aiohttp.ClientError:
        logger.exception("SMM API connection failed")
        raise SMMAPIError("Unable to connect to SMM panel.")

    except TimeoutError:
        raise SMMAPIError("SMM panel request timed out.")


async def get_balance():
    """Fetch SMM panel account balance."""

    result = await api_request({
        "action": "balance"
    })

    if not isinstance(result, dict):
        raise SMMAPIError("Invalid balance response.")

    return {
        "balance": result.get("balance"),
        "currency": result.get("currency")
    }


async def add_order(service_id, link, quantity):
    """Submit a new SMM panel order."""

    if not str(service_id).strip():
        raise ValueError("Service ID is required.")

    if not str(link).strip():
        raise ValueError("Link is required.")

    if int(quantity) <= 0:
        raise ValueError("Quantity must be greater than zero.")

    result = await api_request({
        "action": "add",
        "service": str(service_id),
        "link": str(link),
        "quantity": int(quantity)
    })

    if not isinstance(result, dict):
        raise SMMAPIError("Invalid order response.")

    return result


async def get_order_status(order_id):
    """Check an existing order status."""

    if not str(order_id).strip():
        raise ValueError("Order ID is required.")

    result = await api_request({
        "action": "status",
        "order": str(order_id)
    })

    if not isinstance(result, dict):
        raise SMMAPIError("Invalid order status response.")

    return result


async def get_multiple_order_status(order_ids):
    """Check multiple order statuses."""

    if not order_ids:
        raise ValueError("Order IDs are required.")

    orders = ",".join(str(x) for x in order_ids)

    result = await api_request({
        "action": "status",
        "orders": orders
    })

    return result


async def get_services():
    """Fetch available panel services."""

    result = await api_request({
        "action": "services"
    })

    if not isinstance(result, list):
        raise SMMAPIError("Invalid services response.")

    return result
