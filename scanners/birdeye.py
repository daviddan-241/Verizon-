"""
Extra Scanner - Minimal, just catches trending tokens we might miss.
"""
import logging
import aiohttp
from typing import List
from .base import TokenInfo

logger = logging.getLogger(__name__)


async def scan_extra_sources(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Placeholder - pump.fun and dexscreener cover most fresh coins."""
    # Keeping this minimal to avoid rate limits
    # The pump.fun scanner is the main fresh coin source now
    logger.debug("Extra sources: skipped (pump.fun covers fresh coins)")
    return []
