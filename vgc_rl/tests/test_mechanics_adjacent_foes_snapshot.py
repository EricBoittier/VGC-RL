from __future__ import annotations

import json
from importlib import resources

from vgc_rl.doubles_turn_engine import _SPREAD_BOTH_OPPONENTS_MOVES


def test_python_spread_moves_are_adjacent_multi_foe_targets_in_export() -> None:
    raw = resources.files("vgc_rl").joinpath("examples/adjacent_foes_move_names_champions.json").read_text(encoding="utf-8")
    exported = set(json.loads(raw))
    missing = _SPREAD_BOTH_OPPONENTS_MOVES - exported

    assert not missing, missing
