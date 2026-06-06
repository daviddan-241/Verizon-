# Telegram Coin Scanner Bot

Scans DexScreener, GeckoTerminal, Pump.fun, and trending pools every 2 seconds for new tokens with Telegram links. Posts them to your Telegram group.

## Deploy on Render

1. Create a **Background Worker** on Render
2. Connect this GitHub repo
3. Set runtime to **Docker**
4. Add environment variables:
   - `TELEGRAM_BOT_TOKEN` - from @BotFather
   - `TELEGRAM_CHAT_ID` - your group chat ID

## Run Locally

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with your values
python bot.py
```

## Bot Commands

- `/start` - Info
- `/status` - Status
- `/scan` - Manual scan
- `/stats` - Statistics
- `/clear` - Clear cache
