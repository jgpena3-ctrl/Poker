# P0-3 · Muestra e incertidumbre de PostflopRangeModel

**Estado:** contrato y auditoría implementados en sombra. Probabilidades,
priors efectivos, observaciones utilizadas y recomendaciones no se activan ni
se filtran.
**Alcance reproducible:** ventana fiable (877 manos) y base (1.344 manos).
**Auditor:** `tools/auditar_muestra_postflop.py` (`--json`, `--base`).

## 1. Hallazgo: los cuatro tamaños no son intercambiables

El conteo se verificó siguiendo exactamente `PostflopRangeModel.from_hands`
en `motor/postflop_ranges.py` y contrastándolo con `extract_hands`, `opp` y
`cnt`. El builder no rechaza manos completas; selecciona observaciones por
cartas, calle, tablero, perfil y bucket.

| Medida verificada en ventana | Valor | Definición en el código |
|---|---:|---|
| Manos recibidas | 877 | `len(hands)` → `n_hands_input` |
| Manos contadas por el `n_hands_used` histórico | 864 | IDs distintos con al menos una observación `hand_known` con cartas, **incluido preflop**; no es el n postflop |
| Manos con ≥1 observación que entra en `opp` postflop | 339 | IDs distintos que pasan filtros de carta, board, label y bucket del builder |
| Observaciones postflop usadas | 1.388 | `sum(model.opp.values())`; denominador de la celda es observaciones |
| Celdas pobladas | 116 | Claves `(perfil, street, facing, bucket)` de `opp` |
| Consultas estimadas en esas celdas | 580 | 116 celdas × 5 acciones (`x,b,c,f,r`) |

Por tanto, **864 no significa 864 manos aportando evidencia postflop**. El
modelo no tiene una fase de “mano válida/rechazada” a nivel de registro: se
reciben las 877 y se procesan las observaciones individualmente. Para no
inventar una definición de validez de mano, el contrato informa
`whole_hand_validation = none`, `rejected_as_whole_hand = 0`, el conteo
histórico de 864 y el número de manos que realmente aportan observaciones
postflop: 339.

En la base completa se obtuvo: 1.344 recibidas, 1.325 en el conteo histórico,
554 manos con observación postflop, 2.353 observaciones y 121 celdas.

## 2. Distribución de muestra por celda y consulta

`n` es siempre el número de **observaciones** del denominador de la celda,
nunca el número de manos. El segundo número de muestra es el conteo de IDs
distintos que aportan a esa misma celda.

| Tamaño observado por celda | Celdas ventana | Consultas acción ventana | Celdas base | Consultas acción base |
|---|---:|---:|---:|---:|
| `n < 3` | 30 | 150 | 17 | 85 |
| `3 ≤ n < 20` | 68 | 340 | 69 | 345 |
| `n ≥ 20` | 18 | 90 | 35 | 175 |
| **Total pobladas** | **116** | **580** | **121** | **605** |

Las celdas ventana tienen `n` entre 1 y 77. En particular, hay 13 celdas con
una sola observación y 17 con dos. El JSON enumera las 116 (o 121) celdas, las
cinco consultas de acción de cada una, `observation_count`,
`distinct_hand_count`, `action_observation_count`, las manos contribuyentes y
la traza de cada observación con su elegibilidad P0-2.

Estos rangos son **diagnósticos de cobertura**: `<3` corresponde además al
mínimo `DEFAULT_MIN_N=3` de las tablas de comportamiento Oracle; `<20` se
incluye para inspeccionar el corte de `OracleResponse.fade_n=20` que pidió la
auditoría. No son niveles de confianza ni activan reglas estadísticas.

## 3. Contrato de evidencia

`PostflopRangeModel.evidence_for(perfil, street, facing, bucket, action)` y
`evidence_for_vector(...)` devuelven un sidecar que no es leído por
`p_action`, `prob_vec`, `RangeState`, EV ni selector de acción. El contrato
`postflop_evidence_v1` contiene:

| Clave | Qué significa |
|---|---|
| `observation_count` | Observaciones de la celda `opp` |
| `distinct_hand_count` | IDs de manos diferentes; `None` en cargas históricas sin esa traza |
| `action_observation_count` | `cnt` de esa acción |
| `observation_provenance` | `hands_db.jsonl` → `extract_hands` |
| `amount_evidence` | Valor original (`known_zero`, `known_positive`, `absent`, `invalid`) y origen (`canonical_observed`, `derived`, `non_canonical`, `unknown`); ausencia no es cero |
| `model_prior_source` | Celda/fallback Oracle, `flat_no_oracle`, `flat_oracle_no_cell` o ausencia de prior |
| `prior_probability` | Probabilidad de esa acción en el prior efectivamente usado; no se sustituye ausencia por cero |
| `prior_returned_n` / `prior_support_observations` | n devuelto por `Oracle.p_action` y soporte efectivamente agregado, por separado |
| `alpha` | Alpha histórico del shrinkage |
| `prior_weight` / `observation_weight` | Coeficientes algebraicos actuales, no confianza estadística |
| `coverage` | `prior_only`, `no_evidence_no_prior`, `<3`, `<20` o `≥20` |
| `eligibility_projection` | Estado P0-2 sombra; no activa filtros |
| `confidence` / `uncertainty_reasons` | `not_quantified` y causas descriptivas; no CI inventado |

