"""Base scanner class that all scanners inherit from."""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Regex to find Telegram links in text
TG_LINK_PATTERNS = [
    re.compile(r'https?://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
    re.compile(r'https?://telegram\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
    re.compile(r't\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
]


@dataclass
class TokenInfo:
    """Represents a newly found token with a Telegram link."""
    name: str
    symbol: str
    contract_address: str
    chain: str
    telegram_link: str
    source: str  # which scanner found it
    website: Optional[str] = None
    twitter: Optional[str] = None
    liquidity_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    pair_url: Optional[str] = None

    @property
    def unique_key(self) -> str:
        """Unique identifier to avoid duplicate posts."""
        return f"{self.chain}:{self.contract_address}".lower()


def extract_telegram_links(text: str) -> list[str]:
    """Extract all Telegram links from a string."""
    links = []
    if not text:
        return links
    for pattern in TG_LINK_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # Skip common bot/service usernames
            skip = ['joinchat', 'addstickers', 'share', 'proxy', 'socks', 'iv']
            if match.lower() not in skip:
                link = f"https://t.me/{match}"
                if link not in links:
                    links.append(link)
    return links


def find_tg_in_socials(socials_data: dict | list | str | None) -> Optional[str]:
    """
    Try to find a Telegram link in various social data formats.
    Different APIs return socials in different structures.
    """
    if not socials_data:
        return None

    # If it's a string, search directly
    if isinstance(socials_data, str):
        links = extract_telegram_links(socials_data)
        return links[0] if links else None

    # If it's a list of social objects (DexScreener style)
    if isinstance(socials_data, list):
        for social in socials_data:
            if isinstance(social, dict):
                stype = social.get("type", "").lower()
                url = social.get("url", "")
                if stype == "telegram" and url:
                    if not url.startswith("http"):
                        url = f"https://t.me/{url}"
                    return url
                # Also check the url field for TG links
                links = extract_telegram_links(url)
                if links:
                    return links[0]
        # Fallback: search all text
        full_text = str(socials_data)
        links = extract_telegram_links(full_text)
        return links[0] if links else None

    # If it's a dict
    if isinstance(socials_data, dict):
        # Check for explicit telegram key
        for key in ['telegram', 'tg', 'telegramUrl', 'telegram_url']:
            val = socials_data.get(key)
            if val:
                if not val.startswith("http"):
                    val = f"https://t.me/{val}"
                return val
        # Search all values
        full_text = str(socials_data)
        links = extract_telegram_links(full_text)
        return links[0] if links else None

    return None
