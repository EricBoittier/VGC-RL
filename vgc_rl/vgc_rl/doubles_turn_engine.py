from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from vgc_rl.champions_metadata import move_category_champions
from vgc_rl.doubles_ability_hooks import defiant_boost_after_opponent_unboost, rough_skin_if, stamina_if_damaging_hit
from vgc_rl.doubles_actions import JointDoublesAction, MoveSlotAction, SendOutMoveSlotAction, SwitchSlotAction, DoublesTarget
from vgc_rl.doubles_move_targeting import (
    ALL_ADJACENT_EXCEPT_USER_MOVES,
    FIELD_STATUS_MOVES,
    SIDE_STATUS_MOVES,
    SPREAD_BOTH_OPPONENTS_MOVES,
    showdown_target_for_move,
)
from vgc_rl.doubles_protect_moves import PROTECT_FAMILY_MOVES
from vgc_rl.doubles_status_effects import (
    STATUS_EFFECT_MOVES,
    apply_damage_through_substitute,
    resolve_side_status,
    resolve_status_effect,
)
from vgc_rl.example_teams import with_active_move
from vgc_rl.held_item_effects import (
    black_sludge_tick,
    leftovers_heal,
    life_orb_recoil_if,
    maybe_lum_berry,
    maybe_trigger_heal_berries,
    maybe_weakness_policy,
    rocky_helmet_if,
    try_white_herb_clear,
)
from vgc_rl.held_item_rules import clear_choice_lock, set_choice_lock
from vgc_rl.oracle_client import OracleClient
from vgc_rl.turn_sim import STATUS_NO_CALC, _initiative_first, _sort_by_initiative

TAILWIND_DURATION_TURNS = 4

_PROTECT_STALL_MOVES = PROTECT_FAMILY_MOVES

_SPREAD_BOTH_OPPONENTS_MOVES = SPREAD_BOTH_OPPONENTS_MOVES

_BOOST_KEYS = ("atk", "def", "spa", "spd", "spe")

_SPREAD_FOE_STAT_DROPS: dict[str, dict[str, int]] = {
    "Growl": {"atk": -1},
    "Icy Wind": {"spe": -1},
    "Leer": {"def": -1},
    "Snarl": {"atk": -1},
    "Struggle Bug": {"spa": -1},
    "Tail Whip": {"def": -1},
}

_SELF_STAT_DROP_AFTER_HIT: dict[str, dict[str, int]] = {
    "Draco Meteor": {"spa": -2},
}

_FOCUS_SASH_ITEM_NAMES = frozenset({"focus sash"})

_FOCUS_SASH_SURVIVAL_HP_PCT = 0.01


def _item_key(mon: dict[str, Any]) -> str:
    return str(mon.get("item") or "").strip().lower()


def _apply_intimidate(state: DoublesBattleState, events: list[tuple[str, str]], *, switching_side: str) -> None:
    if switching_side == "alpha":
        foe_party = state.party_b
        foe_leads = state.leads_b
        foe_side = "beta"
    else:
        foe_party = state.party_a
        foe_leads = state.leads_a
        foe_side = "alpha"

    for fi in range(2):
        dpi = foe_leads[fi]
        mon = foe_party[dpi]

        if float(mon.get("hpPercentage") or 0) <= 0:
            continue

        chg = apply_boost_delta(mon, "atk", -1)
        addr = active_address(foe_side, fi, mon)

        if chg != 0:
            events.append(("-unboost", f"{addr} atk {chg:+d} (Intimidate)"))

        defiant_boost_after_opponent_unboost(mon, events, addr, had_negative_stage_change=chg < 0)
        try_white_herb_clear(mon, events, addr)

_ELECTRO_SHOT = "Electro Shot"

_SUCKER_PUNCH = "Sucker Punch"

_WEATHER_SETTING_MOVES: dict[str, tuple[str, int]] = {
    "Rain Dance": ("Rain", 5),
    "Sandstorm": ("Sand", 5),
    "Snowscape": ("Snow", 5),
    "Sunny Day": ("Sun", 5),
}

_ENTRY_WEATHER_ABILITIES: dict[str, tuple[str, int]] = {
    "Drizzle": ("Rain", 5),
    "Drought": ("Sun", 5),
    "Sand Stream": ("Sand", 5),
    "Snow Warning": ("Snow", 5),
}


def normalize_mon_boosts(mon: dict[str, Any]) -> None:
    raw = mon.get("boosts")

    if not isinstance(raw, dict):
        mon["boosts"] = {k: 0 for k in _BOOST_KEYS}

        return

    for k in _BOOST_KEYS:
        raw.setdefault(k, 0)


def normalize_state_boosts(state: DoublesBattleState) -> None:
    for m in state.party_a + state.party_b:
        normalize_mon_boosts(m)


def apply_boost_delta(mon: dict[str, Any], stat: str, delta: int) -> int:
    normalize_mon_boosts(mon)
    cur = int(mon["boosts"][stat])
    new = max(-6, min(6, cur + delta))

    mon["boosts"][stat] = new

    return new - cur


def apply_initial_field_weather(state: DoublesBattleState) -> None:
    for party, leads in ((state.party_a, state.leads_a), (state.party_b, state.leads_b)):
        for fi in range(2):
            pi = leads[fi]

            if float(party[pi].get("hpPercentage") or 0) <= 0:
                continue

            ab = str(party[pi].get("ability") or "")
            pair = _ENTRY_WEATHER_ABILITIES.get(ab)

            if pair:
                state.weather, state.weather_turns_left = pair


