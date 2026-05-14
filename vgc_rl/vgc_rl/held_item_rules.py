from __future__ import annotations

from typing import Any, Literal

from vgc_rl.champions_metadata import move_category_champions

RestrictionKind = Literal["none", "choice", "assault_vest"]

ITEM_DEFERRALS: tuple[dict[str, str], ...] = (
    {"name": "Eject Button", "disposition": "deferred", "reason": "switch timing and targeting"},
    {"name": "Red Card", "disposition": "deferred", "reason": "forced switch resolution"},
    {"name": "Throat Spray", "disposition": "deferred", "reason": "sound move hook"},
    {"name": "Room Service", "disposition": "deferred", "reason": "Trick Room field hook"},
    {"name": "Mirror Herb", "disposition": "deferred", "reason": "copy positive boosts"},
    {"name": "Covert Cloak", "disposition": "oracle_only", "reason": "secondary suppression in damage calc"},
    {"name": "Safety Goggles", "disposition": "deferred", "reason": "powder and weather damage immunity"},
    {"name": "Utility Umbrella", "disposition": "oracle_only", "reason": "weather damage modifiers"},
    {"name": "Punching Glove", "disposition": "oracle_only", "reason": "punch move power and contact"},
    {"name": "Loaded Dice", "disposition": "oracle_only", "reason": "multi-hit odds"},
    {"name": "Clear Amulet", "disposition": "deferred", "reason": "blocks opponent stat drops e.g. Intimidate"},
    {"name": "Big Root", "disposition": "oracle_only", "reason": "drain heal percent"},
    {"name": "Shell Bell", "disposition": "oracle_only", "reason": "drain heal percent"},
    {"name": "Air Balloon", "disposition": "deferred", "reason": "Ground immunity until pop"},
    {"name": "Heavy-Duty Boots", "disposition": "deferred", "reason": "hazard damage not modeled"},
    {"name": "Binding Band", "disposition": "deferred", "reason": "partial trap damage"},
    {"name": "Metronome", "disposition": "deferred", "reason": "consecutive same-move stacking"},
    {"name": "Expert Belt", "disposition": "oracle_only", "reason": "super-effective damage"},
    {"name": "Light Clay", "disposition": "deferred", "reason": "screen duration"},
    {"name": "Mental Herb", "disposition": "deferred", "reason": "Taunt Encore Attract"},
    {"name": "White Herb", "disposition": "engine", "reason": "implemented via held_item_effects"},
    {"name": "Power Herb", "disposition": "deferred", "reason": "two-turn charge skip"},
    {"name": "Focus Band", "disposition": "deferred", "reason": "probabilistic survival"},
)


def normalize_item_key(item: Any) -> str:
    return str(item or "").strip().lower()


def item_restriction_kind(mon: dict[str, Any]) -> RestrictionKind:
    k = normalize_item_key(mon.get("item"))

    if k in ("choice band", "choice specs", "choice scarf"):
        return "choice"

    if k == "assault vest":
        return "assault_vest"

    return "none"


def gorilla_tactics_choice_like(mon: dict[str, Any]) -> bool:
    return str(mon.get("ability") or "").strip() == "Gorilla Tactics"


def choice_like_move_lock(mon: dict[str, Any]) -> bool:
    return item_restriction_kind(mon) == "choice" or gorilla_tactics_choice_like(mon)


def move_slot_illegal_assault_vest(mon: dict[str, Any], move_slot: int, *, game: str) -> bool:
    if game != "champions":
        return False

    if item_restriction_kind(mon) != "assault_vest":
        return False

    moves = mon.get("moves")

    if not isinstance(moves, list) or not (1 <= move_slot <= len(moves)):
        return True

    slot = moves[move_slot - 1]

    if not isinstance(slot, dict):
        return True

    name = str(slot.get("name") or "").strip()
    cat = move_category_champions(name)

    return cat == "Status"


def move_slot_illegal_choice_lock(mon: dict[str, Any], move_slot: int) -> bool:
    if not choice_like_move_lock(mon):
        return False

    locked = mon.get("choice_locked_move_slot")

    if locked is None:
        return False

    return int(locked) != int(move_slot)


def clear_choice_lock(mon: dict[str, Any]) -> None:
    mon.pop("choice_locked_move_slot", None)


def set_choice_lock(mon: dict[str, Any], move_slot: int) -> None:
    if choice_like_move_lock(mon):
        mon["choice_locked_move_slot"] = int(move_slot)


SITRUS_ITEM_KEYS = frozenset({"sitrus berry"})
PINCH_HEAL_BERRIES: dict[str, tuple[int, int]] = {
    "wiki berry": (25, 33),
    "mago berry": (25, 33),
    "figy berry": (25, 33),
    "aguav berry": (25, 33),
    "iapapa berry": (25, 33),
}
WEAKNESS_POLICY_KEY = "weakness policy"
WHITE_HERB_KEY = "white herb"
LEFTOVERS_KEY = "leftovers"
BLACK_SLUDGE_KEY = "black sludge"
LIFE_ORB_KEY = "life orb"
ROCKY_HELMET_KEY = "rocky helmet"
LUM_BERRY_KEY = "lum berry"

SITRUS_TRIGGER_MAX_HP = 50
SITRUS_HEAL_PCT = 25
