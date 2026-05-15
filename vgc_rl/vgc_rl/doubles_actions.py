from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from itertools import product
from typing import Sequence

DEFAULT_MOVE_SLOTS = 4
DEFAULT_BENCH_SLOTS = 2


class DoublesTarget(IntEnum):
    FOE_SLOT_0 = 0
    FOE_SLOT_1 = 1
    ALLY_ACTIVE = 2
    SELF = 3
    BOTH_FOES = 4
    FIELD = 5
    NONE = 6
    ALL_OTHERS = 7


@dataclass(frozen=True, slots=True)
class MoveSlotAction:
    move_slot: int
    target: DoublesTarget


@dataclass(frozen=True, slots=True)
class SwitchSlotAction:
    bench_index: int


@dataclass(frozen=True, slots=True)
class SendOutMoveSlotAction:
    bench_index: int
    move_slot: int
    target: DoublesTarget


SlotAction = MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction


@dataclass(frozen=True, slots=True)
class JointDoublesAction:
    active_0: SlotAction
    active_1: SlotAction


def structural_move_targets() -> tuple[DoublesTarget, ...]:
    return tuple(DoublesTarget)


def enumerate_slot_actions_structural(*, move_slots: int = DEFAULT_MOVE_SLOTS, bench_slots: int = DEFAULT_BENCH_SLOTS) -> tuple[SlotAction, ...]:
    out: list[SlotAction] = []

    for m in range(move_slots):
        for t in structural_move_targets():
            out.append(MoveSlotAction(move_slot=m, target=t))

    for b in range(bench_slots):
        out.append(SwitchSlotAction(bench_index=b))

    for b in range(bench_slots):
        for m in range(move_slots):
            for t in structural_move_targets():
                out.append(SendOutMoveSlotAction(bench_index=b, move_slot=m, target=t))

    return tuple(out)


def enumerate_joint_actions_structural(
    *,
    move_slots: int = DEFAULT_MOVE_SLOTS,
    bench_slots: int = DEFAULT_BENCH_SLOTS,
    filter_duplicate_switch_to_same_bench: bool = True,
) -> tuple[JointDoublesAction, ...]:
    slots = enumerate_slot_actions_structural(move_slots=move_slots, bench_slots=bench_slots)
    joint: list[JointDoublesAction] = []

    for a, b in product(slots, repeat=2):
        if filter_duplicate_switch_to_same_bench:
            if isinstance(a, SwitchSlotAction) and isinstance(b, SwitchSlotAction):
                if a.bench_index == b.bench_index:
                    continue

            if isinstance(a, SendOutMoveSlotAction) and isinstance(b, SendOutMoveSlotAction):
                if a.bench_index == b.bench_index:
                    continue

        joint.append(JointDoublesAction(active_0=a, active_1=b))

    return tuple(joint)


def joint_action_index_table(joints: Sequence[JointDoublesAction]) -> dict[JointDoublesAction, int]:
    return {j: i for i, j in enumerate(joints)}


def encode_joint_index(active_0: SlotAction, active_1: SlotAction, joints: Sequence[JointDoublesAction]) -> int:
    table = joint_action_index_table(joints)

    return table[JointDoublesAction(active_0=active_0, active_1=active_1)]


def decode_joint_index(idx: int, joints: Sequence[JointDoublesAction]) -> JointDoublesAction:
    return joints[idx]


def count_actions_per_turn(*, move_slots: int = DEFAULT_MOVE_SLOTS, bench_slots: int = DEFAULT_BENCH_SLOTS, filter_duplicate_switch_to_same_bench: bool = True) -> dict[str, int]:
    slot_actions = enumerate_slot_actions_structural(move_slots=move_slots, bench_slots=bench_slots)
    joint = enumerate_joint_actions_structural(
        move_slots=move_slots,
        bench_slots=bench_slots,
        filter_duplicate_switch_to_same_bench=filter_duplicate_switch_to_same_bench,
    )

    return {
        "slot_actions": len(slot_actions),
        "joint_actions": len(joint),
        "move_slots": move_slots,
        "bench_slots": bench_slots,
        "targets_per_move": len(structural_move_targets()),
    }
