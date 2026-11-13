# Política de cobertura e incertidumbre (2026-11-13)

**Estado:** diseño. No implementa resolvedores, no modifica `motor/`, no
escribe `data/` y no activa multiway.

**Objetivo:** que “no hay tabla/rango/probabilidad” sea un estado explícito y
no un cero, y que cada consumidor sepa qué hacer con ese estado.

## 1. Estados de cobertura

```
CoverageState = exact | alias | coverage_gap | impossible | unknown
```

| Estado | Significado | Ejemplo | ¿Es información? |
|---|---|---|---|
| `exact` | existe la clave exacta | `3B_CO_vs_UTG` | sí, con fuente |
| `alias` | existe un alias declarado y auditable | `4B_UTG_vs_MP → 4B_UTG_vs_HJ` | sí, con alias visible |
| `coverage_gap` | la tabla debería existir y no existe | `Call_OR_MP_vs_UTG` | no; hueco declarado |
| `impossible` | no aplica por orden de acción o regla | `OR_BB`, `4B_UTG` con orden imposible | no; no hay spot legal |
| `unknown` | no se puede clasificar la cobertura | acción/posición/importe roto | no; falta información |

Cada estado lleva `reason` y `source_key`. `alias` lleva `alias_of`. `unknown`
lleva `unknown_reason`. `coverage_gap` puede llevar `fallback_used` y
`fallback_key`; eso no crea un sexto estado.

### 1.1 `impossible` incluye ausencias intencionales

La ausencia de `OR_BB` no es un hueco de datos: BB no abre; tiene opción de
check. La ausencia de `ROL_UTG` tampoco: UTG no puede hacer rol sin limps
previos. Se clasifican `impossible` con razón:

- `impossible_action_order`
- `intentional_check_option`
- `intentional_no_prior_limp`

No se convierten en `coverage_gap` ni en cero.

### 1.2 `unknown` no es `coverage_gap`

- `coverage_gap`: sabemos que falta una tabla que debería existir.
- `unknown`: no sabemos si falta o no, porque la acción no se pudo leer.

Mezclarlos haría que un error de parsing pareciera una carencia de datos.

## 2. Cobertura preflop actual

Inventario estático verificado (`preflop.audit_engine_coverage`):

| Estado | Claves |
|---|---:|
| exact | 107 |
| alias | 1 |
| intentional_missing | 2 |
| impossible_missing | 82 |
| coverage_gap | 30 |
| unclassified_missing | 0 |

En la base:

- 1.080 decisiones `facing_open` sin `Call_OR` (1.079 `missing` + 1
  `fallback_other_vs`).
- 78 decisiones `facing_3bet` sin `4B` ni `Call_3B`.
- 69 decisiones `facing_3bet` con `fallback_other_vs`.

`fallback_other_vs` no es un sexto estado ni es `exact`: es
`state=coverage_gap` con `fallback_used=true` y una tabla de otro rival. Solo
es una aproximación declarada; no se contabiliza como cobertura exacta.

## 3. Matriz de consumidores

### 3.1 Decisión preflop live

| Cobertura de la tabla necesaria | Comportamiento |
|---|---|
| `exact` | usar la tabla, registrar fuente |
| `alias` | usar la tabla, registrar alias |
| `coverage_gap` | **no decidir con esa tabla**; devolver `unsupported_spot` o activar política de prior declarada |
| `impossible` | no aplica; no hay tabla que consultar |
| `unknown` | no decidir; devolver `unknown_spot` |

En modo `strict`, `coverage_gap` y `unknown` producen `unsupported`, no un
fold. En modo `shadow`, se puede calcular legacy para comparar, pero se marca
como legacy y no se presenta como recomendación canónica.

Un `coverage_gap` con `fallback_used=true` sigue siendo un gap. En `strict`
no se usa; en `shadow` se puede calcular como aproximación, pero se etiqueta
`fallback_other_vs` y no se suma a las celdas exactas.

### 3.2 Rango/equity live

| Situación | Comportamiento |
|---|---|
| rango vacío | `RangeState.empty=True` con `empty_reason`; equity `unknown` |
| prior plano | usar `FLAT_PRIOR` solo si el consumidor lo declara como prior |
| tabla ausente | `no_range`; no crear vector de ceros |
| `prob_vec` vacío | `empty`; no normalizar, no dividir por cero |
| blockers dejan el rango vacío | `empty`; no convertirlo en “fold” |

