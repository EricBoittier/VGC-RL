from __future__ import annotations

import random
from typing import Any, Callable, Literal, Sequence

import numpy as np

from vgc_rl.doubles_action_mask import legal_joint_mask_alpha, legal_joint_mask_beta
from vgc_rl.doubles_move_targeting import structural_target_allowed
from vgc_rl.doubles_actions import DoublesTarget, JointDoublesAction, MoveSlotAction, SendOutMoveSlotAction, SwitchSlotAction, decode_joint_index
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_TOTAL_DIM, DOUBLES_RL_BRING_TAIL_DIM, doubles_obs_boost_features, doubles_obs_identity_features
from vgc_rl.doubles_turn_engine import DoublesBattleState, _PROTECT_STALL_MOVES, _SPREAD_BOTH_OPPONENTS_MOVES, bench_slot_to_party_index, joint_to_planned_side, resolve_turn
from vgc_rl.oracle_client import OracleClient


def _mon_name(party: list[dict[str, Any]], party_index: int) -> str:
    return str(party[party_index].get("name", "?"))


def _target_choice_label(
    t: DoublesTarget,
    *,
    party: list[dict[str, Any]],
    leads: list[int],
    field_idx: int,
    foe_party: list[dict[str, Any]] | None,
    foe_leads: list[int] | None,
) -> str:
    if foe_party is not None and foe_leads is not None:
        if t == DoublesTarget.FOE_SLOT_0:
            return f"Foe A ({_mon_name(foe_party, foe_leads[0])})"

        if t == DoublesTarget.FOE_SLOT_1:
            return f"Foe B ({_mon_name(foe_party, foe_leads[1])})"

        if t == DoublesTarget.BOTH_FOES:
            return f"Both foes ({_mon_name(foe_party, foe_leads[0])} · {_mon_name(foe_party, foe_leads[1])})"

        if t == DoublesTarget.ALLY_ACTIVE:
            return f"Ally ({_mon_name(party, leads[1 - field_idx])})"

        if t == DoublesTarget.SELF:
            return f"Self ({_mon_name(party, leads[field_idx])})"

        if t == DoublesTarget.ALL_OTHERS:
            ally = _mon_name(party, leads[1 - field_idx])

            return f"All others ({_mon_name(foe_party, foe_leads[0])} · {_mon_name(foe_party, foe_leads[1])} · Ally {ally})"

    if t == DoublesTarget.FOE_SLOT_0:
        return "Foe A"

    if t == DoublesTarget.FOE_SLOT_1:
        return "Foe B"

    if t == DoublesTarget.ALLY_ACTIVE:
        return "Ally"

    if t == DoublesTarget.SELF:
        return "Self"

    if t == DoublesTarget.BOTH_FOES:
        return "Both foes"

    if t == DoublesTarget.FIELD:
        return "Field"

    if t == DoublesTarget.NONE:
        return "—"

    if t == DoublesTarget.ALL_OTHERS:
        return "All others"

    return t.name


def _form_mechanic_obs_tail(
    state: DoublesBattleState,
    *,
    game: str,
    allow_mega_evolution: bool,
    allow_terastal: bool,
) -> list[float]:
    am = 1.0 if game == "champions" and allow_mega_evolution and not state.alpha_mega_used else 0.0
    bm = 1.0 if game == "champions" and allow_mega_evolution and not state.beta_mega_used else 0.0
    at = 1.0 if game == "sv" and allow_terastal and not state.alpha_tera_used else 0.0
    bt = 1.0 if game == "sv" and allow_terastal and not state.beta_tera_used else 0.0

    return [am, bm, at, bt]


def doubles_obs_vector(
    state: DoublesBattleState,
    *,
    game: str = "champions",
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
) -> np.ndarray:
    parts: list[float] = []

    obs_slice_a = state.battle_obs_party_slice_alpha()
    obs_slice_b = state.battle_obs_party_slice_beta()

    for mon in obs_slice_a:
        parts.append(float(mon.get("hpPercentage") or 0) / 100.0)

    for mon in obs_slice_b:
        parts.append(float(mon.get("hpPercentage") or 0) / 100.0)

    parts.append(state.alpha_tailwind_turns_left / 4.0)
    parts.append(state.beta_tailwind_turns_left / 4.0)

    den_a = max(len(state.party_a) - 1, 1)
    den_b = max(len(state.party_b) - 1, 1)

    for pi in state.leads_a:
        parts.append(pi / den_a)

    for pi in state.leads_b:
        parts.append(pi / den_b)

    parts.extend(_form_mechanic_obs_tail(state, game=game, allow_mega_evolution=allow_mega_evolution, allow_terastal=allow_terastal))

    base = np.asarray(parts, dtype=np.float32)
    boosts = doubles_obs_boost_features(obs_slice_a, obs_slice_b)
    ident = doubles_obs_identity_features(obs_slice_a, obs_slice_b)

    return np.concatenate([base, boosts, ident]).astype(np.float32)


