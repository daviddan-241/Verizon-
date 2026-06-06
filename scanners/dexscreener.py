"""
DexScreener Scanner
1. Fetches latest boost, profile, and top token addresses
2. Batch lookups via /tokens/v1 to get REAL name, symbol, image, and socials
3. Finds TG links from pair info.socials (the reliable source)
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

ENDPOINTS = [
    "https://api.dexscreener.com/token-boosts/latest/v1",
    "https://api.dexscreener.com/token-profiles/latest/v1",
    "https://api.dexscreener.com/token-boosts/top/v1",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


async def scan_dexscreener(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan DexScreener - get all listed tokens, batch lookup for real info + TG."""
    
    # Step 1: Collect all token addresses from boosts/profiles/top
    addr_chain: dict[str, str] = {}  # address -> chainId
    
    for url in ENDPOINTS:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    items = await resp.json()
                    if isinstance(items, list):
                        for item in items:
                            addr = item.get("tokenAddress", "")
                            chain = item.get("chainId", "")
                            if addr and chain and addr not in addr_chain:
                                addr_chain[addr] = chain
        except Exception as e:
            logger.error(f"DexScreener endpoint error: {e}")

    logger.debug(f"DexScreener: collected {len(addr_chain)} unique token addresses")

    # Step 2: Group by chain for batch lookup
    by_chain: dict[str, list[str]] = {}
    for addr, chain in addr_chain.items():
        by_chain.setdefault(chain, []).append(addr)

    # Step 3: Batch lookup via /tokens/v1/{chain}/{addrs} — returns full pair data with socials
    tokens: list[TokenInfo] = []
    seen = set()

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
                                token = _parse_pair(pair, chain_id)
                                if token and token.contract_address.lower() not in seen:
                                    seen.add(token.contract_address.lower())
                                    tokens.append(token)
            except Exception as e:
                logger.debug(f"DexScreener batch lookup error ({chain_id}): {e}")

    logger.info(f"DexScreener: {len(tokens)} tokens with TG links")
    return tokens


def _parse_pair(pair: dict, chain_id: str) -> TokenInfo | None:
    """Parse a DexScreener pair response - get name, symbol, image, socials."""
    try:
        base = pair.get("baseToken", {})
        info = pair.get("info", {})
        
        name = base.get("name", "")
        symbol = base.get("symbol", "")
        address = base.get("address", "")

        if not address or not name:
            return None

        # Get socials from pair info
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

        # Website
        if websites and isinstance(websites, list):
            for w in websites:
                wurl = w.get("url", "") if isinstance(w, dict) else str(w)
                if wurl:
                    website = wurl
                    break

        # No TG? Check description for TG links
        if not tg_link:
            desc = info.get("description", "") or ""
            found = extract_telegram_links(desc)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        # Ensure full URL
        if tg_link and not tg_link.startswith("http"):
            tg_link = f"https://t.me/{tg_link}"

        chain_name = _chain_name(chain_id)

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=address,
            chain=chain_name,
            telegram_link=tg_link,
            source="DexScreener",
            website=website or None,
            twitter=twitter or None,
            image_url=image_url or None,
            pair_url=f"https://dexscreener.com/{chain_id}/{address}",
        )
    except Exception as e:
        logger.debug(f"Pair parse error: {e}")
        return None


def _chain_name(chain_id: str) -> str:
    names = {
        "solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
        "arbitrum": "Arbitrum", "polygon": "Polygon", "avalanche": "Avalanche",
        "optimism": "Optimism", "fantom": "Fantom", "blast": "Blast", "sui": "Sui",
        "ton": "TON", "tron": "Tron", "linea": "Linea", "cronos": "Cronos",
        "pulsechain": "PulseChain", "mantle": "Mantle", "scroll": "Scroll",
        "zksync": "zkSync", "celo": "Celo", "aptos": "Aptos", "sei": "Sei",
    }
    return names.get(chain_id.lower(), chain_id.capitalize())
