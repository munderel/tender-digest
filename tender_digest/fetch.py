"""Download and parse the CanadaBuys open tender notice file.

The file is federal only, CSV, published under the Open Government Licence - Canada, and
refreshed once a day between 07:00 and 08:30 Eastern. Dataset:
https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2
"""

from __future__ import annotations

import csv
import io
import urllib.request

OPEN_NOTICES_URL = (
    "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
)

# Columns the matcher reads. If CanadaBuys renames one, fail loudly rather than
# quietly matching nothing and sending a cheerful "nothing new" email.
REQUIRED_COLUMNS = (
    "title-titre-eng",
    "referenceNumber-numeroReference",
    "amendmentNumber-numeroModification",
    "solicitationNumber-numeroSollicitation",
    "publicationDate-datePublication",
    "tenderClosingDate-appelOffresDateCloture",
    "unspsc",
    "procurementCategory-categorieApprovisionnement",
    "noticeType-avisType-eng",
    "procurementMethod-methodeApprovisionnement-eng",
    "regionsOfDelivery-regionsLivraison-eng",
    "contractingEntityName-nomEntitContractante-eng",
    "tenderDescription-descriptionAppelOffres-eng",
)

# The live file held 918 open notices on 2026-09-28. Far fewer means a truncated
# download or an emptied feed, not a quiet week.
MIN_ROWS = 100


class FeedError(RuntimeError):
    """The feed could not be trusted this run."""


def download(url: str = OPEN_NOTICES_URL, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tender-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        if resp.status != 200:
            raise FeedError(f"CanadaBuys returned HTTP {resp.status}")
        return resp.read()


def parse(raw: bytes, min_rows: int = MIN_ROWS) -> list[dict[str, str]]:
    """Rows as dicts. Raises FeedError on a missing column or a suspiciously short file."""
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise FeedError(f"CanadaBuys file is missing columns: {', '.join(missing)}")
    rows = list(reader)
    if len(rows) < min_rows:
        raise FeedError(f"CanadaBuys file has only {len(rows)} rows (expected {min_rows}+)")
    return rows
