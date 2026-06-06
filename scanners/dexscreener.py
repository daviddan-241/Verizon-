"""
DexScreener Scanner - Scans for new token pairs across all chains.
Uses DexScreener's public API to find latest boosted/new tokens.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, find_tg_in_socials, extract_telegram_links

logger = logging.getLogger(__name__)

DEXSCREENER_LATEST_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"

CHAIN_MAP = {
    "solana": "Solana",
    "ethereum": "Ethereum",
    "bsc": "BSC",
    "base": "Base",
    "arbitrum": "Arbitrum",
    "polygon": "Polygon",
    "avalanche": "Avalanche",
    "optimism": "Optimism",
    "fantom": "Fantom",
    "cronos": "Cronos",
    "pulsechain": "PulseChain",
    "blast": "Blast",
    "sui": "Sui",
    "ton": "TON",
}


async def scan_dexscreener(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """
    Scan DexScreener for new tokens that have Telegram links.
    Returns a list of TokenInfo objects.
    """
    tokens = []

    # 1) Scan latest boosted tokens
    try:
        async with session.get(DEXSCREENER_LATEST_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        token = _parse_boost_item(item)
                        if token:
                            tokens.append(token)
            else:
                logger.warning(f"DexScreener boosts API returned {resp.status}")
    except Exception as e:
        logger.error(f"DexScreener boosts scan error: {e}")

    # 2) Scan latest token profiles (these often have socials)
    try:
        async with session.get(DEXSCREENER_PROFILES_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        token = _parse_profile_item(item)
                        if token:
                            tokens.append(token)
            else:
                logger.warning(f"DexScreener profiles API returned {resp.status}")
    except Exception as e:
        logger.error(f"DexScreener profiles scan error: {e}")

    logger.info(f"DexScreener: found {len(tokens)} tokens with TG links")
    return tokens


def _parse_boost_item(item: dict) -> TokenInfo | None:
    """Parse a boosted token item from DexScreener."""
    try:
        chain_id = item.get("chainId", "unknown")
        token_address = item.get("tokenAddress", "")
        description = item.get("description", "")
        links = item.get("links", [])
        name = item.get("name", "") or item.get("tokenName", "") or "Unknown"
        symbol = item.get("symbol", "") or item.get("tokenSymbol", "") or "?"

        if not token_address:
            return None

        # Look for TG in links
        tg_link = find_tg_in_socials(links)

        # Also check description
        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        chain_name = CHAIN_MAP.get(chain_id.lower(), chain_id.capitalize())

        # Get website and twitter from links
        website = None
        twitter = None
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    ltype = link.get("type", "").lower() if link.get("type") else link.get("label", "").lower()
                    url = link.get("url", "")
                    if "website" in ltype or "web" in ltype:
                        website = url
                    elif "twitter" in ltype or "x" in ltype:
                        twitter = url

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=token_address,
            chain=chain_name,
            telegram_link=tg_link,
            source="DexScreener (Boost)",
            website=website,
            twitter=twitter,
            pair_url=f"https://dexscreener.com/{chain_id}/{token_address}",
        )
    except Exception as e:
        logger.debug(f"Error parsing DexScreener boost item: {e}")
        return None


def _parse_profile_item(item: dict) -> TokenInfo | None:
    """Parse a token profile item from DexScreener."""
    try:
        chain_id = item.get("chainId", "unknown")
        token_address = item.get("tokenAddress", "")
        description = item.get("description", "")
        links = item.get("links", [])
        name = item.get("name", "") or item.get("tokenName", "") or "Unknown"
        symbol = item.get("symbol", "") or item.get("tokenSymbol", "") or "?"

        if not token_address:
            return None

        # Look for TG in links
        tg_link = find_tg_in_socials(links)

        # Also check description
        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        chain_name = CHAIN_MAP.get(chain_id.lower(), chain_id.capitalize())

        website = None
        twitter = None
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    ltype = link.get("type", "").lower() if link.get("type") else link.get("label", "").lower()
                    url = link.get("url", "")
                    if "website" in ltype or "web" in ltype:
                        website = url
                    elif "twitter" in ltype or "x" in ltype:
                        twitter = url

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=token_address,
            chain=chain_name,
            telegram_link=tg_link,
            source="DexScreener (Profile)",
            website=website,
            twitter=twitter,
            pair_url=f"https://dexscreener.com/{chain_id}/{token_address}",
        )
    except Exception as e:
        logger.debug(f"Error parsing DexScreener profile item: {e}")
        return None
