from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train MaskablePPO controlling Beta vs random legal Alpha (CPU). Default --save is derived from --team-alpha-key / --team-beta-key and game.",
    )
    parser.add_argument("--fake-oracle", action="store_true", help="Use deterministic FakeOracleClient (no oracle-server).")
    parser.add_argument("--oracle-url", default=os.environ.get("ORACLE_URL"), help="Oracle base URL when not --fake-oracle")
    parser.add_argument("--timesteps", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=None, help="PPO learning rate (default 1e-3; with --finetune default 3e-4)")
    parser.add_argument(
        "--save",
        default=None,
        metavar="PATH",
        help="Policy zip path (default: beta_<beta_team>_vs_<alpha_team>_<game>[_bring6].zip from vgc_rl.rl_policy_paths)",
    )
    parser.add_argument("--fresh-start", action="store_true", help="Ignore existing --save zip and train a new model")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sv", action="store_true", help="game=sv instead of champions")
    parser.add_argument("--no-mega", action="store_true", help="Disable Mega Evolution training option (Champions).")
    parser.add_argument("--no-tera", action="store_true", help="Disable Terastal training option (SV).")
    parser.add_argument(
        "--six-bring",
        action="store_true",
        help="Six-mon registered teams: first env step is a 90-way bring pick (policy-controlled Beta).",
    )
    parser.add_argument(
        "--team-alpha-key",
        default="team_alpha",
        metavar="KEY",
        help="example_teams.json roster key for the Alpha side (opponent); with --six-bring must be a 6-mon party (default team_alpha; use team_eileen etc. for six-bring)",
    )
    parser.add_argument(
        "--team-beta-key",
        default="team_beta",
        metavar="KEY",
        help="example_teams.json roster key for the Beta side (learned); with --six-bring must be 6-mon (default team_beta; use team_eric etc.)",
    )
    parser.add_argument(
        "--random-pair-bring-on-reset",
        action="store_true",
        help="With --six-bring: sample both brings on reset (skip bring step); first env.step is battle.",
    )
    parser.add_argument(
        "--debug-print-bring",
        "--bring-debug",
        action="store_true",
        dest="debug_print_bring",
        help="With --six-bring: print [bring-debug] lead prefs after each bring resolution.",
    )
    parser.add_argument("--random-bring-alpha", action="store_true", help="With --six-bring: Alpha bring is uniform RNG (ignore policy on bring step).")
    parser.add_argument("--random-bring-beta", action="store_true", help="With --six-bring: Beta bring is uniform RNG (ignore policy / frozen zip on bring step).")
    parser.add_argument(
        "--meta-pool",
        action="store_true",
        help="Sample two distinct teams from meta_teams/ each reset (requires --six-bring). Policy zip gets a _meta suffix.",
    )
    parser.add_argument(
        "--init-policy",
        default=None,
        metavar="PATH",
        help="Load weights from PATH before training (overwrites --save on completion; ignores existing --save unless --fresh-start without init)",
    )
    parser.add_argument(
        "--finetune",
        action="store_true",
        help="Fine-tune mode: default learning rate 3e-4 when --learning-rate omitted; continues timesteps from loaded zip",
    )
    args = parser.parse_args()

    if bool(args.meta_pool) and not bool(args.six_bring):
        print("--meta-pool requires --six-bring", file=sys.stderr)

        return 2

    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
    except ImportError:
        print("Install sb3-contrib stable-baselines3 torch (CPU builds): pip install sb3-contrib", file=sys.stderr)

        return 1

    from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
    from vgc_rl.doubles_obs_identity import (
        DOUBLES_OBS_BATTLE_DIM,
        DOUBLES_OBS_BOOST_DIM,
        DOUBLES_OBS_IDENTITY_DIM,
        DOUBLES_OBS_TOTAL_DIM,
        DOUBLES_OBS_WITH_SIX_BRING_DIM,
        obs_vocab_sizes,
    )
    from vgc_rl.fake_oracle_client import FakeOracleClient
    from vgc_rl.oracle_client import OracleClient
    from vgc_rl.rl_policy_paths import beta_policy_zip_filename
    from vgc_rl.training_utils import load_or_create_maskable_ppo, resolve_learning_rate

    game = "sv" if args.sv else "champions"
    learning_rate = resolve_learning_rate(finetune=bool(args.finetune), learning_rate=args.learning_rate)

    save_path = (
        Path(args.save)
        if args.save is not None
        else Path(
            beta_policy_zip_filename(
                alpha_team_key=str(args.team_alpha_key),
                beta_team_key=str(args.team_beta_key),
                game=game,
                six_bring=bool(args.six_bring),
                meta_pool=bool(args.meta_pool),
            )
        )
    )

    print(
        f"matchup · Alpha roster={args.team_alpha_key} · Beta roster={args.team_beta_key} · game={game} · six_bring={bool(args.six_bring)} · save={save_path}",
        flush=True,
    )

    if args.fake_oracle:
        client = FakeOracleClient()
    else:
        base = args.oracle_url or "http://127.0.0.1:8765"
        client = OracleClient(base_url=base)

        try:
            client.health()
        except Exception as exc:
            print(f"Oracle health failed ({base}): {exc}", file=sys.stderr)

            return 1

    base_env = BetaControlledOracleDoublesEnv(
        oracle=client,
        game=game,
        seed=args.seed,
        allow_mega_evolution=not args.no_mega,
        allow_terastal=not args.no_tera,
        six_mon_bring=args.six_bring,
        team_alpha_key=str(args.team_alpha_key),
        team_beta_key=str(args.team_beta_key),
        meta_pool=bool(args.meta_pool),
        random_bring_alpha=bool(args.random_bring_alpha),
        random_bring_beta=bool(args.random_bring_beta),
        random_pair_bring_on_reset=bool(args.random_pair_bring_on_reset),
        debug_print_bring=bool(args.debug_print_bring),
    )
    env = ActionMasker(base_env, action_mask_fn=lambda e: e.unwrapped.action_masks())

    obs_dim = int(env.observation_space.shape[0])
    expected_dim = DOUBLES_OBS_WITH_SIX_BRING_DIM if args.six_bring else DOUBLES_OBS_TOTAL_DIM

    if obs_dim != expected_dim:
        print(f"Unexpected observation_space.shape[0]={obs_dim}; expected {expected_dim}", file=sys.stderr)

        return 2

    vocab = obs_vocab_sizes()

    print(
        f"Beta env observation_dim={obs_dim} ({DOUBLES_OBS_BATTLE_DIM} battle + {DOUBLES_OBS_BOOST_DIM} boosts + {DOUBLES_OBS_IDENTITY_DIM} identity"
        f"{' + bring tail' if args.six_bring else ''}) · vocab species={vocab['species']} moves={vocab['moves']} "
        f"abilities={vocab['abilities']} items={vocab['items']}",
        flush=True,
    )

    init_policy = Path(args.init_policy) if args.init_policy else None

    if args.fresh_start and save_path.is_file() and init_policy is None:
        print(f"--fresh-start: ignoring existing {save_path.resolve()}", flush=True)

    try:
        loaded = load_or_create_maskable_ppo(
            env=env,
            save_path=save_path,
            init_policy=init_policy,
            fresh_start=bool(args.fresh_start),
            learning_rate=learning_rate,
            seed=args.seed,
            label="Beta",
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)

        return 1

    model = loaded.model

    print(
        f"Beta policy · source={loaded.source} · lr={learning_rate} · save → {save_path.resolve()} · "
        f"num_timesteps={model.num_timesteps}",
        flush=True,
    )

    model.learn(total_timesteps=args.timesteps, reset_num_timesteps=loaded.reset_num_timesteps)
    model.save(str(save_path))

    print("saved:", save_path.resolve(), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
