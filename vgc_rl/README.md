# VGC RL (Python)

Feature-only oracle integration against [`oracle-server`](../oracle-server/README.md), plus a minimal [Gymnasium](https://gymnasium.farama.org/) toy env that stacks oracle-derived floats after each reset.

Treat HTTP responses as extra observation channels: KO text, damage percent range, roll-derived stats. Reward shaping and MCTS notes stay research-side until you wire a real battle simulator.

## Serving (two processes)

**Terminal A — oracle HTTP API**

```bash
cd oracle-server
npm install
npm start
```

**Terminal B — Python env**

```bash
cd vgc_rl
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vgc-rl smoke
vgc-rl demo-env
```

Optional: `export ORACLE_URL=http://127.0.0.1:8765`

Commands:

- `vgc-rl smoke` — `GET /health` and sample `POST /batch`
- `vgc-rl demo-env` — `OracleFeatureToyEnv.reset()` against the live oracle
- `vgc-rl list-actions` — print structural doubles action counts and samples
- `vgc-rl rl-env-smoke` — reset **`vgc_rl/OracleDoubles-v0`** and take random **legal** joint actions against the live oracle (`--steps`, `--seed`)
- `vgc-rl example-battle` — oracle damage check between two packaged example teams
- `vgc-rl simulate-turn1` — scripted multi-turn demo with oracle initiative order and colored Rich log (`--verbose` adds a style legend)
- `vgc-rl self-play` — Rich **field snapshot** each turn plus **Showdown-style** pipe logs (`|field|`, `|move|`, `|switch|`, `|-damage|`, …); Tailwind ticks; Protect stall RNG. Default is **1v1** (`--alpha-slot` / `--beta-slot`). **`--doubles`** simulates a **full party 4v4 HP pool** (indices `0–3`): two field slots per trainer (`--alpha-field` / `--beta-field` set starters), **bench** rows under the 2×2 grid, **switch phase** (oracle-ordered) then **move phase**, with **`--switch-rate`** controlling random switches (KO’d slots force a switch when the bench has living Pokémon).
- `vgc-rl play-doubles` — **Interactive** doubles vs the oracle: per side you pick **Lead A** then **Lead B** actions from move names and bench switches; if a move allows several targets, a short target submenu appears (`--mode human-random` uses random legal Beta unless **`--beta-policy PATH`**; **`--two-player`** / **`--mode human-human`** prompts both sides and cannot pair with **`--beta-policy`**). **`--beta-stochastic`** samples Beta policy actions. **`--save-checkpoint`** / **`--save PATH`** writes JSON after each turn and **reloads that path on startup when it already exists** unless **`--fresh-start`** or **`--load-checkpoint OTHER`**. **`--log-trajectory`** logs global **`joint#`** indices (5826-way structural ids, same as **`vgc_rl/OracleDoubles-v0`**).
- `vgc-rl showcase-doubles` — **No stdin**: watch both sides act (**random legal** by default, or **`--alpha-policy`** / **`--beta-policy`** MaskablePPO zips). **`--turns`**, **`--delay`**, **`--seed`**, fields match **`play-doubles`**.

## Interactive doubles detail

Requires a **live oracle**. The CLI resolves choices to the same **global joint index** used by **`vgc_rl/OracleDoubles-v0`**; trajectory JSON still stores `joint_idx_*` plus human-readable labels. Two-player logs label **both** sides’ choices each turn.

## Goal: trainable opponent you can play against

End state: a **random-init neural policy** trained with **Stable-Baselines3** and **PyTorch** (**CPU-only for now**; GPU optional later), saved as an SB3 artifact (e.g. **`*.zip`**), that acts as **Beta** while you play Alpha—then **keep improving** it from env rollouts and/or logged human games.

**Dependency split**

- Default **`pip install -e .`** / **`uv sync`** keeps **`vgc-rl`** light (oracle + Gymnasium only).
- Training is **CPU-only for now**: install SB3 + PyTorch in the **same virtualenv** (or a sibling training repo). Example for CPU wheels: install [**PyTorch CPU**](https://pytorch.org/get-started/locally/) for your OS, then **`pip install stable-baselines3`**. CUDA builds are optional later when you want GPU rollouts. Keeping SB3 **out of this package’s dependency closure** avoids pinning huge CUDA stacks in **`uv.lock`** and Gymnasium version churn.

**Suggested improvement loop**

1. **`vgc-rl self-play --doubles …`** — confirm oracle + dynamics (RNG doubles baseline).
2. **`vgc-rl play-doubles --log-trajectory demos.jsonl …`** — capture labeled joints (`joint_idx_alpha`, `joint_idx_beta`, `obs_before`, legal-index lists); `--two-player` gives teacher labels on both sides.
3. **Train Beta (online RL)** — install **`sb3-contrib`** plus SB3/PyTorch (**CPU**). Either `gym.make("vgc_rl/BetaOracleDoubles-v0", oracle=..., ...)` after **`register_vgc_envs()`**, or run the packaged CPU example:

```bash
cd vgc_rl
pip install sb3-contrib stable-baselines3 torch
python train_beta_maskable_ppo_cpu.py --fake-oracle --timesteps 4096 --save beta_policy.zip
```

Re-running with the same **`--save`** path loads that zip and continues (**`learn(..., reset_num_timesteps=False)`**); SB3’s rollout table then shows cumulative timesteps. Use **`--fresh-start`** to ignore an existing zip and train from scratch (required if the zip was trained on the old **14-D** observation — SB3 will reject mismatched net inputs otherwise). **`--learning-rate`** defaults to **`1e-3`** in this script (SB3’s usual default is **`3e-4`**); lower it if updates become unstable (KL spikes, reward collapses). The env exposes **`BetaControlledOracleDoublesEnv.observation_space` shape **`(54,)`**: **14** battle floats plus **40** slot identity floats (species + four moves per party slot), same layout as **`play-doubles`** / trajectory **`obs_before`\*\*.

(`BetaControlledOracleDoublesEnv` exposes **`action_masks()`** for **MaskablePPO**; sparse reward is **Beta-centric** via sign flip vs Alpha env.)

**Optional iterative self-play (frozen opponent each phase):** `python train_alternate_self_play_cpu.py --fake-oracle --alternating-rounds 4 --steps-per-phase 4096` alternates **Beta.learn** vs random Alpha (first round) or frozen **`alpha_policy_selfplay.zip`**, then **Alpha.learn** vs frozen **`beta_policy_selfplay.zip`** (same weights Beta just trained), repeating. Outputs **`--save-alpha`** / **`--save-beta`** (defaults above). Use **`--fresh-start`** to ignore both zips; **`--opponent-stochastic`** samples frozen opponent actions.

4. **Save** — `model.save("beta_policy.zip")`.

5. **Play against it** — **`vgc-rl play-doubles --beta-policy beta_policy.zip`** with **`oracle-server`** running (use the same oracle you trained against). **`play-doubles`** loads **Beta** only for now; **Alpha** zips from alternating training are for **`OracleDoublesRlEnv`** or future CLI wiring. Older **`beta_policy.zip`** files trained on the previous **14-dimensional** observation must be **retrained** after this change.

**Offline / hybrid:** behavioral cloning or auxiliary losses from JSONL (`joint_idx_beta`, …) in your own notebooks—SB3 does not ship BC here.

Trajectory rows are plain JSON objects per turn (`step_index`, `obs_before`, legal joint index lists, `joint_idx_*`, `reward`, `terminated`, …), aligned with the shared observation layout (**14** battle scalars plus **40** slot identity floats: species + four move names per party slot, normalized from `example_teams` vocab with deterministic hash fallback for unknown strings — **54** floats total).

The **`OracleDoubles-v0`** section below shows minimal **`gym.make`** usage when the **Alpha** side is the RL agent; **`BetaOracleDoubles-v0`** mirrors it for **Beta** training.

## Example teams (Pokémon Champions)

Bundled squads use species present in **SETDEX_CHAMPIONS** (`game: champions`). Showdown text lists six Pokémon per side; `example_teams.json` carries the **first four** of each list for the oracle fixture (indices `0–3`).

Files under [`vgc_rl/examples/`](vgc_rl/vgc_rl/examples/README.md):

- `team_alpha_showdown.txt`, `team_beta_showdown.txt` — paste-style blocks
- `example_teams.json` — oracle payloads (**four** Pokémon per side; indices `0–1` field leads, `2–3` bench)

```bash
vgc-rl example-battle
vgc-rl example-battle --alpha-slot 1 --beta-slot 1 --kind allMoves
vgc-rl example-battle --sv
vgc-rl simulate-turn1
vgc-rl simulate-turn1 --verbose
vgc-rl self-play --turns 6 --seed 1 --alpha-slot 0 --beta-slot 0
```

Pass **`--sv`** only if you point `example_teams.json` at Scarlet/Violet builds; the default matchup assumes Pokémon Champions rules.

`simulate-turn1` resolves each scripted turn in **speed/initiative order** when `POST /batch` `speedCompare` succeeds; otherwise it keeps the **script order** for that turn. A lightweight **Protect** rule skips later damaging oracle rows that target the Protected party slot (**Protect is treated as always succeeding**; cartridge stall decay is not modeled there). Output is a pipe-style trace with **Rich** colors. **`--verbose`** prints a short style legend. `self-play` is a smoke harness—not a full doubles simulator—until battle rules land server-side.

Python: `from vgc_rl.example_teams import load_example_teams, example_battle_batch_body`.

## VGC doubles custom env (action enumeration)

Design follows the usual Gymnasium layout ([Create a custom environment](https://gymnasium.farama.org/introduction/create_custom_env/)).

**Party layout:** each trainer uses **four** Pokémon in the battle team: **two on the field** and **two on the bench** (official doubles squad size when four are selected). The agent issues one intent per **field** slot per turn (selection phase).

Opposing side mirrors that layout (four Pokémon total per trainer); globally eight Pokémon are involved in the match, four per player.

**Structural slots** ([`vgc_rl/doubles_actions.py`](vgc_rl/doubles_actions.py)):

- Per active: **move** — `(move_slot 0–3, target)` with `DoublesTarget` as a coarse doubles-facing enum (`FOE_SLOT_0`, `FOE_SLOT_1`, `ALLY_ACTIVE`, `SELF`, `BOTH_FOES`, `FIELD`, `NONE`).
- Per active: **switch** — `bench_index` over **`DEFAULT_BENCH_SLOTS` = 2** (the two bench Pokémon).

Default counts: **86** slot actions (= 4×7 move/target combos for living actives + **2** voluntary switches + **2×4×7** faint **send-out + first-turn move** combos), **5826** joint pairs (= 86² minus pairs where **both** slots pick the **same** bench index as **voluntary** double-switch or **faint** double-send-out). Most pairs are still **illegal** for real battles until you add rules and **action masking** ([Action masking tutorial](https://gymnasium.farama.org/tutorials/training_agents/action_masking_taxi_env/)).

```python
import gymnasium as gym
from vgc_rl.doubles_env import register_vgc_envs

register_vgc_envs()

env = gym.make("vgc_rl/VGC-Doubles-v0")
obs, info = env.reset()
obs2, r, term, trunc, info2 = env.step(0)
```

## RL training (`OracleDoubles-v0`)

Use this environment when you want **one Gymnasium step = one full doubles turn**: your policy picks Alpha’s **5826-way structural joint** (`enumerate_joint_actions_structural` in [`vgc_rl/doubles_actions.py`](vgc_rl/doubles_actions.py)); Beta samples a **uniform random legal joint** under the same masking rules (swap Beta for your SB3 policy when you integrate masking at inference). Switch and move phases call the HTTP oracle (`speedCompare` ordering, then `single` damage rows). Training runs need a **live oracle** (`oracle-server`); unit tests swap in a **`FakeOracleClient`** that returns deterministic batch rows.

**Targeting (v0):** coarse `DoublesTarget` slots in the structural enum are **not** passed through to damage resolution yet—damaging hits pick a **random living foe slot**, matching [`run_self_play_doubles`](vgc_rl/vgc_rl/self_play.py). Read `info["legal_actions_mask"]` each step for Alpha’s admissible discrete indices (Beta masking uses the same predicate on party B).

```python
import gymnasium as gym
import numpy as np

from vgc_rl.doubles_env import register_vgc_envs
from vgc_rl.oracle_client import OracleClient

register_vgc_envs()

env = gym.make(
    "vgc_rl/OracleDoubles-v0",
    oracle=OracleClient(base_url="http://127.0.0.1:8765"),
    game="champions",
    max_steps=128,
    seed=0,
)

obs, info = env.reset(seed=0)
mask = info["legal_actions_mask"]
legal = np.flatnonzero(mask)

obs2, reward, terminated, truncated, info2 = env.step(int(legal[0]))
```

Install **`pip install sb3-contrib`** (MaskablePPO) alongside SB3/PyTorch when you train or use **`--beta-policy`**; **`vgc-rl`** itself does not import torch until you load a policy.

## Library usage

```python
import gymnasium as gym
from vgc_rl.env import OracleFeatureToyEnv

env = OracleFeatureToyEnv(game="sv")
obs, info = env.reset()
```
