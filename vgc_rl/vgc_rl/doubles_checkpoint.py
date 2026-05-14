from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from vgc_rl.doubles_turn_engine import DoublesBattleState

CHECKPOINT_SCHEMA_VERSION = 4
CHECKPOINT_SCHEMA_MIN = 1


def _protect_to_serial(protect_prior_successes: dict[tuple[str, int], int]) -> dict[str, int]:
    out: dict[str, int] = {}

    for (side, pi), v in protect_prior_successes.items():
        out[f"{side}:{pi}"] = int(v)

    return out


def _protect_from_serial(raw: dict[str, Any]) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}

    for k, v in raw.items():
        if ":" not in str(k):
            continue

        side, _, rest = str(k).partition(":")

        out[(side, int(rest))] = int(v)

    return out


def battle_state_to_checkpoint_dict(
    state: DoublesBattleState,
    *,
    game: str,
    seed: int | None = None,
    step_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "game": game,
        "seed": seed,
        "step_count": step_count,
        "party_a": deepcopy(state.party_a),
        "party_b": deepcopy(state.party_b),
        "leads_a": list(state.leads_a),
        "leads_b": list(state.leads_b),
        "alpha_tailwind_turns_left": int(state.alpha_tailwind_turns_left),
        "beta_tailwind_turns_left": int(state.beta_tailwind_turns_left),
        "protect_prior_successes": _protect_to_serial(state.protect_prior_successes),
        "weather": state.weather,
        "weather_turns_left": int(state.weather_turns_left),
        "electro_shot_charging": {f"{k[0]}:{k[1]}": True for k, v in state.electro_shot_charging.items() if v},
        "alpha_mega_used": bool(state.alpha_mega_used),
        "beta_mega_used": bool(state.beta_mega_used),
        "alpha_tera_used": bool(state.alpha_tera_used),
        "beta_tera_used": bool(state.beta_tera_used),
        "team_alpha_path": state.team_alpha_path,
        "team_beta_path": state.team_beta_path,
        "team_alpha_id": state.team_alpha_id,
        "team_beta_id": state.team_beta_id,
        "brought_a": list(state.brought_alpha_sorted()) if len(state.party_a) == 6 or state.brought_a is not None else None,
        "brought_b": list(state.brought_beta_sorted()) if len(state.party_b) == 6 or state.brought_b is not None else None,
    }


def battle_state_from_checkpoint_dict(data: dict[str, Any]) -> tuple[DoublesBattleState, str, int | None, int]:
    ver = int(data.get("schema_version") or 0)

    if ver < CHECKPOINT_SCHEMA_MIN or ver > CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(f"unsupported checkpoint schema_version {ver!r} (expected {CHECKPOINT_SCHEMA_MIN}..{CHECKPOINT_SCHEMA_VERSION})")

    game = str(data["game"])
    seed = data.get("seed")

    if seed is not None:
        seed = int(seed)

    step_count = int(data.get("step_count") or 0)

    tap = data.get("team_alpha_path")
    tbp = data.get("team_beta_path")

    if tap is not None:
        tap = str(tap)

    if tbp is not None:
        tbp = str(tbp)

    tai = data.get("team_alpha_id")
    tbi = data.get("team_beta_id")

    if tai is not None:
        tai = str(tai)

    if tbi is not None:
        tbi = str(tbi)

    bra = data.get("brought_a")
    brb = data.get("brought_b")

    brought_a_tuple: tuple[int, int, int, int] | None = None
    brought_b_tuple: tuple[int, int, int, int] | None = None

    if isinstance(bra, list) and len(bra) == 4:
        brought_a_tuple = tuple(int(x) for x in bra)

    if isinstance(brb, list) and len(brb) == 4:
        brought_b_tuple = tuple(int(x) for x in brb)

    raw_prot = data.get("protect_prior_successes") or {}

    if not isinstance(raw_prot, dict):
        raw_prot = {}

    raw_charge = data.get("electro_shot_charging") or {}

    if not isinstance(raw_charge, dict):
        raw_charge = {}

    electro: dict[tuple[str, int], bool] = {}

    for k, v in raw_charge.items():
        if not v:
            continue

        if ":" not in str(k):
            continue

        side, _, rest = str(k).partition(":")

        electro[(side, int(rest))] = True

    wthr = data.get("weather")

    if wthr is not None:
        wthr = str(wthr)

    state = DoublesBattleState(
        party_a=deepcopy(data["party_a"]),
        party_b=deepcopy(data["party_b"]),
        leads_a=list(data["leads_a"]),
        leads_b=list(data["leads_b"]),
        alpha_tailwind_turns_left=int(data.get("alpha_tailwind_turns_left") or 0),
        beta_tailwind_turns_left=int(data.get("beta_tailwind_turns_left") or 0),
        protect_prior_successes=_protect_from_serial(raw_prot),
        weather=wthr,
        weather_turns_left=int(data.get("weather_turns_left") or 0),
        electro_shot_charging=electro,
        alpha_mega_used=bool(data.get("alpha_mega_used")),
        beta_mega_used=bool(data.get("beta_mega_used")),
        alpha_tera_used=bool(data.get("alpha_tera_used")),
        beta_tera_used=bool(data.get("beta_tera_used")),
        team_alpha_path=tap,
        team_beta_path=tbp,
        team_alpha_id=tai,
        team_beta_id=tbi,
        brought_a=brought_a_tuple,
        brought_b=brought_b_tuple,
    )

    return state, game, seed, step_count


def write_checkpoint(path: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_checkpoint(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
