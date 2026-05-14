from __future__ import annotations

import os
from typing import Any, Literal

import httpx

OracleGame = Literal["sv", "champions"]


class OracleClient:
    def __init__(self, base_url: str | None = None, timeout_s: float = 60.0) -> None:
        self.base_url = (base_url or os.environ.get("ORACLE_URL") or "http://127.0.0.1:8765").rstrip("/")
        self._timeout = timeout_s

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()

            return response.json()

    def batch(self, body: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self.base_url}/batch", json=body)
            response.raise_for_status()

            return response.json()


def sample_raging_bolt_vs_flutter_mane_single(game: OracleGame = "sv") -> dict[str, Any]:
    return {
        "game": game,
        "requests": [
            {
                "kind": "single",
                "field": {},
                "attacker": {
                    "name": "Raging Bolt",
                    "moves": [{"name": "Thunderbolt"}, {"name": "Thunderclap"}, {"name": "Draco Meteor"}, {"name": "Protect"}],
                    "activeMovePosition": 1,
                },
                "defender": {
                    "name": "Flutter Mane",
                    "moves": [{"name": "Moonblast"}, {"name": "Shadow Ball"}, {"name": "Dazzling Gleam"}, {"name": "Protect"}],
                },
            }
        ],
    }


def summarize_single_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "moveName": result.get("moveName"),
        "moveDesc": result.get("moveDesc"),
        "koChanceText": result.get("koChanceText"),
        "damagePercentMin": result.get("damagePercentMin"),
        "damagePercentMax": result.get("damagePercentMax"),
    }


def summarize_double_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "firstMoveName": result.get("firstMoveName"),
        "secondMoveName": result.get("secondMoveName"),
        "koChanceText": result.get("koChanceText"),
        "damagePercentMax": result.get("damagePercentMax"),
        "combinedMoveDesc": result.get("combinedMoveDesc"),
    }
