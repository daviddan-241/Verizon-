"""
Main Telegram Bot - Handles commands and token posting.
"""
import logging
import asyncio
import aiohttp
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from formatter import format_token_message
from scanners.base import TokenInfo
from scanners.dexscreener import scan_dexscreener
from scanners.geckoterminal import scan_geckoterminal
from scanners.pumpfun import scan_pumpfun

logger = logging.getLogger(__name__)

# Track already-posted tokens to avoid duplicates
seen_tokens: set[str] = set()

# Max seen tokens to keep in memory (prevent memory leak)
MAX_SEEN = 10000


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🤖 <b>Coin Scanner Bot</b>\n\n"
        "I scan multiple platforms for newly launched tokens that have Telegram groups.\n\n"
        "<b>Commands:</b>\n"
        "/start - Show this message\n"
        "/status - Show bot status\n"
        "/scan - Trigger a manual scan now\n"
        "/stats - Show scanning statistics\n"
        "/clear - Clear seen tokens cache\n",
        parse_mode=ParseMode.HTML,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    scanners = []
    if config.ENABLE_DEXSCREENER:
        scanners.append("✅ DexScreener")
    else:
        scanners.append("❌ DexScreener")
    if config.ENABLE_GECKOTERMINAL:
        scanners.append("✅ GeckoTerminal")
    else:
        scanners.append("❌ GeckoTerminal")
    if config.ENABLE_PUMPFUN:
        scanners.append("✅ Pump.fun")
    else:
        scanners.append("❌ Pump.fun")

    await update.message.reply_text(
        f"📊 <b>Bot Status</b>\n\n"
        f"⏱ Scan interval: {config.SCAN_INTERVAL}s\n"
        f"🔢 Tokens seen: {len(seen_tokens)}\n"
        f"📡 Chat ID: <code>{config.TELEGRAM_CHAT_ID}</code>\n\n"
        f"<b>Scanners:</b>\n" + "\n".join(scanners),
        parse_mode=ParseMode.HTML,
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    await update.message.reply_text(
        f"📈 <b>Scan Statistics</b>\n\n"
        f"🔢 Total unique tokens seen: {len(seen_tokens)}\n"
        f"💾 Cache limit: {MAX_SEEN}",
        parse_mode=ParseMode.HTML,
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    global seen_tokens
    count = len(seen_tokens)
    seen_tokens.clear()
    await update.message.reply_text(
        f"🧹 Cleared {count} tokens from cache.",
        parse_mode=ParseMode.HTML,
    )


async def manual_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command - trigger manual scan."""
    await update.message.reply_text("🔍 Running manual scan...")
    count = await run_scan_cycle(context.bot)
    await update.message.reply_text(
        f"✅ Manual scan complete. Found {count} new tokens with TG links.",
        parse_mode=ParseMode.HTML,
    )


async def run_scan_cycle(bot: Bot) -> int:
    """
    Run one full scan cycle across all enabled scanners.
    Returns the number of new tokens found and posted.
    """
    global seen_tokens
    all_tokens: list[TokenInfo] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        if config.ENABLE_DEXSCREENER:
            tasks.append(scan_dexscreener(session))
        if config.ENABLE_GECKOTERMINAL:
            tasks.append(scan_geckoterminal(session))
        if config.ENABLE_PUMPFUN:
            tasks.append(scan_pumpfun(session))

        if not tasks:
            logger.warning("No scanners enabled!")
            return 0

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scanner error: {result}")
            elif isinstance(result, list):
                all_tokens.extend(result)

    # Filter out already-seen tokens and deduplicate
    new_tokens = []
    for token in all_tokens:
        key = token.unique_key
        if key not in seen_tokens:
            seen_tokens.add(key)
            new_tokens.append(token)

    # Post new tokens to the group
    posted = 0
    for token in new_tokens:
        try:
            message = format_token_message(token)
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            posted += 1
            logger.info(f"Posted: {token.name} ({token.symbol}) on {token.chain} - {token.telegram_link}")
            # Small delay between messages to avoid rate limits
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to post token {token.name}: {e}")

    # Prune seen tokens if too large
    if len(seen_tokens) > MAX_SEEN:
        # Keep the most recent half
        excess = len(seen_tokens) - (MAX_SEEN // 2)
        for _ in range(excess):
            seen_tokens.pop()

    return posted


async def periodic_scan(bot: Bot):
    """Background task that runs scans periodically."""
    logger.info(f"Starting periodic scanner (interval: {config.SCAN_INTERVAL}s)")

    # Initial startup message
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="🤖 <b>Coin Scanner Bot Started!</b>\n\n"
                 f"⏱ Scanning every {config.SCAN_INTERVAL} seconds\n"
                 f"📡 Sources: DexScreener, GeckoTerminal, Pump.fun\n"
                 f"🔗 Looking for tokens with Telegram links...",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    while True:
        try:
            count = await run_scan_cycle(bot)
            if count > 0:
                logger.info(f"Scan cycle complete: {count} new tokens posted")
            else:
                logger.debug("Scan cycle complete: no new tokens")
        except Exception as e:
            logger.error(f"Scan cycle error: {e}")

        await asyncio.sleep(config.SCAN_INTERVAL)


async def post_init(application: Application):
    """Called after the bot is initialized - starts the background scanner."""
    asyncio.create_task(periodic_scan(application.bot))


def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    )

    # Reduce noise from httpx/httpcore
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Check your .env file.")
        return

    if not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set! Check your .env file.")
        return

    logger.info("Starting Coin Scanner Bot...")

    # Build the bot application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("scan", manual_scan_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # Start background scanner after bot init
    app.post_init = post_init

    # Run the bot
    logger.info("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
