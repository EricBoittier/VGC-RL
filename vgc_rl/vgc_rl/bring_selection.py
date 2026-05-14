from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from itertools import combinations
import random
from typing import Any

import numpy as np

from vgc_rl.doubles_action_mask import legal_joint_mask_alpha, legal_joint_mask_beta
from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_turn_engine import (
    DoublesBattleState,
    apply_initial_field_weather,
    joint_to_planned_side,
    resolve_turn,
    side_party_wiped_brought,
)

BRING_ACTION_SPACE_SIZE = 90

_QUADS: tuple[tuple[int, int, int, int], ...] = tuple(combinations(range(6), 4))
_PAIRS_PER_QUAD: tuple[tuple[tuple[int, int], ...], ...] = tuple(tuple(combinations(q, 2)) for q in _QUADS)


def bring_decode(action_id: int) -> tuple[tuple[int, int, int, int], tuple[int, int]]:
    if not (0 <= action_id < BRING_ACTION_SPACE_SIZE):
        raise ValueError(f"bring action_id must be in 0..{BRING_ACTION_SPACE_SIZE - 1}, got {action_id}")

    qi = action_id // 6
    pi = action_id % 6

    return _QUADS[qi], _PAIRS_PER_QUAD[qi][pi]


def bring_encode(brought: Sequence[int], leads: Sequence[int]) -> int:
    b = tuple(sorted(int(x) for x in brought))

    if len(b) != 4 or len(set(b)) != 4:
        raise ValueError("brought must be four distinct party indices")

    la = int(leads[0])
    lb = int(leads[1])
    sm, lg = (la, lb) if la <= lb else (lb, la)

    if sm not in b or lg not in b:
        raise ValueError("both leads must appear in brought set")

    try:
        qi = _QUADS.index(b)
    except ValueError:
        raise ValueError("brought quartet is not one of the C(6,4) canonical sets") from None

    pair = (sm, lg)

    try:
        pi = _PAIRS_PER_QUAD[qi].index(pair)
    except ValueError:
        raise ValueError("lead pair does not match a bench ordering for this quartet") from None

    return qi * 6 + pi


def battle_state_from_bring_actions(
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    bring_action_a: int,
    bring_action_b: int,
    *,
    team_kw: dict[str, Any] | None = None,
) -> DoublesBattleState:
    brought_a, pair_a = bring_decode(bring_action_a)
    brought_b, pair_b = bring_decode(bring_action_b)
    pa = deepcopy(party_a)
    pb = deepcopy(party_b)

    for m in pa + pb:
        hp = m.get("hpPercentage")

        if hp is None:
            m["hpPercentage"] = 100.0
        else:
            m["hpPercentage"] = float(hp)

    kw = dict(team_kw or {})

    return DoublesBattleState(
        party_a=pa,
        party_b=pb,
        leads_a=[pair_a[0], pair_a[1]],
        leads_b=[pair_b[0], pair_b[1]],
        brought_a=brought_a,
        brought_b=brought_b,
        **kw,
    )


def format_six_bring_lead_prefs_line(
    state: DoublesBattleState,
    *,
    alpha_bring_id: int | None = None,
    beta_bring_id: int | None = None,
) -> str:
    def chunk(side: str, party: list[dict[str, Any]], brought: tuple[int, int, int, int], leads: list[int], bid: int | None) -> str:
        ba = tuple(sorted(brought))
        n0 = str(party[leads[0]].get("name", "?"))
        n1 = str(party[leads[1]].get("name", "?"))
        suf = f" bring_id={bid}" if bid is not None else ""

        return f"{side}{suf} brought={ba} leads_idx={tuple(leads)} leads=({n0} | {n1})"

    a = chunk("Alpha", state.party_a, state.brought_alpha_sorted(), state.leads_a, alpha_bring_id)
    b = chunk("Beta", state.party_b, state.brought_beta_sorted(), state.leads_b, beta_bring_id)

    return "[bring-debug] " + a + " || " + b


