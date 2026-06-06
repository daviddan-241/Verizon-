"""
Pump.fun Scanner (V3 API) - Fresh coins ONLY.
Only posts coins created within the last MAX_AGE_MIN minutes.
Validates TG links are real t.me/ links, not scam domains.
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

# Only post coins younger than this (minutes)
MAX_AGE_MIN = 60

# Skip known spam bot TG links
SPAM_TG = {"masslauncherbot", "masslaunchbot", "masslauncher"}


async def scan_pumpfun(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan Pump.fun V3 for BRAND NEW coins with real TG links."""
    tokens = []
    seen = set()
    now_ms = time.time() * 1000

    # Scan latest coins (newest first) - stop when coins are too old
    for offset in range(0, 1000, 50):
        url = f"{BASE}/coins?limit=50&offset={offset}&sort=created_timestamp&order=DESC&includeNsfw=false"
        too_old = False
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    if not isinstance(coins, list) or not coins:
                        break
                    for coin in coins:
                        created = coin.get("created_timestamp", 0)
                        # Handle both ms and seconds timestamps
                        if created < 1e12:
                            created = created * 1000
                        age_min = (now_ms - created) / 60000 if created else 99999

                        # Stop scanning if coins are older than MAX_AGE
                        if age_min > MAX_AGE_MIN:
                            too_old = True
                            break

                        t = _parse(coin, age_min)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
                else:
                    break
        except Exception as e:
            logger.debug(f"Pump.fun page {offset} error: {e}")
            break

        if too_old:
            break

    logger.info(f"Pump.fun: {len(tokens)} fresh tokens with TG (under {MAX_AGE_MIN}min)")
    return tokens


def _parse(coin: dict, age_min: float) -> TokenInfo | None:
    """Parse a pump.fun coin - strict TG validation."""
    try:
        name = (coin.get("name", "") or "").strip()
        symbol = (coin.get("symbol", "") or "").strip()
        mint = coin.get("mint", "")
        tg_raw = (coin.get("telegram", "") or "").strip()
        website = (coin.get("website", "") or "").strip()
        twitter = (coin.get("twitter", "") or "").strip()
        image = (coin.get("image_uri", "") or "").strip()
        description = (coin.get("description", "") or "").strip()

        if not mint or not name:
            return None

        # --- Strict TG validation ---
        tg_link = _validate_tg(tg_raw)

        # Also check description
        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        if not tg_link:
            return None

        # Filter spam TG handles
        tg_handle = tg_link.split("t.me/")[-1].lower().strip("/") if "t.me/" in tg_link else ""
        if tg_handle in SPAM_TG:
            return None

        # Clean website - skip if it's just a social link
        if website:
            if any(x in website for x in ["t.me/", "x.com/", "twitter.com/", "discord.gg/"]):
                website = ""

        # Clean twitter
        if twitter and "t.me/" in twitter:
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


def _validate_tg(raw: str) -> str | None:
    """
    Strictly validate that the TG field is a REAL t.me/ link.
    Reject scam domains, twitter links, random URLs.
    """
    if not raw:
        return None

    raw = raw.strip()

    # REJECT anything that is NOT a telegram link
    # Scammers put random domains like "mistik.best" or "bunox.top" in TG field
    if "x.com" in raw or "twitter.com" in raw or "discord" in raw:
        return None

    # Must contain t.me/ to be valid
    if raw.startswith("https://t.me/") or raw.startswith("http://t.me/"):
        handle = raw.split("t.me/")[1].strip("/")
        if handle and len(handle) >= 2:
            return raw
        return None

    if raw.startswith("t.me/"):
        handle = raw[5:].strip("/")
        if handle and len(handle) >= 2:
            return f"https://{raw}"
        return None

    # @handle format
    if raw.startswith("@") and len(raw) > 2 and "." not in raw:
        return f"https://t.me/{raw[1:]}"

    # Plain handle (no dots, no slashes, no spaces = likely a TG handle)
    if raw and "/" not in raw and " " not in raw and len(raw) >= 3:
        # BUT reject if it has a dot (likely a domain, not a TG handle)
        if "." in raw:
            return None
        return f"https://t.me/{raw}"

    # Try extracting from string
    found = extract_telegram_links(raw)
    return found[0] if found else None
