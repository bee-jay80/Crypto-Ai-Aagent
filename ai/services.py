import json
import httpx
from openai import OpenAI
from django.conf import settings

from datetime import datetime, timedelta
import dateparser

def normalize_date(date_text: str):
    if not date_text:
        return None
    
    # parse natural language (yesterday, 3 days ago, one week ago)
    dt = dateparser.parse(date_text)

    if not dt:
        return None

    return dt.strftime("%Y-%m-%d")

HF_TOKEN = getattr(settings, "HF_API_TOKEN", None)

if not HF_TOKEN:
    raise RuntimeError("HF_API_TOKEN missing in env")

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

SYSTEM_PROMPT = """
You are a crypto command parser.
Your job:
- Detect the requested crypto asset
- Extract the symbol
- Convert any human date into YYYY-MM-DD format (ISO)
- If date is unclear, guess intelligently (ex: "3 days ago")
- If user gives an invalid date like "2025-31-12", fix it or return the closest valid date
- Respond with ONLY JSON, no text around it.
- Make sure to start counting from todays date (current date)

Examples:

User: "check btc yesterday"
Response:
{"asset":"bitcoin","symbol":"BTC","date":"yesterday"}

User: "ethereum price three days ago"
Response:
{"asset":"ethereum","symbol":"ETH","date":"3 days ago"}

User: "solana on 2025-12-31"
Response:
{"asset":"solana","symbol":"SOL","date":"2025-12-31"}

User: "compare eth price one week ago"
Response:
{"asset":"ethereum","symbol":"ETH","date":"1 week ago"}

Also give the right symbols and asset  for the right coins even the once not mentioned here
For a more than one word asset seperate by hyphine (-) e.g pi-network but asset like pink sale that is pinksale should not be with an hyphine(-)

Always try to format the asset even if the user passes a wrong spelling get the original asset from the matching words AND MAKE USE OF KEYWORDS THAT SHOULD BE A COIN e.g Hamaster coin= Hamster Kombat

TODAY is current date.
Return ONLY valid JSON like:
{"asset":"bitcoin","symbol":"BTC","date":"todays date"}

NOTE: do not actually return 2025-month in number-day in number but return it with the month as a number and also the date as a number also the updated year
"""


async def parse_text(text: str) -> dict:
    try:
        completion = client.chat.completions.create(
            # model="katanemo/Arch-Router-1.5B:hf-inference",
            # model="openai/gpt-oss-20b:groq",
            model="zai-org/GLM-4.6:novita",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=120,
        )

        raw = completion.choices[0].message.content.strip()

        try:
            data = json.loads(raw)
        except Exception:
            return {
                "error": "MODEL_RETURNED_NON_JSON",
                "raw": raw
            }

        parsed_date = normalize_date(data.get("date"))
        return {
            "asset": data.get("asset"),
            "symbol": data.get("symbol"),
            "date": parsed_date,
            "raw": raw
        }

    except Exception as e:
        return {"error": "PARSE_FAILED", "details": str(e)}


SYSTEM_PROMPT2 = """
You are a professional cryptocurrency analysis assistant.

Your task:
- Receive data about a cryptocurrency including: asset name, symbol, date, and price.
- Provide a clear, concise, and insightful analysis.
- The tone should be professional, informative, simple, and beginner-friendly.

Your response must include:
1. A short summary of the asset and what it is known for
2. The date and price analyzed
3. Whether the price is rising, falling, or stagnant (based only on the data given — do NOT make up data)
4. Market sentiment words like: bullish, bearish, neutral (based only on the trend)
5. A caution note reminding users that crypto prices are volatile

Rules:
- Do not hallucinate price history or future predictions.
- Do not promise profits or financial returns.
- If data is missing or unclear, say it clearly.
- Never provide financial advice. Instead, give market insights and trends.
- Do not mention that you are an AI model.

Example output style (not literal):


Asset: Bitcoin (BTC)
Date checked: 2025-01-05
Price on date: $42,500
Current price: $45,300
Percentage change: 
Direction: "Increase"

Bitcoin remains the leading cryptocurrency known for secure, decentralized payments.
Based on the latest data, BTC appears to be trending slightly upward, suggesting moderate bullish sentiment.

As always, crypto markets are highly volatile — this is not financial advice, but a snapshot of current conditions.
"""
async def response_text(data: dict) -> dict:
    try:
        # data already is a dict, no need to json.loads
        formatted_user_input = json.dumps(data, ensure_ascii=False)

        completion = client.chat.completions.create(
            model="zai-org/GLM-4.6:novita",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT2},
                {"role": "user", "content": formatted_user_input}
            ],
            max_tokens=300,
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        return {"error": "RESPONSE_FAILED", "details": str(e)}
