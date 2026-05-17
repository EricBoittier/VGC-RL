from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

from vgc_rl.held_item_rules import normalize_item_key

_GENDER_SUFFIX = re.compile(r" \((M|F)\)$")


@lru_cache(maxsize=1)
def _load_mega_table() -> dict[tuple[str, str], tuple[str, str]]:
    raw = resources.files("vgc_rl").joinpath("examples/mega_evolution_champions.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    by_item_base: dict[tuple[str, str], tuple[str, str]] = {}

    for row in data.get("lookups") or []:
        if not isinstance(row, dict):
            continue

        item_key = str(row.get("itemKey") or "")
        base = str(row.get("baseSpecies") or "")
        mega = str(row.get("mega") or "")
        ability = str(row.get("ability") or "")

        if not item_key or not base or not mega:
            continue

        by_item_base[(item_key, base)] = (mega, ability)

    return by_item_base


def _species_lookup_names(name: str) -> list[str]:
    n = str(name or "").strip()

    if not n:
        return []

    out = [n]
    stripped = _GENDER_SUFFIX.sub("", n)

    if stripped != n:
        out.append(stripped)

    if stripped.endswith("-M") or stripped.endswith("-F"):
        out.append(stripped[:-2])

    return out


def mega_lookup_transform(mon: dict[str, Any]) -> tuple[str, str] | None:
    item_key = normalize_item_key(mon.get("item"))

    if not item_key:
        return None

    by_item_base = _load_mega_table()

    for base in _species_lookup_names(str(mon.get("name") or "")):
        hit = by_item_base.get((item_key, base))

        if hit is not None:
            return hit

    return None


_MEGA_ITEM_TO_FORM: dict[str, tuple[str, str]] = {}


def _refresh_legacy_item_map() -> None:
    global _MEGA_ITEM_TO_FORM

    by_item_base = _load_mega_table()
    _MEGA_ITEM_TO_FORM.clear()

    for (item_key, _base), pair in by_item_base.items():
        if item_key not in _MEGA_ITEM_TO_FORM:
            _MEGA_ITEM_TO_FORM[item_key] = pair


_refresh_legacy_item_map()


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
