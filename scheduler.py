import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import database
import price_service
from config import TIMEFRAME_SECONDS, CANDLE_CLOSE_BUFFER_SECONDS, ALLOWED_TIMEFRAMES

logger = logging.getLogger(__name__)


def get_next_candle_close(timeframe: str, from_ts: Optional[int] = None) -> int:
    """
    Compute the next candle close timestamp (UTC seconds) for the given timeframe.

    4h closes: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
    1h closes: every full UTC hour
    1d closes: 00:00 UTC daily
    """
    now = from_ts if from_ts is not None else int(time.time())
    tf_sec = TIMEFRAME_SECONDS[timeframe]
    current_candle_open = (now // tf_sec) * tf_sec
    next_close = current_candle_open + tf_sec
    return next_close


class AlertScheduler:
    def __init__(self, send_alert_callback: Callable):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.send_alert = send_alert_callback
        self._scheduled_jobs: dict[str, str] = {}  # timeframe -> job_id

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started.")
        # Schedule the first check for each timeframe
        for tf in ALLOWED_TIMEFRAMES:
            self._schedule_next_check(tf)

    def stop(self):
        self.scheduler.shutdown(wait=False)

    def _schedule_next_check(self, timeframe: str):
        """Schedule a one-time job to fire at the next candle close + buffer."""
        next_close = get_next_candle_close(timeframe)
        fire_at = next_close + CANDLE_CLOSE_BUFFER_SECONDS
        fire_dt = datetime.fromtimestamp(fire_at, tz=timezone.utc)

        job_id = f"candle_check_{timeframe}"

        # Remove existing job if present
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._check_candle_and_reschedule,
            trigger=DateTrigger(run_date=fire_dt),
            id=job_id,
            args=[timeframe, next_close],
            misfire_grace_time=60,
        )
        logger.info(
            f"[{timeframe}] Next candle check scheduled for {fire_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

    async def _check_candle_and_reschedule(self, timeframe: str, candle_close_ts: int):
        """Check all rules for this timeframe, then schedule the next check."""
        logger.info(f"[{timeframe}] Candle closed at ts={candle_close_ts}. Evaluating rules...")
        await self._evaluate_rules(timeframe, candle_close_ts)
        # Always reschedule the next check
        self._schedule_next_check(timeframe)

    async def _evaluate_rules(self, timeframe: str, candle_close_ts: int):
        rules = database.get_rules_by_timeframe(timeframe)
        if not rules:
            logger.info(f"[{timeframe}] No active rules.")
            return

        # Group rules by coin to minimize API calls
        coin_rules: dict[str, list] = {}
        for rule in rules:
            coin_rules.setdefault(rule["coin"], []).append(rule)

        for coin, coin_rule_list in coin_rules.items():
            candle = price_service.get_latest_closed_candle(coin, timeframe, candle_close_ts)
            if candle is None:
                logger.error(f"[{timeframe}] Could not fetch candle for {coin}. Skipping.")
                continue

            close_price = candle["close"]
            candle_open_ts = candle["candle_open_ts"]

            logger.info(
                f"[{timeframe}] {coin} candle close={close_price} "
                f"(open_ts={candle_open_ts})"
            )

            for rule in coin_rule_list:
                rule_id = rule["id"]
                last_triggered = rule["last_triggered_candle"]

                # Skip if already triggered for this candle
                if last_triggered == candle_open_ts:
                    logger.info(f"Rule {rule_id}: already triggered for this candle. Skipping.")
                    continue

                condition = rule["condition"]
                target_price = rule["price"]
                triggered = False

                if condition == "above" and close_price > target_price:
                    triggered = True
                elif condition == "below" and close_price < target_price:
                    triggered = True

                if triggered:
                    logger.info(f"Rule {rule_id} TRIGGERED: {coin} {condition} {target_price}")
                    database.update_last_triggered(rule_id, candle_open_ts)
                    await self.send_alert(rule, close_price, candle_close_ts)
                else:
                    logger.info(
                        f"Rule {rule_id}: {coin} close={close_price} did not meet "
                        f"{condition} {target_price}"
                    )

    def reschedule_all(self):
        """Call after rules change to ensure jobs are running."""
        for tf in ALLOWED_TIMEFRAMES:
            if not self.scheduler.get_job(f"candle_check_{tf}"):
                self._schedule_next_check(tf)
