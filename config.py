import os
from dotenv import load_dotenv

load_dotenv()  # No-op on Railway (env vars injected directly); loads .env locally

# --- Required: Set via environment variables or .env file ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# Message @userinfobot on Telegram to find your user ID
TELEGRAM_USER_ID = int(os.environ.get("TELEGRAM_USER_ID", "0"))

# --- Bybit Public API (no key required) ---
# category=linear means USDT perpetual futures
BYBIT_BASE_URL = "https://api.bybit.com"
BYBIT_CATEGORY = "linear"  # USDT perpetual futures

# --- Allowed timeframes ---
ALLOWED_TIMEFRAMES = ["15m", "1h", "4h", "1d"]

# Bybit interval strings (minutes as integers, except D/W/M)
TIMEFRAME_BYBIT_INTERVAL = {
    "15m": "15",
    "1h":  "60",
    "4h":  "240",
    "1d":  "D",
}

# Candle duration in seconds
TIMEFRAME_SECONDS = {
    "15m": 900,
    "1h":  3600,
    "4h":  14400,
    "1d":  86400,
}

# Candles to fetch per check (3 is enough to find the closed one)
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

# Default coin ID -> Bybit USDT perpetual symbol mapping (seeded into DB on first run).
# Use /addcoin to add more at runtime without editing this file.
# Note: not all spot coins have perpetual futures — only high-liquidity ones do.
DEFAULT_COINS = {
    "bitcoin":            "BTCUSDT",
    "ethereum":           "ETHUSDT",
    "solana":             "SOLUSDT",
    "binancecoin":        "BNBUSDT",
    "ripple":             "XRPUSDT",
    "cardano":            "ADAUSDT",
    "avalanche":          "AVAXUSDT",
    "dogecoin":           "DOGEUSDT",
    "polkadot":           "DOTUSDT",
    "chainlink":          "LINKUSDT",
    "litecoin":           "LTCUSDT",
    "shiba-inu":          "SHIBUSDT",
    "uniswap":            "UNIUSDT",
    "stellar":            "XLMUSDT",
    "cosmos":             "ATOMUSDT",
    "toncoin":            "TONUSDT",
    "sui":                "SUIUSDT",
    "pepe":               "PEPEUSDT",
    "aptos":              "APTUSDT",
    "near":               "NEARUSDT",
    "hedera-hashgraph":   "HBARUSDT",
    "arbitrum":           "ARBUSDT",
    "optimism":           "OPUSDT",
    "injective-protocol": "INJUSDT",
    "sei-network":        "SEIUSDT",
    "render-token":       "RENDERUSDT",
    "hyperliquid":        "HYPEUSDT",
    "mantra-dao":         "OMUSDT",
    "berachain":          "BERAUSDT",
    "ondo-finance":       "ONDOUSDT",
}