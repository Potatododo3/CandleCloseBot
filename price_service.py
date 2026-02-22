import time
import logging
import requests
from typing import Optional

from config import (
    BYBIT_BASE_URL,
    BYBIT_CATEGORY,
    TIMEFRAME_BYBIT_INTERVAL,
    TIMEFRAME_SECONDS,
    TIMEFRAME_FETCH_LIMIT,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

# Bybit kline response list (each candle, newest first):
# [0] startTime (ms)
# [1] openPrice
# [2] highPrice
# [3] lowPrice
# [4] closePrice
# [5] volume
# [6] turnover (quote volume)


def coin_to_symbol(coin: str) -> Optional[str]:
    """
    Resolve a coin ID to a Bybit USDT perpetual symbol.
    Priority:
      1. Raw symbol passthrough (e.g. BTCUSDT)
      2. DB lookup via coin ID (e.g. bitcoin -> BTCUSDT)
      3. Guess: uppercase coin + USDT
    """
    import database  # imported here to avoid circular import at module load

    upper = coin.upper()

    # Direct symbol passthrough — if it ends in a known quote suffix, treat as full symbol
    for suffix in ("USDT", "USDC", "PERP", "USD"):
        if upper.endswith(suffix) and len(upper) > len(suffix):
            return upper

    # DB lookup
    symbol = database.get_coin_symbol(coin)
    if symbol:
        return symbol

    # Fallback guess
    return upper + "USDT"


def fetch_klines(symbol: str, interval: str, limit: int) -> Optional[list]:
    """
    Fetch klines from Bybit v5 API for a USDT perpetual symbol.
    Returns list of candles (newest first) or None on failure.

    Bybit response format:
    {
        "retCode": 0,
        "result": {
            "list": [
                ["startTime_ms", "open", "high", "low", "close", "volume", "turnover"],
                ...
            ]
        }
    }
    """
    url = f"{BYBIT_BASE_URL}/v5/market/kline"
    params = {
        "category": BYBIT_CATEGORY,
        "symbol":   symbol,
        "interval": interval,
        "limit":    limit,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Bybit rate limit hit. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            data = resp.json()

            ret_code = data.get("retCode", -1)
            if ret_code != 0:
                logger.error(
                    f"Bybit API error for {symbol}/{interval}: "
                    f"retCode={ret_code} msg={data.get('retMsg')}"
                )
                return None

            candles = data.get("result", {}).get("list", [])
            if not candles:
                logger.warning(f"Empty klines for {symbol}/{interval}")
                return None

            return candles  # newest candle first

        except requests.RequestException as e:
            logger.error(f"Attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"All retries exhausted for {symbol}/{interval}")
    return None


def get_latest_closed_candle(coin: str, timeframe: str, candle_close_ts: int) -> Optional[dict]:
    """
    Fetch the candle that closed at candle_close_ts (Unix seconds).

    Bybit candles use startTime (open time). The candle that closed at
    candle_close_ts opened at (candle_close_ts - tf_seconds).
    Candles are returned newest first, so index 0 may still be open —
    we match by comparing startTime to the expected open time.
    """
    symbol = coin_to_symbol(coin)
    if not symbol:
        logger.error(f"Cannot resolve Bybit symbol for: {coin}")
        return None

    interval = TIMEFRAME_BYBIT_INTERVAL[timeframe]
    limit = TIMEFRAME_FETCH_LIMIT[timeframe]
    tf_seconds = TIMEFRAME_SECONDS[timeframe]

    candles = fetch_klines(symbol, interval, limit)
    if not candles:
        return None

    expected_open_ms = (candle_close_ts - tf_seconds) * 1000

    best = None
    best_diff = float("inf")
    for c in candles:
        start_ms = int(c[0])
        diff = abs(start_ms - expected_open_ms)
        if diff < best_diff:
            best_diff = diff
            best = c

    if best is None:
        return None

    # Reject if more than half a candle period off
    tolerance_ms = (tf_seconds // 2) * 1000
    if best_diff > tolerance_ms:
        logger.warning(
            f"Candle mismatch {best_diff}ms > tolerance {tolerance_ms}ms "
            f"for {symbol}/{timeframe}"
        )
        return None

    start_ms = int(best[0])
    return {
        "open_time_ms":   start_ms,
        "open":           float(best[1]),
        "high":           float(best[2]),
        "low":            float(best[3]),
        "close":          float(best[4]),
        "volume":         float(best[5]),
        "candle_open_ts": start_ms // 1000,
    }


def validate_symbol(symbol: str) -> bool:
    """
    Check a raw Bybit symbol exists using the instruments-info endpoint.
    More reliable than klines which can return empty for newly listed coins.
    """
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"
    params = {
        "category": BYBIT_CATEGORY,
        "symbol":   symbol,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return False
        data = resp.json()
        if data.get("retCode") != 0:
            return False
        instruments = data.get("result", {}).get("list", [])
        if not instruments:
            return False
        # Also check it's actively trading
        status = instruments[0].get("status", "")
        if status != "Trading":
            logger.warning(f"{symbol} exists but status is '{status}', not 'Trading'")
        return True
    except requests.RequestException as e:
        logger.error(f"validate_symbol error for {symbol}: {e}")
        return False


def validate_coin(coin: str) -> bool:
    """Resolve coin to symbol and validate it exists on Bybit perpetuals."""
    symbol = coin_to_symbol(coin)
    if not symbol:
        return False
    return validate_symbol(symbol)


def search_symbols(query: str) -> list[str]:
    """
    Search Bybit linear perpetual instruments for symbols matching a query string.
    Returns a list of matching symbol names (up to 10).
    """
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"
    params = {"category": BYBIT_CATEGORY, "limit": 1000}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            return []
        instruments = data.get("result", {}).get("list", [])
        query_upper = query.upper()
        matches = [
            i["symbol"] for i in instruments
            if query_upper in i["symbol"]
        ]
        # Sort: exact prefix matches first, then others
        matches.sort(key=lambda s: (not s.startswith(query_upper), s))
        return matches[:10]
    except requests.RequestException as e:
        logger.error(f"search_symbols error: {e}")
        return []