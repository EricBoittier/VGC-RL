from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import numpy as np

from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
from vgc_rl.doubles_turn_engine import DoublesBattleState, side_party_wiped_brought
from vgc_rl.example_teams import load_example_teams
from vgc_rl.fake_oracle_client import FakeOracleClient
from vgc_rl.oracle_client import OracleClient
from vgc_rl.replay import build_replay_document, force_battle_outcome, snapshot_state
from vgc_rl.replay_recorder import ReplayCaptureWrapper
from vgc_rl.rl_policy_paths import alpha_policy_zip_filename, beta_policy_zip_filename
from vgc_rl.team_registry import load_meta_manifest, meta_pool_keys, team_key_exists


def list_teams_for_viewer(*, six_mon_only: bool = True) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    data = load_example_teams()

    for key, block in data.items():
        if key == "meta" or not isinstance(block, dict):
            continue

        party = block.get("party")

        if not isinstance(party, list):
            continue

        if six_mon_only and len(party) != 6:
            continue

        if not six_mon_only and len(party) not in (4, 6):
            continue

        label = block.get("label")

        if not isinstance(label, str):
            label = key

        species = [str((m or {}).get("name") or "?") for m in party[:6]]
        out.append({"key": key, "label": label, "species": species, "six_mon": len(party) == 6})
        seen.add(key)

    manifest = load_meta_manifest()
    teams = manifest.get("teams")

    if isinstance(teams, list):
        for row in teams:
            if not isinstance(row, dict):
                continue

            key = row.get("key")

            if not isinstance(key, str) or key in seen:
                continue

            species = row.get("species")

            if not isinstance(species, list):
                continue

            if six_mon_only and len(species) != 6:
                continue

            label = row.get("label")

            if not isinstance(label, str):
                label = key

            out.append(
                {
                    "key": key,
                    "label": label,
                    "species": [str(s) for s in species],
                    "six_mon": len(species) == 6,
                }
            )
            seen.add(key)

    out.sort(key=lambda row: str(row.get("label") or row.get("key")))

    return out


def list_policy_zips(policy_dir: Path) -> list[str]:
    root = policy_dir.resolve()

    if not root.is_dir():
        return []

    return sorted(p.name for p in root.glob("*.zip"))


def resolve_policy_path(
    policy_dir: Path,
    *,
    side: str,
    filename: str | None,
    team_alpha_key: str,
    team_beta_key: str,
    game: str,
    six_bring: bool,
    meta_pool: bool,
    default_alpha: Path | None,
    default_beta: Path | None,
) -> Path:
    root = policy_dir.resolve()

    if filename:
        candidate = (root / filename).resolve()

        if not str(candidate).startswith(str(root)) or not candidate.is_file():
            raise FileNotFoundError(f"{side} policy not found: {filename}")

        return candidate

    if side == "alpha":
        if default_alpha is not None and default_alpha.is_file():
            return default_alpha.resolve()

        guess = root / alpha_policy_zip_filename(
            alpha_team_key=team_alpha_key,
            beta_team_key=team_beta_key,
            game=game,
            six_bring=six_bring,
            meta_pool=meta_pool,
        )

        if guess.is_file():
            return guess.resolve()

    if side == "beta":
        if default_beta is not None and default_beta.is_file():
            return default_beta.resolve()

        guess = root / beta_policy_zip_filename(
            alpha_team_key=team_alpha_key,
            beta_team_key=team_beta_key,
            game=game,
            six_bring=six_bring,
            meta_pool=meta_pool,
        )

        if guess.is_file():
            return guess.resolve()

    raise FileNotFoundError(f"no {side} policy zip for teams {team_alpha_key!r} vs {team_beta_key!r}")


