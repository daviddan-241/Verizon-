import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Minimum 15s to avoid API rate limits and TG flood
_raw_interval = int(os.getenv("SCAN_INTERVAL", "15"))
SCAN_INTERVAL = max(_raw_interval, 15)

ENABLE_DEXSCREENER = os.getenv("ENABLE_DEXSCREENER", "true").lower() == "true"
ENABLE_GECKOTERMINAL = os.getenv("ENABLE_GECKOTERMINAL", "true").lower() == "true"
ENABLE_PUMPFUN = os.getenv("ENABLE_PUMPFUN", "true").lower() == "true"

MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
