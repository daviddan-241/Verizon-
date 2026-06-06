"""
DexTools / Extra Sources Scanner
Scans additional endpoints for new tokens with TG links.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links, find_tg_in_socials

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# DexScreener search for latest pairs on specific chains
DEXSCREENER_LATEST_PAIRS = [
    "https://api.dexscreener.com/latest/dex/pairs/solana",
    "https://api.dexscreener.com/latest/dex/pairs/ethereum",
    "https://api.dexscreener.com/latest/dex/pairs/bsc",
    "https://api.dexscreener.com/latest/dex/pairs/base",
]

# GeckoTerminal trending pools (catches tokens with socials)
GECKO_TRENDING = [
    ("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools", "Solana"),
    ("https://api.geckoterminal.com/api/v2/networks/eth/trending_pools", "Ethereum"),
    ("https://api.geckoterminal.com/api/v2/networks/bsc/trending_pools", "BSC"),
    ("https://api.geckoterminal.com/api/v2/networks/base/trending_pools", "Base"),
    ("https://api.geckoterminal.com/api/v2/networks/ton/trending_pools", "TON"),
    ("https://api.geckoterminal.com/api/v2/networks/arbitrum/trending_pools", "Arbitrum"),
    ("https://api.geckoterminal.com/api/v2/networks/blast/trending_pools", "Blast"),
    ("https://api.geckoterminal.com/api/v2/networks/sui-network/trending_pools", "Sui"),
]


async def scan_extra_sources(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan additional sources for tokens with TG links."""
    tokens = []
    seen = set()

    # Scan GeckoTerminal trending pools
    for url, chain in GECKO_TRENDING:
        try:
            async with session.get(url, headers={"Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pools = data.get("data", [])
                    for pool in pools:
                        t = await _parse_gecko_trending(session, pool, chain)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
        except Exception as e:
            logger.debug(f"Trending {chain} error: {e}")

    logger.info(f"Extra sources: {len(tokens)} tokens with TG links")
    return tokens


async def _parse_gecko_trending(session, pool: dict, chain_name: str) -> TokenInfo | None:
    """Parse a GeckoTerminal trending pool."""
    try:
        attrs = pool.get("attributes", {})
        relationships = pool.get("relationships", {})
        pool_id = pool.get("id", "")
        
        name = attrs.get("name", "Unknown")
        token_name = name.split("/")[0].strip() if "/" in name else name
        
        net_id = pool_id.split("_")[0] if "_" in pool_id else ""
        pool_address = pool_id.split("_")[1] if "_" in pool_id else ""
        
        base_token = relationships.get("base_token", {}).get("data", {})
        token_id = base_token.get("id", "")
        token_address = token_id.split("_")[1] if "_" in token_id else ""
        
        if not token_address or not net_id:
            return None

        # Get token TG
        tg_link = await _fetch_tg(session, net_id, token_address)
        if not tg_link:
            return None

        return TokenInfo(
            name=token_name,
            symbol=token_name,
            contract_address=token_address,
            chain=chain_name,
            telegram_link=tg_link,
            source="GeckoTerminal Trending",
            pair_url=f"https://www.geckoterminal.com/{net_id}/pools/{pool_address}",
        )
    except:
        return None


async def _fetch_tg(session, network: str, token_address: str) -> str | None:
    """Fetch token socials from GeckoTerminal."""
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}/info"
        async with session.get(url, headers={"Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
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
