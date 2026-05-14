from __future__ import annotations

from typing import Any

from vgc_rl.held_item_rules import normalize_item_key

_MEGA_ITEM_TO_FORM: dict[str, tuple[str, str]] = {
    "charizardite y": ("Charizard-Mega-Y", "Drought"),
    "charizardite x": ("Charizard-Mega-X", "Tough Claws"),
    "gardevoirite": ("Gardevoir-Mega", "Pixilate"),
    "venusaurite": ("Venusaur-Mega", "Thick Fat"),
}


def mega_lookup_transform(mon: dict[str, Any]) -> tuple[str, str] | None:
    key = normalize_item_key(mon.get("item"))

    return _MEGA_ITEM_TO_FORM.get(key)


def can_mega_evolve_species(mon: dict[str, Any], *, game: str) -> bool:
    if game != "champions":
        return False

    base = str(mon.get("name") or "")

    if "-Mega" in base:
        return False

    return mega_lookup_transform(mon) is not None


def apply_mega_evolution(mon: dict[str, Any]) -> bool:
    pair = mega_lookup_transform(mon)

    if not pair:
        return False

    mega_name, ability = pair

    mon["name"] = mega_name
    mon["ability"] = ability
    mon["abilityOn"] = False

    return True


def can_terastal(mon: dict[str, Any], *, game: str) -> bool:
    if game != "sv":
        return False

    if bool(mon.get("teraTypeActive")):
        return False

    return bool(str(mon.get("teraType") or "").strip())


def apply_terastal(mon: dict[str, Any]) -> bool:
    if not str(mon.get("teraType") or "").strip():
        return False

    mon["teraTypeActive"] = True

    return True
