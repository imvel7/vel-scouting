"""Normalize inconsistent position labels from event and lineup datasets."""

from __future__ import annotations

import ast
from typing import Any

_CANONICAL = {
    label.casefold(): label
    for label in (
        "Goalkeeper",
        "Center Back",
        "Left Back",
        "Right Back",
        "Defender",
        "Defensive Midfielder",
        "Central Midfielder",
        "Left Midfielder",
        "Right Midfielder",
        "Midfielder",
        "Attacking Midfielder",
        "Left Winger",
        "Right Winger",
        "Forward",
        "Center Forward",
        "Supporting Striker",
    )
}
_ALIASES = {
    "goal keeper": "Goalkeeper",
}


def normalize_position_labels(value: Any) -> tuple[list[str], list[str]]:
    """Return (recognized canonical labels, unrecognized labels).

    Handles normal strings, Python/JSON-style list strings, and partially
    malformed list strings such as "['Center Back".
    """
    if isinstance(value, (list, tuple, set)):
        recognized: list[str] = []
        unknown: list[str] = []
        for item in value:
            item_recognized, item_unknown = normalize_position_labels(item)
            recognized.extend(item_recognized)
            unknown.extend(item_unknown)
        return _unique(recognized), _unique(unknown)

    if not isinstance(value, str) or not value.strip():
        return [], []

    raw = value.strip()
    candidates: list[str]

    if raw.startswith("[") or raw.endswith("]"):
        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple, set)):
            return normalize_position_labels(parsed)

    # Fallback also repairs truncated list-like strings from the source.
    cleaned = raw.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    candidates = [part.strip() for part in cleaned.split(",") if part.strip()]

    recognized = []
    unknown = []
    for candidate in candidates:
        key = candidate.casefold()
        canonical = _CANONICAL.get(key) or _ALIASES.get(key)
        if canonical:
            recognized.append(canonical)
        else:
            unknown.append(candidate)
    return _unique(recognized), _unique(unknown)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
