"""Unified webhook notifier: Telegram, Slack, Discord.

All three are fire-and-forget HTTP posts. Each channel is enabled only
when its env var is set:
    TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
    SLACK_WEBHOOK_URL
    DISCORD_WEBHOOK_URL

Posts run on a daemon thread so a slow webhook never blocks a request
thread. Failures are logged at WARN; no retries — these are alerts, not
transactions.
"""
from __future__ import annotations

import logging
import os
import threading
from enum import Enum
from typing import List, Optional

import requests

log = logging.getLogger("notifier")

_HTTP_TIMEOUT = 5.0


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRIT = "crit"


# Discord embed colour per severity.
_DISCORD_COLOR = {
    Severity.INFO: 0x3B82F6,   # blue
    Severity.WARN: 0xF59E0B,   # amber
    Severity.CRIT: 0xEF4444,   # red
}

# Slack colour per severity (sidebar bar).
_SLACK_COLOR = {
    Severity.INFO: "#3b82f6",
    Severity.WARN: "#f59e0b",
    Severity.CRIT: "#ef4444",
}


def _telegram(title: str, body: str, severity: Severity) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    emoji = {"info": "ℹ️", "warn": "⚠️", "crit": "🚨"}[severity.value]
    text = f"{emoji} *{title}*\n{body}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        log.warning("telegram post failed: %s", e)


def _slack(title: str, body: str, severity: Severity) -> None:
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(
            url,
            json={
                "attachments": [{
                    "color": _SLACK_COLOR[severity],
                    "title": title,
                    "text": body,
                    "mrkdwn_in": ["text"],
                }]
            },
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        log.warning("slack post failed: %s", e)


def _discord(title: str, body: str, severity: Severity) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(
            url,
            json={
                "embeds": [{
                    "title": title,
                    "description": body,
                    "color": _DISCORD_COLOR[severity],
                }]
            },
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        log.warning("discord post failed: %s", e)


_CHANNELS: List = [_telegram, _slack, _discord]


def notify(title: str, body: str = "", severity: Severity = Severity.INFO) -> None:
    """Fire-and-forget: dispatch to every configured channel in parallel."""
    for ch in _CHANNELS:
        threading.Thread(target=ch, args=(title, body, severity), daemon=True).start()


def configured_channels() -> List[str]:
    """Which channels have credentials available. Used by /api/health."""
    out: List[str] = []
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        out.append("telegram")
    if os.getenv("SLACK_WEBHOOK_URL"):
        out.append("slack")
    if os.getenv("DISCORD_WEBHOOK_URL"):
        out.append("discord")
    return out


# --- Convenience wrappers for the main alert types -----------------------

def on_kill_switch(reason: str) -> None:
    notify("Kill switch engaged", reason, Severity.CRIT)


def on_signal_flip(ticker: str, action_label: str, confidence: float, source: Optional[str]) -> None:
    notify(
        f"Signal · {ticker} → {action_label}",
        f"confidence `{confidence:.0%}`  ·  source `{source or '-'}`",
        Severity.INFO,
    )


def on_paper_trade(ticker: str, side: str, qty: float, price: float, pnl: Optional[float] = None) -> None:
    body = f"`{side.upper()}` {qty:g} @ ${price:,.2f}"
    if pnl is not None:
        body += f"  · realized pnl `${pnl:+,.2f}`"
    notify(f"Paper trade · {ticker}", body, Severity.INFO)


def on_guardrail_block(ticker: str, code: str, reason: str) -> None:
    notify(f"Order blocked · {ticker}", f"`{code}`\n{reason}", Severity.WARN)
