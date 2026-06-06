"""
DexScreener Scanner - Scans boosts + profiles, fetches real token name/symbol/image.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, find_tg_in_socials, extract_telegram_links

logger = logging.getLogger(__name__)

BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
TOKEN_URL = "https://api.dexscreener.com/tokens/v1"

CHAIN_MAP = {
    "solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
    "arbitrum": "Arbitrum", "polygon": "Polygon", "avalanche": "Avalanche",
    "optimism": "Optimism", "fantom": "Fantom", "cronos": "Cronos",
    "pulsechain": "PulseChain", "blast": "Blast", "sui": "Sui", "ton": "TON",
    "tron": "Tron", "linea": "Linea", "mantle": "Mantle", "scroll": "Scroll",
    "zksync": "zkSync", "celo": "Celo", "aptos": "Aptos", "sei": "Sei",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


async def scan_dexscreener(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan DexScreener boosts + profiles, fetch real names via token lookup."""
    raw_items = []
    seen_addr = set()

    # 1) Boosts
    try:
        async with session.get(BOOSTS_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        addr = item.get("tokenAddress", "").lower()
                        if addr and addr not in seen_addr:
                            seen_addr.add(addr)
                            raw_items.append(item)
    except Exception as e:
        logger.error(f"DexScreener boosts error: {e}")

    # 2) Profiles
    try:
        async with session.get(PROFILES_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        addr = item.get("tokenAddress", "").lower()
                        if addr and addr not in seen_addr:
                            seen_addr.add(addr)
                            raw_items.append(item)
    except Exception as e:
        logger.error(f"DexScreener profiles error: {e}")

    # Filter items that have TG links first
    tg_items = []
    for item in raw_items:
        links = item.get("links", [])
        description = item.get("description", "")
        header = item.get("header", "")

        tg_link = find_tg_in_socials(links)
        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]
        if not tg_link and header:
            found = extract_telegram_links(header)
            if found:
                tg_link = found[0]

        if tg_link:
            item["_tg_link"] = tg_link
            tg_items.append(item)

    # 3) Batch fetch real token names/symbols via DexScreener token lookup
    # Group by chain for batch lookup
    chain_groups = {}
    for item in tg_items:
        chain_id = item.get("chainId", "")
        addr = item.get("tokenAddress", "")
        if chain_id and addr:
            chain_groups.setdefault(chain_id, []).append(item)

    token_details = {}  # addr_lower -> {name, symbol, image, price, mcap, ...}

    for chain_id, items in chain_groups.items():
        addrs = [it.get("tokenAddress", "") for it in items]
        # DexScreener allows comma-separated addresses (up to 30)
        addr_str = ",".join(addrs[:30])
        try:
            url = f"{TOKEN_URL}/{chain_id}/{addr_str}"
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    pairs = await resp.json()
                    if isinstance(pairs, list):
                        for pair in pairs:
                            base = pair.get("baseToken", {})
                            addr_low = base.get("address", "").lower()
                            if addr_low and addr_low not in token_details:
                                token_details[addr_low] = {
                                    "name": base.get("name", ""),
                                    "symbol": base.get("symbol", ""),
                                    "image": pair.get("info", {}).get("imageUrl", ""),
                                }
        except Exception as e:
            logger.debug(f"Token lookup error for {chain_id}: {e}")

    # 4) Build final TokenInfo list
    tokens = []
    for item in tg_items:
        chain_id = item.get("chainId", "unknown")
        addr = item.get("tokenAddress", "")
        tg_link = item.get("_tg_link", "")
        chain_name = CHAIN_MAP.get(chain_id.lower(), chain_id.capitalize())

        # Get real name/symbol from token lookup
        details = token_details.get(addr.lower(), {})
        name = details.get("name", "") or item.get("name", "") or item.get("tokenName", "")
        symbol = details.get("symbol", "") or item.get("symbol", "") or item.get("tokenSymbol", "")
        image_url = details.get("image", "") or item.get("icon", "")

        if not name:
            name = "Unknown"
        if not symbol:
            symbol = "?"

        # Extract website and twitter from links
        website = None
        twitter = None
        links = item.get("links", [])
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    ltype = (link.get("type", "") or link.get("label", "")).lower()
                    url = link.get("url", "")
                    if any(w in ltype for w in ["website", "web"]):
                        website = url
                    elif any(w in ltype for w in ["twitter", "x"]):
                        twitter = url

        tokens.append(TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=addr,
            chain=chain_name,
            telegram_link=tg_link,
            source="DexScreener",
            website=website,
            twitter=twitter,
            image_url=image_url if image_url else None,
            pair_url=f"https://dexscreener.com/{chain_id}/{addr}",
        ))

    logger.info(f"DexScreener: {len(tokens)} tokens with TG links")
    return tokens
