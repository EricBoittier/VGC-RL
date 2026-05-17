from __future__ import annotations

import random

from vgc_rl.doubles_actions import DoublesTarget
from vgc_rl.doubles_turn_engine import DoublesBattleState, resolve_turn_flat
from vgc_rl.example_teams import party_member
from vgc_rl.fake_oracle_client import FakeOracleClient


def _mv(side: str, field_idx: int, move_slot: int, orig_index: int, *, doubles_target: int | None = None) -> dict:
    row: dict = {"kind": "move", "atk_side": side, "field_idx": field_idx, "move_slot": move_slot, "orig_index": orig_index}

    if doubles_target is not None:
        row["doubles_target"] = doubles_target

    return row


def test_electro_shot_charges_without_rain_then_fires() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[3, 0], leads_b=[0, 1])
    rng = random.Random(42)
    client = FakeOracleClient()

    hp_b_before = sum(float(x.get("hpPercentage") or 0) for x in state.party_b)

    planned = [_mv("alpha", 0, 1, 0), _mv("alpha", 1, 2, 1), _mv("beta", 0, 3, 2), _mv("beta", 1, 1, 3)]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert state.electro_shot_charging.get(("a", 3)) is True

    hp_b_mid = sum(float(x.get("hpPercentage") or 0) for x in state.party_b)

    assert hp_b_mid == hp_b_before

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert state.electro_shot_charging.get(("a", 3)) is None

    hp_b_after = sum(float(x.get("hpPercentage") or 0) for x in state.party_b)

    assert hp_b_after < hp_b_mid


def test_electro_skips_charge_when_rain_active() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(
        party_a=party_a,
        party_b=party_b,
        leads_a=[3, 0],
        leads_b=[2, 3],
        weather="Rain",
        weather_turns_left=5,
    )
    rng = random.Random(1)
    client = FakeOracleClient()

    hp_b_before = sum(float(x.get("hpPercentage") or 0) for x in state.party_b)

    planned = [_mv("alpha", 0, 1, 0), _mv("alpha", 1, 2, 1), _mv("beta", 0, 1, 2), _mv("beta", 1, 4, 3)]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert state.electro_shot_charging.get(("a", 3)) is None

    hp_b_after = sum(float(x.get("hpPercentage") or 0) for x in state.party_b)

    assert hp_b_after < hp_b_before


def test_spread_icy_wind_applies_speed_drop_to_both_foes() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[2, 0], leads_b=[2, 3])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [_mv("alpha", 0, 4, 0), _mv("alpha", 1, 2, 1), _mv("beta", 0, 1, 2), _mv("beta", 1, 4, 3)]

    resolve_turn_flat(state, rng, client, "champions", planned)

    b0 = state.party_b[state.leads_b[0]]
    b1 = state.party_b[state.leads_b[1]]

    assert int(b0.get("boosts", {}).get("spe", 0)) == -1
    assert int(b1.get("boosts", {}).get("spe", 0)) == -1


def test_mega_beta_declaration_updates_species_and_weather() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [_mv("alpha", 0, 1, 0), _mv("alpha", 1, 1, 1), _mv("beta", 0, 1, 2), _mv("beta", 1, 1, 3)]

    resolve_turn_flat(state, rng, client, "champions", planned, mega_beta=1)

    cz = state.party_b[state.leads_b[0]]

    assert str(cz.get("name")) == "Charizard-Mega-Y"
    assert str(cz.get("ability")) == "Drought"
    assert state.weather == "Sun"
    assert state.beta_mega_used is True


def test_single_target_move_respects_foe_slot_under_protect() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[1, 0], leads_b=[0, 1])
    rng = random.Random(7)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 2, 0, doubles_target=int(DoublesTarget.FOE_SLOT_1)),
        _mv("alpha", 1, 3, 1),
        _mv("beta", 0, 4, 2),
        _mv("beta", 1, 1, 3),
    ]

    _reward, _term, events, _dbg = resolve_turn_flat(state, rng, client, "champions", planned)

    prot_blocks = [b for t, b in events if t == "-activate" and "Protect" in b]

    assert any("Gardevoir" in b for b in prot_blocks)
    assert not any("Charizard" in b for b in prot_blocks)


