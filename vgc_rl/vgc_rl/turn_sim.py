from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from vgc_rl.example_teams import load_example_teams, with_active_move
from vgc_rl.oracle_client import OracleClient

PartyRef = tuple[Literal["alpha", "beta"], int]


@dataclass(frozen=True)
class StepDamage:
    attacker: PartyRef
    move_slot: int
    defender: PartyRef


@dataclass(frozen=True)
class StepSelfAction:
    attacker: PartyRef
    move_slot: int


@dataclass(frozen=True)
class StepDoubleInto:
    attacker_a: PartyRef
    move_slot_a: int
    attacker_b: PartyRef
    move_slot_b: int
    defender: PartyRef


@dataclass(frozen=True)
class TurnSpec:
    title: str
    field: dict[str, Any]
    steps: tuple[StepDamage | StepSelfAction | StepDoubleInto, ...]


@dataclass(frozen=True)
class SimSeg:
    text: str
    style: str


@dataclass(frozen=True)
class SimLine:
    segments: tuple[SimSeg, ...]


PROTECT_FAMILY = frozenset({"Protect", "Detect", "Spiky Shield", "Baneful Bunker", "Burning Bulwark", "Silk Trap"})
STATUS_NO_CALC = frozenset({
    "Tailwind",
    "Trick Room",
    "Light Screen",
    "Reflect",
    "Aurora Veil",
    "Haze",
    "Sunny Day",
    "Rain Dance",
    "Snowscape",
    "Sandstorm",
    "Electric Terrain",
    "Grassy Terrain",
    "Psychic Terrain",
    "Misty Terrain",
})


def _trainer_label(side: str) -> str:
    return "Alpha" if side == "alpha" else "Beta"


def _party_mon(ref: PartyRef, ta: list[dict[str, Any]], tb: list[dict[str, Any]]) -> dict[str, Any]:
    side, idx = ref

    return ta[idx] if side == "alpha" else tb[idx]


def _move_name(mon: dict[str, Any], slot: int) -> str:
    return mon["moves"][slot - 1]["name"]


def _initiative_first(
    client: OracleClient,
    game: str,
    field: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_side: str,
    right_side: str,
    left_index: int,
    right_index: int,
) -> bool:
    opposing_sides = left_side != right_side
    mode = "opposingTrainers" if opposing_sides else "alliedDoubles"

    body = {
        "game": game,
        "requests": [
            {
                "kind": "speedCompare",
                "field": field,
                "attacker": left,
                "secondAttacker": right,
                "speedCompareMode": mode,
            }
        ],
    }

    row = client.batch(body)["results"][0]

    if not row.get("ok"):
        return left_index < right_index

    res = row["result"]

    lf = (res.get("firstSpecies"), res.get("firstMove"))
    ls = (left["name"], _move_name(left, int(left.get("activeMovePosition") or 1)))

    return lf == ls


