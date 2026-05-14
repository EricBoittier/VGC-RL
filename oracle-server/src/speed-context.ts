import { Field } from "@lib/model/field"
import { Move } from "@lib/model/move"
import { Pokemon } from "@lib/model/pokemon"
import { getFinalSpeed } from "@lib/smogon/stat-calculator/spe/modified-spe"
import { basePriorityLevel, moveIsFlyingType, orderPairBySpeed, priorityLevel } from "@lib/speed-calculator/order-pair-by-speed"

import type { SpeedCompareOutcomeJson, SpeedContextDoubleJson, SpeedContextSingleJson } from "./batch-types.js"

const PRIORITY_BRACKET_ABILITIES = "Gale Wings +1 on Flying-type moves at full HP; Prankster +1 on Status-category moves"

function statusLabel(pokemon: Pokemon): string {
  const st = pokemon.status

  if (!st.code) return "Healthy"

  return st.description
}

function boostSpe(pokemon: Pokemon): number {
  return pokemon.boosts.spe ?? 0
}

export function buildSpeedOrderExplanation(first: Pokemon, second: Pokemon, field: Field, speedOf: (p: Pokemon) => number): string {
  const p1 = priorityLevel(first.move, field, first)
  const p2 = priorityLevel(second.move, field, second)

  if (p1 !== p2) {
    return `${first.name} moves before ${second.name}: priority ${p1} beats ${p2}.`
  }

  const s1 = speedOf(first)
  const s2 = speedOf(second)

  if (field.isTrickRoom) {
    return `${first.name} moves before ${second.name} under Trick Room (effective Speed ${s1} vs ${s2}, priorities tied at ${p1}).`
  }

  return `${first.name} moves before ${second.name} by Speed (${s1} vs ${s2}, priorities tied at ${p1}).`
}

export function buildSpeedCompareOutcome(attacker: Pokemon, secondAttacker: Pokemon, field: Field, speedCompareMode: "alliedDoubles" | "opposingTrainers"): SpeedCompareOutcomeJson {
  const [first, second] = orderPairBySpeed(attacker, secondAttacker, field, { mode: speedCompareMode })

  const opposingTrainers = speedCompareMode === "opposingTrainers"
  const speedOf = (p: Pokemon) => (opposingTrainers ? getFinalSpeed(p, field, p === attacker) : getFinalSpeed(p, field, true))

  const pF = priorityLevel(first.move, field, first)
  const pS = priorityLevel(second.move, field, second)
  const bF = basePriorityLevel(first.move, field)
  const bS = basePriorityLevel(second.move, field)
  const sF = speedOf(first)
  const sS = speedOf(second)

  return {
    kind: "speedCompare",
    firstSpecies: first.name,
    secondSpecies: second.name,
    firstMove: first.move.name,
    secondMove: second.move.name,
    firstPriority: pF,
    secondPriority: pS,
    firstBasePriority: bF,
    secondBasePriority: bS,
    firstEffectiveSpeed: sF,
    secondEffectiveSpeed: sS,
    trickRoomActive: field.isTrickRoom,
    weather: field.weather,
    terrain: field.terrain,
    explanation: buildSpeedOrderExplanation(first, second, field, speedOf),
    resolvedOrderSpecies: [first.name, second.name],
    priorityBracketNote:
      pF !== pS
        ? `Priority brackets differ (${pF} vs ${pS}). ${PRIORITY_BRACKET_ABILITIES} (bases ${bF} vs ${bS}).`
        : `Priorities tied at ${pF}. ${PRIORITY_BRACKET_ABILITIES}. Resolved using ${field.isTrickRoom ? "Trick Room (slower moves first)" : "effective Speed (faster moves first)"} (bases ${bF} vs ${bS}).`
  }
}

export function buildSpeedContextSingle(attacker: Pokemon, defender: Pokemon, field: Field, attackerMove?: Move): SpeedContextSingleJson {
  const move = attackerMove ?? attacker.move
  const atkPri = priorityLevel(move, field, attacker)
  const basePri = basePriorityLevel(move, field)

  return {
    trickRoomActive: field.isTrickRoom,
    weather: field.weather,
    terrain: field.terrain,
    tailwindAttackerSide: field.attackerSide.isTailwind,
    tailwindDefenderSide: field.defenderSide.isTailwind,
    attackerMovePriority: atkPri,
    attackerMoveBasePriority: basePri,
    galeWingsBoostApplied: attacker.ability.is("Gale Wings") && attacker.hpPercentage >= 100 && moveIsFlyingType(move.name) && atkPri > basePri,
    pranksterBoostApplied: attacker.ability.is("Prankster") && move.category === "Status" && atkPri > basePri,
    lines: [
      {
        role: "attacker",
        species: attacker.name,
        effectiveSpeed: getFinalSpeed(attacker, field, true),
        speBoost: boostSpe(attacker),
        status: statusLabel(attacker),
        hpPercent: attacker.hpPercentage,
        ability: attacker.ability.name,
        item: attacker.item
      },
      {
        role: "defender",
        species: defender.name,
        effectiveSpeed: getFinalSpeed(defender, field, false),
        speBoost: boostSpe(defender),
        status: statusLabel(defender),
        hpPercent: defender.hpPercentage,
        ability: defender.ability.name,
        item: defender.item
      }
    ],
    initiativeNote: `Isolated damage calc for attacker move “${move.name}”: defender did not select a move. Speed lines use attacker/defender Field sides (Tailwind is per side). Damage percents are calculator roll bands versus max HP; KO text is derived from those rolls.`
  }
}

export function buildSpeedContextDouble(first: Pokemon, second: Pokemon, field: Field): SpeedContextDoubleJson {
  return {
    trickRoomActive: field.isTrickRoom,
    weather: field.weather,
    terrain: field.terrain,
    orderedSpecies: [first.name, second.name],
    orderedMoves: [first.move.name, second.move.name],
    priorities: [priorityLevel(first.move, field, first), priorityLevel(second.move, field, second)],
    basePriorities: [basePriorityLevel(first.move, field), basePriorityLevel(second.move, field)],
    effectiveSpeeds: [getFinalSpeed(first, field, true), getFinalSpeed(second, field, true)],
    explanation: buildSpeedOrderExplanation(first, second, field, p => getFinalSpeed(p, field, true)),
    initiativeNote: "Dual strike into one defender: order follows priority, then Trick Room Speed inversion, then Speed. Each hit uses its own damage roll band; defender HP is not updated between hits in this payload."
  }
}
