from __future__ import annotations

import numpy as np

from vgc_rl.doubles_action_mask import legal_joint_mask_alpha, legal_joint_mask_beta
from vgc_rl.doubles_actions import DoublesTarget, MoveSlotAction, SendOutMoveSlotAction, SwitchSlotAction, enumerate_joint_actions_structural
from vgc_rl.doubles_turn_engine import DoublesBattleState


def _mon(*, name: str = "M", hp: float = 100.0) -> dict:
    return {
        "name": name,
        "moves": [{"name": "Tackle"}, {"name": "Tackle"}, {"name": "Tackle"}, {"name": "Tackle"}],
        "hpPercentage": hp,
        "activeMovePosition": 1,
    }


def test_single_living_foe_masks_dead_foe_slot_for_alpha() -> None:
    party_a = [_mon(name="A0"), _mon(name="A1"), _mon(name="A2"), _mon(name="A3")]
    party_b = [_mon(name="B0", hp=100), _mon(name="B1", hp=0), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.target == DoublesTarget.FOE_SLOT_1:
            assert not mask[ji]

        if isinstance(j.active_1, MoveSlotAction) and j.active_1.target == DoublesTarget.FOE_SLOT_1:
            assert not mask[ji]

    any_foe0 = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.target == DoublesTarget.FOE_SLOT_0
            and isinstance(j.active_1, MoveSlotAction)
            and j.active_1.target == DoublesTarget.ALLY_ACTIVE
            and mask[ji]
        ):
            any_foe0 = True

            break

    assert any_foe0

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.target == DoublesTarget.BOTH_FOES:
            assert not mask[ji]

        if isinstance(j.active_1, MoveSlotAction) and j.active_1.target == DoublesTarget.BOTH_FOES:
            assert not mask[ji]


def test_fainted_slot_allows_sendout_move_not_plain_switch() -> None:
    party_a = [_mon(name="Dead", hp=0), _mon(name="Alive"), _mon(name="Bench0"), _mon(name="Bench1")]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, SwitchSlotAction):
            assert not mask[ji]

        if isinstance(j.active_0, SendOutMoveSlotAction) and isinstance(j.active_1, MoveSlotAction):
            if j.active_0.bench_index == 0 and j.active_0.move_slot == 0 and j.active_0.target == DoublesTarget.FOE_SLOT_0 and j.active_1.move_slot == 0 and j.active_1.target == DoublesTarget.FOE_SLOT_1:
                assert mask[ji]

                return

    raise AssertionError("expected a legal SendOutMove + partner move joint")


def test_single_living_foe_masks_dead_foe_slot_for_beta() -> None:
    party_a = [_mon(name="A0", hp=0), _mon(name="A1", hp=100), _mon(name="A2"), _mon(name="A3")]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_beta(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.target == DoublesTarget.FOE_SLOT_0:
            assert not mask[ji]

        if isinstance(j.active_1, MoveSlotAction) and j.active_1.target == DoublesTarget.FOE_SLOT_0:
            assert not mask[ji]

    assert np.any(mask)


def test_ally_target_requires_living_partner() -> None:
    party_a = [_mon(name="A0", hp=100), _mon(name="A1", hp=0), _mon(name="A2"), _mon(name="A3")]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.target == DoublesTarget.ALLY_ACTIVE:
            assert not mask[ji]


def test_spread_opposing_move_only_allows_both_foes_target() -> None:
    party_a = [
        {
            "name": "Poli",
            "moves": [{"name": "Icy Wind"}, {"name": "Tackle"}, {"name": "Tackle"}, {"name": "Tackle"}],
            "hpPercentage": 100.0,
            "activeMovePosition": 1,
        },
        _mon(name="A1"),
        _mon(name="A2"),
        _mon(name="A3"),
    ]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.move_slot == 0 and j.active_0.target != DoublesTarget.BOTH_FOES:
            assert not mask[ji]

    any_both = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.move_slot == 0
            and j.active_0.target == DoublesTarget.BOTH_FOES
            and isinstance(j.active_1, MoveSlotAction)
            and j.active_1.target == DoublesTarget.ALLY_ACTIVE
            and mask[ji]
        ):
            any_both = True

            break

    assert any_both


