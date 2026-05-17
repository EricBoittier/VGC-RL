from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vgc_rl.doubles_checkpoint import battle_state_to_checkpoint_dict
from vgc_rl.doubles_turn_engine import DoublesBattleState, side_party_wiped_brought
from vgc_rl.interactive_doubles import format_joint_human_summary

REPLAY_SCHEMA_VERSION = 1


def _form_suffix(*, mega: bool, tera: bool) -> str:
    bits: list[str] = []

    if mega:
        bits.append("Mega")

    if tera:
        bits.append("Tera")

    if not bits:
        return ""

    return " [" + " · ".join(bits) + "]"


def _action_label(
    state: DoublesBattleState,
    *,
    side: str,
    joint_index: int,
    joints: tuple[Any, ...],
    mega: bool,
    tera: bool,
) -> str:
    if joint_index < 0:
        return "—"

    joint = joints[joint_index]

    if side == "alpha":
        body = format_joint_human_summary(
            joint,
            state.party_a,
            state.leads_a,
            foe_party=state.party_b,
            foe_leads=state.leads_b,
            brought=state.brought_alpha_sorted(),
        )
    else:
        body = format_joint_human_summary(
            joint,
            state.party_b,
            state.leads_b,
            foe_party=state.party_a,
            foe_leads=state.leads_a,
            brought=state.brought_beta_sorted(),
        )

    return body + _form_suffix(mega=mega, tera=tera)


def bring_action_label(state: DoublesBattleState, *, alpha_bring_id: int, beta_bring_id: int) -> tuple[str, str]:
    from vgc_rl.bring_selection import format_six_bring_lead_prefs_line

    line = format_six_bring_lead_prefs_line(state, alpha_bring_id=alpha_bring_id, beta_bring_id=beta_bring_id)
    body = line.removeprefix("[bring-debug] ")
    parts = body.split(" || ")

    if len(parts) == 2:
        return parts[0], parts[1]

    return body, "—"


def make_replay_frame(
    state_before: DoublesBattleState,
    *,
    game: str,
    step_index: int,
    alpha_label: str,
    beta_label: str,
    events: list[tuple[str, str]],
    reward: float,
    terminated: bool,
    truncated: bool = False,
    frame_kind: str = "turn",
) -> dict[str, Any]:
    return {
        "kind": frame_kind,
        "turn": int(step_index),
        "state_before": battle_state_to_checkpoint_dict(state_before, game=game, step_count=step_index),
        "alpha_action": alpha_label,
        "beta_action": beta_label,
        "events": [[tag, body] for tag, body in events],
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }


def attach_turn_replay_frame(
    info: dict[str, Any],
    *,
    state_before: DoublesBattleState,
    game: str,
    step_index: int,
    joints: tuple[Any, ...],
    joint_index_alpha: int,
    joint_index_beta: int,
    mega_alpha: bool,
    mega_beta: bool,
    tera_alpha: bool,
    tera_beta: bool,
    events: list[tuple[str, str]],
    reward: float,
    terminated: bool,
    truncated: bool = False,
) -> None:
    alpha_label = _action_label(
        state_before,
        side="alpha",
        joint_index=joint_index_alpha,
        joints=joints,
        mega=mega_alpha,
        tera=tera_alpha,
    )
    beta_label = _action_label(
        state_before,
        side="beta",
        joint_index=joint_index_beta,
        joints=joints,
        mega=mega_beta,
        tera=tera_beta,
    )

    info["replay_frame"] = make_replay_frame(
        state_before,
        game=game,
        step_index=step_index,
        alpha_label=alpha_label,
        beta_label=beta_label,
        events=events,
        reward=reward,
        terminated=terminated,
        truncated=truncated,
        frame_kind="turn",
    )


def attach_bring_replay_frame(
    info: dict[str, Any],
    *,
    state_after_bring: DoublesBattleState,
    game: str,
    alpha_bring_id: int,
    beta_bring_id: int,
) -> None:
    alpha_label, beta_label = bring_action_label(state_after_bring, alpha_bring_id=alpha_bring_id, beta_bring_id=beta_bring_id)

    info["replay_frame"] = make_replay_frame(
        state_after_bring,
        game=game,
        step_index=0,
        alpha_label=alpha_label,
        beta_label=beta_label,
        events=[],
        reward=0.0,
        terminated=False,
        frame_kind="bring",
    )


def replay_outcome(
    *,
    terminated: bool,
    truncated: bool,
    party_wiped_alpha: bool,
    party_wiped_beta: bool,
    last_reward_beta: float | None = None,
) -> str:
    if party_wiped_alpha and not party_wiped_beta:
        return "beta_win"

    if party_wiped_beta and not party_wiped_alpha:
        return "alpha_win"

    if party_wiped_alpha and party_wiped_beta:
        return "draw"

    if terminated and last_reward_beta is not None:
        if last_reward_beta > 1e-6:
            return "beta_win"

        if last_reward_beta < -1e-6:
            return "alpha_win"

        return "draw"

    if truncated and not terminated:
        return "truncated"

    return "ongoing"


