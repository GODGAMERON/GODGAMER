
import aiohttp
import logging

logger = logging.getLogger(__name__)


class SMMApi:
    """
    Standard SMM Panel API v2 client.

    API actions:
    balance
    services
    add
    status
    cancel
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.strip()
        self.api_key = api_key.strip()

        if not self.api_url:
            raise ValueError("SMM API URL missing")

        if not self.api_key:
            raise ValueError("SMM API key missing")

        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _request(self, payload: dict):
        data = {
            "key": self.api_key,
            **payload
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
                        raise Exception(
                            f"Panel HTTP Error: {response.status}"
                        )

                    try:
                        import json
                        result = json.loads(response_text)
                    except Exception:
                        raise Exception(
                            "Panel ne invalid JSON response diya."
                        )

                    if isinstance(result, dict) and result.get("error"):
                        raise Exception(str(result["error"]))

                    return result

        except aiohttp.ClientError as error:
            logger.exception("SMM API connection error")
            raise Exception(
                f"Panel connection failed: {str(error)}"
            )

    async def get_balance(self):
        result = await self._request({
            "action": "balance"
        })

        if not isinstance(result, dict):
            raise Exception("Invalid balance response")

        return {
            "balance": result.get("balance"),
            "currency": result.get("currency")
        }

    async def get_services(self):
        result = await self._request({
            "action": "services"
        })

        if not isinstance(result, list):
            raise Exception("Invalid services response")

        return result

    async def add_order(
        self,
        service_id: int,
        link: str,
        quantity: int
    ):
        if int(service_id) <= 0:
            raise ValueError("Invalid service ID")

        if int(quantity) <= 0:
            raise ValueError("Quantity must be greater than zero")

        if not link:
            raise ValueError("Post link missing")

        result = await self._request({
            "action": "add",
            "service": int(service_id),
            "link": link,
            "quantity": int(quantity)
        })

        if not isinstance(result, dict):
            raise Exception("Invalid order response")

        if result.get("error"):
            raise Exception(str(result["error"]))

        order_id = result.get("order")

        if not order_id:
            raise Exception(
                f"Panel did not return order ID: {result}"
            )

        return {
            "order": str(order_id),
            "response": result
        }

    async def get_order_status(self, order_id: str):
        result = await self._request({
            "action": "status",
            "order": str(order_id)
        })

        if not isinstance(result, dict):
            raise Exception("Invalid order status response")

        if result.get("error"):
            raise Exception(str(result["error"]))

        return result

    async def cancel_order(self, order_id: str):
        result = await self._request({
            "action": "cancel",
            "orders": str(order_id)
        })

        if isinstance(result, dict) and result.get("error"):
            raise Exception(str(result["error"]))

        return result


# Simple helper functions

async def check_panel_connection(api_url: str, api_key: str):
    api = SMMApi(api_url, api_key)

    balance = await api.get_balance()

    return {
        "connected": True,
        "balance": balance.get("balance"),
        "currency": balance.get("currency")
    }


async def get_panel_services(api_url: str, api_key: str):
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
        quantity=quantity
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
