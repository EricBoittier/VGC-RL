from __future__ import annotations

from vgc_rl.viewer_simulate import apply_vs_greedy


def test_apply_vs_greedy_overrides_stochastic_flags() -> None:
    a, b = apply_vs_greedy(vs_greedy="alpha", alpha_deterministic=False, beta_deterministic=False)

    assert a is True
    assert b is False

    a, b = apply_vs_greedy(vs_greedy="beta", alpha_deterministic=True, beta_deterministic=True)

    assert a is False
    assert b is True

    a, b = apply_vs_greedy(vs_greedy=None, alpha_deterministic=True, beta_deterministic=False)

    assert a is True
    assert b is False
