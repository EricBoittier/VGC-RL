from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx

OUT_DIR = Path(__file__).resolve().parent.parent / "vgc_rl" / "examples" / "meta_teams"

URLS = [
    "https://pokepast.es/44c2d848ea8b9f24",
    "https://pokepast.es/174fb4599deb2ff1",
    "https://pokepast.es/19bfb6a4c2264cf9",
    "https://pokepast.es/80d837bcfa686f59",
    "https://pokepast.es/c12e5da78d0d38c4",
    "https://pokepast.es/afb93b0f4522a6e2",
    "https://pokepast.es/3f405eeb6bcfd036",
    "https://pokepast.es/ff0f6d9d49a3e703",
    "https://pokepast.es/53cb2a5b80f371d2",
    "https://pokepast.es/374287b23334e5bb",
    "https://pokepast.es/1205c758da04ffc1",
    "https://pokepast.es/6b4fb095fd343f1e",
    "https://pokepast.es/d466236588ebde30",
    "https://pokepast.es/47c0a153d7454020",
    "https://pokepast.es/11b2cb9752b1483b",
    "https://pokepast.es/08faae6de43bfd7b",
    "https://pokepast.es/7e5fee00c045d9cb",
    "https://pokepast.es/5890bfd7324e4c57",
    "https://pokepast.es/709aa0f59cca2cba",
    "https://pokepast.es/504d67dc8354f602",
    "https://pokepast.es/3b26c853abf7d9f4",
    "https://pokepast.es/c69adb1dda2cff20",
    "https://pokepast.es/ff7e147eba00ff6e",
    "https://pokepast.es/1d099b0c9536bca4",
    "https://pokepast.es/4b8de440eb41120f",
    "https://pokepast.es/50cbad627a62f5ea",
    "https://pokepast.es/eafdca3706c02574",
    "https://pokepast.es/f5ac5d30fedb98d5",
    "https://pokepast.es/3e07f5052c39e85b",
    "https://pokepast.es/bc99081e201154a0",
    "https://pokepast.es/f46e8c179f42a9b7",
    "https://pokepast.es/314825f9e17b700d",
    "https://pokepast.es/75a93b5efdd4ff0f",
    "https://pokepast.es/677e22143b1c107b",
    "https://pokepast.es/333dc97e13bcda20",
    "https://pokepast.es/8872710ff73c4b3f",
    "https://pokepast.es/971f560b85603f7d",
    "https://pokepast.es/6d8d8c857f2c380b",
    "https://pokepast.es/ae516ffce0fe7251",
    "https://pokepast.es/1a52952ee179797d",
    "https://pokepast.es/9c89d416fc111174",
    "https://pokepast.es/6ce53663f641c308",
    "https://pokepast.es/1a253a71a2077747",
    "https://pokepast.es/8e98aa5005367f06",
    "https://pokepast.es/cde5a715af3fff84",
    "https://pokepast.es/7ab2b2920d92280f",
    "https://pokepast.es/716dffe25a855236",
    "https://pokepast.es/fd62b2862d49c78b",
    "https://pokepast.es/d378e96b903dcff5",
    "https://pokepast.es/22d85b73d74b58d2",
    "https://pokepast.es/bb22c6441ed3116c",
    "https://pokepast.es/110f1ffe9d58776b",
    "https://pokepast.es/d4a4030826913c70",
    "https://pokepast.es/44dace349421e14c",
    "https://pokepast.es/bfcfc47093e5ed1b",
    "https://pokepast.es/0b77e085c8177eb3",
    "https://pokepast.es/a81abbf4ab14e717",
    "https://pokepast.es/ddd1e5c85adbef80",
    "https://pokepast.es/071ccbb83885360a",
    "https://pokepast.es/868af4a892140681",
    "https://pokepast.es/6fc20ff94dbb449c",
]

EV_STAT_MAP = {
    "hp": "hp",
    "atk": "atk",
    "attack": "atk",
    "def": "def",
    "defense": "def",
    "spa": "spa",
    "spatk": "spa",
    "sp. atk": "spa",
    "spd": "spd",
    "spdef": "spd",
    "sp. def": "spd",
    "spe": "spe",
    "speed": "spe",
}

ALT_FORM_BASES = {
    "Rockruff",
    "Polteageist",
    "Sinistea",
    "Sinistcha",
    "Vivillon",
    "Alcremie",
    "Dudunsparce",
    "Pikachu",
    "Flabébé",
    "Floette",
    "Florges",
    "Squawkabilly",
    "Maushold",
    "Tatsugiri",
    "Gastrodon",
}

