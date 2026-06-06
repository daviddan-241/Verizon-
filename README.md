# 🚀 Telegram Coin Scanner Bot

A Telegram bot that automatically scans **multiple platforms** for newly launched tokens/coins that have **Telegram group links**, then posts them to your Telegram group.

## 📡 Supported Sources

| Platform | Chains | What it scans |
|----------|--------|--------------|
| **DexScreener** | All chains | Boosted tokens & new token profiles |
| **GeckoTerminal** | SOL, ETH, BSC, Base, Arbitrum, TON | New pools with social links |
| **Pump.fun** | Solana | New meme coin launches |

## 📋 Features

- 🔄 **Auto-scanning** every 30 seconds (configurable)
- 🔗 **Telegram link detection** in descriptions, social fields, and metadata
- 🛡️ **Duplicate prevention** - won't post the same token twice
- 📊 **Multi-source** - scans 3 platforms simultaneously
- 🌐 **All chains** - Solana, Ethereum, BSC, Base, Arbitrum, and more
- ⚡ **Async** - fast, non-blocking scanning
- 🤖 **Bot commands** for manual control

## 🛠️ Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Get Your Group Chat ID

1. Add `@userinfobot` or `@raw_data_bot` to your group
2. Send a message in the group
3. The bot will reply with the chat ID (it starts with `-100...`)
4. Remove the helper bot

### 3. Configure the Bot

```bash
# Copy the example config
cp .env.example .env

# Edit with your values
nano .env
```

Fill in:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=-1001234567890
```

### 4. Install Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 5. Run the Bot

```bash
python bot.py
```

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and available commands |
| `/status` | Show bot status, enabled scanners, and config |
| `/scan` | Trigger an immediate manual scan |
| `/stats` | Show scanning statistics |
| `/clear` | Clear the seen tokens cache |

## ⚙️ Configuration

All settings are in the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | - | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | - | Target group chat ID |
| `SCAN_INTERVAL` | `30` | Seconds between scans |
| `ENABLE_DEXSCREENER` | `true` | Enable DexScreener scanner |
| `ENABLE_GECKOTERMINAL` | `true` | Enable GeckoTerminal scanner |
| `ENABLE_PUMPFUN` | `true` | Enable Pump.fun scanner |
| `MIN_LIQUIDITY` | `0` | Minimum liquidity filter (USD) |
| `LOG_LEVEL` | `INFO` | Logging level |

## 📝 Example Output

When the bot finds a new token with a Telegram link, it posts:

```
🚀 NEW TOKEN WITH TG FOUND 🚀

🟣 Chain: Solana
📛 Name: ExampleCoin
🏷️ Symbol: $EXC
📋 Contract: 7xKXt...abc123

💬 Telegram: https://t.me/ExampleCoinGroup
🌐 Website: https://examplecoin.com
🐦 Twitter: https://twitter.com/examplecoin

📊 View Chart
🔍 Source: Pump.fun

⚠️ DYOR - Not financial advice
```

## 🏃 Running in Production

### Using `screen` or `tmux`:
```bash
screen -S coinbot
python bot.py
# Press Ctrl+A, then D to detach
```

### Using `systemd` (Linux):
```ini
# /etc/systemd/system/coinbot.service
[Unit]
Description=Telegram Coin Scanner Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/telegram-coin-scanner
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable coinbot
sudo systemctl start coinbot
```

### Using Docker:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t coinbot .
docker run -d --env-file .env --name coinbot coinbot
```

## ⚠️ Disclaimer

This bot is for **informational purposes only**. Finding a token with a Telegram group does NOT mean it's legitimate. **Always Do Your Own Research (DYOR)** before interacting with any token. Many new tokens are scams.

## 📄 License

MIT License - Use at your own risk.
