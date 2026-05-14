from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from rich.console import Console
from rich.panel import Panel

from vgc_rl.doubles_turn_engine import (
    DoublesBattleState,
    apply_initial_field_weather,
    living_bench_indices,
    resolve_turn_flat,
    side_party_wiped,
)
from vgc_rl.doubles_protect_moves import PROTECT_FAMILY_MOVES
from vgc_rl.example_teams import party_member, with_active_move
from vgc_rl.oracle_client import OracleClient
from vgc_rl.rich_report import print_showdown_line, render_self_play_doubles_snapshot, render_self_play_field_snapshot
from vgc_rl.turn_sim import STATUS_NO_CALC

_TAILWIND_DURATION_TURNS = 4

_PROTECT_STALL_MOVES = PROTECT_FAMILY_MOVES


def _protect_success_probability(prior_consecutive_successes: int) -> float:
    return (1.0 / 3.0) ** prior_consecutive_successes


def _side_label(side: str) -> str:
    return "Alpha" if side == "a" else "Beta"


def _side_party_wiped(party: list[dict[str, Any]]) -> bool:
    return side_party_wiped(party)


def _plan_doubles_turn_actions(
    rng: random.Random,
    *,
    switch_prob: float,
    party_a: list[dict[str, Any]],
    party_b: list[dict[str, Any]],
    leads_a: list[int],
    leads_b: list[int],
) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    serial = 0
    chosen_a: set[int] = set()
    chosen_b: set[int] = set()

    for atk_side, party, leads, chosen in (
        ("alpha", party_a, leads_a, chosen_a),
        ("beta", party_b, leads_b, chosen_b),
    ):
        for fi in range(2):
            pi = leads[fi]
            mon = party[pi]
            hp = float(mon.get("hpPercentage") or 0)
            bench = living_bench_indices(party, leads, chosen)

            if hp <= 0:
                if bench:
                    j = rng.choice(bench)
                    chosen.add(j)

                    planned.append(
                        {
                            "kind": "switch",
                            "atk_side": atk_side,
                            "field_idx": fi,
                            "to_party": j,
                            "orig_index": serial,
                            "forced_replace_move_slot": rng.randint(1, 4),
                        }
                    )
                else:
                    planned.append({"kind": "skip", "atk_side": atk_side, "field_idx": fi, "orig_index": serial})

                serial += 1

                continue

            if rng.random() < switch_prob and bench:
                j = rng.choice(bench)
                chosen.add(j)

                planned.append({"kind": "switch", "atk_side": atk_side, "field_idx": fi, "to_party": j, "orig_index": serial})
            else:
                planned.append({"kind": "move", "atk_side": atk_side, "field_idx": fi, "move_slot": rng.randint(1, 4), "orig_index": serial})

            serial += 1

    return planned


def _choice_tag(planned: dict[str, Any]) -> str:
    if planned["kind"] == "switch":
        return f"sw→{planned['to_party']}"

    if planned["kind"] == "skip":
        return "skip"

    return f"mv{planned['move_slot']}"


