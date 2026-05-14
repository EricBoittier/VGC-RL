from __future__ import annotations

import zlib
from functools import lru_cache
from typing import Any

import numpy as np

from vgc_rl.example_teams import load_example_teams

from vgc_rl.doubles_turn_engine import normalize_mon_boosts

DOUBLES_OBS_SCALAR_DIM = 18
DOUBLES_OBS_BOOST_DIM = 40
DOUBLES_OBS_IDENTITY_PER_SLOT = 5
DOUBLES_OBS_PARTY_SLOTS = 8
DOUBLES_OBS_IDENTITY_DIM = DOUBLES_OBS_IDENTITY_PER_SLOT * DOUBLES_OBS_PARTY_SLOTS
DOUBLES_OBS_TOTAL_DIM = DOUBLES_OBS_SCALAR_DIM + DOUBLES_OBS_BOOST_DIM + DOUBLES_OBS_IDENTITY_DIM

DOUBLES_RL_BRING_TAIL_DIM = 13
DOUBLES_OBS_WITH_SIX_BRING_DIM = DOUBLES_OBS_TOTAL_DIM + DOUBLES_RL_BRING_TAIL_DIM

DOUBLES_OBS_BATTLE_DIM = DOUBLES_OBS_SCALAR_DIM


@lru_cache(maxsize=1)
def _vocab_sizes_and_maps() -> tuple[int, int, dict[str, int], dict[str, int]]:
    data = load_example_teams()
    species: set[str] = set()
    moves: set[str] = set()

    for tk in sorted(k for k in data if str(k).startswith("team_")):
        block = data.get(tk)

        if not isinstance(block, dict) or not isinstance(block.get("party"), list):
            continue

        for mon in block["party"]:
            species.add(str(mon["name"]))

            for mv in mon["moves"]:
                moves.add(str(mv["name"]))

    species_list = sorted(species)
    move_list = sorted(moves)
    smap = {n: i for i, n in enumerate(species_list)}
    mmap = {n: i for i, n in enumerate(move_list)}

    return len(species_list), len(move_list), smap, mmap


def _norm_vocab(idx: int, size: int) -> float:
    if size <= 1:
        return 0.5

    return idx / (size - 1)


def _feat_from_vocab_or_hash(label: str, vmap: dict[str, int], size: int) -> float:
    if label in vmap:
        return float(_norm_vocab(vmap[label], size))

    return float(zlib.adler32(label.encode("utf-8")) % 1_000_003) / 1_000_003.0


_BOOST_KEYS = ("atk", "def", "spa", "spd", "spe")


def doubles_obs_boost_features(party_a: list[dict[str, Any]], party_b: list[dict[str, Any]]) -> np.ndarray:
    parts: list[float] = []

    for party in (party_a, party_b):
        for mon in party:
            normalize_mon_boosts(mon)

            b = mon["boosts"]

            for k in _BOOST_KEYS:
                v = int(b[k])
                parts.append(float(v + 6) / 12.0)

    return np.asarray(parts, dtype=np.float32)


def doubles_obs_identity_features(party_a: list[dict[str, Any]], party_b: list[dict[str, Any]]) -> np.ndarray:
    ns, nm, smap, mmap = _vocab_sizes_and_maps()
    parts: list[float] = []

    for party in (party_a, party_b):
        for mon in party:
            parts.append(_feat_from_vocab_or_hash(str(mon.get("name", "?")), smap, ns))

            for j in range(4):
                mv = "?"

                try:
                    mv = str(mon["moves"][j]["name"])
                except (KeyError, IndexError, TypeError):
                    pass

                parts.append(_feat_from_vocab_or_hash(mv, mmap, nm))

    return np.asarray(parts, dtype=np.float32)
