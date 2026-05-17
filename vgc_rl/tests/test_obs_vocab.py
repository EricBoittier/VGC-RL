from __future__ import annotations

from vgc_rl.doubles_obs_identity import DOUBLES_OBS_IDENTITY_DIM, DOUBLES_OBS_TOTAL_DIM, load_obs_vocab, obs_vocab_sizes


def test_vocab_covers_meta_pool() -> None:
    vocab = load_obs_vocab()
    sizes = obs_vocab_sizes()

    assert sizes["species"] >= 100
    assert "Gengar-Mega" in vocab["species"]
    assert "Charizard-Mega-Y" in vocab["species"]
    assert sizes["moves"] >= 150
    assert sizes["abilities"] >= 50
    assert sizes["items"] >= 40
    assert "Sneasler" in vocab["species"]
    assert "Kingambit" in vocab["species"]


def test_obs_dims_with_ability_item_identity() -> None:
    assert DOUBLES_OBS_IDENTITY_DIM == 56
    assert DOUBLES_OBS_TOTAL_DIM == 114
