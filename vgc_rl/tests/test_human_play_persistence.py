from __future__ import annotations

import random

import numpy as np

from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_checkpoint import CHECKPOINT_SCHEMA_VERSION, battle_state_from_checkpoint_dict, battle_state_to_checkpoint_dict
from vgc_rl.doubles_turn_engine import DoublesBattleState
from vgc_rl.doubles_actions import DoublesTarget, JointDoublesAction, MoveSlotAction, SwitchSlotAction

from vgc_rl.interactive_doubles import format_joint_human_summary, prompt_joint_choice, sample_beta_joint_index


def _minimal_mon(*, name: str = "M", hp: float = 55.0) -> dict:
    return {
        "name": name,
        "moves": [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}],
        "hpPercentage": hp,
        "activeMovePosition": 1,
    }


def test_checkpoint_roundtrip_state() -> None:
    state = DoublesBattleState(
        party_a=[_minimal_mon(name="A0"), _minimal_mon(name="A1", hp=100), _minimal_mon(name="A2", hp=0), _minimal_mon(name="A3", hp=22)],
        party_b=[_minimal_mon(name="B0"), _minimal_mon(name="B1"), _minimal_mon(name="B2"), _minimal_mon(name="B3")],
        leads_a=[0, 3],
        leads_b=[1, 2],
        alpha_tailwind_turns_left=2,
        beta_tailwind_turns_left=0,
        protect_prior_successes={("a", 2): 3, ("b", 0): 1},
        weather="Rain",
        weather_turns_left=3,
        electro_shot_charging={("a", 3): True},
        beta_mega_used=True,
        alpha_tera_used=True,
        team_alpha_path="/tmp/a.json",
        team_beta_path="/tmp/b.json",
        team_alpha_id="sha_a",
        team_beta_id="sha_b",
    )

    payload = battle_state_to_checkpoint_dict(state, game="champions", seed=99, step_count=12)

    assert payload["schema_version"] == CHECKPOINT_SCHEMA_VERSION

    assert payload["weather"] == "Rain"
    assert payload["weather_turns_left"] == 3
    assert payload["electro_shot_charging"].get("a:3") is True
    assert payload["team_alpha_path"] == "/tmp/a.json"
    assert payload["team_beta_path"] == "/tmp/b.json"
    assert payload["team_alpha_id"] == "sha_a"
    assert payload["team_beta_id"] == "sha_b"

    state2, game2, seed2, step_count2 = battle_state_from_checkpoint_dict(payload)

    assert state2.weather == "Rain"
    assert state2.weather_turns_left == 3
    assert state2.electro_shot_charging.get(("a", 3)) is True

    assert game2 == "champions"
    assert seed2 == 99
    assert step_count2 == 12
    assert state2.leads_a == state.leads_a
    assert state2.leads_b == state.leads_b
    assert state2.alpha_tailwind_turns_left == 2
    assert state2.beta_tailwind_turns_left == 0
    assert state2.protect_prior_successes == state.protect_prior_successes
    assert state2.beta_mega_used is True
    assert state2.alpha_tera_used is True
    assert state2.team_alpha_path == "/tmp/a.json"
    assert state2.team_beta_path == "/tmp/b.json"
    assert state2.team_alpha_id == "sha_a"
    assert state2.team_beta_id == "sha_b"

    for side in ("party_a", "party_b"):
        for i in range(4):
            assert getattr(state2, side)[i]["hpPercentage"] == getattr(state, side)[i]["hpPercentage"]
            assert getattr(state2, side)[i]["name"] == getattr(state, side)[i]["name"]


def test_checkpoint_roundtrip_six_mon_brought() -> None:
    party_a = [_minimal_mon(name=f"A{i}") for i in range(6)]
    party_b = [_minimal_mon(name=f"B{i}") for i in range(6)]

    state = DoublesBattleState(
        party_a=party_a,
        party_b=party_b,
        leads_a=[1, 4],
        leads_b=[2, 5],
        brought_a=(0, 1, 4, 5),
        brought_b=(1, 2, 3, 5),
    )

    payload = battle_state_to_checkpoint_dict(state, game="champions", seed=3, step_count=1)

    assert payload["brought_a"] == [0, 1, 4, 5]
    assert payload["brought_b"] == [1, 2, 3, 5]

    state2, game2, seed2, step2 = battle_state_from_checkpoint_dict(payload)

    assert game2 == "champions"
    assert seed2 == 3
    assert step2 == 1
    assert state2.brought_a == (0, 1, 4, 5)
    assert state2.brought_b == (1, 2, 3, 5)
    assert state2.leads_a == [1, 4]
    assert state2.leads_b == [2, 5]

    for side in ("party_a", "party_b"):
        for i in range(6):
            assert getattr(state2, side)[i]["hpPercentage"] == getattr(state, side)[i]["hpPercentage"]
            assert getattr(state2, side)[i]["name"] == getattr(state, side)[i]["name"]


def test_format_joint_human_summary_move_and_switch() -> None:
    party = [_minimal_mon(name="A0"), _minimal_mon(name="A1"), _minimal_mon(name="A2"), _minimal_mon(name="A3")]
    leads = [0, 3]
    foe_party = [_minimal_mon(name="Fox"), _minimal_mon(name="Wolf"), _minimal_mon(name="Z"), _minimal_mon(name="W")]
    foe_leads = [0, 1]

    joint = JointDoublesAction(
        active_0=MoveSlotAction(move_slot=0, target=DoublesTarget.FOE_SLOT_0),
        active_1=SwitchSlotAction(bench_index=0),
    )

    text_named = format_joint_human_summary(joint, party, leads, foe_party=foe_party, foe_leads=foe_leads)

    assert "a (Foe A (Fox))" in text_named
    assert "A1" in text_named

    text_plain = format_joint_human_summary(joint, party, leads)

    assert "a (Foe A)" in text_plain


def test_prompt_joint_choice_menu_index() -> None:
    joints = enumerate_joint_actions_structural()
    legal = [0, 5, 10]

    inp = iter(["nope", "100", "1"])

    def fake_input(_prompt: str = "") -> str:
        return next(inp)

    picked = prompt_joint_choice(legal, joints, "TestSide", input_fn=fake_input)

    assert picked == 5


def test_sample_beta_joint_index_deterministic() -> None:
    joints = enumerate_joint_actions_structural()

    mask = np.zeros(len(joints), dtype=np.bool_)
    mask[[1, 44, 100]] = True

    rng = random.Random(12345)

    seen = {sample_beta_joint_index(rng, mask) for _ in range(40)}

    assert seen <= {1, 44, 100}
