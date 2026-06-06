"""Base scanner class - token model and TG link extraction."""
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

TG_LINK_PATTERNS = [
    re.compile(r'https?://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
    re.compile(r'https?://telegram\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
    re.compile(r't\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
]

# Skip these - not real TG groups
SKIP_HANDLES = {
    'joinchat', 'addstickers', 'share', 'proxy', 'socks', 'iv',
    'addtheme', 'setlanguage', 'addlist', 'boost', 'contact',
}


@dataclass
class TokenInfo:
    name: str
    symbol: str
    contract_address: str
    chain: str
    telegram_link: str
    source: str
    website: Optional[str] = None
    twitter: Optional[str] = None
    image_url: Optional[str] = None
    liquidity_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    pair_url: Optional[str] = None

    @property
    def unique_key(self) -> str:
        return f"{self.chain}:{self.contract_address}".lower()


def extract_telegram_links(text: str) -> list[str]:
    """Extract Telegram group/channel links from text."""
    links = []
    if not text:
        return links
    for pattern in TG_LINK_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if match.lower() in SKIP_HANDLES:
                continue
            # Skip if it contains paths like addstickers/xxx
            if '/' in match:
                continue
            link = f"https://t.me/{match}"
            if link not in links:
                links.append(link)
    return links


def find_tg_in_socials(socials_data) -> Optional[str]:
    """Find a Telegram link in various social data formats."""
    if not socials_data:
        return None

    if isinstance(socials_data, str):
        links = extract_telegram_links(socials_data)
        return links[0] if links else None

    if isinstance(socials_data, list):
        for social in socials_data:
            if isinstance(social, dict):
                stype = social.get("type", "").lower()
                url = social.get("url", "")
                if stype == "telegram" and url:
                    # Validate it's not a skip handle
                    if not url.startswith("http"):
                        url = f"https://t.me/{url}"
                    links = extract_telegram_links(url)
                    if links:
                        return links[0]
                    # If extract didn't find it but type is telegram, use raw
                    return url
        full_text = str(socials_data)
        links = extract_telegram_links(full_text)
        return links[0] if links else None

    if isinstance(socials_data, dict):
        for key in ['telegram', 'tg', 'telegramUrl', 'telegram_url']:
            val = socials_data.get(key)
            if val:
                if not val.startswith("http"):
                    val = f"https://t.me/{val}"
                links = extract_telegram_links(val)
                if links:
                    return links[0]
                return val
        full_text = str(socials_data)
        links = extract_telegram_links(full_text)
        return links[0] if links else None

    return None
