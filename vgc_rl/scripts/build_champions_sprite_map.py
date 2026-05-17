from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


def fetch_category_files() -> set[str]:
    files: list[str] = []
    cmcontinue: str | None = None

    while True:
        url = (
            "https://archives.bulbagarden.net/w/api.php"
            "?action=query&list=categorymembers"
            "&cmtitle=Category:Champions_menu_sprites&cmlimit=500&format=json"
        )

        if cmcontinue:
            url += "&cmcontinue=" + urllib.parse.quote(cmcontinue, safe="")

        out = subprocess.check_output(["curl", "-sA", "VGC-RL/1.0", url], text=True)
        data = json.loads(out)
        files.extend(m["title"].replace("File:", "") for m in data["query"]["categorymembers"])
        cont = data.get("continue")

        if not cont:
            break

        cmcontinue = cont.get("cmcontinue")

    return set(files)


def fetch_file_urls(files: set[str]) -> dict[str, str]:
    file_urls: dict[str, str] = {}
    batch = sorted(files)

    for i in range(0, len(batch), 40):
        chunk = batch[i : i + 40]
        titles = "|".join("File:" + f.replace(" ", "_") for f in chunk)
        api = (
            "https://archives.bulbagarden.net/w/api.php?action=query&format=json"
            "&prop=imageinfo&iiprop=url&titles=" + urllib.parse.quote(titles, safe="")
        )
        out = subprocess.check_output(["curl", "-sA", "VGC-RL/1.0", api], text=True)
        data = json.loads(out)

        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title", "").replace("File:", "").replace("_", " ")
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url")

            if not url:
                continue

            for fname in chunk:
                if fname == title:
                    file_urls[fname] = url
                    break

    return file_urls


def dex_for(name: str) -> int | None:
    base = name.split("-")[0].lower().replace("'", "").replace(".", "")

    for slug in (base, name.lower().replace(" ", "-")):
        url = f"https://pokeapi.co/api/v2/pokemon/{slug}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VGC-RL"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return int(json.load(resp)["id"])
        except Exception:
            pass

    url = f"https://pokeapi.co/api/v2/pokemon-species/{base}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VGC-RL"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(json.load(resp)["id"])
    except Exception:
        return None


def form_suffix(name: str) -> str:
    parts = name.split("-")

    if len(parts) == 1:
        return ""

    rest = parts[1:]

    if rest[0] == "Mega":
        if len(rest) == 1:
            return "Mega"

        if rest[1] in ("X", "Y"):
            return f"Mega {rest[1]}"

    if rest[0] in ("Alola", "Galar", "Hisui"):
        return rest[0]

    if rest[0] == "Paldea" and len(rest) >= 2:
        return f"Paldea {rest[1].capitalize()}"

    if rest[0] == "Rotom":
        return rest[1]

    if rest in (["F", "Mega"], ["F"]):
        return "Female"

    if rest in (["M", "Mega"], ["M"]):
        return "Male"

    return "-".join(rest)


def resolve_file(name: str, files: set[str]) -> str | None:
    dex = dex_for(name)

    if dex is None:
        return None

    form = form_suffix(name)
    candidates: list[str] = []

    if form:
        candidates.append(f"Menu CP {dex:04d}-{form}.png")

    candidates.append(f"Menu CP {dex:04d}.png")

    for candidate in candidates:
        if candidate in files:
            return candidate

    prefix = f"Menu CP {dex:04d}"
    matches = sorted(f for f in files if f.startswith(prefix))

    if form == "Mega" and matches:
        mega = next((f for f in matches if "-Mega" in f and "Female" not in f and "Male" not in f), None)

        if mega:
            return mega

    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Champions menu sprite map for the replay viewer.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "vgc_rl" / "replay_viewer" / "champions_sprite_map.json",
    )
    parser.add_argument(
        "--vocab",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "vgc_rl" / "examples" / "vocab.json",
    )
    args = parser.parse_args()

    files = fetch_category_files()
    file_urls = fetch_file_urls(files)
    species = json.loads(args.vocab.read_text(encoding="utf-8"))["species"]
    by_species: dict[str, str] = {}
    missing: list[str] = []

    for sp in species:
        fname = resolve_file(sp, files)

        if not fname:
            missing.append(sp)
            continue

        url = file_urls.get(fname)

        if not url:
            missing.append(sp)
            continue

        by_species[sp] = url

    if missing:
        raise SystemExit(f"no sprite for: {', '.join(missing)}")

    payload = {"bySpecies": by_species, "byFile": file_urls}
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(by_species)} species, {len(file_urls)} files)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
