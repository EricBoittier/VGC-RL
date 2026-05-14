import { Field } from "@lib/model/field"
import { Move } from "@lib/model/move"
import { Pokemon } from "@lib/model/pokemon"
import { getFinalSpeed } from "@lib/smogon/stat-calculator/spe/modified-spe"
import { MOVES } from "@robsonbittencourt/calc"

const PRIORITY_5 = ["Helping Hand"] as const
const PRIORITY_4 = ["Baneful Bunker", "Burning Bulwark", "Detect", "Endure", "Protect", "Spiky Shield", "Silk Trap"] as const
const PRIORITY_3 = ["Fake Out", "Quick Guard", "Upper Hand", "Wide Guard"] as const
const PRIORITY_2 = ["Ally Switch", "Extreme Speed", "Feint", "First Impression", "Follow Me", "Rage Powder"] as const
const PRIORITY_1 = ["Accelerock", "Aqua Jet", "Baby-Doll Eyes", "Bullet Punch", "Ice Shard", "Jet Punch", "Mach Punch", "Quick Attack", "Shadow Sneak", "Sucker Punch", "Thunderclap", "Vacuum Wave", "Water Shuriken"] as const
const PRIORITY_MINUS_3 = ["Beak Blast", "Focus Punch"] as const
const PRIORITY_MINUS_4 = ["Avalanche"] as const
const PRIORITY_MINUS_5 = ["Counter", "Mirror Coat"] as const
const PRIORITY_MINUS_6 = ["Circle Throw", "Dragon Tail", "Roar", "Whirlwind", "Teleport"] as const
const PRIORITY_MINUS_7 = ["Trick Room"] as const

function includesMove(moveName: string, list: readonly string[]): boolean {
  return list.includes(moveName)
}

export function moveIsFlyingType(moveName: string): boolean {
  const g9 = MOVES[9]?.[moveName]?.type

  const g0 = MOVES[0]?.[moveName]?.type

  return g9 === "Flying" || g0 === "Flying"
}

export function basePriorityLevel(move: Move, field: Field): number {
  if (move.name === "Grassy Glide" && field.terrain === "Grassy") {
    return 1
  }

  if (includesMove(move.name, PRIORITY_5)) return 5

  if (includesMove(move.name, PRIORITY_4)) return 4

  if (includesMove(move.name, PRIORITY_3)) return 3

  if (includesMove(move.name, PRIORITY_2)) return 2

  if (includesMove(move.name, PRIORITY_1)) return 1

  if (includesMove(move.name, PRIORITY_MINUS_3)) return -3

  if (includesMove(move.name, PRIORITY_MINUS_4)) return -4

  if (includesMove(move.name, PRIORITY_MINUS_5)) return -5

  if (includesMove(move.name, PRIORITY_MINUS_6)) return -6

  if (includesMove(move.name, PRIORITY_MINUS_7)) return -7

  return 0
}

export function priorityLevel(move: Move, field: Field, pokemon?: Pokemon): number {
  let level = basePriorityLevel(move, field)

  if (pokemon?.ability.is("Gale Wings") && pokemon.hpPercentage >= 100 && moveIsFlyingType(move.name)) {
    level += 1
  }

  if (pokemon?.ability.is("Prankster") && move.category === "Status") {
    level += 1
  }

  return level
}

export type OrderPairBySpeedOptions = {
  mode?: "alliedDoubles" | "opposingTrainers"
}

export function orderPairBySpeed(pokemonOne: Pokemon, pokemonTwo: Pokemon, field: Field, options?: OrderPairBySpeedOptions): [Pokemon, Pokemon] {
  const mode = options?.mode ?? "alliedDoubles"
  const speedOne = getFinalSpeed(pokemonOne, field, true)
  const speedTwo = getFinalSpeed(pokemonTwo, field, mode === "opposingTrainers" ? false : true)

  const pokemonOnePriority = priorityLevel(pokemonOne.move, field, pokemonOne)
  const pokemonTwoPriority = priorityLevel(pokemonTwo.move, field, pokemonTwo)

  const someoneHasPriority = pokemonOnePriority != 0 || pokemonTwoPriority != 0
  const equalsPriority = pokemonOnePriority == pokemonTwoPriority

  if (someoneHasPriority && !equalsPriority) {
    return pokemonOnePriority > pokemonTwoPriority ? [pokemonOne, pokemonTwo] : [pokemonTwo, pokemonOne]
  }

  const oneBeforeTwo = field.isTrickRoom ? speedOne <= speedTwo : speedOne >= speedTwo

  return oneBeforeTwo ? [pokemonOne, pokemonTwo] : [pokemonTwo, pokemonOne]
}
