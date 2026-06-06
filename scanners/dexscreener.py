"""
DexScreener Scanner - All chains, FRESH coins only.
Fetches profiles/boosts, batch lookups pair info, filters by age.
Only posts coins created within the last MAX_AGE_MIN.
"""
import logging
import time
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

ENDPOINTS = [
    "https://api.dexscreener.com/token-profiles/latest/v1",
    "https://api.dexscreener.com/token-boosts/latest/v1",
    "https://api.dexscreener.com/token-boosts/top/v1",
]

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# Only post coins younger than this (minutes)
MAX_AGE_MIN = 60


async def scan_dexscreener(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan DexScreener - only fresh tokens with TG."""

    # Step 1: Collect token addresses
    addr_chain: dict[str, str] = {}
    for url in ENDPOINTS:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    items = await resp.json()
                    if isinstance(items, list):
                        for item in items:
                            addr = item.get("tokenAddress", "")
                            chain = item.get("chainId", "")
                            if addr and chain:
                                addr_chain.setdefault(addr, chain)
        except Exception as e:
            logger.error(f"DexScreener error: {e}")

    # Step 2: Group by chain, batch lookup
    by_chain: dict[str, list[str]] = {}
    for addr, chain in addr_chain.items():
        by_chain.setdefault(chain, []).append(addr)

    tokens: list[TokenInfo] = []
    seen = set()
    now_ms = time.time() * 1000

    for chain_id, addrs in by_chain.items():
        for i in range(0, len(addrs), 30):
            batch = addrs[i:i + 30]
            url = f"https://api.dexscreener.com/tokens/v1/{chain_id}/{','.join(batch)}"
            try:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        pairs = await resp.json()
                        if isinstance(pairs, list):
                            for pair in pairs:
                                t = _parse_pair(pair, chain_id, now_ms)
                                if t and t.contract_address.lower() not in seen:
                                    seen.add(t.contract_address.lower())
                                    tokens.append(t)
            except Exception as e:
                logger.debug(f"DexScreener batch error ({chain_id}): {e}")

    logger.info(f"DexScreener: {len(tokens)} fresh tokens with TG (under {MAX_AGE_MIN}min)")
    return tokens


def _parse_pair(pair: dict, chain_id: str, now_ms: float) -> TokenInfo | None:
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})

        name = base.get("name", "")
        symbol = base.get("symbol", "")
        address = base.get("address", "")
        if not address or not name:
            return None

        # --- AGE CHECK: Skip old coins ---
        created = pair.get("pairCreatedAt", 0)
        if created:
            age_min = (now_ms - created) / 60000
            if age_min > MAX_AGE_MIN:
                return None

        # --- Get TG from socials ---
        socials = info.get("socials", [])
        image_url = info.get("imageUrl", "")
        websites = info.get("websites", [])

        tg = ""
        twitter = ""
        website = ""

        for soc in socials:
            st = soc.get("type", "").lower()
            su = soc.get("url", "")
            if st == "telegram" and su:
                tg = su
            elif st == "twitter" and su:
                twitter = su

        if websites:
            for w in websites:
                wu = w.get("url", "") if isinstance(w, dict) else str(w)
                if wu:
                    website = wu
                    break

        if not tg:
            desc = info.get("description", "") or ""
            found = extract_telegram_links(desc)
            if found:
                tg = found[0]

        if not tg:
            return None
        if not tg.startswith("http"):
            tg = f"https://t.me/{tg}"

        names = {
            "solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
            "arbitrum": "Arbitrum", "polygon": "Polygon", "avalanche": "Avalanche",
            "optimism": "Optimism", "blast": "Blast", "sui": "Sui", "ton": "TON",
            "tron": "Tron", "linea": "Linea", "cronos": "Cronos",
        }
        chain_name = names.get(chain_id.lower(), chain_id.capitalize())

        return TokenInfo(
            name=name, symbol=symbol, contract_address=address,
            chain=chain_name, telegram_link=tg, source="DexScreener",
            website=website or None, twitter=twitter or None,
            image_url=image_url or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except:
        return None
