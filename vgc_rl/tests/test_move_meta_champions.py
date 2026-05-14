from __future__ import annotations

import json
from importlib import resources

from vgc_rl.champions_metadata import move_category_champions, move_meta_champions
from vgc_rl.example_teams import load_example_teams


def test_all_example_team_move_names_have_champions_meta() -> None:
    data = load_example_teams()
    missing: list[str] = []

    for _k, blob in data.items():
        if _k == "meta" or not isinstance(blob, dict):
            continue

        party = blob.get("party")

        if not isinstance(party, list):
            continue

        for mon in party:
            if not isinstance(mon, dict):
                continue

            for slot in mon.get("moves") or []:
                if isinstance(slot, dict):
                    nm = str(slot.get("name") or "").strip()

                    if nm and move_meta_champions(nm) is None:
                        missing.append(nm)

    assert not missing, missing


def test_type_chart_loads() -> None:
    raw = resources.files("vgc_rl").joinpath("examples/type_chart_champions.json").read_text(encoding="utf-8")
    chart = json.loads(raw)

    assert chart["Fire"]["Grass"] == 2


def test_move_category_helpers() -> None:
    assert move_category_champions("Protect") == "Status"