def run_self_play_1v1(
    *,
    client: OracleClient,
    game: str,
    alpha_slot: int,
    beta_slot: int,
    turns_max: int,
    seed: int | None,
    console: Console,
) -> int:
    rng = random.Random(seed)

    a = deepcopy(party_member("team_alpha", alpha_slot))
    b = deepcopy(party_member("team_beta", beta_slot))

    a["hpPercentage"] = 100
    b["hpPercentage"] = 100

    alpha_tailwind_turns_left = 0
    beta_tailwind_turns_left = 0

    protect_prior_successes = {"a": 0, "b": 0}

    console.print(
        Panel.fit(
            "[bold]Oracle self-play (1v1 smoke)[/bold]\n"
            "Each turn opens with a Rich **field snapshot** (HP, status, item, ability, moves).\n"
            "Between snapshots the trace uses **Showdown-style** pipe lines with distinct tag colors "
            "([spring_green3]|move|[/spring_green3], [red3]|-damage|[/red3], [cyan]|-hint|[/cyan], …).\n"
            "Initiative uses [gold1]speedCompare[/gold1] with [bright_blue]speedCompareMode: opposingTrainers[/bright_blue]; "
            "Tailwind ticks map to [yellow1]field.alphaSide[/yellow1] / [deep_sky_blue1]field.betaSide[/deep_sky_blue1] "
            "(aligned with batch attacker = α, secondAttacker = β).\n"
            "Successive Protect-family stalls use ~(⅓)^n success after prior consecutive successes.\n"
            "Not rules-complete (no opposing Protect blocking, no pivot targeting).",
            title="vgc-rl self-play",
        )
    )

    for turn in range(1, turns_max + 1):
        ha = float(a.get("hpPercentage") or 0)
        hb = float(b.get("hpPercentage") or 0)

        if ha <= 0 or hb <= 0:
            console.print(f"[bold]Stopped[/bold] after turn {turn - 1}: {a['name']} HP≈{ha:.1f}% · {b['name']} HP≈{hb:.1f}%")

            return 0

        render_self_play_field_snapshot(console, turn_heading=f"Turn {turn} · field state", alpha_mon=a, beta_mon=b)

        field: dict[str, Any] = {
            "alphaSide": {"isTailwind": alpha_tailwind_turns_left > 0},
            "betaSide": {"isTailwind": beta_tailwind_turns_left > 0},
        }

        sa = rng.randint(1, 4)
        sb = rng.randint(1, 4)

        console.rule("[dim]Battle log[/dim]")

        print_showdown_line(
            console,
            "field",
            f"weather=— terrain=— alphaTailwind={'yes' if alpha_tailwind_turns_left > 0 else 'no'} "
            f"betaTailwind={'yes' if beta_tailwind_turns_left > 0 else 'no'} "
            f"τ_rem α={alpha_tailwind_turns_left} β={beta_tailwind_turns_left}",
        )

        print_showdown_line(console, "choice", f"random slots α={sa} β={sb}")

        sc_body = {
            "game": game,
            "requests": [
                {
                    "kind": "speedCompare",
                    "field": field,
                    "attacker": with_active_move(a, sa),
                    "secondAttacker": with_active_move(b, sb),
                    "speedCompareMode": "opposingTrainers",
                }
            ],
        }

        sc_row = client.batch(sc_body)["results"][0]

        if not sc_row.get("ok"):
            print_showdown_line(console, "error", str(sc_row.get("error")))

            return 1

        order_json = sc_row["result"]
        first_is_a = order_json.get("firstSpecies") == a["name"]

        ordered_slots = [("a", sa), ("b", sb)] if first_is_a else [("b", sb), ("a", sa)]

        exp = str(order_json.get("explanation") or "").strip()

        if exp:
            print_showdown_line(console, "speed", exp)

        bracket = str(order_json.get("priorityBracketNote") or "").strip()

        if bracket:
            print_showdown_line(console, "-hint", bracket)

        for atk_key, atk_slot in ordered_slots:
            atk_payload = a if atk_key == "a" else b
            def_payload = b if atk_key == "a" else a

            if float(def_payload.get("hpPercentage") or 0) <= 0:
                continue

            atk_lab = _side_label(atk_key)
            def_lab = _side_label("b" if atk_key == "a" else "a")

            slot_mv = str(atk_payload["moves"][atk_slot - 1]["name"])

            if slot_mv in _PROTECT_STALL_MOVES:
                streak = protect_prior_successes[atk_key]
                p_succ = _protect_success_probability(streak)

                print_showdown_line(console, "move", f"{atk_lab} {atk_payload['name']} used {slot_mv}!")

                if rng.random() < p_succ:
                    protect_prior_successes[atk_key] = streak + 1

                    print_showdown_line(console, "-singleturn", f"{atk_lab} {atk_payload['name']} (Protect)")
                    print_showdown_line(
                        console,
                        "-hint",
                        f"Protect succeeded (~{100 * p_succ:.4g}% roll · prior streak {streak}). Defender HP unchanged.",
                    )
                else:
                    protect_prior_successes[atk_key] = 0

                    print_showdown_line(console, "-hint", f"Protect failed (~{100 * (1 - p_succ):.4g}% fail · streak was {streak}).")

                continue

            protect_prior_successes[atk_key] = 0

            if slot_mv == "Tailwind":
                if atk_key == "a":
                    alpha_tailwind_turns_left = _TAILWIND_DURATION_TURNS
                else:
                    beta_tailwind_turns_left = _TAILWIND_DURATION_TURNS

            dmg_body = {
                "game": game,
                "requests": [{"kind": "single", "field": field, "attacker": with_active_move(atk_payload, atk_slot), "defender": def_payload}],
            }

            dmg_row = client.batch(dmg_body)["results"][0]

            if not dmg_row.get("ok"):
                print_showdown_line(console, "error", str(dmg_row.get("error")))

                return 1

            dmg = dmg_row["result"]
            mv = str(dmg.get("moveName") or "")

            lo = float(dmg.get("damagePercentMin") or 0)
            hi = float(dmg.get("damagePercentMax") or 0)
            avg = (lo + hi) / 2

            prev_hp = float(def_payload.get("hpPercentage") or 100)
            new_hp = max(0.0, prev_hp - avg)

            def_payload["hpPercentage"] = new_hp

            print_showdown_line(console, "move", f"{atk_lab} {atk_payload['name']} used {mv} → {def_lab} {def_payload['name']}.")

            if mv == "Tailwind":
                print_showdown_line(console, "-sidestart", f"Tailwind · {atk_lab} side ({_TAILWIND_DURATION_TURNS}-tick refresh)")

            if lo > 0 or hi > 0:
                print_showdown_line(
                    console,
                    "-damage",
                    f"{def_lab} {def_payload['name']} HP {prev_hp:.1f}% → {new_hp:.1f}% (band {lo:.1f}–{hi:.1f}% max HP)",
                )

            hint_rest = str(dmg.get("koChanceText") or "").strip()

            if hint_rest:
                print_showdown_line(console, "-hint", hint_rest)

        if alpha_tailwind_turns_left > 0:
            alpha_tailwind_turns_left -= 1

        if beta_tailwind_turns_left > 0:
            beta_tailwind_turns_left -= 1

        console.print()

    console.print("[yellow]Turn cap reached without forced stop[/yellow]")

    return 0


