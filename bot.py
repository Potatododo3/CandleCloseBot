import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import database
import price_service
from config import TELEGRAM_TOKEN, TELEGRAM_USER_ID, ALLOWED_TIMEFRAMES
from scheduler import AlertScheduler, get_next_candle_close

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

application: Application = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def authorized_only(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != TELEGRAM_USER_ID:
            logger.warning(f"Unauthorized user {update.effective_user.id}")
            await update.message.reply_text("⛔ Unauthorized.")
            return
        return await handler(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# Alert sender (called by scheduler)
# ---------------------------------------------------------------------------

async def send_alert(rule, close_price: float, candle_close_ts: int):
    close_dt = datetime.fromtimestamp(candle_close_ts, tz=timezone.utc)
    emoji = "🚀" if rule["condition"] == "above" else "📉"
    symbol = price_service.coin_to_symbol(rule["coin"]) or rule["coin"].upper()
    msg = (
        f"{emoji} <b>Alert Triggered</b>\n\n"
        f"<b>Coin:</b> {rule['coin']} (<code>{symbol}</code>)\n"
        f"<b>Timeframe:</b> {rule['timeframe']}\n"
        f"<b>Condition:</b> close {rule['condition']} ${rule['price']:,.4f}\n"
        f"<b>Candle Close:</b> ${close_price:,.4f}\n"
        f"<b>Closed at:</b> {close_dt.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"<b>Rule ID:</b> #{rule['id']}"
    )
    try:
        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID, text=msg, parse_mode="HTML"
        )
        logger.info(f"Alert sent for rule #{rule['id']}")
    except Exception as e:
        logger.error(f"Failed to send alert for rule #{rule['id']}: {e}")


# ---------------------------------------------------------------------------
# /watch
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 4:
        await update.message.reply_text(
            "❌ <b>Usage:</b> /watch &lt;coin&gt; &lt;timeframe&gt; &lt;above|below&gt; &lt;price&gt;\n\n"
            "<b>Example:</b> /watch bitcoin 4h below 60000\n\n"
            f"<b>Timeframes:</b> {', '.join(ALLOWED_TIMEFRAMES)}\n"
            "Use /coins to see watchable coins.",
            parse_mode="HTML",
        )
        return

    coin, timeframe, condition, price_str = args
    coin = coin.lower()
    timeframe = timeframe.lower()
    condition = condition.lower()

    if timeframe not in ALLOWED_TIMEFRAMES:
        await update.message.reply_text(
            f"❌ Invalid timeframe <code>{timeframe}</code>.\n"
            f"Allowed: {', '.join(ALLOWED_TIMEFRAMES)}",
            parse_mode="HTML",
        )
        return

    if condition not in ("above", "below"):
        await update.message.reply_text("❌ Condition must be <code>above</code> or <code>below</code>.", parse_mode="HTML")
        return

    try:
        price = float(price_str)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Price must be a positive number.")
        return

    # Resolve symbol before validating so we can show it
    symbol = price_service.coin_to_symbol(coin)
    await update.message.reply_text(
        f"⏳ Validating <code>{coin}</code> → <code>{symbol}</code> on Bybit perpetuals...",
        parse_mode="HTML",
    )

    if not price_service.validate_coin(coin):
        await update.message.reply_text(
            f"❌ <code>{symbol}</code> not found on Bybit perpetuals.\n\n"
            f"• Use /coins to see supported coins\n"
            f"• Use /addcoin to add a new one",
            parse_mode="HTML",
        )
        return

    rule_id = database.add_rule(coin, timeframe, condition, price)
    next_close = get_next_candle_close(timeframe)
    next_close_str = datetime.fromtimestamp(next_close, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    await update.message.reply_text(
        f"✅ <b>Rule #{rule_id} created</b>\n\n"
        f"<b>Coin:</b> {coin} (<code>{symbol}</code>)\n"
        f"<b>Timeframe:</b> {timeframe}\n"
        f"<b>Condition:</b> close {condition} ${price:,.4f}\n\n"
        f"⏰ <b>Next check:</b> {next_close_str}",
        parse_mode="HTML",
    )
    logger.info(f"Rule #{rule_id}: {coin} {timeframe} {condition} {price}")


# ---------------------------------------------------------------------------
# /unwatch
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /unwatch &lt;id&gt;", parse_mode="HTML")
        return
    try:
        rule_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number.")
        return

    if database.remove_rule(rule_id):
        await update.message.reply_text(f"🗑 Rule #{rule_id} removed.")
        logger.info(f"Rule #{rule_id} removed.")
    else:
        await update.message.reply_text(f"❌ Rule #{rule_id} not found. Use /list to see active rules.")


# ---------------------------------------------------------------------------
# /list
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = database.get_all_rules()
    if not rules:
        await update.message.reply_text("📭 No active rules.\n\nUse /watch to create one.")
        return

    lines = [f"📋 <b>Active Rules ({len(rules)})</b>\n"]
    for rule in rules:
        symbol = price_service.coin_to_symbol(rule["coin"]) or "?"
        next_close = get_next_candle_close(rule["timeframe"])
        next_str = datetime.fromtimestamp(next_close, tz=timezone.utc).strftime("%H:%M UTC")

        triggered_str = "never"
        if rule["last_triggered_candle"]:
            triggered_str = datetime.fromtimestamp(
                rule["last_triggered_candle"], tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")

        lines.append(
            f"<b>#{rule['id']}</b> {rule['coin']} (<code>{symbol}</code>) "
            f"| {rule['timeframe']} | {rule['condition']} ${rule['price']:,.4f}\n"
            f"  ⏰ next: {next_str}  |  last triggered: {triggered_str}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /coins
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    coins = database.get_all_coins()
    if not coins:
        await update.message.reply_text("No coins in registry. Use /addcoin to add one.")
        return

    lines = [f"🪙 <b>Watchable Coins ({len(coins)})</b>\n"]
    for c in coins:
        lines.append(f"<code>{c['id']}</code> → <code>{c['symbol']}</code>")

    lines.append("\nUse /addcoin &lt;coin_id&gt; &lt;SYMBOL&gt; to add more.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /addcoin
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "❌ <b>Usage:</b> /addcoin &lt;coin_id&gt; &lt;BINANCE_SYMBOL&gt;\n\n"
            "<b>Example:</b> /addcoin ondo ONDOUSDT\n\n"
            "coin_id is how you'll refer to it in /watch.\n"
            "BINANCE_SYMBOL must be a valid Bybit USDT perpetual.",
            parse_mode="HTML",
        )
        return

    coin_id = args[0].lower()
    symbol = args[1].upper()

    if not symbol.endswith("USDT"):
        await update.message.reply_text(
            f"❌ Symbol must end in USDT (e.g. <code>ONDOUSDT</code>).", parse_mode="HTML"
        )
        return

    await update.message.reply_text(
        f"⏳ Validating <code>{symbol}</code> on Bybit perpetuals...", parse_mode="HTML"
    )

    if not price_service.validate_symbol(symbol):
        await update.message.reply_text(
            f"❌ <code>{symbol}</code> not found on Bybit perpetuals.\n"
            f"Check the symbol at bybit.com and try again.",
            parse_mode="HTML",
        )
        return

    added = database.add_coin(coin_id, symbol)
    if not added:
        # Update existing entry
        with database.get_connection() as conn:
            conn.execute("UPDATE coins SET symbol = ? WHERE id = ?", (symbol, coin_id))
            conn.commit()
        await update.message.reply_text(
            f"♻️ Updated <code>{coin_id}</code> → <code>{symbol}</code>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"✅ Added <code>{coin_id}</code> → <code>{symbol}</code>\n\n"
            f"You can now use: /watch {coin_id} 1h above 1.50",
            parse_mode="HTML",
        )
    logger.info(f"Coin registry: {coin_id} -> {symbol}")


# ---------------------------------------------------------------------------
# /removecoin
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_removecoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /removecoin &lt;coin_id&gt;", parse_mode="HTML")
        return

    coin_id = context.args[0].lower()
    if database.remove_coin(coin_id):
        await update.message.reply_text(f"🗑 Removed <code>{coin_id}</code> from coin registry.", parse_mode="HTML")
        logger.info(f"Coin {coin_id} removed from registry.")
    else:
        await update.message.reply_text(f"❌ <code>{coin_id}</code> not found in registry.", parse_mode="HTML")


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Crypto Candle Alert Bot</b>\n"
        "Powered by Bybit perpetual futures — no API key required.\n\n"

        "<b>Alert commands</b>\n"
        "/watch <code>coin timeframe above|below price</code>\n"
        "  Create a candle close alert\n"
        "/unwatch <code>id</code>\n"
        "  Delete a rule by ID\n"
        "/list\n"
        "  Show all active rules\n\n"

        "<b>Coin commands</b>\n"
        "/coins\n"
        "  List all watchable coins\n"
        "/addcoin <code>coin_id SYMBOL</code>\n"
        "  Add a new coin to the registry\n"
        "/removecoin <code>coin_id</code>\n"
        "  Remove a coin from the registry\n\n"

        "<b>Timeframes</b>\n"
        "15m · 1h · 4h · 1d\n\n"

        "<b>Examples</b>\n"
        "/watch bitcoin 4h below 60000\n"
        "/watch ethereum 15m above 3500\n"
        "/watch solana 1d above 200\n"
        "/addcoin ondo ONDOUSDT\n"
        "/watch ondo 1h above 1.50\n"
        "/unwatch 3\n\n"

        "<b>Notes</b>\n"
        "• Alerts fire on candle <b>close</b>, not live price\n"
        "• One alert per candle — no duplicate spam\n"
        "• 15m closes: :00 :15 :30 :45 UTC each hour\n"
        "• 4h closes: 00:00 04:00 08:00 12:00 16:00 20:00 UTC\n"
        "• 1d closes: 00:00 UTC daily\n",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

def build_application() -> Application:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set.")
    if TELEGRAM_USER_ID == 0:
        raise ValueError("TELEGRAM_USER_ID is not set.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch",       cmd_watch))
    app.add_handler(CommandHandler("unwatch",     cmd_unwatch))
    app.add_handler(CommandHandler("list",        cmd_list))
    app.add_handler(CommandHandler("coins",       cmd_coins))
    app.add_handler(CommandHandler("addcoin",     cmd_addcoin))
    app.add_handler(CommandHandler("removecoin",  cmd_removecoin))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("start",       cmd_help))
    return app


async def main():
    global application

    database.init_db()
    application = build_application()

    scheduler = AlertScheduler(send_alert_callback=send_alert)
    scheduler.start()

    logger.info("Bot starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Shutting down...")
        scheduler.stop()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())