import aiohttp
import asyncio

JUPITER_PRICE_URL = "https://price.jup.ag/v4/price"

async def get_price(ca):
    params = {
        "ids": ca,
        "vsToken": "So11111111111111111111111111111111111111112"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JUPITER_PRICE_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price_data = data.get("data", {}).get(ca)
                    if price_data:
                        return price_data.get("price", None)
    except Exception as e:
        print(f"Error get price: {e}")
    return None
