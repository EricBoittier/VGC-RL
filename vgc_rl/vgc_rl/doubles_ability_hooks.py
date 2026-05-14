from __future__ import annotations

from typing import Any

from vgc_rl.champions_metadata import move_contact_champions


def defiant_boost_after_opponent_unboost(mon: dict[str, Any], events: list[tuple[str, str]], addr: str, *, had_negative_stage_change: bool) -> None:
    if not had_negative_stage_change:
        return

    if str(mon.get("ability") or "").strip() != "Defiant":
        return

    from vgc_rl.doubles_turn_engine import apply_boost_delta

    chg = apply_boost_delta(mon, "atk", 2)

    if chg == 0:
        return

    events.append(("-ability", f"{addr} Defiant"))
    events.append(("-boost", f"{addr} atk {chg:+d}"))


def stamina_if_damaging_hit(def_mon: dict[str, Any], events: list[tuple[str, str]], def_addr: str, *, dealt_damage_numbers: bool) -> None:
    if not dealt_damage_numbers:
        return

    if str(def_mon.get("ability") or "").strip() != "Stamina":
        return

    if float(def_mon.get("hpPercentage") or 0) <= 0:
        return

    from vgc_rl.doubles_turn_engine import apply_boost_delta

    chg = apply_boost_delta(def_mon, "def", 1)

    if chg == 0:
        return

    events.append(("-ability", f"{def_addr} Stamina"))
    events.append(("-boost", f"{def_addr} def {chg:+d}"))


def rough_skin_if(
    def_mon: dict[str, Any],
    atk_mon: dict[str, Any],
    move_name: str,
    events: list[tuple[str, str]],
    *,
    def_addr: str,
    atk_addr: str,
) -> None:
    if str(def_mon.get("ability") or "").strip() != "Rough Skin":
        return

    if float(def_mon.get("hpPercentage") or 0) <= 0:
        return

    if not move_contact_champions(move_name):
        return

    if float(atk_mon.get("hpPercentage") or 0) <= 0:
        return

    chip = 100.0 / 8.0
    hp = max(0.0, float(atk_mon.get("hpPercentage") or 0) - chip)
    atk_mon["hpPercentage"] = hp
    events.append(("-ability", f"{def_addr} Rough Skin"))
    events.append(("-damage", f"{atk_addr} Rough Skin ({chip:.1f}%)"))
