# Diseño técnico de arquitectura HU/MW (2026-11-13)

**Estado:** diseño, no implementación. No se activa multiway, no se escribe en
`data/`, no se cambian contratos ni se regeneran artefactos.

**Base:** auditoría `AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md` y
discrepancias `DISCREPANCIAS_AUDITORIA_2026-11-13.md`.

**Objetivo:** definir una arquitectura conjunta en la que HU y multiway sean
dos modos del mismo contrato, no dos caminos que se confunden. La prioridad es
corregir HU antes de activar MW.

## 1. Principios

1. **Una sola interpretación preflop.** La acción, el denominador, el agresor y
   la cobertura salen de un contrato único. La ruta live no reimplementa la
   lectura.
2. **Estado explícito, nunca cero silencioso.** Sin tabla, sin perfil o sin
   muestra se devuelve `unknown`/`coverage_gap`, no una frecuencia 0.
3. **HU y MW son modos distintos.** `n_players>2` no es un detalle de tamaño:
   cambia el objeto de rango, la equity, el EV y la política.
4. **Rango por rival, no unión.** `RangeState.union()` no representa la
   distribución conjunta de varios rivales. Puede quedar como baseline
   etiquetado, nunca como equity MW.
5. **Equity actual, showdown y EV son campos distintos.** Cada uno con
   muestreo, semilla, incertidumbre y fuente.
6. **Sin soporte declarado no hay recomendación presentada como válida.**
   `multiway_soportado=False` debe ser visible y accionable, no una etiqueta.
7. **Trazabilidad.** Toda decisión debe poder reconstruirse con commit, hashes
   de artefactos, versión de contrato y semilla.
8. **No se activa por tests.** La activación exige validación mecánica,
   estadística y estratégica, y revisión.

## 2. Vista de componentes

```
┌─────────────────────────────────────────────────────────────┐
│ 0. Snapshot y procedencia                                    │
│    commit, hashes, versión de contrato, ventana de datos     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 1. Contrato preflop                                           │
│    PreflopDecision: acción, denominador, raises/limps, vs,   │
│    cobertura, estado                                        │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 2. Estado de la mano                                          │
│    hero, rivales activos, stacks, bote, board, side pots     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 3. Proveedor de rangos por rival                              │
│    PlayerRange: pesos, reach, perfil, fuente, n_eff,         │
│    cobertura, incertidumbre                                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 4. MultiwayRangeSet                                           │
│    un rango por rival + blockers compartidos + correlación    │
│    declarada; nunca una sola unión                            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 5. Motor de equity y EV                                       │
│    CurrentEquity | ShowdownEquity | EvByAction                │
│    HU o MW; exacto o Monte Carlo; IC y semilla                │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 6. Política                                                   │
│    HU: reglas actuales corregidas                             │
│    MW: reglas MW con soporte declarado; sin fallback HU       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 7. Explicación y telemetría                                   │
│    fuente, cobertura, n_eff, IC, semilla, versión, motivo     │
└─────────────────────────────────────────────────────────────┘
```

## 3. Contrato preflop canónico

Concepto, no implementación:

```
PreflopDecision:
  player
  action            # open/limp/call/3bet/4bet/fold/check...
  denom             # no_raise | facing_open | facing_3bet
  raises_before
  limps_before
  callers_before
  last_aggressor
  last_aggressor_amount
  category          # categoría de entrenamiento
  status            # resolved | unresolved | non_decision
  reason
  coverage          # exact | alias | gap | impossible | unknown
```

Reglas de diseño:

- El contrato es la única fuente de `denom`, `category`, `raises_before` y
  `last_aggressor`.
- `b` se clasifica por importe y contexto; no por la letra. Un `b` corto sin
  subida previa es limp; un `b` posterior a subida es agresión.
- `fold`, `bb_check`, `call_limp`, `squeeze`, `rol` y `fold_vs_*` son estados
  explícitos, no sinónimos de `open`.
- Un estado `unresolved` no se convierte en `open` por defecto. Debe propagar
  `unknown` y una política de decisión.
- La ruta live y la de entrenamiento consumen la misma función. La lectura
  legacy queda como compatibilidad auditada, no como fuente de tablas.

Salida mínima para cada spot:

```
{denom, category, status, coverage, source, n, reason}
```

## 4. Rangos por rival

### 4.1 `PlayerRange`

```
PlayerRange:
  player_id
  weights: (1326,)          # masa por combo
  reach: (1326,)            # probabilidad de haber llegado al spot
  profile
  profile_source           # history | stake | unknown
  prior_source             # exact | alias | flat | unknown
  n_obs
  n_eff                    # (Σw)² / Σw²
  coverage                 # exact | alias | gap | impossible
  uncertainty              # IC o clase de incertidumbre
```

Invariantes:

- `weights >= 0`; suma > 0 o estado `empty`/`unknown`.
- Blockers del hero y del board aplicados antes de normalizar.
- `reach` no se mezcla con `weights` sin declarar la operación.
- No se normaliza un `FLAT_PRIOR` como si fuera una lectura observada.
- Un rival sin datos no recibe un rango estrecho: recibe `unknown` con
  incertidumbre amplia.

### 4.2 `MultiwayRangeSet`

```
MultiwayRangeSet:
  hero
  opponents: [PlayerRange]
  shared_blockers
  correlation_model        # independent | latent | sampled_joint
  n_players
  source
```

Operaciones:

- `current_equity(hero, board, set)`.
- `showdown_equity(hero, board, set, n_samples, seed)`.
- `update(action_by_player, street)` por rival, no una actualización agregada.
- `effective_combos()` por rival y del conjunto.

Prohibiciones:

