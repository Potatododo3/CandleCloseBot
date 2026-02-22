# Crypto Candle Alert Bot

Telegram bot that monitors CoinGecko candle **closes** and sends alerts when the close price crosses a target.

## Features
- Monitors candle close prices (not intra-candle)
- Supports 1h, 4h, 1d timeframes with precise UTC alignment
- Deduplicates alerts per candle via `last_triggered_candle`
- CoinGecko free OHLC API — no API key required
- Single-user with hardcoded Telegram user ID
- SQLite storage, zero external dependencies beyond pip packages

## Project Structure
```
bot.py           # Telegram bot, command handlers, entry point
config.py        # All configuration and constants
database.py      # SQLite CRUD operations
price_service.py # CoinGecko OHLC fetch with retry logic
scheduler.py     # APScheduler: precise candle close timing + rule evaluation
requirements.txt
Procfile         # Railway worker process
```

---

## Local Setup

### 1. Get your Bot Token
Message `@BotFather` on Telegram → /newbot → copy the token.

### 2. Get your Telegram User ID
Message `@userinfobot` on Telegram → copy the ID number.

### 3. Install & run
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="123456:ABCdef..."
export TELEGRAM_USER_ID="987654321"
python bot.py
```

---

## Deploy to Railway (Free Tier)

### Step 1 — Create account
Sign up at https://railway.app (free, no credit card needed for hobby plan).

### Step 2 — Push code to GitHub
```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 3 — Create Railway project
- Railway dashboard → New Project → Deploy from GitHub repo → select your repo

### Step 4 — Set environment variables
In Railway: Project → Variables → Add:
- `TELEGRAM_TOKEN` = your bot token
- `TELEGRAM_USER_ID` = your Telegram user ID

### Step 5 — Deploy
Railway auto-detects `Procfile` and runs the `worker` process. Watch logs in Railway dashboard → Logs.

### Step 6 — Verify
Send `/help` to your bot in Telegram. You should get a response.

### Notes on Railway free tier
- SQLite is on the ephemeral filesystem — it resets on redeploy. Re-add rules after deploys.
- For persistence: use Railway Postgres addon or commit a snapshot before redeploying.
- Bot runs as a **worker** (no HTTP port), so it stays alive unlike web services.

---

## Commands

| Command | Description |
|---|---|
| `/watch bitcoin 4h below 60000` | Alert when BTC 4h candle closes below $60,000 |
| `/watch ethereum 1h above 3500` | Alert when ETH 1h candle closes above $3,500 |
| `/watch solana 1d above 200` | Alert when SOL daily candle closes above $200 |
| `/unwatch 3` | Remove rule with ID 3 |
| `/list` | Show all active rules with next check time |
| `/help` | Show this help |

## Candle Close Schedule (UTC)
| Timeframe | Close times |
|---|---|
| 1h | Every full hour |
| 4h | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 |
| 1d | 00:00 daily |

Bot waits for close time + 5 seconds buffer before fetching to ensure finalized candle.

## CoinGecko IDs
Use the slug from coingecko.com URLs: bitcoin, ethereum, solana, binancecoin, etc.
