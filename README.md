# Crypto Candle Alert Bot

Telegram bot that monitors Bybit perpetual futures candle **closes** and sends alerts when the close price crosses your target. No API keys required.

## Features
- Monitors candle close prices (not intra-candle live price)
- Supports 15m, 1h, 4h, 1d timeframes with precise UTC alignment
- Deduplicates alerts per candle — one alert per candle, no spam
- Bybit public API — free, no key needed, perpetual futures
- Single-user with hardcoded Telegram user ID
- SQLite storage — rules and coin registry persist through restarts
- Rule IDs reset to #1 when all rules are deleted
- Search Bybit for exact symbol names from within the bot

## Project Structure
```
bot.py           # Telegram bot, all command handlers, entry point
config.py        # Configuration, constants, default coin list
database.py      # SQLite: rules table + coins registry
price_service.py # Bybit klines fetch with retry logic
scheduler.py     # Precise candle close timing + rule evaluation
requirements.txt
.env.example     # Template for environment variables
```

---

## Local Setup (Windows)

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Get your Bot Token
Message `@BotFather` on Telegram → /newbot → follow prompts → copy the token.

### 3. Get your Telegram User ID
Message `@userinfobot` on Telegram → copy the ID number.

### 4. Create a .env file
Create a file called `.env` in your project folder:
```
TELEGRAM_TOKEN=123456:ABCdef...
TELEGRAM_USER_ID=987654321
```

### 5. Run
```
cd D:\path\to\your\project
python bot.py
```

### 6. Auto-start on Windows boot (optional)
Create a `start.bat` file in your project folder:
```bat
@echo off
cd /d D:\path\to\your\project
python bot.py
pause
```
Then press `Win + R` → type `shell:startup` → drag a shortcut to `start.bat` into that folder.

---

## Deploy on Old Laptop / Raspberry Pi (Recommended)

Running on your own hardware avoids cloud IP blocks from Bybit.

### Recommended OS
- **Ubuntu Server 24.04** — no desktop, ~200MB RAM idle, best for weak hardware
- **Lubuntu 24.04** — if you occasionally want a GUI

### Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip git -y
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip3 install -r requirements.txt --break-system-packages
nano .env   # paste your TELEGRAM_TOKEN and TELEGRAM_USER_ID
```

### Run as a systemd service (auto-starts on boot, restarts on crash)
```bash
sudo nano /etc/systemd/system/cryptobot.service
```
Paste (replace YOUR_USERNAME and YOUR_REPO):
```ini
[Unit]
Description=Crypto Candle Alert Bot
After=network-online.target
Wants=network-online.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/YOUR_REPO
ExecStart=python3 /home/YOUR_USERNAME/YOUR_REPO/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cryptobot
sudo systemctl start cryptobot
```

View logs:
```bash
journalctl -u cryptobot -f
```

### Power optimisations (laptop)
```bash
# Don't sleep on lid close
sudo nano /etc/systemd/logind.conf
# Set: HandleLidSwitch=ignore
sudo systemctl restart systemd-logind

# Disable Bluetooth
sudo systemctl disable bluetooth --now

# CPU powersave mode
sudo apt install cpufrequtils -y
sudo cpufreq-set -g powersave
```

---

## Commands

| Command | Description |
|---|---|
| `/watch bitcoin 4h below 60000` | Alert when BTC 4h candle closes below $60,000 |
| `/watch ethereum 15m above 3500` | Alert when ETH 15m candle closes above $3,500 |
| `/unwatch 3` | Remove rule with ID #3 |
| `/list` | Show all active rules with next check time |
| `/coins` | List all watchable coins and their Bybit symbols |
| `/addcoin btc BTCUSDT` | Add a new coin to the registry |
| `/removecoin btc` | Remove a coin from the registry |
| `/search BTC` | Search Bybit perpetuals for matching symbols |
| `/reset` | Reset database to defaults (asks for confirmation) |
| `/reset confirm` | Confirm reset — wipes all rules and custom coins |
| `/help` | Show all commands and usage |

## Timeframes

| Timeframe | Candle close times (UTC) |
|---|---|
| 15m | :00, :15, :30, :45 every hour |
| 1h | Every full hour |
| 4h | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 |
| 1d | 00:00 daily |

Bot waits close time + 5 seconds before fetching to ensure the candle is finalised on Bybit.

## Adding Coins

The bot ships with 30 pre-loaded perpetual futures coins.

To find and add any coin:
```
/search BTC
/addcoin btc BTCUSDT
/watch btc 1h above 65000
```

The bot validates the symbol against Bybit's instruments API before saving.

## What Persists Through Restarts

| Data | Persists? |
|---|---|
| Alert rules | ✅ Yes — stored in SQLite |
| Coin registry | ✅ Yes — stored in SQLite |
| Candle close schedule | ✅ Yes — recalculated from UTC on startup |
| Missed candle alerts | ❌ No — bot only checks at close time |

## Coin IDs vs Bybit Symbols

You always use the **coin ID** (left side) in `/watch`:
```
/watch bitcoin 4h below 60000    ✅
/watch BTCUSDT 4h below 60000    ✅ (direct symbol also works)
/watch eth 1h above 2100         ✅ (after /addcoin eth ETHUSDT)
```

## Notes on Cloud Hosting

Bybit may block requests from known cloud datacenter IPs (Railway, Render, etc.) with a 403 error. If this happens, running on your own hardware (old laptop, Raspberry Pi) is the most reliable solution as home IPs are not blocked.
