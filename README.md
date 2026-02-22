# Crypto Candle Alert Bot

Telegram bot that monitors Binance candle **closes** and sends alerts when the close price crosses a target. No API keys required.

## Features
- Monitors candle close prices (not intra-candle live price)
- Supports 15m, 1h, 4h, 1d timeframes with precise UTC alignment
- Deduplicates alerts per candle — no spam
- Binance public API — free, no key needed
- Single-user with hardcoded Telegram user ID
- SQLite storage — coin registry persists across restarts
- Rule IDs reset to #1 when all rules are deleted

## Project Structure
```
bot.py           # Telegram bot, all command handlers, entry point
config.py        # Configuration, constants, default coin list
database.py      # SQLite: rules table + coins registry
price_service.py # Binance klines fetch with retry logic
scheduler.py     # Precise candle close timing + rule evaluation
requirements.txt
Procfile         # Railway worker process definition
.env.example     # Template for environment variables
```

---

## Local Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Get your Bot Token
Message `@BotFather` on Telegram → /newbot → follow prompts → copy the token.

### 3. Get your Telegram User ID
Message `@userinfobot` on Telegram → copy the ID number.

### 4. Create a .env file
Copy `.env.example` to `.env` and fill in your values:
```
TELEGRAM_TOKEN=123456:ABCdef...
TELEGRAM_USER_ID=987654321
```

### 5. Run
```
python bot.py
```

---

## Deploy to Railway (Free Tier)

Railway gives you $5 credit/month — more than enough to run a 24/7 bot.

### Step 1 — Create account
Sign up at https://railway.app using GitHub (free, no credit card required).

### Step 2 — Install Git
Download from https://git-scm.com/download/win and install. Then verify:
```
git --version
```

### Step 3 — Push code to GitHub
In your project folder:
```
git init
git add .
git commit -m "initial commit"
```
Create a new private repo at https://github.com/new, then:
```
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Step 4 — Create Railway project
1. Go to https://railway.app/dashboard
2. New Project → Deploy from GitHub repo
3. Authorize Railway → select your repo → Deploy Now

### Step 5 — Set environment variables
In your Railway service → Variables tab → add:
- `TELEGRAM_TOKEN` = your bot token
- `TELEGRAM_USER_ID` = your Telegram user ID

### Step 6 — Set start command
Service → Settings → Start Command:
```
python bot.py
```
(Railway may detect the Procfile automatically — if so, skip this.)

### Step 7 — Redeploy and verify
Go to Deployments tab → Redeploy. Then check logs — you should see:
```
Bot starting...
Scheduler started.
Bot is running.
```
Send `/help` to your bot in Telegram to confirm it's working.

### Note on free tier
Railway uses an ephemeral filesystem — `alerts.db` resets on every redeploy. Your **coin registry** and **rules** will be wiped when you push new code. Re-add your rules after each deploy. The default coins are re-seeded automatically.

---

## Commands

| Command | Description |
|---|---|
| `/watch bitcoin 4h below 60000` | Alert when BTC 4h candle closes below $60,000 |
| `/watch ethereum 15m above 3500` | Alert when ETH 15m candle closes above $3,500 |
| `/unwatch 3` | Remove rule with ID #3 |
| `/list` | Show all active rules with next check time |
| `/coins` | List all watchable coins and their Binance symbols |
| `/addcoin ondo ONDOUSDT` | Add a new coin to the registry |
| `/removecoin ondo` | Remove a coin from the registry |
| `/help` | Show help message |

## Timeframes

| Timeframe | Candle close times (UTC) |
|---|---|
| 15m | :00, :15, :30, :45 every hour |
| 1h | Every full hour |
| 4h | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 |
| 1d | 00:00 daily |

Bot waits for close time + 5 seconds before fetching to ensure the candle is finalized on Binance.

## Adding Coins

The bot ships with 30 pre-loaded coins (bitcoin, ethereum, solana, etc.).

To add any coin not in the list, find its Binance USDT trading pair symbol at binance.com, then:
```
/addcoin ondo ONDOUSDT
/watch ondo 1h above 1.50
```

The bot validates the symbol against Binance before saving it.

## Coin IDs vs Binance Symbols

You always use the **coin ID** (left side) in `/watch`, never the symbol directly:
```
/watch bitcoin 4h below 60000    ✅
/watch BTCUSDT 4h below 60000    ✅ (also works as passthrough)
/watch BTC 4h below 60000        ❌ (use bitcoin or BTCUSDT)
```
