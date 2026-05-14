import championsMod from "../src/data/move-details-champions.ts"
import moveDetailsMod from "../src/data/move-details.ts"

const MOVE_DETAILS = (moveDetailsMod as { MOVE_DETAILS: Record<string, { name: string; target: string }> }).MOVE_DETAILS
const MOVE_DETAILS_CHAMPIONS = (championsMod as { MOVE_DETAILS_CHAMPIONS: Record<string, Partial<{ target?: string; name?: string }>> }).MOVE_DETAILS_CHAMPIONS

const names: string[] = []

for (const key of Object.keys(MOVE_DETAILS)) {
  const base = MOVE_DETAILS[key]

  if (!base) {
    continue
  }

  const ov = MOVE_DETAILS_CHAMPIONS[key]
  const merged = ov ? { ...base, ...ov } : base

  if (merged.target === "allAdjacentFoes" || merged.target === "allAdjacent") {
    names.push(merged.name)
  }
}

names.sort()

process.stdout.write(JSON.stringify(names, null, 2) + "\n")
