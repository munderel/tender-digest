"""What earlier runs already reported, kept in state/seen.json and committed back by the workflow.

The daily commit is also the keep-alive: GitHub disables a scheduled workflow after 60 days
without repository activity, and `last_run` changes every run.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = 1


def load(path: Path) -> dict:
    if not path.exists():
        return {"version": VERSION, "last_run": None, "seen": {}, "vehicles": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("seen", {})
    data.setdefault("vehicles", {})
    data.setdefault("last_run", None)
    return data


def is_first_run(state: dict) -> bool:
    return not state.get("last_run")


def split_new(notices: list, state: dict) -> tuple[list, list]:
    """(new, already reported). An amendment has a new key, so it counts as new."""
    seen = state["seen"]
    new = [n for n in notices if n.key not in seen]
    old = [n for n in notices if n.key in seen]
    return new, old


def vehicle_changes(status: list[dict], state: dict) -> list[dict]:
    """Watched lists whose amendment moved, or that appeared or vanished, since the last run."""
    before = state["vehicles"]
    changes = []
    for v in status:
        prev = before.get(v["name"])
        if prev is None:
            continue  # first sighting: the baseline, not news
        if v["found"] != prev.get("found", True) or v.get("amendment") != prev.get("amendment"):
            changes.append({**v, "previous": prev.get("amendment") if prev.get("found", True) else None})
    return changes


def advance(state: dict, notices: list, status: list[dict], today: str) -> dict:
    """Record this run. Keys for notices no longer open are dropped, so the file stays small."""
    seen = {k: d for k, d in state["seen"].items() if k in {n.key for n in notices}}
    for n in notices:
        seen.setdefault(n.key, today)
    vehicles = {
        v["name"]: {"found": v["found"], "amendment": v.get("amendment"), "reference": v.get("reference")}
        for v in status
    }
    return {"version": VERSION, "last_run": today, "seen": dict(sorted(seen.items())), "vehicles": vehicles}


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