def doubles_rl_six_bring_observation(
    state: DoublesBattleState | None,
    *,
    party_a_full: list[dict[str, Any]],
    party_b_full: list[dict[str, Any]],
    game: str,
    bring_phase: bool,
    allow_mega_evolution: bool,
    allow_terastal: bool,
) -> np.ndarray:
    tail = np.zeros(DOUBLES_RL_BRING_TAIL_DIM, dtype=np.float32)

    if bring_phase:
        tail[0] = 1.0
        na = len(party_a_full)
        nb = len(party_b_full)

        for i in range(6):
            hp = float(party_a_full[i].get("hpPercentage") or 0) / 100.0 if i < na else 0.0
            tail[1 + i] = hp

        for i in range(6):
            hp = float(party_b_full[i].get("hpPercentage") or 0) / 100.0 if i < nb else 0.0
            tail[1 + 6 + i] = hp

    if bring_phase or state is None:
        base = np.zeros(DOUBLES_OBS_TOTAL_DIM, dtype=np.float32)

        return np.concatenate([base, tail], dtype=np.float32)

    base = doubles_obs_vector(state, game=game, allow_mega_evolution=allow_mega_evolution, allow_terastal=allow_terastal)

    return np.concatenate([base, tail], dtype=np.float32)


def format_slot_action(slot: MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction) -> str:
    if isinstance(slot, SwitchSlotAction):
        return f"sw{slot.bench_index}"

    if isinstance(slot, SendOutMoveSlotAction):
        return f"so{slot.bench_index}m{slot.move_slot + 1}{slot.target.name}"

    return f"m{slot.move_slot + 1}{slot.target.name}"


def format_joint_for_display(joint: JointDoublesAction) -> str:
    return f"{format_slot_action(joint.active_0)}|{format_slot_action(joint.active_1)}"


