from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from vgc_rl.example_teams import load_example_teams, party_member, with_active_move
from vgc_rl.oracle_client import OracleClient
from vgc_rl.turn_sim import STATUS_NO_CALC


def _game_from_teams(data: dict[str, Any]) -> str:
    meta = data.get("meta")

    if isinstance(meta, dict) and meta.get("game"):
        return str(meta["game"])

    return "champions"


def _iter_party_entries(data: dict[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    out: list[tuple[str, int, dict[str, Any]]] = []

    for team_key, blob in data.items():
        if team_key == "meta" or not isinstance(blob, dict):
            continue

        party = blob.get("party")

        if not isinstance(party, list):
            continue

        for idx, mon in enumerate(party):
            if isinstance(mon, dict):
                out.append((team_key, idx, mon))

    return out


def _all_move_names_in_teams(data: dict[str, Any]) -> set[str]:
    names: set[str] = set()

    for _tk, _idx, mon in _iter_party_entries(data):
        for slot in mon.get("moves") or []:
            if isinstance(slot, dict):
                mv = str(slot.get("name") or "").strip()

                if mv:
                    names.add(mv)

    return names


def _unique_move_first_party_slot(data: dict[str, Any]) -> list[tuple[str, int, int]]:
    seen: set[str] = set()
    rows: list[tuple[str, int, int]] = []

    for team_key, idx, mon in _iter_party_entries(data):
        moves = mon.get("moves")

        if not isinstance(moves, list):
            continue

        for si, slot in enumerate(moves, start=1):
            if not isinstance(slot, dict):
                continue

            name = str(slot.get("name") or "").strip()

            if not name or name in seen:
                continue

            seen.add(name)
            rows.append((team_key, idx, si))

    return rows


def _dedupe_party_templates(data: dict[str, Any]) -> list[tuple[str, int]]:
    sigs: set[str] = set()
    out: list[tuple[str, int]] = []

    for team_key, idx, mon in _iter_party_entries(data):
        blob = json.dumps(mon, sort_keys=True)

        if blob in sigs:
            continue

        sigs.add(blob)
        out.append((team_key, idx))

    return out


def _chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


@pytest.mark.oracle
def test_oracle_speed_compare_smoke(oracle_client_or_skip: OracleClient) -> None:
    data = load_example_teams()
    game = _game_from_teams(data)
    left = with_active_move(party_member("team_alpha", 0), 1)
    right = with_active_move(party_member("team_beta", 3), 1)
    body: dict[str, Any] = {
        "game": game,
        "requests": [
            {
                "kind": "speedCompare",
                "field": {},
                "attacker": left,
                "secondAttacker": right,
                "speedCompareMode": "opposingTrainers",
            }
        ],
    }
    row = oracle_client_or_skip.batch(body)["results"][0]

    assert row.get("ok") is True


@pytest.mark.oracle
def test_oracle_single_for_each_unique_example_team_move(oracle_client_or_skip: OracleClient) -> None:
    data = load_example_teams()
    game = _game_from_teams(data)
    defender = party_member("team_beta", 2)
    defender["hpPercentage"] = 100.0
    requests: list[dict[str, Any]] = []

    for team_key, idx, slot in _unique_move_first_party_slot(data):
        attacker = with_active_move(party_member(team_key, idx), slot)
        attacker["hpPercentage"] = 100.0
        requests.append({"kind": "single", "field": {}, "attacker": attacker, "defender": deepcopy(defender)})

    client = oracle_client_or_skip

    for chunk in _chunked(requests, 24):
        body = {"game": game, "requests": chunk}
        rows = client.batch(body)["results"]

        for row in rows:
            assert row.get("ok") is True, row.get("error")
            res = row.get("result") or {}

            assert "moveName" in res


@pytest.mark.oracle
def test_oracle_single_for_each_distinct_party_member_template(oracle_client_or_skip: OracleClient) -> None:
    data = load_example_teams()
    game = _game_from_teams(data)
    defender = party_member("team_alpha", 0)
    defender["hpPercentage"] = 100.0
    requests: list[dict[str, Any]] = []

    for team_key, idx in _dedupe_party_templates(data):
        attacker = party_member(team_key, idx)
        pos = int(attacker.get("activeMovePosition") or 1)
        attacker = with_active_move(attacker, pos)
        attacker["hpPercentage"] = 100.0
        requests.append({"kind": "single", "field": {}, "attacker": attacker, "defender": deepcopy(defender)})

    client = oracle_client_or_skip

    for chunk in _chunked(requests, 20):
        body = {"game": game, "requests": chunk}
        rows = client.batch(body)["results"]

        for row in rows:
            assert row.get("ok") is True, row.get("error")


@pytest.mark.oracle
def test_oracle_single_for_status_no_calc_moves_used_in_example_teams(oracle_client_or_skip: OracleClient) -> None:
    data = load_example_teams()
    game = _game_from_teams(data)
    defender = party_member("team_beta", 2)
    defender["hpPercentage"] = 100.0
    client = oracle_client_or_skip
    requests: list[dict[str, Any]] = []
    names_in_teams = _all_move_names_in_teams(data)

    for mv in sorted(STATUS_NO_CALC & names_in_teams):
        team_key, idx, slot = _first_party_slot_for_move_name(data, mv)
        attacker = with_active_move(party_member(team_key, idx), slot)
        attacker["hpPercentage"] = 100.0
        requests.append({"kind": "single", "field": {}, "attacker": attacker, "defender": deepcopy(defender)})

    for chunk in _chunked(requests, 20):
        body = {"game": game, "requests": chunk}
        rows = client.batch(body)["results"]

        for row in rows:
            assert row.get("ok") is True, row.get("error")


def _first_party_slot_for_move_name(data: dict[str, Any], move_name: str) -> tuple[str, int, int]:
    for team_key, idx, mon in _iter_party_entries(data):
        moves = mon.get("moves")

        if not isinstance(moves, list):
            continue

        for si, slot in enumerate(moves, start=1):
            if isinstance(slot, dict) and str(slot.get("name") or "").strip() == move_name:
                return team_key, idx, si

    raise KeyError(move_name)
