# Contratos de rango, equity y EV (2026-11-13)

**Estado:** diseño. No implementa modelos, no modifica `motor/`, no escribe
`data/` y no activa multiway.

**Objetivo:** separar observación, estimación, prior, equity y EV para que HU
pueda mejorarse sin mezclar objetos ni presentar una simulación como dato.

## 1. Objetos y relaciones

```
observación de acciones
        │
        ├──▶ ObservedRange        (combos exactos vistos)
        │
        ├──▶ EstimatedRange       (pesos, reach, prior, posterior)
        │
        └──▶ GenericPrior         (tabla/FLAT_PRIOR; no observación)

board + rango + blockers
        ├──▶ CurrentEquity        (equity en el board actual)
        └──▶ ShowdownEquity       (equity con runouts futuros)

acción + creencias + respuesta
        └──▶ EvByAction           (EV por acción)
```

Un objeto no se convierte en otro sin declararlo y sin conservar la
procedencia.

## 2. `ObservedRange`

Qué es: combinaciones exactas que el héroe/observador **vio** en una mano o
conjunto de manos, sin inferencia.

```
ObservedRange:
  hand_id
  player
  street
  combos: [exact_combo]
  source_actions: [index]
  data_hash
  coverage: exact | coverage_gap | unknown
```

Reglas:

- Es un conjunto, no una probabilidad.
- No se normaliza a 100 % de un rango rival.
- No se usa en live para inferir manos no mostradas.
- Una acción observada puede ser `no_range` (por ejemplo, fold).
- Un `coverage_gap` de tabla no se convierte en observación.

## 3. `EstimatedRange`

Qué es: distribución de pesos sobre combos, con `reach`, prior y posterior
explícitos.

```
EstimatedRange:
  player
  street
  board
  combos: [combo]
  weights: [w_i]              # w_i >= 0
  reach: [r_i]                # prob. de llegar al spot
  prior: GenericPrior
  posterior: [p_i]            # p_i = w_i / sum(w)
  n_hands / n_opp
  n_eff                       # (sum w)^2 / sum(w^2)
  coverage
  model_version
  data_snapshot_hash
```

Reglas:

1. Si `sum(w) > 0`, `posterior` normaliza; si `sum(w) == 0`, el rango es
   `empty`.
2. `empty` no es una distribución nula; es ausencia y no produce equity.
3. `reach` no se ignora al pasar de acciones observadas a creencias.
4. `n_eff` no es el número de manos; no se usa como muestra observacional.
5. Un rango estimado no se presenta como “manos que el rival tiene” sin
   declarar el modelo y la cobertura.
6. Los blockers se aplican al rango, no a la equity después de calcularla.

## 4. `GenericPrior`

Qué es: distribución genérica o de tabla para un spot, sin observación
individual.

```
GenericPrior:
  key
  vector
  source: flat | preflop_table | profile_template | alias
  alias_of
  coverage
  n / opp
  version
```

Reglas:

- `FLAT_PRIOR` es un prior, no una estimación del rival.
- Un prior de tabla puede ser `exact`, `alias` o `coverage_gap`.
- `coverage_gap` no se imputa con `FLAT_PRIOR` en silencio; si se hace, el
  resultado es `source=prior_fallback` y se declara.
- Un prior no se calibra con datos de la misma mano que se evalúa.

## 5. `CurrentEquity`

Qué es: probabilidad de ganar/empatar **en el board actual**, sin runouts
futuros.

```
CurrentEquity:
  hero_hand
  board
  villain_range: EstimatedRange | GenericPrior
  dead_cards
  method: exact | monte_carlo
  value: win | tie | lose
  n_combos
  n_samples
  seed
  ci_low / ci_high
  coverage
  equity_version
```

Reglas:

- `current` no es `showdown`; no se usa para justificar una acción futura como
  si ya estuviera completed.
- Enumeración exacta si el espacio es pequeño; MC si no, con `n`, seed y CI.
- Empates se reparten; se reportan `win/tie/lose` por separado.
- Board y dead cards son entradas; no se recalcula con el board “casi igual”.
- Rango vacío → `unknown`; no `0.0`.
- Un `fallback_other_vs` se etiqueta como `coverage_gap` con fallback, no como
  `exact`.

## 6. `ShowdownEquity`

Qué es: equity considerando runouts futuros y, cuando aplica, side pots.

```
ShowdownEquity:
  hero_hand
  board
  villain_range
  runouts: [card] | sampled
  n_runouts
  n_samples
  seed
  method: exact | monte_carlo
  win / tie / lose
  side_pots
  ci_low / ci_high
  coverage
```

