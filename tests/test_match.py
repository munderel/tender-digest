from datetime import date

import pytest

from conftest import live_header, row, to_csv
from tender_digest import fetch, match
from tender_digest.match import SECTION_BID, SECTION_HOLDERS, SECTION_JOIN, SECTION_RFI

TODAY = date(2026, 9, 28)


def classify_one(profile, **over):
    found = match.classify([row(**over)], profile, TODAY)
    return found[0] if found else None


# ---- feed parsing

def test_live_header_still_has_every_required_column():
    assert set(fetch.REQUIRED_COLUMNS) <= set(live_header())


def test_parse_reads_bom_and_embedded_newlines():
    raw = to_csv([row(unspsc="*81111500\n*43230000")] * 3)
    rows = fetch.parse(raw, min_rows=3)
    assert rows[0]["unspsc"] == "*81111500\n*43230000"


def test_parse_refuses_a_missing_column():
    raw = "﻿\"title-titre-eng\"\n\"x\"\n".encode("utf-8")
    with pytest.raises(fetch.FeedError, match="missing columns"):
        fetch.parse(raw, min_rows=1)


def test_parse_refuses_a_short_file():
    with pytest.raises(fetch.FeedError, match="only 2 rows"):
        fetch.parse(to_csv([row(), row()]), min_rows=100)


# ---- helpers

def test_multi_value_cells_split_and_strip_stars():
    assert match.multi("*81111500\n*43230000\n") == ["81111500", "43230000"]
    assert match.multi("") == []


def test_clean_text_unescapes_entities_and_drops_tags():
    assert match.clean_text("<p>Data&rsquo;s &quot;platform&quot;</p>") == "Data’s \"platform\""


@pytest.mark.parametrize("ref, slug", [
    ("cb-8448-42897985", "cb-8448-42897985"),
    ("WS4286933967-Doc4822970058", "ws4286933967-doc4822970058"),
    ("PW-_NCS-030-11940", "pw-ncs-030-11940"),
    ("SSC-26-00034400:T", "ssc-26-00034400t"),
])
def test_notice_url_slug_matches_canadabuys(ref, slug):
    assert match.notice_url(ref).endswith("/tender-notice/" + slug)


# ---- matching

def test_unspsc_prefix_matches_a_services_notice(profile):
    n = classify_one(profile, unspsc="*81111500", unspsc_desc="*Software or hardware engineering", category="*SRV")
    assert n and n.reasons == ["UNSPSC 81111500 Software or hardware engineering"]


def test_cloud_saas_code_matches(profile):
    assert classify_one(profile, unspsc="*81162000", category="*SRV")


def test_goods_notice_with_software_as_a_side_code_is_dropped(profile):
    # Lab kit that ships with analysis software: not the corp's work.
    assert classify_one(profile, unspsc="*41115400\n*43232605", category="*GD") is None


def test_goods_notice_that_is_mainly_software_matches(profile):
    assert classify_one(profile, unspsc="*43230000", category="*GD")


def test_keyword_in_description_matches_services(profile):
    n = classify_one(profile, category="*SRV", desc="Migrate workloads to Microsoft Azure")
    assert n and n.reasons == ['keyword "Azure"']


def test_keyword_on_goods_notice_is_ignored(profile):
    assert classify_one(profile, category="*GD", desc="Hardware managed through Azure") is None


def test_title_only_word_in_description_does_not_match(profile):
    assert classify_one(profile, category="*SRV", desc="Results stored in the cloud") is None
    assert classify_one(profile, category="*SRV", title="Cloud hosting services")


def test_ai_is_case_sensitive(profile):
    assert classify_one(profile, category="*SRV", desc="Il y a ai des services") is None
    assert classify_one(profile, category="*SRV", title="AI-powered triage pilot")


def test_exclude_word_drops_keyword_match_but_not_code_match(profile):
    assert classify_one(profile, category="*SRV", title="Building automation and HVAC controls") is None
    assert classify_one(profile, category="*SRV", unspsc="*81111500", title="Translation portal software")


def test_closed_notice_is_skipped(profile):
    assert classify_one(profile, unspsc="*81111500", category="*SRV", closing="2025-08-26T14:00:00") is None


# ---- sections and flags

@pytest.mark.parametrize("over, section", [
    ({"type": "Request for Proposal", "method": "Competitive - Open bidding"}, SECTION_BID),
    ({"type": "Advance Contract Award Notice", "method": "Advance contract award notice"}, SECTION_BID),
    ({"type": "Request for Supply Arrangement"}, SECTION_JOIN),
    ({"type": "Invitation to Qualify"}, SECTION_JOIN),
    ({"type": "Request for Information"}, SECTION_RFI),
    ({"type": "RFP against Supply Arrangement"}, SECTION_HOLDERS),
    ({"type": "Request for Proposal", "method": "Competitive - Selective tendering"}, SECTION_HOLDERS),
    ({"type": "Not Applicable", "title": "TBIPS UX Consultant", "method": "Competitive - Open bidding"}, SECTION_HOLDERS),
])
def test_section(profile, over, section):
    n = classify_one(profile, unspsc="*81111500", category="*SRV", **over)
    assert n.section == section


def test_clearance_flag(profile):
    n = classify_one(profile, unspsc="*81111500", category="*SRV", desc="Resources must hold Reliability Status.")
    assert n.needs_clearance


# ---- supplier-list watch

def test_vehicle_status_takes_the_latest_amendment(profile):
    rows = [
        row(ref="cb-8448-42897985", sol="E60ZT-180024/C", amend="005", title="ProServices Method of Supply"),
        row(ref="cb-8448-42897985", sol="E60ZT-180024/C", amend="006", title="ProServices Method of Supply"),
    ]
    status = {v["name"]: v for v in match.vehicle_status(rows, profile)}
    assert status["ProServices"]["found"] and status["ProServices"]["amendment"] == "006"
    assert status["TBIPS"]["found"] is False