def run_self_play_doubles(
    *,
    client: OracleClient,
    game: str,
    alpha_party_slots: tuple[int, int],
    beta_party_slots: tuple[int, int],
    turns_max: int,
    seed: int | None,
    console: Console,
    switch_prob: float,
) -> int:
    rng = random.Random(seed)

    party_a = [deepcopy(party_member("team_alpha", i)) for i in range(4)]
    party_b = [deepcopy(party_member("team_beta", i)) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100

    leads_a = list(alpha_party_slots)
    leads_b = list(beta_party_slots)

    battle = DoublesBattleState(
        party_a=party_a,
        party_b=party_b,
        leads_a=leads_a,
        leads_b=leads_b,
    )

    apply_initial_field_weather(battle)

    console.print(
        Panel.fit(
            "[bold]Oracle self-play (doubles · full party 4v4)[/bold]\n"
            "Each trainer keeps **[0–3] party HP**; **Slot A/B** shows who is fielded (starting leads from **--alpha-field** / **--beta-field**).\n"
            "**Bench** lines list Pokémon not currently active. Each turn uses **switch phase** (oracle speed order among switches) "
            "then **move phase** (existing insertion-sort speedCompare among attacks).\n"
            "[italic]switch[/italic] lines log party-index swaps; **faint** replacements use send-out + same-turn move (logged as “fainted · go!”); voluntary switches still log “withdrew” and the incoming Pokémon does not act that turn.\n"
            "Still a smoke harness (no pivot/U-turn semantics, no Pursuit, duplicate-target Protect unchanged).",
            title="vgc-rl self-play",
        )
    )

    for turn in range(1, turns_max + 1):
        if _side_party_wiped(party_a):
            console.print(f"[bold]Stopped[/bold] after turn {turn - 1}: Alpha party wiped (Beta wins).")

            return 0

        if _side_party_wiped(party_b):
            console.print(f"[bold]Stopped[/bold] after turn {turn - 1}: Beta party wiped (Alpha wins).")

            return 0

        render_self_play_doubles_snapshot(
            console,
            turn_heading=f"Turn {turn} · field state",
            party_alpha=party_a,
            party_beta=party_b,
            leads_alpha=(leads_a[0], leads_a[1]),
            leads_beta=(leads_b[0], leads_b[1]),
        )

        planned = _plan_doubles_turn_actions(
            rng,
            switch_prob=switch_prob,
            party_a=party_a,
            party_b=party_b,
            leads_a=leads_a,
            leads_b=leads_b,
        )

        console.rule("[dim]Battle log[/dim]")

        print_showdown_line(
            console,
            "field",
            f"weather=— terrain=— alphaTailwind={'yes' if battle.alpha_tailwind_turns_left > 0 else 'no'} "
            f"betaTailwind={'yes' if battle.beta_tailwind_turns_left > 0 else 'no'} "
            f"τ_rem α={battle.alpha_tailwind_turns_left} β={battle.beta_tailwind_turns_left}",
        )

        ca = [_choice_tag(planned[i]) for i in range(2)]
        cb = [_choice_tag(planned[i]) for i in range(2, 4)]

        print_showdown_line(
            console,
            "choice",
            f"αA={ca[0]} αB={ca[1]} βA={cb[0]} βB={cb[1]} · switch_prob≈{switch_prob:.2f} (sw→# = bench party index)",
        )

        try:
            _, _, events, _ = resolve_turn_flat(battle, rng, client, game, planned, reward_shaping=False)
        except RuntimeError as exc:
            print_showdown_line(console, "error", str(exc))

            return 1

        for tag, body_evt in events:
            print_showdown_line(console, tag, body_evt)

        console.print()

    console.print("[yellow]Turn cap reached without forced stop[/yellow]")

    return 0
