from __future__ import annotations

from pathlib import Path

import pytest

from vgc_rl.viewer_simulate import list_teams_for_viewer, simulate_ai_replay


def test_list_teams_for_viewer_includes_six_mon() -> None:
    teams = list_teams_for_viewer(six_mon_only=True)

    assert teams
    assert all(t.get("six_mon") for t in teams)
    assert any(t["key"] == "team_eileen" for t in teams)


@pytest.mark.skipif(
    not Path("alpha_alpha_vs_beta_champions_bring6_meta.zip").is_file()
    or not Path("beta_beta_vs_alpha_champions_bring6_meta.zip").is_file(),
    reason="trained policy zips not in cwd",
)
def test_simulate_ai_replay_produces_frames() -> None:
    doc = simulate_ai_replay(
        team_alpha_key="team_eileen",
        team_beta_key="team_eric",
        alpha_policy_path=Path("alpha_alpha_vs_beta_champions_bring6_meta.zip"),
        beta_policy_path=Path("beta_beta_vs_alpha_champions_bring6_meta.zip"),
        seed=0,
        max_steps=8,
        fake_oracle=True,
    )

    assert doc["frames"]
    assert doc["meta"]["phase"] == "viewer_simulate"
    assert doc["outcome"] in ("alpha_win", "beta_win", "draw")
    assert doc["outcome"] != "truncated"


@pytest.mark.skipif(
    not Path("alpha_alpha_vs_beta_champions_bring6_meta.zip").is_file()
    or not Path("beta_beta_vs_alpha_champions_bring6_meta.zip").is_file(),
    reason="trained policy zips not in cwd",
)
def test_simulate_low_max_steps_still_finishes_with_winner() -> None:
    doc = simulate_ai_replay(
        team_alpha_key="team_eileen",
        team_beta_key="team_eric",
        alpha_policy_path=Path("alpha_alpha_vs_beta_champions_bring6_meta.zip"),
        beta_policy_path=Path("beta_beta_vs_alpha_champions_bring6_meta.zip"),
        seed=3,
        max_steps=6,
        fake_oracle=True,
        play_to_completion=True,
    )

    assert doc["outcome"] in ("alpha_win", "beta_win", "draw")
    assert len(doc["frames"]) > 6
