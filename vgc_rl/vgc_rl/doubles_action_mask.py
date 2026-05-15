from __future__ import annotations

import numpy as np
from typing import Any

from vgc_rl.doubles_actions import DoublesTarget, JointDoublesAction, MoveSlotAction, SendOutMoveSlotAction, SwitchSlotAction
from vgc_rl.doubles_mega_tera import can_mega_evolve_species, can_terastal
from vgc_rl.doubles_move_targeting import structural_target_allowed
from vgc_rl.doubles_turn_engine import DoublesBattleState, _ELECTRO_SHOT, bench_slot_to_party_index
from vgc_rl.held_item_rules import move_slot_illegal_assault_vest, move_slot_illegal_choice_lock


FORM_ACTION_BRANCHES = 3


def encode_flat_form_action(form_branch: int, joint_idx: int, num_joints: int) -> int:
    return form_branch * num_joints + joint_idx


def _move_slots_item_legal(mon: dict[str, Any], move_slot: int, game: str) -> bool:
    if move_slot_illegal_choice_lock(mon, move_slot):
        return False

    if move_slot_illegal_assault_vest(mon, move_slot, game=game):
        return False

    return True


def decode_flat_form_action(flat_idx: int, num_joints: int) -> tuple[int, int]:
    return flat_idx // num_joints, flat_idx % num_joints


def split_form_branch_for_game(form_branch: int, game: str) -> tuple[int, int]:
    if form_branch < 0 or form_branch > 2:
        raise ValueError(f"form_branch must be 0..2, got {form_branch}")

    if game == "champions":
        return form_branch, 0

    if game == "sv":
        return 0, form_branch

    return 0, 0


def _move_target_legal_for_side(
    target: DoublesTarget,
    *,
    field_idx: int,
    party: list[dict],
    leads: list[int],
    foe_party: list[dict],
    foe_leads: list[int],
) -> bool:
    if target == DoublesTarget.FOE_SLOT_0:
        pi = foe_leads[0]

        return float(foe_party[pi].get("hpPercentage") or 0) > 0

    if target == DoublesTarget.FOE_SLOT_1:
        pi = foe_leads[1]

        return float(foe_party[pi].get("hpPercentage") or 0) > 0

    if target == DoublesTarget.BOTH_FOES:
        return any(float(foe_party[foe_leads[i]].get("hpPercentage") or 0) > 0 for i in (0, 1))

    if target == DoublesTarget.ALLY_ACTIVE:
        ally_pi = leads[1 - field_idx]

        return float(party[ally_pi].get("hpPercentage") or 0) > 0

    if target == DoublesTarget.SELF:
        self_pi = leads[field_idx]

        return float(party[self_pi].get("hpPercentage") or 0) > 0

    return True


