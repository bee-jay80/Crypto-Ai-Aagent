import httpx
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, date
import asyncio

getcontext().prec = 18

BINANCE = settings.BINANCE_BASE

class HttpClientSingleton:
    _client = None

    @classmethod
    async def get_client(cls):
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=10.0)
        return cls._client

async def fetch_binance_trading_pairs():
    key = "binance_symbols"
    cached = cache.get(key)
    if cached:
        return cached

    client = await HttpClientSingleton.get_client()
    url = f"{BINANCE}/api/v3/exchangeInfo"
    try:
        r = await client.get(url)
        data = r.json()
        symbols = {s["symbol"] for s in data["symbols"]}
        cache.set(key, symbols, 86400)  # cache 24hrs
        return symbols
    except Exception:
        return set()

async def is_valid_binance_symbol(symbol: str):
    symbols = await fetch_binance_trading_pairs()
    return symbol.upper() in symbols

async def binance_price(symbol: str):
    if not await is_valid_binance_symbol(symbol):
        raise ValueError(f"Sorry {symbol} is not listed in my database")

    key = f"price:{symbol}"
    cached = cache.get(key)
    if cached:
        return Decimal(str(cached))

    client = await HttpClientSingleton.get_client()
    url = f"{BINANCE}/api/v3/ticker/price"
    params = {"symbol": symbol.upper()}

    for _ in range(3):
        r = await client.get(url, params=params)
        if r.status_code == 200:
            price = r.json()["price"]
            cache.set(key, price, 10)
            return Decimal(price)

        if r.status_code == 429:
            await asyncio.sleep(0.3)
            continue

    raise ValueError("Unable to fetch price — try another coin")

async def binance_price_at_date(symbol: str, dt: date):
    if not await is_valid_binance_symbol(symbol):
        raise ValueError(f"Sorry {symbol} is not listed in my database")

    key = f"hist:{symbol}:{dt}"
    cached = cache.get(key)
    if cached:
        return Decimal(str(cached))

    start = int(datetime(dt.year, dt.month, dt.day).timestamp() * 1000)
    end = start + 86400000

    url = f"{BINANCE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": "1d", "startTime": start, "endTime": end}

    client = await HttpClientSingleton.get_client()
    r = await client.get(url, params=params)

    if r.status_code != 200:
        raise ValueError("No history for selected date")

    data = r.json()
    if not data:
        raise ValueError("No historic price data")

    price = data[0][4]
    cache.set(key, price, 3600)
    return Decimal(price)

def percent_change(new: Decimal, old: Decimal) -> Decimal:
    if old == 0:
        return Decimal("0")
    return ((new - old) / old * 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def direction(pc: Decimal):
    if pc > 0: return "increase"
    if pc < 0: return "decrease"
    return "no_change"

async def get_comparison(asset: str, dt: date):
    symbol = asset.upper() + "USDT"

    old_price = await binance_price_at_date(symbol, dt)
    new_price = await binance_price(symbol)
    pc = percent_change(new_price, old_price)

    return {
        "asset": asset,
        "date": dt.isoformat(),
        "price_on_date": str(old_price),
        "current_price": str(new_price),
        "percent_change": str(pc),
        "direction": direction(pc)
    }