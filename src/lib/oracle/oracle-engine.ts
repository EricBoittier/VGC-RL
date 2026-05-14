import { CalcAdjuster } from "@lib/damage-calculator/calc-adjuster/calc-adjuster"
import { RollLevelConfig } from "@lib/damage-calculator/roll-level-config"
import { SpecificDamageCalculator } from "@lib/damage-calculator/specific-damage-calculator/specific-damage-calculator"
import { FieldMapper } from "@lib/field-mapper"
import { Field } from "@lib/model/field"
import { Move } from "@lib/model/move"
import { Pokemon } from "@lib/model/pokemon"
import { CALC_ADJUSTER_CLASSES_IN_ORDER, SPECIFIC_DAMAGE_CALCULATOR_CLASSES } from "@lib/oracle/calc-adjuster-chain"
import { orderPairBySpeed } from "@lib/speed-calculator/order-pair-by-speed"
import { fromExisting } from "@lib/smogon/smogon-pokemon-builder"
import { evToSp } from "@lib/utils/ev-sp-converter"
import { calculate, calculateMulti, Generations, Move as MoveSmogon, MultiResult, Result, Pokemon as PokemonSmogon, Field as FieldSmogon } from "@robsonbittencourt/calc"
import { Generation } from "@robsonbittencourt/calc/dist/data/interface"

export type OracleGame = "sv" | "champions"

export type OracleContext = {
  game: OracleGame
  useSpsMode?: boolean
}

export type OracleCalculationDeps = {
  adjusters: CalcAdjuster[]
  specificDamageCalculators: SpecificDamageCalculator[]
  fieldMapper: FieldMapper
}

export const ORACLE_ZERO_DAMAGE_ROLLS = Array(RollLevelConfig.ROLLS_NUMBER).fill(0)

export function createDefaultOracleCalculationDeps(): OracleCalculationDeps {
  return {
    adjusters: CALC_ADJUSTER_CLASSES_IN_ORDER.map(Adj => new Adj()),
    specificDamageCalculators: SPECIFIC_DAMAGE_CALCULATOR_CLASSES.map(C => new C()),
    fieldMapper: new FieldMapper()
  }
}

export function oracleGeneration(ctx: OracleContext): Generation {
  return Generations.get(ctx.game === "champions" ? 0 : 9)
}

function prepareCalculation(ctx: OracleContext, deps: OracleCalculationDeps, attacker: Pokemon, target: Pokemon, move: Move, field: Field, rightIsDefender: boolean, secondAttacker?: Pokemon) {
  const gen = oracleGeneration(ctx)
  const smogonField = deps.fieldMapper.toSmogon(field, rightIsDefender)

  const moveSmogon = new MoveSmogon(gen, move.name)
  moveSmogon.isCrit = rightIsDefender ? field.attackerSide.isCriticalHit : field.defenderSide.isCriticalHit
  moveSmogon.isStellarFirstUse = true
  moveSmogon.hits = +move.hits

  const forceMaxIvs = ctx.game === "champions"
  const smogonAttacker = fromExisting(attacker, forceMaxIvs)
  const smogonTarget = fromExisting(target, forceMaxIvs)

  deps.adjusters.forEach(a => a.adjust(smogonAttacker, smogonTarget, move, moveSmogon, smogonField, secondAttacker, field))

  return { gen, smogonAttacker, smogonTarget, moveSmogon, smogonField }
}

function calculateDamageWithSpecifics(deps: OracleCalculationDeps, gen: Generation, attacker: PokemonSmogon, target: PokemonSmogon, move: MoveSmogon, field: FieldSmogon, moveModel: MoveSmogon): Result {
  const applicableCalculator = deps.specificDamageCalculators.find(calculator => calculator.isApplicable(moveModel))

  if (applicableCalculator) {
    const baseResult = calculate(gen, attacker, target, move, field)

    return applicableCalculator.calculate(target, baseResult)
  }

  return calculate(gen, attacker, target, move, field)
}

export function normalizeOracleResultDamage(result: Result): void {
  if (!result.damage) {
    result.damage = [...ORACLE_ZERO_DAMAGE_ROLLS]
  }

  if (typeof result.damage === "number") {
    result.damage = Array(RollLevelConfig.ROLLS_NUMBER).fill(result.damage)
  }
}

export function calculateOracleResult(ctx: OracleContext, deps: OracleCalculationDeps, attacker: Pokemon, target: Pokemon, move: Move, field: Field, rightIsDefender: boolean, secondAttacker?: Pokemon): Result {
  const prep = prepareCalculation(ctx, deps, attacker, target, move, field, rightIsDefender, secondAttacker)
  const result = calculateDamageWithSpecifics(deps, prep.gen, prep.smogonAttacker, prep.smogonTarget, prep.moveSmogon, prep.smogonField, prep.moveSmogon)

  normalizeOracleResultDamage(result)

  return result
}

