"""
GeckoTerminal Scanner — Multi-chain new pools.
Wider coverage: 6 chains, 2 pages each, 3-hour age window.
Uses DexScreener for token enrichment (socials, image).
"""
import logging
import time
import asyncio
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

NETWORKS = [
    ("eth", "ethereum", "Ethereum"),
    ("base", "base", "Base"),
    ("bsc", "bsc", "BSC"),
    ("arbitrum", "arbitrum", "Arbitrum"),
    ("polygon_pos", "polygon", "Polygon"),
    ("solana", "solana", "Solana"),
]

HEADERS = {"Accept": "application/json"}
MAX_AGE_MIN = 180  # 3 hours


async def scan_geckoterminal(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan GeckoTerminal new pools across 6 chains, enrich via DexScreener."""
    by_chain: dict[str, list[str]] = {}

    for gecko_id, dex_id, _ in NETWORKS:
        addrs = []
        for page in [1, 2]:
            url = f"https://api.geckoterminal.com/api/v2/networks/{gecko_id}/new_pools?page={page}"
            try:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pool in data.get("data", []):
                            tid = pool.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                            addr = tid.split("_")[1] if "_" in tid else ""
                            if addr and addr not in addrs:
                                addrs.append(addr)
                    elif resp.status == 429:
                        break
            except:
                pass
            await asyncio.sleep(1.5)

        if addrs:
            existing = by_chain.get(dex_id, [])
            existing.extend(a for a in addrs if a not in existing)
            by_chain[dex_id] = existing

    # Batch lookup on DexScreener
    tokens = []
    seen = set()
    now_ms = time.time() * 1000
    names_map = {d: n for _, d, n in NETWORKS}

    for dex_id, addrs in by_chain.items():
        chain_name = names_map.get(dex_id, dex_id)
        for i in range(0, len(addrs), 30):
            batch = addrs[i:i + 30]
            url = f"https://api.dexscreener.com/tokens/v1/{dex_id}/{','.join(batch)}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        pairs = await resp.json()
                        if isinstance(pairs, list):
                            for pair in pairs:
                                t = _parse(pair, dex_id, chain_name, now_ms)
                                if t and t.contract_address.lower() not in seen:
                                    seen.add(t.contract_address.lower())
                                    tokens.append(t)
            except:
                pass

    logger.info(f"GeckoTerminal: {len(tokens)} fresh tokens with TG")
    return tokens


def _parse(pair: dict, chain_id: str, chain_name: str, now_ms: float) -> TokenInfo | None:
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})
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

        return TokenInfo(
            name=name, symbol=symbol, contract_address=address,
            chain=chain_name, telegram_link=tg, source="New Pair",
            website=website or None, twitter=twitter or None,
            image_url=info.get("imageUrl") or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except:
        return None