def test_draco_meteor_lowers_attacker_spa_after_hit() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[1, 0], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [_mv("beta", 1, 1, 3), _mv("beta", 0, 4, 2), _mv("alpha", 1, 3, 1), _mv("alpha", 0, 1, 0)]

    resolve_turn_flat(state, rng, client, "champions", planned)

    dn = state.party_a[state.leads_a[0]]

    assert int(dn.get("boosts", {}).get("spa", 0)) == -2


def test_intimidate_on_switch_lowers_both_foes_atk() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_a[2]["ability"] = "Intimidate"

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        {"kind": "switch", "atk_side": "alpha", "field_idx": 0, "to_party": 2, "orig_index": 0},
        _mv("alpha", 1, 3, 1),
        _mv("beta", 0, 4, 2),
        _mv("beta", 1, 1, 3),
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    b0 = state.party_b[state.leads_b[0]]
    b1 = state.party_b[state.leads_b[1]]

    assert int(b0.get("boosts", {}).get("atk", 0)) == -1
    assert int(b1.get("boosts", {}).get("atk", 0)) == -1


def test_defiant_triggers_on_intimidate_net_plus_one_atk() -> None:
    party_a = [party_member("team_eileen", i) for i in range(6)]
    party_b = [party_member("team_eric", i) for i in range(6)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(
        party_a=party_a,
        party_b=party_b,
        leads_a=[0, 1],
        leads_b=[1, 2],
        brought_a=(0, 1, 2, 3),
        brought_b=(0, 1, 2, 3),
    )
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        {"kind": "switch", "atk_side": "alpha", "field_idx": 0, "to_party": 3, "orig_index": 0},
        {"kind": "skip", "atk_side": "alpha", "field_idx": 1, "orig_index": 1},
        {"kind": "skip", "atk_side": "beta", "field_idx": 0, "orig_index": 2},
        {"kind": "skip", "atk_side": "beta", "field_idx": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    king = party_b[state.leads_b[0]]
    other = party_b[state.leads_b[1]]

    assert str(king.get("ability")) == "Defiant"
    assert int(king.get("boosts", {}).get("atk", 0)) == 1
    assert int(other.get("boosts", {}).get("atk", 0)) == -1


def test_stamina_raises_def_when_damaged() -> None:
    party_a = [party_member("team_eileen", i) for i in range(6)]
    party_b = [party_member("team_eric", i) for i in range(6)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(
        party_a=party_a,
        party_b=party_b,
        leads_a=[0, 1],
        leads_b=[0, 1],
        brought_a=(0, 1, 2, 3),
        brought_b=(0, 1, 2, 3),
    )
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0, doubles_target=int(DoublesTarget.FOE_SLOT_0)),
        _mv("alpha", 1, 1, 1),
        _mv("beta", 0, 1, 2),
        _mv("beta", 1, 1, 3),
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    arch = party_b[state.leads_b[0]]

    assert str(arch.get("ability")) == "Stamina"
    assert int(arch.get("boosts", {}).get("def", 0)) == 1


def test_rough_skin_if_chips_contact_attacker() -> None:
    from vgc_rl.doubles_ability_hooks import rough_skin_if

    garch: dict = {
        "name": "Garchomp",
        "ability": "Rough Skin",
        "hpPercentage": 88.0,
        "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
    }
    atk_mon: dict = {
        "name": "Attacker",
        "hpPercentage": 100.0,
        "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
    }
    events: list[tuple[str, str]] = []

    rough_skin_if(garch, atk_mon, "Dragon Claw", events, def_addr="Def", atk_addr="Atk")

    assert float(atk_mon["hpPercentage"]) == 100.0 - 100.0 / 8.0
    assert any(t[0] == "-damage" and "Rough Skin" in t[1] for t in events)


def test_sucker_punch_fails_when_foe_declared_status_move() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_eric", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_a[0]["moves"] = [
        {"name": "Tailwind"},
        {"name": "Moonblast"},
        {"name": "Psychic"},
        {"name": "Protect"},
    ]

    hp_a0_before = float(party_a[0]["hpPercentage"])

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[1, 0])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0),
        _mv("alpha", 1, 2, 1),
        _mv("beta", 0, 1, 2, doubles_target=int(DoublesTarget.FOE_SLOT_0)),
        _mv("beta", 1, 1, 3),
    ]

    _r, _t, events, _d = resolve_turn_flat(state, rng, client, "champions", planned)

    assert float(party_a[0]["hpPercentage"]) == hp_a0_before
    assert any("It failed" in b for t, b in events if t == "-hint")


