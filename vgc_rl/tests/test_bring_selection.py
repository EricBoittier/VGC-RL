from __future__ import annotations

import random
from copy import deepcopy

import numpy as np

from vgc_rl.bring_selection import (
    BRING_ACTION_SPACE_SIZE,
    bring_decode,
    bring_encode,
    pure_nash_pairs_zero_sum,
    simulate_alpha_payoff_once,
)
from vgc_rl.doubles_turn_engine import bench_party_positions_for_brought
from vgc_rl.example_teams import load_example_teams
from vgc_rl.fake_oracle_client import FakeOracleClient


def test_bring_encode_decode_bijection_all_actions() -> None:
    seen = set()

    for aid in range(BRING_ACTION_SPACE_SIZE):
        b, pair = bring_decode(aid)

        assert len(set(b)) == 4

        for x in pair:
            assert x in b

        rid = bring_encode(b, [pair[0], pair[1]])

        assert rid == aid

        seen.add(rid)

    assert len(seen) == BRING_ACTION_SPACE_SIZE


def test_bench_party_positions_for_brought_filters_non_brought() -> None:
    brought = (0, 2, 4, 5)
    leads = [0, 4]

    assert bench_party_positions_for_brought(leads, brought) == [2, 5]


def test_pure_nash_pairs_single_cell() -> None:
    u = np.zeros((1, 1), dtype=np.float64)

    assert pure_nash_pairs_zero_sum(u) == [(0, 0)]


def test_simulate_alpha_payoff_once_runs_with_fake_oracle() -> None:
    rng = random.Random(0)
    client = FakeOracleClient()
    data = load_example_teams()
    pa = deepcopy(data["team_eileen"]["party"])
    pb = deepcopy(data["team_eric"]["party"])

    r = simulate_alpha_payoff_once(pa, pb, 0, 1, rng, client, "champions", max_turns=48)

    assert r in (-1.0, 0.0, 1.0)
