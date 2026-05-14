from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Alternating self-play: train MaskablePPO Beta vs (frozen Alpha | random), then Alpha vs (frozen Beta | random); repeat. "
        "Default policy zips are named from --team-alpha-key / --team-beta-key and game.",
    )
    parser.add_argument("--fake-oracle", action="store_true", help="Use deterministic FakeOracleClient (no oracle-server).")
    parser.add_argument("--oracle-url", default=os.environ.get("ORACLE_URL"), help="Oracle base URL when not --fake-oracle")
    parser.add_argument("--alternating-rounds", type=int, default=4, metavar="N", help="Full cycles (Beta phase then Alpha phase each)")
    parser.add_argument("--steps-per-phase", type=int, default=4096, metavar="T", help="MaskablePPO.learn timesteps per side per round")
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument(
        "--save-alpha",
        type=str,
        default=None,
        metavar="PATH",
        help="Alpha policy zip (default: alpha_<alpha>_vs_<beta>_<game>[_bring6].zip)",
    )
    parser.add_argument(
        "--save-beta",
        type=str,
        default=None,
        metavar="PATH",
        help="Beta policy zip (default: beta_<beta>_vs_<alpha>_<game>[_bring6].zip)",
    )
    parser.add_argument("--fresh-start", action="store_true", help="Ignore existing policy zips for both sides")
    parser.add_argument("--opponent-stochastic", action="store_true", help="Frozen opponent samples actions (default deterministic greedy)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sv", action="store_true", help="game=sv instead of champions")
    parser.add_argument("--no-mega", action="store_true", help="Disable Mega Evolution training option (Champions).")
    parser.add_argument("--no-tera", action="store_true", help="Disable Terastal training option (SV).")
    parser.add_argument(
        "--six-bring",
        action="store_true",
        help="Six-mon teams: first env step each episode is a 90-way bring pick for the learning side; pass --team-alpha-key / --team-beta-key with 6-mon example_teams keys (e.g. team_eileen, team_eric).",
    )
    parser.add_argument("--team-alpha-key", default="team_alpha", metavar="KEY", help="Alpha roster key in example_teams.json (must be 6-mon when --six-bring)")
    parser.add_argument("--team-beta-key", default="team_beta", metavar="KEY", help="Beta roster key (must be 6-mon when --six-bring)")
    args = parser.parse_args()

    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
    except ImportError:
        print("Install sb3-contrib stable-baselines3 torch (CPU builds): pip install sb3-contrib", file=sys.stderr)

        return 1

    from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
    from vgc_rl.doubles_obs_identity import DOUBLES_OBS_BATTLE_DIM, DOUBLES_OBS_BOOST_DIM, DOUBLES_OBS_IDENTITY_DIM, DOUBLES_OBS_TOTAL_DIM, DOUBLES_OBS_WITH_SIX_BRING_DIM
    from vgc_rl.fake_oracle_client import FakeOracleClient
    from vgc_rl.oracle_client import OracleClient
    from vgc_rl.oracle_doubles_rl_env import OracleDoublesRlEnv
    from vgc_rl.rl_policy_paths import alpha_policy_zip_filename, beta_policy_zip_filename

    game = "sv" if args.sv else "champions"
    allow_mega = not args.no_mega
    allow_tera = not args.no_tera

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

    opp_det = not args.opponent_stochastic

    alpha_path = (
        Path(args.save_alpha)
        if args.save_alpha is not None
        else Path(
            alpha_policy_zip_filename(
                alpha_team_key=str(args.team_alpha_key),
                beta_team_key=str(args.team_beta_key),
                game=game,
                six_bring=bool(args.six_bring),
            )
        )
    )
    beta_path = (
        Path(args.save_beta)
        if args.save_beta is not None
        else Path(
            beta_policy_zip_filename(
                alpha_team_key=str(args.team_alpha_key),
                beta_team_key=str(args.team_beta_key),
                game=game,
                six_bring=bool(args.six_bring),
            )
        )
    )

    print(
        f"matchup · Alpha roster={args.team_alpha_key} · Beta roster={args.team_beta_key} · game={game} · six_bring={bool(args.six_bring)} · "
        f"save_alpha={alpha_path} · save_beta={beta_path}",
        flush=True,
    )

    alpha_model = None
    beta_model = None

    obs_dim_print = DOUBLES_OBS_WITH_SIX_BRING_DIM if args.six_bring else DOUBLES_OBS_TOTAL_DIM

    print(
        f"Alternating self-play · rounds={args.alternating_rounds} · steps/phase={args.steps_per_phase} · "
        f"obs_dim={obs_dim_print} ({DOUBLES_OBS_BATTLE_DIM}+{DOUBLES_OBS_BOOST_DIM}+{DOUBLES_OBS_IDENTITY_DIM}"
        f"{'+bring' if args.six_bring else ''})",
        flush=True,
    )

    for rnd in range(args.alternating_rounds):
        beta_inner = BetaControlledOracleDoublesEnv(
            oracle=client,
            game=game,
            seed=args.seed + rnd * 97,
            alpha_policy_model=alpha_model,
            alpha_policy_deterministic=opp_det,
            allow_mega_evolution=allow_mega,
            allow_terastal=allow_tera,
            six_mon_bring=args.six_bring,
            team_alpha_key=str(args.team_alpha_key),
            team_beta_key=str(args.team_beta_key),
        )

        beta_wrapped = ActionMasker(beta_inner, action_mask_fn=lambda e: e.unwrapped.action_masks())

        if beta_model is None:
            beta_reset_ts = True
            resume_b = beta_path.is_file() and not args.fresh_start

            if resume_b:
                try:
                    beta_model = MaskablePPO.load(str(beta_path), env=beta_wrapped, device="cpu")
                    beta_model.learning_rate = args.learning_rate
                    beta_reset_ts = False

                    print(f"Round {rnd + 1} Beta: loaded {beta_path.resolve()} · num_timesteps={beta_model.num_timesteps}", flush=True)
                except Exception as exc:
                    print(f"Round {rnd + 1} Beta load failed ({beta_path}): {exc}", file=sys.stderr)
                    print("Training new Beta policy.", file=sys.stderr)

                    beta_model = MaskablePPO(
                        "MlpPolicy",
                        beta_wrapped,
                        verbose=1,
                        device="cpu",
                        seed=args.seed,
                        learning_rate=args.learning_rate,
                        n_steps=128,
                        batch_size=64,
                    )

                    beta_reset_ts = True
            else:
                if args.fresh_start and beta_path.is_file():
                    print(f"Round {rnd + 1} Beta: --fresh-start ignoring {beta_path.resolve()}", flush=True)

                print(f"Round {rnd + 1} Beta: new MaskablePPO · save → {beta_path.resolve()}", flush=True)

                beta_model = MaskablePPO(
                    "MlpPolicy",
                    beta_wrapped,
                    verbose=1,
                    device="cpu",
                    seed=args.seed,
                    learning_rate=args.learning_rate,
                    n_steps=128,
                    batch_size=64,
                )

                beta_reset_ts = True
        else:
            beta_model.set_env(beta_wrapped)
            beta_model.learning_rate = args.learning_rate
            beta_reset_ts = False

            print(f"Round {rnd + 1} Beta: continuing vs {'frozen Alpha policy' if alpha_model is not None else 'random Alpha'}", flush=True)

        beta_model.learn(total_timesteps=args.steps_per_phase, reset_num_timesteps=beta_reset_ts)
        beta_model.save(str(beta_path))

        print(f"Round {rnd + 1} Beta saved → {beta_path.resolve()}", flush=True)

        alpha_inner = OracleDoublesRlEnv(
            oracle=client,
            game=game,
            seed=args.seed + rnd * 97 + 11,
            beta_policy_model=beta_model,
            beta_policy_deterministic=opp_det,
            allow_mega_evolution=allow_mega,
            allow_terastal=allow_tera,
            six_mon_bring=args.six_bring,
            team_alpha_key=str(args.team_alpha_key),
            team_beta_key=str(args.team_beta_key),
        )

        alpha_wrapped = ActionMasker(alpha_inner, action_mask_fn=lambda e: e.unwrapped.action_masks())

        if alpha_model is None:
            alpha_reset_ts = True
            resume_a = alpha_path.is_file() and not args.fresh_start

            if resume_a:
                try:
                    alpha_model = MaskablePPO.load(str(alpha_path), env=alpha_wrapped, device="cpu")
                    alpha_model.learning_rate = args.learning_rate
                    alpha_reset_ts = False

                    print(f"Round {rnd + 1} Alpha: loaded {alpha_path.resolve()} · num_timesteps={alpha_model.num_timesteps}", flush=True)
                except Exception as exc:
                    print(f"Round {rnd + 1} Alpha load failed ({alpha_path}): {exc}", file=sys.stderr)
                    print("Training new Alpha policy.", file=sys.stderr)

                    alpha_model = MaskablePPO(
                        "MlpPolicy",
                        alpha_wrapped,
                        verbose=1,
                        device="cpu",
                        seed=args.seed + 1,
                        learning_rate=args.learning_rate,
                        n_steps=128,
                        batch_size=64,
                    )

                    alpha_reset_ts = True
            else:
                if args.fresh_start and alpha_path.is_file():
                    print(f"Round {rnd + 1} Alpha: --fresh-start ignoring {alpha_path.resolve()}", flush=True)

                print(f"Round {rnd + 1} Alpha: new MaskablePPO · save → {alpha_path.resolve()}", flush=True)

                alpha_model = MaskablePPO(
                    "MlpPolicy",
                    alpha_wrapped,
                    verbose=1,
                    device="cpu",
                    seed=args.seed + 1,
                    learning_rate=args.learning_rate,
                    n_steps=128,
                    batch_size=64,
                )

                alpha_reset_ts = True
        else:
            alpha_model.set_env(alpha_wrapped)
            alpha_model.learning_rate = args.learning_rate
            alpha_reset_ts = False

            print(f"Round {rnd + 1} Alpha: continuing vs frozen Beta policy", flush=True)

        alpha_model.learn(total_timesteps=args.steps_per_phase, reset_num_timesteps=alpha_reset_ts)
        alpha_model.save(str(alpha_path))

        print(f"Round {rnd + 1} Alpha saved → {alpha_path.resolve()}", flush=True)

    print("done:", alpha_path.resolve(), beta_path.resolve(), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
