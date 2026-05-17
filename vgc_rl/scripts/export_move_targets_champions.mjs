import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const MOVE_DETAILS_PATH = path.resolve(__dirname, "../../src/data/move-details.ts")
const META_PATH = path.resolve(__dirname, "../vgc_rl/examples/move_meta_champions.json")
const OUT_PATH = path.resolve(__dirname, "../vgc_rl/examples/move_targets_champions.json")

function loadMoveDetails() {
  const raw = fs.readFileSync(MOVE_DETAILS_PATH, "utf8")
  const body = raw.replace(/^import[\s\S]*?export const MOVE_DETAILS[^=]*=\s*/, "").replace(/;\s*$/, "")

  return eval(`(${body})`)
}

function main() {
  const details = loadMoveDetails()
  const meta = JSON.parse(fs.readFileSync(META_PATH, "utf8"))
  const championsMoves = new Set(Object.keys(meta))
  const targets = {}

  for (const entry of Object.values(details)) {
    if (!entry || typeof entry !== "object") {
      continue
    }

    const name = String(entry.name || "").trim()
    const target = String(entry.target || "").trim()

    if (!name || !target || !championsMoves.has(name)) {
      continue
    }

    targets[name] = target
  }

  const missing = [...championsMoves].filter(m => meta[m]?.category === "Status" && !targets[m]).sort()

  const payload = {
    version: 1,
    source: "src/data/move-details.ts",
    moveCount: Object.keys(targets).length,
    missingStatusTargets: missing,
    targets: Object.fromEntries(Object.entries(targets).sort(([a], [b]) => a.localeCompare(b))),
  }

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true })
  fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2) + "\n", "utf8")

  process.stderr.write(
    `move_targets_champions → ${OUT_PATH} · moves=${Object.keys(targets).length} missingStatus=${missing.length}\n`,
  )
}

main()
