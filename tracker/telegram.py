"""Minimal Telegram Bot API client (sendMessage only)."""
from __future__ import annotations

import os

import requests

LIMIT = 4000   # Telegram's hard limit is 4096 characters per message


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    """Split on blank lines so HTML tags (which never span paragraphs) stay balanced."""
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        cand = f"{cur}\n\n{block}" if cur else block
        if len(cand) <= limit:
            cur = cand
            continue
        if cur:
            chunks.append(cur)
        while len(block) > limit:                       # oversized single block: split on lines
            cut = block.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            chunks.append(block[:cut])
            block = block[cut:].lstrip("\n")
        cur = block
    if cur:
        chunks.append(cur)
    return chunks


def send(text: str, token: str | None = None, chat_id: str | None = None) -> None:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set")
    for chunk in split_message(text):
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30, json={
            "chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        })
        if not r.ok:
            raise RuntimeError(f"Telegram sendMessage failed: {r.status_code} {r.text[:300]}")
