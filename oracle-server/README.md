# VGC oracle HTTP server

Headless batch API that mirrors the Angular damage pipeline (`DamageCalculatorService` delegates to [`oracle-engine`](../src/lib/oracle/oracle-engine.ts)): same `@robsonbittencourt/calc` generation rules, adjusters (see [`calc-adjuster-chain.ts`](../src/lib/oracle/calc-adjuster-chain.ts)), field mapping, and `fromExisting` / Champions max IV behavior.

## Why esbuild

Source lives under the main app’s `src/` tree with `@lib` / `@data` path aliases. Node does not resolve those aliases when running TypeScript directly. The server **bundles** entrypoints with `esbuild` and `--alias:@lib=../src/lib` (and the other app aliases) so paths match the calculator. `@angular/core` is installed here only so `@Injectable` stubs on adjusters load at runtime; they are not used reflectively.

## Run

```bash
cd oracle-server
npm install
npm start
```

`PORT` defaults to `8765`.

## HTTP

| Method | Path      | Body         | Response               |
| ------ | --------- | ------------ | ---------------------- |
| GET    | `/health` | —            | `{"ok":true}`          |
| POST   | `/batch`  | JSON (below) | Batch response (below) |

## Batch request JSON

Top level:

- `game` (required): `"sv"` | `"champions"` — matches calculator meta (gen 9 vs gen 0, Champions forces max IVs on Smogon Pokémon).
- `useSpsMode` (optional): when `true` with Champions, damage **descriptions** use SP labels like the UI (`formatOracleDescription`); damage numbers are unchanged.
- `includeSpeedContext` (optional, default **`true`**): attaches structured speed/initiative metadata to `single`, `double`, and each row of `allMoves` (`speedContext`), including effective Speed lines, attacker move priority for the evaluated move (base vs Gale Wings / Prankster adjustments when applicable), and field toggles. Set `false` for smaller payloads.
- `requests` (required): array of items.

Each **request item**:

- `kind`: `"single"` | `"allMoves"` | `"double"` | `"speedCompare"`
- `field`: object matching [`Field`](../src/lib/model/field.ts) / [`FieldSide`](../src/lib/model/field.ts) constructor options (weather, terrain, ruin flags, trick room, neutralizing gas, fairy aura, **`alphaSide`**, **`betaSide`**, legacy **`attackerSide`** / **`defenderSide`**, screen flags, etc.). **`alphaSide`** is merged into the internal left trainer slot (`attackerSide`); **`betaSide`** into the right slot (`defenderSide`). If both `alphaSide` and `attackerSide` are present, **`alphaSide` wins** for that slot (same for `betaSide` vs `defenderSide`). Omitted booleans default like `new Field()`.
- `rightIsDefender` (optional, default `true`): same meaning as in the app (`FieldMapper.toSmogon`).
- `attacker`, `defender`: Pokémon payloads (below). Omit `defender` only for `speedCompare`. For **`speedCompareMode: opposingTrainers`**, put the **α trainer’s Pokémon** in **`attacker`** and the **β trainer’s Pokémon** in **`secondAttacker`** so **`field.alphaSide` / `field.betaSide`** Tailwind lines up with initiative math.
- `secondAttacker`: required when `kind === "double"` or `kind === "speedCompare"`.
- `opposingSides` (optional, `speedCompare` only): legacy boolean; `false` forces allied doubles Speed semantics (both Pokémon read **internal** `attackerSide` modifiers after JSON merge). Prefer **`speedCompareMode`**.
- `speedCompareMode` (optional, `speedCompare` only): `"opposingTrainers"` | `"alliedDoubles"`. When set, overrides `opposingSides`. **`opposingTrainers`** (default when omitted): batch **`attacker`** (α) uses **`field.alphaSide`** (or legacy `attackerSide`) for Tailwind / side-scoped Speed; **`secondAttacker`** (β) uses **`field.betaSide`** (or legacy `defenderSide`). **`alliedDoubles`**: both combatants read **internal** `attackerSide` (same as ordering two allied attackers into one target).

`speedCompare` resolves **which of two attackers moves first** using the same priority ladder as doubles dual-target ordering (including Gale Wings +1 on Flying moves at full HP, Prankster +1 on Status-category moves, Trick Room speed inversion on ties, then effective Speed). Prefer **`field.alphaSide`** / **`field.betaSide`** for trainer halves so Tailwind lines up with **`speedCompareMode: opposingTrainers`** (batch **`attacker`** = α, **`secondAttacker`** = β). Legacy **`attackerSide`** / **`defenderSide`** still work. Use **`"alliedDoubles"`** when ordering two allies (same as `double` ordering). Legacy **`opposingSides`: `false`** also selects allied doubles mode. Response item has `kind: "speedCompare"` with priorities, effective speeds, and a short explanation string.

Damage outcomes include `damageRollInterpretation` explaining that min–max percents come from the calculator’s roll sample for that interaction.

Each **Pokémon payload**:

- `name` (required): species string as in the dex (e.g. `"Raging Bolt"`).
- `moves` (required): length **4**. Each move: `{ "name": "Thunderbolt", "hits"?, "alliesFainted"?, "lastMoveFailed"? }`. Move data merges Champions overrides when `game === "champions"`.
- `activeMovePosition` (optional): `1`–`4`, default `1` — which move is “active” for `single` (`attacker.move`).
- Optional stat/build fields: `nature`, `item`, `ability`, `abilityOn`, `teraType`, `teraTypeActive`, `evs`, `ivs`, `boosts`, `bonusBoosts`, `status` (status code like `par` or description like `Paralysis`), `hpPercentage`, `commanderActive`, `higherStat`, `isAttacker`.

## Batch response JSON

```json
{
  "results": [
    { "ok": true, "index": 0, "result": {} },
    { "ok": false, "index": 1, "error": "message" }
  ]
}
```

Success `result` shape depends on `kind`:

- **`single`**: one [`DamageOutcomeJson`](src/batch-types.ts) — `moveName`, `moveDesc`, `koChanceText`, `damagePercentMin` / `damagePercentMax` (parsed from `moveDesc`), `damageRolls` (16-roll rows as `number[][]`), `description`, `afterTurnResidualHp`.
- **`allMoves`**: `DamageOutcomeJson[]` in move table order.
- **`double`**: [`DoubleOutcomeJson`](src/batch-types.ts) — combined KO text, range max percent, multi-line description, per-attacker roll grids, ordering matches speed/priority (`orderPairBySpeed`).

## RL: feature-only oracle

Typical stacking (per focused defender slot, per attacker move):

- Normalized `damagePercentMin`, `damagePercentMax`, or mean damage from `damageRolls` vs defender max HP if you join HP elsewhere.
- Bag-of-words or hashed `koChanceText`, or a separate parser for probabilities later.
- Concatenate multiple batch rows for “my active vs each foe slot” and repeat for swap targets.

Auxiliary heads can predict these oracle fields from a backbone that only sees noisy simulator state.

## RL: search (MCTS)

Use `single` / `allMoves` / `double` leaves only when the leaf state matches full-information assumptions (known sets, known field). Otherwise marginalize over meta presets or drop oracle channels for that branch.

## Tests

```bash
npm test
```

Builds a bundled test file with the same aliases, then runs `node --test`. Includes a golden parity case aligned with [`damage-calculator.service.spec.ts`](../src/lib/damage-calculator/damage-calculator.service.spec.ts) (Raging Bolt Thunderbolt vs Flutter Mane) and an HTTP smoke test on an ephemeral port.
