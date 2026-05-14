import { inject, Injectable } from "@angular/core"
import { CalculatorStore } from "@data/store/calculator-store"
import { CALC_ADJUSTERS } from "@lib/damage-calculator/calc-adjuster/calc-adjuster"
import { DamageResult } from "@lib/damage-calculator/damage-result"
import { SPECIFIC_DAMAGE_CALCULATORS } from "@lib/damage-calculator/specific-damage-calculator/specific-damage-calculator"
import { FieldMapper } from "@lib/field-mapper"
import { Field } from "@lib/model/field"
import { Move } from "@lib/model/move"
import { Pokemon } from "@lib/model/pokemon"
import {
  calculateOracleDoubleAttack,
  calculateOracleMultiResult,
  calculateOracleResult,
  oracleDamageDescription,
  oracleKoChanceText,
  oracleMaxPercentageDamage,
  oracleMultiDamageDescription,
  OracleCalculationDeps,
  OracleContext
} from "@lib/oracle/oracle-engine"
import { MultiResult } from "@robsonbittencourt/calc"

@Injectable({
  providedIn: "root"
})
export class DamageCalculatorService {
  adjusters = inject(CALC_ADJUSTERS)
  specificDamageCalculators = inject(SPECIFIC_DAMAGE_CALCULATORS)
  fieldMapper = inject(FieldMapper)
  calculatorStore = inject(CalculatorStore)

  private oracleCtx(): OracleContext {
    return {
      game: this.calculatorStore.isChampions() ? "champions" : "sv",
      useSpsMode: this.calculatorStore.useSpsMode()
    }
  }

  private oracleDeps(): OracleCalculationDeps {
    return {
      adjusters: this.adjusters,
      specificDamageCalculators: this.specificDamageCalculators,
      fieldMapper: this.fieldMapper
    }
  }

  calcDamage(attacker: Pokemon, target: Pokemon, field: Field, rightIsDefender = true): DamageResult {
    const ctx = this.oracleCtx()
    const deps = this.oracleDeps()
    const result = calculateOracleResult(ctx, deps, attacker, target, attacker.move, field, rightIsDefender)

    return new DamageResult(
      attacker,
      target,
      attacker.move.name,
      result.moveDesc(),
      oracleKoChanceText(result),
      oracleMaxPercentageDamage(result),
      oracleDamageDescription(ctx, result),
      result.damage,
      undefined,
      undefined,
      result.afterTurn().residualHpInTurn(1) ?? 0
    )
  }

  calcDamageAllAttacks(attacker: Pokemon, target: Pokemon, field: Field, rightIsDefender: boolean): DamageResult[] {
    const ctx = this.oracleCtx()
    const deps = this.oracleDeps()

    return attacker.moveSet.moves.map(move => {
      const result = calculateOracleResult(ctx, deps, attacker, target, move, field, rightIsDefender)

      return new DamageResult(
        attacker,
        target,
        move.name,
        result.moveDesc(),
        oracleKoChanceText(result),
        oracleMaxPercentageDamage(result),
        oracleDamageDescription(ctx, result),
        result.damage,
        undefined,
        undefined,
        result.afterTurn().residualHpInTurn(1) ?? 0
      )
    })
  }

  calcDamageForTwoAttackers(attacker: Pokemon, secondAttacker: Pokemon, target: Pokemon, field: Field, rightIsDefender = true): DamageResult {
    const ctx = this.oracleCtx()
    const deps = this.oracleDeps()
    const { multiResult, firstAttacker, secondAttacker: secondAttackerOrdered, prepOneMoveSmogon, prepTwoMoveSmogon } = calculateOracleDoubleAttack(ctx, deps, attacker, secondAttacker, target, field, rightIsDefender)

    const firstResult = multiResult.results[0]
    const secondResult = multiResult.results[1]

    return new DamageResult(
      firstAttacker,
      target,
      firstAttacker.move.name,
      multiResult.resultString(),
      multiResult.getHKO(),
      multiResult.rangePercentage().max,
      oracleMultiDamageDescription(ctx, multiResult, prepOneMoveSmogon, prepTwoMoveSmogon),
      firstResult.damage,
      secondAttackerOrdered,
      secondResult.damage,
      firstResult.afterTurn().residualHpInTurn(1) ?? 0
    )
  }

  koChanceForOneAttacker(attacker: Pokemon, target: Pokemon, field: Field, rightIsDefender = true): string {
    const result = calculateOracleResult(this.oracleCtx(), this.oracleDeps(), attacker, target, attacker.move, field, rightIsDefender)

    return oracleKoChanceText(result)
  }

  koChanceForTwoAttackers(attacker: Pokemon, secondAttacker: Pokemon, target: Pokemon, field: Field, rightIsDefender = true): string {
    return this.calcDamageForTwoAttackers(attacker, secondAttacker, target, field, rightIsDefender).koChance
  }

  calcDamageValueForTwoAttackers(attacker: Pokemon, secondAttacker: Pokemon, target: Pokemon, field: Field, rightIsDefender = true): MultiResult {
    return calculateOracleMultiResult(this.oracleCtx(), this.oracleDeps(), attacker, secondAttacker, target, field, rightIsDefender)
  }

  calculateResult(attacker: Pokemon, target: Pokemon, move: Move, field: Field, rightIsDefender: boolean, secondAttacker?: Pokemon) {
    return calculateOracleResult(this.oracleCtx(), this.oracleDeps(), attacker, target, move, field, rightIsDefender, secondAttacker)
  }
}
