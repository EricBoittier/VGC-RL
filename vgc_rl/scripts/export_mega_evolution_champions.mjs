import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SETDEX_PATH = path.resolve(__dirname, "../../src/data/movesets-champions.ts")
const OUT_PATH = path.resolve(__dirname, "../vgc_rl/examples/mega_evolution_champions.json")

function normalizeItemKey(item) {
  return String(item || "")
    .trim()
    .toLowerCase()
}

function loadSetdex() {
  const raw = fs.readFileSync(SETDEX_PATH, "utf8")
  const body = raw.replace(/^export const SETDEX_CHAMPIONS[^=]*=\s*/, "").replace(/;\s*$/, "")

  return eval(`(${body})`)
}

function basesForMega(megaKey, candidates) {
  const out = []

  for (const base of candidates) {
    if (megaKey === `${base}-Mega`) {
      out.push(base)

      continue
    }

    if (megaKey.startsWith(`${base}-Mega`)) {
      out.push(base)

      continue
    }

    if (base === "Meowstic" && megaKey.includes("-F-")) {
      continue
    }

    if (megaKey.startsWith(`${base}-`)) {
      out.push(base)
    }
  }

  return [...new Set(out)]
}

function main() {
  const setdex = loadSetdex()
  const itemToBases = {}

  for (const [key, data] of Object.entries(setdex)) {
    if (key.includes("-Mega") || !data || typeof data !== "object") {
      continue
    }

    for (const it of data.items || []) {
      const ik = normalizeItemKey(it)

      if (!ik) {
        continue
      }

      if (!itemToBases[ik]) {
        itemToBases[ik] = []
      }

      itemToBases[ik].push(key)
    }
  }

  const lookups = []
  const megaForms = []

  for (const [megaKey, data] of Object.entries(setdex)) {
    if (!megaKey.includes("-Mega") || !data || typeof data !== "object") {
      continue
    }

    const stone = (data.items || [])[0]

    if (!stone) {
      continue
    }

    const itemKey = normalizeItemKey(stone)
    const candidates = itemToBases[itemKey] || []
    const bases = basesForMega(megaKey, candidates)

    if (bases.length === 0) {
      const inferred = megaKey.replace(/-Mega(-[XY])?$/, "").replace(/-M$/, "")

      bases.push(inferred)
    }

    megaForms.push({
      mega: megaKey,
      ability: String(data.ability || ""),
      item: String(stone),
    })

    for (const base of bases) {
      lookups.push({
        itemKey,
        baseSpecies: base,
        mega: megaKey,
        ability: String(data.ability || ""),
        item: String(stone),
      })
    }
  }

  const payload = {
    version: 1,
    source: "src/data/movesets-champions.ts",
    megaFormCount: megaForms.length,
    lookupCount: lookups.length,
    megaForms: megaForms.sort((a, b) => a.mega.localeCompare(b.mega)),
    lookups: lookups.sort((a, b) => a.itemKey.localeCompare(b.itemKey) || a.baseSpecies.localeCompare(b.baseSpecies)),
  }

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true })
  fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2) + "\n", "utf8")

  process.stderr.write(`mega_evolution_champions → ${OUT_PATH} · forms=${megaForms.length} lookups=${lookups.length}\n`)
}

main()
