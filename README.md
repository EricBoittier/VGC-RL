# VGC RL

Reinforcement learning and oracle-backed doubles battle simulation for **Pokémon Champions** (VGC-style), built on the [VGC Multi Calc](https://github.com/ericburcham/VGC-Multi-Calc) codebase.

Train a **MaskablePPO** policy that generalizes across meta teams (species, moves, items, mega evolution), play against it interactively, or use the bundled damage calculator web app.

## Repository layout

| Path | Role |
|------|------|
| [`vgc_rl/`](vgc_rl/README.md) | Python package: Gymnasium envs, CLI (`vgc-rl`), training scripts, meta team pool |
| [`oracle-server/`](oracle-server/README.md) | HTTP oracle for damage, speed, and batch battle requests |
| [`src/`](src/) | Angular **VGC Multi Calc** web UI (team building, damage calc) |
| [`vgc_rl/vgc_rl/examples/meta_teams/`](vgc_rl/vgc_rl/examples/meta_teams/) | Imported competitive teams (Showdown paste + oracle JSON) |

## Quick start (RL training)

**1. Install Python deps** (base + training stack):

```bash
cd vgc_rl
uv sync --extra train
```

Add `--extra dev` for pytest.

**2. Train** with fake oracle (no `oracle-server` required):

```bash
uv run python train_alternate_self_play_cpu.py --fake-oracle --six-bring --meta-pool \
  --random-pair-bring-on-reset --alternating-rounds 4 --steps-per-phase 4096
```

**3. Train against live oracle** (terminal A):

```bash
cd oracle-server && npm install && npm start
```

Terminal B:

```bash
cd vgc_rl
export ORACLE_URL=http://127.0.0.1:8765
uv run python train_alternate_self_play_cpu.py --six-bring --meta-pool \
  --replay-dir replays --replay-every-episodes 15
```

**4. Play vs a saved policy:**

```bash
vgc-rl play-doubles --beta-policy path/to/beta_policy.zip
```

See [`vgc_rl/README.md`](vgc_rl/README.md) for observation dimensions (114 / 127 with six-bring), action masking, fine-tuning (`--init-policy`, `--finetune`), replay viewer, and CLI commands.

## Meta teams

Sixty-one teams from Pokepaste are stored under `vgc_rl/vgc_rl/examples/meta_teams/`. Re-import or refresh vocabulary:

```bash
uv run python vgc_rl/scripts/import_meta_teams.py
uv run python vgc_rl/scripts/build_obs_vocab.py
node vgc_rl/scripts/export_mega_evolution_champions.mjs
```

## Web calculator

The root app is an Angular project (see `package.json`). Typical dev flow:

```bash
npm install
npm start
```

## License

Based on MultiCalc VGC, licensed under the MIT License. See [LICENSE](LICENSE).
