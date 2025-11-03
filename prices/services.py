# ai/services.py
import httpx
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, date
import asyncio

getcontext().prec = 18

OKX_BASE = settings.OKX_BASE

class HttpClientSingleton:
    _client = None

    @classmethod
    async def get_client(cls):
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=10.0)
        return cls._client


# ✅ Fetch OKX trading symbols and cache
async def fetch_okx_symbols():
    key = "okx_symbols"
    cached = cache.get(key)
    if cached:
        return cached

    client = await HttpClientSingleton.get_client()
    url = f"{OKX_BASE}/api/v5/public/instruments?instType=SPOT"

    try:
        r = await client.get(url)
        if r.status_code != 200:
            return set()

        data = r.json()
        symbols = {item["instId"] for item in data.get("data", [])}
        cache.set(key, symbols, 86400)  # 24hrs
        return symbols

    except Exception:
        return set()


async def is_valid_symbol(symbol: str):
    symbols = await fetch_okx_symbols()
    return f"{symbol.upper()}-USDT" in symbols


# ✅ Current price from OKX
async def okx_price(symbol: str):
    full_symbol = f"{symbol.upper()}-USDT"

    if not await is_valid_symbol(symbol):
        raise ValueError(f"❌ '{symbol}' not found on OKX. Please try another coin.")

    key = f"price:{full_symbol}"
    cached = cache.get(key)
    if cached:
        return Decimal(str(cached))

    url = f"{OKX_BASE}/api/v5/market/ticker?instId={full_symbol}"
    client = await HttpClientSingleton.get_client()

    for _ in range(3):
        try:
            r = await client.get(url)
            if r.status_code == 429:  # Rate limit
                await asyncio.sleep(0.3)
                continue

            if r.status_code != 200:
                raise ValueError("Unable to fetch current price — please try again shortly.")

            result = r.json()
            last = result["data"][0]["last"]
            cache.set(key, last, 10)
            return Decimal(last)

        except Exception:
            await asyncio.sleep(0.2)

    raise ValueError("⚠️ Network error fetching price — try again.")


# ✅ Historical price
async def okx_price_at_date(symbol: str, dt: date):
    full_symbol = f"{symbol.upper()}-USDT"

    if not await is_valid_symbol(symbol):
        raise ValueError(f"❌ '{symbol}' not found on OKX. Please try another coin.")

    key = f"hist:{full_symbol}:{dt}"
    cached = cache.get(key)
    if cached:
        return Decimal(str(cached))

    start = int(datetime(dt.year, dt.month, dt.day).timestamp() * 1000)

    url = (
        f"{OKX_BASE}/api/v5/market/history-candles?"
        f"instId={full_symbol}&bar=1D&limit=1&after={start}"
    )
    client = await HttpClientSingleton.get_client()

    r = await client.get(url)

    if r.status_code != 200:
        raise ValueError("⚠️ Unable to fetch historical price — try another date.")

    data = r.json().get("data", [])
    if not data:
        raise ValueError("⚠️ No data for that date.")

    close = data[0][4]
    cache.set(key, close, 3600)
    return Decimal(close)


def percent_change(new: Decimal, old: Decimal) -> Decimal:
    if old == 0:
        return Decimal("0")
    return ((new - old) / old * 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def direction(pc: Decimal):
    if pc > 0: return "increase"
    if pc < 0: return "decrease"
    return "no_change"


async def get_comparison(asset: str, dt: date):
    old_price = await okx_price_at_date(asset, dt)
    new_price = await okx_price(asset)
    pc = percent_change(new_price, old_price)

    return {
        "asset": asset,
        "date": dt.isoformat(),
        "price_on_date": str(old_price),
        "current_price": str(new_price),
        "percent_change": str(pc),
        "direction": direction(pc)
    }