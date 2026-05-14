import { CalcAdjuster } from "@lib/damage-calculator/calc-adjuster/calc-adjuster"
import { FairyAuraAdjuster } from "@lib/damage-calculator/calc-adjuster/fairy-aura-adjuster"
import { LastRespectsAdjuster } from "@lib/damage-calculator/calc-adjuster/last-respects-adjuster"
import { NeutralizingGasAdjuster } from "@lib/damage-calculator/calc-adjuster/neutralizing-gas-adjuster"
import { OgerponAdjuster } from "@lib/damage-calculator/calc-adjuster/ogerpon-adjuster"
import { RageFistAdjuster } from "@lib/damage-calculator/calc-adjuster/rage-fist-adjuster"
import { RuinsAbilityAdjuster } from "@lib/damage-calculator/calc-adjuster/ruins-ability-adjuster"
import { StompingTantrumAdjuster } from "@lib/damage-calculator/calc-adjuster/stomping-tantrum-adjuster"
import { ZacianZamazentaAdjuster } from "@lib/damage-calculator/calc-adjuster/zacian-zamazenta-adjuster"
import { SpecificDamageCalculator } from "@lib/damage-calculator/specific-damage-calculator/specific-damage-calculator"
import { RuinationCalculator } from "@lib/damage-calculator/specific-damage-calculator/ruination-calculator"

export const CALC_ADJUSTER_CLASSES_IN_ORDER: Array<new () => CalcAdjuster> = [RuinsAbilityAdjuster, FairyAuraAdjuster, LastRespectsAdjuster, RageFistAdjuster, StompingTantrumAdjuster, ZacianZamazentaAdjuster, NeutralizingGasAdjuster, OgerponAdjuster]

export const SPECIFIC_DAMAGE_CALCULATOR_CLASSES: Array<new () => SpecificDamageCalculator> = [RuinationCalculator]
