"""
Extra Scanner - GeckoTerminal trending pools -> DexScreener token details.
"""
import logging
import asyncio
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

TRENDING = [
    ("solana", "solana", "Solana"),
    ("eth", "ethereum", "Ethereum"),
]

HEADERS = {"Accept": "application/json"}


async def scan_extra_sources(session: aiohttp.ClientSession) -> List[TokenInfo]:
    tokens = []
    seen = set()

    for gecko_id, dex_id, chain_name in TRENDING:
        url = f"https://api.geckoterminal.com/api/v2/networks/{gecko_id}/trending_pools"
        addrs = []
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
                    continue
        except:
            pass
        await asyncio.sleep(1.5)

        if not addrs:
            continue

        # Batch lookup on DexScreener
        url = f"https://api.dexscreener.com/tokens/v1/{dex_id}/{','.join(addrs[:30])}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    pairs = await resp.json()
                    if isinstance(pairs, list):
                        for pair in pairs:
                            t = _parse(pair, dex_id, chain_name)
                            if t and t.contract_address.lower() not in seen:
                                seen.add(t.contract_address.lower())
                                tokens.append(t)
        except:
            pass

    logger.info(f"Extra sources: {len(tokens)} tokens with TG links")
    return tokens


def _parse(pair: dict, chain_id: str, chain_name: str) -> TokenInfo | None:
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})
        name = base.get("name", "")
        symbol = base.get("symbol", "")
        address = base.get("address", "")
        if not address or not name:
            return None

        socials = info.get("socials", [])
        tg = next((s.get("url", "") for s in socials if s.get("type") == "telegram"), "")
        if not tg:
            return None
        if not tg.startswith("http"):
            tg = f"https://t.me/{tg}"

        twitter = next((s.get("url", "") for s in socials if s.get("type") == "twitter"), "")
        websites = info.get("websites", [])
        website = websites[0].get("url", "") if websites else ""

        return TokenInfo(
            name=name, symbol=symbol, contract_address=address,
            chain=chain_name, telegram_link=tg, source="Trending",
            website=website or None, twitter=twitter or None,
            image_url=info.get("imageUrl") or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except:
        return None
