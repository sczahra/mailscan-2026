from __future__ import annotations

from datetime import datetime


APP_AUTHOR = "Sczahra"
BUY_ME_A_COFFEE_URL = "https://www.buymeacoffee.com/sczahra"


def copyright_text() -> str:
    return f"Copyright {APP_AUTHOR} {datetime.now().year}"


def support_link_html() -> str:
    return f'<a href="{BUY_ME_A_COFFEE_URL}">Buy me a coffee</a>'
