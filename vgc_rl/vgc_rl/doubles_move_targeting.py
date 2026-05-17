from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from vgc_rl.champions_metadata import move_category_champions
from vgc_rl.doubles_actions import DoublesTarget
from vgc_rl.doubles_protect_moves import PROTECT_FAMILY_MOVES
from vgc_rl.turn_sim import STATUS_NO_CALC

SPREAD_BOTH_OPPONENTS_MOVES = frozenset(
    {
        "Blizzard",
        "Boomburst",
        "Breaking Swipe",
        "Dazzling Gleam",
        "Growl",
        "Heat Wave",
        "Hyper Voice",
        "Icy Wind",
        "Incinerate",
        "Leer",
        "Rock Slide",
        "Snarl",
        "Struggle Bug",
        "Sweet Scent",
        "Tail Whip",
    },
)

ALL_ADJACENT_EXCEPT_USER_MOVES = frozenset(
    {
        "Brutal Swing",
        "Bulldoze",
        "Corrosive Gas",
        "Discharge",
        "Earthquake",
        "Explosion",
        "Lava Plume",
        "Misty Explosion",
        "Parabolic Charge",
        "Petal Blizzard",
        "Self-Destruct",
        "Sludge Wave",
        "Sparkling Aria",
        "Surf",
        "Teeter Dance",
    },
)

SIDE_STATUS_MOVES = frozenset({"Wide Guard", "Perish Song"})

FIELD_STATUS_MOVES = STATUS_NO_CALC | SIDE_STATUS_MOVES

_FOE_SLOT_TARGETS = frozenset({DoublesTarget.FOE_SLOT_0, DoublesTarget.FOE_SLOT_1})

_SINGLE_SLOT_TARGETS = frozenset(
    {
        DoublesTarget.FOE_SLOT_0,
        DoublesTarget.FOE_SLOT_1,
        DoublesTarget.ALLY_ACTIVE,
    },
)

_SHOWDOWN_TO_DOUBLES: dict[str, frozenset[DoublesTarget]] = {
    "self": frozenset({DoublesTarget.SELF}),
    "adjacentAlly": frozenset({DoublesTarget.ALLY_ACTIVE}),
    "allies": frozenset({DoublesTarget.SELF}),
    "adjacentAllyOrSelf": frozenset({DoublesTarget.SELF, DoublesTarget.ALLY_ACTIVE}),
    "normal": _FOE_SLOT_TARGETS,
    "adjacentFoe": _FOE_SLOT_TARGETS,
    "any": _FOE_SLOT_TARGETS,
    "randomNormal": _FOE_SLOT_TARGETS,
    "allAdjacentFoes": frozenset({DoublesTarget.BOTH_FOES}),
    "allAdjacent": frozenset({DoublesTarget.ALL_OTHERS}),
    "allySide": frozenset({DoublesTarget.FIELD, DoublesTarget.NONE}),
    "allyTeam": frozenset({DoublesTarget.FIELD, DoublesTarget.NONE}),
    "foeSide": frozenset({DoublesTarget.FIELD, DoublesTarget.NONE}),
    "all": frozenset({DoublesTarget.FIELD, DoublesTarget.NONE}),
    "scripted": frozenset({DoublesTarget.FIELD, DoublesTarget.NONE}),
}

_TARGETS_JSON = Path(__file__).resolve().parent / "examples" / "move_targets_champions.json"


@lru_cache(maxsize=1)
def _load_showdown_targets() -> dict[str, str]:
    if not _TARGETS_JSON.is_file():
        return {}

    data: dict[str, Any] = json.loads(_TARGETS_JSON.read_text(encoding="utf-8"))

    raw = data.get("targets")

    if not isinstance(raw, dict):
        return {}

    return {str(k): str(v) for k, v in raw.items()}


def showdown_target_for_move(move_name: str) -> str | None:
    return _load_showdown_targets().get(move_name)


def allowed_targets_for_showdown(showdown_target: str) -> frozenset[DoublesTarget] | None:
    return _SHOWDOWN_TO_DOUBLES.get(showdown_target)


def structural_target_allowed(move_name: str, target: DoublesTarget) -> bool:
    if move_name in PROTECT_FAMILY_MOVES:
        return target == DoublesTarget.SELF

    if move_name in SPREAD_BOTH_OPPONENTS_MOVES:
        return target == DoublesTarget.BOTH_FOES

    if move_name in ALL_ADJACENT_EXCEPT_USER_MOVES:
        return target == DoublesTarget.ALL_OTHERS

    if move_name == "Sucker Punch":
        return target in (DoublesTarget.FOE_SLOT_0, DoublesTarget.FOE_SLOT_1)

    if move_name in FIELD_STATUS_MOVES:
        return target in (DoublesTarget.FIELD, DoublesTarget.NONE)

    sd = showdown_target_for_move(move_name)

    if sd is not None:
        allowed = allowed_targets_for_showdown(sd)

        if allowed is not None:
            return target in allowed

    cat = move_category_champions(move_name)

    if cat == "Status":
        return target in _FOE_SLOT_TARGETS

    if cat in ("Physical", "Special"):
        return target in _SINGLE_SLOT_TARGETS

    return target in _SINGLE_SLOT_TARGETS or target in (DoublesTarget.FIELD, DoublesTarget.NONE)
