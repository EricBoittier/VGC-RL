from __future__ import annotations

import re
from typing import Any

from rich.box import ROUNDED
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vgc_rl.doubles_turn_engine import normalize_mon_boosts
from vgc_rl.turn_sim import SimLine

SHOWDOWN_PIPE_TAG_STYLES: dict[str, str] = {
    "field": "bold bright_blue",
    "choice": "italic grey62",
    "speed": "bold gold1",
    "move": "bold spring_green3",
    "switch": "bold medium_purple1",
    "-damage": "bold red3",
    "-hint": "dim cyan",
    "-singleturn": "bold deep_sky_blue1",
    "-activate": "bold deep_sky_blue1",
    "-unboost": "bold orange_red1",
    "error": "bold white on red",
}

SEGMENT_STYLES: dict[str, str] = {
    "default": "bright_white",
    "pipe_turn": "bold magenta",
    "pipe_field": "bold bright_blue",
    "pipe_move": "bold spring_green3",
    "pipe_damage": "bold red3",
    "pipe_hint": "dim cyan",
    "pipe_activate": "bold deep_sky_blue1",
    "pipe_singleturn": "bold deep_sky_blue1",
    "pipe_sidestart": "bold plum2",
    "pipe_order": "bold gold1",
    "pipe_error": "bold white on red",
    "turn_title": "bold magenta",
    "field": "grey70",
    "trainer_spec": "bold yellow1",
    "target_spec": "bold chartreuse3",
    "move": "bold aquamarine3",
    "damage_pct": "bold red1",
    "ko_hint": "bold orange_red1",
    "hint": "italic grey62",
    "protect": "bold deep_sky_blue1",
    "blocked": "bold white on dark_red",
    "status_side": "bold plum2",
    "order": "gold1",
    "error": "bold white on red",
}


def _append_showdown_body(text: Text, body_plain: str) -> None:
    base = "bright_white"
    parts = re.split(r"(\bAlpha\b|\bBeta\b)", body_plain)

    for part in parts:
        if part == "Alpha":
            text.append(part, style="bold yellow1")

            continue

        if part == "Beta":
            text.append(part, style="bold deep_sky_blue1")

            continue

        if part:
            text.append(part, style=base)


def print_showdown_line(console: Console, tag: str, body_plain: str) -> None:
    pipe_style = SHOWDOWN_PIPE_TAG_STYLES.get(tag, "bold slate_blue1")
    line = Text()
    line.append("|", style=pipe_style)
    line.append(tag, style=pipe_style)
    line.append("| ", style=pipe_style)
    _append_showdown_body(line, body_plain)
    console.print(line)


def _dash(v: Any, empty: str = "—") -> str:
    if v is None or v == "":
        return empty

    return str(v)


def _boost_line(mon: dict[str, Any]) -> str:
    normalize_mon_boosts(mon)

    b = mon["boosts"]

    bits = [f"{k}:{int(b[k]):+d}" for k in ("atk", "def", "spa", "spd", "spe") if int(b[k]) != 0]

    return ", ".join(bits) if bits else "neutral"


def _trainer_active_panel(mon: dict[str, Any], trainer_title: str, *, expand: bool = True) -> Panel:
    hp = float(mon.get("hpPercentage") or 0)
    status_raw = mon.get("status")
    status = "Healthy" if status_raw in (None, "") else str(status_raw)
    item = _dash(mon.get("item"))
    ability = _dash(mon.get("ability"))
    nature = _dash(mon.get("nature"))
    tera = _dash(mon.get("teraType"))
    tera_act = bool(mon.get("teraTypeActive"))

    if tera != "—":
        tera = f"{tera}{' · Tera active' if tera_act else ''}"

    moves = " / ".join(str(m.get("name") or "?") for m in mon.get("moves") or [])

    inner = Table(show_header=False, box=None, pad_edge=False, expand=expand)
    inner.add_column(style="bright_black", justify="right", width=10)
    inner.add_column(ratio=1)

    inner.add_row("Species", f"[bold bright_white]{_dash(mon.get('name'), '?')}[/bold bright_white]")
    inner.add_row("HP", f"[bold spring_green3]{hp:.1f}%[/bold spring_green3]")
    inner.add_row("Boosts", f"[orange_red1]{_boost_line(mon)}[/orange_red1]")
    inner.add_row("Status", f"[gold1]{status}[/gold1]")
    inner.add_row("Item", f"[plum2]{item}[/plum2]")
    inner.add_row("Ability", f"[deep_sky_blue1]{ability}[/deep_sky_blue1]")
    inner.add_row("Nature", f"[dim grey62]{nature}[/dim grey62]")
    inner.add_row("Tera", f"[dim grey62]{tera}[/dim grey62]")
    inner.add_row("Moves", f"[italic grey93]{moves}[/italic grey93]")

    title_style = "bold yellow1" if "Alpha" in trainer_title else "bold deep_sky_blue1"

    return Panel(inner, title=f"[{title_style}]{trainer_title}[/{title_style}]", border_style="bright_blue", expand=expand)


