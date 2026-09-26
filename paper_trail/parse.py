"""Reads the folder of papers into something I can work with.

A "paper" here is just a markdown file with a few lines of front matter at the
top. I am after the graph, not PDF scraping, so the input is something I can
type in half a minute while I am reading the thing anyway.

    ---
    id: batchnorm2015
    title: Batch Normalization
    authors: Ioffe, Szegedy
    year: 2015
    cites: sgd1998, covariate2014
    ---

    We show that normalising layer inputs allows much higher learning rates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .text import sentences

FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
INLINE_CITE_RE = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")

# Sentences where the paper is actually claiming something, which is what
# everyone else ends up leaning on.
CLAIM_PATTERNS = [
    (re.compile(r"\bwe (show|find|prove|observe|demonstrate|report)\b", re.I), "result"),
    (re.compile(r"\b(outperform|improves?|reduces?|achieves?|yields?|beats)\b", re.I), "result"),
    (re.compile(r"\bstate[- ]of[- ]the[- ]art\b", re.I), "result"),
    (re.compile(r"\bwe (introduce|propose|present|describe)\b", re.I), "method"),
    (re.compile(r"\b(however|but|fails?|cannot|does not|limitation|caveat|unclear)\b", re.I),
     "limitation"),
]


@dataclass
class Claim:
    kind: str
    text: str


@dataclass
class Paper:
    id: str
    title: str
    path: str = ""
    authors: str = ""
    year: int | None = None
    cites: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    body: str = ""

    @property
    def label(self) -> str:
        return f"{self.title} ({self.year})" if self.year else self.title

    def claims_of(self, kind: str) -> list[Claim]:
        return [c for c in self.claims if c.kind == kind]


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields, text[m.end():]


def split_list(value: str) -> list[str]:
    value = value.strip().strip("[]")
    return [v.strip() for v in re.split(r"[,\s]+", value) if v.strip()]


def extract_claims(body: str) -> list[Claim]:
    found: list[Claim] = []
    for sent in sentences(body):
        for pattern, kind in CLAIM_PATTERNS:
            if pattern.search(sent):
                found.append(Claim(kind, " ".join(sent.split())))
                break          # one sentence, one claim - first pattern wins
    return found


def parse_text(text: str, *, fallback_id: str = "", path: str = "") -> Paper:
    fields, body = parse_front_matter(text)
    cites = split_list(fields.get("cites", ""))
    cites += INLINE_CITE_RE.findall(body)      # I also write [[key]] mid-sentence
    seen, ordered = set(), []
    for c in cites:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    year = fields.get("year", "")
    return Paper(
        id=fields.get("id") or fallback_id,
        title=fields.get("title") or fallback_id,
        path=path,
        authors=fields.get("authors", ""),
        year=int(year) if year.isdigit() else None,
        cites=ordered,
        claims=extract_claims(body),
        body=body.strip(),
    )


def read_folder(folder: str | Path) -> list[Paper]:
    root = Path(folder)
    papers: list[Paper] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".md", ".txt", ".markdown"} or not path.is_file():
            continue
        papers.append(
            parse_text(
                path.read_text(encoding="utf-8", errors="replace"),
                fallback_id=path.stem,
                path=str(path),
            )
        )
    return papers