Un `RangeState` vacío es una representación válida de ausencia, siempre que:
- tenga `empty_reason`;
- no se use para calcular equity;
- no se presente como “el rival no tiene manos”;
- no se normalice a una masa arbitraria.

### 3.3 Entrenamiento

| Cobertura | Comportamiento |
|---|---|
| `exact` | incluir con `source` |
| `alias` | incluir con `alias_of` |
| `coverage_gap` | excluir de la celda o marcar `missing`; nunca como 0 |
| `impossible` | no generar celda |
| `unknown` | excluir; no imputar |

Un `coverage_gap` con fallback no entra como `exact`; si se usa para
entrenamiento, se marca `fallback_other_vs` y se mantiene fuera de la celda
canónica.

La etiqueta de entrenamiento no puede convertir un `coverage_gap` en una
frecuencia observada. Si se usa un prior, se etiqueta `prior`, no `observed`.

### 3.4 Auditoría y sombra

- Puede medir `gap`, `impossible` y `unknown` por separado.
- No puede sumarlos como “cobertura total” sin declararlo.
- Un `fallback_other_vs` se reporta como aproximación, no como exacto.
- La sombra no cambia la acción ni la base.

## 4. Observación, estadística, prior, predicción, simulación

Son cinco objetos distintos y deben llevar etiqueta:

| Tipo | Qué es | Campos mínimos | No es |
|---|---|---|---|
| Observación | acción registrada en una mano | `hand_id`, `player`, `action`, `source`, `data_hash` | una estimación |
| Estadística | agregado con denominador | `n`, `opp`, `freq`, `ci`, filtros | una predicción |
| Prior | distribución genérica o de tabla | `source`, `n` o `table`, `coverage` | una observación |
| Predicción | salida de un modelo | `model_version`, `score`, `coverage`, `n` | una probabilidad calibrada por defecto |
| Simulación | muestreo de runouts/manos | `n`, `seed`, `ci`, `method` | evidencia observada |

Reglas:

1. Una frecuencia observada sin denominador no es una estadística.
2. Un prior no se presenta como “lo que hizo el rival”.
3. Una predicción no se presenta como observación.
4. Una simulación no se presenta como dato real.
5. Un intervalo de confianza no se omite cuando se comparan dos valores.
6. `n_eff` de un rango no es `n` de manos observadas.

## 5. Incertidumbre

Cada valor debe declarar al menos:

```
source_kind: observation | statistic | prior | prediction | simulation
source_id
n / opp / denominator
coverage
ci_low / ci_high        # si aplica
seed                    # si es simulación
model_version           # si es predicción
data_snapshot_hash
```

No se acepta:

- una probabilidad sin muestra;
- una equity sin `n_combos`/`n_runouts`;
- un EV sin métodos y semilla;
- un rango sin `coverage` y `n_eff`;
- un `0.0` que signifique “no hay tabla”.

## 6. Fallbacks permitidos

| Fallback | Permitido | Condición |
|---|---|---|
| alias declarado | sí | `alias_of` visible |
| tabla de otro `vs` (`fallback_other_vs`) | solo como sombra/aproximación | `state=coverage_gap`, `fallback_used=true`, no `exact` |
| `FLAT_PRIOR` | sí como prior | `source=flat`, no observación |
| rango vacío | sí como ausencia | `empty_reason`; no equity |
| perfil `UNKNOWN` | sí | rango amplio, no estrecho |
| `0.0` por ausencia | **no** | prohibido |
| inventar categoría | **no** | prohibido |

## 7. Criterios de aceptación

- El 100 % de las consultas devuelve un `CoverageState` y una `reason`.
- Ningún consumidor convierte `gap`/`unknown` en 0 o en fold.
- Un `RangeState` vacío nunca produce equity.
- `fallback_other_vs` no se contabiliza como exacto.
- Un `unknown` de parsing no se agrupa con `coverage_gap`.
- Cada estimación declara `source_kind`, denominador y cobertura.
- Cada simulación declara `n`, seed e intervalo.
