from __future__ import annotations

import json
from typing import Any

from vgc_rl.doubles_mega_tera import _MEGA_ITEM_TO_FORM
from vgc_rl.doubles_protect_moves import PROTECT_FAMILY_MOVES
from vgc_rl.doubles_move_targeting import ALL_ADJACENT_EXCEPT_USER_MOVES, FIELD_STATUS_MOVES, SPREAD_BOTH_OPPONENTS_MOVES
from vgc_rl.doubles_status_effects import SIDE_STATUS_MOVES, STATUS_EFFECT_MOVES
from vgc_rl.doubles_turn_engine import (
    TAILWIND_DURATION_TURNS,
    _ENTRY_WEATHER_ABILITIES,
    _FOCUS_SASH_ITEM_NAMES,
    _SELF_STAT_DROP_AFTER_HIT,
    _SPREAD_FOE_STAT_DROPS,
    _WEATHER_SETTING_MOVES,
)
from vgc_rl.example_teams import load_example_teams
from vgc_rl.held_item_rules import ITEM_DEFERRALS
from vgc_rl.turn_sim import STATUS_NO_CALC


def python_mechanics_string_inventory() -> dict[str, Any]:
    return {
        "protect_family_moves": sorted(PROTECT_FAMILY_MOVES),
        "spread_both_opponents_moves": sorted(SPREAD_BOTH_OPPONENTS_MOVES),
        "all_adjacent_except_user_moves": sorted(ALL_ADJACENT_EXCEPT_USER_MOVES),
        "spread_foe_stat_drops": {k: dict(v) for k, v in sorted(_SPREAD_FOE_STAT_DROPS.items())},
        "self_stat_drop_after_hit": {k: dict(v) for k, v in sorted(_SELF_STAT_DROP_AFTER_HIT.items())},
        "weather_setting_moves": {k: list(v) for k, v in sorted(_WEATHER_SETTING_MOVES.items())},
        "entry_weather_abilities": {k: list(v) for k, v in sorted(_ENTRY_WEATHER_ABILITIES.items())},
        "focus_sash_item_keys": sorted(_FOCUS_SASH_ITEM_NAMES),
        "tailwind_duration_turns": TAILWIND_DURATION_TURNS,
        "status_no_calc_moves": sorted(STATUS_NO_CALC),
        "field_status_moves": sorted(FIELD_STATUS_MOVES),
        "side_status_moves": sorted(SIDE_STATUS_MOVES),
        "status_effect_moves": sorted(STATUS_EFFECT_MOVES),
        "mega_item_to_form_keys": sorted(_MEGA_ITEM_TO_FORM.keys()),
        "item_deferrals": [{"name": r["name"], "disposition": r["disposition"]} for r in ITEM_DEFERRALS],
        "hardcoded_engine_strings": sorted(
            {
                "Defiant",
                "Electro Shot",
                "Intimidate",
                "Rough Skin",
                "Stamina",
                "Tailwind",
                "Unburden",
            }
        ),
    }


def example_teams_string_inventory() -> dict[str, Any]:
    data = load_example_teams()
    species: set[str] = set()
    moves: set[str] = set()
    items: set[str] = set()
    abilities: set[str] = set()
    game = ""

    if isinstance(data.get("meta"), dict):
        game = str(data["meta"].get("game") or "")

    for key, blob in sorted(data.items()):
        if key == "meta" or not isinstance(blob, dict):
            continue

        party = blob.get("party")

        if not isinstance(party, list):
            continue

        for mon in party:
            if not isinstance(mon, dict):
                continue

            nm = str(mon.get("name") or "").strip()

            if nm:
                species.add(nm)

            it = str(mon.get("item") or "").strip()

            if it:
                items.add(it)

            ab = str(mon.get("ability") or "").strip()

            if ab:
                abilities.add(ab)

            for slot in mon.get("moves") or []:
                if isinstance(slot, dict):
                    mv = str(slot.get("name") or "").strip()

                    if mv:
                        moves.add(mv)

    return {
        "game": game,
        "species": sorted(species),
        "moves": sorted(moves),
        "items": sorted(items),
        "abilities": sorted(abilities),
    }


def full_mechanics_inventory() -> dict[str, Any]:
    return {
        "python_mechanics": python_mechanics_string_inventory(),
        "example_teams": example_teams_string_inventory(),
    }


def main() -> None:
    print(json.dumps(full_mechanics_inventory(), indent=2))


if __name__ == "__main__":
    main()
