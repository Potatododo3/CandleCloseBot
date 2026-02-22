import time
import logging
import requests
from typing import Optional

from config import (
    BINANCE_BASE_URL,
    TIMEFRAME_BINANCE_INTERVAL,
    TIMEFRAME_SECONDS,
    TIMEFRAME_FETCH_LIMIT,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

# Binance kline fields:
# [0] open_time_ms  [1] open  [2] high  [3] low  [4] close
# [5] volume        [6] close_time_ms


def coin_to_symbol(coin: str) -> Optional[str]:
    """
    Resolve a coin ID to a Binance USDT symbol.
    Priority:
      1. Raw Binance symbol passthrough (e.g. BTCUSDT)
      2. DB lookup via coin ID (e.g. bitcoin -> BTCUSDT)
      3. Guess: uppercase coin + USDT
    """
    import database  # imported here to avoid circular imports at module load

    upper = coin.upper()

    # Direct Binance symbol (e.g. user typed BTCUSDT or btcusdt)
    if upper.endswith("USDT") and len(upper) > 4:
        return upper

    # DB lookup
    symbol = database.get_coin_symbol(coin)
    if symbol:
        return symbol

    # Fallback guess
    return upper + "USDT"


def fetch_klines(symbol: str, interval: str, limit: int) -> Optional[list]:
    url = f"{BINANCE_BASE_URL}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Binance rate limit. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            if resp.status_code == 400:
                logger.error(f"Binance bad request symbol={symbol}: {resp.text}")
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data:
                logger.warning(f"Empty klines for {symbol}/{interval}")
                return None
            return data
        except requests.RequestException as e:
            logger.error(f"Attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"All retries exhausted for {symbol}/{interval}")
    return None


def get_latest_closed_candle(coin: str, timeframe: str, candle_close_ts: int) -> Optional[dict]:
    """
    Fetch the candle that closed at candle_close_ts (Unix seconds).
    Matches by comparing expected open_time to actual open_time within half-period tolerance.
    """
    symbol = coin_to_symbol(coin)
    if not symbol:
        logger.error(f"Cannot resolve Binance symbol for: {coin}")
        return None

    interval = TIMEFRAME_BINANCE_INTERVAL[timeframe]
    limit = TIMEFRAME_FETCH_LIMIT[timeframe]
    tf_seconds = TIMEFRAME_SECONDS[timeframe]

    candles = fetch_klines(symbol, interval, limit)
    if not candles:
        return None

    expected_open_ms = (candle_close_ts - tf_seconds) * 1000

    best = None
    best_diff = float("inf")
    for c in candles:
        diff = abs(int(c[0]) - expected_open_ms)
        if diff < best_diff:
            best_diff = diff
            best = c

    if best is None:
        return None

    tolerance_ms = (tf_seconds // 2) * 1000
    if best_diff > tolerance_ms:
        logger.warning(f"Candle mismatch {best_diff}ms > tolerance {tolerance_ms}ms for {symbol}/{timeframe}")
        return None

    open_time_ms = int(best[0])
    return {
        "open_time_ms":   open_time_ms,
        "close_time_ms":  int(best[6]),
        "open":           float(best[1]),
        "high":           float(best[2]),
        "low":            float(best[3]),
        "close":          float(best[4]),
        "volume":         float(best[5]),
        "candle_open_ts": open_time_ms // 1000,
    }


def validate_symbol(symbol: str) -> bool:
    """Check a raw Binance symbol exists by fetching one kline."""
    url = f"{BINANCE_BASE_URL}/klines"
    params = {"symbol": symbol, "interval": "1d", "limit": 1}
    try:
        resp = requests.get(url, params=params, timeout=10)
        return resp.status_code == 200 and bool(resp.json())
    except requests.RequestException as e:
        logger.error(f"validate_symbol error for {symbol}: {e}")
        return False


def validate_coin(coin: str) -> bool:
    """Resolve coin to symbol and validate it exists on Binance."""
    symbol = coin_to_symbol(coin)
    if not symbol:
        return False
    return validate_symbol(symbol)