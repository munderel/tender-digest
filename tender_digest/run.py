"""Daily tender digest: fetch CanadaBuys, match IT / cloud notices, email what is new.

    python -m tender_digest.run --dry-run            # print the digest, send nothing, save nothing
    python -m tender_digest.run --dry-run --csv x.csv  # same, from a saved file
    python -m tender_digest.run                      # send, then record what was sent
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import fetch, match, render, send, state

ROOT = Path(__file__).resolve().parent.parent


def today_eastern() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Toronto")).date()
    except Exception:  # noqa: BLE001  (no tz database on some Windows installs)
        return (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the digest; send nothing, save nothing")
    ap.add_argument("--csv", type=Path, help="read this file instead of downloading")
    ap.add_argument("--profile", type=Path, default=ROOT / "profile.toml")
    ap.add_argument("--state", type=Path, default=ROOT / "state" / "seen.json")
    ap.add_argument("--out", type=Path, default=ROOT / "out", help="dry run writes digest.txt and digest.html here")
    ap.add_argument("--today", type=date.fromisoformat, help="override today's date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252

    today = args.today or today_eastern()
    profile = match.load_profile(args.profile)
    raw = args.csv.read_bytes() if args.csv else fetch.download()
    rows = fetch.parse(raw)

    notices = match.classify(rows, profile, today)
    vehicles = match.vehicle_status(rows, profile)
    st = state.load(args.state)
    first = state.is_first_run(st)
    new, old = state.split_new(notices, st)
    changes = state.vehicle_changes(vehicles, st)

    digest = render.build(
        new=new, old=old, vehicles=vehicles, vehicle_changes=changes, first_run=first,
        scanned=len(rows), today=today, soon_days=profile.closing_soon_days,
    )
    print(f"scanned {len(rows)} notices, {len(notices)} IT/cloud matches, {len(new)} new, "
          f"{len(changes)} list changes, first_run={first}")

    if args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "digest.txt").write_text(digest.text, encoding="utf-8")
        (args.out / "digest.html").write_text(digest.html, encoding="utf-8")
        print(digest.text)
        print(f"\n[dry run] nothing sent, state not saved; preview in {args.out}")
        return 0

    # Send first, record after: a failed send must not mark notices as already reported.
    to = send.send(digest.subject, digest.text, digest.html)
    state.save(args.state, state.advance(st, notices, vehicles, today.isoformat()))
    print(f"sent '{digest.subject}' to {len(to)} recipient(s); state saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
