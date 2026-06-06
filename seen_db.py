"""
Persistent seen-tokens database.
Tracks both contract addresses AND telegram links to prevent duplicates.
Survives Render restarts via JSON file on disk.
"""
import os
import json
import time
import logging

logger = logging.getLogger(__name__)

DB_FILE = os.getenv("SEEN_DB_FILE", "/tmp/seen_tokens.json")
MAX_AGE_HOURS = 24
MAX_ENTRIES = 20000

# addr_lower -> timestamp
_addrs: dict[str, float] = {}
# tg_handle_lower -> timestamp  (to catch same project with diff contract)
_tg_links: dict[str, float] = {}
_loaded = False


def _load():
    global _addrs, _tg_links, _loaded
    if _loaded:
        return
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _addrs = data.get("addrs", {})
                _tg_links = data.get("tg_links", {})
                # Backward compat: old format was just addrs dict
                if "addrs" not in data and "tg_links" not in data:
                    _addrs = data
            logger.info(f"Loaded {len(_addrs)} addrs + {len(_tg_links)} TG links from disk")
    except Exception as e:
        logger.warning(f"Load DB error: {e}")
    _loaded = True


def _save():
    try:
        with open(DB_FILE, "w") as f:
            json.dump({"addrs": _addrs, "tg_links": _tg_links}, f)
    except Exception as e:
        logger.warning(f"Save DB error: {e}")


def _cleanup():
    global _addrs, _tg_links
    now = time.time()
    cutoff = now - (MAX_AGE_HOURS * 3600)
    _addrs = {k: v for k, v in _addrs.items() if v > cutoff}
    _tg_links = {k: v for k, v in _tg_links.items() if v > cutoff}
    # Cap size
    if len(_addrs) > MAX_ENTRIES:
        items = sorted(_addrs.items(), key=lambda x: x[1], reverse=True)
        _addrs = dict(items[:MAX_ENTRIES])
    if len(_tg_links) > MAX_ENTRIES:
        items = sorted(_tg_links.items(), key=lambda x: x[1], reverse=True)
        _tg_links = dict(items[:MAX_ENTRIES])


def _tg_key(tg_link: str) -> str:
    """Normalize TG link to a dedup key."""
    # https://t.me/SomeGroup -> somegroup
    if "t.me/" in tg_link:
        return tg_link.split("t.me/")[-1].strip("/").lower()
    return tg_link.lower()


def is_seen(contract_address: str, tg_link: str = "") -> bool:
    """Check if token or its TG group has been posted."""
    _load()
    addr = contract_address.lower()
    if addr in _addrs:
        return True
    if tg_link:
        tk = _tg_key(tg_link)
        if tk in _tg_links:
            return True
    return False


def mark_seen(contract_address: str, tg_link: str = ""):
    """Mark token + TG as posted."""
    _load()
    now = time.time()
    _addrs[contract_address.lower()] = now
    if tg_link:
        _tg_links[_tg_key(tg_link)] = now
    # Periodic cleanup + save
    if (len(_addrs) + len(_tg_links)) % 20 == 0:
        _cleanup()
    _save()


def seen_count() -> int:
    _load()
    return len(_addrs)


def clear_all():
    global _addrs, _tg_links
    _addrs = {}
    _tg_links = {}
    _save()
