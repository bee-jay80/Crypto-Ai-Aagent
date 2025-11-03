# 🤖 AI Crypto Price Agent — Django + OKX + Telex A2A

An AI-powered cryptocurrency intelligence agent built with **Django**, **GPT-5**, and **OKX API**, fully integrated with **Telex A2A protocol**.  
The bot answers natural crypto queries such as:

> "What's Bitcoin's price right now?"  
> "Check ETH price yesterday"  
> "What is the 7-day trend for BTC?"

It returns **real-time market prices** + **AI-analysis** in Telex-formatted response blocks.

---

## 🚀 Features

| Capability | Description |
|---|---|
✅ Live crypto prices from **OKX API**  
✅ Historical price lookups (yesterday / date-range)  
✅ GPT-powered analysis (trend + sentiment)  
✅ Fully working **Telex A2A agent endpoint**  
✅ Django REST API backend  
✅ Local / Redis caching support  
✅ Environment-driven config (`.env`)  

---

## 🧠 Tech Stack

| Layer | Tools |
|---|---|
Backend Framework | Django + DRF  
AI Engine | GPT-5 / HuggingFace Router  
Crypto Market Data | **OKX REST API**  
Agent Protocol | **Telex A2A JSON-RPC**  
Cache | LocMem / Redis (optional)  
Task Queue | Celery (optional)  
Config | python-dotenv  

---

## 📦 Installation

```bash
git clone https://github.com/your-username/ai-crypto-agent.git
cd ai-crypto-agent
Create & Activate Virtual Env
python -m venv venv
source venv/bin/activate     # macOS / Linux
venv\Scripts\activate        # Windows

Install Dependencies
pip install -r requirements.txt

⚙️ Environment Variables

Create .env file:

SECRET_KEY=your-django-secret
DEBUG=True

# AI Endpoint
HF_API_URL=https://router.huggingface.co/hf-inference/models/flair/ner-english
HF_API_TOKEN=your_huggingface_token

# Crypto API
OKX_BASE=https://www.okx.com

# Optional Redis / Celery
REDIS_URL=redis://redis:6379/0

▶️ Run the Server
python manage.py migrate
python manage.py runserver

🔗 Telex A2A Endpoint
POST /api/v1/nlp/parse/
Content-Type: application/json

✅ Example Request
{
  "jsonrpc": "2.0",
  "id": "1234",
  "params": {
    "message": {
      "kind": "message",
      "parts": [
        { "kind": "text", "text": "Check BTC yesterday" }
      ]
    }
  }
}

✅ Example Response (Correct Telex Format)
{
  "status": "completed",
  "message": {
    "role": "agent",
    "parts": [
      {
        "kind": "text",
        "text": "BTC Yesterday: $110,117 → Today: $105,584 (-4.12% 🟥 bearish trend)"
      }
    ]
  }
}
