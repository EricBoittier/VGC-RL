from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgc_rl.champions_metadata import move_category_champions
from vgc_rl.doubles_actions import DoublesTarget
from vgc_rl.doubles_move_targeting import (
    allowed_targets_for_showdown,
    showdown_target_for_move,
    structural_target_allowed,
)


def _allowed_names(move_name: str) -> set[str]:
    return {t.name for t in DoublesTarget if structural_target_allowed(move_name, t)}


@pytest.mark.parametrize(
    ("move", "expected"),
    [
        ("Protect", {"SELF"}),
        ("King's Shield", {"SELF"}),
        ("Substitute", {"SELF"}),
        ("Swords Dance", {"SELF"}),
        ("Life Dew", {"SELF"}),
        ("Recover", {"SELF"}),
        ("Helping Hand", {"ALLY_ACTIVE"}),
        ("Coaching", {"ALLY_ACTIVE"}),
        ("Follow Me", {"SELF"}),
        ("Wide Guard", {"FIELD", "NONE"}),
        ("Perish Song", {"FIELD", "NONE"}),
        ("Will-O-Wisp", {"FOE_SLOT_0", "FOE_SLOT_1"}),
        ("Taunt", {"FOE_SLOT_0", "FOE_SLOT_1"}),
    ],
)
def test_named_move_target_masks(move: str, expected: set[str]) -> None:
    assert _allowed_names(move) == expected


def test_showdown_export_covers_meta_status_moves() -> None:
    meta_dir = Path(__file__).resolve().parents[1] / "vgc_rl" / "examples" / "meta_teams"
    status_moves: set[str] = set()

    for path in meta_dir.glob("*.json"):
        if path.name == "manifest.json":
            continue

        party = json.loads(path.read_text(encoding="utf-8")).get("party") or []

        for mon in party:
            for slot in mon.get("moves") or []:
                name = str(slot.get("name") or "").strip()

                if name and move_category_champions(name) == "Status":
                    status_moves.add(name)

    missing = sorted(m for m in status_moves if showdown_target_for_move(m) is None)

    assert not missing, f"meta status moves missing from export: {missing}"

    for mv in status_moves:
        sd = showdown_target_for_move(mv)

        assert sd is not None

        allowed_sd = allowed_targets_for_showdown(sd)

        assert allowed_sd is not None

        for t in DoublesTarget:
            in_mask = structural_target_allowed(mv, t)

            assert in_mask == (t in allowed_sd), f"{mv} target {t.name} sd={sd}"


def test_foe_status_cannot_target_ally() -> None:
    assert not structural_target_allowed("Will-O-Wisp", DoublesTarget.ALLY_ACTIVE)
    assert not structural_target_allowed("Taunt", DoublesTarget.ALLY_ACTIVE)
