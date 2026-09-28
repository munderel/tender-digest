from datetime import date

from conftest import row
from tender_digest import match, render, state

TODAY = date(2026, 9, 28)


def notices(profile, *rows):
    return match.classify(list(rows), profile, TODAY)


def empty_state():
    return {"version": 1, "last_run": None, "seen": {}, "vehicles": {}}


def test_first_run_then_only_new(profile):
    a = row(ref="cb-1-1", unspsc="*81111500", category="*SRV", title="Data platform build")
    ns = notices(profile, a)
    st = empty_state()
    assert state.is_first_run(st)
    st = state.advance(st, ns, [], "2026-09-28")
    assert not state.is_first_run(st)

    b = row(ref="cb-2-2", unspsc="*81111500", category="*SRV", title="Cloud migration")
    new, old = state.split_new(notices(profile, a, b), st)
    assert [n.reference for n in new] == ["cb-2-2"]
    assert [n.reference for n in old] == ["cb-1-1"]


def test_amendment_counts_as_new(profile):
    a0 = row(ref="cb-1-1", amend="000", unspsc="*81111500", category="*SRV")
    st = state.advance(empty_state(), notices(profile, a0), [], "2026-09-27")
    a1 = row(ref="cb-1-1", amend="001", unspsc="*81111500", category="*SRV")
    new, _ = state.split_new(notices(profile, a1), st)
    assert [n.key for n in new] == ["cb-1-1|001"]


def test_closed_notices_are_pruned_from_state(profile):
    a = row(ref="cb-1-1", unspsc="*81111500", category="*SRV")
    st = state.advance(empty_state(), notices(profile, a), [], "2026-09-27")
    st = state.advance(st, [], [], "2026-09-28")
    assert st["seen"] == {} and st["last_run"] == "2026-09-28"


def test_vehicle_change_is_reported_but_first_sighting_is_not():
    v6 = [{"name": "ProServices", "match": "E60ZT-180024", "found": True, "amendment": "006",
           "reference": "cb-8448-42897985", "closing": "2028-07-04", "url": "u"}]
    st = empty_state()
    assert state.vehicle_changes(v6, st) == []
    st = state.advance(st, [], v6, "2026-09-28")
    v7 = [{**v6[0], "amendment": "007"}]
    changes = state.vehicle_changes(v7, st)
    assert changes and changes[0]["previous"] == "006"
    gone = [{"name": "ProServices", "match": "E60ZT-180024", "found": False}]
    assert state.vehicle_changes(gone, st)[0]["found"] is False


def test_state_round_trips(tmp_path, profile):
    p = tmp_path / "state" / "seen.json"
    st = state.advance(empty_state(), notices(profile, row(unspsc="*81111500", category="*SRV")), [], "2026-09-28")
    state.save(p, st)
    assert state.load(p) == st


def test_digest_sections_escaping_and_dead_man_line(profile):
    ns = notices(
        profile,
        row(ref="cb-1-1", unspsc="*81111500", category="*SRV", title="Data & BI for > 5 teams"),
        row(ref="cb-2-2", unspsc="*81111500", category="*SRV", type="Request for Supply Arrangement", title="IT list"),
    )
    d = render.build(new=ns, old=[], vehicles=[], vehicle_changes=[], first_run=False,
                     scanned=918, today=TODAY, soon_days=5)
    assert d.subject == "Tender digest 2026-09-28: 1 to bid, 1 lists"
    assert "Bid now: open competitions (1)" in d.text
    assert "Data &amp; BI for &gt; 5 teams" in d.html
    assert "A day without it means the job broke." in d.text


def test_nothing_new_still_produces_a_digest(profile):
    d = render.build(new=[], old=[], vehicles=[], vehicle_changes=[], first_run=False,
                     scanned=918, today=TODAY, soon_days=5)
    assert d.subject == "Tender digest 2026-09-28: nothing new (918 notices scanned)"
    assert "No new IT or cloud notices today." in d.text


def test_closing_soon_lists_old_biddable_notices(profile):
    old = notices(profile, row(ref="cb-1-1", unspsc="*81111500", category="*SRV", closing="2026-10-01T14:00:00"))
    d = render.build(new=[], old=old, vehicles=[], vehicle_changes=[], first_run=False,
                     scanned=918, today=TODAY, soon_days=5)
    assert "Closing within 5 days (1)" in d.text
