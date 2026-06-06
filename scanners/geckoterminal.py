"""
GeckoTerminal Scanner - Scans new pools on top chains only (avoid rate limits).
"""
import logging
import asyncio
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

# Only scan top 4 chains to avoid rate limits (free API = 30 req/min)
NETWORKS = [
    ("solana", "Solana"),
    ("eth", "Ethereum"),
    ("bsc", "BSC"),
    ("base", "Base"),
]

HEADERS = {"Accept": "application/json"}


async def scan_geckoterminal(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan GeckoTerminal new pools for tokens with TG links."""
    tokens = []
    seen = set()

    for net_id, net_name in NETWORKS:
        url = f"https://api.geckoterminal.com/api/v2/networks/{net_id}/new_pools?page=1"
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pools = data.get("data", [])
                    for pool in pools:
                        t = await _process_pool(session, pool, net_id, net_name)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
                elif resp.status == 429:
                    logger.warning(f"GeckoTerminal rate limited on {net_name}, skipping rest")
                    break
        except Exception as e:
            logger.debug(f"GeckoTerminal {net_id} error: {e}")

        # Small delay between chain requests
        await asyncio.sleep(1)

    logger.info(f"GeckoTerminal: {len(tokens)} tokens with TG links")
    return tokens


async def _process_pool(session, pool: dict, net_id: str, net_name: str) -> TokenInfo | None:
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

        if not token_address:
            return None

        tg_link = await _get_token_tg(session, net_id, token_address)
        if not tg_link:
            return None

        return TokenInfo(
            name=token_name,
            symbol=token_name,
            contract_address=token_address,
            chain=net_name,
            telegram_link=tg_link,
            source="GeckoTerminal",
            pair_url=f"https://www.geckoterminal.com/{net_id}/pools/{pool_address}",
        )
    except Exception as e:
        logger.debug(f"GeckoTerminal pool parse error: {e}")
        return None


async def _get_token_tg(session, network: str, token_address: str) -> str | None:
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
