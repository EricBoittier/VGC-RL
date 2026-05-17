from __future__ import annotations

import random

from vgc_rl.team_registry import copy_party, load_party_by_key, meta_pool_keys, prepare_parties_for_reset


def test_meta_pool_keys_non_empty() -> None:
    keys = meta_pool_keys(six_mon_only=True)

    assert len(keys) >= 2


def test_load_meta_team_party() -> None:
    key = meta_pool_keys(six_mon_only=True)[0]
    label, party = load_party_by_key(key)

    assert label is not None
    assert len(party) == 6
    assert party[0]["name"]


def test_prepare_parties_meta_pool_samples_distinct() -> None:
    rng = random.Random(0)
    a1, b1, _, _ = prepare_parties_for_reset(
        team_alpha_key="team_eileen",
        team_beta_key="team_eric",
        meta_pool=True,
        team_pool_keys=None,
        rng=rng,
        six_mon_bring=True,
        expected_party_len=6,
    )
    a2, b2, _, _ = prepare_parties_for_reset(
        team_alpha_key="team_eileen",
        team_beta_key="team_eric",
        meta_pool=True,
        team_pool_keys=None,
        rng=rng,
        six_mon_bring=True,
        expected_party_len=6,
    )

    assert a1 != b1
    assert len(copy_party(a1)) == 6
