from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from vgc_rl.doubles_actions import DEFAULT_BENCH_SLOTS
from vgc_rl.oracle_client import OracleClient, sample_raging_bolt_vs_flutter_mane_single, summarize_single_result
from vgc_rl.turn_one import parse_brought_quad, parse_field_slots


def _fresh_party_bundle(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from copy import deepcopy

    from vgc_rl.example_teams import party_member
    from vgc_rl.team_json import load_team_party, team_file_sha256

    tap = getattr(args, "team_alpha", None)
    tbp = getattr(args, "team_beta", None)

    if (tap or tbp) and not (tap and tbp):
        raise ValueError("--team-alpha and --team-beta must be supplied together.")

    if tap:
        pa_p = Path(str(tap))
        pb_p = Path(str(tbp))

        if not pa_p.is_file():
            raise ValueError(f"--team-alpha not found: {pa_p}")

        if not pb_p.is_file():
            raise ValueError(f"--team-beta not found: {pb_p}")

        _, party_a = load_team_party(pa_p)
        _, party_b = load_team_party(pb_p)

        for m in party_a + party_b:
            m["hpPercentage"] = 100

        extra = {
            "team_alpha_path": str(pa_p.resolve()),
            "team_beta_path": str(pb_p.resolve()),
            "team_alpha_id": team_file_sha256(pa_p),
            "team_beta_id": team_file_sha256(pb_p),
        }

        return party_a, party_b, extra

    party_a = [deepcopy(party_member("team_alpha", i)) for i in range(4)]
    party_b = [deepcopy(party_member("team_beta", i)) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100

    return party_a, party_b, {}


def cmd_simulate_turn_one(args: argparse.Namespace) -> int:
    from rich.console import Console

    from vgc_rl.rich_report import render_turn_simulation
    from vgc_rl.turn_one import parse_field_slots
    from vgc_rl.turn_sim import run_turn_one_demo, simulation_has_errors

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    try:
        alpha_slots = parse_field_slots(args.alpha_field)
        beta_slots = parse_field_slots(args.beta_field)
    except ValueError as exc:
        print(exc, file=sys.stderr)

        return 2

    game = "sv" if args.sv else "champions"

    console = Console()

    console.print(f"[dim]alpha_field={alpha_slots} beta_field={beta_slots} game={game} (speedContext defaulted on by oracle)[/dim]")

    turns = run_turn_one_demo(client=client, game=game, alpha_slots=alpha_slots, beta_slots=beta_slots)

    render_turn_simulation(console, turns, verbose=args.verbose)

    return 1 if simulation_has_errors(turns) else 0


def cmd_self_play(args: argparse.Namespace) -> int:
    from rich.console import Console

    from vgc_rl.self_play import run_self_play_1v1, run_self_play_doubles

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    game = "sv" if args.sv else "champions"
    console = Console()

    if args.doubles:
        try:
            alpha_party_slots = parse_field_slots(args.alpha_field)
            beta_party_slots = parse_field_slots(args.beta_field)
        except ValueError as exc:
            print(exc, file=sys.stderr)

            return 2

        for label, tup in (("--alpha-field", alpha_party_slots), ("--beta-field", beta_party_slots)):
            for idx in tup:
                if not 0 <= idx <= 3:
                    print(f"{label} party indices must be in 0..3.", file=sys.stderr)

                    return 2

        if alpha_party_slots[0] == alpha_party_slots[1] or beta_party_slots[0] == beta_party_slots[1]:
            print("--alpha-field and --beta-field must name two distinct party indices each.", file=sys.stderr)

            return 2

        if not 0.0 <= args.switch_rate <= 1.0:
            print("--switch-rate must be between 0 and 1.", file=sys.stderr)

            return 2

        return run_self_play_doubles(
            client=client,
            game=game,
            alpha_party_slots=alpha_party_slots,
            beta_party_slots=beta_party_slots,
            turns_max=args.turns,
            seed=args.seed,
            console=console,
            switch_prob=args.switch_rate,
        )

    if not 0 <= args.alpha_slot <= 3 or not 0 <= args.beta_slot <= 3:
        print("alpha-slot and beta-slot must be in 0..3.", file=sys.stderr)

        return 2

    return run_self_play_1v1(
        client=client,
        game=game,
        alpha_slot=args.alpha_slot,
        beta_slot=args.beta_slot,
        turns_max=args.turns,
        seed=args.seed,
        console=console,
    )


def cmd_example_battle(args: argparse.Namespace) -> int:
    from vgc_rl.example_teams import example_battle_batch_body, load_example_teams

    if not 0 <= args.alpha_slot <= 3 or not 0 <= args.beta_slot <= 3:
        print("alpha-slot and beta-slot must be in 0..3 (four-mon doubles party index).", file=sys.stderr)

        return 2

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    game = "sv" if args.sv else "champions"
    body = example_battle_batch_body(game=game, alpha_slot=args.alpha_slot, beta_slot=args.beta_slot, kind=args.kind)
    data = client.batch(body)
    row = data["results"][0]

    if not row.get("ok"):
        print("batch error:", row.get("error"), file=sys.stderr)

        return 1

    teams = load_example_teams()

    print("team_alpha:", teams["team_alpha"]["label"], "party_index", args.alpha_slot)
    print("team_beta:", teams["team_beta"]["label"], "party_index", args.beta_slot)
    print("mode:", args.kind)

    result = row["result"]

    if args.kind == "single":
        print("oracle summary:", summarize_single_result(result))
    else:
        for i, sub in enumerate(result):
            print(i, summarize_single_result(sub))

    return 0


def cmd_list_actions(args: argparse.Namespace) -> int:
    from vgc_rl.doubles_actions import count_actions_per_turn, enumerate_joint_actions_structural, enumerate_slot_actions_structural

    summary = count_actions_per_turn(
        move_slots=args.move_slots,
        bench_slots=args.bench_slots,
        filter_duplicate_switch_to_same_bench=not args.allow_duplicate_switch,
    )

    print(summary)

    slots = enumerate_slot_actions_structural(move_slots=args.move_slots, bench_slots=args.bench_slots)

    tail = ("...",) if len(slots) > 6 else ()

    print("slot_actions_sample:", slots[:6] + tail)

    joints = enumerate_joint_actions_structural(
        move_slots=args.move_slots,
        bench_slots=args.bench_slots,
        filter_duplicate_switch_to_same_bench=not args.allow_duplicate_switch,
    )

    print("joint_actions_first:", joints[0])
    print("joint_actions_last:", joints[-1])

    return 0


def cmd_make_doubles(args: argparse.Namespace) -> int:
    import gymnasium as gym

    from vgc_rl.doubles_env import register_vgc_envs

    register_vgc_envs()

    env = gym.make(
        "vgc_rl/VGC-Doubles-v0",
        filter_duplicate_switch_to_same_bench=not args.allow_duplicate_switch,
    )

    obs, info = env.reset()

    print("action_space:", env.action_space)
    print("reset info:", info)

    _o, _r, _term, _trunc, inf = env.step(env.action_space.sample())

    print("step info joint_action:", inf.get("joint_action"))

    env.close()

    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    client = OracleClient(base_url=args.oracle_url)

    try:
        health = client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the calculator oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    print("health:", health)

    payload = sample_raging_bolt_vs_flutter_mane_single("champions" if args.champions else "sv")
    data = client.batch(payload)
    row = data["results"][0]

    if not row.get("ok"):
        print("batch error:", row.get("error"), file=sys.stderr)

        return 1

    print("oracle summary:", summarize_single_result(row["result"]))

    return 0


def cmd_rl_env_smoke(args: argparse.Namespace) -> int:
    import numpy as np

    import gymnasium as gym

    from vgc_rl.doubles_env import register_vgc_envs

    register_vgc_envs()

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    from vgc_rl.oracle_doubles_rl_env import OracleDoublesRlEnv

    game = "sv" if args.sv else "champions"

    if getattr(args, "six_bring", False):
        env = OracleDoublesRlEnv(
            oracle=client,
            game=game,
            max_steps=max(args.steps + 8, 32),
            seed=args.seed,
            six_mon_bring=True,
            team_alpha_key=str(args.team_alpha_key),
            team_beta_key=str(args.team_beta_key),
            random_pair_bring_on_reset=bool(getattr(args, "random_pair_bring_on_reset", False)),
            debug_print_bring=bool(getattr(args, "debug_print_bring", False)),
            random_bring_alpha=bool(getattr(args, "random_bring_alpha", False)),
            random_bring_beta=bool(getattr(args, "random_bring_beta", False)),
        )
    else:
        env = gym.make(
            "vgc_rl/OracleDoubles-v0",
            oracle=client,
            game=game,
            max_steps=max(args.steps + 8, 32),
            seed=args.seed,
        )

    rng = np.random.default_rng(args.seed)

    obs, info = env.reset(seed=args.seed)

    reward = 0.0

    for _ in range(args.steps):
        mask = np.asarray(info["legal_actions_mask"], dtype=bool)
        legal = np.flatnonzero(mask)

        if legal.size == 0:
            print("no legal actions; stopping smoke")

            break

        act = int(rng.choice(legal))
        obs, reward, terminated, truncated, info = env.step(act)

        if terminated or truncated:
            print(f"episode ended: terminated={terminated} truncated={truncated} reward={reward}")

            break

    print("rl-env-smoke ok:", obs.shape, "last_reward", reward)

    env.close()

    return 0


def cmd_play_doubles(args: argparse.Namespace) -> int:
    import json
    import random

    import numpy as np

    from rich.console import Console

    from vgc_rl.doubles_action_mask import (
        decode_flat_form_action,
        legal_flat_mask_beta,
        legal_joint_mask_alpha,
        legal_joint_mask_beta,
        split_form_branch_for_game,
    )
    from vgc_rl.doubles_actions import enumerate_joint_actions_structural
    from vgc_rl.doubles_checkpoint import battle_state_from_checkpoint_dict, battle_state_to_checkpoint_dict, read_checkpoint, write_checkpoint
    from vgc_rl.doubles_turn_engine import DoublesBattleState, apply_initial_field_weather, side_party_wiped_brought
    from vgc_rl.interactive_doubles import (
        doubles_obs_vector,
        format_joint_human_summary,
        legal_joint_indices,
        prompt_joint_human_side,
        sample_beta_joint_index,
        step_turn,
        trajectory_row,
    )
    from vgc_rl.rich_report import print_showdown_line, render_self_play_doubles_snapshot

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    console = Console()
    joints = enumerate_joint_actions_structural()
    mode_human_human = args.two_player or args.mode == "human-human"

    if args.beta_policy and mode_human_human:
        print("--beta-policy cannot be combined with --two-player / --mode human-human.", file=sys.stderr)

        return 2

    beta_model = None

    if args.beta_policy:
        pth = Path(args.beta_policy)

        if not pth.is_file():
            print(f"--beta-policy file not found: {pth}", file=sys.stderr)

            return 2

        from vgc_rl.sb3_masked_policy import load_maskable_ppo, predict_masked_joint_index

        beta_model = load_maskable_ppo(str(pth), device="cpu")

    trajectory_fp = None

    if args.log_trajectory:
        trajectory_fp = open(args.log_trajectory, "a", encoding="utf-8")

    try:
        load_path: str | None = args.load_checkpoint

        if load_path is None and args.save_checkpoint and not args.fresh_start:
            save_p = Path(args.save_checkpoint)

            if save_p.is_file():
                load_path = str(save_p.resolve())

        if load_path is not None:
            raw = read_checkpoint(load_path)
            battle, game, seed_ckpt, step_count = battle_state_from_checkpoint_dict(raw)
            session_seed = seed_ckpt if seed_ckpt is not None else args.seed
            rng = random.Random(session_seed)
        else:
            game = "sv" if args.sv else "champions"

            try:
                party_a, party_b, team_kw = _fresh_party_bundle(args)
            except ValueError as exc:
                print(exc, file=sys.stderr)

                return 2

            try:
                alpha_party_slots = parse_field_slots(args.alpha_field)
                beta_party_slots = parse_field_slots(args.beta_field)
            except ValueError as exc:
                print(exc, file=sys.stderr)

                return 2

            na = len(party_a)
            nb = len(party_b)

            abspec = getattr(args, "alpha_brought", None)
            bbspec = getattr(args, "beta_brought", None)

            if abspec is not None and na != 6:
                print("--alpha-brought requires Alpha party length 6.", file=sys.stderr)

                return 2

            if bbspec is not None and nb != 6:
                print("--beta-brought requires Beta party length 6.", file=sys.stderr)

                return 2

            brought_a_kw: tuple[int, int, int, int] | None

            if abspec is None:
                brought_a_kw = None
            else:
                try:
                    brought_a_kw = parse_brought_quad(abspec)
                except ValueError as exc:
                    print(exc, file=sys.stderr)

                    return 2

            brought_b_kw: tuple[int, int, int, int] | None

            if bbspec is None:
                brought_b_kw = None
            else:
                try:
                    brought_b_kw = parse_brought_quad(bbspec)
                except ValueError as exc:
                    print(exc, file=sys.stderr)

                    return 2

            for label, tup, lim in (
                ("--alpha-field", alpha_party_slots, na),
                ("--beta-field", beta_party_slots, nb),
            ):
                for idx in tup:
                    if not 0 <= idx < lim:
                        print(f"{label} party indices must be in 0..{lim - 1}.", file=sys.stderr)

                        return 2

            if alpha_party_slots[0] == alpha_party_slots[1] or beta_party_slots[0] == beta_party_slots[1]:
                print("--alpha-field and --beta-field must name two distinct party indices each.", file=sys.stderr)

                return 2

            leads_a = list(alpha_party_slots)
            leads_b = list(beta_party_slots)

            battle = DoublesBattleState(
                party_a=party_a,
                party_b=party_b,
                leads_a=leads_a,
                leads_b=leads_b,
                brought_a=brought_a_kw,
                brought_b=brought_b_kw,
                **team_kw,
            )

            ba = battle.brought_alpha_sorted()
            bb = battle.brought_beta_sorted()

            if any(i not in ba for i in leads_a):
                print(f"Alpha leads must be contained in brought roster {ba}.", file=sys.stderr)

                return 2

            if any(i not in bb for i in leads_b):
                print(f"Beta leads must be contained in brought roster {bb}.", file=sys.stderr)

                return 2

            apply_initial_field_weather(battle)
            session_seed = args.seed
            rng = random.Random(session_seed)
            step_count = 0

        mode_desc = "two-player (human Alpha · human Beta)"

        if not mode_human_human:
            mode_desc = "human Alpha vs SB3 Beta policy" if beta_model is not None else "human Alpha vs random legal Beta"

        console.print(f"[bold]Interactive doubles[/bold] — {mode_desc} · game={game}")

        if load_path is not None:
            via = " (--load-checkpoint)" if args.load_checkpoint is not None else " (--save path)"

            console.print(
                f"[bold cyan]Checkpoint restart[/bold cyan]{via}: [bold]{load_path}[/bold] · "
                f"step_count={step_count} · seed={session_seed}",
            )

        sessions_turns = 0

        try:
            while sessions_turns < args.max_turns:
                if side_party_wiped_brought(battle, alpha=True):
                    console.print("[bold]Alpha party wiped[/bold] — Beta wins.")

                    return 0

                if side_party_wiped_brought(battle, alpha=False):
                    console.print("[bold]Beta party wiped[/bold] — Alpha wins.")

                    return 0

                render_self_play_doubles_snapshot(
                    console,
                    turn_heading=f"Turn {step_count + 1} · field state",
                    party_alpha=battle.party_a,
                    party_beta=battle.party_b,
                    leads_alpha=(battle.leads_a[0], battle.leads_a[1]),
                    leads_beta=(battle.leads_b[0], battle.leads_b[1]),
                )

                console.rule("[dim]Battle log[/dim]")

                wthr = battle.weather or "—"
                wtau = int(battle.weather_turns_left) if battle.weather else 0

                print_showdown_line(
                    console,
                    "field",
                    f"weather={wthr} (τ={wtau}) terrain=— alphaTailwind={'yes' if battle.alpha_tailwind_turns_left > 0 else 'no'} "
                    f"betaTailwind={'yes' if battle.beta_tailwind_turns_left > 0 else 'no'} "
                    f"τ_rem α={battle.alpha_tailwind_turns_left} β={battle.beta_tailwind_turns_left}",
                )

                ma = legal_joint_mask_alpha(battle, joints)
                mb = legal_joint_mask_beta(battle, joints)
                mfb = legal_flat_mask_beta(battle, joints, game=game)

                obs_before = doubles_obs_vector(battle, game=game)
                legal_a = legal_joint_indices(ma).tolist()
                legal_b = legal_joint_indices(mb).tolist()

                if beta_model is not None:
                    legal_b = np.flatnonzero(mfb).tolist()

                if not np.any(ma):
                    console.print("[bold]Alpha has no legal joint actions[/bold] — Beta wins.")

                    return 0

                if beta_model is None:
                    beta_has_legal = np.any(mb)
                else:
                    beta_has_legal = np.any(mfb)

                if not beta_has_legal:
                    console.print("[bold]Beta has no legal joint actions[/bold] — Alpha wins.")

                    return 0

                idx_a = prompt_joint_human_side(
                    mask=ma,
                    joints=joints,
                    party=battle.party_a,
                    leads=battle.leads_a,
                    brought=battle.brought_alpha_sorted(),
                    trainer_heading="Alpha",
                    input_fn=input,
                    foe_party=battle.party_b,
                    foe_leads=battle.leads_b,
                )

                mega_alpha = 0
                tera_alpha = 0
                mega_beta = 0
                tera_beta = 0

                if mode_human_human:
                    idx_b = prompt_joint_human_side(
                        mask=mb,
                        joints=joints,
                        party=battle.party_b,
                        leads=battle.leads_b,
                        brought=battle.brought_beta_sorted(),
                        trainer_heading="Beta",
                        input_fn=input,
                        foe_party=battle.party_a,
                        foe_leads=battle.leads_a,
                    )
                elif beta_model is not None:
                    flat_b = int(
                        predict_masked_joint_index(
                            beta_model,
                            obs_before,
                            mfb,
                            deterministic=not args.beta_stochastic,
                        )
                    )
                    branch_b, idx_b = decode_flat_form_action(flat_b, len(joints))
                    mega_beta, tera_beta = split_form_branch_for_game(branch_b, game)

                    jb_preview = joints[idx_b]

                    console.print(
                        f"[dim]Beta policy: flat#{flat_b} joint#{idx_b} "
                        f"{format_joint_human_summary(jb_preview, battle.party_b, battle.leads_b, foe_party=battle.party_a, foe_leads=battle.leads_a, brought=battle.brought_beta_sorted())}[/dim]",
                    )
                else:
                    idx_b = sample_beta_joint_index(rng, mb)
                    jb_preview = joints[idx_b]

                    console.print(
                        f"[dim]Beta random legal: joint#{idx_b} "
                        f"{format_joint_human_summary(jb_preview, battle.party_b, battle.leads_b, foe_party=battle.party_a, foe_leads=battle.leads_a, brought=battle.brought_beta_sorted())}[/dim]",
                    )

                ja = joints[idx_a]
                jb = joints[idx_b]

                label_a = format_joint_human_summary(
                    ja,
                    battle.party_a,
                    battle.leads_a,
                    foe_party=battle.party_b,
                    foe_leads=battle.leads_b,
                    brought=battle.brought_alpha_sorted(),
                )
                label_b = format_joint_human_summary(
                    jb,
                    battle.party_b,
                    battle.leads_b,
                    foe_party=battle.party_a,
                    foe_leads=battle.leads_a,
                    brought=battle.brought_beta_sorted(),
                )

                try:
                    reward, terminated, events, _debug = step_turn(
                        battle,
                        rng,
                        client,
                        game,
                        idx_a,
                        idx_b,
                        joints,
                        mega_alpha=mega_alpha,
                        mega_beta=mega_beta,
                        tera_alpha=tera_alpha,
                        tera_beta=tera_beta,
                    )
                except RuntimeError as exc:
                    print_showdown_line(console, "error", str(exc))

                    return 1

                for tag, body in events:
                    print_showdown_line(console, tag, body)

                sessions_turns += 1
                step_count += 1

                if trajectory_fp is not None:
                    row = trajectory_row(
                        obs_before=obs_before,
                        legal_alpha_indices=legal_a,
                        legal_beta_indices=legal_b,
                        joint_idx_alpha=idx_a,
                        joint_idx_beta=idx_b,
                        joint_label_alpha=label_a,
                        joint_label_beta=label_b,
                        reward=float(reward),
                        terminated=bool(terminated),
                        step_index=step_count - 1,
                    )

                    trajectory_fp.write(json.dumps(row) + "\n")
                    trajectory_fp.flush()

                if args.save_checkpoint:
                    payload = battle_state_to_checkpoint_dict(battle, game=game, seed=session_seed, step_count=step_count)

                    write_checkpoint(args.save_checkpoint, payload)

                if terminated:
                    console.print(f"[bold]Terminated[/bold] reward={reward}")

                    return 0

                console.print()

            console.print("[yellow]Session max turns reached[/yellow]")

            return 0
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")

            if args.save_checkpoint:
                payload = battle_state_to_checkpoint_dict(battle, game=game, seed=session_seed, step_count=step_count)

                write_checkpoint(args.save_checkpoint, payload)

            return 130
    finally:
        if trajectory_fp is not None:
            trajectory_fp.close()


def cmd_showcase_doubles(args: argparse.Namespace) -> int:
    import random
    import time

    import numpy as np

    from rich.console import Console

    from vgc_rl.bring_selection import BRING_ACTION_SPACE_SIZE
    from vgc_rl.doubles_action_mask import (
        FORM_ACTION_BRANCHES,
        decode_flat_form_action,
        legal_flat_mask_alpha,
        legal_flat_mask_beta,
        split_form_branch_for_game,
    )
    from vgc_rl.doubles_actions import enumerate_joint_actions_structural
    from vgc_rl.doubles_turn_engine import DoublesBattleState, apply_initial_field_weather, side_party_wiped_brought
    from vgc_rl.interactive_doubles import doubles_obs_vector, doubles_rl_six_bring_observation, format_joint_human_summary, sample_random_legal_flat_index, step_turn
    from vgc_rl.rich_report import print_showdown_line, render_self_play_doubles_snapshot

    client = OracleClient(base_url=args.oracle_url)

    try:
        client.health()
    except Exception as exc:
        print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
        print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

        return 1

    if args.alpha_policy or args.beta_policy:
        from vgc_rl.sb3_masked_policy import load_maskable_ppo, predict_masked_joint_index

    alpha_model = None

    if args.alpha_policy:
        pth = Path(args.alpha_policy)

        if not pth.is_file():
            print(f"--alpha-policy file not found: {pth}", file=sys.stderr)

            return 2

        alpha_model = load_maskable_ppo(str(pth), device="cpu")

    beta_model = None

    if args.beta_policy:
        pth = Path(args.beta_policy)

        if not pth.is_file():
            print(f"--beta-policy file not found: {pth}", file=sys.stderr)

            return 2

        beta_model = load_maskable_ppo(str(pth), device="cpu")

    if args.seed is not None:
        s = int(args.seed)
        np.random.seed(s)
        try:
            import torch

            torch.manual_seed(s)
        except ImportError:
            pass
        for _m in (alpha_model, beta_model):
            if _m is not None and hasattr(_m, "set_random_seed"):
                _m.set_random_seed(s)

    greedy_side = getattr(args, "vs_greedy", None)

    if greedy_side:
        if alpha_model is None and beta_model is None:
            print("--vs-greedy requires --alpha-policy and/or --beta-policy.", file=sys.stderr)

            return 2

        if beta_model is None:
            beta_model = alpha_model

        if alpha_model is None:
            alpha_model = beta_model

    game = "sv" if args.sv else "champions"
    six_bring = bool(getattr(args, "six_bring", False))

    rng = random.Random(0 if args.seed is None else int(args.seed))
    joints = enumerate_joint_actions_structural()
    n_battle_flat = len(joints) * FORM_ACTION_BRANCHES

    team_kw: dict[str, Any] = {}

    if six_bring:
        from copy import deepcopy

        from vgc_rl.bring_selection import battle_state_from_bring_actions
        from vgc_rl.example_teams import load_example_teams, party_member

        tap = getattr(args, "team_alpha", None)
        tbp = getattr(args, "team_beta", None)

        if tap and tbp:
            try:
                party_a, party_b, team_kw = _fresh_party_bundle(args)
            except ValueError as exc:
                print(exc, file=sys.stderr)

                return 2
        else:
            tak = str(getattr(args, "team_alpha_key", "team_eileen"))
            tbk = str(getattr(args, "team_beta_key", "team_eric"))
            data = load_example_teams()

            if tak not in data or tbk not in data:
                print(f"--six-bring: unknown team key in example_teams: {tak!r} {tbk!r}", file=sys.stderr)

                return 2

            party_a = [deepcopy(party_member(tak, i)) for i in range(6)]
            party_b = [deepcopy(party_member(tbk, i)) for i in range(6)]

        if len(party_a) != 6 or len(party_b) != 6:
            print("--six-bring requires both parties to have length 6 (use example team keys or two JSON paths with six Pokémon each).", file=sys.stderr)

            return 2

        for m in party_a + party_b:
            m["hpPercentage"] = 100.0

        obs_bring = doubles_rl_six_bring_observation(
            None,
            party_a_full=party_a,
            party_b_full=party_b,
            game=game,
            bring_phase=True,
            allow_mega_evolution=True,
            allow_terastal=True,
        )
        mask_bring = np.zeros(BRING_ACTION_SPACE_SIZE + n_battle_flat, dtype=np.bool_)
        mask_bring[:BRING_ACTION_SPACE_SIZE] = True

        def pick_bring_action(model, *, det: bool) -> int:
            if model is None:
                return int(rng.randrange(BRING_ACTION_SPACE_SIZE))

            flat = int(predict_masked_joint_index(model, obs_bring, mask_bring, deterministic=det))

            if 0 <= flat < BRING_ACTION_SPACE_SIZE:
                return flat

            return int(rng.randrange(BRING_ACTION_SPACE_SIZE))

        if greedy_side:
            alpha_bring_det = greedy_side == "alpha"
            beta_bring_det = greedy_side == "beta"
        else:
            alpha_bring_det = not args.alpha_stochastic
            beta_bring_det = not args.beta_stochastic

        alpha_bring = pick_bring_action(alpha_model, det=alpha_bring_det)
        beta_bring = pick_bring_action(beta_model, det=beta_bring_det)

        battle = battle_state_from_bring_actions(party_a, party_b, alpha_bring, beta_bring, team_kw=team_kw or None)

        apply_initial_field_weather(battle)
    else:
        try:
            party_a, party_b, team_kw = _fresh_party_bundle(args)
        except ValueError as exc:
            print(exc, file=sys.stderr)

            return 2

        try:
            alpha_party_slots = parse_field_slots(args.alpha_field)
            beta_party_slots = parse_field_slots(args.beta_field)
        except ValueError as exc:
            print(exc, file=sys.stderr)

            return 2

        na = len(party_a)
        nb = len(party_b)

        abspec = getattr(args, "alpha_brought", None)
        bbspec = getattr(args, "beta_brought", None)

        if abspec is not None and na != 6:
            print("--alpha-brought requires Alpha party length 6.", file=sys.stderr)

            return 2

        if bbspec is not None and nb != 6:
            print("--beta-brought requires Beta party length 6.", file=sys.stderr)

            return 2

        brought_a_kw: tuple[int, int, int, int] | None

        if abspec is None:
            brought_a_kw = None
        else:
            try:
                brought_a_kw = parse_brought_quad(abspec)
            except ValueError as exc:
                print(exc, file=sys.stderr)

                return 2

        brought_b_kw: tuple[int, int, int, int] | None

        if bbspec is None:
            brought_b_kw = None
        else:
            try:
                brought_b_kw = parse_brought_quad(bbspec)
            except ValueError as exc:
                print(exc, file=sys.stderr)

                return 2

        for label, tup, lim in (
            ("--alpha-field", alpha_party_slots, na),
            ("--beta-field", beta_party_slots, nb),
        ):
            for idx in tup:
                if not 0 <= idx < lim:
                    print(f"{label} party indices must be in 0..{lim - 1}.", file=sys.stderr)

                    return 2

        if alpha_party_slots[0] == alpha_party_slots[1] or beta_party_slots[0] == beta_party_slots[1]:
            print("--alpha-field and --beta-field must name two distinct party indices each.", file=sys.stderr)

            return 2

        battle = DoublesBattleState(
            party_a=party_a,
            party_b=party_b,
            leads_a=list(alpha_party_slots),
            leads_b=list(beta_party_slots),
            brought_a=brought_a_kw,
            brought_b=brought_b_kw,
            **team_kw,
        )

        ba = battle.brought_alpha_sorted()
        bb = battle.brought_beta_sorted()

        if any(i not in ba for i in battle.leads_a):
            print(f"Alpha leads must be contained in brought roster {ba}.", file=sys.stderr)

            return 2

        if any(i not in bb for i in battle.leads_b):
            print(f"Beta leads must be contained in brought roster {bb}.", file=sys.stderr)

            return 2

        apply_initial_field_weather(battle)

    console = Console()
    mode_bits = []

    if six_bring:
        mode_bits.append("six-bring")

    if greedy_side:
        if greedy_side == "beta":
            mode_bits.append("vs greedy · Beta deterministic · Alpha stochastic")
        else:
            mode_bits.append("vs greedy · Alpha deterministic · Beta stochastic")

        if beta_model is alpha_model:
            mode_bits.append("same checkpoint · both seats")
    else:
        if alpha_model is None:
            mode_bits.append("Alpha random legal")

        else:
            mode_bits.append("Alpha MaskablePPO")

        if beta_model is None:
            mode_bits.append("Beta random legal")

        else:
            mode_bits.append("Beta MaskablePPO")

    console.print(f"[bold]Showcase doubles[/bold] — {' · '.join(mode_bits)} · game={game}")

    if six_bring:
        console.print(f"[dim]Bring phase · alpha_bring_action={alpha_bring} · beta_bring_action={beta_bring}[/dim]")

    if greedy_side and (args.alpha_stochastic or args.beta_stochastic):
        console.print("[dim]Note: --vs-greedy overrides --alpha-stochastic / --beta-stochastic[/dim]")

    step_count = 0

    for _ in range(args.turns):
        if side_party_wiped_brought(battle, alpha=True):
            console.print("[bold]Alpha party wiped[/bold] — Beta wins.")

            return 0

        if side_party_wiped_brought(battle, alpha=False):
            console.print("[bold]Beta party wiped[/bold] — Alpha wins.")

            return 0

        render_self_play_doubles_snapshot(
            console,
            turn_heading=f"Turn {step_count + 1} · field state",
            party_alpha=battle.party_a,
            party_beta=battle.party_b,
            leads_alpha=(battle.leads_a[0], battle.leads_a[1]),
            leads_beta=(battle.leads_b[0], battle.leads_b[1]),
        )

        console.rule("[dim]Battle log[/dim]")

        wthr = battle.weather or "—"
        wtau = int(battle.weather_turns_left) if battle.weather else 0

        print_showdown_line(
            console,
            "field",
            f"weather={wthr} (τ={wtau}) terrain=— alphaTailwind={'yes' if battle.alpha_tailwind_turns_left > 0 else 'no'} "
            f"betaTailwind={'yes' if battle.beta_tailwind_turns_left > 0 else 'no'} "
            f"τ_rem α={battle.alpha_tailwind_turns_left} β={battle.beta_tailwind_turns_left}",
        )

        mfa = legal_flat_mask_alpha(battle, joints, game=game)
        mfb = legal_flat_mask_beta(battle, joints, game=game)

        if not np.any(mfa):
            console.print("[bold]Alpha has no legal joint actions[/bold] — Beta wins.")

            return 0

        if not np.any(mfb):
            console.print("[bold]Beta has no legal joint actions[/bold] — Alpha wins.")

            return 0

        if six_bring:
            obs_before = doubles_rl_six_bring_observation(
                battle,
                party_a_full=battle.party_a,
                party_b_full=battle.party_b,
                game=game,
                bring_phase=False,
                allow_mega_evolution=True,
                allow_terastal=True,
            )
            mfa_ext = np.concatenate([np.zeros(BRING_ACTION_SPACE_SIZE, dtype=np.bool_), np.asarray(mfa, dtype=np.bool_)])
            mfb_ext = np.concatenate([np.zeros(BRING_ACTION_SPACE_SIZE, dtype=np.bool_), np.asarray(mfb, dtype=np.bool_)])
        else:
            obs_before = doubles_obs_vector(battle, game=game)
            mfa_ext = np.asarray(mfa, dtype=np.bool_)
            mfb_ext = np.asarray(mfb, dtype=np.bool_)

        def _normalize_battle_flat(raw: int, legal_battle: np.ndarray) -> int:
            if not six_bring:
                return raw

            if raw >= BRING_ACTION_SPACE_SIZE:
                bf = raw - BRING_ACTION_SPACE_SIZE

                if bf < len(legal_battle) and bool(legal_battle[bf]):
                    return bf

            legal_only = np.flatnonzero(np.asarray(legal_battle, dtype=bool))

            return int(rng.choice(legal_only))

        if greedy_side:
            alpha_deterministic = greedy_side == "alpha"
            beta_deterministic = greedy_side == "beta"
            raw_a = int(predict_masked_joint_index(alpha_model, obs_before, mfa_ext, deterministic=alpha_deterministic))
            raw_b = int(predict_masked_joint_index(beta_model, obs_before, mfb_ext, deterministic=beta_deterministic))
            flat_a = _normalize_battle_flat(raw_a, mfa)
            flat_b = _normalize_battle_flat(raw_b, mfb)
        elif alpha_model is None:
            flat_a = sample_random_legal_flat_index(rng, mfa)
        else:
            raw_a = int(predict_masked_joint_index(alpha_model, obs_before, mfa_ext, deterministic=not args.alpha_stochastic))
            flat_a = _normalize_battle_flat(raw_a, mfa)

        if not greedy_side:
            if beta_model is None:
                flat_b = sample_random_legal_flat_index(rng, mfb)
            else:
                raw_b = int(predict_masked_joint_index(beta_model, obs_before, mfb_ext, deterministic=not args.beta_stochastic))
                flat_b = _normalize_battle_flat(raw_b, mfb)

        branch_a, idx_a = decode_flat_form_action(flat_a, len(joints))
        branch_b, idx_b = decode_flat_form_action(flat_b, len(joints))
        mega_alpha, tera_alpha = split_form_branch_for_game(branch_a, game)
        mega_beta, tera_beta = split_form_branch_for_game(branch_b, game)

        ja = joints[idx_a]
        jb = joints[idx_b]

        console.print(
            f"[dim]Alpha: flat#{flat_a} joint#{idx_a} "
            f"{format_joint_human_summary(ja, battle.party_a, battle.leads_a, foe_party=battle.party_b, foe_leads=battle.leads_b, brought=battle.brought_alpha_sorted())}[/dim]",
        )
        console.print(
            f"[dim]Beta: flat#{flat_b} joint#{idx_b} "
            f"{format_joint_human_summary(jb, battle.party_b, battle.leads_b, foe_party=battle.party_a, foe_leads=battle.leads_a, brought=battle.brought_beta_sorted())}[/dim]",
        )

        try:
            reward, terminated, events, _debug = step_turn(
                battle,
                rng,
                client,
                game,
                idx_a,
                idx_b,
                joints,
                mega_alpha=mega_alpha,
                mega_beta=mega_beta,
                tera_alpha=tera_alpha,
                tera_beta=tera_beta,
            )
        except RuntimeError as exc:
            print_showdown_line(console, "error", str(exc))

            return 1

        for tag, body in events:
            print_showdown_line(console, tag, body)

        step_count += 1

        if terminated:
            console.print(f"[bold]Terminated[/bold] reward={reward}")

            return 0

        if args.delay > 0:
            time.sleep(args.delay)

        console.print()

    console.print("[yellow]Showcase max turns reached[/yellow]")

    return 0


def cmd_bring_eval(args: argparse.Namespace) -> int:
    import random
    from copy import deepcopy

    import numpy as np

    from vgc_rl.bring_selection import score_alpha_brings_vs_random_opponent
    from vgc_rl.example_teams import load_example_teams
    from vgc_rl.fake_oracle_client import FakeOracleClient

    ta = str(args.team_alpha_key)
    tb = str(args.team_beta_key)
    data = load_example_teams()

    if ta not in data or not isinstance(data.get(ta), dict) or not isinstance(data[ta].get("party"), list):
        print(f"unknown team key or missing party: {ta}", file=sys.stderr)

        return 2

    if tb not in data or not isinstance(data.get(tb), dict) or not isinstance(data[tb].get("party"), list):
        print(f"unknown team key or missing party: {tb}", file=sys.stderr)

        return 2

    party_a = deepcopy(data[ta]["party"])
    party_b = deepcopy(data[tb]["party"])

    if len(party_a) != 6 or len(party_b) != 6:
        print("bring-eval expects registered parties of length 6 for both keys", file=sys.stderr)

        return 2

    game = "sv" if args.sv else "champions"

    if args.fake_oracle:
        client: FakeOracleClient | OracleClient = FakeOracleClient()
    else:
        client = OracleClient(base_url=args.oracle_url)

        try:
            client.health()
        except Exception as exc:
            print(f"Oracle health check failed ({client.base_url}): {exc}", file=sys.stderr)
            print("Start the oracle first: cd oracle-server && npm install && npm start", file=sys.stderr)

            return 1

    rng = random.Random(0 if args.seed is None else int(args.seed))
    scores = score_alpha_brings_vs_random_opponent(
        party_a,
        party_b,
        client,
        game=game,
        rng=rng,
        opponent_samples=int(args.opponent_samples),
        rolls_per_pair=int(args.rolls),
        max_turns=int(args.max_turns),
    )

    best_i = int(np.argmax(scores))

    print(
        f"team_alpha_key={ta} team_beta_key={tb} game={game} "
        f"opponent_samples={int(args.opponent_samples)} rolls_per_pair={int(args.rolls)} "
        f"best_alpha_action={best_i} mean_payoff={scores[best_i]:.6f}",
    )

    return 0


def cmd_demo_env(args: argparse.Namespace) -> int:
    from vgc_rl.env import OracleFeatureToyEnv

    game = "champions" if args.champions else "sv"
    env = OracleFeatureToyEnv(oracle=OracleClient(base_url=args.oracle_url), game=game)
    obs, info = env.reset()

    print("obs:", obs.tolist())
    print("info keys:", list(info.keys()))

    return 0


def cmd_battle_sim(args: argparse.Namespace) -> int:
    try:
        from sb3_contrib import MaskablePPO
    except ImportError:
        print("Install sb3-contrib stable-baselines3 torch (CPU builds): pip install sb3-contrib", file=sys.stderr)

        return 1

    from vgc_rl.beta_oracle_env import BetaControlledOracleDoublesEnv
    from vgc_rl.fake_oracle_client import FakeOracleClient
    from vgc_rl.oracle_client import OracleClient

    if args.swap_seats and not args.alpha_policy:
        print("--swap-seats requires --alpha-policy (two checkpoints).", file=sys.stderr)

        return 2

    beta_path = Path(args.beta_policy)

    if not beta_path.is_file():
        print(f"--beta-policy not found: {beta_path}", file=sys.stderr)

        return 2

    alpha_ckpt_model = None

    if args.alpha_policy:
        ap = Path(args.alpha_policy)

        if not ap.is_file():
            print(f"--alpha-policy not found: {ap}", file=sys.stderr)

            return 2

        try:
            alpha_ckpt_model = MaskablePPO.load(str(ap), device="cpu")
        except Exception as exc:
            print(f"Failed to load Alpha MaskablePPO ({ap}): {exc}", file=sys.stderr)

            return 1

    game = "sv" if args.sv else "champions"

    try:
        alpha_party_slots = parse_field_slots(args.alpha_field)
        beta_party_slots = parse_field_slots(args.beta_field)
    except ValueError as exc:
        print(exc, file=sys.stderr)

        return 2

    for label, tup in (("--alpha-field", alpha_party_slots), ("--beta-field", beta_party_slots)):
        for idx in tup:
            if not 0 <= idx <= 3:
                print(f"{label} party indices must be in 0..3.", file=sys.stderr)

                return 2

    if alpha_party_slots[0] == alpha_party_slots[1] or beta_party_slots[0] == beta_party_slots[1]:
        print("--alpha-field and --beta-field must name two distinct party indices each.", file=sys.stderr)

        return 2

    if args.fake_oracle:
        client = FakeOracleClient()
    else:
        client = OracleClient(base_url=args.oracle_url)

        try:
            client.health()
        except Exception as exc:
            print(f"Oracle health failed ({client.base_url}): {exc}", file=sys.stderr)

            return 1

    allow_mega = not args.no_mega
    allow_tera = not args.no_tera

    alpha_party_tuple = tuple(alpha_party_slots)
    beta_party_tuple = tuple(beta_party_slots)
    internal_alpha_deterministic = not args.alpha_stochastic

    def make_env(internal_alpha: MaskablePPO | None) -> BetaControlledOracleDoublesEnv:
        return BetaControlledOracleDoublesEnv(
            oracle=client,
            game=game,
            seed=0,
            alpha_field=alpha_party_tuple,
            beta_field=beta_party_tuple,
            alpha_policy_model=internal_alpha,
            alpha_policy_deterministic=internal_alpha_deterministic,
            allow_mega_evolution=allow_mega,
            allow_terastal=allow_tera,
        )

    try:
        beta_ckpt_model = MaskablePPO.load(str(beta_path), device="cpu")
    except Exception as exc:
        print(f"Failed to load Beta MaskablePPO ({beta_path}): {exc}", file=sys.stderr)

        return 1

    def run_beta_external_batch(
        env: BetaControlledOracleDoublesEnv,
        external_beta: MaskablePPO,
        external_deterministic: bool,
        *,
        episodes: int,
        seed_base: int,
    ) -> tuple[int, int, int, int]:
        beta_party_wins = 0
        alpha_party_wins = 0
        draws = 0
        truncs = 0

        for ep in range(episodes):
            obs, _info = env.reset(seed=seed_base + ep)

            terminated = False
            truncated = False

            while not (terminated or truncated):
                mask = env.action_masks()
                act, _ = external_beta.predict(obs, deterministic=external_deterministic, action_masks=mask)
                obs, reward, terminated, truncated, _info2 = env.step(int(act))

            if truncated and not terminated:
                truncs += 1

                continue

            if terminated:
                if reward > 1e-6:
                    beta_party_wins += 1
                elif reward < -1e-6:
                    alpha_party_wins += 1
                else:
                    draws += 1

        return beta_party_wins, alpha_party_wins, draws, truncs

    def run_modes_no_swap(mode_specs: list[tuple[str, bool]]) -> None:
        rows: list[tuple[str, int, int, int, int]] = []

        for label, beta_det in mode_specs:
            env = make_env(alpha_ckpt_model)

            try:
                bw, aw, dr, tr = run_beta_external_batch(
                    env,
                    beta_ckpt_model,
                    beta_det,
                    episodes=args.episodes,
                    seed_base=args.seed,
                )
            finally:
                env.close()

            rows.append((label, bw, aw, dr, tr))

        alpha_lab = "random flat legal"

        if alpha_ckpt_model is not None:
            alpha_lab = "frozen Alpha policy (" + ("greedy" if internal_alpha_deterministic else "stochastic") + ")"

        print(
            f"battle-sim · episodes={args.episodes} · seed={args.seed} · game={game} · "
            f"Alpha={alpha_lab} · fake_oracle={bool(args.fake_oracle)}",
            flush=True,
        )

        w = max(len(r[0]) for r in rows)

        print(f"{'Beta inference':<{w}}  β_party  α_party  draw  trunc", flush=True)

        for label, bw, aw, dr, tr in rows:
            print(f"{label:<{w}}  {bw:7d}  {aw:7d}  {dr:4d}  {tr:5d}", flush=True)

    def run_modes_swap(mode_specs: list[tuple[str, bool]]) -> None:
        assert alpha_ckpt_model is not None

        beta_name = beta_path.name
        alpha_name = Path(args.alpha_policy).name

        print(
            f"battle-sim · swap-seats · episodes per assignment={args.episodes} · total games={2 * args.episodes} · "
            f"seed={args.seed} · game={game} · fake_oracle={bool(args.fake_oracle)}",
            flush=True,
        )

        for label, beta_det in mode_specs:
            env_default = make_env(alpha_ckpt_model)

            try:
                bw_d, aw_d, dr_d, tr_d = run_beta_external_batch(
                    env_default,
                    beta_ckpt_model,
                    beta_det,
                    episodes=args.episodes,
                    seed_base=args.seed,
                )
            finally:
                env_default.close()

            env_swapped = make_env(beta_ckpt_model)

            try:
                bw_s, aw_s, dr_s, tr_s = run_beta_external_batch(
                    env_swapped,
                    alpha_ckpt_model,
                    beta_det,
                    episodes=args.episodes,
                    seed_base=args.seed + args.episodes,
                )
            finally:
                env_swapped.close()

            beta_ckpt_wins = bw_d + aw_s
            alpha_ckpt_wins = aw_d + bw_s
            draws_tot = dr_d + dr_s
            truncs_tot = tr_d + tr_s

            print(f"\nBeta inference: {label}", flush=True)
            print(f"  default seats   Beta←{beta_name} · Alpha←{alpha_name}", flush=True)
            print(f"    β_party {bw_d:5d}  α_party {aw_d:5d}  draw {dr_d:4d}  trunc {tr_d:5d}", flush=True)
            print(f"  swapped seats   Beta←{alpha_name} · Alpha←{beta_name}", flush=True)
            print(f"    β_party {bw_s:5d}  α_party {aw_s:5d}  draw {dr_s:4d}  trunc {tr_s:5d}", flush=True)
            print("  checkpoint totals (seat-averaged)", flush=True)
            print(
                f"    {beta_name} wins {beta_ckpt_wins:5d} · {alpha_name} wins {alpha_ckpt_wins:5d} · "
                f"draws {draws_tot} · trunc {truncs_tot}",
                flush=True,
            )

    if args.swap_seats:
        mode_specs = (
            [("stochastic (trained sampling)", False), ("greedy (deterministic)", True)]
            if args.single is None
            else [("stochastic (trained sampling)", False)]
            if args.single == "trained"
            else [("greedy (deterministic)", True)]
        )

        run_modes_swap(mode_specs)
    else:
        mode_specs = (
            [("stochastic (trained sampling)", False), ("greedy (deterministic)", True)]
            if args.single is None
            else [("stochastic (trained sampling)", False)]
            if args.single == "trained"
            else [("greedy (deterministic)", True)]
        )

        run_modes_no_swap(mode_specs)

    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vgc-rl")
    parser.add_argument("--oracle-url", default=os.environ.get("ORACLE_URL"), help="Base URL for oracle-server (default ORACLE_URL or http://127.0.0.1:8765)")

    sub = parser.add_subparsers(dest="command", required=True)

    p_smoke = sub.add_parser("smoke", help="GET /health and POST /batch sample matchup")
    p_smoke.add_argument("--champions", action="store_true")
    p_smoke.set_defaults(func=cmd_smoke)

    p_demo = sub.add_parser("demo-env", help="Gymnasium OracleFeatureToyEnv reset against live oracle")
    p_demo.add_argument("--champions", action="store_true")
    p_demo.set_defaults(func=cmd_demo_env)

    p_list = sub.add_parser(
        "list-actions",
        help="Enumerate structural VGC doubles joint actions (two field + two bench per trainer; rules masking not applied)",
    )
    p_list.add_argument("--move-slots", type=int, default=4)
    p_list.add_argument("--bench-slots", type=int, default=DEFAULT_BENCH_SLOTS)
    p_list.add_argument(
        "--allow-duplicate-switch",
        action="store_true",
        help="Allow both actives to choose the same bench switch index (illegal in-game)",
    )
    p_list.set_defaults(func=cmd_list_actions)

    p_make = sub.add_parser("make-doubles", help="gym.make vgc_rl/VGC-Doubles-v0 and sample one step")
    p_make.add_argument("--allow-duplicate-switch", action="store_true")
    p_make.set_defaults(func=cmd_make_doubles)

    p_rl_smoke = sub.add_parser(
        "rl-env-smoke",
        help="Reset OracleDoubles-v0 and run random legal joint actions against the live oracle",
    )
    p_rl_smoke.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules")
    p_rl_smoke.add_argument("--steps", type=int, default=5, help="How many env.step calls after reset")
    p_rl_smoke.add_argument("--seed", type=int, default=None)
    p_rl_smoke.add_argument(
        "--six-bring",
        action="store_true",
        help="OracleDoublesRlEnv with six-mon bring phase (first step chooses among 90 bring actions)",
    )
    p_rl_smoke.add_argument("--team-alpha-key", default="team_eileen", metavar="KEY")
    p_rl_smoke.add_argument("--team-beta-key", default="team_eric", metavar="KEY")
    p_rl_smoke.add_argument(
        "--random-pair-bring-on-reset",
        action="store_true",
        help="With --six-bring: sample both brings on reset (first step is battle).",
    )
    p_rl_smoke.add_argument("--debug-print-bring", action="store_true", help="With --six-bring: print lead prefs after bring resolution.")
    p_rl_smoke.add_argument("--random-bring-alpha", action="store_true", help="With --six-bring: Alpha bring RNG on bring step (OracleDoublesRlEnv).")
    p_rl_smoke.add_argument("--random-bring-beta", action="store_true", help="With --six-bring: Beta bring RNG on bring step (BetaControlledOracleDoublesEnv).")
    p_rl_smoke.set_defaults(func=cmd_rl_env_smoke)

    p_play = sub.add_parser(
        "play-doubles",
        help="Interactive doubles: move/switch menus per lead (target submenu when needed); vs random Beta, SB3 Beta, or two humans",
    )
    p_play.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules (ignored when loading checkpoint)")
    p_play.add_argument(
        "--mode",
        choices=("human-random", "human-human"),
        default="human-random",
        help="human-random: stdin Alpha, random legal Beta; human-human: stdin both",
    )
    p_play.add_argument("--two-player", action="store_true", help="Alias for --mode human-human")
    p_play.add_argument("--alpha-field", default="0,1", metavar="I,J", help="Starting Alpha actives (ignored when resuming from checkpoint)")
    p_play.add_argument("--beta-field", default="0,3", metavar="I,J", help="Starting Beta actives (ignored when resuming from checkpoint)")
    p_play.add_argument(
        "--alpha-brought",
        default=None,
        metavar="I,J,K,L",
        help="Comma-separated four distinct brought indices for Alpha when party length is 6 (default first four)",
    )
    p_play.add_argument(
        "--beta-brought",
        default=None,
        metavar="I,J,K,L",
        help="Comma-separated four distinct brought indices for Beta when party length is 6 (default first four)",
    )
    p_play.add_argument("--team-alpha", metavar="PATH", default=None, help='Alpha party JSON {"party":[4 or 6 Pokémon]} (requires --team-beta; checkpoint stores SHA + path)')
    p_play.add_argument("--team-beta", metavar="PATH", default=None, help='Beta party JSON {"party":[4 or 6 Pokémon]} (requires --team-alpha)')
    p_play.add_argument("--seed", type=int, default=None, help="RNG seed for Beta random policy (also stored in checkpoint)")
    p_play.add_argument("--max-turns", type=int, default=512, help="Maximum turns this session (after resume, counts new turns only)")
    p_play.add_argument(
        "--save-checkpoint",
        "--save",
        dest="save_checkpoint",
        metavar="PATH",
        default=None,
        help="Write JSON battle state after each turn; if PATH exists and --load-checkpoint is omitted, resume from PATH unless --fresh-start",
    )
    p_play.add_argument("--fresh-start", action="store_true", help="Do not load existing checkpoint at --save/--save-checkpoint path")
    p_play.add_argument("--load-checkpoint", metavar="PATH", default=None, help="Resume from checkpoint JSON (overrides auto-load from --save path)")
    p_play.add_argument("--log-trajectory", metavar="PATH", default=None, help="Append one JSON object per turn (obs, legal lists, actions)")
    p_play.add_argument(
        "--beta-policy",
        metavar="PATH",
        default=None,
        help="SB3 MaskablePPO zip trained as Beta (vgc_rl/BetaOracleDoubles-v0); CPU load; requires sb3-contrib",
    )
    p_play.add_argument(
        "--beta-stochastic",
        action="store_true",
        help="Beta policy samples actions instead of deterministic mean/greedy",
    )
    p_play.set_defaults(func=cmd_play_doubles)

    p_showcase = sub.add_parser(
        "showcase-doubles",
        help="Watch automated doubles: random legal and/or SB3 policies on both sides (no stdin)",
    )
    p_showcase.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules")
    p_showcase.add_argument("--alpha-field", default="0,1", metavar="I,J", help="Starting Alpha actives")
    p_showcase.add_argument("--beta-field", default="0,3", metavar="I,J", help="Starting Beta actives")
    p_showcase.add_argument(
        "--alpha-brought",
        default=None,
        metavar="I,J,K,L",
        help="Comma-separated four distinct brought indices for Alpha when party length is 6 (default first four)",
    )
    p_showcase.add_argument(
        "--beta-brought",
        default=None,
        metavar="I,J,K,L",
        help="Comma-separated four distinct brought indices for Beta when party length is 6 (default first four)",
    )
    p_showcase.add_argument("--team-alpha", metavar="PATH", default=None, help='Alpha party JSON {"party":[4 or 6 Pokémon]} (requires --team-beta)')
    p_showcase.add_argument("--team-beta", metavar="PATH", default=None, help='Beta party JSON {"party":[4 or 6 Pokémon]} (requires --team-alpha)')
    p_showcase.add_argument(
        "--six-bring",
        action="store_true",
        help="Six-mon example teams + policy bring phase, then battle (matches *_bring6.zip training; use with --alpha-policy / --beta-policy)",
    )
    p_showcase.add_argument(
        "--team-alpha-key",
        default="team_eileen",
        metavar="KEY",
        help="When --six-bring without --team-alpha/--team-beta JSON: example_teams roster key for Alpha (six Pokémon)",
    )
    p_showcase.add_argument(
        "--team-beta-key",
        default="team_eric",
        metavar="KEY",
        help="When --six-bring without JSON paths: example_teams roster key for Beta (six Pokémon)",
    )
    p_showcase.add_argument("--seed", type=int, default=None)
    p_showcase.add_argument("--turns", type=int, default=512, help="Maximum turns to simulate")
    p_showcase.add_argument("--delay", type=float, default=0.75, help="Seconds between turns (0 for fastest)")
    p_showcase.add_argument(
        "--alpha-policy",
        metavar="PATH",
        default=None,
        help="SB3 MaskablePPO zip trained as Alpha (OracleDoubles-v0); CPU load; requires sb3-contrib",
    )
    p_showcase.add_argument(
        "--beta-policy",
        metavar="PATH",
        default=None,
        help="SB3 MaskablePPO zip trained as Beta (BetaOracleDoubles-v0); CPU load; requires sb3-contrib",
    )
    p_showcase.add_argument("--alpha-stochastic", action="store_true", help="Alpha policy samples instead of greedy")
    p_showcase.add_argument("--beta-stochastic", action="store_true", help="Beta policy samples instead of greedy")
    p_showcase.add_argument(
        "--vs-greedy",
        nargs="?",
        const="beta",
        choices=("alpha", "beta"),
        default=None,
        metavar="SIDE",
        help="Greedy masked action on SIDE (default beta) vs stochastic sampling on the other; with one --*-policy zip, loads it for both seats. Overrides --alpha-stochastic / --beta-stochastic.",
    )
    p_showcase.set_defaults(func=cmd_showcase_doubles)

    p_bring = sub.add_parser(
        "bring-eval",
        help="Monte Carlo scores for Alpha's 90 bring actions vs random opponent brings (six-mon example teams)",
    )
    p_bring.add_argument("--team-alpha-key", default="team_eileen", metavar="KEY")
    p_bring.add_argument("--team-beta-key", default="team_eric", metavar="KEY")
    p_bring.add_argument("--sv", action="store_true")
    p_bring.add_argument("--fake-oracle", action="store_true")
    p_bring.add_argument("--seed", type=int, default=0)
    p_bring.add_argument("--opponent-samples", type=int, default=2)
    p_bring.add_argument("--rolls", type=int, default=1)
    p_bring.add_argument("--max-turns", type=int, default=64)
    p_bring.set_defaults(func=cmd_bring_eval)

    p_battle = sub.add_parser(
        "battle-sim",
        help="Batch-evaluate MaskablePPO doubles policies vs random or frozen Alpha; optional seat swap for fair comparison",
    )
    p_battle.add_argument("--beta-policy", metavar="PATH", required=True, help="SB3 MaskablePPO zip trained as Beta (BetaOracleDoubles-v0)")
    p_battle.add_argument(
        "--alpha-policy",
        metavar="PATH",
        default=None,
        help="Optional SB3 zip trained as Alpha (OracleDoubles-v0); default Alpha opponent samples random legal flat actions",
    )
    p_battle.add_argument(
        "--single",
        choices=("trained", "greedy"),
        default=None,
        help="Run only one Beta mode (trained=stochastic sampling); default runs both for comparison",
    )
    p_battle.add_argument("--episodes", type=int, default=64, metavar="N", help="Battles per mode; with --swap-seats, per seat assignment (total games = 2×episodes)")
    p_battle.add_argument("--seed", type=int, default=0, help="Base seed; episode i uses seed+i (swapped block uses seed+episodes+i)")
    p_battle.add_argument("--sv", action="store_true", help="game=sv instead of champions")
    p_battle.add_argument("--fake-oracle", action="store_true", help="Deterministic FakeOracleClient (no oracle-server)")
    p_battle.add_argument("--alpha-field", default="0,1", metavar="I,J", help="Starting Alpha actives")
    p_battle.add_argument("--beta-field", default="0,3", metavar="I,J", help="Starting Beta actives")
    p_battle.add_argument("--alpha-stochastic", action="store_true", help="Frozen Alpha policy samples actions when --alpha-policy is set")
    p_battle.add_argument(
        "--swap-seats",
        action="store_true",
        help="Requires --alpha-policy: run twice swapping which checkpoint sits on Beta vs Alpha, then report per-party rows plus checkpoint win totals",
    )
    p_battle.add_argument("--no-mega", action="store_true", help="Disable Mega Evolution (Champions)")
    p_battle.add_argument("--no-tera", action="store_true", help="Disable Terastal (SV)")
    p_battle.set_defaults(func=cmd_battle_sim)

    p_ex = sub.add_parser(
        "example-battle",
        help="Oracle batch using packaged example teams (Showdown-style mirrors under vgc_rl/examples/)",
    )
    p_ex.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules (bundled example teams target Pokémon Champions)")
    p_ex.add_argument("--alpha-slot", type=int, default=0, help="team_alpha party index 0..3")
    p_ex.add_argument("--beta-slot", type=int, default=0, help="team_beta party index 0..3")
    p_ex.add_argument("--kind", choices=["single", "allMoves"], default="single")
    p_ex.set_defaults(func=cmd_example_battle)

    p_t1 = sub.add_parser(
        "simulate-turn1",
        help="Scripted multi-turn demo: oracle initiative order, Protect blocking, colored Rich log (default leads alpha 0,1 beta 0,3)",
    )
    p_t1.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules (bundled teams target Pokémon Champions)")
    p_t1.add_argument("--alpha-field", default="0,1", metavar="I,J", help="Comma-separated team_alpha party indices for the two actives (default 0,1)")
    p_t1.add_argument("--beta-field", default="0,3", metavar="I,J", help="Comma-separated team_beta party indices for the two actives (default 0,3 Charizard + Talonflame)")
    p_t1.add_argument("--verbose", action="store_true", help="Print Rich style legend after the battle log")
    p_t1.set_defaults(func=cmd_simulate_turn_one)

    p_sp = sub.add_parser(
        "self-play",
        help="Random-move oracle loop: 1v1 (default) or doubles (--doubles); HP from average damage band",
    )
    p_sp.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules")
    p_sp.add_argument("--doubles", action="store_true", help="Doubles full party (4v4 HP pool): two field slots per trainer + bench switches via --switch-rate")
    p_sp.add_argument("--alpha-field", default="0,1", metavar="I,J", help="Doubles: starting active party indices for Alpha slots A/B (default 0,1)")
    p_sp.add_argument("--beta-field", default="0,3", metavar="I,J", help="Doubles: starting active party indices for Beta slots A/B (default 0,3)")
    p_sp.add_argument(
        "--switch-rate",
        type=float,
        default=0.22,
        metavar="P",
        help="Doubles: per-slot probability to switch when bench has living Pokémon (0–1; KO’d slots force switch when possible)",
    )
    p_sp.add_argument("--alpha-slot", type=int, default=0, help="1v1 only: team_alpha party index 0..3")
    p_sp.add_argument("--beta-slot", type=int, default=0, help="1v1 only: team_beta party index 0..3")
    p_sp.add_argument("--turns", type=int, default=8, help="Maximum full turns to simulate")
    p_sp.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible move choices")
    p_sp.set_defaults(func=cmd_self_play)

    args = parser.parse_args(argv)

    if not args.oracle_url:
        args.oracle_url = "http://127.0.0.1:8765"

    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
