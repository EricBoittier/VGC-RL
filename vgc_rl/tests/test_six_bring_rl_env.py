from __future__ import annotations

import numpy as np

from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
from vgc_rl.bring_selection import BRING_ACTION_SPACE_SIZE
from vgc_rl.doubles_action_mask import FORM_ACTION_BRANCHES
from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_WITH_SIX_BRING_DIM
from vgc_rl.fake_oracle_client import FakeOracleClient
from vgc_rl.oracle_doubles_rl_env import OracleDoublesRlEnv


def test_oracle_alpha_six_bring_reset_mask_and_transition() -> None:
    joints = enumerate_joint_actions_structural()
    n_b = len(joints) * FORM_ACTION_BRANCHES

    env = OracleDoublesRlEnv(FakeOracleClient(), seed=7, six_mon_bring=True)

    obs, info = env.reset(seed=7)

    assert obs.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert info["awaiting_bring"] is True

    m = np.asarray(info["legal_actions_mask"], dtype=bool)

    assert m.shape == (BRING_ACTION_SPACE_SIZE + n_b,)
    assert bool(m[:BRING_ACTION_SPACE_SIZE].all())
    assert not bool(m[BRING_ACTION_SPACE_SIZE:].any())

    obs2, r, term, trunc, info2 = env.step(3)

    assert obs2.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert r == 0.0
    assert not term and not trunc
    assert info2["awaiting_bring"] is False
    assert info2["alpha_bring_action"] == 3

    m2 = np.asarray(info2["legal_actions_mask"], dtype=bool)

    assert not bool(m2[:BRING_ACTION_SPACE_SIZE].any())
    assert bool(m2[BRING_ACTION_SPACE_SIZE:].any())


def test_beta_control_six_bring_first_step_is_beta_bring() -> None:
    joints = enumerate_joint_actions_structural()
    n_b = len(joints) * FORM_ACTION_BRANCHES

    env = BetaControlledOracleDoublesEnv(FakeOracleClient(), seed=1, six_mon_bring=True)

    obs, info = env.reset(seed=1)

    assert obs.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert info["awaiting_bring"] is True

    m = np.asarray(info["legal_actions_mask"], dtype=bool)

    assert m.shape == (BRING_ACTION_SPACE_SIZE + n_b,)

    obs2, r, term, trunc, info2 = env.step(42)

    assert info2["beta_bring_action"] == 42
    assert r == 0.0
    assert not term


def test_oracle_random_pair_bring_on_reset_skips_bring_phase() -> None:
    joints = enumerate_joint_actions_structural()
    n_b = len(joints) * FORM_ACTION_BRANCHES

    env = OracleDoublesRlEnv(FakeOracleClient(), seed=99, six_mon_bring=True, random_pair_bring_on_reset=True)

    obs, info = env.reset(seed=99)

    assert obs.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert info["awaiting_bring"] is False
    assert "alpha_bring_action" in info and "beta_bring_action" in info

    m = np.asarray(info["legal_actions_mask"], dtype=bool)

    assert m.shape == (BRING_ACTION_SPACE_SIZE + n_b,)
    assert not bool(m[:BRING_ACTION_SPACE_SIZE].any())
    assert bool(m[BRING_ACTION_SPACE_SIZE:].any())
