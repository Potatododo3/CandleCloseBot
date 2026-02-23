import sqlite3
import logging
from config import DB_PATH, DEFAULT_COINS

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                condition TEXT NOT NULL,
                price REAL NOT NULL,
                last_triggered_candle INTEGER DEFAULT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coins (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL
            )
        """)
        # Seed defaults only if table is empty
        count = conn.execute("SELECT COUNT(*) FROM coins").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO coins (id, symbol) VALUES (?, ?)",
                DEFAULT_COINS.items(),
            )
        conn.commit()
    logger.info("Database initialized.")


# --- Rules ---

def add_rule(coin: str, timeframe: str, condition: str, price: float) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO rules (coin, timeframe, condition, price) VALUES (?, ?, ?, ?)",
            (coin, timeframe, condition, price),
        )
        conn.commit()
        return cursor.lastrowid


def remove_rule(rule_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return False
        # Reset autoincrement counter when the last rule is deleted so IDs restart from 1
        remaining = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
        if remaining == 0:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'rules'")
            conn.commit()
        return True


def get_all_rules() -> list:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM rules ORDER BY id").fetchall()


def get_rules_by_timeframe(timeframe: str) -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM rules WHERE timeframe = ?", (timeframe,)
        ).fetchall()


def update_last_triggered(rule_id: int, candle_timestamp: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE rules SET last_triggered_candle = ? WHERE id = ?",
            (candle_timestamp, rule_id),
        )
        conn.commit()


# --- Coin registry ---

def get_all_coins() -> list:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM coins ORDER BY id").fetchall()


def get_coin_symbol(coin_id: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT symbol FROM coins WHERE id = ?", (coin_id.lower(),)
        ).fetchone()
        return row["symbol"] if row else None


def add_coin(coin_id: str, symbol: str) -> bool:
    """Returns False if coin_id already exists."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM coins WHERE id = ?", (coin_id.lower(),)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO coins (id, symbol) VALUES (?, ?)",
            (coin_id.lower(), symbol.upper()),
        )
        conn.commit()
        return True


def remove_coin(coin_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM coins WHERE id = ?", (coin_id.lower(),))
        conn.commit()
        return cursor.rowcount > 0


def reset_db():
    """
    Wipe all rules and coins, reset autoincrement, then reseed default coins.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM rules")
        conn.execute("DELETE FROM coins")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'rules'")
        conn.executemany(
            "INSERT INTO coins (id, symbol) VALUES (?, ?)",
            DEFAULT_COINS.items(),
        )
        conn.commit()
    logger.info("Database reset to defaults.")