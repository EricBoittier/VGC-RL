from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from vgc_rl.doubles_turn_engine import DoublesBattleState
from vgc_rl.example_teams import party_member
from vgc_rl.fake_oracle_client import FakeOracleClient
from vgc_rl.oracle_doubles_rl_env import OracleDoublesRlEnv
from vgc_rl.replay import REPLAY_SCHEMA_VERSION, attach_turn_replay_frame, build_replay_document, list_replay_files, write_replay
from vgc_rl.replay_recorder import ReplayCaptureWrapper


def test_replay_frame_and_write(tmp_path: Path) -> None:
    party_a = [party_member("team_alpha", i) for i in range(4)]
    party_b = [party_member("team_beta", i) for i in range(4)]

    for m in party_a + party_b:
        m["hpPercentage"] = 100

    state = DoublesBattleState(party_a=party_a, party_b=party_b, leads_a=[0, 1], leads_b=[0, 3])
    info: dict = {}
    attach_turn_replay_frame(
        info,
        state_before=state,
        game="champions",
        step_index=1,
        joints=(),
        joint_index_alpha=-1,
        joint_index_beta=-1,
        mega_alpha=False,
        mega_beta=False,
        tera_alpha=False,
        tera_beta=False,
        events=[("move", "Alpha used Tackle.")],
        reward=0.0,
        terminated=False,
    )

    doc = build_replay_document(
        game="champions",
        meta={"phase": "test"},
        initial_state=None,
        frames=[info["replay_frame"]],
        final_state=None,
        outcome="ongoing",
    )
    path = write_replay(tmp_path / "sample.json", doc)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["schema_version"] == REPLAY_SCHEMA_VERSION
    assert loaded["frames"][0]["events"][0] == ["move", "Alpha used Tackle."]
    assert list_replay_files(tmp_path)[0].name == "sample.json"


def test_replay_capture_wrapper_saves_on_episode(tmp_path: Path) -> None:
    env = OracleDoublesRlEnv(oracle=FakeOracleClient(), game="champions", seed=0, max_steps=4)
    wrapped = ReplayCaptureWrapper(env, save_dir=tmp_path, save_every_n_episodes=1, enabled=True)
    obs, _ = wrapped.reset(seed=0)
    done = False
    steps = 0

    while not done and steps < 16:
        mask = wrapped.env.unwrapped.action_masks()
        legal = np.flatnonzero(mask)

        if legal.size == 0:
            break

        obs, _r, term, trunc, info = wrapped.step(int(legal[0]))
        done = bool(term or trunc)
        steps += 1

        if info.get("replay_frame") is None and steps > 1:
            continue

    files = list_replay_files(tmp_path)

    assert files, "expected at least one replay json"
