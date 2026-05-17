from __future__ import annotations

from vgc_rl.doubles_turn_engine import DoublesBattleState, side_party_wiped_brought
from vgc_rl.replay import force_battle_outcome


def apply_step_cap_as_decisive_end(
    state: DoublesBattleState,
    *,
    step_count: int,
    max_steps: int,
    terminated: bool,
) -> tuple[bool, bool, str | None]:
    if terminated or step_count < max_steps:
        return terminated, False, None

    if side_party_wiped_brought(state, alpha=True) or side_party_wiped_brought(state, alpha=False):
        return True, False, None

    return True, False, force_battle_outcome(state)


def alpha_reward_for_outcome(outcome: str) -> float:
    if outcome == "alpha_win":
        return 1.0

    if outcome == "beta_win":
        return -1.0

    return 0.0