def test_sucker_punch_deals_damage_when_foe_declared_physical_move() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_eric", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_a[0]["moves"] = [
        {"name": "Iron Head"},
        {"name": "Moonblast"},
        {"name": "Psychic"},
        {"name": "Protect"},
    ]

    hp_a0_before = float(party_a[0]["hpPercentage"])

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[1, 0])
    rng = random.Random(2)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0),
        _mv("alpha", 1, 2, 1),
        _mv("beta", 0, 1, 2, doubles_target=int(DoublesTarget.FOE_SLOT_0)),
        _mv("beta", 1, 1, 3),
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert float(party_a[0]["hpPercentage"]) < hp_a0_before


def test_single_target_damage_skipped_when_encoded_target_is_self() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_eric", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    for m in party_a:
        m["moves"] = [{"name": "Rain Dance"}, {"name": "Rain Dance"}, {"name": "Rain Dance"}, {"name": "Rain Dance"}]

    party_b[0]["moves"] = [{"name": "Rain Dance"}, {"name": "Rain Dance"}, {"name": "Rain Dance"}, {"name": "Rain Dance"}]

    king_pi = party_b[1]
    king_pi["moves"] = [
        {"name": "Rain Dance"},
        {"name": "Rain Dance"},
        {"name": "Rain Dance"},
        {"name": "Low Kick"},
    ]

    hp_k_before = float(king_pi["hpPercentage"])

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[1, 0])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0),
        _mv("alpha", 1, 1, 1),
        _mv("beta", 0, 4, 2, doubles_target=int(DoublesTarget.SELF)),
        _mv("beta", 1, 1, 3),
    ]

    _r, _t, events, _d = resolve_turn_flat(state, rng, client, "champions", planned)

    assert float(king_pi["hpPercentage"]) == hp_k_before
    assert any("cannot target the user" in b for t, b in events if t == "-hint")


def test_mega_venusaurite_yields_thick_fat() -> None:
    from vgc_rl.doubles_mega_tera import apply_mega_evolution

    mon = party_member("team_eric", 5)

    assert apply_mega_evolution(mon) is True
    assert str(mon.get("name")) == "Venusaur-Mega"
    assert str(mon.get("ability")) == "Thick Fat"


class _OhkoFakeOracle(FakeOracleClient):
    def batch(self, body: dict) -> dict:
        results = []

        for req in body["requests"]:
            k = req["kind"]

            if k == "single":
                results.append(
                    {
                        "ok": True,
                        "result": {
                            "moveName": "Thunderbolt",
                            "damagePercentMin": 100.0,
                            "damagePercentMax": 100.0,
                            "koChanceText": "",
                        },
                    }
                )

                continue

            out = super().batch({"requests": [req]})

            results.append(out["results"][0])

        return {"results": results}


