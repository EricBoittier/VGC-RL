from __future__ import annotations

from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_WITH_SIX_BRING_DIM
from vgc_rl.fake_oracle_client import FakeOracleClient


def test_meta_pool_reset_obs_shape() -> None:
    env = BetaControlledOracleDoublesEnv(
        oracle=FakeOracleClient(),
        six_mon_bring=True,
        meta_pool=True,
        random_pair_bring_on_reset=True,
        seed=3,
    )

    obs, info = env.reset(seed=3)

    assert obs.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert info["team_alpha_key"] != info["team_beta_key"]
    assert str(info["team_alpha_key"]).startswith("meta_")
