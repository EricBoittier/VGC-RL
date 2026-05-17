from __future__ import annotations

import re


def team_key_slug(team_key: str) -> str:
    k = str(team_key).strip()

    if k.startswith("team_"):
        return k[5:]

    return k


def _safe_slug(s: str) -> str:
    t = re.sub(r"[^0-9A-Za-z._-]+", "_", s).strip("_")

    return t or "team"


def beta_policy_zip_filename(*, alpha_team_key: str, beta_team_key: str, game: str, six_bring: bool, meta_pool: bool = False) -> str:
    a = _safe_slug(team_key_slug(alpha_team_key))
    b = _safe_slug(team_key_slug(beta_team_key))
    g = "sv" if game == "sv" else "champions"
    suf = "_bring6" if six_bring else ""
    meta = "_meta" if meta_pool else ""

    return f"beta_{b}_vs_{a}_{g}{suf}{meta}.zip"


def alpha_policy_zip_filename(*, alpha_team_key: str, beta_team_key: str, game: str, six_bring: bool, meta_pool: bool = False) -> str:
    a = _safe_slug(team_key_slug(alpha_team_key))
    b = _safe_slug(team_key_slug(beta_team_key))
    g = "sv" if game == "sv" else "champions"
    suf = "_bring6" if six_bring else ""
    meta = "_meta" if meta_pool else ""

    return f"alpha_{a}_vs_{b}_{g}{suf}{meta}.zip"
