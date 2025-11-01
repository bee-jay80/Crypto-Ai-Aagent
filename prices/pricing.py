import requests
from django.core.cache import cache

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

def get_cached_price(symbol: str):
    key = f"price:{symbol.lower()}"
    cached_price = cache.get(key)

    if cached_price:
        return cached_price, "cached"

    response = requests.get(COINGECKO_URL, params={
        "ids": symbol,
        "vs_currencies": "usd"
    })

    data = response.json().get(symbol)
    price = data["usd"]

    # Cache for 5 minutes (avoid rate limit)
    cache.set(key, price, timeout=300)

    return price, "api"
