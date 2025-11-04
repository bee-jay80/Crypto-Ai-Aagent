# ai/services.py
import httpx
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, date
from dateutil.parser import parse as parse_date
from datetime import date as DateType, datetime
import asyncio

getcontext().prec = 18
import uuid

OKX_BASE = settings.OKX_BASE

# Common symbols that should always be available as a safe fallback
COMMON_SYMBOLS = {
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "XRP-USDT",
    "ADA-USDT",
    "DOGE-USDT",
    "DOT-USDT",
}

class HttpClientSingleton:
    """Create a fresh AsyncClient per-call.

    AsyncClient instances bind to the event loop they are created on. Reusing
    a single AsyncClient across multiple short-lived event loops (created by
    asgiref.async_to_sync) can cause "Event loop is closed" errors. To avoid
    that, return a new client for each call and use an async context manager to
    ensure it is properly closed.
    """

    @classmethod
    async def get_client(cls):
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        timeout = httpx.Timeout(30.0, connect=10.0, read=20.0, write=20.0)
        base = OKX_BASE if OKX_BASE else "https://www.okx.com"
        return httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
            verify=True,
            base_url=base
        )


# ✅ Fetch OKX trading symbols and cache
async def fetch_okx_symbols():
    key = "okx_symbols"
    cached = cache.get(key)
    if cached:
        # ensure common symbols are present in the cached set
        try:
            cached.update(COMMON_SYMBOLS)
        except Exception:
            # if cache stored a non-mutable type, replace it
            cached = set(cached) | COMMON_SYMBOLS
            cache.set(key, cached, 86400)
        return cached

    url = f"{OKX_BASE}/api/v5/public/instruments?instType=SPOT"

    try:
        async with await HttpClientSingleton.get_client() as client:
            r = await client.get(url)
            if r.status_code == 429:
                # rate limited — return fallback but don't cache bad data
                return COMMON_SYMBOLS

            if r.status_code != 200:
                return COMMON_SYMBOLS

            data = r.json()
            symbols = {item["instId"] for item in data.get("data", [])}
            if not symbols:
                return COMMON_SYMBOLS

            # Always include common symbols to be robust
            symbols.update(COMMON_SYMBOLS)
            cache.set(key, symbols, 3600)  # cache for 1 hour
            return symbols

    except Exception:
        return COMMON_SYMBOLS


async def is_valid_symbol(symbol: str):
    formatted = f"{symbol.upper()}-USDT"
    # Quick allow-list for known top symbols
    if formatted in COMMON_SYMBOLS:
        return True

    symbols = await fetch_okx_symbols()
    return formatted in symbols


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

    for _ in range(3):
        try:
            async with await HttpClientSingleton.get_client() as client:
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

async def okx_price_at_date(symbol: str, dt):
    """
    dt can be a datetime.date object or a string.
    """
    # Convert string to date if needed
    if isinstance(dt, str):
        try:
            dt = parse_date(dt).date()
        except Exception:
            raise ValueError(f"Invalid date format: {dt}")
    elif not isinstance(dt, DateType):
        raise ValueError(f"dt must be a date object or string, got {type(dt)}")

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
    async with await HttpClientSingleton.get_client() as client:
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


getcontext().prec = 18

def build_task_response(asset: str, old_price: Decimal, new_price: Decimal, dt: date):
    """
    Builds Telex-compliant JSON-RPC response structure
    """
    task_id = str(uuid.uuid4())
    msg_id_user = str(uuid.uuid4())
    msg_id_agent = str(uuid.uuid4())

    pc = percent_change(new_price, old_price)
    dir_text = direction(pc)

    # Human-readable text
    text_msg = (
        f"Asset: {asset.upper()}\n"
        f"Date checked: {dt}\n"
        f"Price on date: ${old_price}\n"
        f"Current price: ${new_price}\n"
        f"Percentage change: {pc}%\n"
        f"Direction: {dir_text}\n"
    )

    # Structured artifact (optional, can be used by agent programmatically)
    artifact_data = {
        "asset": asset.upper(),
        "date": str(dt),
        "price_on_date": str(old_price),
        "current_price": str(new_price),
        "percent_change": str(pc),
        "direction": dir_text
    }

    return {
        "jsonrpc": "2.0",
        "id": task_id,
        "result": {
            "id": task_id,
            "contextId": f"crypto-{asset.lower()}",
            "status": {
                "state": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "message": {
                    "kind": "message",
                    "role": "agent",
                    "parts": [
                        {"kind": "text", "text": text_msg}
                    ],
                    "messageId": msg_id_agent,
                    "taskId": task_id
                }
            },
            "artifacts": [
                {
                    "artifactId": str(uuid.uuid4()),
                    "name": "comparison_data",
                    "parts": [
                        {"kind": "text", "text": str(artifact_data)}
                    ]
                }
            ],
            "history": [
                {
                    "kind": "message",
                    "role": "user",
                    "parts": [{"kind": "text", "text": f"Check {asset} price {dt}"}],
                    "messageId": msg_id_user,
                    "taskId": task_id
                },
                {
                    "kind": "message",
                    "role": "agent",
                    "parts": [{"kind": "text", "text": text_msg}],
                    "messageId": msg_id_agent,
                    "taskId": task_id
                }
            ],
            "kind": "task"
        },
        "error": None
    }

async def get_comparison(asset: str, dt: date):
    old_price = await okx_price_at_date(asset, dt)
    new_price = await okx_price(asset)
    return build_task_response(asset, old_price, new_price, dt)
