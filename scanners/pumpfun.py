"""
Pump.fun Scanner - Scans for new Solana meme coins launched on Pump.fun.
Uses Pump.fun's public API and frontend endpoints.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

# Pump.fun endpoints
PUMPFUN_NEW_COINS_URL = "https://frontend-api-v2.pump.fun/coins/latest"
PUMPFUN_COINS_URL = "https://frontend-api-v2.pump.fun/coins"


async def scan_pumpfun(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """
    Scan Pump.fun for newly created coins that have Telegram links.
    """
    tokens = []

    # Try the latest coins endpoint
    try:
        params = {
            "limit": 50,
            "offset": 0,
            "includeNsfw": "false",
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        async with session.get(
            PUMPFUN_COINS_URL,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                coins = data if isinstance(data, list) else data.get("coins", data.get("data", []))
                for coin in coins:
                    token = _parse_pumpfun_coin(coin)
                    if token:
                        tokens.append(token)
            else:
                logger.warning(f"Pump.fun API returned {resp.status}")
    except Exception as e:
        logger.error(f"Pump.fun scan error: {e}")

    # Also try the latest endpoint as backup
    try:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        async with session.get(
            PUMPFUN_NEW_COINS_URL,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                coins = data if isinstance(data, list) else data.get("coins", data.get("data", []))
                for coin in coins:
                    token = _parse_pumpfun_coin(coin)
                    if token:
                        # Avoid duplicates
                        existing_keys = {t.contract_address.lower() for t in tokens}
                        if token.contract_address.lower() not in existing_keys:
                            tokens.append(token)
            else:
                logger.debug(f"Pump.fun latest endpoint returned {resp.status}")
    except Exception as e:
        logger.debug(f"Pump.fun latest scan error: {e}")

    logger.info(f"Pump.fun: found {len(tokens)} tokens with TG links")
    return tokens


def _parse_pumpfun_coin(coin: dict) -> TokenInfo | None:
    """Parse a Pump.fun coin entry and check for Telegram links."""
    try:
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "?")
        mint = coin.get("mint", "") or coin.get("address", "") or coin.get("token_address", "")
        description = coin.get("description", "")
        website = coin.get("website", "")
        telegram = coin.get("telegram", "")
        twitter = coin.get("twitter", "")

        if not mint:
            return None

        tg_link = None

        # Check explicit telegram field
        if telegram:
            if telegram.startswith("http"):
                tg_link = telegram
            elif telegram.startswith("t.me/"):
                tg_link = f"https://{telegram}"
            elif telegram.startswith("@"):
                tg_link = f"https://t.me/{telegram[1:]}"
            else:
                tg_link = f"https://t.me/{telegram}"

        # Check description for TG links
        if not tg_link and description:
            links = extract_telegram_links(description)
            if links:
                tg_link = links[0]

        # Check website for TG links
        if not tg_link and website:
            links = extract_telegram_links(website)
            if links:
                tg_link = links[0]

        if not tg_link:
            return None

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=mint,
            chain="Solana",
            telegram_link=tg_link,
            source="Pump.fun",
            website=website if website else None,
            twitter=twitter if twitter else None,
            pair_url=f"https://pump.fun/{mint}",
        )
    except Exception as e:
        logger.debug(f"Error parsing Pump.fun coin: {e}")
        return None
