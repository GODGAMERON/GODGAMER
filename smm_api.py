
import asyncio
import logging

import aiohttp


logger = logging.getLogger(__name__)


class SMMAPIError(Exception):
    """Raised when an SMM panel API request fails."""
    pass


class SMMApi:
    """
    Standard SMM Panel API v2 client.

    Supported actions:
    - balance
    - services
    - add
    - status
    - cancel
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = str(api_url or "").strip()
        self.api_key = str(api_key or "").strip()

        if not self.api_url:
            raise ValueError("SMM API URL missing")

        if not self.api_key:
            raise ValueError("SMM API key missing")

        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _request(self, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("Invalid API request payload")

        data = {
            **payload,
            "key": self.api_key,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout
            ) as session:

                async with session.post(
                    self.api_url,
                    data=data
                ) as response:

                    response_text = await response.text()

                    if response.status != 200:
                        raise SMMAPIError(
                            f"Panel HTTP error: {response.status}"
                        )

                    try:
                        import json
                        result = json.loads(response_text)
                    except (ValueError, TypeError):
                        raise SMMAPIError(
                            "Panel returned invalid JSON response."
                        )

                    if isinstance(result, dict) and result.get("error"):
                        raise SMMAPIError(
                            str(result["error"])
                        )

                    return result

        except asyncio.TimeoutError:
            logger.error("SMM panel request timed out")
            raise SMMAPIError(
                "SMM panel request timed out."
            )

        except aiohttp.ClientError as error:
            logger.exception("SMM panel connection failed")
            raise SMMAPIError(
                f"Panel connection failed: {error}"
            )

    async def get_balance(self):
        result = await self._request({
            "action": "balance"
        })

        if not isinstance(result, dict):
            raise SMMAPIError(
                "Invalid panel balance response."
            )

        return {
            "balance": result.get("balance"),
            "currency": result.get("currency"),
        }

    async def get_services(self):
        result = await self._request({
            "action": "services"
        })

        if not isinstance(result, list):
            raise SMMAPIError(
                "Invalid panel services response."
            )

        return result

    async def add_order(
        self,
        service_id: int,
        link: str,
        quantity: int
    ):
        try:
            service_id = int(service_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValueError(
                "Service ID and quantity must be numbers."
            )

        link = str(link or "").strip()

        if service_id <= 0:
            raise ValueError("Invalid service ID.")

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if not link:
            raise ValueError("Post link missing.")

        result = await self._request({
            "action": "add",
            "service": service_id,
            "link": link,
            "quantity": quantity,
        })

        if not isinstance(result, dict):
            raise SMMAPIError(
                "Invalid panel order response."
            )

        order_id = result.get("order")

        if not order_id:
            raise SMMAPIError(
                f"Panel did not return order ID: {result}"
            )

        return {
            "order": str(order_id),
            "response": result,
        }

    async def get_order_status(self, order_id: str):
        order_id = str(order_id or "").strip()

        if not order_id:
            raise ValueError("Order ID is required.")

        result = await self._request({
            "action": "status",
            "order": order_id,
        })

        if not isinstance(result, dict):
            raise SMMAPIError(
                "Invalid order status response."
            )

        return result

    async def cancel_order(self, order_id: str):
        order_id = str(order_id or "").strip()

        if not order_id:
            raise ValueError("Order ID is required.")

        result = await self._request({
            "action": "cancel",
            "orders": order_id,
        })

        return result


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

async def check_panel_connection(
    api_url: str,
    api_key: str
):
    api = SMMApi(api_url, api_key)

    balance = await api.get_balance()

    return {
        "connected": True,
        "balance": balance.get("balance"),
        "currency": balance.get("currency"),
    }


async def get_panel_services(
    api_url: str,
    api_key: str
):
    api = SMMApi(api_url, api_key)

    return await api.get_services()


async def place_panel_order(
    api_url: str,
    api_key: str,
    service_id: int,
    link: str,
    quantity: int
):
    api = SMMApi(api_url, api_key)

    return await api.add_order(
        service_id=service_id,
        link=link,
        quantity=quantity,
    )


async def check_panel_order(
    api_url: str,
    api_key: str,
    order_id: str
):
    api = SMMApi(api_url, api_key)

    return await api.get_order_status(order_id)


async def cancel_panel_order(
    api_url: str,
    api_key: str,
    order_id: str
):
    api = SMMApi(api_url, api_key)

    return await api.cancel_order(order_id)