Reglas:

- `n_runouts` y `n_samples` son distintos; no se intercambian.
- Si hay all-in y side pots, se calcula por bote y por orden de elegibilidad.
- Empates y odd chips se declaran.
- Mismo seed + mismas entradas → mismo resultado.
- `current` y `showdown` se comparan solo con esa etiqueta visible.

## 7. `EvByAction`

Qué es: valor esperado de una acción bajo un modelo de respuesta y unas
creencias declaradas.

```
EvByAction:
  action
  ev
  method
  n_samples
  seed
  ci_low / ci_high
  tree_depth
  response_model
  beliefs: EstimatedRange | GenericPrior
  side_pots
  coverage
  ev_version
```

Reglas:

1. Sin modelo de respuesta no hay EV de una subida; como máximo hay equity.
2. Sin creencias no hay EV; no se usa un rival genérico sin declararlo.
3. El EV de fold es una convención (normalmente 0 en el nodo), no una
   probabilidad.
4. El EV de call usa la equity y el bote; el de raise usa fold equity +
   equity cuando pagan; el de check puede requerir árbol posterior.
5. Se reporta `tree_depth`; un EV con árbol truncado no se presenta como
   solución completa.
6. Un EV con `coverage_gap` no se compara con uno con `exact` sin declararlo.
7. No se elige la acción por EV de una sola muestra ni por una simulación sin
   intervalo.

## 8. Confianza

No hay un único “confidence score”. Se reportan componentes:

```
confidence:
  coverage
  n_obs
  n_combos
  n_runouts / n_samples
  ci_low / ci_high
  model_version
  data_snapshot_hash
  calibration_status: none | provisional | validated
```

Reglas:

- `coverage` no se sustituye por `n`.
- `n` alto con `coverage_gap` sigue siendo cobertura insuficiente.
- Un intervalo estrecho de una simulación no arregla un prior mal
  especificado.
- `calibration_status=validated` exige el dataset de evaluación de §9.

## 9. Política de calibración

**No se calibra sin un dataset de evaluación definido, congelado y separado.**

`EvaluationDataset` debe declarar:

```
name
snapshot_hash
date_from / date_to
sessions
stakes / format
player_scope
label_definition
features_available_at_decision
exclusions
split: train | validation | test
n_hands
n_decisions
```

Reglas:

1. Split temporal; no aleatorio entre manos del mismo día si hay fuga.
2. `features_available_at_decision` no puede incluir información posterior.
3. No se usa la misma mano para construir el prior y para evaluar.
4. No se calibra con logs de sombra que dependan del modelo evaluado.
5. No se declara calibración por una métrica agregada sin curvas y CI.
6. No se reajusta el test tras mirarlo; si se itera, se documenta.

Métricas mínimas:

- Brier score y log loss por clase;
- curvas de fiabilidad y ECE;
- bootstrap CI por sesión/mano, no por decisión independiente si están
  correlacionadas;
- evaluación estratégica en held-out: EV/utility, no solo accuracy;
- comparación contra baseline declarado (`flat`, tabla, legacy).

Umbral de aceptación: se fija **antes** de mirar el test. Un resultado
favorable en accuracy no compensa un EV held-out peor.

## 10. Invariantes

1. `ObservedRange` no se normaliza como si fuera una distribución completa.
2. `EstimatedRange` vacío no produce equity.
3. `GenericPrior` no se presenta como observación.
4. `CurrentEquity` no se presenta como `ShowdownEquity`.
5. `ShowdownEquity` no se presenta como equity actual.
6. `EvByAction` sin modelo de respuesta es inválido.
7. Un `0.0` nunca significa “no hay datos”.
8. Toda estimación declara denominador, cobertura y versión.
9. Toda simulación declara `n`, seed e intervalo.
10. Toda calibración declara dataset, split y criterio predefinido.

## 11. Criterios de aceptación

- Exacto vs MC: diferencia dentro del CI declarado; no igualdad forzada.
- Mismo seed → mismo resultado.
- Blockers reducen masa; no convierten un rango no vacío en cero sin
  justificarlo.
- Rango vacío → `unknown`, no `0.0`.
- `current` y `showdown` no se mezclan en una misma métrica.
- EV de raise requiere `response_model`; sin él, no se acepta.
- `fallback_other_vs` y prior se reportan como tales.
- Calibración solo con `EvaluationDataset` congelado y test no visto.
