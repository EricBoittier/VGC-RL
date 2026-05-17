from __future__ import annotations

import random

from vgc_rl.doubles_actions import DoublesTarget, JointDoublesAction, MoveSlotAction
from vgc_rl.doubles_action_mask import legal_joint_mask_alpha
from vgc_rl.doubles_turn_engine import DoublesBattleState, resolve_turn_flat
from vgc_rl.example_teams import party_member
from vgc_rl.fake_oracle_client import FakeOracleClient


def _mv(side: str, fi: int, slot: int, tgt: int) -> MoveSlotAction:
    return MoveSlotAction(move_slot=slot, target=DoublesTarget(tgt))


def test_assault_vest_blocks_status_moves_in_mask() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_a[0]["item"] = "Assault Vest"

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = (
        JointDoublesAction(active_0=_mv("alpha", 0, 2, int(DoublesTarget.FOE_SLOT_0)), active_1=_mv("alpha", 1, 2, int(DoublesTarget.FOE_SLOT_0))),
    )
    mask = legal_joint_mask_alpha(state, joints, game="champions")

    assert not bool(mask[0])


def test_choice_scarf_locks_second_turn_move_slot() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_a[0]["item"] = "Choice Scarf"
    party_a[0]["moves"] = [
        {"name": "Giga Drain"},
        {"name": "Sludge Bomb"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]
    party_a[1]["moves"] = [
        {"name": "Giga Drain"},
        {"name": "Sludge Bomb"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    j1 = JointDoublesAction(active_0=_mv("alpha", 0, 1, int(DoublesTarget.FOE_SLOT_0)), active_1=_mv("alpha", 1, 1, int(DoublesTarget.FOE_SLOT_0)))
    j2 = JointDoublesAction(active_0=_mv("alpha", 0, 2, int(DoublesTarget.FOE_SLOT_0)), active_1=_mv("alpha", 1, 2, int(DoublesTarget.FOE_SLOT_0)))
    joints = (j1, j2)

    m0 = legal_joint_mask_alpha(state, joints, game="champions")

    assert bool(m0[0]) and bool(m0[1])

    rng = random.Random(0)
    client = FakeOracleClient()
    planned = [
        {"kind": "move", "atk_side": "alpha", "field_idx": 0, "move_slot": 1, "orig_index": 0, "doubles_target": int(DoublesTarget.FOE_SLOT_0)},
        {"kind": "move", "atk_side": "alpha", "field_idx": 1, "move_slot": 2, "orig_index": 1},
        {"kind": "move", "atk_side": "beta", "field_idx": 0, "move_slot": 1, "orig_index": 2},
        {"kind": "move", "atk_side": "beta", "field_idx": 1, "move_slot": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert int(state.party_a[state.leads_a[0]].get("choice_locked_move_slot") or 0) == 1

    m1 = legal_joint_mask_alpha(state, joints, game="champions")

    assert bool(m1[0]) and not bool(m1[1])


def test_switch_clears_choice_lock() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_a[0]["item"] = "Choice Scarf"
    party_a[0]["choice_locked_move_slot"] = 1

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(1)
    client = FakeOracleClient()
    planned = [
        {"kind": "switch", "atk_side": "alpha", "field_idx": 0, "to_party": 2, "orig_index": 0},
        {"kind": "move", "atk_side": "alpha", "field_idx": 1, "move_slot": 2, "orig_index": 1},
        {"kind": "move", "atk_side": "beta", "field_idx": 0, "move_slot": 1, "orig_index": 2},
        {"kind": "move", "atk_side": "beta", "field_idx": 1, "move_slot": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert state.party_a[0].get("choice_locked_move_slot") is None
