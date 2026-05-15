from __future__ import annotations

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

FIELD_STATUS_MOVES = STATUS_NO_CALC

_SINGLE_SLOT_TARGETS = frozenset(
    {
        DoublesTarget.FOE_SLOT_0,
        DoublesTarget.FOE_SLOT_1,
        DoublesTarget.ALLY_ACTIVE,
    },
)


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

    cat = move_category_champions(move_name)

    if cat in ("Physical", "Special", "Status"):
        return target in _SINGLE_SLOT_TARGETS

    return target in _SINGLE_SLOT_TARGETS or target in (DoublesTarget.FIELD, DoublesTarget.NONE)
