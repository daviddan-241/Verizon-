"""
GeckoTerminal Scanner - Scans for new pools across all networks.
Uses GeckoTerminal's public API.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, find_tg_in_socials, extract_telegram_links

logger = logging.getLogger(__name__)

# GeckoTerminal API - new pools across all networks
GECKO_NEW_POOLS_URL = "https://api.geckoterminal.com/api/v2/networks/trending_pools"
GECKO_NEW_POOLS_MULTI = [
    "https://api.geckoterminal.com/api/v2/networks/solana/new_pools",
    "https://api.geckoterminal.com/api/v2/networks/eth/new_pools",
    "https://api.geckoterminal.com/api/v2/networks/bsc/new_pools",
    "https://api.geckoterminal.com/api/v2/networks/base/new_pools",
    "https://api.geckoterminal.com/api/v2/networks/arbitrum/new_pools",
    "https://api.geckoterminal.com/api/v2/networks/ton/new_pools",
]

CHAIN_NAME_MAP = {
    "solana": "Solana",
    "eth": "Ethereum",
    "bsc": "BSC",
    "base": "Base",
    "arbitrum": "Arbitrum",
    "polygon_pos": "Polygon",
    "avax": "Avalanche",
    "optimism": "Optimism",
    "fantom": "Fantom",
    "ton": "TON",
}

HEADERS = {
    "Accept": "application/json",
}


async def scan_geckoterminal(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """
    Scan GeckoTerminal for new pools and check for Telegram links.
    """
    tokens = []

    for url in GECKO_NEW_POOLS_MULTI:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pools = data.get("data", [])
                    for pool in pools:
                        token = await _parse_pool(session, pool)
                        if token:
                            tokens.append(token)
                elif resp.status == 429:
                    logger.warning("GeckoTerminal rate limited, backing off")
                    break
                else:
                    logger.warning(f"GeckoTerminal {url} returned {resp.status}")
        except Exception as e:
            logger.error(f"GeckoTerminal scan error for {url}: {e}")

    logger.info(f"GeckoTerminal: found {len(tokens)} tokens with TG links")
    return tokens


async def _parse_pool(session: aiohttp.ClientSession, pool: dict) -> TokenInfo | None:
    """Parse a pool and check for Telegram links in token info."""
    try:
        attrs = pool.get("attributes", {})
        relationships = pool.get("relationships", {})
        pool_id = pool.get("id", "")  # format: "network_pooladdress"

        name = attrs.get("name", "Unknown")
        # Pool name is usually "TOKEN/WETH" - extract the token part
        token_name = name.split("/")[0].strip() if "/" in name else name

        # Get the network from pool id
        network = pool_id.split("_")[0] if "_" in pool_id else "unknown"
        chain_name = CHAIN_NAME_MAP.get(network, network.capitalize())

        # Get token address from the pool data
        # GeckoTerminal pool id format: network_poolAddress
        pool_address = pool_id.split("_")[1] if "_" in pool_id else ""

        # Check if there's a Telegram link in the description or attributes
        description = attrs.get("description", "")
        tg_link = None

        if description:
            links = extract_telegram_links(description)
            if links:
                tg_link = links[0]

        # Try to get token info with socials from the token endpoint
        if not tg_link:
            base_token = relationships.get("base_token", {}).get("data", {})
            token_id = base_token.get("id", "")  # format: network_tokenAddress

            if token_id:
                token_address = token_id.split("_")[1] if "_" in token_id else ""
                tg_link = await _fetch_token_socials(session, network, token_address)

                if tg_link and token_address:
                    return TokenInfo(
                        name=token_name,
                        symbol=token_name,
                        contract_address=token_address,
                        chain=chain_name,
                        telegram_link=tg_link,
                        source="GeckoTerminal",
                        pair_url=f"https://www.geckoterminal.com/{network}/pools/{pool_address}",
                    )

        if tg_link and pool_address:
            # Use pool address as fallback
            base_token = relationships.get("base_token", {}).get("data", {})
            token_id = base_token.get("id", "")
            token_address = token_id.split("_")[1] if "_" in token_id else pool_address

            return TokenInfo(
                name=token_name,
                symbol=token_name,
                contract_address=token_address,
                chain=chain_name,
                telegram_link=tg_link,
                source="GeckoTerminal",
                pair_url=f"https://www.geckoterminal.com/{network}/pools/{pool_address}",
            )

        return None
    except Exception as e:
        logger.debug(f"Error parsing GeckoTerminal pool: {e}")
        return None


async def _fetch_token_socials(session: aiohttp.ClientSession, network: str, token_address: str) -> str | None:
    """Fetch token info from GeckoTerminal to get social links."""
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}/info"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                attrs = data.get("data", {}).get("attributes", {})

                # Check websites and socials
                websites = attrs.get("websites", [])
                description = attrs.get("description", "")
                telegram_handle = attrs.get("telegram_handle", "")

                if telegram_handle:
                    return f"https://t.me/{telegram_handle}"

                # Check all text for TG links
                all_text = f"{description} {str(websites)}"
                links = extract_telegram_links(all_text)
                if links:
                    return links[0]

            return None
    except Exception as e:
        logger.debug(f"Error fetching token socials: {e}")
        return None
