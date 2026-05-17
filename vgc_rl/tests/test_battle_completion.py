from __future__ import annotations

from vgc_rl.battle_completion import apply_step_cap_as_decisive_end, alpha_reward_for_outcome
from vgc_rl.doubles_turn_engine import DoublesBattleState
from vgc_rl.example_teams import party_member


def test_step_cap_forces_decisive_end_not_truncation() -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for mon in party_a + party_b:
        mon["hpPercentage"] = 50.0

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])
    terminated, truncated, outcome = apply_step_cap_as_decisive_end(
        state,
        step_count=128,
        max_steps=128,
        terminated=False,
    )

    assert terminated is True
    assert truncated is False
    assert outcome in ("alpha_win", "beta_win")


def test_alpha_reward_for_outcome_signs() -> None:
    assert alpha_reward_for_outcome("alpha_win") == 1.0
    assert alpha_reward_for_outcome("beta_win") == -1.0
