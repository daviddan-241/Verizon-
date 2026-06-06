"""
Telegram Coin Scanner Bot
Scans DexScreener, GeckoTerminal, Pump.fun, and trending pools
for new tokens with Telegram links. Posts to your group every 2s.
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
from scanners.birdeye import scan_extra_sources

logger = logging.getLogger(__name__)

# Track posted tokens to avoid duplicates
seen_tokens: set[str] = set()
MAX_SEEN = 50000
scan_count = 0
total_posted = 0


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Coin Scanner Bot</b>\n\n"
        "Scanning DexScreener, GeckoTerminal, Pump.fun for new tokens with TG links.\n\n"
        "/status - Bot status\n"
        "/scan - Manual scan\n"
        "/stats - Statistics\n"
        "/clear - Clear cache",
        parse_mode=ParseMode.HTML,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scanners = []
    if config.ENABLE_DEXSCREENER: scanners.append("✅ DexScreener")
    if config.ENABLE_GECKOTERMINAL: scanners.append("✅ GeckoTerminal")
    if config.ENABLE_PUMPFUN: scanners.append("✅ Pump.fun")
    scanners.append("✅ Trending Pools")

    await update.message.reply_text(
        f"📊 <b>Status</b>\n\n"
        f"Interval: {config.SCAN_INTERVAL}s\n"
        f"Tokens cached: {len(seen_tokens)}\n"
        f"Scans done: {scan_count}\n"
        f"Total posted: {total_posted}\n\n"
        + "\n".join(scanners),
        parse_mode=ParseMode.HTML,
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📈 Scans: {scan_count} | Posted: {total_posted} | Cached: {len(seen_tokens)}",
        parse_mode=ParseMode.HTML,
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seen_tokens
    c = len(seen_tokens)
    seen_tokens.clear()
    await update.message.reply_text(f"🧹 Cleared {c} tokens from cache.")


async def manual_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning...")
    count = await run_scan_cycle(context.bot)
    await update.message.reply_text(f"✅ Done. {count} new tokens found.")


async def run_scan_cycle(bot: Bot) -> int:
    """Run one scan cycle across all scanners."""
    global seen_tokens, scan_count, total_posted
    scan_count += 1
    all_tokens: list[TokenInfo] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        if config.ENABLE_DEXSCREENER:
            tasks.append(scan_dexscreener(session))
        if config.ENABLE_GECKOTERMINAL:
            tasks.append(scan_geckoterminal(session))
        if config.ENABLE_PUMPFUN:
            tasks.append(scan_pumpfun(session))
        # Always run extra sources
        tasks.append(scan_extra_sources(session))

        if not tasks:
            return 0

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_tokens.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Scanner error: {result}")

    # Deduplicate
    new_tokens = []
    for token in all_tokens:
        key = token.unique_key
        if key not in seen_tokens:
            seen_tokens.add(key)
            new_tokens.append(token)

    # Post to group
    posted = 0
    for token in new_tokens:
        try:
            msg = format_token_message(token)
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            posted += 1
            total_posted += 1
            logger.info(f"Posted: {token.name} (${token.symbol}) [{token.chain}] - {token.telegram_link}")
            await asyncio.sleep(0.5)  # avoid TG rate limits
        except Exception as e:
            logger.error(f"Post error for {token.name}: {e}")

    # Prune cache
    if len(seen_tokens) > MAX_SEEN:
        excess = len(seen_tokens) - (MAX_SEEN // 2)
        for _ in range(excess):
            seen_tokens.pop()

    return posted


async def periodic_scan(bot: Bot):
    """Background loop - scans every SCAN_INTERVAL seconds."""
    logger.info(f"Scanner started (every {config.SCAN_INTERVAL}s)")
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="🤖 <b>Coin Scanner Started</b>\n\n"
                 f"⏱ Scanning every {config.SCAN_INTERVAL}s\n"
                 f"📡 DexScreener + GeckoTerminal + Pump.fun\n"
                 f"🔗 Finding tokens with Telegram links...",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Startup msg error: {e}")

    while True:
        try:
            count = await run_scan_cycle(bot)
            if count > 0:
                logger.info(f"Cycle #{scan_count}: posted {count} new tokens")
        except Exception as e:
            logger.error(f"Scan cycle error: {e}")
        await asyncio.sleep(config.SCAN_INTERVAL)


async def post_init(application: Application):
    asyncio.create_task(periodic_scan(application.bot))


def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set! Add it to .env or environment variables.")
        return
    if not config.TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID not set! Add it to .env or environment variables.")
        return

    print("🚀 Starting Coin Scanner Bot...")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("scan", manual_scan_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_command))

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
