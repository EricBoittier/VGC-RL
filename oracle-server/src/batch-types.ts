import type { OracleGame } from "@lib/oracle/oracle-engine"
import type { FieldJson, PokemonJson } from "./domain-from-json.js"
import type { Terrain, Weather } from "@lib/types"

export type BatchFieldFragment = {
  field: FieldJson
  rightIsDefender?: boolean
}

export type BatchDamageRequest = BatchFieldFragment & {
  kind: "single" | "allMoves" | "double"
  attacker: PokemonJson
  defender: PokemonJson
  secondAttacker?: PokemonJson
}

export type BatchSpeedCompareRequest = BatchFieldFragment & {
  kind: "speedCompare"
  attacker: PokemonJson
  secondAttacker: PokemonJson
  opposingSides?: boolean
  speedCompareMode?: "alliedDoubles" | "opposingTrainers"
}

export type BatchRequestItem = BatchDamageRequest | BatchSpeedCompareRequest

export type BatchRequestBody = {
  game: OracleGame
  useSpsMode?: boolean
  includeSpeedContext?: boolean
  requests: BatchRequestItem[]
}

export type SpeedLineJson = {
  role: "attacker" | "defender"
  species: string
  effectiveSpeed: number
  speBoost: number
  status: string
  hpPercent: number
  ability: string
  item: string
}

export type SpeedContextSingleJson = {
  trickRoomActive: boolean
  weather: Weather | null
  terrain: Terrain | null
  tailwindAttackerSide: boolean
  tailwindDefenderSide: boolean
  attackerMovePriority: number
  attackerMoveBasePriority: number
  galeWingsBoostApplied: boolean
  pranksterBoostApplied: boolean
  lines: SpeedLineJson[]
  initiativeNote: string
}

export type SpeedContextDoubleJson = {
  trickRoomActive: boolean
  weather: Weather | null
  terrain: Terrain | null
  orderedSpecies: [string, string]
  orderedMoves: [string, string]
  priorities: [number, number]
  basePriorities: [number, number]
  effectiveSpeeds: [number, number]
  explanation: string
  initiativeNote: string
}

export type SpeedCompareOutcomeJson = {
  kind: "speedCompare"
  firstSpecies: string
  secondSpecies: string
  firstMove: string
  secondMove: string
  firstPriority: number
  secondPriority: number
  firstBasePriority: number
  secondBasePriority: number
  firstEffectiveSpeed: number
  secondEffectiveSpeed: number
  trickRoomActive: boolean
  weather: Weather | null
  terrain: Terrain | null
  explanation: string
  resolvedOrderSpecies: [string, string]
  priorityBracketNote: string
}

export type DamageOutcomeJson = {
  moveName: string
  moveDesc: string
  koChanceText: string
  damagePercentMin: number | null
  damagePercentMax: number | null
  damageRolls: number[][]
  description: string
  afterTurnResidualHp: number | null
  damageRollInterpretation?: string
  speedContext?: SpeedContextSingleJson
}

export type DoubleOutcomeJson = {
  kind: "double"
  koChanceText: string
  combinedMoveDesc: string
  damagePercentMax: number
  description: string
  firstMoveName: string
  secondMoveName: string
  firstAttackerRolls: number[][]
  secondAttackerRolls: number[][]
  afterTurnResidualHpFirst: number | null
  damageRollInterpretation?: string
  speedContext?: SpeedContextDoubleJson
}

export type BatchOk = {
  ok: true
  index: number
  result: DamageOutcomeJson | DamageOutcomeJson[] | DoubleOutcomeJson | SpeedCompareOutcomeJson
}

export type BatchErr = { ok: false; index: number; error: string }

export type BatchResponseBody = { results: Array<BatchOk | BatchErr> }
