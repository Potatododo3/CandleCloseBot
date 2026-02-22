import os
from dotenv import load_dotenv

load_dotenv()

# --- Required: Set via environment variables or .env file ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# Message @userinfobot on Telegram to find your user ID
TELEGRAM_USER_ID = int(os.environ.get("TELEGRAM_USER_ID", "0"))

# --- Binance Public API (no key required) ---
BINANCE_BASE_URL = "https://api.binance.com/api/v3"

# --- Allowed timeframes ---
ALLOWED_TIMEFRAMES = ["15m", "1h", "4h", "1d"]

# Binance interval strings
TIMEFRAME_BINANCE_INTERVAL = {
    "15m": "15m",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1d",
}

# Candle duration in seconds
TIMEFRAME_SECONDS = {
    "15m": 900,
    "1h":  3600,
    "4h":  14400,
    "1d":  86400,
}

# Candles to fetch per check (last N candles, 3 is enough)
TIMEFRAME_FETCH_LIMIT = {
    "15m": 3,
    "1h":  3,
    "4h":  3,
    "1d":  3,
}

# Buffer seconds after candle close before fetching
CANDLE_CLOSE_BUFFER_SECONDS = 5

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# SQLite DB path
DB_PATH = "alerts.db"

# Default coin ID -> Binance symbol mapping (seeded into DB on first run).
# Use /addcoin to add more at runtime without editing this file.
DEFAULT_COINS = {
    "bitcoin":            "BTCUSDT",
    "ethereum":           "ETHUSDT",
    "solana":             "SOLUSDT",
    "binancecoin":        "BNBUSDT",
    "ripple":             "XRPUSDT",
    "cardano":            "ADAUSDT",
    "avalanche-2":        "AVAXUSDT",
    "dogecoin":           "DOGEUSDT",
    "polkadot":           "DOTUSDT",
    "chainlink":          "LINKUSDT",
    "litecoin":           "LTCUSDT",
    "shiba-inu":          "SHIBUSDT",
    "uniswap":            "UNIUSDT",
    "stellar":            "XLMUSDT",
    "cosmos":             "ATOMUSDT",
    "monero":             "XMRUSDT",
    "toncoin":            "TONUSDT",
    "sui":                "SUIUSDT",
    "pepe":               "PEPEUSDT",
    "aptos":              "APTUSDT",
    "near":               "NEARUSDT",
    "internet-computer":  "ICPUSDT",
    "ethereum-classic":   "ETCUSDT",
    "filecoin":           "FILUSDT",
    "hedera-hashgraph":   "HBARUSDT",
    "arbitrum":           "ARBUSDT",
    "optimism":           "OPUSDT",
    "injective-protocol": "INJUSDT",
    "sei-network":        "SEIUSDT",
    "render-token":       "RENDERUSDT",
}