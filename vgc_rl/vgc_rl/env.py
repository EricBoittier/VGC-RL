from __future__ import annotations

import os
from typing import Any, SupportsFloat, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from vgc_rl.oracle_client import OracleClient, sample_raging_bolt_vs_flutter_mane_single


def oracle_single_features(result: dict[str, Any]) -> np.ndarray:
    dmin = float(result.get("damagePercentMin") or 0.0)
    dmax = float(result.get("damagePercentMax") or 0.0)
    rolls = result.get("damageRolls") or []

    if rolls and isinstance(rolls[0], list):
        flat = [float(x) for row in rolls for x in row]

        if flat:
            mean_roll = float(np.mean(flat))
        else:
            mean_roll = 0.0
    else:
        mean_roll = 0.0

    return np.array([dmin / 100.0, dmax / 100.0, mean_roll / 200.0], dtype=np.float32)


class OracleFeatureToyEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, oracle: OracleClient | None = None, game: str = "sv") -> None:
        super().__init__()
        self._oracle = oracle or OracleClient(base_url=os.environ.get("ORACLE_URL"))
        self._game = game if game in ("sv", "champions") else "sv"
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(3,), dtype=np.float32)
        self.action_space = spaces.Discrete(1)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        payload = sample_raging_bolt_vs_flutter_mane_single(self._game)  # type: ignore[arg-type]
        data = self._oracle.batch(payload)
        row = data["results"][0]

        if not row.get("ok"):
            raise RuntimeError(row.get("error", "oracle batch failed"))

        obs = oracle_single_features(row["result"])
        info = {"oracle": row["result"]}

        return obs, info

    def step(self, action: SupportsFloat) -> Tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        obs = np.zeros((3,), dtype=np.float32)

        return obs, 0.0, True, False, {}
