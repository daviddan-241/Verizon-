"""
GeckoTerminal Scanner
Gets fresh token addresses from new pools, then uses DexScreener
to fetch full token info (name, symbol, image, TG, socials).
"""
import logging
import asyncio
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

NETWORKS = [
    ("solana", "solana", "Solana"),
    ("eth", "ethereum", "Ethereum"),
    ("bsc", "bsc", "BSC"),
    ("base", "base", "Base"),
]

HEADERS = {"Accept": "application/json"}


async def scan_geckoterminal(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Get fresh token addresses from GeckoTerminal, lookup details on DexScreener."""
    
    # Step 1: Collect fresh token addresses from new pools
    by_chain: dict[str, list[str]] = {}  # dex_chain -> [addresses]
    
    for gecko_id, dex_id, chain_name in NETWORKS:
        addrs = []
        for page in [1, 2]:
            url = f"https://api.geckoterminal.com/api/v2/networks/{gecko_id}/new_pools?page={page}"
            try:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pool in data.get("data", []):
                            token_id = pool.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                            addr = token_id.split("_")[1] if "_" in token_id else ""
                            if addr and addr not in addrs:
                                addrs.append(addr)
                    elif resp.status == 429:
                        logger.debug(f"GeckoTerminal rate limited on {chain_name}")
                        break
            except Exception as e:
                logger.debug(f"GeckoTerminal {chain_name} page {page} error: {e}")
            await asyncio.sleep(1.5)
        
        if addrs:
            by_chain[dex_id] = addrs

    # Step 2: Batch lookup on DexScreener for full info + socials
    tokens: list[TokenInfo] = []
    seen = set()

    for dex_chain, addrs in by_chain.items():
        chain_name = next((n for g, d, n in NETWORKS if d == dex_chain), dex_chain)
        for i in range(0, len(addrs), 30):
            batch = addrs[i:i + 30]
            url = f"https://api.dexscreener.com/tokens/v1/{dex_chain}/{','.join(batch)}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        pairs = await resp.json()
                        if isinstance(pairs, list):
                            for pair in pairs:
                                t = _parse_pair(pair, dex_chain, chain_name)
                                if t and t.contract_address.lower() not in seen:
                                    seen.add(t.contract_address.lower())
                                    tokens.append(t)
            except Exception as e:
                logger.debug(f"DexScreener batch lookup error ({dex_chain}): {e}")

    logger.info(f"GeckoTerminal: {len(tokens)} fresh tokens with TG links")
    return tokens


def _parse_pair(pair: dict, chain_id: str, chain_name: str) -> TokenInfo | None:
    """Parse a DexScreener pair for fresh GeckoTerminal token."""
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})

        name = base.get("name", "")
        symbol = base.get("symbol", "")
        address = base.get("address", "")

        if not address or not name:
            return None

        socials = info.get("socials", [])
        image_url = info.get("imageUrl", "")
        websites = info.get("websites", [])

        tg_link = ""
        twitter = ""
        website = ""

        for soc in socials:
            stype = soc.get("type", "").lower()
            surl = soc.get("url", "")
            if stype == "telegram" and surl:
                tg_link = surl
            elif stype == "twitter" and surl:
                twitter = surl

        if websites:
            for w in websites:
                wurl = w.get("url", "") if isinstance(w, dict) else str(w)
                if wurl:
                    website = wurl
                    break

        if not tg_link:
            return None

        if not tg_link.startswith("http"):
            tg_link = f"https://t.me/{tg_link}"

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=address,
            chain=chain_name,
            telegram_link=tg_link,
            source="GeckoTerminal",
            website=website or None,
            twitter=twitter or None,
            image_url=image_url or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except:
        return None