def protect_success_probability(prior_consecutive_successes: int) -> float:
    return (1.0 / 3.0) ** prior_consecutive_successes


def side_party_wiped(party: list[dict[str, Any]]) -> bool:
    return all(float(p.get("hpPercentage") or 0) <= 0 for p in party)


def side_party_wiped_brought(state: DoublesBattleState, *, alpha: bool) -> bool:
    party = state.party_a if alpha else state.party_b
    brought = state.brought_alpha_sorted() if alpha else state.brought_beta_sorted()

    return all(float(party[i].get("hpPercentage") or 0) <= 0 for i in brought)


def validate_battle_roster(state: DoublesBattleState) -> None:
    ba = frozenset(state.brought_alpha_sorted())
    bb = frozenset(state.brought_beta_sorted())

    if len(state.leads_a) != 2 or len(set(state.leads_a)) != 2:
        raise RuntimeError("leads_a must name two distinct party indices")

    if len(state.leads_b) != 2 or len(set(state.leads_b)) != 2:
        raise RuntimeError("leads_b must name two distinct party indices")

    if any(pi not in ba for pi in state.leads_a):
        raise RuntimeError("Alpha leads must be within brought_alpha roster")

    if any(pi not in bb for pi in state.leads_b):
        raise RuntimeError("Beta leads must be within brought_beta roster")


def living_bench_indices(
    party: list[dict[str, Any]],
    leads: list[int],
    chosen: set[int],
    *,
    brought_indices: tuple[int, int, int, int] | None = None,
) -> list[int]:
    busy = set(leads)
    out: list[int] = []
    pool = sorted(brought_indices) if brought_indices is not None else list(range(len(party)))

    for i in pool:
        if i in busy or i in chosen:
            continue

        if float(party[i].get("hpPercentage") or 0) <= 0:
            continue

        out.append(i)

    return out


def bench_party_positions_for_brought(leads: list[int], brought: tuple[int, int, int, int]) -> list[int]:
    busy = set(leads)

    return sorted(i for i in brought if i not in busy)


def bench_slot_to_party_index(leads: list[int], bench_slot: int, *, brought: tuple[int, int, int, int]) -> int | None:
    bench = bench_party_positions_for_brought(leads, brought)

    if bench_slot < 0 or bench_slot >= len(bench):
        return None

    return bench[bench_slot]


def trainer_side_word(side: str) -> str:
    return "Alpha" if side == "alpha" else "Beta"


def slot_letter(field_idx: int) -> str:
    return chr(ord("A") + field_idx)


def active_address(side: str, field_idx: int, mon: dict[str, Any]) -> str:
    return f"{trainer_side_word(side)}[{slot_letter(field_idx)}] {mon.get('name') or '?'}"


