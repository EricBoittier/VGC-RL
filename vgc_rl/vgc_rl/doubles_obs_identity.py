from __future__ import annotations

import json
import zlib
from functools import lru_cache
from importlib import resources
from typing import Any

import numpy as np

from vgc_rl.doubles_turn_engine import normalize_mon_boosts

DOUBLES_OBS_SCALAR_DIM = 18
DOUBLES_OBS_BOOST_DIM = 40
DOUBLES_OBS_IDENTITY_PER_SLOT = 7
DOUBLES_OBS_PARTY_SLOTS = 8
DOUBLES_OBS_IDENTITY_DIM = DOUBLES_OBS_IDENTITY_PER_SLOT * DOUBLES_OBS_PARTY_SLOTS
DOUBLES_OBS_TOTAL_DIM = DOUBLES_OBS_SCALAR_DIM + DOUBLES_OBS_BOOST_DIM + DOUBLES_OBS_IDENTITY_DIM

DOUBLES_RL_BRING_TAIL_DIM = 13
DOUBLES_OBS_WITH_SIX_BRING_DIM = DOUBLES_OBS_TOTAL_DIM + DOUBLES_RL_BRING_TAIL_DIM

DOUBLES_OBS_BATTLE_DIM = DOUBLES_OBS_SCALAR_DIM


@lru_cache(maxsize=1)
def load_obs_vocab() -> dict[str, list[str]]:
    raw = resources.files("vgc_rl").joinpath("examples/vocab.json").read_text(encoding="utf-8")
    data = json.loads(raw)

    return {
        "species": list(data.get("species") or []),
        "moves": list(data.get("moves") or []),
        "abilities": list(data.get("abilities") or []),
        "items": list(data.get("items") or []),
    }


@lru_cache(maxsize=1)
def _vocab_sizes_and_maps() -> tuple[int, int, int, int, dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    vocab = load_obs_vocab()
    species_list = vocab["species"]
    move_list = vocab["moves"]
    ability_list = vocab["abilities"]
    item_list = vocab["items"]

    smap = {n: i for i, n in enumerate(species_list)}
    mmap = {n: i for i, n in enumerate(move_list)}
    amap = {n: i for i, n in enumerate(ability_list)}
    imap = {n: i for i, n in enumerate(item_list)}

    return (
        len(species_list),
        len(move_list),
        len(ability_list),
        len(item_list),
        smap,
        mmap,
        amap,
        imap,
    )


def obs_vocab_sizes() -> dict[str, int]:
    ns, nm, na, ni, _, _, _, _ = _vocab_sizes_and_maps()

    return {"species": ns, "moves": nm, "abilities": na, "items": ni}


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
    ns, nm, na, ni, smap, mmap, amap, imap = _vocab_sizes_and_maps()
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

            parts.append(_feat_from_vocab_or_hash(str(mon.get("ability") or ""), amap, na))
            parts.append(_feat_from_vocab_or_hash(str(mon.get("item") or ""), imap, ni))

    return np.asarray(parts, dtype=np.float32)
