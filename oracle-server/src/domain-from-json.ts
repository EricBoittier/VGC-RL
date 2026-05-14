import { Field, FieldSide } from "@lib/model/field"
import { Ability } from "@lib/model/ability"
import { Move } from "@lib/model/move"
import { MoveSet } from "@lib/model/moveset"
import { Pokemon } from "@lib/model/pokemon"
import { Status } from "@lib/model/status"
import { GameType, Stats, Terrain, Weather } from "@lib/types"
import { StatIDExceptHP } from "@robsonbittencourt/calc/src/data/interface"
import type { OracleGame } from "@lib/oracle/oracle-engine"

export type FieldSideJson = {
  gameType?: GameType
  isCriticalHit?: boolean
  isHelpingHand?: boolean
  isBattery?: boolean
  isPowerSpot?: boolean
  isTailwind?: boolean
  isReflect?: boolean
  isLightScreen?: boolean
  isAuroraVeil?: boolean
  isFriendGuard?: boolean
  spikes?: number
  isSR?: boolean
  isSeeded?: boolean
}

export type FieldJson = {
  weather?: Weather | null
  terrain?: Terrain | null
  isBeadsOfRuin?: boolean
  isSwordOfRuin?: boolean
  isTabletsOfRuin?: boolean
  isVesselOfRuin?: boolean
  isMagicRoom?: boolean
  isWonderRoom?: boolean
  isGravity?: boolean
  isTrickRoom?: boolean
  isNeutralizingGas?: boolean
  isFairyAura?: boolean
  attackerSide?: FieldSideJson
  defenderSide?: FieldSideJson
  alphaSide?: FieldSideJson
  betaSide?: FieldSideJson
}

export type MoveJson = {
  name: string
  hits?: string
  alliesFainted?: string
  lastMoveFailed?: boolean
}

export type PokemonJson = {
  name: string
  nature?: string
  item?: string
  ability?: string
  abilityOn?: boolean
  teraType?: string
  teraTypeActive?: boolean
  evs?: Partial<Stats>
  ivs?: Partial<Stats>
  boosts?: Partial<Stats>
  bonusBoosts?: Partial<Stats>
  status?: string
  hpPercentage?: number
  commanderActive?: boolean
  higherStat?: string
  isAttacker?: boolean
  moves: MoveJson[]
  activeMovePosition?: 1 | 2 | 3 | 4
}

export function fieldFromJson(raw: FieldJson): Field {
  const attackerSideSource = raw.alphaSide ?? raw.attackerSide
  const defenderSideSource = raw.betaSide ?? raw.defenderSide

  return new Field({
    weather: raw.weather ?? null,
    terrain: raw.terrain ?? null,
    isBeadsOfRuin: raw.isBeadsOfRuin,
    isSwordOfRuin: raw.isSwordOfRuin,
    isTabletsOfRuin: raw.isTabletsOfRuin,
    isVesselOfRuin: raw.isVesselOfRuin,
    isMagicRoom: raw.isMagicRoom,
    isWonderRoom: raw.isWonderRoom,
    isGravity: raw.isGravity,
    isTrickRoom: raw.isTrickRoom,
    isNeutralizingGas: raw.isNeutralizingGas,
    isFairyAura: raw.isFairyAura,
    attackerSide: attackerSideSource ? new FieldSide(attackerSideSource) : undefined,
    defenderSide: defenderSideSource ? new FieldSide(defenderSideSource) : undefined,
  })
}

function statusFromJson(s?: string): Status | undefined {
  if (!s) return undefined

  const fromCode = Status.byCode(s)

  if (fromCode.code === s) return fromCode

  return Status.byDescription(s)
}

export function pokemonFromJson(raw: PokemonJson, game: OracleGame): Pokemon {
  if (!raw.moves || raw.moves.length !== 4) {
    throw new Error("Pokemon JSON requires exactly 4 moves")
  }

  const moveOpts = { game }
  const m1 = new Move(raw.moves[0].name, { ...raw.moves[0], ...moveOpts })
  const m2 = new Move(raw.moves[1].name, { ...raw.moves[1], ...moveOpts })
  const m3 = new Move(raw.moves[2].name, { ...raw.moves[2], ...moveOpts })
  const m4 = new Move(raw.moves[3].name, { ...raw.moves[3], ...moveOpts })
  const moveSet = new MoveSet(m1, m2, m3, m4, raw.activeMovePosition ?? 1)

  const abilityName = raw.ability ?? ""

  return new Pokemon(raw.name, {
    nature: raw.nature,
    item: raw.item,
    ability: new Ability(abilityName, raw.abilityOn ?? false),
    teraType: raw.teraType,
    teraTypeActive: raw.teraTypeActive,
    evs: raw.evs,
    ivs: raw.ivs,
    boosts: raw.boosts,
    bonusBoosts: raw.bonusBoosts,
    status: statusFromJson(raw.status),
    hpPercentage: raw.hpPercentage,
    commanderActive: raw.commanderActive,
    higherStat: raw.higherStat as StatIDExceptHP | undefined,
    isAttacker: raw.isAttacker,
    moveSet
  })
}
