from __future__ import annotations

import numpy as np

from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
from vgc_rl.doubles_action_mask import FORM_ACTION_BRANCHES
from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_TOTAL_DIM
from vgc_rl.fake_oracle_client import FakeOracleClient


def test_beta_env_reset_masks_and_step() -> None:
    joints = enumerate_joint_actions_structural()
    env = BetaControlledOracleDoublesEnv(oracle=FakeOracleClient(), game="champions", seed=0)

    obs, info = env.reset(seed=0)

    assert obs.shape == (DOUBLES_OBS_TOTAL_DIM,)
    assert info["legal_actions_mask"].shape == (len(joints) * FORM_ACTION_BRANCHES,)

    m = env.action_masks()

    assert m.shape == (len(joints) * FORM_ACTION_BRANCHES,)
    assert bool(m.any())

    legal = np.flatnonzero(m)
    obs2, r, term, trunc, inf2 = env.step(int(legal[0]))

    assert obs2.shape == (DOUBLES_OBS_TOTAL_DIM,)
    assert isinstance(r, float)
    assert inf2["legal_actions_mask"].shape == (len(joints) * FORM_ACTION_BRANCHES,)