def _living_brought_speed_total(state: DoublesBattleState, *, alpha: bool) -> float:
    party = state.party_a if alpha else state.party_b
    brought = state.brought_alpha_sorted() if alpha else state.brought_beta_sorted()
    total = 0.0

    for idx in brought:
        mon = party[idx]

        if float(mon.get("hpPercentage") or 0) <= 0:
            continue

        evs = mon.get("evs") if isinstance(mon.get("evs"), dict) else {}
        boosts = mon.get("boosts") if isinstance(mon.get("boosts"), dict) else {}
        total += float(evs.get("spe", 0) or 0) + float(boosts.get("spe", 0) or 0)

    return total


def _living_brought_hp_total(state: DoublesBattleState, *, alpha: bool) -> float:
    party = state.party_a if alpha else state.party_b
    brought = state.brought_alpha_sorted() if alpha else state.brought_beta_sorted()

    return sum(float(party[i].get("hpPercentage") or 0) for i in brought)


def force_battle_outcome(
    state: DoublesBattleState | None,
    *,
    last_reward_beta: float | None = None,
) -> str:
    if state is not None:
        party_wiped_alpha = side_party_wiped_brought(state, alpha=True)
        party_wiped_beta = side_party_wiped_brought(state, alpha=False)

        if party_wiped_alpha and not party_wiped_beta:
            return "beta_win"

        if party_wiped_beta and not party_wiped_alpha:
            return "alpha_win"

        hp_a = _living_brought_hp_total(state, alpha=True)
        hp_b = _living_brought_hp_total(state, alpha=False)

        if hp_a > hp_b + 1e-6:
            return "alpha_win"

        if hp_b > hp_a + 1e-6:
            return "beta_win"

        spe_a = _living_brought_speed_total(state, alpha=True)
        spe_b = _living_brought_speed_total(state, alpha=False)

        if spe_a > spe_b + 1e-6:
            return "alpha_win"

        if spe_b > spe_a + 1e-6:
            return "beta_win"

    if last_reward_beta is not None:
        if last_reward_beta > 1e-6:
            return "beta_win"

        if last_reward_beta < -1e-6:
            return "alpha_win"

    return "alpha_win"


def replay_outcome_from_state(
    state: DoublesBattleState | None,
    *,
    terminated: bool,
    truncated: bool,
    last_reward_beta: float | None = None,
    require_winner: bool = False,
) -> str:
    if require_winner:
        if state is not None:
            party_wiped_alpha = side_party_wiped_brought(state, alpha=True)
            party_wiped_beta = side_party_wiped_brought(state, alpha=False)

            if party_wiped_alpha or party_wiped_beta or terminated or truncated:
                return force_battle_outcome(state, last_reward_beta=last_reward_beta)

        return force_battle_outcome(state, last_reward_beta=last_reward_beta)

    if state is None:
        return replay_outcome(
            terminated=terminated,
            truncated=truncated,
            party_wiped_alpha=False,
            party_wiped_beta=False,
            last_reward_beta=last_reward_beta,
        )

    party_wiped_alpha = side_party_wiped_brought(state, alpha=True)
    party_wiped_beta = side_party_wiped_brought(state, alpha=False)

    if not party_wiped_alpha and not party_wiped_beta and (terminated or truncated):
        brought_a = state.brought_alpha_sorted()
        brought_b = state.brought_beta_sorted()
        hp_a = sum(float(state.party_a[i].get("hpPercentage") or 0) for i in brought_a)
        hp_b = sum(float(state.party_b[i].get("hpPercentage") or 0) for i in brought_b)

        if hp_a > hp_b + 1e-6:
            return "alpha_win"

        if hp_b > hp_a + 1e-6:
            return "beta_win"

        if terminated or truncated:
            return force_battle_outcome(state, last_reward_beta=last_reward_beta)

    return replay_outcome(
        terminated=terminated,
        truncated=truncated,
        party_wiped_alpha=party_wiped_alpha,
        party_wiped_beta=party_wiped_beta,
        last_reward_beta=last_reward_beta,
    )


def build_replay_document(
    *,
    game: str,
    meta: dict[str, Any],
    initial_state: dict[str, Any] | None,
    frames: list[dict[str, Any]],
    final_state: dict[str, Any] | None,
    outcome: str,
) -> dict[str, Any]:
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "game": game,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "initial": initial_state,
        "frames": frames,
        "final": final_state,
        "outcome": outcome,
    }


def write_replay(path: Path | str, document: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2)

    with open(p, "w", encoding="utf-8") as f:
        f.write(text)

    return p.resolve()


def list_replay_files(directory: Path | str) -> list[Path]:
    root = Path(directory)

    if not root.is_dir():
        return []

    return sorted(root.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)


def snapshot_state(state: DoublesBattleState | None, *, game: str, step_count: int = 0) -> dict[str, Any] | None:
    if state is None:
        return None

    return battle_state_to_checkpoint_dict(deepcopy(state), game=game, step_count=step_count)
