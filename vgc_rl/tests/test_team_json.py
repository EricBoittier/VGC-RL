from __future__ import annotations

import json

from vgc_rl.team_json import load_team_party, team_file_sha256


def _four_slot_party(name_prefix: str = "X") -> dict:
    mon = {
        "name": name_prefix,
        "moves": [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}],
        "hpPercentage": 100.0,
        "activeMovePosition": 1,
    }

    return {"label": "test", "party": [dict(mon, name=f"{name_prefix}{i}") for i in range(4)]}


def _six_slot_party(name_prefix: str = "Y") -> dict:
    mon = {
        "name": name_prefix,
        "moves": [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}],
        "hpPercentage": 100.0,
        "activeMovePosition": 1,
    }

    return {"label": "six", "party": [dict(mon, name=f"{name_prefix}{i}") for i in range(6)]}


def test_load_team_party_six_slots_tmp(tmp_path) -> None:
    p = tmp_path / "six.json"

    p.write_text(json.dumps(_six_slot_party("Q")), encoding="utf-8")

    label, party = load_team_party(p)

    assert label == "six"
    assert len(party) == 6


def test_load_team_party_roundtrip_tmp(tmp_path) -> None:
    p = tmp_path / "t.json"
    body = _four_slot_party("Z")

    p.write_text(json.dumps(body), encoding="utf-8")

    label, party = load_team_party(p)

    assert label == "test"
    assert len(party) == 4
    assert party[0]["name"] == "Z0"

    h = team_file_sha256(p)

    assert len(h) == 64
