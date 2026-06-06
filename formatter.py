"""
Message formatter — clean caption + inline keyboard buttons.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from scanners.base import TokenInfo


def format_caption(token: TokenInfo) -> str:
    """Clean caption for photo/text message."""
    return (
        f"<b>{_esc(token.name)}</b> (${_esc(token.symbol)})\n"
        f"🔗 {token.chain}\n"
        f"<code>{token.contract_address}</code>"
    )


def build_keyboard(token: TokenInfo) -> InlineKeyboardMarkup:
    """Inline buttons — TG on top alone, rest below."""
    rows = []

    # Row 1: Telegram alone
    rows.append([InlineKeyboardButton("💬 Telegram", url=token.telegram_link)])

    # Row 2: Website + Twitter side by side (if available)
    row2 = []
    if token.website:
        row2.append(InlineKeyboardButton("🌐 Website", url=token.website))
    if token.twitter:
        row2.append(InlineKeyboardButton("𝕏 Twitter", url=token.twitter))
    if row2:
        rows.append(row2)

    # Row 3: Chart + Scan
    row3 = []
    if token.pair_url:
        row3.append(InlineKeyboardButton("📊 Chart", url=token.pair_url))
    # Add a DexScreener link for easy lookup
    dex_url = f"https://dexscreener.com/solana/{token.contract_address}" if token.chain == "Solana" else token.pair_url
    if dex_url and dex_url != token.pair_url:
        row3.append(InlineKeyboardButton("🔍 DexScreener", url=dex_url))
    if row3:
        rows.append(row3)

    return InlineKeyboardMarkup(rows)


def _esc(text: str) -> str:
    """Escape HTML special chars."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
