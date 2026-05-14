from __future__ import annotations

from typing import Any

from vgc_rl.champions_metadata import move_contact_champions, move_meta_champions, species_types_champions, type_effectiveness_dual
from vgc_rl.held_item_rules import (
    BLACK_SLUDGE_KEY,
    LEFTOVERS_KEY,
    LIFE_ORB_KEY,
    LUM_BERRY_KEY,
    PINCH_HEAL_BERRIES,
    ROCKY_HELMET_KEY,
    SITRUS_HEAL_PCT,
    SITRUS_ITEM_KEYS,
    SITRUS_TRIGGER_MAX_HP,
    WEAKNESS_POLICY_KEY,
    WHITE_HERB_KEY,
    normalize_item_key,
)

_BOOST_KEYS = ("atk", "def", "spa", "spd", "spe")


def _normalize_boosts(mon: dict[str, Any]) -> None:
    raw = mon.get("boosts")

    if not isinstance(raw, dict):
        mon["boosts"] = {k: 0 for k in _BOOST_KEYS}

        return

    for k in _BOOST_KEYS:
        raw.setdefault(k, 0)


def _apply_boost(mon: dict[str, Any], stat: str, delta: int) -> None:
    _normalize_boosts(mon)
    cur = int(mon["boosts"][stat])
    new = max(-6, min(6, cur + delta))

    mon["boosts"][stat] = new


def _def_types(mon: dict[str, Any]) -> list[str]:
    raw = mon.get("types")

    if isinstance(raw, list) and raw:
        return [str(x) for x in raw]

    nm = str(mon.get("name") or "").strip()
    st = species_types_champions(nm)

    if st:
        return st

    return []


def try_white_herb_clear(mon: dict[str, Any], events: list[tuple[str, str]], addr: str) -> None:
    if normalize_item_key(mon.get("item")) != WHITE_HERB_KEY:
        return

    if mon.get("white_herb_consumed"):
        return

    _normalize_boosts(mon)

    if not any(int(mon["boosts"][k]) < 0 for k in _BOOST_KEYS):
        return

    for k in _BOOST_KEYS:
        v = int(mon["boosts"][k])

        if v < 0:
            mon["boosts"][k] = 0

    mon["white_herb_consumed"] = True
    events.append(("-activate", f"{addr} White Herb"))


def maybe_trigger_heal_berries(mon: dict[str, Any], prev_hp: float, new_hp: float, events: list[tuple[str, str]], addr: str) -> float:
    hp = float(new_hp)
    ik = normalize_item_key(mon.get("item"))

    if ik in SITRUS_ITEM_KEYS and not mon.get("sitrus_berry_consumed"):
        if prev_hp > float(SITRUS_TRIGGER_MAX_HP) + 1e-9 and hp <= float(SITRUS_TRIGGER_MAX_HP) + 1e-9:
            heal = float(SITRUS_HEAL_PCT)
            hp = min(100.0, hp + heal)
            mon["hpPercentage"] = hp
            mon["sitrus_berry_consumed"] = True
            mon["item"] = ""
            events.append(("-activate", f"{addr} Sitrus Berry"))

            return hp

    pinch = PINCH_HEAL_BERRIES.get(ik)

    if pinch and not mon.get("pinch_berry_consumed"):
        thr, heal_pct = pinch

        if hp <= float(thr) + 1e-9:
            hp = min(100.0, hp + float(heal_pct))
            mon["hpPercentage"] = hp
            mon["pinch_berry_consumed"] = True
            mon["item"] = ""
            events.append(("-activate", f"{addr} pinch berry"))

            return hp

    return hp