def _sort_by_initiative(client: OracleClient, game: str, field: dict[str, Any], prepared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []

    for item in prepared:
        placed = False

        for j in range(len(ordered)):
            other = ordered[j]

            if _initiative_first(
                client,
                game,
                field,
                item["atk_payload"],
                other["atk_payload"],
                left_side=item["atk_side"],
                right_side=other["atk_side"],
                left_index=item["orig_index"],
                right_index=other["orig_index"],
            ):
                ordered.insert(j, item)

                placed = True

                break

        if not placed:
            ordered.append(item)

    return ordered


def _line(*segments: SimSeg) -> SimLine:
    return SimLine(segments=segments)


def _seg(text: str, style: str = "default") -> SimSeg:
    return SimSeg(text=text, style=style)


def build_demo_turns(*, alpha_slots: tuple[int, int], beta_slots: tuple[int, int]) -> tuple[TurnSpec, ...]:
    ai, aj = alpha_slots
    bk, bl = beta_slots

    return (
        TurnSpec(
            title="Turn 1 · Field leads scrap (initiative + Protect)",
            field={},
            steps=(
                StepSelfAction(("alpha", aj), 4),
                StepDamage(("beta", bl), 1, ("alpha", ai)),
                StepSelfAction(("alpha", ai), 2),
                StepDamage(("beta", bk), 2, ("alpha", ai)),
            ),
        ),
        TurnSpec(
            title="Turn 2 · Rain pocket (bench attackers)",
            field={"weather": "Rain"},
            steps=(
                StepDamage(("alpha", 2), 1, ("beta", bk)),
                StepDamage(("beta", 2), 2, ("alpha", aj)),
            ),
        ),
        TurnSpec(
            title="Turn 3 · Same-target double into Talonflame",
            field={},
            steps=(
                StepDoubleInto(("alpha", ai), 4, ("alpha", aj), 3, ("beta", bl)),
            ),
        ),
        TurnSpec(
            title="Turn 4 · Heat Wave tags Protecting Dragonite (blocked)",
            field={},
            steps=(
                StepSelfAction(("alpha", aj), 4),
                StepDamage(("beta", bk), 2, ("alpha", aj)),
            ),
        ),
    )


def simulate_turn(
    *,
    client: OracleClient,
    game: str,
    turn: TurnSpec,
    ta: list[dict[str, Any]],
    tb: list[dict[str, Any]],
) -> list[SimLine]:
    lines: list[SimLine] = []

    lines.append(_line(_seg("|turn| ", "pipe_turn"), _seg(turn.title, "turn_title")))

    fld = turn.field or {}

    fparts = [
        f"weather={fld.get('weather') or '—'}",
        f"terrain={fld.get('terrain') or '—'}",
        f"trick_room={'yes' if fld.get('isTrickRoom') else 'no'}",
    ]

    lines.append(_line(_seg("|field| ", "pipe_field"), _seg("|".join(fparts), "field")))

    protected: set[PartyRef] = set()

    prepared_non_double: list[dict[str, Any]] = []

    double_steps: list[StepDoubleInto] = []

    prep_serial = 0

    for step in turn.steps:
        if isinstance(step, StepDoubleInto):
            double_steps.append(step)

            continue

        if isinstance(step, StepDamage):
            mon = _party_mon(step.attacker, ta, tb)

            prepared_non_double.append(
                {
                    "kind": "damage",
                    "step": step,
                    "atk_payload": with_active_move(mon, step.move_slot),
                    "orig_index": prep_serial,
                    "atk_side": step.attacker[0],
                }
            )

            prep_serial += 1

        elif isinstance(step, StepSelfAction):
            mon = _party_mon(step.attacker, ta, tb)

            prepared_non_double.append(
                {
                    "kind": "self",
                    "step": step,
                    "atk_payload": with_active_move(mon, step.move_slot),
                    "orig_index": prep_serial,
                    "atk_side": step.attacker[0],
                }
            )

            prep_serial += 1

    ordered = _sort_by_initiative(client, game, fld, prepared_non_double)

    for item in ordered:
        step = item["step"]
        atk_ref = step.attacker
        atk_side, _atk_idx = atk_ref
        atk_mon = item["atk_payload"]
        mv_name = _move_name(atk_mon, step.move_slot)

        atk_lab = _trainer_label(atk_side)
        atk_spec = atk_mon["name"]

        if isinstance(step, StepSelfAction):
            lines.append(
                _line(
                    _seg("|move| ", "pipe_move"),
                    _seg(f"{atk_lab} {atk_spec}", "trainer_spec"),
                    _seg(" used ", "default"),
                    _seg(mv_name, "move"),
                    _seg(".", "default"),
                )
            )

            if mv_name in PROTECT_FAMILY:
                lines.append(_line(_seg("|-singleturn| ", "pipe_singleturn"), _seg(f"{atk_lab} {atk_spec}", "trainer_spec"), _seg(" Protect", "protect")))
                lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(f"{atk_lab} {atk_spec} protected itself from incoming attacks this turn.", "hint")))
                protected.add(atk_ref)

            elif mv_name in STATUS_NO_CALC:
                lines.append(_line(_seg("|-sidestart| ", "pipe_sidestart"), _seg(f"{atk_lab}", "trainer_spec"), _seg(f" {mv_name}", "status_side")))
                lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(f"Team status move — no damage calc in this harness ({mv_name}).", "hint")))

            else:
                lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(f"Self-target action ({mv_name}); oracle damage skipped.", "hint")))

            continue

        def_ref = step.defender
        def_side, _def_idx = def_ref
        def_mon = _party_mon(def_ref, ta, tb)
        def_lab = _trainer_label(def_side)
        def_spec = def_mon["name"]

        lines.append(
            _line(
                _seg("|move| ", "pipe_move"),
                _seg(f"{atk_lab} {atk_spec}", "trainer_spec"),
                _seg(" used ", "default"),
                _seg(mv_name, "move"),
                _seg(" → ", "default"),
                _seg(f"{def_lab} {def_spec}", "target_spec"),
                _seg(".", "default"),
            )
        )

        if def_ref in protected:
            lines.append(_line(_seg("|-activate| ", "pipe_activate"), _seg(f"{def_lab} {def_spec}", "target_spec"), _seg(" Protect", "protect")))
            lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg("Damage blocked — defender was Protecting this turn.", "blocked")))

            continue

        body = {
            "game": game,
            "requests": [{"kind": "single", "field": fld, "attacker": atk_mon, "defender": def_mon}],
        }

        row = client.batch(body)["results"][0]

        if not row.get("ok"):
            lines.append(_line(_seg("|error| ", "pipe_error"), _seg(str(row.get("error")), "error")))

            continue

        res = row["result"]

        lo = res.get("damagePercentMin")
        hi = res.get("damagePercentMax")
        ko = str(res.get("koChanceText") or "").strip()

        lines.append(
            _line(
                _seg("|-damage| ", "pipe_damage"),
                _seg(f"{def_lab} {def_spec}", "target_spec"),
                _seg(f" — {lo}–{hi}% max HP", "damage_pct"),
            )
        )

        if ko:
            lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(ko, "ko_hint")))

        md = str(res.get("moveDesc") or "").strip()

        if md and md != f"{lo} - {hi}%":
            lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(md, "hint")))

        sc = res.get("speedContext")

        if isinstance(sc, dict) and sc.get("lines"):
            lines.append(
                _line(
                    _seg("|hint| ", "pipe_hint"),
                    _seg(
                        f"Spe prio {sc.get('attackerMovePriority')} (base {sc.get('attackerMoveBasePriority')}) GW={sc.get('galeWingsBoostApplied')} PK={sc.get('pranksterBoostApplied')}",
                        "hint",
                    ),
                )
            )

    for dbl in double_steps:
        da = _party_mon(dbl.attacker_a, ta, tb)
        db = _party_mon(dbl.attacker_b, ta, tb)
        df = _party_mon(dbl.defender, ta, tb)

        pa = with_active_move(da, dbl.move_slot_a)
        pb = with_active_move(db, dbl.move_slot_b)

        ma = _move_name(pa, dbl.move_slot_a)
        mb = _move_name(pb, dbl.move_slot_b)

        def_ref = dbl.defender
        def_side, _def_i = def_ref
        def_lab = _trainer_label(def_side)

        opposing = dbl.attacker_a[0] != dbl.attacker_b[0]
        mode = "opposingTrainers" if opposing else "alliedDoubles"

        sc_body = {
            "game": game,
            "requests": [
                {
                    "kind": "speedCompare",
                    "field": fld,
                    "attacker": pa,
                    "secondAttacker": pb,
                    "speedCompareMode": mode,
                }
            ],
        }

        sc_row = client.batch(sc_body)["results"][0]

        if sc_row.get("ok"):
            sr = sc_row["result"]

            lines.append(
                _line(
                    _seg("|order| ", "pipe_order"),
                    _seg(f"{sr.get('firstSpecies')} ({sr.get('firstMove')}) before ", "order"),
                    _seg(f"{sr.get('secondSpecies')} ({sr.get('secondMove')})", "order"),
                )
            )

        if def_ref in protected:
            lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(f"{df['name']} still Protecting — double-target skipped.", "blocked")))

            continue

        lines.append(
            _line(
                _seg("|move| ", "pipe_move"),
                _seg(f"Alpha {pa['name']}", "trainer_spec"),
                _seg(f" {ma} / ", "move"),
                _seg(f"Alpha {pb['name']}", "trainer_spec"),
                _seg(f" {mb} → ", "move"),
                _seg(f"{def_lab} {df['name']}", "target_spec"),
                _seg(".", "default"),
            )
        )

        dmg_body = {
            "game": game,
            "requests": [{"kind": "double", "field": fld, "attacker": pa, "secondAttacker": pb, "defender": df}],
        }

        dr = client.batch(dmg_body)["results"][0]

        if not dr.get("ok"):
            lines.append(_line(_seg("|error| ", "pipe_error"), _seg(str(dr.get("error")), "error")))

            continue

        drs = dr["result"]

        combo = str(drs.get("combinedMoveDesc") or "").replace("\n", " ")
        ko2 = str(drs.get("koChanceText") or "").strip()

        lines.append(_line(_seg("|-damage| ", "pipe_damage"), _seg(f"{def_lab} {df['name']}", "target_spec"), _seg(f" — {combo}", "damage_pct")))

        if ko2:
            lines.append(_line(_seg("|hint| ", "pipe_hint"), _seg(ko2, "ko_hint")))

    lines.append(_line(_seg("", "default")))

    return lines


def run_turn_one_demo(
    *,
    client: OracleClient,
    game: str,
    alpha_slots: tuple[int, int],
    beta_slots: tuple[int, int],
) -> tuple[list[SimLine], ...]:
    data = load_example_teams()
    ta = [dict(x) for x in data["team_alpha"]["party"]]
    tb = [dict(x) for x in data["team_beta"]["party"]]

    turns = build_demo_turns(alpha_slots=alpha_slots, beta_slots=beta_slots)

    return tuple(simulate_turn(client=client, game=game, turn=t, ta=ta, tb=tb) for t in turns)


def simulation_has_errors(all_turn_lines: tuple[list[SimLine], ...]) -> bool:
    for turn in all_turn_lines:
        for ln in turn:
            for seg in ln.segments:
                if seg.style == "error":
                    return True

    return False