def simulate_ai_replay(
    *,
    team_alpha_key: str,
    team_beta_key: str,
    alpha_policy_path: Path,
    beta_policy_path: Path,
    seed: int | None = None,
    max_steps: int = 128,
    game: str = "champions",
    fake_oracle: bool = True,
    oracle_url: str | None = None,
    alpha_deterministic: bool = True,
    beta_deterministic: bool = True,
    allow_mega_evolution: bool = True,
    allow_terastal: bool = True,
    random_bring_alpha: bool = False,
    random_bring_beta: bool = False,
    play_to_completion: bool = True,
) -> dict[str, Any]:
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
    except ImportError as exc:
        raise RuntimeError("Install train extras: uv sync --extra train (sb3-contrib, torch)") from exc

    from vgc_rl.sb3_masked_policy import load_maskable_ppo

    if not team_key_exists(team_alpha_key):
        raise ValueError(f"unknown team key: {team_alpha_key!r}")

    if not team_key_exists(team_beta_key):
        raise ValueError(f"unknown team key: {team_beta_key!r}")

    if fake_oracle:
        client: FakeOracleClient | OracleClient = FakeOracleClient()
    else:
        base = oracle_url or "http://127.0.0.1:8765"
        client = OracleClient(base_url=base)

        try:
            client.health()
        except Exception as exc:
            raise RuntimeError(f"Oracle unavailable at {base}: {exc}") from exc

    alpha_model = load_maskable_ppo(str(alpha_policy_path), device="cpu")
    beta_model = load_maskable_ppo(str(beta_policy_path), device="cpu")

    if seed is not None:
        s = int(seed)
        np.random.seed(s)
        random.seed(s)

        try:
            import torch

            torch.manual_seed(s)
        except ImportError:
            pass

        for model in (alpha_model, beta_model):
            if hasattr(model, "set_random_seed"):
                model.set_random_seed(s)

    env_max_steps = max(int(max_steps), 512)

    inner = BetaControlledOracleDoublesEnv(
        client,
        game=game,
        max_steps=env_max_steps,
        seed=seed,
        six_mon_bring=True,
        team_alpha_key=team_alpha_key,
        team_beta_key=team_beta_key,
        alpha_policy_model=alpha_model,
        alpha_policy_deterministic=alpha_deterministic,
        random_bring_alpha=random_bring_alpha,
        random_bring_beta=random_bring_beta,
        allow_mega_evolution=allow_mega_evolution,
        allow_terastal=allow_terastal,
    )
    env: Any = ActionMasker(inner, action_mask_fn=lambda e: e.unwrapped.action_masks())
    capture = ReplayCaptureWrapper(env, save_dir=Path("."), save_every_n_episodes=10_000, enabled=False)
    obs, _info = capture.reset(seed=seed)
    terminated = False
    truncated = False
    last_reward_beta = 0.0
    info: dict[str, Any] = dict(_info)
    steps = 0
    step_limit = max(env_max_steps * 24, 2048)
    absolute_cap = 8192
    party_wiped_alpha = False
    party_wiped_beta = False

    while steps < absolute_cap:
        if steps >= step_limit:
            step_limit += max(env_max_steps, 128)
        battle_state = getattr(inner, "_state", None)

        if battle_state is not None:
            party_wiped_alpha = side_party_wiped_brought(battle_state, alpha=True)
            party_wiped_beta = side_party_wiped_brought(battle_state, alpha=False)

            if party_wiped_alpha or party_wiped_beta:
                terminated = True
                truncated = False

                break

        mask = capture.env.unwrapped.action_masks()
        legal = np.flatnonzero(mask)

        if legal.size == 0:
            action = 0
        else:
            action, _ = beta_model.predict(obs, deterministic=beta_deterministic, action_masks=mask)
            action = int(action)

        try:
            obs, reward_beta, term, trunc, info = capture.step(action)
        except RuntimeError:
            battle_state = getattr(inner, "_state", None)

            if battle_state is not None:
                party_wiped_alpha = side_party_wiped_brought(battle_state, alpha=True)
                party_wiped_beta = side_party_wiped_brought(battle_state, alpha=False)

                if party_wiped_alpha or party_wiped_beta:
                    terminated = True

                    break

            continue

        last_reward_beta = float(reward_beta)
        steps += 1

        battle_state = getattr(inner, "_state", None)

        if battle_state is not None:
            party_wiped_alpha = side_party_wiped_brought(battle_state, alpha=True)
            party_wiped_beta = side_party_wiped_brought(battle_state, alpha=False)
        else:
            party_wiped_alpha = bool(info.get("party_wiped_alpha"))
            party_wiped_beta = bool(info.get("party_wiped_beta"))

        if bool(term) or party_wiped_alpha or party_wiped_beta:
            terminated = True
            truncated = False

            break

        if bool(trunc) and play_to_completion:
            inner._max_steps = int(inner._max_steps) + max(env_max_steps, 64)

            continue

        if bool(trunc):
            truncated = True

    inner_state = capture.env.unwrapped
    battle_state = getattr(inner_state, "_state", None)

    if battle_state is not None:
        party_wiped_alpha = side_party_wiped_brought(battle_state, alpha=True)
        party_wiped_beta = side_party_wiped_brought(battle_state, alpha=False)

    final_state = snapshot_state(battle_state, game=game, step_count=int(getattr(inner_state, "_step_count", 0) or 0))
    outcome = force_battle_outcome(battle_state, last_reward_beta=last_reward_beta)

    meta = {
        "phase": "viewer_simulate",
        "team_alpha_key": getattr(inner_state, "_active_alpha_key", team_alpha_key),
        "team_beta_key": getattr(inner_state, "_active_beta_key", team_beta_key),
        "alpha_policy": alpha_policy_path.name,
        "beta_policy": beta_policy_path.name,
        "seed": seed,
        "max_steps": max_steps,
        "alpha_deterministic": alpha_deterministic,
        "beta_deterministic": beta_deterministic,
        "allow_mega_evolution": allow_mega_evolution,
        "allow_terastal": allow_terastal,
        "random_bring_alpha": random_bring_alpha,
        "random_bring_beta": random_bring_beta,
        "fake_oracle": fake_oracle,
        "outcome": outcome,
        "battle_steps": steps,
    }

    return build_replay_document(
        game=game,
        meta=meta,
        initial_state=capture._initial,
        frames=list(capture._frames),
        final_state=final_state,
        outcome=outcome,
    )


def apply_vs_greedy(
    *,
    vs_greedy: str | None,
    alpha_deterministic: bool,
    beta_deterministic: bool,
) -> tuple[bool, bool]:
    if vs_greedy == "alpha":
        return True, False

    if vs_greedy == "beta":
        return False, True

    return alpha_deterministic, beta_deterministic


def viewer_simulate_defaults() -> dict[str, Any]:
    alpha_team, beta_team = default_viewer_team_keys()

    return {
        "team_alpha_key": alpha_team,
        "team_beta_key": beta_team,
        "max_turns": 128,
        "game": "champions",
        "alpha_deterministic": True,
        "beta_deterministic": True,
        "allow_mega_evolution": True,
        "allow_terastal": True,
        "random_bring_alpha": False,
        "random_bring_beta": False,
        "save": True,
        "meta_pool_policies": True,
        "live_oracle": False,
    }


def default_viewer_team_keys() -> tuple[str, str]:
    pool = meta_pool_keys(six_mon_only=True)
    data = load_example_teams()

    if "team_eileen" in data and "team_eric" in data:
        return "team_eileen", "team_eric"

    if len(pool) >= 2:
        return pool[0], pool[1]

    return "team_alpha", "team_beta"
