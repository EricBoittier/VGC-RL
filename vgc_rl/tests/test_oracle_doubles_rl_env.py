from __future__ import annotations

import numpy as np

from vgc_rl.doubles_action_mask import FORM_ACTION_BRANCHES, legal_flat_mask_alpha
from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_TOTAL_DIM
from vgc_rl.fake_oracle_client import FakeOracleClient
from vgc_rl.oracle_doubles_rl_env import OracleDoublesRlEnv


def _party_hp_sum(env: OracleDoublesRlEnv) -> float:
    assert env._state is not None

    out = 0.0

    for mon in env._state.party_a + env._state.party_b:
        out += float(mon.get("hpPercentage") or 0)

    return out


def test_reset_obs_shape_and_mask_length() -> None:
    env = OracleDoublesRlEnv(FakeOracleClient(), seed=1)
    joints = enumerate_joint_actions_structural()

    obs, info = env.reset(seed=1)

    assert obs.shape == (DOUBLES_OBS_TOTAL_DIM,)
    assert len(info["legal_actions_mask"]) == len(joints) * FORM_ACTION_BRANCHES
    np.testing.assert_array_equal(env.action_masks(), info["legal_actions_mask"])


def test_step_legal_action_updates_hp_or_switch() -> None:
    env = OracleDoublesRlEnv(FakeOracleClient(), seed=2)
    obs, info = env.reset(seed=2)

    hp0 = _party_hp_sum(env)
    leads0 = (tuple(env._state.leads_a), tuple(env._state.leads_b))

    rng = np.random.default_rng(2)
    changed = False

    for _ in range(40):
        mask = np.asarray(info["legal_actions_mask"], dtype=bool)
        legal = np.flatnonzero(mask)

        assert legal.size > 0

        act = int(rng.choice(legal))
        obs2, _reward, _term, _trunc, info = env.step(act)

        assert obs2.shape == (DOUBLES_OBS_TOTAL_DIM,)

        hp1 = _party_hp_sum(env)
        leads1 = (tuple(env._state.leads_a), tuple(env._state.leads_b))

        if hp1 < hp0 or leads1 != leads0:
            changed = True

            break

    assert changed


def test_illegal_alpha_action_remapped_when_legal_remain() -> None:
    env = OracleDoublesRlEnv(FakeOracleClient(), seed=3)
    env.reset(seed=3)

    assert env._state is not None

    ai = env._state.leads_a[0]
    env._state.party_a[ai]["hpPercentage"] = 0

    mask = legal_flat_mask_alpha(env._state, env._joints, game=env._game)
    illegal = np.where(~np.asarray(mask, dtype=bool))[0]

    assert illegal.size > 0

    obs, _reward, _term, _trunc, info = env.step(int(illegal[0]))

    assert obs.shape == (DOUBLES_OBS_TOTAL_DIM,)
    assert len(info["legal_actions_mask"]) == len(env._joints) * FORM_ACTION_BRANCHES
