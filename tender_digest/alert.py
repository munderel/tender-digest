"""Email the tail of a failed run's log. Called by the workflow's failure step.

    python -m tender_digest.alert --log run_log.txt --run-url https://github.com/...

If Gmail itself is what broke, this fails too. Then the missing daily digest is the
signal, and GitHub's own failed-run email to the repo owner is the backstop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import send


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--run-url", default="")
    args = ap.parse_args(argv)

    try:
        tail = args.log.read_text(encoding="utf-8", errors="replace")[-2500:]
    except OSError:
        tail = "(no log captured)"
    body = f"The tender digest run failed.\n{args.run_url}\n\nLast lines of the log:\n\n{tail}"
    try:
        send.send("Tender digest FAILED", body)
    except send.SendError as exc:
        print(f"alert not sent: {exc}")
        return 1
    print("failure alert sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
