from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, SupportsFloat

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from vgc_rl.battle_completion import alpha_reward_for_outcome, apply_step_cap_as_decisive_end
from vgc_rl.bring_selection import BRING_ACTION_SPACE_SIZE, battle_state_from_bring_actions, format_six_bring_lead_prefs_line
from vgc_rl.doubles_action_mask import (
    FORM_ACTION_BRANCHES,
    decode_flat_form_action,
    legal_flat_mask_alpha,
    legal_flat_mask_beta,
    split_form_branch_for_game,
)
from vgc_rl.doubles_actions import enumerate_joint_actions_structural
from vgc_rl.doubles_obs_identity import DOUBLES_OBS_TOTAL_DIM, DOUBLES_OBS_WITH_SIX_BRING_DIM
from vgc_rl.doubles_turn_engine import DoublesBattleState, apply_initial_field_weather, joint_to_planned_side, resolve_turn, side_party_wiped_brought
from vgc_rl.team_registry import prepare_parties_for_reset
from vgc_rl.interactive_doubles import doubles_obs_vector, doubles_rl_six_bring_observation
from vgc_rl.oracle_client import OracleClient
from vgc_rl.replay import attach_bring_replay_frame, attach_turn_replay_frame
from vgc_rl.sb3_masked_policy import predict_masked_joint_index


class OracleDoublesRlEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        oracle: OracleClient,
        *,
        game: str = "champions",
        max_steps: int = 128,
        seed: int | None = None,
        alpha_field: tuple[int, int] = (0, 1),
        beta_field: tuple[int, int] = (0, 3),
        reward_shaping: bool = False,
        beta_policy_model: Any | None = None,
        beta_policy_deterministic: bool = True,
        allow_mega_evolution: bool = True,
        allow_terastal: bool = True,
        six_mon_bring: bool = False,
        team_alpha_key: str | None = None,
        team_beta_key: str | None = None,
        random_bring_alpha: bool = False,
        random_bring_beta: bool = False,
        random_pair_bring_on_reset: bool = False,
        debug_print_bring: bool = False,
        meta_pool: bool = False,
        team_pool_keys: list[str] | None = None,
    ) -> None:
        super().__init__()

        if alpha_field[0] == alpha_field[1] or beta_field[0] == beta_field[1]:
            raise ValueError("alpha_field and beta_field must be two distinct party indices")

        if random_pair_bring_on_reset and not six_mon_bring:
            raise ValueError("random_pair_bring_on_reset requires six_mon_bring")

        if meta_pool and not six_mon_bring:
            raise ValueError("meta_pool requires six_mon_bring")

        self._oracle = oracle
        self._game = game if game in ("sv", "champions") else "champions"
        self._max_steps = max_steps
        self._alpha_field = alpha_field
        self._beta_field = beta_field
        self._reward_shaping = reward_shaping
        self._beta_policy_model = beta_policy_model
        self._beta_policy_deterministic = beta_policy_deterministic
        self._allow_mega_evolution = allow_mega_evolution
        self._allow_terastal = allow_terastal
        self._six_mon_bring = six_mon_bring
        self._team_alpha_key = team_alpha_key or ("team_eileen" if six_mon_bring else "team_alpha")
        self._team_beta_key = team_beta_key or ("team_eric" if six_mon_bring else "team_beta")
        self._random_bring_alpha = random_bring_alpha
        self._random_bring_beta = random_bring_beta
        self._random_pair_bring_on_reset = random_pair_bring_on_reset
        self._debug_print_bring = debug_print_bring
        self._meta_pool = meta_pool
        self._team_pool_keys = list(team_pool_keys) if team_pool_keys is not None else None
        self._active_alpha_key = self._team_alpha_key
        self._active_beta_key = self._team_beta_key

        self._joints = enumerate_joint_actions_structural()
        self._n_battle_flat = len(self._joints) * FORM_ACTION_BRANCHES

        if self._six_mon_bring:
            self._n_action = BRING_ACTION_SPACE_SIZE + self._n_battle_flat
            self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(DOUBLES_OBS_WITH_SIX_BRING_DIM,), dtype=np.float32)
        else:
            self._n_action = self._n_battle_flat
            self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(DOUBLES_OBS_TOTAL_DIM,), dtype=np.float32)

        self.action_space = spaces.Discrete(self._n_action)

        self._rng = np.random.default_rng(seed)
        self._py_rng = random.Random(seed)
        self._state: DoublesBattleState | None = None
        self._awaiting_bring = False
        self._reg_party_a: list[dict[str, Any]] | None = None
        self._reg_party_b: list[dict[str, Any]] | None = None
        self._step_count = 0

    def _emit_bring_debug(self, alpha_bring_id: int, beta_bring_id: int) -> None:
        if not self._debug_print_bring or self._state is None:
            return

        print(format_six_bring_lead_prefs_line(self._state, alpha_bring_id=alpha_bring_id, beta_bring_id=beta_bring_id), flush=True)

    def _obs_vec(self) -> np.ndarray:
        if self._six_mon_bring and self._awaiting_bring and self._reg_party_a is not None and self._reg_party_b is not None:
            return doubles_rl_six_bring_observation(
                None,
                party_a_full=self._reg_party_a,
                party_b_full=self._reg_party_b,
                game=self._game,
                bring_phase=True,
                allow_mega_evolution=self._allow_mega_evolution,
                allow_terastal=self._allow_terastal,
            )

        assert self._state is not None

        if self._six_mon_bring:
            return doubles_rl_six_bring_observation(
                self._state,
                party_a_full=self._state.party_a,
                party_b_full=self._state.party_b,
                game=self._game,
                bring_phase=False,
                allow_mega_evolution=self._allow_mega_evolution,
                allow_terastal=self._allow_terastal,
            )

        return doubles_obs_vector(
            self._state,
            game=self._game,
            allow_mega_evolution=self._allow_mega_evolution,
            allow_terastal=self._allow_terastal,
        )

    def action_masks(self) -> np.ndarray:
        if self._six_mon_bring and self._awaiting_bring:
            m = np.zeros(self._n_action, dtype=np.bool_)
            m[:BRING_ACTION_SPACE_SIZE] = True

            return m

        if self._state is None:
            return np.zeros(self._n_action, dtype=np.bool_)

        mb = legal_flat_mask_alpha(
            self._state,
            self._joints,
            game=self._game,
            allow_mega_evolution=self._allow_mega_evolution,
            allow_terastal=self._allow_terastal,
        )

        if self._six_mon_bring:
            m = np.zeros(self._n_action, dtype=np.bool_)
            m[BRING_ACTION_SPACE_SIZE :] = np.asarray(mb, dtype=np.bool_)

            return m

        return np.asarray(mb, dtype=np.bool_)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)

        if seed is not None:
            self._rng = np.random.default_rng(seed)
            self._py_rng = random.Random(int(seed))

        if self._six_mon_bring:
            self._active_alpha_key, self._active_beta_key, self._reg_party_a, self._reg_party_b = prepare_parties_for_reset(
                team_alpha_key=self._team_alpha_key,
                team_beta_key=self._team_beta_key,
                meta_pool=self._meta_pool,
                team_pool_keys=self._team_pool_keys,
                rng=self._py_rng,
                six_mon_bring=True,
                expected_party_len=6,
            )

            if self._random_pair_bring_on_reset:
                ab = int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE))
                bb = int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE))

                self._state = battle_state_from_bring_actions(self._reg_party_a, self._reg_party_b, ab, bb)
                apply_initial_field_weather(self._state)
                self._awaiting_bring = False
                self._step_count = 0
                self._emit_bring_debug(ab, bb)

                mask_a = self.action_masks()

                return self._obs_vec(), {
                    "legal_actions_mask": mask_a,
                    "awaiting_bring": False,
                    "alpha_bring_action": ab,
                    "beta_bring_action": bb,
                    "team_alpha_key": self._active_alpha_key,
                    "team_beta_key": self._active_beta_key,
                }

            self._state = None
            self._awaiting_bring = True
            self._step_count = 0

            mask_a = self.action_masks()

            return self._obs_vec(), {
                "legal_actions_mask": mask_a,
                "awaiting_bring": True,
                "team_alpha_key": self._active_alpha_key,
                "team_beta_key": self._active_beta_key,
            }

        self._active_alpha_key, self._active_beta_key, party_a, party_b = prepare_parties_for_reset(
            team_alpha_key=self._team_alpha_key,
            team_beta_key=self._team_beta_key,
            meta_pool=False,
            team_pool_keys=self._team_pool_keys,
            rng=self._py_rng,
            six_mon_bring=False,
            expected_party_len=4,
        )

        self._state = DoublesBattleState(
            party_a=party_a,
            party_b=party_b,
            leads_a=list(self._alpha_field),
            leads_b=list(self._beta_field),
        )

        self._awaiting_bring = False
        self._reg_party_a = None
        self._reg_party_b = None

        apply_initial_field_weather(self._state)
        self._step_count = 0

        assert self._state is not None

        mask_a = self.action_masks()

        return self._obs_vec(), {
            "legal_actions_mask": mask_a,
            "awaiting_bring": False,
            "team_alpha_key": self._active_alpha_key,
            "team_beta_key": self._active_beta_key,
        }

    def step(self, action: SupportsFloat) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        raw = int(action)

        if self._six_mon_bring and self._awaiting_bring:
            if not (0 <= raw < self._n_action):
                raise ValueError(f"action {raw} out of range [0, {self._n_action})")

            mask = self.action_masks()

            if not bool(mask[raw]) or raw >= BRING_ACTION_SPACE_SIZE:
                legal_fix = np.flatnonzero(mask[:BRING_ACTION_SPACE_SIZE])

                if legal_fix.size == 0:
                    raise RuntimeError("no legal bring actions")

                raw = int(self._rng.choice(legal_fix))

            alpha_bring = int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE)) if self._random_bring_alpha else raw

            if self._random_bring_beta:
                beta_bring = int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE))
            elif self._beta_policy_model is not None:
                obs_b = doubles_rl_six_bring_observation(
                    None,
                    party_a_full=self._reg_party_a,
                    party_b_full=self._reg_party_b,
                    game=self._game,
                    bring_phase=True,
                    allow_mega_evolution=self._allow_mega_evolution,
                    allow_terastal=self._allow_terastal,
                )
                mask_pb = np.zeros(self._n_action, dtype=np.bool_)
                mask_pb[:BRING_ACTION_SPACE_SIZE] = True
                bf = int(
                    predict_masked_joint_index(
                        self._beta_policy_model,
                        obs_b,
                        mask_pb,
                        deterministic=self._beta_policy_deterministic,
                    )
                )
                beta_bring = bf if 0 <= bf < BRING_ACTION_SPACE_SIZE else int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE))
            else:
                beta_bring = int(self._rng.integers(0, BRING_ACTION_SPACE_SIZE))

            assert self._reg_party_a is not None and self._reg_party_b is not None

            self._state = battle_state_from_bring_actions(self._reg_party_a, self._reg_party_b, alpha_bring, beta_bring)
            apply_initial_field_weather(self._state)
            self._awaiting_bring = False
            self._emit_bring_debug(alpha_bring, beta_bring)

            mask_next = self.action_masks()

            info = {
                "legal_actions_mask": mask_next,
                "events": [],
                "debug": {},
                "alpha_joint_index": -1,
                "beta_joint_index": -1,
                "party_wiped_alpha": side_party_wiped_brought(self._state, alpha=True),
                "party_wiped_beta": side_party_wiped_brought(self._state, alpha=False),
                "awaiting_bring": False,
                "alpha_bring_action": alpha_bring,
                "beta_bring_action": beta_bring,
            }

            attach_bring_replay_frame(
                info,
                state_after_bring=self._state,
                game=self._game,
                alpha_bring_id=alpha_bring,
                beta_bring_id=beta_bring,
            )

            return self._obs_vec(), 0.0, False, False, info

        if self._state is None:
            raise RuntimeError("Call reset() before step()")

        n_j = len(self._joints)

        if self._six_mon_bring:
            mask_full = self.action_masks()

            if not (0 <= raw < self._n_action):
                raise ValueError(f"action {raw} out of range [0, {self._n_action})")

            if not bool(mask_full[raw]):
                legal_fix = np.flatnonzero(mask_full)

                if legal_fix.size == 0:
                    self._step_count += 1

                    obs = self._obs_vec()
                    mask_next = self.action_masks()

                    info = {
                        "legal_actions_mask": mask_next,
                        "events": [],
                        "debug": {},
                        "beta_joint_index": -1,
                        "party_wiped_alpha": side_party_wiped_brought(self._state, alpha=True),
                        "party_wiped_beta": side_party_wiped_brought(self._state, alpha=False),
                        "awaiting_bring": False,
                    }

                    return obs, -1.0, True, False, info

                raw = int(self._rng.choice(legal_fix))

            flat_a = raw - BRING_ACTION_SPACE_SIZE
        else:
            flat_a = raw

            if not (0 <= flat_a < self._n_battle_flat):
                raise ValueError(f"action {flat_a} out of range [0, {self._n_battle_flat})")

        mask_a = legal_flat_mask_alpha(
            self._state,
            self._joints,
            game=self._game,
            allow_mega_evolution=self._allow_mega_evolution,
            allow_terastal=self._allow_terastal,
        )

        if not bool(mask_a[flat_a]):
            legal_fix = np.flatnonzero(mask_a)

            if legal_fix.size == 0:
                self._step_count += 1

                obs = self._obs_vec()
                mask_next = self.action_masks()

                info = {
                    "legal_actions_mask": mask_next,
                    "events": [],
                    "debug": {},
                    "beta_joint_index": -1,
                    "party_wiped_alpha": side_party_wiped_brought(self._state, alpha=True),
                    "party_wiped_beta": side_party_wiped_brought(self._state, alpha=False),
                    "awaiting_bring": False,
                }

                return obs, -1.0, True, False, info

            flat_a = int(self._rng.choice(legal_fix))

        branch_a, ji_a = decode_flat_form_action(flat_a, n_j)
        mega_alpha, tera_alpha = split_form_branch_for_game(branch_a, self._game)

        mask_fb = legal_flat_mask_beta(
            self._state,
            self._joints,
            game=self._game,
            allow_mega_evolution=self._allow_mega_evolution,
            allow_terastal=self._allow_terastal,
        )
        legal_fb = np.flatnonzero(mask_fb)

        if legal_fb.size == 0:
            self._step_count += 1

            obs = self._obs_vec()
            mask_next = self.action_masks()

            info = {
                "legal_actions_mask": mask_next,
                "events": [],
                "debug": {},
                "beta_joint_index": -1,
                "party_wiped_alpha": side_party_wiped_brought(self._state, alpha=True),
                "party_wiped_beta": side_party_wiped_brought(self._state, alpha=False),
                "awaiting_bring": False,
            }

            return obs, 1.0, True, False, info

        obs_pre = self._obs_vec()

        if self._beta_policy_model is not None:
            mask_for_beta = (
                np.concatenate(
                    [
                        np.zeros(BRING_ACTION_SPACE_SIZE, dtype=np.bool_),
                        np.asarray(mask_fb, dtype=np.bool_),
                    ]
                )
                if self._six_mon_bring
                else np.asarray(mask_fb, dtype=np.bool_)
            )
            beta_flat = predict_masked_joint_index(
                self._beta_policy_model,
                obs_pre,
                mask_for_beta,
                deterministic=self._beta_policy_deterministic,
            )
            bf = int(beta_flat)

            if self._six_mon_bring:
                if bf >= BRING_ACTION_SPACE_SIZE:
                    bf -= BRING_ACTION_SPACE_SIZE
                else:
                    bf = int(self._rng.choice(legal_fb))

            branch_b, ji_b = decode_flat_form_action(bf, n_j)
        else:
            beta_flat = int(self._rng.choice(legal_fb))
            branch_b, ji_b = decode_flat_form_action(beta_flat, n_j)

        mega_beta, tera_beta = split_form_branch_for_game(branch_b, self._game)

        j_alpha = self._joints[ji_a]
        j_beta = self._joints[ji_b]

        state_before = deepcopy(self._state)

        planned_alpha = joint_to_planned_side(
            j_alpha,
            self._state.party_a,
            self._state.leads_a,
            atk_side="alpha",
            serial_base=0,
            brought=self._state.brought_alpha_sorted(),
        )
        planned_beta = joint_to_planned_side(
            j_beta,
            self._state.party_b,
            self._state.leads_b,
            atk_side="beta",
            serial_base=2,
            brought=self._state.brought_beta_sorted(),
        )

        reward, terminated, events, debug = resolve_turn(
            self._state,
            self._py_rng,
            self._oracle,
            self._game,
            planned_alpha,
            planned_beta,
            mega_alpha=mega_alpha,
            mega_beta=mega_beta,
            tera_alpha=tera_alpha,
            tera_beta=tera_beta,
            allow_mega_evolution=self._allow_mega_evolution,
            allow_terastal=self._allow_terastal,
            reward_shaping=self._reward_shaping,
        )

        self._step_count += 1
        terminated, truncated, forced_outcome = apply_step_cap_as_decisive_end(
            self._state,
            step_count=self._step_count,
            max_steps=self._max_steps,
            terminated=bool(terminated),
        )

        if forced_outcome is not None:
            reward = alpha_reward_for_outcome(forced_outcome)

        mask_next = self.action_masks()

        obs = self._obs_vec()

        info = {
            "legal_actions_mask": mask_next,
            "events": events,
            "debug": debug,
            "alpha_joint_index": ji_a,
            "beta_joint_index": ji_b,
            "party_wiped_alpha": side_party_wiped_brought(self._state, alpha=True),
            "party_wiped_beta": side_party_wiped_brought(self._state, alpha=False),
            "awaiting_bring": False,
        }

        attach_turn_replay_frame(
            info,
            state_before=state_before,
            game=self._game,
            step_index=self._step_count,
            joints=self._joints,
            joint_index_alpha=ji_a,
            joint_index_beta=ji_b,
            mega_alpha=mega_alpha,
            mega_beta=mega_beta,
            tera_alpha=tera_alpha,
            tera_beta=tera_beta,
            events=events,
            reward=float(reward),
            terminated=bool(terminated),
            truncated=bool(truncated),
        )

        return obs, float(reward), terminated, truncated, info


def make_oracle_doubles_rl_env(**kwargs: Any) -> OracleDoublesRlEnv:
    return OracleDoublesRlEnv(**kwargs)
