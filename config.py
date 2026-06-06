import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Scanning
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "2"))

# Scanners
ENABLE_DEXSCREENER = os.getenv("ENABLE_DEXSCREENER", "true").lower() == "true"
ENABLE_GECKOTERMINAL = os.getenv("ENABLE_GECKOTERMINAL", "true").lower() == "true"
ENABLE_PUMPFUN = os.getenv("ENABLE_PUMPFUN", "true").lower() == "true"

# Filters
MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", "0"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
