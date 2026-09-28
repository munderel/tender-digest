"""Decide which notices are IT / cloud work, and which section of the digest each belongs in."""

from __future__ import annotations

import html
import re
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

NOTICE_PAGE = "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/{slug}"

SECTION_BID = "bid"          # open competition: the corp can bid today
SECTION_JOIN = "join"        # a supplier list the corp could apply to join
SECTION_RFI = "rfi"          # request for information: answer to get known
SECTION_HOLDERS = "holders"  # list holders or invited suppliers only: teaming leads


@dataclass(frozen=True)
class Profile:
    prefixes: tuple[str, ...]
    anywhere: re.Pattern | None
    title_only: re.Pattern | None
    exact_words: re.Pattern | None
    exclude: re.Pattern | None
    clearance: re.Pattern | None
    open_methods: frozenset[str]
    join_types: frozenset[str]
    rfi_types: frozenset[str]
    holder_types: frozenset[str]
    holder_title_words: tuple[str, ...]
    closing_soon_days: int
    vehicles: tuple[dict, ...]


def _any(patterns: list[str], flags: int = re.I) -> re.Pattern | None:
    return re.compile("|".join(f"(?:{p})" for p in patterns), flags) if patterns else None


def load_profile(path: Path) -> Profile:
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    kw, sec = cfg.get("keywords", {}), cfg.get("sections", {})
    exact = kw.get("exact_words", [])
    return Profile(
        prefixes=tuple(cfg.get("codes", {}).get("prefixes", [])),
        anywhere=_any(kw.get("anywhere", [])),
        title_only=_any(kw.get("title_only", [])),
        exact_words=_any([rf"\b{re.escape(w)}\b" for w in exact], 0),
        exclude=_any(kw.get("exclude", [])),
        clearance=_any(cfg.get("flags", {}).get("clearance", [])),
        open_methods=frozenset(sec.get("open_methods", [])),
        join_types=frozenset(sec.get("join_types", [])),
        rfi_types=frozenset(sec.get("rfi_types", [])),
        holder_types=frozenset(sec.get("holder_types", [])),
        holder_title_words=tuple(sec.get("holder_title_words", [])),
        closing_soon_days=int(sec.get("closing_soon_days", 5)),
        vehicles=tuple(cfg.get("vehicles", [])),
    )


def multi(cell: str) -> list[str]:
    """CanadaBuys packs several values in one cell as '*a\\n*b'."""
    return [v.strip().lstrip("*").strip() for v in (cell or "").split("\n") if v.strip().lstrip("*").strip()]


def clean_text(s: str) -> str:
    """Descriptions carry HTML entities and sometimes tags."""
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def notice_url(reference: str) -> str:
    """CanadaBuys page for any notice: lowercase, keep only letters, digits and hyphens.

    Verified 2026-09-28 on cb-, WS-, PW-, SSC- and MX- references. The file's own noticeURL
    is empty for most notices and points at SAP Ariba or MERX for the rest.
    """
    slug = re.sub(r"[^a-z0-9-]", "", reference.lower())
    return NOTICE_PAGE.format(slug=slug)


@dataclass
class Notice:
    reference: str
    amendment: str
    solicitation: str
    title: str
    description: str
    published: str
    closing: str
    notice_type: str
    method: str
    categories: list[str]
    unspsc: list[str]
    unspsc_labels: list[str]
    regions: list[str]
    buyer: str
    url: str
    reasons: list[str] = field(default_factory=list)
    section: str = ""
    needs_clearance: bool = False

    @property
    def key(self) -> str:
        """An amended notice gets a new key, so an amendment shows up as new."""
        return f"{self.reference}|{self.amendment}"

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Notice":
        ref = row["referenceNumber-numeroReference"].strip()
        return cls(
            reference=ref,
            amendment=row["amendmentNumber-numeroModification"].strip(),
            solicitation=row["solicitationNumber-numeroSollicitation"].strip(),
            title=clean_text(row["title-titre-eng"]),
            description=clean_text(row["tenderDescription-descriptionAppelOffres-eng"]),
            published=row["publicationDate-datePublication"].strip()[:10],
            closing=row["tenderClosingDate-appelOffresDateCloture"].strip(),
            notice_type=row["noticeType-avisType-eng"].strip(),
            method=row["procurementMethod-methodeApprovisionnement-eng"].strip(),
            categories=multi(row["procurementCategory-categorieApprovisionnement"]),
            unspsc=multi(row["unspsc"]),
            unspsc_labels=multi(row.get("unspscDescription-eng", "")),
            regions=multi(row["regionsOfDelivery-regionsLivraison-eng"]),
            buyer=clean_text(row["contractingEntityName-nomEntitContractante-eng"]),
            url=notice_url(ref),
        )