def _side_joint_legal(joint: JointDoublesAction, state: DoublesBattleState, *, atk_side: str, game: str) -> bool:
    party = state.party_a if atk_side == "alpha" else state.party_b
    leads = state.leads_a if atk_side == "alpha" else state.leads_b
    foe_party = state.party_b if atk_side == "alpha" else state.party_a
    foe_leads = state.leads_b if atk_side == "alpha" else state.leads_a

    chosen_switch_targets: set[int] = set()

    for slot_action, fi in ((joint.active_0, 0), (joint.active_1, 1)):
        pi_cur = leads[fi]
        hp_slot = float(party[pi_cur].get("hpPercentage") or 0)

        if isinstance(slot_action, SwitchSlotAction):
            if hp_slot <= 0:
                return False

            ba = state.brought_alpha_sorted() if atk_side == "alpha" else state.brought_beta_sorted()

            to_pi = bench_slot_to_party_index(leads, slot_action.bench_index, brought=ba)

            if to_pi is None:
                return False

            if to_pi == leads[1 - fi]:
                return False

            if to_pi in chosen_switch_targets:
                return False

            if float(party[to_pi].get("hpPercentage") or 0) <= 0:
                return False

            chosen_switch_targets.add(to_pi)

            continue

        if isinstance(slot_action, SendOutMoveSlotAction):
            if hp_slot > 0:
                return False

            ba = state.brought_alpha_sorted() if atk_side == "alpha" else state.brought_beta_sorted()

            to_pi = bench_slot_to_party_index(leads, slot_action.bench_index, brought=ba)

            if to_pi is None:
                return False

            if to_pi == leads[1 - fi]:
                return False

            if to_pi in chosen_switch_targets:
                return False

            if float(party[to_pi].get("hpPercentage") or 0) <= 0:
                return False

            incoming = party[to_pi]
            mv_name = str(incoming["moves"][slot_action.move_slot]["name"]).strip()

            if not _move_slots_item_legal(incoming, slot_action.move_slot, game):
                return False

            ck = ("a" if atk_side == "alpha" else "b", to_pi)

            if state.electro_shot_charging.get(ck) and mv_name != _ELECTRO_SHOT:
                return False

            if not structural_target_allowed(mv_name, slot_action.target):
                return False

            if slot_action.target == DoublesTarget.SELF:
                if float(incoming.get("hpPercentage") or 0) <= 0:
                    return False
            elif not _move_target_legal_for_side(
                slot_action.target,
                field_idx=fi,
                party=party,
                leads=leads,
                foe_party=foe_party,
                foe_leads=foe_leads,
            ):
                return False

            chosen_switch_targets.add(to_pi)

            continue

        if hp_slot <= 0:
            return False

        mv_name = str(party[pi_cur]["moves"][slot_action.move_slot]["name"]).strip()

        if not _move_slots_item_legal(party[pi_cur], slot_action.move_slot, game):
            return False

        ck = ("a" if atk_side == "alpha" else "b", pi_cur)

        if state.electro_shot_charging.get(ck) and mv_name != _ELECTRO_SHOT:
            return False

        if not structural_target_allowed(mv_name, slot_action.target):
            return False

        if not _move_target_legal_for_side(
            slot_action.target,
            field_idx=fi,
            party=party,
            leads=leads,
            foe_party=foe_party,
            foe_leads=foe_leads,
        ):
            return False

    return True


def legal_joint_mask_alpha(state: DoublesBattleState, joints: tuple[JointDoublesAction, ...], *, game: str = "champions") -> np.ndarray:
    out = np.zeros(len(joints), dtype=np.bool_)

    for i, j in enumerate(joints):
        out[i] = _side_joint_legal(j, state, atk_side="alpha", game=game)

    return out


def legal_joint_mask_beta(state: DoublesBattleState, joints: tuple[JointDoublesAction, ...], *, game: str = "champions") -> np.ndarray:
    out = np.zeros(len(joints), dtype=np.bool_)

    for i, j in enumerate(joints):
        out[i] = _side_joint_legal(j, state, atk_side="beta", game=game)

    return out


def legal_flat_mask_alpha(
    state: DoublesBattleState,
    joints: tuple[JointDoublesAction, ...],
    *,
    game: str,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
) -> np.ndarray:
    n = len(joints)
    base = legal_joint_mask_alpha(state, joints, game=game)
    out = np.zeros(n * FORM_ACTION_BRANCHES, dtype=np.bool_)
    party_a = state.party_a
    leads_a = state.leads_a

    for ji in range(n):
        if not base[ji]:
            continue

        j = joints[ji]

        out[0 * n + ji] = True

        if game == "champions" and allow_mega_evolution and not state.alpha_mega_used:
            if isinstance(j.active_0, MoveSlotAction):
                pi0 = leads_a[0]

                if float(party_a[pi0].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_a[pi0], game=game):
                    out[1 * n + ji] = True

            elif isinstance(j.active_0, SendOutMoveSlotAction):
                pi0 = bench_slot_to_party_index(leads_a, j.active_0.bench_index, brought=state.brought_alpha_sorted())

                if pi0 is not None and float(party_a[pi0].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_a[pi0], game=game):
                    out[1 * n + ji] = True

            if isinstance(j.active_1, MoveSlotAction):
                pi1 = leads_a[1]

                if float(party_a[pi1].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_a[pi1], game=game):
                    out[2 * n + ji] = True

            elif isinstance(j.active_1, SendOutMoveSlotAction):
                pi1 = bench_slot_to_party_index(leads_a, j.active_1.bench_index, brought=state.brought_alpha_sorted())

                if pi1 is not None and float(party_a[pi1].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_a[pi1], game=game):
                    out[2 * n + ji] = True

        elif game == "sv" and allow_terastal and not state.alpha_tera_used:
            if isinstance(j.active_0, MoveSlotAction):
                pi0 = leads_a[0]

                if float(party_a[pi0].get("hpPercentage") or 0) > 0 and can_terastal(party_a[pi0], game=game):
                    out[1 * n + ji] = True

            elif isinstance(j.active_0, SendOutMoveSlotAction):
                pi0 = bench_slot_to_party_index(leads_a, j.active_0.bench_index, brought=state.brought_alpha_sorted())

                if pi0 is not None and float(party_a[pi0].get("hpPercentage") or 0) > 0 and can_terastal(party_a[pi0], game=game):
                    out[1 * n + ji] = True

            if isinstance(j.active_1, MoveSlotAction):
                pi1 = leads_a[1]

                if float(party_a[pi1].get("hpPercentage") or 0) > 0 and can_terastal(party_a[pi1], game=game):
                    out[2 * n + ji] = True

            elif isinstance(j.active_1, SendOutMoveSlotAction):
                pi1 = bench_slot_to_party_index(leads_a, j.active_1.bench_index, brought=state.brought_alpha_sorted())

                if pi1 is not None and float(party_a[pi1].get("hpPercentage") or 0) > 0 and can_terastal(party_a[pi1], game=game):
                    out[2 * n + ji] = True

    return out


