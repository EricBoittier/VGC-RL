import { Generations, Move as MoveSmogon } from "@robsonbittencourt/calc"
import championsMod from "../src/data/move-details-champions.ts"
import moveDetailsMod from "../src/data/move-details.ts"

const MOVE_DETAILS = (moveDetailsMod as { MOVE_DETAILS: Record<string, { name: string; category: string; type: string }> }).MOVE_DETAILS
const MOVE_DETAILS_CHAMPIONS = (championsMod as { MOVE_DETAILS_CHAMPIONS: Record<string, Partial<{ category?: string; type?: string }>> }).MOVE_DETAILS_CHAMPIONS

const gen = Generations.get(0)

const out: Record<string, { category: string; type: string; contact: boolean }> = {}

for (const key of Object.keys(MOVE_DETAILS)) {
  const base = MOVE_DETAILS[key]

  if (!base) {
    continue
  }

  const ov = MOVE_DETAILS_CHAMPIONS[key]
  const merged = ov ? { ...base, ...ov } : base
  const name = merged.name

  let contact = false

  try {
    const sm = new MoveSmogon(gen, name)

    contact = !!(sm as { flags?: { contact?: number } }).flags?.contact
  } catch {
    contact = false
  }

  out[name] = {
    category: merged.category,
    type: merged.type,
    contact
  }
}

const names = Object.keys(out).sort()

const sorted: Record<string, { category: string; type: string; contact: boolean }> = {}

for (const n of names) {
  sorted[n] = out[n]!
}

process.stdout.write(JSON.stringify(sorted, null, 2) + "\n")
