import assert from "node:assert/strict"
import test from "node:test"
import { once } from "node:events"
import type { BatchRequestBody, BatchResponseBody, DamageOutcomeJson } from "./batch-types.js"
import { ragingBoltVsFlutterManeSingle } from "./test-fixtures.js"
import { handleOracleBatch } from "./run-batch.js"
import { createOracleHttpServer } from "./server.js"

test("handleOracleBatch golden SV Thunderbolt vs Flutter Mane", () => {
  const out = handleOracleBatch(ragingBoltVsFlutterManeSingle)

  assert.equal(out.results.length, 1)

  const row = out.results[0]

  assert.equal(row.ok, true)

  if (!row.ok) return

  const r = row.result

  assert.ok(!Array.isArray(r))
  assert.ok(!(typeof r === "object" && r !== null && "kind" in r && (r as { kind: string }).kind === "double"))

  const damage = r as DamageOutcomeJson

  assert.equal(damage.moveName, "Thunderbolt")
  assert.equal(damage.moveDesc, "40 - 48.4%")
  assert.equal(damage.koChanceText, "guaranteed 3HKO")
  assert.equal(damage.damagePercentMin, 40)
  assert.equal(damage.damagePercentMax, 48.4)
  assert.equal(damage.damageRolls.length, 1)
  assert.deepEqual(damage.damageRolls[0], [52, 54, 54, 54, 55, 55, 57, 57, 58, 58, 58, 60, 60, 61, 61, 63])
  assert.equal(typeof damage.damageRollInterpretation, "string")
  assert.ok(damage.speedContext)
  assert.equal(damage.speedContext!.lines.length, 2)
  assert.ok(damage.speedContext!.initiativeNote.includes("Thunderbolt"))
})

test("includeSpeedContext false omits speedContext", () => {
  const body: BatchRequestBody = { ...ragingBoltVsFlutterManeSingle, includeSpeedContext: false }

  const out = handleOracleBatch(body)
  const row = out.results[0]

  assert.equal(row.ok, true)

  if (!row.ok) return

  const damage = row.result as DamageOutcomeJson

  assert.equal(damage.speedContext, undefined)
})

test("allMoves rows include per-move speedContext by default", () => {
  const body: BatchRequestBody = {
    game: "sv",
    requests: [
      {
        kind: "allMoves",
        field: {},
        attacker: {
          name: "Raging Bolt",
          moves: [{ name: "Thunderbolt" }, { name: "Thunderclap" }, { name: "Draco Meteor" }, { name: "Protect" }],
          activeMovePosition: 1
        },
        defender: {
          name: "Flutter Mane",
          moves: [{ name: "Moonblast" }, { name: "Shadow Ball" }, { name: "Dazzling Gleam" }, { name: "Protect" }]
        }
      }
    ]
  }

  const out = handleOracleBatch(body)
  const row = out.results[0]

  assert.equal(row.ok, true)

  if (!row.ok) return

  const rows = row.result as DamageOutcomeJson[]

  assert.equal(rows.length, 4)

  for (const sub of rows) {
    assert.ok(sub.speedContext)
    assert.ok(sub.speedContext!.initiativeNote.includes(sub.moveName))
  }
})

test("speedCompare orders Extreme Speed before Gale Wings Brave Bird", () => {
  const body: BatchRequestBody = {
    game: "champions",
    requests: [
      {
        kind: "speedCompare",
        field: {},
        attacker: {
          name: "Dragonite",
          nature: "Mild",
          ability: "Multiscale",
          moves: [{ name: "Draco Meteor" }, { name: "Extreme Speed" }, { name: "Ice Beam" }, { name: "Protect" }],
          activeMovePosition: 2
        },
        secondAttacker: {
          name: "Talonflame",
          nature: "Jolly",
          ability: "Gale Wings",
          item: "Focus Sash",
          moves: [{ name: "Brave Bird" }, { name: "Taunt" }, { name: "Upper Hand" }, { name: "Tailwind" }],
          activeMovePosition: 1
        }
      }
    ]
  }

  const out = handleOracleBatch(body)

  assert.equal(out.results.length, 1)
  assert.equal(out.results[0].ok, true)

  const row = out.results[0]

  if (!row.ok) return

  const r = row.result as import("./batch-types.js").SpeedCompareOutcomeJson

  assert.equal(r.kind, "speedCompare")
  assert.equal(r.firstSpecies, "Dragonite")
  assert.equal(r.firstMove, "Extreme Speed")
  assert.ok(r.firstPriority > r.secondPriority)
})

test("speedCompare Prankster boosts Status Tailwind ahead of faster foe attacking move", () => {
  const body: BatchRequestBody = {
    game: "sv",
    requests: [
      {
        kind: "speedCompare",
        field: {},
        speedCompareMode: "opposingTrainers",
        attacker: {
          name: "Whimsicott",
          ability: "Prankster",
          moves: [{ name: "Moonblast" }, { name: "Tailwind" }, { name: "Encore" }, { name: "Protect" }],
          activeMovePosition: 2
        },
        secondAttacker: {
          name: "Dragapult",
          moves: [{ name: "Dragon Darts" }, { name: "Phantom Force" }, { name: "U-turn" }, { name: "Protect" }],
          activeMovePosition: 1,
          evs: { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 252 }
        }
      }
    ]
  }

  const out = handleOracleBatch(body)

  assert.equal(out.results.length, 1)
  assert.equal(out.results[0].ok, true)

  const row = out.results[0]

  if (!row.ok) return

  const r = row.result as import("./batch-types.js").SpeedCompareOutcomeJson

  assert.equal(r.kind, "speedCompare")
  assert.equal(r.firstSpecies, "Whimsicott")
  assert.equal(r.firstMove, "Tailwind")
  assert.equal(r.secondSpecies, "Dragapult")
  assert.ok(r.firstPriority > r.secondPriority)
})

