"""
Pump.fun Scanner (V3 API) - THE main source of fresh coins.
Scans latest launches + currently-live for coins with Telegram links.
~40 coins with TG per hour.
"""
import logging
import time
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links

logger = logging.getLogger(__name__)

BASE = "https://frontend-api-v3.pump.fun"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Skip known spam bot TG links
SPAM_TG = {"masslauncherbot", "masslaunchbot", "masslauncher"}


async def scan_pumpfun(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan Pump.fun V3 for brand new coins with TG links."""
    tokens = []
    seen = set()

    # 1) Latest coins (sorted by creation time, newest first) - pages 0-500
    for offset in range(0, 500, 50):
        url = f"{BASE}/coins?limit=50&offset={offset}&sort=created_timestamp&order=DESC&includeNsfw=false"
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    if isinstance(coins, list):
                        for coin in coins:
                            t = _parse(coin)
                            if t and t.contract_address.lower() not in seen:
                                seen.add(t.contract_address.lower())
                                tokens.append(t)
                else:
                    break
        except Exception as e:
            logger.debug(f"Pump.fun page {offset} error: {e}")
            break

    # 2) Currently live (graduated from bonding curve)
    try:
        url = f"{BASE}/coins/currently-live?limit=50&offset=0"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                coins = await resp.json()
                if isinstance(coins, list):
                    for coin in coins:
                        t = _parse(coin)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
    except Exception as e:
        logger.debug(f"Pump.fun currently-live error: {e}")

    logger.info(f"Pump.fun: {len(tokens)} fresh tokens with TG links")
    return tokens


def _parse(coin: dict) -> TokenInfo | None:
    """Parse a pump.fun coin and validate TG link."""
    try:
        name = coin.get("name", "").strip()
        symbol = coin.get("symbol", "").strip()
        mint = coin.get("mint", "")
        tg_raw = (coin.get("telegram", "") or "").strip()
        website = (coin.get("website", "") or "").strip()
        twitter = (coin.get("twitter", "") or "").strip()
        image = (coin.get("image_uri", "") or "").strip()
        description = (coin.get("description", "") or "").strip()

        if not mint or not name:
            return None

        # --- Find and validate TG link ---
        tg_link = _clean_tg(tg_raw)

        # Also check description for TG links
        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        # Filter spam bots
        tg_handle = tg_link.split("t.me/")[-1].lower() if "t.me/" in tg_link else ""
        if tg_handle in SPAM_TG:
            return None

        # Filter TG links that are actually Twitter/X links
        if "x.com" in tg_link or "twitter.com" in tg_link:
            return None

        # Clean up website - skip if it's a TG/X link
        if website and ("t.me/" in website or "x.com/" in website or "twitter.com/" in website):
            website = ""

        # If twitter field is actually a TG link, skip it
        if twitter and ("t.me/" in twitter):
            twitter = ""

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=mint,
            chain="Solana",
            telegram_link=tg_link,
            source="Pump.fun",
            website=website or None,
            twitter=twitter or None,
            image_url=image or None,
            pair_url=f"https://pump.fun/{mint}",
        )
    except Exception as e:
        logger.debug(f"Pump.fun parse error: {e}")
        return None


def _clean_tg(raw: str) -> str | None:
    """Clean and validate a Telegram link."""
    if not raw:
        return None

    raw = raw.strip()

    # Skip non-TG links
    if "x.com" in raw or "twitter.com" in raw or "discord" in raw:
        return None

    # Already a full URL
    if raw.startswith("https://t.me/") or raw.startswith("http://t.me/"):
        return raw
    if raw.startswith("t.me/"):
        return f"https://{raw}"
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"

    # Plain handle
    if raw and "/" not in raw and "." not in raw and " " not in raw:
        return f"https://t.me/{raw}"

    # Try extracting from the string
    found = extract_telegram_links(raw)
    return found[0] if found else None
