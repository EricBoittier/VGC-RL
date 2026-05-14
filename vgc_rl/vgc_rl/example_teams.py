from __future__ import annotations

import json
from copy import deepcopy
from importlib import resources
from typing import Any


def load_example_teams() -> dict[str, Any]:
    raw = resources.files("vgc_rl").joinpath("examples/example_teams.json").read_text(encoding="utf-8")

    return json.loads(raw)


def party_member(team_key: str, slot_index: int) -> dict[str, Any]:
    data = load_example_teams()

    return deepcopy(data[team_key]["party"][slot_index])


def with_active_move(member: dict[str, Any], position: int) -> dict[str, Any]:
    out = deepcopy(member)

    out["activeMovePosition"] = position

    return out


def move_display_name(member: dict[str, Any], position: int) -> str:
    return member["moves"][position - 1]["name"]


def example_battle_batch_body(
    *,
    game: str,
    alpha_slot: int,
    beta_slot: int,
    kind: str = "single",
) -> dict[str, Any]:
    if kind not in ("single", "allMoves"):
        raise ValueError(kind)

    attacker = party_member("team_alpha", alpha_slot)
    defender = party_member("team_beta", beta_slot)

    return {
        "game": game,
        "requests": [{"kind": kind, "field": {}, "attacker": attacker, "defender": defender}],
    }