def maybe_weakness_policy(
    def_mon: dict[str, Any],
    move_name: str,
    events: list[tuple[str, str]],
    addr: str,
) -> None:
    if normalize_item_key(def_mon.get("item")) != WEAKNESS_POLICY_KEY:
        return

    if def_mon.get("weakness_policy_consumed"):
        return

    meta = move_meta_champions(move_name)

    if not meta:
        return

    atk_t = str(meta.get("type") or "")

    if not atk_t:
        return

    defs = _def_types(def_mon)

    if not defs:
        return

    mult = type_effectiveness_dual(atk_t, defs)

    if mult < 2.0 - 1e-9:
        return

    _apply_boost(def_mon, "atk", 2)
    _apply_boost(def_mon, "spa", 2)
    def_mon["weakness_policy_consumed"] = True
    def_mon["item"] = ""
    events.append(("-activate", f"{addr} Weakness Policy"))


def maybe_lum_berry(mon: dict[str, Any], events: list[tuple[str, str]], addr: str) -> None:
    if normalize_item_key(mon.get("item")) != LUM_BERRY_KEY:
        return

    if mon.get("lum_berry_consumed"):
        return

    st = str(mon.get("status") or "").strip()

    if not st:
        return

    mon["status"] = ""
    mon["lum_berry_consumed"] = True
    mon["item"] = ""
    events.append(("-activate", f"{addr} Lum Berry"))


def leftovers_heal(mon: dict[str, Any], events: list[tuple[str, str]], addr: str) -> None:
    if normalize_item_key(mon.get("item")) != LEFTOVERS_KEY:
        return

    if float(mon.get("hpPercentage") or 0) <= 0:
        return

    if float(mon.get("hpPercentage") or 0) >= 100.0 - 1e-9:
        return

    hp = min(100.0, float(mon.get("hpPercentage") or 0) + 100.0 / 16.0)
    mon["hpPercentage"] = hp
    events.append(("-heal", f"{addr} Leftovers"))


def black_sludge_tick(mon: dict[str, Any], events: list[tuple[str, str]], addr: str) -> None:
    if normalize_item_key(mon.get("item")) != BLACK_SLUDGE_KEY:
        return

    if float(mon.get("hpPercentage") or 0) <= 0:
        return

    defs = _def_types(mon)
    poison = "Poison" in defs

    if poison:
        hp = min(100.0, float(mon.get("hpPercentage") or 0) + 100.0 / 16.0)
        mon["hpPercentage"] = hp
        events.append(("-heal", f"{addr} Black Sludge"))

        return

    hp = max(0.0, float(mon.get("hpPercentage") or 0) - 100.0 / 8.0)
    mon["hpPercentage"] = hp
    events.append(("-damage", f"{addr} Black Sludge"))


def life_orb_recoil_if(
    atk_mon: dict[str, Any],
    *,
    dealt_damage: bool,
    events: list[tuple[str, str]],
    atk_addr: str,
) -> None:
    if not dealt_damage:
        return

    if normalize_item_key(atk_mon.get("item")) != LIFE_ORB_KEY:
        return

    if float(atk_mon.get("hpPercentage") or 0) <= 0:
        return

    hp = max(0.0, float(atk_mon.get("hpPercentage") or 0) - 10.0)
    atk_mon["hpPercentage"] = hp
    events.append(("-damage", f"{atk_addr} Life Orb"))


def rocky_helmet_if(
    def_mon: dict[str, Any],
    atk_mon: dict[str, Any],
    move_name: str,
    events: list[tuple[str, str]],
    *,
    def_addr: str,
    atk_addr: str,
) -> None:
    if normalize_item_key(def_mon.get("item")) != ROCKY_HELMET_KEY:
        return

    if float(def_mon.get("hpPercentage") or 0) <= 0:
        return

    if not move_contact_champions(move_name):
        return

    if float(atk_mon.get("hpPercentage") or 0) <= 0:
        return

    hp = max(0.0, float(atk_mon.get("hpPercentage") or 0) - 100.0 / 6.0)
    atk_mon["hpPercentage"] = hp
    events.append(("-damage", f"{atk_addr} Rocky Helmet"))