def test_protect_requires_self_target() -> None:
    party_a = [
        {
            "name": "Garchomp",
            "moves": [{"name": "Earthquake"}, {"name": "Protect"}, {"name": "Tackle"}, {"name": "Tackle"}],
            "hpPercentage": 100.0,
            "activeMovePosition": 1,
        },
        _mon(name="A1"),
        _mon(name="A2"),
        _mon(name="A3"),
    ]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.move_slot == 1:
            if j.active_0.target != DoublesTarget.SELF:
                assert not mask[ji]

    any_self_protect = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.move_slot == 1
            and j.active_0.target == DoublesTarget.SELF
            and isinstance(j.active_1, MoveSlotAction)
            and j.active_1.target == DoublesTarget.FOE_SLOT_0
            and mask[ji]
        ):
            any_self_protect = True

            break

    assert any_self_protect


def test_single_target_offensive_not_both_foes() -> None:
    party_a = [
        {
            "name": "Garchomp",
            "moves": [{"name": "Dragon Claw"}, {"name": "Sludge Bomb"}, {"name": "Electro Shot"}, {"name": "Tackle"}],
            "hpPercentage": 100.0,
            "activeMovePosition": 1,
        },
        _mon(name="A1"),
        _mon(name="A2"),
        _mon(name="A3"),
    ]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if not isinstance(j.active_0, MoveSlotAction):
            continue

        if j.active_0.move_slot not in (0, 1, 2):
            continue

        if j.active_0.target == DoublesTarget.BOTH_FOES:
            assert not mask[ji]

    any_foe_single = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.move_slot == 0
            and j.active_0.target == DoublesTarget.FOE_SLOT_0
            and isinstance(j.active_1, MoveSlotAction)
            and j.active_1.target == DoublesTarget.FOE_SLOT_1
            and mask[ji]
        ):
            any_foe_single = True

            break

    assert any_foe_single


def test_field_target_only_for_field_status_moves() -> None:
    party_a = [
        {
            "name": "Incineroar",
            "moves": [{"name": "Parting Shot"}, {"name": "Low Kick"}, {"name": "Tailwind"}, {"name": "Tackle"}],
            "hpPercentage": 100.0,
            "activeMovePosition": 1,
        },
        _mon(name="A1"),
        _mon(name="A2"),
        _mon(name="A3"),
    ]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if not isinstance(j.active_0, MoveSlotAction):
            continue

        if j.active_0.move_slot == 0 and j.active_0.target == DoublesTarget.FIELD:
            assert not mask[ji]

        if j.active_0.move_slot == 1 and j.active_0.target == DoublesTarget.FIELD:
            assert not mask[ji]

        if j.active_0.move_slot == 2 and j.active_0.target == DoublesTarget.FOE_SLOT_0:
            assert not mask[ji]

    any_tailwind_field = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.move_slot == 2
            and j.active_0.target == DoublesTarget.FIELD
            and mask[ji]
        ):
            any_tailwind_field = True

            break

    assert any_tailwind_field


def test_earthquake_requires_all_others_target() -> None:
    party_a = [
        {
            "name": "Garchomp",
            "moves": [{"name": "Earthquake"}, {"name": "Tackle"}, {"name": "Tackle"}, {"name": "Tackle"}],
            "hpPercentage": 100.0,
            "activeMovePosition": 1,
        },
        _mon(name="A1"),
        _mon(name="A2"),
        _mon(name="A3"),
    ]
    party_b = [_mon(name="B0"), _mon(name="B1"), _mon(name="B2"), _mon(name="B3")]
    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    joints = enumerate_joint_actions_structural()
    mask = legal_joint_mask_alpha(state, joints)

    for ji, j in enumerate(joints):
        if isinstance(j.active_0, MoveSlotAction) and j.active_0.move_slot == 0:
            if j.active_0.target != DoublesTarget.ALL_OTHERS:
                assert not mask[ji]

    any_eq = False

    for ji, j in enumerate(joints):
        if (
            isinstance(j.active_0, MoveSlotAction)
            and j.active_0.move_slot == 0
            and j.active_0.target == DoublesTarget.ALL_OTHERS
            and isinstance(j.active_1, MoveSlotAction)
            and j.active_1.target == DoublesTarget.FOE_SLOT_0
            and mask[ji]
        ):
            any_eq = True

            break

    assert any_eq

