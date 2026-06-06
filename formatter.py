"""
Message formatter - Simple clean Telegram messages.
"""
from scanners.base import TokenInfo


def format_token_message(token: TokenInfo) -> str:
    """Format a token into a simple Telegram message."""

    lines = [
        f"<b>{token.name}</b> (${token.symbol})",
        f"Chain: {token.chain}",
        f"CA: <code>{token.contract_address}</code>",
        f"",
        f"TG: {token.telegram_link}",
    ]

    if token.website:
        lines.append(f"Web: {token.website}")
    if token.twitter:
        lines.append(f"X: {token.twitter}")
    if token.pair_url:
        lines.append(f"Chart: {token.pair_url}")

    return "\n".join(lines)
