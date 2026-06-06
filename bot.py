"""
Telegram Coin Scanner Bot
Scans DexScreener, GeckoTerminal, Pump.fun for new tokens with TG links.
Posts photo + inline buttons to your group.
"""
import logging
import asyncio
import aiohttp
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from server import start_health_server
from formatter import format_caption, build_keyboard
from scanners.base import TokenInfo
from scanners.dexscreener import scan_dexscreener
from scanners.geckoterminal import scan_geckoterminal
from scanners.pumpfun import scan_pumpfun
from scanners.birdeye import scan_extra_sources

logger = logging.getLogger(__name__)

seen_tokens: set[str] = set()
MAX_SEEN = 50000
scan_count = 0
total_posted = 0

# Default placeholder image when token has no icon
DEFAULT_IMAGE = "https://i.ibb.co/4Rz0gJq/coin-placeholder.png"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 <b>Coin Scanner Bot</b>\n\n"
        f"Your Chat ID: <code>{chat_id}</code>\n\n"
        "Scanning for new tokens with TG links.\n\n"
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


async def send_token_message(bot: Bot, token: TokenInfo):
    """Send a token as photo + caption + inline buttons."""
    caption = format_caption(token)
    keyboard = build_keyboard(token)

    image_url = token.image_url or DEFAULT_IMAGE

    try:
        # Try sending with token image
        await bot.send_photo(
            chat_id=config.TELEGRAM_CHAT_ID,
            photo=image_url,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return True
    except Exception as e:
        logger.debug(f"Photo send failed ({e}), trying fallback...")

    # Fallback: try with default image
    if image_url != DEFAULT_IMAGE:
        try:
            await bot.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=DEFAULT_IMAGE,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return True
        except Exception as e2:
            logger.debug(f"Default image also failed ({e2}), sending text only")

    # Final fallback: text message with buttons
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e3:
        logger.error(f"All send methods failed for {token.name}: {e3}")
        return False


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
        success = await send_token_message(bot, token)
        if success:
            posted += 1
            total_posted += 1
            logger.info(f"Posted: {token.name} (${token.symbol}) [{token.chain}] - {token.telegram_link}")
        await asyncio.sleep(1)  # rate limit safety

    # Prune cache
    if len(seen_tokens) > MAX_SEEN:
        excess = len(seen_tokens) - (MAX_SEEN // 2)
        for _ in range(excess):
            seen_tokens.pop()

    return posted


async def periodic_scan(bot: Bot):
    """Background loop."""
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
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        return
    if not config.TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID not set!")
        return

    start_health_server()

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
