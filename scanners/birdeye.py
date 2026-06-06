"""
Extra Sources Scanner - GeckoTerminal trending pools (limited to avoid rate limits).
"""
import logging
import asyncio
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

# Only 2 trending sources to avoid rate limits
GECKO_TRENDING = [
    ("solana", "Solana"),
    ("eth", "Ethereum"),
]

HEADERS = {"Accept": "application/json"}


async def scan_extra_sources(session: aiohttp.ClientSession) -> List[TokenInfo]:
    tokens = []
    seen = set()

    for net_id, chain in GECKO_TRENDING:
        url = f"https://api.geckoterminal.com/api/v2/networks/{net_id}/trending_pools"
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pools = data.get("data", [])
                    for pool in pools:
                        t = await _parse_trending(session, pool, net_id, chain)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
                elif resp.status == 429:
                    break
        except Exception as e:
            logger.debug(f"Trending {chain} error: {e}")
        await asyncio.sleep(1)

    logger.info(f"Extra sources: {len(tokens)} tokens with TG links")
    return tokens


async def _parse_trending(session, pool: dict, net_id: str, chain_name: str) -> TokenInfo | None:
    try:
        attrs = pool.get("attributes", {})
        relationships = pool.get("relationships", {})
        pool_id = pool.get("id", "")

        name = attrs.get("name", "Unknown")
        token_name = name.split("/")[0].strip() if "/" in name else name

        pool_address = pool_id.split("_")[1] if "_" in pool_id else ""

        base_token = relationships.get("base_token", {}).get("data", {})
        token_id = base_token.get("id", "")
        token_address = token_id.split("_")[1] if "_" in token_id else ""

        if not token_address or not net_id:
            return None

        tg_link = await _fetch_tg(session, net_id, token_address)
        if not tg_link:
            return None

        return TokenInfo(
            name=token_name,
            symbol=token_name,
            contract_address=token_address,
            chain=chain_name,
            telegram_link=tg_link,
            source="Trending",
            pair_url=f"https://www.geckoterminal.com/{net_id}/pools/{pool_address}",
        )
    except:
        return None


async def _fetch_tg(session, network: str, token_address: str) -> str | None:
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}/info"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                attrs = data.get("data", {}).get("attributes", {})
                tg = attrs.get("telegram_handle", "")
                if tg:
                    return f"https://t.me/{tg}"
                desc = attrs.get("description", "")
                sites = str(attrs.get("websites", []))
                links = extract_telegram_links(f"{desc} {sites}")
                if links:
                    return links[0]
    except:
        pass
    return None
