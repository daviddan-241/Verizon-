"""
Pump.fun Scanner - Scans new Solana meme coins on Pump.fun.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


async def scan_pumpfun(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan Pump.fun for new coins with Telegram links."""
    tokens = []
    seen = set()

    urls = [
        ("https://frontend-api-v2.pump.fun/coins/latest", {}),
        ("https://frontend-api-v2.pump.fun/coins", {
            "limit": "50", "offset": "0",
            "sort": "created_timestamp", "order": "DESC",
            "includeNsfw": "false",
        }),
    ]

    for url, params in urls:
        try:
            async with session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    coins = data if isinstance(data, list) else data.get("coins", data.get("data", []))
                    if isinstance(coins, list):
                        for coin in coins:
                            t = _parse_coin(coin)
                            if t and t.contract_address.lower() not in seen:
                                seen.add(t.contract_address.lower())
                                tokens.append(t)
        except Exception as e:
            logger.debug(f"Pump.fun {url} error: {e}")

    logger.info(f"Pump.fun: {len(tokens)} tokens with TG links")
    return tokens


def _parse_coin(coin: dict) -> TokenInfo | None:
    try:
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "?")
        mint = coin.get("mint", "") or coin.get("address", "") or coin.get("token_address", "")
        description = coin.get("description", "")
        website = coin.get("website", "")
        telegram = coin.get("telegram", "")
        twitter = coin.get("twitter", "")
        image_uri = coin.get("image_uri", "") or coin.get("uri", "")

        if not mint:
            return None

        tg_link = None

        if telegram:
            if telegram.startswith("http"):
                tg_link = telegram
            elif telegram.startswith("t.me/"):
                tg_link = f"https://{telegram}"
            elif telegram.startswith("@"):
                tg_link = f"https://t.me/{telegram[1:]}"
            else:
                tg_link = f"https://t.me/{telegram}"

        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link and website:
            found = extract_telegram_links(website)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=mint,
            chain="Solana",
            telegram_link=tg_link,
            source="Pump.fun",
            website=website or None,
            twitter=twitter or None,
            image_url=image_uri or None,
            pair_url=f"https://pump.fun/{mint}",
        )
    except Exception as e:
        logger.debug(f"Pump.fun parse error: {e}")
        return None
