"""
Message formatter - Creates caption + inline keyboard buttons.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from scanners.base import TokenInfo


def format_caption(token: TokenInfo) -> str:
    """Short caption for the photo message."""
    lines = [
        f"<b>{token.name}</b> (${token.symbol})",
        f"Chain: {token.chain}",
        f"CA: <code>{token.contract_address}</code>",
    ]
    return "\n".join(lines)


def build_keyboard(token: TokenInfo) -> InlineKeyboardMarkup:
    """Build inline keyboard buttons."""
    rows = []

    # Top row: TG button alone
    rows.append([InlineKeyboardButton("💬 Telegram", url=token.telegram_link)])

    # Second row: Website + Twitter side by side
    second_row = []
    if token.website:
        second_row.append(InlineKeyboardButton("🌐 Website", url=token.website))
    if token.twitter:
        second_row.append(InlineKeyboardButton("𝕏 Twitter", url=token.twitter))
    if second_row:
        rows.append(second_row)

    # Third row: Chart
    if token.pair_url:
        rows.append([InlineKeyboardButton("📊 Chart", url=token.pair_url)])

    return InlineKeyboardMarkup(rows)
