"""Turn the day's matches into an email: a subject, a plain-text body and an HTML body."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date

from .match import SECTION_BID, SECTION_HOLDERS, SECTION_JOIN, SECTION_RFI, Notice

SECTION_TITLES = {
    SECTION_BID: "Bid now: open competitions",
    SECTION_JOIN: "Supplier lists you could join",
    SECTION_RFI: "Requests for information: answer to get known",
    SECTION_HOLDERS: "List holders or invited suppliers only: teaming leads",
}
SECTION_ORDER = (SECTION_BID, SECTION_JOIN, SECTION_RFI, SECTION_HOLDERS)


@dataclass
class Digest:
    subject: str
    text: str
    html: str


def days_left(closing: str, today: date) -> int | None:
    try:
        return (date.fromisoformat(closing[:10]) - today).days
    except ValueError:
        return None


def closing_soon(old: list[Notice], today: date, within: int) -> list[Notice]:
    """Already-reported notices you could still act on that close within `within` days."""
    out = []
    for n in old:
        d = days_left(n.closing, today)
        if n.section in (SECTION_BID, SECTION_JOIN) and d is not None and 0 <= d <= within:
            out.append(n)
    return sorted(out, key=lambda n: n.closing)


def _facts(n: Notice, today: date) -> list[str]:
    facts = []
    if n.buyer:
        facts.append(n.buyer)
    d = days_left(n.closing, today)
    if d is not None:
        facts.append(f"closes {n.closing[:10]} ({'today' if d == 0 else f'{d} day' if d == 1 else f'{d} days'})")
    if n.regions:
        facts.append(", ".join(n.regions[:2]))
    if n.notice_type:
        facts.append(n.notice_type)
    facts.append(n.reasons[0])
    if n.amendment not in ("", "000"):
        facts.append(f"amendment {n.amendment}")
    if n.needs_clearance:
        facts.append("needs security clearance")
    return facts


def build(
    *,
    new: list[Notice],
    old: list[Notice],
    vehicles: list[dict],
    vehicle_changes: list[dict],
    first_run: bool,
    scanned: int,
    today: date,
    soon_days: int,
) -> Digest:
    by_section = {s: sorted([n for n in new if n.section == s], key=lambda n: n.closing) for s in SECTION_ORDER}
    soon = closing_soon(old, today, soon_days)

    counts = [
        (len(by_section[SECTION_BID]), "to bid"),
        (len(by_section[SECTION_JOIN]), "lists"),
        (len(by_section[SECTION_RFI]), "RFIs"),
        (len(by_section[SECTION_HOLDERS]), "teaming"),
    ]
    if first_run:
        subject = f"Tender digest {today}: first run, {len(new)} open IT and cloud notices"
    elif new or vehicle_changes:
        parts = [f"{c} {label}" for c, label in counts if c]
        if vehicle_changes:
            parts.append(f"{len(vehicle_changes)} list changes")
        subject = f"Tender digest {today}: " + ", ".join(parts)
    else:
        subject = f"Tender digest {today}: nothing new ({scanned} notices scanned)"

    lead = (
        "First run: everything IT or cloud that is open today. From tomorrow, only what is new."
        if first_run else
        "New IT and cloud notices since yesterday's digest."
    )
    footer = (
        f"Scanned {scanned} open federal notices from the CanadaBuys open-data file "
        f"(Open Government Licence - Canada). Provincial, municipal and MERX-only notices are "
        f"not in this file: use the Ontario Tenders Portal and MERX alerts for those. "
        f"This email is sent every day, even when nothing is new. A day without it means the job broke."
    )

    # ---- plain text
    t = [subject, "", lead, ""]
    for s in SECTION_ORDER:
        items = by_section[s]
        if not items:
            continue
        t += [f"== {SECTION_TITLES[s]} ({len(items)})", ""]
        for n in items:
            t += [f"- {n.title}", f"  {' · '.join(_facts(n, today))}", f"  {n.url}", ""]
    if not new:
        t += ["No new IT or cloud notices today.", ""]
    if soon:
        t += [f"== Closing within {soon_days} days ({len(soon)})", ""]
        for n in soon:
            t += [f"- {n.title} · closes {n.closing[:10]}", f"  {n.url}", ""]
    t += ["== Supplier-list watch", ""]
    for c in vehicle_changes:
        was = f"amendment {c['previous']}" if c.get("previous") else "not in the file"
        now = f"amendment {c['amendment']}" if c["found"] else "gone from the open file"
        t.append(f"! {c['name']} changed: {was} -> {now}  {c.get('url', '')}")
    for v in vehicles:
        if v["found"]:
            t.append(f"- {v['name']}: amendment {v['amendment']}, closes {v['closing'][:10]}  {v['url']}")
        else:
            t.append(f"- {v['name']} ({v['match']}): not in the open file")
    t += ["", footer]
    text = "\n".join(t)

    # ---- html
    e = html.escape
    h = [
        "<div style=\"font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:720px;color:#1a1a1a\">",
        f"<p style=\"margin:0 0 16px\">{e(lead)}</p>",
    ]

    def notice_li(n: Notice) -> str:
        return (
            f"<li style=\"margin:0 0 12px\"><a href=\"{e(n.url)}\" style=\"font-weight:600\">{e(n.title)}</a>"
            f"<br><span style=\"color:#555;font-size:13px\">{e(' · '.join(_facts(n, today)))}</span></li>"
        )

    for s in SECTION_ORDER:
        items = by_section[s]
        if not items:
            continue
        h.append(f"<h3 style=\"margin:20px 0 8px\">{e(SECTION_TITLES[s])} ({len(items)})</h3><ul style=\"padding-left:18px\">")
        h += [notice_li(n) for n in items]
        h.append("</ul>")
    if not new:
        h.append("<p><b>No new IT or cloud notices today.</b></p>")
    if soon:
        h.append(f"<h3 style=\"margin:20px 0 8px\">Closing within {soon_days} days ({len(soon)})</h3><ul style=\"padding-left:18px\">")
        h += [notice_li(n) for n in soon]
        h.append("</ul>")
    h.append("<h3 style=\"margin:20px 0 8px\">Supplier-list watch</h3><ul style=\"padding-left:18px\">")
    for c in vehicle_changes:
        was = f"amendment {c['previous']}" if c.get("previous") else "not in the file"
        now = f"amendment {c['amendment']}" if c["found"] else "gone from the open file"
        h.append(f"<li><b>{e(c['name'])} changed: {e(was)} &rarr; {e(now)}</b></li>")
    for v in vehicles:
        if v["found"]:
            h.append(
                f"<li><a href=\"{e(v['url'])}\">{e(v['name'])}</a>: amendment {e(v['amendment'])}, "
                f"closes {e(v['closing'][:10])}</li>"
            )
        else:
            h.append(f"<li>{e(v['name'])} ({e(v['match'])}): not in the open file</li>")
    h.append("</ul>")
    h.append(f"<p style=\"color:#666;font-size:12px;margin-top:24px\">{e(footer)}</p></div>")

    return Digest(subject=subject, text=text, html="\n".join(h))
