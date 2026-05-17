from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

OUT_PATH = Path(__file__).resolve().parent.parent / "vgc_rl" / "examples" / "vocab.json"


def _collect_from_party(party: list[dict[str, Any]], species: set[str], moves: set[str], abilities: set[str], items: set[str]) -> None:
    for mon in party:
        species.add(str(mon["name"]))

        ab = mon.get("ability")

        if ab:
            abilities.add(str(ab))

        it = mon.get("item")

        if it:
            items.add(str(it))

        for mv in mon.get("moves") or []:
            if isinstance(mv, dict) and mv.get("name"):
                moves.add(str(mv["name"]))


def _collect_from_teams_blob(data: dict[str, Any], species: set[str], moves: set[str], abilities: set[str], items: set[str]) -> None:
    for key, block in data.items():
        if key == "meta" or not isinstance(block, dict):
            continue

        party = block.get("party")

        if isinstance(party, list):
            _collect_from_party(party, species, moves, abilities, items)


def main() -> int:
    species: set[str] = set()
    moves: set[str] = set()
    abilities: set[str] = set()
    items: set[str] = set()

    example_path = resources.files("vgc_rl").joinpath("examples/example_teams.json")

    _collect_from_teams_blob(json.loads(example_path.read_text(encoding="utf-8")), species, moves, abilities, items)

    meta_dir = resources.files("vgc_rl").joinpath("examples/meta_teams")

    for entry in meta_dir.iterdir():
        if not str(entry.name).endswith(".json") or entry.name == "manifest.json":
            continue

        blob = json.loads(entry.read_text(encoding="utf-8"))
        party = blob.get("party")

        if isinstance(party, list):
            _collect_from_party(party, species, moves, abilities, items)

    vocab = {
        "version": 2,
        "sources": ["example_teams.json", "meta_teams/*.json"],
        "species": sorted(species),
        "moves": sorted(moves),
        "abilities": sorted(abilities),
        "items": sorted(items),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(vocab, indent=2) + "\n", encoding="utf-8")

    print(
        f"vocab → {OUT_PATH} · species={len(vocab['species'])} moves={len(vocab['moves'])} "
        f"abilities={len(vocab['abilities'])} items={len(vocab['items'])}",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