test("speedCompare opposingTrainers applies alphaSide Tailwind only to batch attacker", () => {
  const body: BatchRequestBody = {
    game: "champions",
    requests: [
      {
        kind: "speedCompare",
        field: {
          alphaSide: { isTailwind: true },
          betaSide: { isTailwind: false }
        },
        speedCompareMode: "opposingTrainers",
        attacker: {
          name: "Whimsicott",
          nature: "Bold",
          ability: "Prankster",
          item: "Focus Sash",
          moves: [{ name: "Giga Drain" }, { name: "Tailwind" }, { name: "Sunny Day" }, { name: "Dazzling Gleam" }],
          activeMovePosition: 1,
          evs: { hp: 0, atk: 0, def: 124, spa: 247, spd: 124, spe: 15 }
        },
        secondAttacker: {
          name: "Charizard",
          nature: "Modest",
          ability: "Solar Power",
          item: "Charizardite Y",
          moves: [{ name: "Solar Beam" }, { name: "Heat Wave" }, { name: "Air Slash" }, { name: "Protect" }],
          activeMovePosition: 2,
          evs: { hp: 15, atk: 0, def: 0, spa: 247, spd: 0, spe: 247 }
        }
      }
    ]
  }

  const out = handleOracleBatch(body)

  assert.equal(out.results[0].ok, true)

  const row = out.results[0]

  if (!row.ok) return

  const r = row.result as import("./batch-types.js").SpeedCompareOutcomeJson

  assert.equal(r.kind, "speedCompare")
  assert.equal(r.firstSpecies, "Whimsicott")
})

test("speedCompare alliedDoubles applies alphaSide Tailwind to both Pokémon", () => {
  const body: BatchRequestBody = {
    game: "champions",
    requests: [
      {
        kind: "speedCompare",
        field: {
          alphaSide: { isTailwind: true },
          betaSide: { isTailwind: false }
        },
        speedCompareMode: "alliedDoubles",
        attacker: {
          name: "Whimsicott",
          nature: "Bold",
          ability: "Prankster",
          item: "Focus Sash",
          moves: [{ name: "Giga Drain" }, { name: "Tailwind" }, { name: "Sunny Day" }, { name: "Dazzling Gleam" }],
          activeMovePosition: 1,
          evs: { hp: 0, atk: 0, def: 124, spa: 247, spd: 124, spe: 15 }
        },
        secondAttacker: {
          name: "Charizard",
          nature: "Modest",
          ability: "Solar Power",
          item: "Charizardite Y",
          moves: [{ name: "Solar Beam" }, { name: "Heat Wave" }, { name: "Air Slash" }, { name: "Protect" }],
          activeMovePosition: 2,
          evs: { hp: 15, atk: 0, def: 0, spa: 247, spd: 0, spe: 247 }
        }
      }
    ]
  }

  const out = handleOracleBatch(body)

  assert.equal(out.results[0].ok, true)

  const row = out.results[0]

  if (!row.ok) return

  const r = row.result as import("./batch-types.js").SpeedCompareOutcomeJson

  assert.equal(r.kind, "speedCompare")
  assert.equal(r.firstSpecies, "Charizard")
})

test("speedCompare opposingTrainers respects legacy attackerSide defenderSide field keys", () => {
  const body: BatchRequestBody = {
    game: "champions",
    requests: [
      {
        kind: "speedCompare",
        field: {
          attackerSide: { isTailwind: true },
          defenderSide: { isTailwind: false }
        },
        speedCompareMode: "opposingTrainers",
        attacker: {
          name: "Whimsicott",
          nature: "Bold",
          ability: "Prankster",
          item: "Focus Sash",
          moves: [{ name: "Giga Drain" }, { name: "Tailwind" }, { name: "Sunny Day" }, { name: "Dazzling Gleam" }],
          activeMovePosition: 1,
          evs: { hp: 0, atk: 0, def: 124, spa: 247, spd: 124, spe: 15 }
        },
        secondAttacker: {
          name: "Charizard",
          nature: "Modest",
          ability: "Solar Power",
          item: "Charizardite Y",
          moves: [{ name: "Solar Beam" }, { name: "Heat Wave" }, { name: "Air Slash" }, { name: "Protect" }],
          activeMovePosition: 2,
          evs: { hp: 15, atk: 0, def: 0, spa: 247, spd: 0, spe: 247 }
        }
      }
    ]
  }

  const out = handleOracleBatch(body)

  assert.equal(out.results[0].ok, true)

  const row = out.results[0]

  if (!row.ok) return

  const r = row.result as import("./batch-types.js").SpeedCompareOutcomeJson

  assert.equal(r.kind, "speedCompare")
  assert.equal(r.firstSpecies, "Whimsicott")
})

test("POST /batch HTTP smoke", async () => {
  const server = createOracleHttpServer()

  await new Promise<void>(resolve => server.listen(0, resolve))

  try {
    const addr = server.address()

    assert.ok(addr && typeof addr === "object")
    const port = addr.port

    const res = await fetch(`http://127.0.0.1:${port}/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ragingBoltVsFlutterManeSingle)
    })

    assert.equal(res.status, 200)

    const json = (await res.json()) as BatchResponseBody

    assert.equal(json.results.length, 1)
    assert.equal(json.results[0].ok, true)

    const dmg = json.results[0].result as DamageOutcomeJson

    assert.ok(dmg.speedContext)
  } finally {
    server.close()

    await once(server, "close")
  }
})
