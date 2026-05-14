from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def team_file_sha256(path: str | Path) -> str:
    raw = Path(path).read_bytes()

    return hashlib.sha256(raw).hexdigest()


def load_team_party(path: str | Path) -> tuple[str | None, list[dict[str, Any]]]:
    p = Path(path)

    data = json.loads(p.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"team JSON must be an object: {p}")

    party = data.get("party")

    if not isinstance(party, list):
        raise ValueError(f'team JSON requires "party" array: {p}')

    if len(party) not in (4, 6):
        raise ValueError(f'team JSON "party" must have length 4 or 6 (got {len(party)}): {p}')

    label = data.get("label")

    if label is not None:
        label = str(label)

    return label, [dict(x) for x in party]
