from __future__ import annotations

import random
from copy import deepcopy

from vgc_rl.doubles_actions import DoublesTarget
from vgc_rl.doubles_turn_engine import DoublesBattleState, resolve_turn_flat
from vgc_rl.example_teams import party_member
from vgc_rl.fake_oracle_client import FakeOracleClient


class _HighDamageFake(FakeOracleClient):
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
                            "damagePercentMin": 55.0,
                            "damagePercentMax": 55.0,
                            "koChanceText": "",
                        },
                    }
                )

                continue

            out = super().batch({"requests": [req]})

            results.append(out["results"][0])

        return {"results": results}


def test_sitrus_triggers_after_damage_threshold() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_b[0]["item"] = "Sitrus Berry"
    party_b[0]["hpPercentage"] = 100.0

    for m in party_a + party_b:
        if float(m.get("hpPercentage") or 0) <= 0:
            m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(0)
    client = _HighDamageFake()
    planned = [
        {"kind": "move", "atk_side": "alpha", "field_idx": 0, "move_slot": 1, "orig_index": 0, "doubles_target": int(DoublesTarget.FOE_SLOT_0)},
        {"kind": "move", "atk_side": "alpha", "field_idx": 1, "move_slot": 2, "orig_index": 1, "doubles_target": int(DoublesTarget.FOE_SLOT_1)},
        {"kind": "move", "atk_side": "beta", "field_idx": 0, "move_slot": 1, "orig_index": 2},
        {"kind": "move", "atk_side": "beta", "field_idx": 1, "move_slot": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    b0 = state.party_b[state.leads_b[0]]

    assert b0.get("sitrus_berry_consumed") is True
    assert float(b0["hpPercentage"]) > 45.0


def test_leftovers_end_of_turn() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_a[0]["item"] = "Leftovers"
    party_a[0]["hpPercentage"] = 50.0

    for m in party_a + party_b:
        if m is not party_a[0]:
            m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(2)
    client = FakeOracleClient()
    planned = [
        {"kind": "move", "atk_side": "alpha", "field_idx": 0, "move_slot": 2, "orig_index": 0},
        {"kind": "move", "atk_side": "alpha", "field_idx": 1, "move_slot": 2, "orig_index": 1},
        {"kind": "move", "atk_side": "beta", "field_idx": 0, "move_slot": 4, "orig_index": 2},
        {"kind": "move", "atk_side": "beta", "field_idx": 1, "move_slot": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    assert float(party_a[0]["hpPercentage"]) > 50.0


def test_weakness_policy_super_effective() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    party_a[0] = deepcopy(party_member("team_beta", 2))
    party_a[0]["item"] = ""
    party_a[0]["activeMovePosition"] = 2

    party_b[0]["item"] = "Weakness Policy"
    party_b[0]["types"] = ["Fire"]

    for m in party_a + party_b:
        m["hpPercentage"] = 100.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    rng = random.Random(3)
    client = FakeOracleClient()
    planned = [
        {"kind": "move", "atk_side": "alpha", "field_idx": 0, "move_slot": 2, "orig_index": 0, "doubles_target": int(DoublesTarget.FOE_SLOT_0)},
        {"kind": "move", "atk_side": "alpha", "field_idx": 1, "move_slot": 2, "orig_index": 1},
        {"kind": "move", "atk_side": "beta", "field_idx": 0, "move_slot": 1, "orig_index": 2},
        {"kind": "move", "atk_side": "beta", "field_idx": 1, "move_slot": 1, "orig_index": 3},
    ]

    resolve_turn_flat(state, rng, client, "champions", planned)

    b0 = state.party_b[state.leads_b[0]]

    assert int(b0.get("boosts", {}).get("atk", 0)) >= 2
