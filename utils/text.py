# utils/text.py
"""
Utility helpers for text / field munging used across the MikroTik Manager app.
"""
from __future__ import annotations

import re


# ────────────────────────────────────────────────────────────────────────────
# Regex constants
# ────────────────────────────────────────────────────────────────────────────
#: 12 hexadecimal characters (after separators have been stripped)
MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")


# ────────────────────────────────────────────────────────────────────────────
# Generic CSV / RouterOS helpers
# ────────────────────────────────────────────────────────────────────────────
def clean_field(value: str | None) -> str:
    """
    Strip surrounding quotes/spaces from a RouterOS field value.

    Returns an empty string if ``value`` is ``None``.
    """
    if value is None:
        return ""
    return value.strip().strip('"').strip("'")


def quote_field(value: str | None) -> str:
    """
    Wrap *value* in double-quotes if it contains a space, comma, or semicolon.
    """
    if value is None:
        return '""'
    value = str(value)
    if any(ch in value for ch in (" ", ",", ";")):
        return f'"{value}"'
    return value


# ────────────────────────────────────────────────────────────────────────────
# MAC-address helpers
# ────────────────────────────────────────────────────────────────────────────
def clean_mac(raw: str) -> str:
    """
    Normalise *raw* to colon-separated upper-case MAC (``AA:BB:CC:DD:EE:FF``).

    Accepts the following user inputs transparently::

        7C:EA:48:05:E5:E4
        7C-EA-48-05-E5-E4
        7CEA4805E5E4
        7c-ea-48-05-e5-e4

    :raises ValueError: if *raw* is not a valid MAC address.
    """
    if not raw:
        raise ValueError("MAC address cannot be empty")

    # Remove any separator characters
    hex_only = re.sub(r"[^0-9A-Fa-f]", "", raw)

    # Validate length/content
    if not MAC_RE.fullmatch(hex_only):
        raise ValueError(f"Invalid MAC address: {raw}")

    # Re-insert colons every two chars and upper-case
    parts = [hex_only[i : i + 2] for i in range(0, 12, 2)]
    return ":".join(parts).upper()


__all__ = [
    "clean_field",
    "quote_field",
    "clean_mac",
]