SPECIES_LINE = re.compile(r"^(.+?)(?:\s*@\s*(.+))?$")
EV_LINE = re.compile(r"^EVs:\s*(.+)$", re.IGNORECASE)
EV_PART = re.compile(r"(\d+)\s+([A-Za-z. ]+?)(?:\s*/\s*|$)")


def pokepast_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def adjust_name(name: str) -> str:
    nick = re.match(r"^.+ \((.+)\)$", name)

    if nick and nick.group(1) not in ("M", "F"):
        name = nick.group(1)

    name = re.sub(r" \((M|F)\)$", "", name)

    if name.startswith("Floette"):
        return "Floette"

    if "-Mega" in name:
        name = name.split("-Mega", 1)[0]

    if "-" not in name:
        return name

    base = name.split("-", 1)[0]

    if base not in ALT_FORM_BASES:
        return name

    return base


def parse_evs(evs_text: str) -> dict[str, int]:
    out = {k: 0 for k in ("hp", "atk", "def", "spa", "spd", "spe")}

    for amount, stat_raw in EV_PART.findall(evs_text):
        key = EV_STAT_MAP.get(stat_raw.strip().lower())

        if key:
            out[key] = int(amount)

    return out


def parse_showdown_team(raw: str) -> list[dict]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()

        if not stripped:
            if current:
                blocks.append(current)
                current = []

            continue

        current.append(stripped)

    if current:
        blocks.append(current)

    party: list[dict] = []

    for block in blocks:
        mon: dict = {
            "name": "",
            "item": "",
            "ability": "",
            "nature": "",
            "teraType": "",
            "evs": {k: 0 for k in ("hp", "atk", "def", "spa", "spd", "spe")},
            "moves": [],
        }

        for line in block:
            if line.startswith("Ability:"):
                mon["ability"] = line.split(":", 1)[1].strip()

                continue

            if line.startswith("Tera Type:"):
                mon["teraType"] = line.split(":", 1)[1].strip()

                continue

            if line.lower().startswith("evs:"):
                mon["evs"] = parse_evs(line.split(":", 1)[1])

                continue

            if line.startswith("-"):
                mon["moves"].append(line[1:].strip())

                continue

            if line.startswith("Level:") or line.startswith("IVs:") or line.startswith("Shiny:"):
                continue

            if line.endswith(" Nature"):
                mon["nature"] = line[: -len(" Nature")]

                continue

            m = SPECIES_LINE.match(line)

            if m and not mon["name"]:
                mon["name"] = m.group(1).strip()

                if m.group(2):
                    mon["item"] = m.group(2).strip()

        if not mon["name"]:
            continue

        party.append(mon)

    return party


def to_party_member(mon: dict) -> dict:
    moves = [{"name": mv} for mv in (mon["moves"] + ["", "", "", ""])[:4]]

    out: dict = {
        "name": adjust_name(mon["name"]),
        "nature": mon["nature"],
        "ability": mon["ability"],
        "abilityOn": False,
        "teraType": mon["teraType"],
        "teraTypeActive": False,
        "evs": mon["evs"],
        "moves": moves,
        "activeMovePosition": 1,
    }

    if mon["item"]:
        out["item"] = mon["item"]

    return out


def team_label(raw: str, party: list[dict]) -> str:
    for line in raw.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if "@" in stripped or stripped.startswith("Ability:"):
            break

        return stripped

    return " / ".join(m["name"] for m in party)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "meta": {
            "source": "pokepast.es",
            "game": "champions",
            "count": len(URLS),
            "importedAt": date.today().isoformat(),
        },
        "teams": [],
    }

    with httpx.Client(timeout=30.0) as client:
        for i, url in enumerate(URLS):
            pid = pokepast_id(url)
            res = client.get(f"{url}/raw")
            res.raise_for_status()
            raw = res.text

            parsed = parse_showdown_team(raw)
            party = [to_party_member(m) for m in parsed]
            label = team_label(raw, party)
            key = f"meta_{i + 1:02d}_{pid}"

            (OUT_DIR / f"{pid}.txt").write_text(raw, encoding="utf-8")

            team_json = {"label": label, "party": party, "pokepast": url}

            (OUT_DIR / f"{pid}.json").write_text(json.dumps(team_json, indent=2) + "\n", encoding="utf-8")

            manifest["teams"].append(
                {
                    "key": key,
                    "id": pid,
                    "url": url,
                    "label": label,
                    "showdown": f"{pid}.txt",
                    "json": f"{pid}.json",
                    "species": [m["name"] for m in party],
                }
            )

            print(f"[{i + 1}/{len(URLS)}] {pid} {label}", file=sys.stderr)

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(URLS)} teams to {OUT_DIR}", file=sys.stderr)

    import subprocess

    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "build_obs_vocab.py")], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