La fórmula efectiva permanece exactamente:

```text
P(A|H,bucket) = (cnt_bucket + alpha * prior_probability)
                / (opp_bucket + alpha)
```

Con `alpha = 2`, la contribución algebraica del prior es `2/(n+2)` y la de
observaciones `n/(n+2)`. Así, para `n=1` el prior aporta 2/3 y para `n=2`
aporta 1/2. En ventana, las 30 celdas con `n<3` producen 150 consultas acción
con peso del prior ≥50%. Esto describe la ecuación, no una probabilidad de
que la estimación sea correcta.

No hay un método calibrado de varianza, bootstrap por mano, modelo jerárquico
ni cobertura de intervalos. Las observaciones de una misma mano pueden estar
correlacionadas; por eso no se construyen intervalos binomiales usando
observaciones como si fueran manos independientes. El contrato declara
`confidence = not_quantified`.

## 4. Oracle y los dos roles distintos del prior

### PostflopRangeModel

`from_hands()` construye un Oracle desde los mismos datos; `build_models()` lo
reemplaza por el Oracle compartido ya construido con esas mismas manos. En la
ventana, las 116 celdas postflop observadas usan una distribución prior de
fuente `por_facing`. El JSON registra también soporte y n por celda.

El fallback plano postflop es **0.2 por acción**, aplicado solo si el Oracle
no está disponible/devuelve `None` y el bucket tiene `n>0`. Si `n=0` y no hay
prior disponible, el comportamiento actual de `p_action` devuelve `0.0`; el
contrato lo etiqueta `no_evidence_no_prior`, no como evidencia ni como una
estimación respaldada. No se ha alterado este fallback.

`motor/player_ranges.py::FLAT_PRIOR = 0.15` es otro fallback, del modelo de
rango preflop; no es el prior plano 0.2 de `PostflopRangeModel`.

### OracleResponse

En los 122 contextos únicos postflop OracleResponse derivados de observaciones
de la ventana:

| Fuente seleccionada | Contextos |
|---|---:|
| Granular | 105 |
| Por facing | 17 |
| n devuelto `<20` / `≥20` | 60 / 62 |
| n devuelto `<3` | 0 |

El mínimo `min_n=3` de `behavior_table` explica que las celdas Oracle
seleccionadas sean n≥3. La auditoría también ejecuta 54 probes controlados de
fallback (no son observaciones ni nuevas recomendaciones): 26 por-facing,
10 agregado por label y 18 población.

El `alpha` existente de OracleResponse es
`min(1, returned_n / fade_n)` con `fade_n=20`, pero **no es un peso convexo**:
el código eleva un factor de respuesta del perfil a ese exponente y
renormaliza junto a la respuesta heurística. El sidecar informa returned n,
soporte del fallback, source, exponente y `confidence=not_quantified`; no
llama a ese exponente “porcentaje de evidencia”.

Hay una limitación explícita: `Oracle.p_action` devuelve `n=0` al fallback
`label` o `poblacion`, aunque se pueda sumar soporte de celdas por-facing. En
ese caso OracleResponse conserva `alpha=0` y usa la heurística pura. El nuevo
`Oracle.evidence()` informa el soporte agregado, pero no lo realimenta al
fade; cambiar ese resultado requeriría otra autorización.

## 5. Carga, cachés y procedencia

* `PostflopRangeModel.p_action` no mantiene caché de probabilidades: consulta
  `opp`, `cnt` y el prior en cada llamada.
* `_scores_cache` memoiza scores/buckets de fuerza por tablero. No contiene
  conteos de muestra ni probabilidades; al cargar un modelo comienza vacío.
* Oracle tiene cachés perezosos de agregados por label/población; son
  memoización de sus tablas, no nuevas observaciones.
* El formato histórico guarda `opp` y `cnt`, pero no la instancia Oracle. Por
  eso `PostflopRangeModel.load()` deja `_oracle=None`; para celdas con n>0
  vuelve al fallback 0.2, y con n=0 retorna 0.0. Una prueba demuestra esta
  diferencia frente al modelo en memoria. **P0-3 no vuelve a inyectar Oracle**,
  porque eso cambiaría probabilidades del camino de carga actual.
