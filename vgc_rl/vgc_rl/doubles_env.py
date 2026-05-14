from __future__ import annotations

from typing import Any, SupportsFloat

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from vgc_rl.doubles_actions import (
    DEFAULT_BENCH_SLOTS,
    DEFAULT_MOVE_SLOTS,
    JointDoublesAction,
    decode_joint_index,
    enumerate_joint_actions_structural,
)

_registered = False


def register_vgc_envs() -> None:
    global _registered

    if _registered:
        return

    gym.register(
        id="vgc_rl/VGC-Doubles-v0",
        entry_point="vgc_rl.doubles_env:VGCDoublesEnv",
        kwargs={"filter_duplicate_switch_to_same_bench": True},
        max_episode_steps=512,
    )

    gym.register(
        id="vgc_rl/BetaOracleDoubles-v0",
        entry_point="vgc_rl.beta_oracle_env:BetaControlledOracleDoublesEnv",
        kwargs={"game": "champions", "max_steps": 128},
        max_episode_steps=128,
    )

    gym.register(
        id="vgc_rl/OracleDoubles-v0",
        entry_point="vgc_rl.oracle_doubles_rl_env:OracleDoublesRlEnv",
        kwargs={"game": "champions", "max_steps": 128},
        max_episode_steps=128,
    )

    _registered = True


class VGCDoublesEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        filter_duplicate_switch_to_same_bench: bool = True,
        move_slots: int = DEFAULT_MOVE_SLOTS,
        bench_slots: int = DEFAULT_BENCH_SLOTS,
    ) -> None:
        super().__init__()
        self._joint_actions: tuple[JointDoublesAction, ...] = enumerate_joint_actions_structural(
            move_slots=move_slots,
            bench_slots=bench_slots,
            filter_duplicate_switch_to_same_bench=filter_duplicate_switch_to_same_bench,
        )
        self.action_space = spaces.Discrete(len(self._joint_actions))
        self.observation_space = spaces.Dict(
            {
                "placeholder": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
            }
        )
        self._obs = {"placeholder": np.zeros((1,), dtype=np.float32)}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        super().reset(seed=seed)

        info = {
            "joint_action_space_size": len(self._joint_actions),
            "note": "Structural enumeration only; legality requires battle rules + action masking.",
        }

        return self._obs.copy(), info

    def step(self, action: SupportsFloat) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        idx = int(action)

        joint = decode_joint_index(idx, self._joint_actions)

        return self._obs.copy(), 0.0, False, False, {"joint_action": joint}
