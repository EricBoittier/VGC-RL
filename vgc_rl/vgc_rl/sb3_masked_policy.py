from __future__ import annotations

from typing import Any

import numpy as np


def load_maskable_ppo(path: str, *, device: str = "cpu") -> Any:
    try:
        from sb3_contrib import MaskablePPO
    except ImportError as exc:
        raise ImportError("Install pip packages sb3-contrib stable-baselines3 torch (CPU builds are fine).") from exc

    return MaskablePPO.load(path, device=device)


def predict_masked_joint_index(model: Any, obs: np.ndarray, mask: np.ndarray, *, deterministic: bool) -> int:
    m = np.asarray(mask, dtype=bool)
    legal = np.flatnonzero(m)

    if legal.size == 0:
        raise RuntimeError("no legal actions under mask")

    act, _ = model.predict(obs, deterministic=deterministic, action_masks=m)
    idx = int(act)

    if 0 <= idx < m.shape[0] and bool(m[idx]):
        return idx

    return int(legal[0])
