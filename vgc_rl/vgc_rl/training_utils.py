from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MaskablePpoLoadResult:
    model: Any
    reset_num_timesteps: bool
    source: str


def resolve_learning_rate(*, finetune: bool, learning_rate: float | None, default_train: float = 1e-3, default_finetune: float = 3e-4) -> float:
    if learning_rate is not None:
        return float(learning_rate)

    if finetune:
        return default_finetune

    return default_train


def load_or_create_maskable_ppo(
    *,
    env: Any,
    save_path: Path,
    init_policy: Path | None,
    fresh_start: bool,
    learning_rate: float,
    seed: int,
    label: str,
    device: str = "cpu",
    n_steps: int = 128,
    batch_size: int = 64,
    verbose: int = 1,
) -> MaskablePpoLoadResult:
    from sb3_contrib import MaskablePPO

    if init_policy is not None:
        init_path = Path(init_policy)

        if not init_path.is_file():
            raise FileNotFoundError(f"{label} init policy not found: {init_path}")

        try:
            model = MaskablePPO.load(str(init_path), env=env, device=device)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load {label} init policy ({init_path}): {exc}. "
                "Checkpoint observation/action space must match the current env.",
            ) from exc

        model.learning_rate = learning_rate

        return MaskablePpoLoadResult(model=model, reset_num_timesteps=False, source=f"init:{init_path}")

    if save_path.is_file() and not fresh_start:
        try:
            model = MaskablePPO.load(str(save_path), env=env, device=device)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load {label} checkpoint ({save_path}): {exc}. "
                "Use --fresh-start to train a new policy or --init-policy with a compatible zip.",
            ) from exc

        model.learning_rate = learning_rate

        return MaskablePpoLoadResult(model=model, reset_num_timesteps=False, source=f"resume:{save_path}")

    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        device=device,
        seed=seed,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
    )

    return MaskablePpoLoadResult(model=model, reset_num_timesteps=True, source="new")
