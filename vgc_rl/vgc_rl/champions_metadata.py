from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

_JSON = "vgc_rl"


@lru_cache(maxsize=1)
def _move_meta_raw() -> dict[str, dict[str, Any]]:
    raw = resources.files(_JSON).joinpath("examples/move_meta_champions.json").read_text(encoding="utf-8")

    return json.loads(raw)


@lru_cache(maxsize=1)
def _type_chart_raw() -> dict[str, dict[str, float]]:
    raw = resources.files(_JSON).joinpath("examples/type_chart_champions.json").read_text(encoding="utf-8")

    return json.loads(raw)


@lru_cache(maxsize=1)
def _species_types_raw() -> dict[str, list[str]]:
    raw = resources.files(_JSON).joinpath("examples/species_types_champions.json").read_text(encoding="utf-8")

    return json.loads(raw)


def move_meta_champions(move_name: str) -> dict[str, Any] | None:
    return _move_meta_raw().get(move_name)


def move_category_champions(move_name: str) -> str | None:
    row = move_meta_champions(move_name)

    if not row:
        return None

    return str(row.get("category") or "")


def move_contact_champions(move_name: str) -> bool:
    row = move_meta_champions(move_name)

    if not row:
        return False

    return bool(row.get("contact"))


def type_effectiveness_single(attack_type: str, defend_type: str) -> float:
    chart = _type_chart_raw()

    return float(chart.get(attack_type, {}).get(defend_type, 1.0))


def type_effectiveness_dual(attack_type: str, defend_types: list[str]) -> float:
    if not defend_types:
        return 1.0

    m = 1.0

    for dt in defend_types:
        m *= type_effectiveness_single(attack_type, dt)

    return m


def species_types_champions(species_name: str) -> list[str] | None:
    row = _species_types_raw().get(species_name)

    if row:
        return list(row)

    return None