def still_open(n: Notice, today: date) -> bool:
    """The file keeps some notices 'Open' long after they closed; those are not actionable."""
    try:
        return date.fromisoformat(n.closing[:10]) >= today
    except ValueError:
        return True


def match_reasons(n: Notice, p: Profile) -> list[str]:
    """Why this notice is IT / cloud work. Empty list = not a match."""
    services = any("SRV" in c for c in n.categories)
    labels = dict(zip(n.unspsc, n.unspsc_labels))
    hits = [c for c in n.unspsc if c.startswith(p.prefixes)]
    # A goods notice with a software code tacked on (lab kit that ships with software)
    # counts only when the software is the first, main code.
    if hits and (services or n.unspsc[0].startswith(p.prefixes)):
        return [f"UNSPSC {c} {labels.get(c, '')}".strip() for c in hits[:3]]

    # Keyword matches count for services only: a goods notice that mentions "cloud"
    # is hardware or lab kit, not work the corp does.
    if not services:
        return []
    text = f"{n.title} {n.description}"
    if p.exclude and p.exclude.search(text):
        return []
    for pattern, where in ((p.anywhere, text), (p.exact_words, text), (p.title_only, n.title)):
        m = pattern.search(where) if pattern else None
        if m:
            return [f'keyword "{m.group(0)}"']
    return []


def section_for(n: Notice, p: Profile) -> str:
    if n.notice_type in p.join_types:
        return SECTION_JOIN
    if n.notice_type in p.rfi_types:
        return SECTION_RFI
    title = n.title.lower()
    if n.notice_type in p.holder_types or any(w.lower() in title for w in p.holder_title_words):
        return SECTION_HOLDERS
    if n.method in p.open_methods:
        return SECTION_BID
    return SECTION_HOLDERS


def classify(rows: list[dict[str, str]], p: Profile, today: date) -> list[Notice]:
    """Every IT / cloud match in the file that has not closed, with its section and flags set."""
    out = []
    for row in rows:
        n = Notice.from_row(row)
        if not still_open(n, today):
            continue
        n.reasons = match_reasons(n, p)
        if not n.reasons:
            continue
        n.section = section_for(n, p)
        n.needs_clearance = bool(p.clearance and p.clearance.search(f"{n.title} {n.description}"))
        out.append(n)
    return out


def vehicle_status(rows: list[dict[str, str]], p: Profile) -> list[dict]:
    """Latest amendment per watched supplier list, or found=False when it left the file."""
    status = []
    for v in p.vehicles:
        needle = v["match"].lower()
        hits = [
            Notice.from_row(r) for r in rows
            if needle in " ".join((
                r["referenceNumber-numeroReference"],
                r["solicitationNumber-numeroSollicitation"],
                r["title-titre-eng"],
            )).lower()
        ]
        if not hits:
            status.append({"name": v["name"], "match": v["match"], "found": False})
            continue
        latest = max(hits, key=lambda n: n.amendment)
        status.append({
            "name": v["name"], "match": v["match"], "found": True,
            "reference": latest.reference, "amendment": latest.amendment,
            "closing": latest.closing, "url": latest.url,
        })
    return status
