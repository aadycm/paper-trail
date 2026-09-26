"""splitting text into sentences
used by the parser and the report"""

from __future__ import annotations

import re

SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}")


def sentences(text: str) -> list[str]:
    return [p.strip() for p in SENT_RE.split(text) if p and p.strip()]


def shorten(text: str, width: int = 96) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= width else clean[: width - 3].rstrip() + "..."