def render_self_play_field_snapshot(console: Console, *, turn_heading: str, alpha_mon: dict[str, Any], beta_mon: dict[str, Any]) -> None:
    console.rule(f"[bold magenta3]{turn_heading}[/bold magenta3]")
    console.print(
        Columns(
            [
                _trainer_active_panel(alpha_mon, "Alpha · active"),
                _trainer_active_panel(beta_mon, "Beta · active"),
            ],
            equal=True,
            expand=True,
        )
    )

    console.print()


def render_self_play_doubles_snapshot(
    console: Console,
    *,
    turn_heading: str,
    party_alpha: list[dict[str, Any]],
    party_beta: list[dict[str, Any]],
    leads_alpha: tuple[int, int],
    leads_beta: tuple[int, int],
) -> None:
    console.rule(f"[bold magenta3]{turn_heading}[/bold magenta3]")
    a0 = party_alpha[leads_alpha[0]]
    a1 = party_alpha[leads_alpha[1]]
    b0 = party_beta[leads_beta[0]]
    b1 = party_beta[leads_beta[1]]
    grid = Table(
        show_header=True,
        box=ROUNDED,
        border_style="bright_blue",
        header_style="bold grey70",
        expand=True,
        pad_edge=True,
    )
    grid.add_column("", justify="right", width=7, vertical="top", style="bold grey62")
    grid.add_column("Slot A", justify="center", ratio=1, vertical="top")
    grid.add_column("Slot B", justify="center", ratio=1, vertical="top")

    grid.add_row(
        Text("Alpha", style="bold yellow1"),
        _trainer_active_panel(a0, f"α · A (party #{leads_alpha[0]})", expand=False),
        _trainer_active_panel(a1, f"α · B (party #{leads_alpha[1]})", expand=False),
    )
    grid.add_row(
        Text("Beta", style="bold deep_sky_blue1"),
        _trainer_active_panel(b0, f"β · A (party #{leads_beta[0]})", expand=False),
        _trainer_active_panel(b1, f"β · B (party #{leads_beta[1]})", expand=False),
    )

    console.print(grid)

    def bench_bits(party: list[dict[str, Any]], leads: tuple[int, int], side_label: str) -> str:
        busy = set(leads)
        parts: list[str] = []

        for i, mon in enumerate(party):
            if i in busy:
                continue

            hp = float(mon.get("hpPercentage") or 0)
            bl = _boost_line(mon)
            tail = f" · {bl}" if bl != "neutral" else ""

            parts.append(f"#{i} {_dash(mon.get('name'))} {hp:.0f}%{tail}")

        body = " · ".join(parts) if parts else "—"

        return f"[bold grey70]{side_label} bench[/bold grey70] {body}"

    console.print(Text.from_markup(bench_bits(party_alpha, leads_alpha, "Alpha")))
    console.print(Text.from_markup(bench_bits(party_beta, leads_beta, "Beta")))
    console.print()


def assemble_sim_line(line: SimLine) -> Text:
    t = Text()

    for seg in line.segments:
        st = SEGMENT_STYLES.get(seg.style, seg.style)

        t.append(seg.text, style=st)

    return t


def render_turn_simulation(
    console: Console,
    turns: tuple[list[SimLine], ...],
    *,
    verbose: bool = False,
) -> None:
    console.print(
        Panel.fit(
            "[bold bright_white]simulate-turn1[/bold bright_white] · full-turn ordering ([gold1]speedCompare[/gold1]) · [deep_sky_blue1]Protect[/deep_sky_blue1] blocks later targeted damage in the same scripted turn",
            title="[bold magenta3]Oracle demo[/bold magenta3]",
            border_style="bright_blue",
        )
    )

    for turn_lines in turns:
        for line in turn_lines:
            row = assemble_sim_line(line)

            if str(row).strip():
                console.print(row)

    if not verbose:
        return

    legend = Text.assemble(
        ("Verbose legend: ", "dim grey62"),
        ("|turn|", SEGMENT_STYLES["pipe_turn"]),
        (" · ", "dim grey62"),
        ("|field|", SEGMENT_STYLES["pipe_field"]),
        (" · ", "dim grey62"),
        ("|move|", SEGMENT_STYLES["pipe_move"]),
        (" · ", "dim grey62"),
        ("|-damage|", SEGMENT_STYLES["pipe_damage"]),
        (" · ", "dim grey62"),
        ("|hint|", SEGMENT_STYLES["pipe_hint"]),
        (" · ", "dim grey62"),
        ("Protect", SEGMENT_STYLES["protect"]),
        ("/blocked", SEGMENT_STYLES["blocked"]),
        (" · ", "dim grey62"),
        ("|error|", SEGMENT_STYLES["pipe_error"]),
        (".", "dim grey62"),
    )

    console.print(Panel(legend, title="[dim grey62]Styles[/dim grey62]", border_style="grey42"))
