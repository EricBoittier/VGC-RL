from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from vgc_rl.doubles_mega_tera import apply_mega_evolution, can_mega_evolve_species, mega_lookup_transform
from vgc_rl.held_item_rules import normalize_item_key


def _mega_data() -> dict:
    raw = resources.files("vgc_rl").joinpath("examples/mega_evolution_champions.json").read_text(encoding="utf-8")

    return json.loads(raw)


def test_mega_table_has_sixty_forms() -> None:
    data = _mega_data()

    assert data["megaFormCount"] == 60
    assert data["lookupCount"] == 60


def test_charizard_dual_stones() -> None:
    y = {"name": "Charizard", "item": "Charizardite Y"}
    x = {"name": "Charizard", "item": "Charizardite X"}

    assert mega_lookup_transform(y) == ("Charizard-Mega-Y", "Drought")
    assert mega_lookup_transform(x) == ("Charizard-Mega-X", "Tough Claws")


def test_gengar_mega_apply() -> None:
    mon = {"name": "Gengar", "item": "Gengarite", "ability": "Cursed Body"}

    assert can_mega_evolve_species(mon, game="champions")
    assert apply_mega_evolution(mon)

    assert mon["name"] == "Gengar-Mega"
    assert mon["ability"] == "Shadow Tag"


def test_meowstic_gendered_bases() -> None:
    m = {"name": "Meowstic", "item": "Meowsticite"}
    f = {"name": "Meowstic-F", "item": "Meowsticite"}

    assert mega_lookup_transform(m) == ("Meowstic-M-Mega", "Trace")
    assert mega_lookup_transform(f) == ("Meowstic-F-Mega", "Trace")


def test_floette_mega() -> None:
    mon = {"name": "Floette", "item": "Floettite"}

    assert mega_lookup_transform(mon) == ("Floette-Mega", "Fairy Aura")


def test_meta_team_mega_stones_resolve() -> None:
    meta_dir = Path(__file__).resolve().parent.parent / "vgc_rl" / "examples" / "meta_teams"
    stones: set[str] = set()

    for path in meta_dir.glob("*.json"):
        if path.name == "manifest.json":
            continue

        blob = json.loads(path.read_text(encoding="utf-8"))

        for mon in blob.get("party") or []:
            it = mon.get("item")

            if it and str(it).lower().endswith("ite"):
                stones.add(str(it))

    missing: list[str] = []

    for stone in sorted(stones):
        probe = {"name": "Placeholder", "item": stone}
        key = normalize_item_key(stone)
        data = _mega_data()
        bases = {row["baseSpecies"] for row in data["lookups"] if row["itemKey"] == key}

        if not bases:
            missing.append(stone)

    assert not missing, f"mega stones without lookup: {missing}"


def test_meta_team_species_can_mega_when_stone_equipped() -> None:
    meta_dir = Path(__file__).resolve().parent.parent / "vgc_rl" / "examples" / "meta_teams"
    failures: list[str] = []

    for path in meta_dir.glob("*.json"):
        if path.name == "manifest.json":
            continue

        blob = json.loads(path.read_text(encoding="utf-8"))

        for mon in blob.get("party") or []:
            it = mon.get("item")

            if not it or not str(it).lower().endswith("ite"):
                continue

            name = str(mon.get("name") or "")
            probe = {"name": name, "item": it}

            if not can_mega_evolve_species(probe, game="champions"):
                failures.append(f"{name} @ {it}")

    assert not failures, f"cannot mega: {failures[:10]}"
