# prices/services.py
import httpx
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.conf import settings
from datetime import datetime, date, timedelta

getcontext().prec = 12

BASE = settings.COINGECKO_BASE

async def fetch_price_for_date(asset_id: str, dt: date) -> Decimal:
    """
    Uses /coins/{id}/history endpoint with date format dd-mm-yyyy
    """
    url = f"{BASE}/coins/{asset_id}/history"
    params = {"date": dt.strftime("%d-%m-%Y"), "localization": "false"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    price = data.get("market_data", {}).get("current_price", {}).get("usd")
    if price is None:
        raise ValueError(f"Price not found for {asset_id} on {dt.isoformat()}")
    return Decimal(str(price))

async def fetch_current_price(asset_id: str) -> Decimal:
    url = f"{BASE}/simple/price"
    params = {"ids": asset_id, "vs_currencies": "usd"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    price = data.get(asset_id, {}).get("usd")
    if price is None:
        raise ValueError(f"Current price not found for {asset_id}")
    return Decimal(str(price))

def percent_change(new: Decimal, old: Decimal) -> Decimal:
    if old == 0:
        return Decimal("0")
    change = (new - old) / old * Decimal("100")
    # round to 6 decimal places
    return change.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

def direction_from(pc: Decimal) -> str:
    if pc > 0:
        return "increase"
    elif pc < 0:
        return "decrease"
    return "no_change"

async def get_comparison(asset_id: str, dt: date):
    """
    Returns dictionary with price_on_date, current_price, percent_change, direction
    """
    price_on_date = await fetch_price_for_date(asset_id, dt)
    current = await fetch_current_price(asset_id)
    pc = percent_change(current, price_on_date)
    return {
        "asset": asset_id,
        "date": dt.isoformat(),
        "price_on_date": str(price_on_date),
        "current_price": str(current),
        "percent_change": str(pc),
        "direction": direction_from(pc),
    }