export type OracleDoubleAttackOutcome = {
  multiResult: MultiResult
  firstAttacker: Pokemon
  secondAttacker: Pokemon
  prepOneMoveSmogon: MoveSmogon
  prepTwoMoveSmogon: MoveSmogon
}

export function calculateOracleDoubleAttack(ctx: OracleContext, deps: OracleCalculationDeps, attacker: Pokemon, secondAttacker: Pokemon, target: Pokemon, field: Field, rightIsDefender: boolean): OracleDoubleAttackOutcome {
  const [firstAttacker, secondAttackerOrdered] = orderPairBySpeed(attacker, secondAttacker, field, { mode: "alliedDoubles" })

  const prepOne = prepareCalculation(ctx, deps, firstAttacker, target, firstAttacker.move, field, rightIsDefender, secondAttackerOrdered)
  const prepTwo = prepareCalculation(ctx, deps, secondAttackerOrdered, target, secondAttackerOrdered.move, field, rightIsDefender, firstAttacker)

  const gen = oracleGeneration(ctx)

  const multiResult = calculateMulti(gen, [prepOne.smogonAttacker, prepTwo.smogonAttacker], prepOne.smogonTarget, [prepOne.moveSmogon, prepTwo.moveSmogon], prepOne.smogonField)

  normalizeOracleMultiResultDamage(multiResult)

  return {
    multiResult,
    firstAttacker,
    secondAttacker: secondAttackerOrdered,
    prepOneMoveSmogon: prepOne.moveSmogon,
    prepTwoMoveSmogon: prepTwo.moveSmogon
  }
}

export function calculateOracleMultiResult(ctx: OracleContext, deps: OracleCalculationDeps, attacker: Pokemon, secondAttacker: Pokemon, target: Pokemon, field: Field, rightIsDefender: boolean): MultiResult {
  return calculateOracleDoubleAttack(ctx, deps, attacker, secondAttacker, target, field, rightIsDefender).multiResult
}

export function normalizeOracleMultiResultDamage(multiResult: MultiResult): void {
  multiResult.results.forEach(r => normalizeOracleResultDamage(r))
}

export function oracleKoChanceText(result: Result): string {
  try {
    return result.kochance().text
  } catch (ex) {
    return "Does not cause any damage"
  }
}

export function oracleMaxPercentageDamage(result: Result): number {
  return +result.moveDesc().substring(result.moveDesc().indexOf("- ") + 1, result.moveDesc().indexOf("%"))
}

export function injectAdjustedBp(description: string, move: MoveSmogon): string {
  const adjustedBp = move.overrides?.basePower

  if (adjustedBp === undefined) return description

  const replacement = `${move.name} (${adjustedBp} BP)`

  if (description.includes(replacement)) return description

  return description.replaceAll(move.name, replacement)
}

export function formatOracleDescription(ctx: OracleContext, description: string): string {
  if (ctx.game === "champions" && ctx.useSpsMode) {
    return description.replace(/\b(\d+)([+-]?)\s+(HP|Atk|Def|SpA|SpD|Spe)\b/g, (_match, ev, nature, stat) => {
      return `${evToSp(+ev)}${nature} ${stat}`
    })
  }

  return description
}

export function oracleDamageDescription(ctx: OracleContext, result: Result): string {
  try {
    return injectAdjustedBp(formatOracleDescription(ctx, result.desc()), result.move)
  } catch (error) {
    return formatOracleDescription(ctx, `${result.attacker.name} ${result.move.name} vs. ${result.defender.name}: 0-0 (0 - 0%) -- possibly the worst move ever`)
  }
}

export function oracleMultiDamageDescription(ctx: OracleContext, multiResult: MultiResult, moveSmogonOne: MoveSmogon, moveSmogonTwo: MoveSmogon): string {
  let description = multiResult.desc()

  description = formatOracleDescription(ctx, description)
  description = injectAdjustedBp(description, moveSmogonOne)
  description = injectAdjustedBp(description, moveSmogonTwo)

  return description
}

export function parseDamagePercentRange(moveDesc: string): { min: number | null; max: number | null } {
  const parenMatch = moveDesc.match(/\(([\d.]+)\s*-\s*([\d.]+)%\)/)

  if (parenMatch) {
    return { min: +parenMatch[1], max: +parenMatch[2] }
  }

  const plainMatch = moveDesc.match(/([\d.]+)\s*-\s*([\d.]+)%/)

  if (plainMatch) {
    return { min: +plainMatch[1], max: +plainMatch[2] }
  }

  return { min: null, max: null }
}
