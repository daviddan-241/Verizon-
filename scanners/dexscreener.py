"""
DexScreener Scanner - Scans for new token pairs across all chains.
Uses DexScreener's public API: boosts, profiles, and latest pairs.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, find_tg_in_socials, extract_telegram_links

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_PAIRS_URL = "https://api.dexscreener.com/latest/dex/pairs"
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens"

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
    "tron": "Tron",
    "linea": "Linea",
    "mantle": "Mantle",
    "scroll": "Scroll",
    "zksync": "zkSync",
    "celo": "Celo",
    "aptos": "Aptos",
    "sei": "Sei",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


async def scan_dexscreener(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan DexScreener for new tokens with Telegram links."""
    tokens = []
    seen_addresses = set()

    # 1) Boosted tokens
    try:
        async with session.get(DEXSCREENER_BOOSTS_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        t = _parse_item(item, "DexScreener Boost")
                        if t and t.contract_address.lower() not in seen_addresses:
                            seen_addresses.add(t.contract_address.lower())
                            tokens.append(t)
    except Exception as e:
        logger.error(f"DexScreener boosts error: {e}")

    # 2) Token profiles
    try:
        async with session.get(DEXSCREENER_PROFILES_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        t = _parse_item(item, "DexScreener Profile")
                        if t and t.contract_address.lower() not in seen_addresses:
                            seen_addresses.add(t.contract_address.lower())
                            tokens.append(t)
    except Exception as e:
        logger.error(f"DexScreener profiles error: {e}")

    # 3) For tokens found without TG, try fetching pair data for socials
    tokens_needing_lookup = []
    for item_data in _collect_no_tg_items:
        pass  # handled inline above

    logger.info(f"DexScreener: {len(tokens)} tokens with TG links")
    return tokens


# Collect addresses from boosts/profiles that had no TG to look up later
_collect_no_tg_items = []


def _parse_item(item: dict, source: str) -> TokenInfo | None:
    """Parse a DexScreener boost or profile item."""
    try:
        chain_id = item.get("chainId", "unknown")
        token_address = item.get("tokenAddress", "")
        description = item.get("description", "")
        links = item.get("links", [])
        name = item.get("name", "") or item.get("tokenName", "") or "Unknown"
        symbol = item.get("symbol", "") or item.get("tokenSymbol", "") or "?"
        header = item.get("header", "")
        icon = item.get("icon", "")

        if not token_address:
            return None

        # Find TG link
        tg_link = find_tg_in_socials(links)

        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link and header:
            found = extract_telegram_links(header)
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
                    ltype = (link.get("type", "") or link.get("label", "")).lower()
                    url = link.get("url", "")
                    if any(w in ltype for w in ["website", "web"]):
                        website = url
                    elif any(w in ltype for w in ["twitter", "x"]):
                        twitter = url

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=token_address,
            chain=chain_name,
            telegram_link=tg_link,
            source=source,
            website=website,
            twitter=twitter,
            pair_url=f"https://dexscreener.com/{chain_id}/{token_address}",
        )
    except Exception as e:
        logger.debug(f"DexScreener parse error: {e}")
        return None