* El nuevo bloque JSON `evidence` serializa tamaños y manos distintas por
  celda. Al cargar archivos viejos sin ese bloque, el conteo de manos por
  celda queda `None`; no se infiere a partir de `opp`.

## 6. Elegibilidad P0-2 en sombra

El auditor evalúa cada observación aceptada actualmente por el builder con
`assess_hand` y `observation_eligibility(..., CONSUMER_POSTFLOP_RANGE)`, y
agrega elegibles/restringidas por celda y acción. Resultados de ventana:

| Estado | Observaciones |
|---|---:|
| Efectivamente usadas por el modelo actual | 1.388 |
| Elegibles según P0-2 sombra | 1.386 |
| Marcadas por P0-2 como restringidas | 2 |

Las 1.388 siguen en el modelo efectivo; las 2 restricciones solo se anotan en
`cells[].observation_trace` y en los contadores sombra. No se recalculan
probabilidades después de filtrar.

## 7. Fingerprints y propagación hasta el live

Se fijaron fingerprints anteriores a P0-3 y el auditor los reproduce:

| Payload | SHA-256 |
|---|---|
| Tablas `alpha`, labels, `opp`, `cnt` de PostflopRangeModel | `ccfcb5586e0dd75c7583adc73da0dddbeb2effa7efa6fc9e65bd90a3e2530ffc` |
| Las 580 estimaciones de acción en celdas pobladas | `a16b0572bbac94efcbf58572d692e1dd8789dab4b52ede5bebcc82045f3b975c` |
| Distribuciones serializadas del Oracle | `50b254d7cce40ad3b9a97dc156505624aeeb3745d312335fd43b6e3f73f6edf5` |

La instrumentación se propaga aditivamente:

1. `Oracle.evidence()` describe source y soporte sin cambiar `p_action()`.
2. `OracleResponse.evidence` conserva esa procedencia, además del n/exponente
   realmente consumido.
3. El loop live obtiene `prob_vec` primero; después consulta
   `evidence_for_vector` con manejo de errores y lo adjunta a los inputs de
   trazabilidad. No entra en `RangeState.update`, EV, reglas ni selección.
4. `EvTable.model_evidence` queda disponible para consumidores/callbacks pero
   no se usa para texto visible ni para comparar EV.

Una prueba determinista ejecuta el mismo `_recomendacion_para` con y sin el
sidecar de evidencia (la segunda llamada fuerza un error del sidecar). Compara
texto visible, EV por acción y acción elegida; son idénticos. Otras pruebas
comparan vectores `prob_vec` antes/después de pedir evidencia y respuestas
OracleResponse con sidecar normal, reemplazado y fallido.

## 8. Pruebas ejecutadas

```text
python tools/auditar_muestra_postflop.py
ventana: 877 recibidas / 864 legacy / 339 contribuyentes / 1.388 obs / 116 celdas
P0-2: 1.386 elegibles / 2 restringidas, sombra únicamente

python tools/auditar_muestra_postflop.py --base
base: 1.344 recibidas / 1.325 legacy / 554 contribuyentes / 2.353 obs / 121 celdas
P0-2: 2.345 elegibles / 8 restringidas, sombra únicamente

python tools/auditar_muestra_postflop.py --verify-no-change
tablas y las 580 consultas de acción tienen fingerprints idénticos

python -m pytest motor/test_postflop_evidence.py motor/test_postflop_ranges.py \
  motor/test_behavior.py motor/test_decision_oracle.py motor/test_asistente_live.py \
  motor/test_decision_log.py motor/test_recommend_loop.py \
  motor/test_player_ranges.py motor/test_field_eligibility.py \
  motor/test_preflop_contract.py motor/test_observations.py -q
249 passed, 1 xfailed, 2 warnings
```

Los dos warnings vienen de pruebas preexistentes del rango preflop que
ejercitan su `FLAT_PRIOR=0.15`; no son el fallback postflop 0.2.

No se regeneraron derivados ni se guardó un modelo auditado sobre los
archivos de datos. No se cambiaron probabilidades, distribuciones, alpha,
priors, selección efectiva, recomendaciones visibles ni los modos de
activación P0-1/P0-2. No se inició P0-4, B2, calibración ni sesiones reales.

## Addendum P0-6 — procedencia de importes por observación

El sidecar de cada observación incluye ahora `amount`, `amount_evidence` y
`sizing`; P0-2 incluye los mismos estados en su proyección de elegibilidad.
Esto solo añade evidencia: no cambia `opp`, `cnt`, `p_action`, el prior ni la
selección efectiva. En la base actual todos los 16.486 importes de acciones son
numéricamente cero-conocido o positivo-conocido; 908 declaran
`amount_type=observed`, y en 15.578 el origen queda `unknown` porque no se
registra `amount_type`. No se promueve ese origen a canónico por inferencia.