- `union()` no es una operación de equity MW.
- No se puede etiquetar una equity de un solo rival como “multiway”.
- No se puede usar `n_players` como sustituto del conjunto de rangos.
- No se puede sumar masa de varios rivales y normalizar como si fuera una
  distribución conjunta.

### 4.3 Aproximación declarada

La distribución conjunta exacta sobre `1326^N` no es viable para N grande. El
diseño admite tres niveles, siempre etiquetados:

1. **Exacto por enumeración** para casos pequeños y validación.
2. **Muestreo conjunto** con un modelo declarado:
   - independencia condicionada por acción, o
   - variable latente compartida (estilo/agresión), o
   - cópula/mezcla de arquetipos.
3. **Baseline agregado** (unión o un solo rival) solo para comparación y
   nunca para una recomendación presentada como MW.

La etiqueta debe viajar con el número: `correlation_model`, `n_samples`,
`seed`, `ci`.

## 5. Equity y EV

### 5.1 Tres objetos separados

| Objeto | Pregunta | Board | Rivales | Uso |
|---|---|---|---|---|
| `CurrentEquity` | ¿Cómo estoy ahora? | actual | conjunto | lectura de calle |
| `ShowdownEquity` | ¿Cómo termino si no foldea nadie? | runout | conjunto | equidad final |
| `EvByAction` | ¿Qué EV tiene cada acción? | actual + árbol | conjunto | decisión |

No se permite un campo llamado solo `equity` que cambie de significado según
la calle. El nombre debe decir qué mide.

### 5.2 `ShowdownEquity` multiway

- Se muestrea una combinación legal para cada rival, no una unión.
- Se descuentan blockers entre todos los rivales y el board.
- Se reparte el bote entre ganadores; los empates se dividen.
- Se contabilizan side pots y stacks efectivos; el EV no puede asumir que
  todos los rivales igualan todo.
- Se reporta `n_samples`, `seed`, media, error estándar o IC.
- La comparación de dos configuraciones exige el mismo `n_samples` y semilla,
  o un IC de la diferencia.

### 5.3 `EvByAction`

- Separar `fold`, `call`, `check`, `bet`, `raise` y `all-in`.
- El EV de fold es el valor real, no 0.
- Un EV no finito no es un EV: se ignora o se declara no disponible; no se
  convierte en 0.
- El árbol futuro debe declarar qué calles modela. Si solo modela la calle
  actual, la etiqueta lo dice.
- La incertidumbre del rango y del runout se propaga al EV; no solo la media.

## 6. Política

### 6.1 Contexto

```
PolicyContext:
  format                  # HU | MW
  opponents               # conjunto, no un ID
  primary_opponent        # solo para presentación
  current_equity
  showdown_equity
  ev_by_action
  range_advantage         # HERO | NEUTRAL | VILLAIN | UNKNOWN
  nut_advantage           # HERO | NEUTRAL | VILLAIN | UNKNOWN
  coverage
```

### 6.2 Reglas

- HU y MW tienen tablas/reglas propias. No se reutiliza una regla HU con
  `n_players` cambiado.
- `n_players` no basta: la política MW recibe el conjunto de rangos.
- `range_advantage` y `nut_advantage` se calculan sobre el conjunto; si no hay
  datos, `UNKNOWN`, no `NEUTRAL`.
- Si `multiway_soportado=False`, la salida debe ser “no soportada” o una
  recomendación conservadora declarada. Nunca una acción presentada como
  válida con equity de un rival.
- `select_best` no debe convertir ausencia de datos en fold; el contrato de
  “sin EV finito” se mantiene explícito.

### 6.3 Activación

`MULTIWAY_SOPORTADO` sigue en `False` durante todo este diseño. No se cambia
hasta que se cumplan las puertas de la sección 8.

## 7. Explicación y telemetría

Cada recomendación debe incluir:

```
format
opponents
range_source_by_opponent
prior_source_by_opponent
coverage_by_spot
current_equity {value, source, n, ci}
showdown_equity {value, source, n_samples, seed, ci}
ev_by_action {label, value, source, n}
policy {name, version, reason}
data {commit, hashes, window}
```

Un número sin fuente, denominador, muestra y cobertura no se muestra como
decisión. Es un dato incompleto.

## 8. Puertas de validación

| Puerta | Qué demuestra | No demuestra |
|---|---|---|
| G0 Datos | snapshot, hash, ventana, versión | calidad estratégica |
| G1 Paridad preflop | misma etiqueta y tabla en live/entrenamiento | calibración |
| G2 Cobertura | cada spot declara exacto/alias/gap | rentabilidad |
| G3 Equity | actual ≠ showdown; IC y semilla | EV |
| G4 Rango MW | un rango por rival, blockers, actualización | estrategia MW |
| G5 Equity MW | muestreo conjunto, side pots, IC | política óptima |
| G6 EV MW | EV por acción e incertidumbre | explotabilidad |
| G7 Política MW | comparación contra baselines y held-out | garantía universal |
| G8 Activación | revisión y rollback | que sea perfecto |

Ninguna puerta se salta por pasar tests unitarios. G1–G3 son obligatorias
antes de tocar MW.

## 9. Frontera de esta fase

- No se implementa `PlayerRange`, `MultiwayRangeSet`, `CurrentEquity`,
  `ShowdownEquity` ni `EvByAction`.
- No se cambia `rules.plan`, `select_best`, `asistente_live` ni
  `recommend_loop`.
- No se regeneran `profile_ranges`, `postflop_ranges` ni matrices.
- No se activa `MULTIWAY_SOPORTADO`.
- No se escriben recomendaciones experimentales en la base.

Este documento solo fija el contrato conceptual y las condiciones que deberá
cumplir la implementación futura.
