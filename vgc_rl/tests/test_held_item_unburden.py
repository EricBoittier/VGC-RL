from vgc_rl.held_item_effects import try_white_herb_clear


def test_unburden_triggers_when_white_herb_clears_negative_boosts() -> None:
    mon: dict = {
        "name": "Sneasler",
        "ability": "Unburden",
        "item": "White Herb",
        "boosts": {"atk": 0, "def": -1, "spa": 0, "spd": 0, "spe": 0},
        "moves": [{"name": "Close Combat"}, {"name": "Protect"}, {"name": "Fake Out"}, {"name": "Detect"}],
        "activeMovePosition": 1,
        "hpPercentage": 100.0,
    }
    events: list[tuple[str, str]] = []

    try_white_herb_clear(mon, events, "Beta[A] Sneasler")

    assert mon.get("abilityOn") is True
    assert mon.get("item") == ""
