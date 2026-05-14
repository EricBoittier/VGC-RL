import {
  calculateOracleDoubleAttack,
  calculateOracleResult,
  createDefaultOracleCalculationDeps,
  oracleDamageDescription,
  oracleKoChanceText,
  oracleMultiDamageDescription,
  OracleCalculationDeps,
  OracleContext,
  parseDamagePercentRange
} from "@lib/oracle/oracle-engine"
import type { BatchErr, BatchOk, BatchRequestBody, BatchRequestItem, BatchResponseBody, BatchSpeedCompareRequest, DamageOutcomeJson, DoubleOutcomeJson } from "./batch-types.js"
import { fieldFromJson, pokemonFromJson } from "./domain-from-json.js"
import { buildSpeedCompareOutcome, buildSpeedContextDouble, buildSpeedContextSingle } from "./speed-context.js"

const defaultDeps: OracleCalculationDeps = createDefaultOracleCalculationDeps()

const DAMAGE_ROLL_NOTE = "Damage percents are min–max versus max HP across the calculator roll sample for this interaction. KO strings summarize cumulative KO odds from those rolls (not extra hypothetical ranges)."

export function rollsTo2d(damage: unknown): number[][] {
  if (damage == null) return []

  if (typeof damage === "number") return [[damage]]

  if (!Array.isArray(damage)) return []

  if (damage.length === 0) return []

  if (typeof (damage as number[])[0] === "number") return [damage as number[]]

  return damage as number[][]
}

function outcomeFromResult(ctx: OracleContext, moveName: string, result: ReturnType<typeof calculateOracleResult>): DamageOutcomeJson {
  const pct = parseDamagePercentRange(result.moveDesc())

  return {
    moveName,
    moveDesc: result.moveDesc(),
    koChanceText: oracleKoChanceText(result),
    damagePercentMin: pct.min,
    damagePercentMax: pct.max,
    damageRolls: rollsTo2d(result.damage),
    description: oracleDamageDescription(ctx, result),
    afterTurnResidualHp: result.afterTurn().residualHpInTurn(1) ?? null,
    damageRollInterpretation: DAMAGE_ROLL_NOTE
  }
}

function resolveSpeedCompareMode(sc: BatchSpeedCompareRequest): "alliedDoubles" | "opposingTrainers" {
  if (sc.speedCompareMode === "alliedDoubles" || sc.speedCompareMode === "opposingTrainers") {
    return sc.speedCompareMode
  }

  return sc.opposingSides === false ? "alliedDoubles" : "opposingTrainers"
}

function runOneRequest(ctx: OracleContext, deps: OracleCalculationDeps, req: BatchRequestItem, index: number, includeSpeedContext: boolean): BatchOk | BatchErr {
  try {
    const field = fieldFromJson(req.field)

    if (req.kind === "speedCompare") {
      const sc = req as BatchSpeedCompareRequest
      const attacker = pokemonFromJson(sc.attacker, ctx.game)
      const secondAttacker = pokemonFromJson(sc.secondAttacker, ctx.game)
      const speedMode = resolveSpeedCompareMode(sc)

      return { ok: true, index, result: buildSpeedCompareOutcome(attacker, secondAttacker, field, speedMode) }
    }

    const rightIsDefender = req.rightIsDefender ?? true
    const attacker = pokemonFromJson(req.attacker, ctx.game)
    const defender = pokemonFromJson(req.defender, ctx.game)

    if (req.kind === "double") {
      if (!req.secondAttacker) {
        return { ok: false, index, error: "double requests require secondAttacker" }
      }

      const secondAttacker = pokemonFromJson(req.secondAttacker, ctx.game)
      const { multiResult, prepOneMoveSmogon, prepTwoMoveSmogon, firstAttacker, secondAttacker: secondOrdered } = calculateOracleDoubleAttack(ctx, deps, attacker, secondAttacker, defender, field, rightIsDefender)

      const firstResult = multiResult.results[0]
      const secondResult = multiResult.results[1]

      const doublePayload: DoubleOutcomeJson = {
        kind: "double",
        koChanceText: multiResult.getHKO(),
        combinedMoveDesc: multiResult.resultString(),
        damagePercentMax: multiResult.rangePercentage().max,
        description: oracleMultiDamageDescription(ctx, multiResult, prepOneMoveSmogon, prepTwoMoveSmogon),
        firstMoveName: firstAttacker.move.name,
        secondMoveName: secondOrdered.move.name,
        firstAttackerRolls: rollsTo2d(firstResult.damage),
        secondAttackerRolls: rollsTo2d(secondResult.damage),
        afterTurnResidualHpFirst: firstResult.afterTurn().residualHpInTurn(1) ?? null,
        damageRollInterpretation: DAMAGE_ROLL_NOTE
      }

      if (includeSpeedContext) {
        doublePayload.speedContext = buildSpeedContextDouble(firstAttacker, secondOrdered, field)
      }

      return { ok: true, index, result: doublePayload }
    }

    if (req.kind === "allMoves") {
      const rows = attacker.moveSet.moves.map(move => {
        const result = calculateOracleResult(ctx, deps, attacker, defender, move, field, rightIsDefender)
        const row = outcomeFromResult(ctx, move.name, result)

        if (includeSpeedContext) {
          row.speedContext = buildSpeedContextSingle(attacker, defender, field, move)
        }

        return row
      })

      return { ok: true, index, result: rows }
    }

    const result = calculateOracleResult(ctx, deps, attacker, defender, attacker.move, field, rightIsDefender)
    const row = outcomeFromResult(ctx, attacker.move.name, result)

    if (includeSpeedContext) {
      row.speedContext = buildSpeedContextSingle(attacker, defender, field)
    }

    return { ok: true, index, result: row }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)

    return { ok: false, index, error: message }
  }
}

export function handleOracleBatch(body: BatchRequestBody, deps: OracleCalculationDeps = defaultDeps): BatchResponseBody {
  const ctx: OracleContext = {
    game: body.game,
    useSpsMode: body.useSpsMode
  }

  const includeSpeedContext = body.includeSpeedContext ?? true

  const results = body.requests.map((req, index) => runOneRequest(ctx, deps, req, index, includeSpeedContext))

  return { results }
}
