"""Profile naming for Fellow Espresso Series 1.

Built-in profiles are not returned by the profiles endpoint; they appear only
as ids like "4_classic9bar" in activeProfileId. Ids seen in the Fellow app so
far are listed here; any other id is still shown, with a name derived from it.
"""
from __future__ import annotations

import re
from typing import Any

BUILTIN_PROFILES: dict[str, str] = {
    "4_classic9bar": "Classic 9-Bar",
    "5_lever": "Lever",
    "6_modernarc": "Modern Arc",
}


def builtin_name(profile_id: str) -> str:
    """Readable name for a built-in profile id."""
    if profile_id in BUILTIN_PROFILES:
        return BUILTIN_PROFILES[profile_id]
    slug = re.sub(r"^\d+_", "", profile_id)
    return slug.replace("_", " ").replace("-", " ").title() or profile_id


def profile_options(
    profiles: list[dict[str, Any]], seen_ids: set[str] | None = None
) -> dict[str, str]:
    """Return {display name: profile id} for built-in and account profiles.

    Built-ins come first, then the account's own/Drops profiles. Duplicate
    titles get the roaster (or id) appended so every name is unique.
    """
    options: dict[str, str] = {}

    def add(name: str, pid: str, extra: str | None) -> None:
        if name in options and options[name] != pid:
            name = f"{name} ({extra or pid})"
        if name in options and options[name] != pid:
            name = f"{name} [{pid}]"
        options[name] = pid

    account_ids = {p.get("id") for p in profiles}
    builtin_ids = list(BUILTIN_PROFILES)
    for pid in sorted(seen_ids or ()):
        if pid not in builtin_ids and pid not in account_ids:
            builtin_ids.append(pid)
    for pid in builtin_ids:
        add(builtin_name(pid), pid, None)
    for p in profiles:
        pid = p.get("id")
        if not pid:
            continue
        add(p.get("title") or pid, pid, p.get("roasterName"))
    return options
