from __future__ import annotations

from vgc_rl.doubles_turn_engine import DoublesBattleState
from vgc_rl.example_teams import party_member
from vgc_rl.replay import replay_outcome, replay_outcome_from_state


def test_replay_outcome_prefers_wipe_over_truncated_flag() -> None:
    assert replay_outcome(terminated=False, truncated=True, party_wiped_alpha=True, party_wiped_beta=False) == "beta_win"

    assert replay_outcome(terminated=False, truncated=True, party_wiped_alpha=False, party_wiped_beta=True) == "alpha_win"


def test_replay_outcome_uses_reward_when_terminated_without_wipe() -> None:
    assert replay_outcome(terminated=True, truncated=False, party_wiped_alpha=False, party_wiped_beta=False, last_reward_beta=1.0) == "beta_win"

    assert replay_outcome(terminated=True, truncated=False, party_wiped_alpha=False, party_wiped_beta=False, last_reward_beta=-1.0) == "alpha_win"


def test_replay_outcome_from_state_speed_tiebreak_when_hp_tied() -> None:
    from vgc_rl.replay import force_battle_outcome

    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for i, hp in enumerate((50.0, 50.0, 0.0, 0.0)):
        party_a[i]["hpPercentage"] = hp
        party_a[i]["evs"]["spe"] = 32

    for i, hp in enumerate((50.0, 50.0, 0.0, 0.0)):
        party_b[i]["hpPercentage"] = hp
        party_b[i]["evs"]["spe"] = 8

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 1])

    assert force_battle_outcome(state) == "alpha_win"
    assert replay_outcome_from_state(state, terminated=False, truncated=True, require_winner=True) == "alpha_win"
