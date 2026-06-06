"""
Persistent seen-tokens database.
Uses a file in the app directory (not /tmp/) so it survives within a deploy.
Also tracks TG links AND token names to catch all duplicates.
"""
import os
import json
import time
import logging

logger = logging.getLogger(__name__)

# Use /data/ in Docker, fallback to app dir locally
DB_FILE = os.getenv("SEEN_DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_tokens.json"))
MAX_AGE_HOURS = 48
MAX_ENTRIES = 30000

_addrs: dict[str, float] = {}
_tg_links: dict[str, float] = {}
_names: dict[str, float] = {}
_loaded = False


def _load():
    global _addrs, _tg_links, _names, _loaded
    if _loaded:
        return
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _addrs = data.get("addrs", {})
                _tg_links = data.get("tg", {})
                _names = data.get("names", {})
                if not any(k in data for k in ("addrs", "tg", "names")):
                    _addrs = data
            logger.info(f"Loaded {len(_addrs)} addrs, {len(_tg_links)} tg, {len(_names)} names")
    except Exception as e:
        logger.warning(f"Load DB error: {e}")
    _loaded = True


def _save():
    try:
        with open(DB_FILE, "w") as f:
            json.dump({"addrs": _addrs, "tg": _tg_links, "names": _names}, f)
    except Exception as e:
        logger.warning(f"Save DB error: {e}")


def _cleanup():
    global _addrs, _tg_links, _names
    cutoff = time.time() - (MAX_AGE_HOURS * 3600)
    _addrs = {k: v for k, v in _addrs.items() if v > cutoff}
    _tg_links = {k: v for k, v in _tg_links.items() if v > cutoff}
    _names = {k: v for k, v in _names.items() if v > cutoff}
    for d in (_addrs, _tg_links, _names):
        if len(d) > MAX_ENTRIES:
            items = sorted(d.items(), key=lambda x: x[1], reverse=True)
            d.clear()
            d.update(dict(items[:MAX_ENTRIES]))


def _tg_key(tg_link: str) -> str:
    if "t.me/" in tg_link:
        return tg_link.split("t.me/")[-1].strip("/").lower()
    return tg_link.strip("/").lower()


def _name_key(name: str, symbol: str) -> str:
    return f"{name.lower().strip()}|{symbol.lower().strip()}"


def is_seen(contract_address: str, tg_link: str = "", name: str = "", symbol: str = "") -> bool:
    _load()
    if contract_address.lower() in _addrs:
        return True
    if tg_link:
        tk = _tg_key(tg_link)
        if tk and tk in _tg_links:
            return True
    if name and symbol:
        nk = _name_key(name, symbol)
        if nk in _names:
            return True
    return False


def mark_seen(contract_address: str, tg_link: str = "", name: str = "", symbol: str = ""):
    _load()
    now = time.time()
    _addrs[contract_address.lower()] = now
    if tg_link:
        tk = _tg_key(tg_link)
        if tk:
            _tg_links[tk] = now
    if name and symbol:
        _names[_name_key(name, symbol)] = now
    if (len(_addrs) + len(_tg_links)) % 50 == 0:
        _cleanup()
    _save()


def seen_count() -> int:
    _load()
    return len(_addrs)


def clear_all():
    global _addrs, _tg_links, _names
    _addrs = {}
    _tg_links = {}
    _names = {}
    _save()
