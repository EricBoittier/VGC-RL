from __future__ import annotations

import numpy as np

from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
from vgc_rl.fake_oracle_client import FakeOracleClient


def test_beta_env_step_cap_ends_terminated_not_truncated() -> None:
    env = BetaControlledOracleDoublesEnv(
        FakeOracleClient(),
        game="champions",
        seed=0,
        max_steps=3,
        six_mon_bring=False,
        team_alpha_key="team_alpha",
        team_beta_key="team_beta",
    )
    obs, _ = env.reset(seed=0)
    saw_truncated = False
    saw_terminated = False

    for _ in range(32):
        mask = env.action_masks()
        legal = np.flatnonzero(mask)

        if legal.size == 0:
            break

        obs, _reward, terminated, truncated, _info = env.step(int(legal[0]))
        saw_truncated = saw_truncated or bool(truncated)
        saw_terminated = saw_terminated or bool(terminated)

        if terminated or truncated:
            assert terminated is True
            assert truncated is False

            return

    assert saw_terminated