def sort_switch_actions(
    client: OracleClient,
    game: str,
    field: dict[str, Any],
    switches: list[dict[str, Any]],
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    leads_a: list[int],
    leads_b: list[int],
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []

    def payload(it: dict[str, Any]) -> dict[str, Any]:
        party = party_a if it["atk_side"] == "alpha" else party_b
        ld = leads_a if it["atk_side"] == "alpha" else leads_b
        pi = ld[it["field_idx"]]

        return with_active_move(party[pi], 1)

    for item in switches:
        placed = False

        for j in range(len(ordered)):
            other = ordered[j]

            if _initiative_first(
                client,
                game,
                field,
                payload(item),
                payload(other),
                left_side=item["atk_side"],
                right_side=other["atk_side"],
                left_index=item["orig_index"],
                right_index=other["orig_index"],
            ):
                ordered.insert(j, item)

                placed = True

                break

        if not placed:
            ordered.append(item)

    return ordered


def joint_to_planned_side(
    joint: JointDoublesAction,
    party: list[dict[str, Any]],
    leads: list[int],
    *,
    atk_side: str,
    serial_base: int,
    brought: tuple[int, int, int, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    def slot_plan(slot_action: MoveSlotAction | SwitchSlotAction | SendOutMoveSlotAction, field_idx: int, serial: int) -> dict[str, Any]:
        if isinstance(slot_action, SwitchSlotAction):
            to_pi = bench_slot_to_party_index(leads, slot_action.bench_index, brought=brought)

            if to_pi is None:
                return {"kind": "skip", "atk_side": atk_side, "field_idx": field_idx, "orig_index": serial}

            return {
                "kind": "switch",
                "atk_side": atk_side,
                "field_idx": field_idx,
                "to_party": to_pi,
                "orig_index": serial,
            }

        if isinstance(slot_action, SendOutMoveSlotAction):
            to_pi = bench_slot_to_party_index(leads, slot_action.bench_index, brought=brought)

            if to_pi is None:
                return {"kind": "skip", "atk_side": atk_side, "field_idx": field_idx, "orig_index": serial}

            return {
                "kind": "switch",
                "atk_side": atk_side,
                "field_idx": field_idx,
                "to_party": to_pi,
                "orig_index": serial,
                "forced_replace_move_slot": slot_action.move_slot + 1,
                "forced_replace_target": int(slot_action.target),
            }

        ms = slot_action.move_slot + 1

        return {
            "kind": "move",
            "atk_side": atk_side,
            "field_idx": field_idx,
            "move_slot": ms,
            "orig_index": serial,
            "doubles_target": int(slot_action.target),
        }

    p0 = slot_plan(joint.active_0, 0, serial_base)
    p1 = slot_plan(joint.active_1, 1, serial_base + 1)

    return p0, p1


def merge_planned_turn(planned_alpha: tuple[dict[str, Any], dict[str, Any]], planned_beta: tuple[dict[str, Any], dict[str, Any]]) -> list[dict[str, Any]]:
    a0, a1 = planned_alpha
    b0, b1 = planned_beta

    return [
        {**a0, "atk_side": "alpha"},
        {**a1, "atk_side": "alpha"},
        {**b0, "atk_side": "beta"},
        {**b1, "atk_side": "beta"},
    ]


def _ensure_batch_ok(row: dict[str, Any], ctx: str) -> None:
    if row.get("ok"):
        return

    raise RuntimeError(f"{ctx}: {row.get('error', 'oracle batch failed')}")


@dataclass
class DoublesBattleState:
    party_a: list[dict[str, Any]]
    party_b: list[dict[str, Any]]
    leads_a: list[int]
    leads_b: list[int]
    alpha_tailwind_turns_left: int = 0
    beta_tailwind_turns_left: int = 0
    protect_prior_successes: dict[tuple[str, int], int] = field(default_factory=dict)
    weather: str | None = None
    weather_turns_left: int = 0
    electro_shot_charging: dict[tuple[str, int], bool] = field(default_factory=dict)
    alpha_mega_used: bool = False
    beta_mega_used: bool = False
    alpha_tera_used: bool = False
    beta_tera_used: bool = False
    team_alpha_path: str | None = None
    team_beta_path: str | None = None
    team_alpha_id: str | None = None
    team_beta_id: str | None = None
    brought_a: tuple[int, int, int, int] | None = None
    brought_b: tuple[int, int, int, int] | None = None

    def brought_alpha_sorted(self) -> tuple[int, int, int, int]:
        if self.brought_a is not None:
            t = tuple(sorted(self.brought_a))

            if len(set(t)) != 4:
                raise ValueError("brought_a must name four distinct party indices")

            if any(i < 0 or i >= len(self.party_a) for i in t):
                raise ValueError("brought_a indices out of range for party_a")

            return t

        n = len(self.party_a)

        if n == 4:
            return (0, 1, 2, 3)

        if n == 6:
            return (0, 1, 2, 3)

        raise ValueError(f"party_a length must be 4 or 6 when brought_a is unset (got {n})")

    def brought_beta_sorted(self) -> tuple[int, int, int, int]:
        if self.brought_b is not None:
            t = tuple(sorted(self.brought_b))

            if len(set(t)) != 4:
                raise ValueError("brought_b must name four distinct party indices")

            if any(i < 0 or i >= len(self.party_b) for i in t):
                raise ValueError("brought_b indices out of range for party_b")

            return t

        n = len(self.party_b)

        if n == 4:
            return (0, 1, 2, 3)

        if n == 6:
            return (0, 1, 2, 3)

        raise ValueError(f"party_b length must be 4 or 6 when brought_b is unset (got {n})")

    def battle_obs_party_slice_alpha(self) -> list[dict[str, Any]]:
        return [self.party_a[i] for i in sorted(self.brought_alpha_sorted())]

    def battle_obs_party_slice_beta(self) -> list[dict[str, Any]]:
        return [self.party_b[i] for i in sorted(self.brought_beta_sorted())]

    def field_payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "alphaSide": {"isTailwind": self.alpha_tailwind_turns_left > 0},
            "betaSide": {"isTailwind": self.beta_tailwind_turns_left > 0},
        }

        if self.weather:
            out["weather"] = self.weather

        def active_slots(leads: list[int], party: list[dict[str, Any]]) -> list[dict[str, Any]]:
            slots: list[dict[str, Any]] = []

            for fi in range(2):
                pi = leads[fi]
                mon = party[pi]

                normalize_mon_boosts(mon)

                slots.append({"partyIndex": pi, "boosts": dict(mon["boosts"])})

            return slots

        out["alphaActives"] = active_slots(self.leads_a, self.party_a)
        out["betaActives"] = active_slots(self.leads_b, self.party_b)

        return out


def _planned_slot_kind(planned: list[dict[str, Any]], side: str, fi: int) -> str | None:
    want = fi if side == "alpha" else (2 + fi)

    for x in planned:
        if x.get("atk_side") != side:
            continue

        if int(x.get("orig_index", -999)) != want:
            continue

        return str(x.get("kind"))

    return None


def _try_mega_declaration(
    state: DoublesBattleState,
    planned: list[dict[str, Any]],
    *,
    side: str,
    choice: int,
    game: str,
    allow: bool,
    events: list[tuple[str, str]],
) -> None:
    if choice == 0:
        return

    if game != "champions" or not allow:
        return

    if side == "alpha":
        if state.alpha_mega_used:
            return
    elif state.beta_mega_used:
        return

    fi = choice - 1

    if fi not in (0, 1):
        return

    if _planned_slot_kind(planned, side, fi) != "move":
        return

    party = state.party_a if side == "alpha" else state.party_b
    leads = state.leads_a if side == "alpha" else state.leads_b
    pi = leads[fi]
    mon = party[pi]

    if float(mon.get("hpPercentage") or 0) <= 0:
        return

    from vgc_rl.doubles_mega_tera import apply_mega_evolution, can_mega_evolve_species

    if not can_mega_evolve_species(mon, game=game):
        return

    old_name = str(mon.get("name") or "?")

    if not apply_mega_evolution(mon):
        return

    if side == "alpha":
        state.alpha_mega_used = True
    else:
        state.beta_mega_used = True

    addr = active_address(side, fi, mon)

    events.append(("-mega", f"{addr}: {old_name} → {mon.get('name')} ({mon.get('ability')})"))

    ab = str(mon.get("ability") or "")
    wp = _ENTRY_WEATHER_ABILITIES.get(ab)

    if wp:
        state.weather, state.weather_turns_left = wp

        events.append(("-weather", f"{wp[0]} · {wp[1]} turns · {ab}"))


def _try_tera_declaration(
    state: DoublesBattleState,
    planned: list[dict[str, Any]],
    *,
    side: str,
    choice: int,
    game: str,
    allow: bool,
    events: list[tuple[str, str]],
) -> None:
    if choice == 0:
        return

    if game != "sv" or not allow:
        return

    if side == "alpha":
        if state.alpha_tera_used:
            return
    elif state.beta_tera_used:
        return

    fi = choice - 1

    if fi not in (0, 1):
        return

    if _planned_slot_kind(planned, side, fi) != "move":
        return

    party = state.party_a if side == "alpha" else state.party_b
    leads = state.leads_a if side == "alpha" else state.leads_b
    pi = leads[fi]
    mon = party[pi]

    if float(mon.get("hpPercentage") or 0) <= 0:
        return

    from vgc_rl.doubles_mega_tera import apply_terastal, can_terastal

    if not can_terastal(mon, game=game):
        return

    tt = str(mon.get("teraType") or "").strip()

    if not apply_terastal(mon):
        return

    if side == "alpha":
        state.alpha_tera_used = True
    else:
        state.beta_tera_used = True

    addr = active_address(side, fi, mon)

    events.append(("-terastallize", f"{addr} Terastal ({tt})"))


def _apply_form_declarations_phase(
    state: DoublesBattleState,
    planned: list[dict[str, Any]],
    game: str,
    *,
    mega_alpha: int,
    mega_beta: int,
    tera_alpha: int,
    tera_beta: int,
    allow_mega_evolution: bool,
    allow_terastal: bool,
    events: list[tuple[str, str]],
) -> None:
    _try_mega_declaration(state, planned, side="alpha", choice=mega_alpha, game=game, allow=allow_mega_evolution, events=events)
    _try_mega_declaration(state, planned, side="beta", choice=mega_beta, game=game, allow=allow_mega_evolution, events=events)
    _try_tera_declaration(state, planned, side="alpha", choice=tera_alpha, game=game, allow=allow_terastal, events=events)
    _try_tera_declaration(state, planned, side="beta", choice=tera_beta, game=game, allow=allow_terastal, events=events)


def resolve_turn_flat(
    state: DoublesBattleState,
    rng: random.Random,
    client: OracleClient,
    game: str,
    planned: list[dict[str, Any]],
    *,
    mega_alpha: int = 0,
    mega_beta: int = 0,
    tera_alpha: int = 0,
    tera_beta: int = 0,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
    reward_shaping: bool = False,
) -> tuple[float, bool, list[tuple[str, str]], dict[str, Any]]:
    events: list[tuple[str, str]] = []
    debug: dict[str, Any] = {"alpha_damage_dealt": 0.0, "alpha_damage_taken": 0.0, "beta_damage_dealt": 0.0, "beta_damage_taken": 0.0}

    normalize_state_boosts(state)

    validate_battle_roster(state)

    party_a = state.party_a
    party_b = state.party_b
    leads_a = state.leads_a
    leads_b = state.leads_b

    field = state.field_payload()

    switches = [x for x in planned if x["kind"] == "switch"]

    if switches:
        ordered_sw = sort_switch_actions(client, game, field, switches, party_a, party_b, leads_a, leads_b)

        sw_bits: list[str] = []

        for it in ordered_sw:
            pty = party_a if it["atk_side"] == "alpha" else party_b
            ld = leads_a if it["atk_side"] == "alpha" else leads_b
            pi_cur = ld[it["field_idx"]]
            mon = pty[pi_cur]
            sw_bits.append(f"{active_address(it['atk_side'], it['field_idx'], mon)} → #{it['to_party']}")

        events.append(("-hint", "switch phase → " + " · ".join(sw_bits)))

        for sw in ordered_sw:
            side = sw["atk_side"]
            fi = sw["field_idx"]
            to_pi = sw["to_party"]
            pty = party_a if side == "alpha" else party_b
            ld = leads_a if side == "alpha" else leads_b
            old_pi = ld[fi]

            if ld[1 - fi] == to_pi:
                events.append(("-hint", f"{trainer_side_word(side)} slot {slot_letter(fi)} switch skipped (illegal target)."))

                continue

            out_m = pty[old_pi]
            in_m = pty[to_pi]
            clear_choice_lock(out_m)
            clear_choice_lock(in_m)
            old_addr = active_address(side, fi, out_m)
            was_faint = float(out_m.get("hpPercentage") or 0) <= 0
            tok = "a" if side == "alpha" else "b"

            state.electro_shot_charging.pop((tok, old_pi), None)
            ld[fi] = to_pi

            if was_faint:
                events.append(("switch", f"{old_addr} fainted · go! {in_m.get('name')} (party #{to_pi})"))
            else:
                events.append(("switch", f"{old_addr} withdrew · go! {in_m.get('name')} (party #{to_pi})"))

            ab_in = str(in_m.get("ability") or "")
            pair_in = _ENTRY_WEATHER_ABILITIES.get(ab_in)

            if pair_in:
                state.weather, state.weather_turns_left = pair_in

            if ab_in == "Intimidate":
                _apply_intimidate(state, events, switching_side=side)

    _apply_form_declarations_phase(
        state,
        planned,
        game,
        mega_alpha=mega_alpha,
        mega_beta=mega_beta,
        tera_alpha=tera_alpha,
        tera_beta=tera_beta,
        allow_mega_evolution=allow_mega_evolution,
        allow_terastal=allow_terastal,
        events=events,
    )

    moves_only = [x for x in planned if x["kind"] == "move"]

    forced_follow: list[dict[str, Any]] = []

    for x in planned:
        if x.get("kind") != "switch":
            continue

        fms = x.get("forced_replace_move_slot")

        if fms is None:
            continue

        forced_follow.append(
            {
                "atk_side": x["atk_side"],
                "field_idx": int(x["field_idx"]),
                "move_slot": int(fms),
                "orig_index": int(x["orig_index"]),
                "doubles_target": int(x.get("forced_replace_target", int(DoublesTarget.NONE))),
            }
        )

    prepared: list[dict[str, Any]] = []

    for it in moves_only:
        pty = party_a if it["atk_side"] == "alpha" else party_b
        ld = leads_a if it["atk_side"] == "alpha" else leads_b
        fi = it["field_idx"]
        pi = ld[fi]

        if float(pty[pi].get("hpPercentage") or 0) <= 0:
            continue

        ms = it["move_slot"]

        prepared.append(
            {
                "atk_side": it["atk_side"],
                "field_idx": fi,
                "move_slot": ms,
                "atk_payload": with_active_move(pty[pi], ms),
                "orig_index": it["orig_index"],
                "doubles_target": it.get("doubles_target"),
            }
        )

    for it in forced_follow:
        pty = party_a if it["atk_side"] == "alpha" else party_b
        ld = leads_a if it["atk_side"] == "alpha" else leads_b
        fi = it["field_idx"]
        pi = ld[fi]

        if float(pty[pi].get("hpPercentage") or 0) <= 0:
            continue

        ms = it["move_slot"]

        prepared.append(
            {
                "atk_side": it["atk_side"],
                "field_idx": fi,
                "move_slot": ms,
                "atk_payload": with_active_move(pty[pi], ms),
                "orig_index": it["orig_index"],
                "doubles_target": it.get("doubles_target"),
            }
        )

    declared_move_by_active: dict[tuple[str, int], str] = {}

    for it in prepared:
        pty = party_a if it["atk_side"] == "alpha" else party_b
        ld = leads_a if it["atk_side"] == "alpha" else leads_b
        fi = int(it["field_idx"])
        pi = ld[fi]

        if float(pty[pi].get("hpPercentage") or 0) <= 0:
            continue

        ms = int(it["move_slot"])
        nm = str(pty[pi]["moves"][ms - 1]["name"])
        declared_move_by_active[(str(it["atk_side"]), fi)] = nm

    ordered_moves: list[dict[str, Any]] = []

    if prepared:
        ordered_moves = _sort_by_initiative(client, game, field, prepared)

        mv_bits: list[str] = []

        for it in ordered_moves:
            pty = party_a if it["atk_side"] == "alpha" else party_b
            ld = leads_a if it["atk_side"] == "alpha" else leads_b
            pack = pty[ld[it["field_idx"]]]
            mv = pack["moves"][it["move_slot"] - 1]["name"]
            mv_bits.append(f"{active_address(it['atk_side'], it['field_idx'], pack)} ({mv})")

        events.append(("-hint", "move phase → " + " · ".join(mv_bits)))

    protected: set[tuple[str, int]] = set()

    for item in ordered_moves:
        field = state.field_payload()
        atk_side = item["atk_side"]
        field_idx = item["field_idx"]
        move_slot = item["move_slot"]

        own_party = party_a if atk_side == "alpha" else party_b
        own_leads = leads_a if atk_side == "alpha" else leads_b
        pi_slot = own_leads[field_idx]

        if float(own_party[pi_slot].get("hpPercentage") or 0) <= 0:
            continue

        atk_mon = own_party[pi_slot]
        atk_payload = with_active_move(atk_mon, move_slot)
        slot_mv = str(atk_mon["moves"][move_slot - 1]["name"])

        atk_addr = active_address(atk_side, field_idx, atk_mon)

        prot_k = ("a" if atk_side == "alpha" else "b", pi_slot)

        if slot_mv in _PROTECT_STALL_MOVES:
            streak = state.protect_prior_successes.get(prot_k, 0)
            p_succ = protect_success_probability(streak)

            events.append(("move", f"{atk_addr} used {slot_mv}!"))

            if rng.random() < p_succ:
                state.protect_prior_successes[prot_k] = streak + 1

                protected.add((atk_side, field_idx))

                events.append(("-singleturn", f"{atk_addr} (Protect)"))
                events.append(
                    (
                        "-hint",
                        f"Protect succeeded (~{100 * p_succ:.4g}% roll · prior streak {streak}). Slot HP unchanged.",
                    )
                )
            else:
                state.protect_prior_successes[prot_k] = 0

                events.append(("-hint", f"Protect failed (~{100 * (1 - p_succ):.4g}% fail · streak was {streak})."))

            set_choice_lock(atk_mon, move_slot)

            continue

        state.protect_prior_successes[prot_k] = 0

        if slot_mv == _ELECTRO_SHOT:
            rain = (state.weather or "").lower() == "rain"

            if rain:
                state.electro_shot_charging.pop(prot_k, None)
            elif state.electro_shot_charging.get(prot_k):
                state.electro_shot_charging.pop(prot_k, None)
            else:
                state.electro_shot_charging[prot_k] = True

                events.append(("move", f"{atk_addr} used {_ELECTRO_SHOT} (charging)!"))
                events.append(("-prepare", f"{atk_addr} harnessed electricity (fires next turn unless Rain)."))

                set_choice_lock(atk_mon, move_slot)

                continue

        if slot_mv in FIELD_STATUS_MOVES:
            events.append(("move", f"{atk_addr} used {slot_mv}."))

            if slot_mv in SIDE_STATUS_MOVES:
                resolve_side_status(
                    slot_mv,
                    atk_addr=atk_addr,
                    state_party_pairs=[(party_a, leads_a), (party_b, leads_b)],
                    events=events,
                )
            elif slot_mv == "Tailwind":
                if atk_side == "alpha":
                    state.alpha_tailwind_turns_left = TAILWIND_DURATION_TURNS
                else:
                    state.beta_tailwind_turns_left = TAILWIND_DURATION_TURNS

                lab = trainer_side_word(atk_side)

                events.append(("-sidestart", f"Tailwind · {lab} side ({TAILWIND_DURATION_TURNS}-tick refresh)"))

            wpair = _WEATHER_SETTING_MOVES.get(slot_mv)

            if wpair:
                state.weather, state.weather_turns_left = wpair

                events.append(("-weather", f"{wpair[0]} · {wpair[1]} turns"))

            events.append(("-hint", f"Field/status move — damage oracle skipped ({slot_mv})."))

            set_choice_lock(atk_mon, move_slot)

            continue

        cat_slot_early = move_category_champions(slot_mv)

        if slot_mv in STATUS_EFFECT_MOVES and cat_slot_early == "Status":
            events.append(("move", f"{atk_addr} used {slot_mv}!"))
            ally_fi = 1 - field_idx
            ally_pi = own_leads[ally_fi]
            ally_mon = own_party[ally_pi]
            ally_addr = None

            if float(ally_mon.get("hpPercentage") or 0) > 0:
                ally_addr = active_address(atk_side, ally_fi, ally_mon)

            dt_raw = item.get("doubles_target")
            dt = DoublesTarget(int(dt_raw)) if dt_raw is not None else None

            if resolve_status_effect(
                slot_mv,
                atk_mon=atk_mon,
                atk_addr=atk_addr,
                ally_mon=ally_mon,
                ally_addr=ally_addr,
                doubles_target=dt,
                events=events,
            ):
                set_choice_lock(atk_mon, move_slot)

                continue

        if cat_slot_early == "Status" and showdown_target_for_move(slot_mv) == "self" and slot_mv not in STATUS_EFFECT_MOVES:
            events.append(("move", f"{atk_addr} used {slot_mv}!"))
            events.append(("-hint", f"Status move ({slot_mv}) — effect stub."))
            set_choice_lock(atk_mon, move_slot)

            continue

        def_party = party_b if atk_side == "alpha" else party_a
        def_leads = leads_b if atk_side == "alpha" else leads_a
        def_side_default = "beta" if atk_side == "alpha" else "alpha"

        foes: list[tuple[int, dict[str, Any]]] = []

        for df_i in range(2):
            dpi = def_leads[df_i]
            dm = def_party[dpi]

            if float(dm.get("hpPercentage") or 0) > 0:
                foes.append((df_i, dm))

        if not foes:
            events.append(("-hint", f"{atk_addr} — no living foe targets; damage skipped."))

            continue

        hit_sequence: list[tuple[str, int, dict[str, Any]]]

        if slot_mv in ALL_ADJACENT_EXCEPT_USER_MOVES:
            hit_sequence = [(def_side_default, df_i, dm) for df_i, dm in foes]
            ally_fi = 1 - field_idx
            ally_pi = own_leads[ally_fi]
            ally_mon = own_party[ally_pi]

            if float(ally_mon.get("hpPercentage") or 0) > 0:
                hit_sequence.append((atk_side, ally_fi, ally_mon))
        elif slot_mv in _SPREAD_BOTH_OPPONENTS_MOVES:
            hit_sequence = [(def_side_default, df_i, dm) for df_i, dm in foes]
        else:
            dt_raw = item.get("doubles_target")

            if dt_raw is None:
                pick_fi, pick_m = rng.choice(foes)

                hit_sequence = [(def_side_default, pick_fi, pick_m)]
            else:
                dt = DoublesTarget(int(dt_raw))

                if dt == DoublesTarget.FOE_SLOT_0:
                    dpi0 = def_leads[0]
                    dm0 = def_party[dpi0]

                    hit_sequence = [(def_side_default, 0, dm0)] if float(dm0.get("hpPercentage") or 0) > 0 else []
                elif dt == DoublesTarget.FOE_SLOT_1:
                    dpi1 = def_leads[1]
                    dm1 = def_party[dpi1]

                    hit_sequence = [(def_side_default, 1, dm1)] if float(dm1.get("hpPercentage") or 0) > 0 else []
                elif dt == DoublesTarget.BOTH_FOES:
                    if slot_mv in _SPREAD_BOTH_OPPONENTS_MOVES:
                        hit_sequence = [(def_side_default, df_i, dm) for df_i, dm in foes]
                    else:
                        pick_fi, pick_m = rng.choice(foes)

                        hit_sequence = [(def_side_default, pick_fi, pick_m)]
                elif dt == DoublesTarget.ALLY_ACTIVE:
                    ally_fi = 1 - field_idx
                    dpi = own_leads[ally_fi]
                    dm = own_party[dpi]

                    hit_sequence = [(atk_side, ally_fi, dm)] if float(dm.get("hpPercentage") or 0) > 0 else []
                elif dt == DoublesTarget.SELF:
                    dpi = own_leads[field_idx]
                    dm = own_party[dpi]

                    hit_sequence = [(atk_side, field_idx, dm)] if float(dm.get("hpPercentage") or 0) > 0 else []
                elif dt == DoublesTarget.ALL_OTHERS:
                    hit_sequence = [(def_side_default, df_i, dm) for df_i, dm in foes]
                    ally_fi = 1 - field_idx
                    ally_pi = own_leads[ally_fi]
                    ally_mon = own_party[ally_pi]

                    if float(ally_mon.get("hpPercentage") or 0) > 0:
                        hit_sequence.append((atk_side, ally_fi, ally_mon))
                else:
                    pick_fi, pick_m = rng.choice(foes)

                    hit_sequence = [(def_side_default, pick_fi, pick_m)]

        if not hit_sequence:
            events.append(("-hint", f"{atk_addr} — no valid damage target; skipped."))

            continue

        cat_slot = move_category_champions(slot_mv)

        if (
            slot_mv not in _SPREAD_BOTH_OPPONENTS_MOVES
            and cat_slot in ("Physical", "Special")
            and len(hit_sequence) == 1
        ):
            dsh, dfi, _dm = hit_sequence[0]

            if dsh == atk_side and dfi == field_idx:
                events.append(("move", f"{atk_addr} used {slot_mv}!"))
                events.append(("-hint", "Invalid target — this damaging move cannot target the user here."))
                set_choice_lock(atk_mon, move_slot)

                continue

        if slot_mv == _SUCKER_PUNCH:

            def _sucker_fail(msg: str) -> None:
                events.append(("move", f"{atk_addr} used {_SUCKER_PUNCH}!"))
                events.append(("-hint", msg))
                set_choice_lock(atk_mon, move_slot)

            if len(hit_sequence) != 1:
                _sucker_fail("Sucker Punch needs exactly one foe target.")

                continue

            d_side, d_fi, _d_mon = hit_sequence[0]

            dkey = (d_side, d_fi)
            decl = declared_move_by_active.get(dkey)
            cat = move_category_champions(decl) if decl else None

            if cat not in ("Physical", "Special"):
                if decl is None:
                    _sucker_fail("It failed — the target is not using a damage move.")
                else:
                    _sucker_fail(f"It failed — the target picked {decl} (not a damage move).")

                continue

        move_connected = False
        any_damage_numbers = False

        for def_side_hit, def_fi, def_mon in hit_sequence:
            if (def_side_hit, def_fi) in protected:
                events.append(("-activate", f"{active_address(def_side_hit, def_fi, def_mon)} Protect"))
                events.append(("-hint", "Damage blocked — target slot was Protecting this turn."))

                continue

            move_connected = True

            dmg_body = {
                "game": game,
                "requests": [{"kind": "single", "field": field, "attacker": atk_payload, "defender": def_mon}],
            }

            dmg_row = client.batch(dmg_body)["results"][0]

            _ensure_batch_ok(dmg_row, "single damage")

            dmg = dmg_row["result"]
            mv = str(dmg.get("moveName") or "")

            lo = float(dmg.get("damagePercentMin") or 0)
            hi = float(dmg.get("damagePercentMax") or 0)
            avg = (lo + hi) / 2

            prev_hp = float(def_mon.get("hpPercentage") or 100)

            def_addr = active_address(def_side_hit, def_fi, def_mon)
            avg = apply_damage_through_substitute(def_mon, avg, events, def_addr)
            new_hp_raw = max(0.0, prev_hp - avg)

            full_hp = prev_hp >= 100.0 - 1e-9
            sash_eligible = _item_key(def_mon) in _FOCUS_SASH_ITEM_NAMES and not bool(def_mon.get("focus_sash_consumed")) and full_hp

            if new_hp_raw <= 0 and sash_eligible:
                def_mon["hpPercentage"] = _FOCUS_SASH_SURVIVAL_HP_PCT
                def_mon["focus_sash_consumed"] = True

                new_hp = _FOCUS_SASH_SURVIVAL_HP_PCT

                events.append(("-activate", f"{def_addr} Focus Sash"))
                events.append(
                    (
                        "-hint",
                        f"{def_addr} endured with Focus Sash (OHKO blocked · HP floor {_FOCUS_SASH_SURVIVAL_HP_PCT}% ).",
                    )
                )
            else:
                def_mon["hpPercentage"] = new_hp_raw

                new_hp = new_hp_raw

            events.append(("move", f"{atk_addr} used {mv} → {def_addr}."))

            if lo > 0 or hi > 0:
                events.append(
                    (
                        "-damage",
                        f"{def_addr} HP {prev_hp:.1f}% → {new_hp:.1f}% (band {lo:.1f}–{hi:.1f}% max HP)",
                    )
                )

            hint_rest = str(dmg.get("koChanceText") or "").strip()

            if hint_rest:
                events.append(("-hint", hint_rest))

            if lo > 0 or hi > 0:
                any_damage_numbers = True

            maybe_weakness_policy(def_mon, slot_mv, events, def_addr)
            maybe_trigger_heal_berries(def_mon, prev_hp, float(def_mon.get("hpPercentage") or new_hp), events, def_addr)
            rocky_helmet_if(def_mon, atk_mon, slot_mv, events, def_addr=def_addr, atk_addr=atk_addr)
            stamina_if_damaging_hit(def_mon, events, def_addr, dealt_damage_numbers=lo > 0 or hi > 0)
            rough_skin_if(def_mon, atk_mon, slot_mv, events, def_addr=def_addr, atk_addr=atk_addr)

            if reward_shaping:
                dealt = max(0.0, prev_hp - new_hp)

                if atk_side == "alpha":
                    debug["alpha_damage_dealt"] += dealt

                    if def_side_hit == "alpha":
                        debug["alpha_damage_taken"] += dealt
                    else:
                        debug["beta_damage_taken"] += dealt
                else:
                    debug["beta_damage_dealt"] += dealt

                    if def_side_hit == "beta":
                        debug["beta_damage_taken"] += dealt
                    else:
                        debug["alpha_damage_taken"] += dealt

            if slot_mv in _SPREAD_BOTH_OPPONENTS_MOVES:
                drops = _SPREAD_FOE_STAT_DROPS.get(slot_mv)

                if drops:
                    for stat_name, delta in drops.items():
                        chg = apply_boost_delta(def_mon, stat_name, delta)

                        if chg != 0:
                            events.append(("-unboost", f"{def_addr} {stat_name} {chg:+d}"))

                        defiant_boost_after_opponent_unboost(def_mon, events, def_addr, had_negative_stage_change=chg < 0)

                    try_white_herb_clear(def_mon, events, def_addr)

        drop_self = _SELF_STAT_DROP_AFTER_HIT.get(slot_mv)

        if drop_self and move_connected:
            for stat_name, delta in drop_self.items():
                chg = apply_boost_delta(atk_mon, stat_name, delta)

                if chg != 0:
                    events.append(("-unboost", f"{atk_addr} {stat_name} {chg:+d}"))

            try_white_herb_clear(atk_mon, events, atk_addr)

        life_orb_recoil_if(atk_mon, dealt_damage=any_damage_numbers, events=events, atk_addr=atk_addr)

        set_choice_lock(atk_mon, move_slot)

    if state.alpha_tailwind_turns_left > 0:
        state.alpha_tailwind_turns_left -= 1

    if state.beta_tailwind_turns_left > 0:
        state.beta_tailwind_turns_left -= 1

    if state.weather_turns_left > 0:
        state.weather_turns_left -= 1

        if state.weather_turns_left <= 0:
            state.weather = None

            events.append(("-weather", "weather ended"))

    for side, party, leads in (("alpha", state.party_a, state.leads_a), ("beta", state.party_b, state.leads_b)):
        for fi in range(2):
            pi = leads[fi]
            mon = party[pi]

            if float(mon.get("hpPercentage") or 0) <= 0:
                continue

            addr = active_address(side, fi, mon)
            leftovers_heal(mon, events, addr)
            black_sludge_tick(mon, events, addr)
            maybe_lum_berry(mon, events, addr)

    reward = 0.0
    terminated = False

    alpha_dead = side_party_wiped_brought(state, alpha=True)
    beta_dead = side_party_wiped_brought(state, alpha=False)

    if alpha_dead and beta_dead:
        terminated = True
        reward = 0.0
    elif beta_dead:
        terminated = True
        reward = 1.0
    elif alpha_dead:
        terminated = True
        reward = -1.0

    if reward_shaping and not terminated:
        reward = (debug["alpha_damage_dealt"] - debug["alpha_damage_taken"]) / 100.0

    return reward, terminated, events, debug


def resolve_turn(
    state: DoublesBattleState,
    rng: random.Random,
    client: OracleClient,
    game: str,
    planned_alpha: tuple[dict[str, Any], dict[str, Any]],
    planned_beta: tuple[dict[str, Any], dict[str, Any]],
    *,
    mega_alpha: int = 0,
    mega_beta: int = 0,
    tera_alpha: int = 0,
    tera_beta: int = 0,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
    reward_shaping: bool = False,
) -> tuple[float, bool, list[tuple[str, str]], dict[str, Any]]:
    planned = merge_planned_turn(planned_alpha, planned_beta)

    return resolve_turn_flat(
        state,
        rng,
        client,
        game,
        planned,
        mega_alpha=mega_alpha,
        mega_beta=mega_beta,
        tera_alpha=tera_alpha,
        tera_beta=tera_beta,
        allow_mega_evolution=allow_mega_evolution,
        allow_terastal=allow_terastal,
        reward_shaping=reward_shaping,
    )
