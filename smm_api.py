
import logging

import aiohttp

from config import SMM_API_KEY, SMM_API_URL

logger = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class SMMAPIError(Exception):
    """Raised when the SMM API returns an error."""


async def api_request(params):
    """
    Send a request to the SMM panel API.
    Uses the standard SMM API form-data format.
    """

    payload = {
        "key": SMM_API_KEY,
        **params
    }

    try:
        async with aiohttp.ClientSession(
            timeout=TIMEOUT
        ) as session:

            async with session.post(
                SMM_API_URL,
                data=payload
            ) as response:

                if response.status != 200:
                    raise SMMAPIError(
                        f"SMM API HTTP error: {response.status}"
                    )

                try:
                    data = await response.json(
                        content_type=None
                    )
                except (ValueError, aiohttp.ContentTypeError):
                    raise SMMAPIError(
                        "SMM API returned an invalid response."
                    )

                if isinstance(data, dict) and data.get("error"):
                    raise SMMAPIError(str(data["error"]))

                return data

    except aiohttp.ClientError as error:
        logger.error("SMM API connection failed: %s", error)
        raise SMMAPIError(
            "Could not connect to the SMM panel."
        ) from error

    except TimeoutError as error:
        logger.error("SMM API request timed out")
        raise SMMAPIError(
            "SMM API request timed out."
        ) from error


async def get_balance():
    """Get the SMM panel account balance."""

    return await api_request({
        "action": "balance"
    })


async def get_services():
    """Get all available SMM services."""

    return await api_request({
        "action": "services"
    })


async def create_order(
    service_id,
    link,
    quantity
):
    """Place a new SMM order."""

    if int(quantity) <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if not link or not str(link).startswith(
        ("https://", "http://")
    ):
        raise ValueError("A valid link is required.")

    return await api_request({
        "action": "add",
        "service": str(service_id),
        "link": str(link),
        "quantity": str(int(quantity))
    })


async def get_order_status(order_id):
    """Check the status of one order."""

    return await api_request({
        "action": "status",
        "order": str(order_id)
    })


async def get_multiple_order_status(order_ids):
    """Check the status of multiple orders."""

    if not order_ids:
        raise ValueError("At least one order ID is required.")

    ids = [
        str(order_id)
        for order_id in order_ids
    ]

    return await api_request({
        "action": "status",
        "orders": ",".join(ids)
    })
