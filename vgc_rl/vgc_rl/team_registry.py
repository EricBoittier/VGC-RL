from __future__ import annotations

import json
import random
from copy import deepcopy
from importlib import resources
from typing import Any

from vgc_rl.example_teams import load_example_teams
from vgc_rl.team_json import load_team_party


def load_meta_manifest() -> dict[str, Any]:
    raw = resources.files("vgc_rl").joinpath("examples/meta_teams/manifest.json").read_text(encoding="utf-8")

    return json.loads(raw)


def meta_pool_keys(*, six_mon_only: bool = True) -> list[str]:
    manifest = load_meta_manifest()
    teams = manifest.get("teams")

    if not isinstance(teams, list):
        return []

    keys: list[str] = []

    for row in teams:
        if not isinstance(row, dict):
            continue

        key = row.get("key")

        if not isinstance(key, str):
            continue

        if six_mon_only:
            species = row.get("species")

            if not isinstance(species, list) or len(species) != 6:
                continue

        keys.append(key)

    return keys


def team_key_exists(key: str) -> bool:
    data = load_example_teams()

    if key in data and isinstance(data[key], dict):
        return True

    return key in {k for k in meta_pool_keys(six_mon_only=False)}


def party_length_for_key(key: str) -> int:
    _, party = load_party_by_key(key)

    return len(party)


def load_party_by_key(key: str) -> tuple[str | None, list[dict[str, Any]]]:
    data = load_example_teams()

    if key in data and isinstance(data[key], dict):
        block = data[key]
        label = block.get("label")

        if label is not None:
            label = str(label)

        party = block.get("party")

        if not isinstance(party, list):
            raise ValueError(f"team {key!r} has no party array")

        return label, [deepcopy(dict(x)) for x in party]

    manifest = load_meta_manifest()
    teams = manifest.get("teams")

    if isinstance(teams, list):
        for row in teams:
            if isinstance(row, dict) and row.get("key") == key:
                pid = row.get("id")

                if not isinstance(pid, str):
                    break

                path = resources.files("vgc_rl").joinpath(f"examples/meta_teams/{pid}.json")

                return load_team_party(path)

    raise KeyError(f"unknown team key: {key!r}")


def copy_party(key: str) -> list[dict[str, Any]]:
    _, party = load_party_by_key(key)

    return [deepcopy(m) for m in party]


def sample_meta_pool_keys(rng: random.Random, *, count: int = 2, six_mon_only: bool = True) -> list[str]:
    pool = meta_pool_keys(six_mon_only=six_mon_only)

    if len(pool) < count:
        raise ValueError(f"meta pool needs at least {count} teams (got {len(pool)})")

    return rng.sample(pool, count)


def resolve_reset_team_keys(
    *,
    team_alpha_key: str,
    team_beta_key: str,
    meta_pool: bool,
    team_pool_keys: list[str] | None,
    rng: random.Random,
    six_mon_bring: bool,
) -> tuple[str, str]:
    if meta_pool or team_pool_keys is not None:
        pool = list(team_pool_keys) if team_pool_keys is not None else meta_pool_keys(six_mon_only=six_mon_bring)

        if len(pool) < 2:
            raise ValueError(f"team pool needs at least 2 keys (got {len(pool)})")

        alpha_key, beta_key = rng.sample(pool, 2)

        return alpha_key, beta_key

    return team_alpha_key, team_beta_key


def prepare_parties_for_reset(
    *,
    team_alpha_key: str,
    team_beta_key: str,
    meta_pool: bool = False,
    team_pool_keys: list[str] | None = None,
    rng: random.Random,
    six_mon_bring: bool,
    expected_party_len: int,
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    alpha_key, beta_key = resolve_reset_team_keys(
        team_alpha_key=team_alpha_key,
        team_beta_key=team_beta_key,
        meta_pool=meta_pool,
        team_pool_keys=team_pool_keys,
        rng=rng,
        six_mon_bring=six_mon_bring,
    )

    party_a = copy_party(alpha_key)
    party_b = copy_party(beta_key)

    if len(party_a) != expected_party_len or len(party_b) != expected_party_len:
        raise ValueError(
            f"expected party length {expected_party_len} for both teams "
            f"(got {len(party_a)} for {alpha_key!r}, {len(party_b)} for {beta_key!r})",
        )

    for m in party_a + party_b:
        m["hpPercentage"] = 100

    return alpha_key, beta_key, party_a, party_b
