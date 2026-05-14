from __future__ import annotations

from copy import deepcopy

import numpy as np

from vgc_rl.doubles_obs_identity import DOUBLES_OBS_IDENTITY_DIM, DOUBLES_OBS_TOTAL_DIM, DOUBLES_OBS_WITH_SIX_BRING_DIM, DOUBLES_RL_BRING_TAIL_DIM, doubles_obs_identity_features
from vgc_rl.doubles_turn_engine import DoublesBattleState
from vgc_rl.example_teams import party_member
from vgc_rl.interactive_doubles import doubles_obs_vector


def test_identity_feats_shape_stable_and_reacts_to_species() -> None:
    pa = [party_member("team_alpha", i) for i in range(4)]
    pb = [party_member("team_beta", i) for i in range(4)]

    x = doubles_obs_identity_features(pa, pb)

    assert x.shape == (DOUBLES_OBS_IDENTITY_DIM,)
    np.testing.assert_array_equal(x, doubles_obs_identity_features(pa, pb))

    pa2 = [deepcopy(party_member("team_alpha", i)) for i in range(4)]

    pa2[0]["name"] = "Zoroark"

    y = doubles_obs_identity_features(pa2, pb)

    assert not np.allclose(x, y)


def test_doubles_obs_vector_concat_length() -> None:
    pa = [deepcopy(party_member("team_alpha", i)) for i in range(4)]
    pb = [deepcopy(party_member("team_beta", i)) for i in range(4)]

    st = DoublesBattleState(party_a=pa, party_b=pb, leads_a=[0, 1], leads_b=[0, 3])

    obs = doubles_obs_vector(st)

    assert obs.shape == (DOUBLES_OBS_TOTAL_DIM,)
    assert np.all((obs >= 0.0) & (obs <= 1.0))


def test_doubles_rl_six_bring_observation_shape() -> None:
    from vgc_rl.interactive_doubles import doubles_rl_six_bring_observation

    pa = [deepcopy(party_member("team_eileen", i)) for i in range(6)]
    pb = [deepcopy(party_member("team_eric", i)) for i in range(6)]

    o = doubles_rl_six_bring_observation(None, party_a_full=pa, party_b_full=pb, game="champions", bring_phase=True, allow_mega_evolution=True, allow_terastal=True)

    assert o.shape == (DOUBLES_OBS_WITH_SIX_BRING_DIM,)
    assert DOUBLES_OBS_WITH_SIX_BRING_DIM == DOUBLES_OBS_TOTAL_DIM + DOUBLES_RL_BRING_TAIL_DIM
