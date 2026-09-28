"""Build CanadaBuys-shaped CSV rows on the live header saved 2026-09-28."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from tender_digest import match

ROOT = Path(__file__).resolve().parent.parent
HEADER_FILE = Path(__file__).parent / "fixtures" / "live_header_2026-09-28.csv"


def live_header() -> list[str]:
    return next(csv.reader(io.StringIO(HEADER_FILE.read_text(encoding="utf-8"))))


def row(**over) -> dict[str, str]:
    """One notice. Short keyword names map onto the long bilingual column names."""
    short = {
        "title": "title-titre-eng",
        "ref": "referenceNumber-numeroReference",
        "amend": "amendmentNumber-numeroModification",
        "sol": "solicitationNumber-numeroSollicitation",
        "published": "publicationDate-datePublication",
        "closing": "tenderClosingDate-appelOffresDateCloture",
        "unspsc": "unspsc",
        "unspsc_desc": "unspscDescription-eng",
        "category": "procurementCategory-categorieApprovisionnement",
        "type": "noticeType-avisType-eng",
        "method": "procurementMethod-methodeApprovisionnement-eng",
        "regions": "regionsOfDelivery-regionsLivraison-eng",
        "buyer": "contractingEntityName-nomEntitContractante-eng",
        "desc": "tenderDescription-descriptionAppelOffres-eng",
        "url": "noticeURL-URLavis-eng",
    }
    base = {c: "" for c in live_header()}
    base.update({
        short["title"]: "Office chairs",
        short["ref"]: "cb-1-1000",
        short["amend"]: "000",
        short["published"]: "2026-09-25",
        short["closing"]: "2026-10-20T14:00:00",
        short["unspsc"]: "*56101500",
        short["category"]: "*GD",
        short["type"]: "Request for Proposal",
        short["method"]: "Competitive - Open bidding",
        short["buyer"]: "Department of Examples",
    })
    for k, v in over.items():
        base[short.get(k, k)] = v
    return base


def to_csv(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=live_header(), quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


@pytest.fixture
def profile() -> match.Profile:
    return match.load_profile(ROOT / "profile.toml")