def test_focus_sash_survives_first_ohko_then_breaks() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    sash_mon = party_b[0]
    sash_mon["item"] = "Focus Sash"

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[1, 0], leads_b=[0, 1])
    rng = random.Random(0)
    client = _OhkoFakeOracle()

    planned_turn1 = [_mv("beta", 1, 1, 3), _mv("beta", 0, 4, 2), _mv("alpha", 1, 3, 1), _mv("alpha", 0, 1, 0, doubles_target=int(DoublesTarget.FOE_SLOT_0))]

    resolve_turn_flat(state, rng, client, "champions", planned_turn1)

    assert sash_mon.get("focus_sash_consumed") is True
    assert float(sash_mon["hpPercentage"]) > 0
    assert float(sash_mon["hpPercentage"]) == 0.01

    resolve_turn_flat(state, rng, client, "champions", planned_turn1)

    assert float(sash_mon["hpPercentage"]) <= 0


def test_swords_dance_boosts_self_atk() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_a[0]["moves"] = [
        {"name": "Swords Dance"},
        {"name": "Tackle"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0, doubles_target=int(DoublesTarget.SELF)),
        _mv("alpha", 1, 2, 1),
        _mv("beta", 0, 1, 2),
        _mv("beta", 1, 1, 3),
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert int(state.party_a[state.leads_a[0]].get("boosts", {}).get("atk", 0)) == 2


def test_life_dew_heals_self_and_ally() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 50.0

    party_a[0]["moves"] = [
        {"name": "Life Dew"},
        {"name": "Tackle"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]

    for slot in party_b[0]["moves"]:
        slot["name"] = "Tailwind"

    for slot in party_b[1]["moves"]:
        slot["name"] = "Tailwind"

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 1, 0, doubles_target=int(DoublesTarget.SELF)),
        _mv("alpha", 1, 2, 1),
        _mv("beta", 0, 1, 2, doubles_target=int(DoublesTarget.FIELD)),
        _mv("beta", 1, 1, 3, doubles_target=int(DoublesTarget.FIELD)),
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert float(state.party_a[state.leads_a[0]]["hpPercentage"]) == 75.0
    assert float(state.party_a[state.leads_a[1]]["hpPercentage"]) == 75.0


def test_substitute_cost_and_absorbs_damage() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_a[0]["moves"] = [
        {"name": "Substitute"},
        {"name": "Tackle"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = FakeOracleClient()

    sub_turn = [
        _mv("alpha", 0, 1, 0, doubles_target=int(DoublesTarget.SELF)),
        _mv("alpha", 1, 2, 1),
        _mv("beta", 0, 1, 2),
        _mv("beta", 1, 1, 3),
    ]

    resolve_turn_flat(state, rng, client, "champions", sub_turn)

    user = state.party_a[state.leads_a[0]]

    assert float(user["hpPercentage"]) == 75.0
    assert float(user.get("substitute_hp_pct") or 0) == 25.0

    hit_turn = [
        _mv("beta", 0, 1, 2, doubles_target=int(DoublesTarget.FOE_SLOT_0)),
        _mv("beta", 1, 1, 3),
        _mv("alpha", 1, 2, 1),
        _mv("alpha", 0, 2, 0),
    ]

    resolve_turn_flat(state, rng, client, "champions", hit_turn)

    assert float(user["hpPercentage"]) == 75.0
    assert float(user.get("substitute_hp_pct") or 0) < 25.0


def test_kings_shield_blocks_damage_like_protect() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    party_b[1]["moves"] = [
        {"name": "Tackle"},
        {"name": "King's Shield"},
        {"name": "Tackle"},
        {"name": "Tackle"},
    ]
    party_b[1]["name"] = "Kingambit"

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[1, 0], leads_b=[0, 1])
    rng = random.Random(7)
    client = FakeOracleClient()

    planned = [
        _mv("alpha", 0, 2, 0, doubles_target=int(DoublesTarget.FOE_SLOT_1)),
        _mv("alpha", 1, 3, 1),
        _mv("beta", 0, 1, 2),
        _mv("beta", 1, 2, 3, doubles_target=int(DoublesTarget.SELF)),
    ]

    _reward, _term, events, _dbg = resolve_turn_flat(state, rng, client, "champions", planned)

    blocks = [b for t, b in events if t == "-activate" and "Protect" in b]

    assert any("Kingambit" in b for b in blocks)

