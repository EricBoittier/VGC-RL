import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { Generations } from "@robsonbittencourt/calc"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const teamsPath = path.join(__dirname, "../vgc_rl/vgc_rl/examples/example_teams.json")

const teams = JSON.parse(fs.readFileSync(teamsPath, "utf8")) as Record<string, unknown>
const names = new Set<string>()

for (const [k, v] of Object.entries(teams)) {
  if (k === "meta" || typeof v !== "object" || v === null || !("party" in v)) {
    continue
  }

  const party = (v as { party: { name: string }[] }).party

  for (const mon of party) {
    if (mon?.name) {
      names.add(mon.name)
    }
  }
}

const gen = Generations.get(9)

function dexKey(display: string): string {
  return display.toLowerCase().replace(/[^a-z0-9]/g, "")
}

const out: Record<string, string[]> = {}

for (const nm of names) {
  let sp = gen.species.get(dexKey(nm))

  if (!sp) {
    sp = gen.species.get(nm.replace(/\s+/g, "").toLowerCase())
  }

  if (!sp) {
    continue
  }

  out[nm] = [...sp.types]
}

const sortedNames = Object.keys(out).sort()
const sorted: Record<string, string[]> = {}

for (const n of sortedNames) {
  sorted[n] = out[n]!
}

process.stdout.write(JSON.stringify(sorted, null, 2) + "\n")
