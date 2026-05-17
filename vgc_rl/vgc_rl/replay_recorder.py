from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import gymnasium as gym

from vgc_rl.replay import build_replay_document, replay_outcome, snapshot_state, write_replay


class ReplayCaptureWrapper(gym.Wrapper):
    def __init__(
        self,
        env: gym.Env,
        *,
        save_dir: Path | str,
        save_every_n_episodes: int = 25,
        meta_fn: Callable[[], dict[str, Any]] | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(env)
        self._save_dir = Path(save_dir)
        self._save_every = max(1, int(save_every_n_episodes))
        self._meta_fn = meta_fn or (lambda: {})
        self._enabled = bool(enabled)
        self._episode_index = 0
        self._frames: list[dict[str, Any]] = []
        self._initial: dict[str, Any] | None = None
        self._last_final: dict[str, Any] | None = None
        self._last_outcome = "ongoing"
        self._game = "champions"

    @property
    def episode_index(self) -> int:
        return self._episode_index

    def _inner(self) -> Any:
        return self.env.unwrapped

    def _read_game(self) -> str:
        inner = self._inner()

        return str(getattr(inner, "_game", "champions"))

    def _maybe_save_replay(self, *, force: bool = False) -> Path | None:
        if not self._enabled or not self._frames:
            return None

        if not force and (self._episode_index % self._save_every) != 0:
            return None

        self._save_dir.mkdir(parents=True, exist_ok=True)
        meta = dict(self._meta_fn())
        meta["episode_index"] = self._episode_index
        stamp = int(time.time() * 1000)
        phase = str(meta.get("phase", "train"))
        rnd = meta.get("round")
        rnd_bit = f"_r{rnd}" if rnd is not None else ""
        fname = f"replay_{phase}{rnd_bit}_ep{self._episode_index}_{stamp}.json"
        doc = build_replay_document(
            game=self._game,
            meta=meta,
            initial_state=self._initial,
            frames=list(self._frames),
            final_state=self._last_final,
            outcome=self._last_outcome,
        )

        return write_replay(self._save_dir / fname, doc)

    def flush_replay(self, *, force: bool = True) -> Path | None:
        return self._maybe_save_replay(force=force)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        if self._frames:
            self._maybe_save_replay()

        obs, info = self.env.reset(seed=seed, options=options)
        self._episode_index += 1
        self._frames = []
        self._game = self._read_game()
        inner = self._inner()
        state = getattr(inner, "_state", None)
        step_count = int(getattr(inner, "_step_count", 0) or 0)
        self._initial = snapshot_state(state, game=self._game, step_count=step_count)
        self._last_final = self._initial
        self._last_outcome = "ongoing"

        return obs, info

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        frame = info.get("replay_frame")

        if isinstance(frame, dict):
            self._frames.append(frame)

        inner = self._inner()
        state = getattr(inner, "_state", None)
        step_count = int(getattr(inner, "_step_count", 0) or 0)
        self._last_final = snapshot_state(state, game=self._game, step_count=step_count)
        self._last_outcome = replay_outcome(
            terminated=bool(terminated),
            truncated=bool(truncated),
            party_wiped_alpha=bool(info.get("party_wiped_alpha")),
            party_wiped_beta=bool(info.get("party_wiped_beta")),
        )

        return obs, reward, terminated, truncated, info


def find_replay_wrapper(env: gym.Env) -> ReplayCaptureWrapper | None:
    cur: gym.Env | Any = env

    while cur is not None:
        if isinstance(cur, ReplayCaptureWrapper):
            return cur

        nxt = getattr(cur, "env", None)

        if nxt is cur:
            break

        cur = nxt

    return None
