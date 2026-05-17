from __future__ import annotations

from typing import Any

from vgc_rl.doubles_actions import DoublesTarget

_BOOST_KEYS = ("atk", "def", "spa", "spd", "spe")

STATUS_SELF_BOOSTS: dict[str, dict[str, int]] = {
    "Swords Dance": {"atk": 2},
    "Dragon Dance": {"atk": 1, "spe": 1},
    "Bulk Up": {"atk": 1, "def": 1},
    "Calm Mind": {"spa": 1, "spd": 1},
    "Coil": {"atk": 1, "def": 1},
    "Iron Defense": {"def": 2},
    "Shell Smash": {"atk": 2, "spa": 2, "spe": 2, "def": -1, "spd": -1},
    "Clangorous Soul": {"atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1},
    "Nasty Plot": {"spa": 2},
    "Agility": {"spe": 2},
    "Rock Polish": {"spe": 2},
    "Amnesia": {"spd": 2},
    "Acid Armor": {"def": 2},
}

STATUS_ALLY_BOOSTS: dict[str, dict[str, int]] = {
    "Coaching": {"def": 1, "spd": 1},
}

STATUS_SELF_HEAL_PCT: dict[str, float] = {
    "Recover": 50.0,
    "Roost": 50.0,
    "Synthesis": 50.0,
    "Moonlight": 50.0,
    "Morning Sun": 50.0,
    "Slack Off": 50.0,
    "Soft-Boiled": 50.0,
}

STATUS_SIDE_HEAL_ON_SELF_MOVES = frozenset({"Life Dew"})

LIFE_DEW_HEAL_PCT = 25.0

SUBSTITUTE_MOVES = frozenset({"Substitute"})

SUBSTITUTE_COST_PCT = 25.0

SUBSTITUTE_HP_PCT = 25.0

SIDE_STATUS_MOVES = frozenset({"Wide Guard", "Perish Song"})

PERISH_SONG_TURNS = 3

STATUS_EFFECT_MOVES = (
    frozenset(STATUS_SELF_BOOSTS)
    | frozenset(STATUS_ALLY_BOOSTS)
    | frozenset(STATUS_SELF_HEAL_PCT)
    | STATUS_SIDE_HEAL_ON_SELF_MOVES
    | SUBSTITUTE_MOVES
)


def _normalize_boosts(mon: dict[str, Any]) -> None:
    raw = mon.get("boosts")

    if not isinstance(raw, dict):
        mon["boosts"] = {k: 0 for k in _BOOST_KEYS}

        return

    for k in _BOOST_KEYS:
        if k not in raw:
            raw[k] = 0


def _apply_boost_delta(mon: dict[str, Any], stat: str, delta: int) -> int:
    _normalize_boosts(mon)
    cur = int(mon["boosts"][stat])
    new = max(-6, min(6, cur + delta))
    mon["boosts"][stat] = new

    return new - cur


def _heal_mon(mon: dict[str, Any], pct: float, events: list[tuple[str, str]], addr: str, label: str) -> None:
    hp = float(mon.get("hpPercentage") or 0)

    if hp <= 0:
        return

    new_hp = min(100.0, hp + pct)
    mon["hpPercentage"] = new_hp
    events.append(("-heal", f"{addr} {label} HP {hp:.1f}% → {new_hp:.1f}%"))


def _apply_boosts(mon: dict[str, Any], deltas: dict[str, int], events: list[tuple[str, str]], addr: str) -> None:
    for stat_name, delta in deltas.items():
        chg = _apply_boost_delta(mon, stat_name, delta)

        if chg > 0:
            events.append(("-boost", f"{addr} {stat_name} {chg:+d}"))
        elif chg < 0:
            events.append(("-unboost", f"{addr} {stat_name} {chg:+d}"))


def resolve_status_effect(
    move_name: str,
    *,
    atk_mon: dict[str, Any],
    atk_addr: str,
    ally_mon: dict[str, Any] | None,
    ally_addr: str | None,
    doubles_target: DoublesTarget | None,
    events: list[tuple[str, str]],
) -> bool:
    if move_name in STATUS_SELF_BOOSTS:
        _apply_boosts(atk_mon, STATUS_SELF_BOOSTS[move_name], events, atk_addr)

        return True

    if move_name in STATUS_SELF_HEAL_PCT:
        pct = STATUS_SELF_HEAL_PCT[move_name]
        _heal_mon(atk_mon, pct, events, atk_addr, move_name)

        return True

    if move_name in STATUS_SIDE_HEAL_ON_SELF_MOVES:
        _heal_mon(atk_mon, LIFE_DEW_HEAL_PCT, events, atk_addr, move_name)

        if ally_mon is not None and ally_addr is not None and float(ally_mon.get("hpPercentage") or 0) > 0:
            _heal_mon(ally_mon, LIFE_DEW_HEAL_PCT, events, ally_addr, move_name)

        return True

    if move_name in SUBSTITUTE_MOVES:
        hp = float(atk_mon.get("hpPercentage") or 0)

        if hp <= 0:
            return True

        cost = SUBSTITUTE_COST_PCT
        new_hp = max(0.0, hp - cost)
        atk_mon["hpPercentage"] = new_hp
        atk_mon["substitute_hp_pct"] = SUBSTITUTE_HP_PCT
        events.append(("-damage", f"{atk_addr} HP {hp:.1f}% → {new_hp:.1f}% (Substitute cost)"))
        events.append(("-start", f"{atk_addr} Substitute"))

        return True

    if move_name in STATUS_ALLY_BOOSTS:
        if ally_mon is None or ally_addr is None or float(ally_mon.get("hpPercentage") or 0) <= 0:
            events.append(("-hint", f"{move_name} failed — no living ally."))

            return True

        _apply_boosts(ally_mon, STATUS_ALLY_BOOSTS[move_name], events, ally_addr)

        return True

    return False


def apply_damage_through_substitute(
    def_mon: dict[str, Any],
    damage: float,
    events: list[tuple[str, str]],
    def_addr: str,
) -> float:
    sub_hp = float(def_mon.get("substitute_hp_pct") or 0)

    if sub_hp <= 0:
        return damage

    if damage <= 0:
        return 0.0

    absorbed = min(sub_hp, damage)
    sub_hp -= absorbed
    remaining = damage - absorbed

    if sub_hp <= 1e-9:
        def_mon.pop("substitute_hp_pct", None)
        events.append(("-end", f"{def_addr} Substitute"))
    else:
        def_mon["substitute_hp_pct"] = sub_hp
        events.append(("-activate", f"{def_addr} Substitute"))

    return remaining


def resolve_side_status(
    move_name: str,
    *,
    atk_addr: str,
    state_party_pairs: list[tuple[list[dict[str, Any]], list[int]]],
    events: list[tuple[str, str]],
) -> bool:
    if move_name == "Wide Guard":
        events.append(("-sidestart", f"Wide Guard · {atk_addr} side (spread block stub)"))

        return True

    if move_name == "Perish Song":
        for party, leads in state_party_pairs:
            for fi in range(2):
                pi = leads[fi]
                mon = party[pi]

                if float(mon.get("hpPercentage") or 0) <= 0:
                    continue

                mon["perish_song_turns"] = PERISH_SONG_TURNS

        events.append(("-fieldstart", "Perish Song · all actives (3-turn stub)"))

        return True

    return False
