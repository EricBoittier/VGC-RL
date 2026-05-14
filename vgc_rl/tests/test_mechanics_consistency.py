from vgc_rl.doubles_protect_moves import PROTECT_FAMILY_MOVES
from vgc_rl.doubles_turn_engine import _PROTECT_STALL_MOVES, _SPREAD_BOTH_OPPONENTS_MOVES, _SPREAD_FOE_STAT_DROPS
from vgc_rl.turn_sim import PROTECT_FAMILY


def test_protect_family_single_source_matches_engine_alias() -> None:
    assert PROTECT_FAMILY_MOVES is _PROTECT_STALL_MOVES
    assert PROTECT_FAMILY is PROTECT_FAMILY_MOVES


def test_spread_foe_stat_drop_move_names_are_spread_moves() -> None:
    for mv in _SPREAD_FOE_STAT_DROPS:
        assert mv in _SPREAD_BOTH_OPPONENTS_MOVES
