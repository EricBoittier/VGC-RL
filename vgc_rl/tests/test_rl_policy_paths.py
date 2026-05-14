from __future__ import annotations

from vgc_rl.rl_policy_paths import alpha_policy_zip_filename, beta_policy_zip_filename, team_key_slug


def test_team_key_slug_strips_team_prefix() -> None:
    assert team_key_slug("team_eileen") == "eileen"
    assert team_key_slug("custom") == "custom"


def test_beta_policy_zip_filename_pattern() -> None:
    assert beta_policy_zip_filename(alpha_team_key="team_alpha", beta_team_key="team_beta", game="champions", six_bring=False) == "beta_beta_vs_alpha_champions.zip"

    assert (
        beta_policy_zip_filename(alpha_team_key="team_eileen", beta_team_key="team_eric", game="champions", six_bring=True) == "beta_eric_vs_eileen_champions_bring6.zip"
    )


def test_alpha_policy_zip_filename_pattern() -> None:
    assert alpha_policy_zip_filename(alpha_team_key="team_alpha", beta_team_key="team_beta", game="sv", six_bring=False) == "alpha_alpha_vs_beta_sv.zip"
