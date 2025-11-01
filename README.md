# DeltaAI — Crypto Delta API (Django + DRF + HF AI Proxy)

DeltaAI parses natural-language requests, extracts a crypto asset and date via a free HuggingFace model (server-side), fetches the requested historical price from CoinGecko, fetches the current price, and returns the percent change and direction.

## Quick start (local, dev)

1. Clone repo
2. Create `.env` from `.env.example` and fill HF_API_TOKEN
3. Create virtualenv and install:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
