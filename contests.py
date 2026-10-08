"""Pure helpers for classifying and formatting Codeforces contests.

No network or Discord imports here on purpose, so the helpers can be
unit-tested without a running bot.
"""

from __future__ import annotations

import datetime

REACTION_EMOJIS = ["🔵", "🟢", "🟡"]
ROLE_NAMES = {"🔵": "Div 1/2", "🟢": "Div 3", "🟡": "Div 4"}


def classify_contest(name: str) -> str | None:
    """Map a contest name to its reaction emoji, or None if not classified."""
    if "Div. 1" in name or "Div. 2" in name or "Div. 1 + Div. 2" in name:
        return "🔵"
    if "Div. 3" in name:
        return "🟢"
    if "Div. 4" in name:
        return "🟡"
    return None


def filter_upcoming(contests: list[dict]) -> list[tuple[dict, str]]:
    """Keep only classified contests whose phase is BEFORE."""
    upcoming = []
    for contest in contests:
        if contest.get("phase") != "BEFORE":
            continue
        emoji = classify_contest(contest.get("name", ""))
        if emoji is not None:
            upcoming.append((contest, emoji))
    return upcoming


def sort_by_start_time(contests: list[tuple[dict, str]]) -> list[tuple[dict, str]]:
    return sorted(contests, key=lambda x: x[0]["startTimeSeconds"])


def format_start_time(contest: dict) -> str:
    start = datetime.datetime.fromtimestamp(contest["startTimeSeconds"], datetime.timezone.utc)
    return start.strftime("%d/%m %H:%M UTC")


def format_announcement(contest: dict, emoji: str, role_id: int | None = None) -> str:
    role_mention = f"<@&{role_id}>" if role_id else ""
    return (
        f"{role_mention}\n"
        f"📢 New contest detected!\n"
        f"{contest['name']}\n"
        f"Starts: {format_start_time(contest)}\n"
        f"https://codeforces.com/contest/{contest['id']}"
    )


def format_list_entry(contest: dict, emoji: str) -> str:
    division = ROLE_NAMES.get(emoji, "")
    return (
        f"**{contest['name']}** ({division}) — Starts: {format_start_time(contest)}\n"
        f"🔗 https://codeforces.com/contest/{contest['id']}\n"
    )