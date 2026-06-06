"""
Extra Scanner — DexScreener search for fresh tokens with TG across chains.
Catches coins that didn't appear in profiles/boosts but are searchable.
"""
import logging
import time
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

# Search terms that find tokens with TG links on various chains
SEARCHES = [
    "tg base",
    "tg ethereum",
    "community bsc",
    "telegram arbitrum",
    "t.me polygon",
    "tg solana",
    "launch base telegram",
    "new bsc telegram",
]

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
MAX_AGE_MIN = 180  # 3 hours


async def scan_extra_sources(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Search DexScreener for tokens mentioning TG across chains."""
    tokens = []
    seen = set()
    now_ms = time.time() * 1000

    for query in SEARCHES:
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for pair in data.get("pairs", []):
                        t = _parse(pair, now_ms)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
        except:
            pass

    logger.info(f"Extra search: {len(tokens)} fresh tokens with TG")
    return tokens


def _parse(pair: dict, now_ms: float) -> TokenInfo | None:
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})
        chain_id = pair.get("chainId", "")

        name = base.get("name", "")
        symbol = base.get("symbol", "")
        address = base.get("address", "")
        if not address or not name:
            return None

        # Age check
        created = pair.get("pairCreatedAt", 0)
        if created:
            age_min = (now_ms - created) / 60000
            if age_min > MAX_AGE_MIN:
                return None

        socials = info.get("socials", [])
        tg = next((s.get("url", "") for s in socials if s.get("type") == "telegram"), "")
        if not tg:
            desc = info.get("description", "") or ""
            found = extract_telegram_links(desc)
            if found:
                tg = found[0]
        if not tg:
            return None
        if not tg.startswith("http"):
            tg = f"https://t.me/{tg}"

        twitter = next((s.get("url", "") for s in socials if s.get("type") == "twitter"), "")
        websites = info.get("websites", [])
        website = websites[0].get("url", "") if websites else ""

        names = {
            "solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
            "arbitrum": "Arbitrum", "polygon": "Polygon", "avalanche": "Avalanche",
            "optimism": "Optimism", "blast": "Blast", "sui": "Sui", "ton": "TON",
            "tron": "Tron",
        }
        chain_name = names.get(chain_id.lower(), chain_id.capitalize())

        return TokenInfo(
            name=name, symbol=symbol, contract_address=address,
            chain=chain_name, telegram_link=tg, source="Search",
            website=website or None, twitter=twitter or None,
            image_url=info.get("imageUrl") or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except:
        return None
