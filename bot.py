"""
Telegram Coin Scanner Bot
Scans Pump.fun + DexScreener + GeckoTerminal for FRESH coins with TG links.
Posts photo + inline buttons. Persistent dedup survives restarts.
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
import seen_db

logger = logging.getLogger(__name__)

scan_count = 0
total_posted = 0


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 <b>Coin Scanner Bot</b>\n\n"
        f"Chat ID: <code>{cid}</code>\n\n"
        "/status - Bot status\n"
        "/scan - Manual scan\n"
        "/stats - Statistics\n"
        "/clear - Clear cache",
        parse_mode=ParseMode.HTML,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"📊 <b>Status</b>\n"]
    lines.append(f"Interval: {config.SCAN_INTERVAL}s")
    lines.append(f"Cached: {seen_db.seen_count()}")
    lines.append(f"Scans: {scan_count}")
    lines.append(f"Posted: {total_posted}")
    if config.ENABLE_PUMPFUN: lines.append("✅ Pump.fun")
    if config.ENABLE_DEXSCREENER: lines.append("✅ DexScreener")
    if config.ENABLE_GECKOTERMINAL: lines.append("✅ GeckoTerminal")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📈 Scans: {scan_count} | Posted: {total_posted} | Cached: {seen_db.seen_count()}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = seen_db.seen_count()
    seen_db.clear_all()
    await update.message.reply_text(f"🧹 Cleared {c} tokens.")


async def manual_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning...")
    count = await run_scan_cycle(context.bot)
    await update.message.reply_text(f"✅ Found {count} new tokens.")


async def send_token(bot: Bot, token: TokenInfo) -> bool:
    """Send token as photo + caption + inline buttons."""
    caption = format_caption(token)
    keyboard = build_keyboard(token)
    image = token.image_url

    # Try photo with token image
    if image:
        try:
            await bot.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=image, caption=caption,
                parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
            return True
        except:
            pass

    # Fallback: text + buttons
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=caption, parse_mode=ParseMode.HTML,
            reply_markup=keyboard, disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.error(f"Send failed for {token.name}: {e}")
        return False


async def run_scan_cycle(bot: Bot) -> int:
    """Run one scan cycle. Returns number of new tokens posted."""
    global scan_count, total_posted
    scan_count += 1

    all_tokens: list[TokenInfo] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        if config.ENABLE_PUMPFUN:
            tasks.append(scan_pumpfun(session))
        if config.ENABLE_DEXSCREENER:
            tasks.append(scan_dexscreener(session))
        if config.ENABLE_GECKOTERMINAL:
            tasks.append(scan_geckoterminal(session))
        tasks.append(scan_extra_sources(session))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_tokens.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Scanner error: {r}")

    # Deduplicate by contract address (case-insensitive)
    # Keep first occurrence (priority: pump.fun > dexscreener > gecko)
    unique: dict[str, TokenInfo] = {}
    for token in all_tokens:
        addr = token.contract_address.lower()
        if addr not in unique:
            unique[addr] = token

    # Filter already-posted tokens (by address AND by TG link)
    new_tokens = []
    for addr, token in unique.items():
        if not seen_db.is_seen(addr, token.telegram_link):
            new_tokens.append(token)

    # Post new tokens
    posted = 0
    for token in new_tokens:
        ok = await send_token(bot, token)
        if ok:
            seen_db.mark_seen(token.contract_address, token.telegram_link)
            posted += 1
            total_posted += 1
            logger.info(f"✅ {token.name} (${token.symbol}) [{token.chain}] {token.telegram_link}")
        await asyncio.sleep(1.5)

    return posted


async def periodic_scan(bot: Bot):
    """Background scanner loop."""
    logger.info(f"Scanner started — every {config.SCAN_INTERVAL}s")
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="🤖 <b>Coin Scanner Started</b>\n\n"
                 f"⏱ Every {config.SCAN_INTERVAL}s\n"
                 "📡 Pump.fun + DexScreener + GeckoTerminal\n"
                 "🔗 Fresh coins with Telegram links only",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Startup msg error: {e}")

    while True:
        try:
            count = await run_scan_cycle(bot)
            if count > 0:
                logger.info(f"Cycle #{scan_count}: {count} new")
        except Exception as e:
            logger.error(f"Cycle error: {e}")
        await asyncio.sleep(config.SCAN_INTERVAL)


async def post_init(app: Application):
    asyncio.create_task(periodic_scan(app.bot))


def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    )
    for noisy in ("httpx", "httpcore", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("❌ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID!")
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