def _summary_brought(party: list[dict[str, Any]], brought: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
    if brought is not None:
        return brought

    n = len(party)

    if n == 4:
        return (0, 1, 2, 3)

    if n == 6:
        return (0, 1, 2, 3)

    raise ValueError(f"party length must be 4 or 6 for summary formatting (got {n})")


def format_slot_action_human(
    party: list[dict[str, Any]],
    leads: list[int],
    field_idx: int,
    slot: MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction,
    *,
    foe_party: list[dict[str, Any]] | None = None,
    foe_leads: list[int] | None = None,
    brought: tuple[int, int, int, int],
) -> str:
    if isinstance(slot, SwitchSlotAction):
        pi = bench_slot_to_party_index(leads, slot.bench_index, brought=brought)

        if pi is None:
            return f"Switch bench-slot {slot.bench_index}"

        name = party[pi].get("name", "?")

        return f"Switch → {name}"

    if isinstance(slot, SendOutMoveSlotAction):
        pi = bench_slot_to_party_index(leads, slot.bench_index, brought=brought)

        if pi is None:
            return f"Send-out bench {slot.bench_index} + move"

        mv = party[pi]["moves"][slot.move_slot]["name"]
        name = party[pi].get("name", "?")
        tg = _target_choice_label(slot.target, party=party, leads=leads, field_idx=field_idx, foe_party=foe_party, foe_leads=foe_leads)

        return f"Send {name}: {mv} ({tg})"

    pi = leads[field_idx]
    mv = party[pi]["moves"][slot.move_slot]["name"]
    tg = _target_choice_label(slot.target, party=party, leads=leads, field_idx=field_idx, foe_party=foe_party, foe_leads=foe_leads)

    return f"{mv} ({tg})"


def format_joint_human_summary(
    joint: JointDoublesAction,
    party: list[dict[str, Any]],
    leads: list[int],
    *,
    foe_party: list[dict[str, Any]] | None = None,
    foe_leads: list[int] | None = None,
    brought: tuple[int, int, int, int] | None = None,
) -> str:
    br = _summary_brought(party, brought)

    a = format_slot_action_human(party, leads, 0, joint.active_0, foe_party=foe_party, foe_leads=foe_leads, brought=br)
    b = format_slot_action_human(party, leads, 1, joint.active_1, foe_party=foe_party, foe_leads=foe_leads, brought=br)

    return f"{a} · {b}"


def _slot_part(joints: tuple[JointDoublesAction, ...], ji: int, leg: Literal["active_0", "active_1"]) -> MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction:
    j = joints[ji]

    return j.active_0 if leg == "active_0" else j.active_1


def _prompt_move_target(
    move_display_name: str,
    targets: list[DoublesTarget],
    input_fn: Callable[[str], str],
    *,
    party: list[dict[str, Any]],
    leads: list[int],
    field_idx: int,
    foe_party: list[dict[str, Any]] | None,
    foe_leads: list[int] | None,
) -> DoublesTarget:
    while True:
        for ti, t in enumerate(targets):
            lab = _target_choice_label(t, party=party, leads=leads, field_idx=field_idx, foe_party=foe_party, foe_leads=foe_leads)

            print(f"  [{ti}] {lab}")

        raw = input_fn(f'Target for "{move_display_name}" [0-{len(targets) - 1}]: ').strip()

        try:
            pick = int(raw)
        except ValueError:
            print("Enter an integer.")

            continue

        if not (0 <= pick < len(targets)):
            print("Out of range.")

            continue

        return targets[pick]


def _prompt_one_slot_menu(
    legal_joint_indices: set[int],
    joints: tuple[JointDoublesAction, ...],
    party: list[dict[str, Any]],
    leads: list[int],
    field_idx: int,
    leg: Literal["active_0", "active_1"],
    input_fn: Callable[[str], str],
    *,
    foe_party: list[dict[str, Any]] | None,
    foe_leads: list[int] | None,
    brought: tuple[int, int, int, int],
) -> MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction:
    pi_act = leads[field_idx]
    hp_act = float(party[pi_act].get("hpPercentage") or 0)

    if hp_act <= 0:
        send_outs: dict[tuple[int, int], set[DoublesTarget]] = {}

        for ji in legal_joint_indices:
            sa = _slot_part(joints, ji, leg)

            if isinstance(sa, SendOutMoveSlotAction):
                send_outs.setdefault((sa.bench_index, sa.move_slot), set()).add(sa.target)

        rows: list[dict[str, Any]] = []

        for (b, m) in sorted(send_outs.keys()):
            pi = bench_slot_to_party_index(leads, b, brought=brought)

            if pi is None:
                continue

            mon_name = party[pi].get("name", "?")
            mvname = str(party[pi]["moves"][m]["name"])
            tgts_set = send_outs[(b, m)]

            tgts_set = {t for t in tgts_set if structural_target_allowed(mvname, t)}

            tgts = sorted(tgts_set, key=lambda t: t.value)
            label = f"Send {mon_name}: {mvname}"

            if len(tgts) == 1:
                rows.append({"kind": "sendout_fixed", "bench": b, "move_slot": m, "target": tgts[0], "label": label})
            else:
                rows.append({"kind": "sendout_pick", "bench": b, "move_slot": m, "targets": tgts, "label": label})

        if not rows:
            raise RuntimeError("no legal send-out moves for this slot")

        if len(rows) == 1:
            row = rows[0]

            if row["kind"] == "sendout_fixed":
                return SendOutMoveSlotAction(bench_index=int(row["bench"]), move_slot=int(row["move_slot"]), target=row["target"])

            tgt = _prompt_move_target(
                str(row["label"]),
                list(row["targets"]),
                input_fn,
                party=party,
                leads=leads,
                field_idx=field_idx,
                foe_party=foe_party,
                foe_leads=foe_leads,
            )

            return SendOutMoveSlotAction(bench_index=int(row["bench"]), move_slot=int(row["move_slot"]), target=tgt)

        while True:
            for i, r in enumerate(rows):
                suf = ""

                if r["kind"] == "sendout_pick":
                    suf = " → pick target"

                print(f"  [{i}] {r['label']}{suf}")

            raw = input_fn(f"Choice [0-{len(rows) - 1}]: ").strip()

            try:
                pick = int(raw)
            except ValueError:
                print("Enter an integer.")

                continue

            if not (0 <= pick < len(rows)):
                print("Out of range.")

                continue

            row = rows[pick]

            if row["kind"] == "sendout_fixed":
                return SendOutMoveSlotAction(bench_index=int(row["bench"]), move_slot=int(row["move_slot"]), target=row["target"])

            tgt = _prompt_move_target(
                str(row["label"]),
                list(row["targets"]),
                input_fn,
                party=party,
                leads=leads,
                field_idx=field_idx,
                foe_party=foe_party,
                foe_leads=foe_leads,
            )

            return SendOutMoveSlotAction(bench_index=int(row["bench"]), move_slot=int(row["move_slot"]), target=tgt)

    switches: dict[int, list[int]] = {}
    move_targets: dict[int, set[DoublesTarget]] = {}

    for ji in legal_joint_indices:
        sa = _slot_part(joints, ji, leg)

        if isinstance(sa, SwitchSlotAction):
            switches.setdefault(sa.bench_index, []).append(ji)
        elif isinstance(sa, MoveSlotAction):
            move_targets.setdefault(sa.move_slot, set()).add(sa.target)

    rows: list[dict[str, Any]] = []

    for b in sorted(switches.keys()):
        pi = bench_slot_to_party_index(leads, b, brought=brought)

        if pi is None:
            continue

        name = party[pi].get("name", "?")

        rows.append({"kind": "switch", "bench": b, "label": f"Switch → {name}"})

    for m in sorted(move_targets.keys()):
        tgts_set = set(move_targets[m])
        mvname = str(party[pi_act]["moves"][m]["name"])

        tgts_set = {t for t in tgts_set if structural_target_allowed(mvname, t)}

        tgts = sorted(tgts_set, key=lambda t: t.value)

        if len(tgts) == 1:
            rows.append({"kind": "move_fixed", "action": MoveSlotAction(move_slot=m, target=tgts[0]), "label": mvname})
        else:
            rows.append({"kind": "move_pick", "move_slot": m, "targets": tgts, "label": mvname})

    if not rows:
        raise RuntimeError("no legal switches or moves for this slot")

    if len(rows) == 1:
        row = rows[0]

        if row["kind"] == "switch":
            return SwitchSlotAction(bench_index=int(row["bench"]))

        if row["kind"] == "move_fixed":
            return row["action"]

        tgt = _prompt_move_target(
            str(row["label"]),
            list(row["targets"]),
            input_fn,
            party=party,
            leads=leads,
            field_idx=field_idx,
            foe_party=foe_party,
            foe_leads=foe_leads,
        )

        return MoveSlotAction(move_slot=int(row["move_slot"]), target=tgt)

    while True:
        for i, r in enumerate(rows):
            suf = ""

            if r["kind"] == "move_pick":
                suf = " → pick target"

            print(f"  [{i}] {r['label']}{suf}")

        raw = input_fn(f"Choice [0-{len(rows) - 1}]: ").strip()

        try:
            pick = int(raw)
        except ValueError:
            print("Enter an integer.")

            continue

        if not (0 <= pick < len(rows)):
            print("Out of range.")

            continue

        row = rows[pick]

        if row["kind"] == "switch":
            return SwitchSlotAction(bench_index=int(row["bench"]))

        if row["kind"] == "move_fixed":
            return row["action"]

        tgt = _prompt_move_target(
            str(row["label"]),
            list(row["targets"]),
            input_fn,
            party=party,
            leads=leads,
            field_idx=field_idx,
            foe_party=foe_party,
            foe_leads=foe_leads,
        )

        return MoveSlotAction(move_slot=int(row["move_slot"]), target=tgt)


def prompt_joint_human_side(
    *,
    mask: np.ndarray,
    joints: tuple[JointDoublesAction, ...],
    party: list[dict[str, Any]],
    leads: list[int],
    brought: tuple[int, int, int, int],
    trainer_heading: str,
    input_fn: Callable[[str], str],
    slot_labels: tuple[str, str] = ("Lead A", "Lead B"),
    foe_party: list[dict[str, Any]] | None = None,
    foe_leads: list[int] | None = None,
) -> int:
    legal_set = {int(x) for x in np.flatnonzero(np.asarray(mask, dtype=bool))}

    if not legal_set:
        raise RuntimeError(f"{trainer_heading}: no legal joint actions")

    print(f"\n—— {trainer_heading} ——")

    print(f"\n{slot_labels[0]}")

    s0 = _prompt_one_slot_menu(legal_set, joints, party, leads, 0, "active_0", input_fn, foe_party=foe_party, foe_leads=foe_leads, brought=brought)

    legal_set = {ji for ji in legal_set if _slot_part(joints, ji, "active_0") == s0}

    if not legal_set:
        raise RuntimeError("no joints remain after first slot choice")

    print(f"\n{slot_labels[1]}")

    s1 = _prompt_one_slot_menu(legal_set, joints, party, leads, 1, "active_1", input_fn, foe_party=foe_party, foe_leads=foe_leads, brought=brought)

    legal_set = {ji for ji in legal_set if _slot_part(joints, ji, "active_1") == s1}

    if len(legal_set) != 1:
        raise RuntimeError(f"could not resolve a unique joint (candidates {len(legal_set)})")

    return legal_set.pop()


def legal_joint_indices(mask: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.asarray(mask, dtype=bool))


def step_turn(
    state: DoublesBattleState,
    rng: random.Random,
    client: OracleClient,
    game: str,
    joint_idx_alpha: int,
    joint_idx_beta: int,
    joints: tuple[JointDoublesAction, ...],
    *,
    mega_alpha: int = 0,
    mega_beta: int = 0,
    tera_alpha: int = 0,
    tera_beta: int = 0,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
    reward_shaping: bool = False,
) -> tuple[float, bool, list[tuple[str, str]], dict[str, Any]]:
    if not (0 <= joint_idx_alpha < len(joints)):
        raise ValueError(f"joint_idx_alpha {joint_idx_alpha} out of range")

    if not (0 <= joint_idx_beta < len(joints)):
        raise ValueError(f"joint_idx_beta {joint_idx_beta} out of range")

    ma = legal_joint_mask_alpha(state, joints, game=game)
    mb = legal_joint_mask_beta(state, joints, game=game)

    if not bool(ma[joint_idx_alpha]):
        raise ValueError(f"illegal Alpha joint index {joint_idx_alpha}")

    if not bool(mb[joint_idx_beta]):
        raise ValueError(f"illegal Beta joint index {joint_idx_beta}")

    ja = joints[joint_idx_alpha]
    jb = joints[joint_idx_beta]

    planned_alpha = joint_to_planned_side(ja, state.party_a, state.leads_a, atk_side="alpha", serial_base=0, brought=state.brought_alpha_sorted())
    planned_beta = joint_to_planned_side(jb, state.party_b, state.leads_b, atk_side="beta", serial_base=2, brought=state.brought_beta_sorted())

    return resolve_turn(
        state,
        rng,
        client,
        game,
        planned_alpha,
        planned_beta,
        mega_alpha=mega_alpha,
        mega_beta=mega_beta,
        tera_alpha=tera_alpha,
        tera_beta=tera_beta,
        allow_mega_evolution=allow_mega_evolution,
        allow_terastal=allow_terastal,
        reward_shaping=reward_shaping,
    )


def trajectory_row(
    *,
    obs_before: np.ndarray,
    legal_alpha_indices: list[int],
    legal_beta_indices: list[int],
    joint_idx_alpha: int,
    joint_idx_beta: int,
    joint_label_alpha: str,
    joint_label_beta: str,
    reward: float,
    terminated: bool,
    step_index: int,
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "obs_before": obs_before.astype(float).tolist(),
        "legal_joint_indices_alpha": legal_alpha_indices,
        "legal_joint_indices_beta": legal_beta_indices,
        "joint_idx_alpha": joint_idx_alpha,
        "joint_idx_beta": joint_idx_beta,
        "joint_label_alpha": joint_label_alpha,
        "joint_label_beta": joint_label_beta,
        "reward": reward,
        "terminated": terminated,
    }


def prompt_joint_choice(
    legal_joint_indices: Sequence[int],
    joints: tuple[JointDoublesAction, ...],
    label: str,
    *,
    input_fn: Callable[[str], str],
) -> int:
    seq = list(legal_joint_indices)

    if not seq:
        raise RuntimeError(f"{label}: no legal joint actions")

    while True:
        for menu_i, ji in enumerate(seq):
            j = decode_joint_index(ji, joints)

            print(f"  [{menu_i}] joint#{ji} {format_joint_for_display(j)}")

        raw = input_fn(f"{label} choice [0-{len(seq) - 1}] (menu index): ").strip()

        try:
            pick = int(raw)
        except ValueError:
            print("Enter an integer menu index.")

            continue

        if not (0 <= pick < len(seq)):
            print(f"Out of range; need 0-{len(seq) - 1}.")

            continue

        return seq[pick]


def sample_beta_joint_index(rng: random.Random, mask_beta: np.ndarray) -> int:
    legal = legal_joint_indices(mask_beta)

    if legal.size == 0:
        raise RuntimeError("Beta has no legal joint actions")

    choices = legal.tolist()

    return int(rng.choice(choices))


def sample_random_legal_joint_index(rng: random.Random, mask: np.ndarray) -> int:
    return sample_beta_joint_index(rng, mask)


def sample_random_legal_flat_index(rng: random.Random, mask_flat: np.ndarray) -> int:
    legal = np.flatnonzero(np.asarray(mask_flat, dtype=bool))

    if legal.size == 0:
        raise RuntimeError("no legal flat actions")

    return int(rng.choice(legal.tolist()))