def legal_flat_mask_beta(
    state: DoublesBattleState,
    joints: tuple[JointDoublesAction, ...],
    *,
    game: str,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
) -> np.ndarray:
    n = len(joints)
    base = legal_joint_mask_beta(state, joints, game=game)
    out = np.zeros(n * FORM_ACTION_BRANCHES, dtype=np.bool_)
    party_b = state.party_b
    leads_b = state.leads_b

    for ji in range(n):
        if not base[ji]:
            continue

        j = joints[ji]

        out[0 * n + ji] = True

        if game == "champions" and allow_mega_evolution and not state.beta_mega_used:
            if isinstance(j.active_0, MoveSlotAction):
                pi0 = leads_b[0]

                if float(party_b[pi0].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_b[pi0], game=game):
                    out[1 * n + ji] = True

            elif isinstance(j.active_0, SendOutMoveSlotAction):
                pi0 = bench_slot_to_party_index(leads_b, j.active_0.bench_index, brought=state.brought_beta_sorted())

                if pi0 is not None and float(party_b[pi0].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_b[pi0], game=game):
                    out[1 * n + ji] = True

            if isinstance(j.active_1, MoveSlotAction):
                pi1 = leads_b[1]

                if float(party_b[pi1].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_b[pi1], game=game):
                    out[2 * n + ji] = True

            elif isinstance(j.active_1, SendOutMoveSlotAction):
                pi1 = bench_slot_to_party_index(leads_b, j.active_1.bench_index, brought=state.brought_beta_sorted())

                if pi1 is not None and float(party_b[pi1].get("hpPercentage") or 0) > 0 and can_mega_evolve_species(party_b[pi1], game=game):
                    out[2 * n + ji] = True

        elif game == "sv" and allow_terastal and not state.beta_tera_used:
            if isinstance(j.active_0, MoveSlotAction):
                pi0 = leads_b[0]

                if float(party_b[pi0].get("hpPercentage") or 0) > 0 and can_terastal(party_b[pi0], game=game):
                    out[1 * n + ji] = True

            elif isinstance(j.active_0, SendOutMoveSlotAction):
                pi0 = bench_slot_to_party_index(leads_b, j.active_0.bench_index, brought=state.brought_beta_sorted())

                if pi0 is not None and float(party_b[pi0].get("hpPercentage") or 0) > 0 and can_terastal(party_b[pi0], game=game):
                    out[1 * n + ji] = True

            if isinstance(j.active_1, MoveSlotAction):
                pi1 = leads_b[1]

                if float(party_b[pi1].get("hpPercentage") or 0) > 0 and can_terastal(party_b[pi1], game=game):
                    out[2 * n + ji] = True

            elif isinstance(j.active_1, SendOutMoveSlotAction):
                pi1 = bench_slot_to_party_index(leads_b, j.active_1.bench_index, brought=state.brought_beta_sorted())

                if pi1 is not None and float(party_b[pi1].get("hpPercentage") or 0) > 0 and can_terastal(party_b[pi1], game=game):
                    out[2 * n + ji] = True

    return out