def simulate_alpha_payoff_once(
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    bring_action_a: int,
    bring_action_b: int,
    rng: random.Random,
    client: Any,
    game: str,
    *,
    max_turns: int = 128,
    team_kw: dict[str, Any] | None = None,
) -> float:
    state = battle_state_from_bring_actions(party_a, party_b, bring_action_a, bring_action_b, team_kw=team_kw)

    apply_initial_field_weather(state)

    joints = enumerate_joint_actions_structural()

    for _ in range(max_turns):
        if side_party_wiped_brought(state, alpha=True):
            return -1.0

        if side_party_wiped_brought(state, alpha=False):
            return 1.0

        ma = legal_joint_mask_alpha(state, joints, game=game)
        mb = legal_joint_mask_beta(state, joints, game=game)
        legal_a = np.flatnonzero(ma)
        legal_b = np.flatnonzero(mb)

        if legal_a.size == 0:
            return -1.0

        if legal_b.size == 0:
            return 1.0

        ia = int(rng.choice(legal_a))
        ib = int(rng.choice(legal_b))

        ja = joints[ia]
        jb = joints[ib]

        planned_alpha = joint_to_planned_side(
            ja,
            state.party_a,
            state.leads_a,
            atk_side="alpha",
            serial_base=0,
            brought=state.brought_alpha_sorted(),
        )
        planned_beta = joint_to_planned_side(
            jb,
            state.party_b,
            state.leads_b,
            atk_side="beta",
            serial_base=2,
            brought=state.brought_beta_sorted(),
        )

        reward, terminated, _, _ = resolve_turn(state, rng, client, game, planned_alpha, planned_beta)

        if terminated:
            return float(reward)

    return 0.0


def estimate_payoff_matrix(
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    client: Any,
    *,
    game: str,
    rng: random.Random,
    rolls: int,
    max_turns: int = 128,
    team_kw: dict[str, Any] | None = None,
) -> np.ndarray:
    u = np.zeros((BRING_ACTION_SPACE_SIZE, BRING_ACTION_SPACE_SIZE), dtype=np.float64)

    if rolls <= 0:
        return u

    for _ in range(rolls):
        for i in range(BRING_ACTION_SPACE_SIZE):
            for j in range(BRING_ACTION_SPACE_SIZE):
                u[i, j] += simulate_alpha_payoff_once(
                    party_a,
                    party_b,
                    i,
                    j,
                    rng,
                    client,
                    game,
                    max_turns=max_turns,
                    team_kw=team_kw,
                )

    u /= float(rolls)

    return u


def expected_payoffs_vs_mixture(u: np.ndarray, opp_probs: np.ndarray) -> np.ndarray:
    return u @ opp_probs


def best_response_pure(u: np.ndarray, opp_probs: np.ndarray) -> tuple[int, float]:
    ev = expected_payoffs_vs_mixture(u, opp_probs)
    i = int(np.argmax(ev))

    return i, float(ev[i])


def pure_nash_pairs_zero_sum(u: np.ndarray, tol: float = 1e-9) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []

    for i in range(u.shape[0]):
        for j in range(u.shape[1]):
            row_best = np.max(u[i, :])

            if abs(float(u[i, j]) - float(row_best)) > tol:
                continue

            col_best = np.min(u[:, j])

            if abs(float(u[i, j]) - float(col_best)) > tol:
                continue

            out.append((i, j))

    return out


def score_alpha_brings_vs_random_opponent(
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    client: Any,
    *,
    game: str,
    rng: random.Random,
    opponent_samples: int,
    rolls_per_pair: int,
    max_turns: int = 128,
    team_kw: dict[str, Any] | None = None,
) -> np.ndarray:
    scores = np.zeros(BRING_ACTION_SPACE_SIZE, dtype=np.float64)

    for i in range(BRING_ACTION_SPACE_SIZE):
        acc = 0.0
        n = 0

        for _ in range(opponent_samples):
            j = rng.randrange(BRING_ACTION_SPACE_SIZE)

            for _ in range(rolls_per_pair):
                acc += simulate_alpha_payoff_once(
                    party_a,
                    party_b,
                    i,
                    j,
                    rng,
                    client,
                    game,
                    max_turns=max_turns,
                    team_kw=team_kw,
                )
                n += 1

        scores[i] = acc / float(max(n, 1))

    return scores
