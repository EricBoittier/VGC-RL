import { importProvidersFrom, provideZonelessChangeDetection } from "@angular/core"
import { bootstrapApplication } from "@angular/platform-browser"
import { provideAnimations } from "@angular/platform-browser/animations"
import { AppRoutingModule } from "@app/app-routing.module"
import { AppComponent } from "@app/app.component"
import { CALC_ADJUSTERS } from "@lib/damage-calculator/calc-adjuster/calc-adjuster"
import { SPECIFIC_DAMAGE_CALCULATORS } from "@lib/damage-calculator/specific-damage-calculator/specific-damage-calculator"
import { CALC_ADJUSTER_CLASSES_IN_ORDER, SPECIFIC_DAMAGE_CALCULATOR_CLASSES } from "@lib/oracle/calc-adjuster-chain"
import { migrateUserData } from "@data/store/utils/migrate-user-data"

migrateUserData()

bootstrapApplication(AppComponent, {
  providers: [
    importProvidersFrom(AppRoutingModule),
    provideAnimations(),
    provideZonelessChangeDetection(),
    ...CALC_ADJUSTER_CLASSES_IN_ORDER.map(useClass => ({ provide: CALC_ADJUSTERS, useClass, multi: true as const })),
    ...SPECIFIC_DAMAGE_CALCULATOR_CLASSES.map(useClass => ({ provide: SPECIFIC_DAMAGE_CALCULATORS, useClass, multi: true as const }))
  ]
}).catch(err => console.error(err))
