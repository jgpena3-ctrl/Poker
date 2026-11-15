# Política de cobertura e incertidumbre (2026-11-13)

**Estado:** diseño. No implementa resolvedores, no modifica `motor/`, no escribe en `data/` y no activa multiway.

**Objetivo:** que la ausencia de una tabla, rango, probabilidad, estimación o evidencia sea un estado explícito y trazable. Cada consumidor debe conocer qué información tiene, qué información falta y qué operaciones están permitidas con ella.

Esta política complementa:
- `ESPECIFICACION_CONTRATO_PREFLOP_2026-11-13.md`
- `MIGRACION_ROLLBACK_PREFLOP_2026-11-13.md`
- Los contratos posteriores de rangos, equity y EV.

Los estados descritos aquí son contratos de diseño. No se presupone que estén implementados.

---

## 1. Estados de cobertura de tablas

```text
CoverageState =
    exact
  | alias
  | coverage_gap
  | impossible
  | unknown
```

| Estado | Significado | Ejemplo | ¿Permite usar una tabla canónica? |
|---|---|---|---|
| `exact` | Existe una tabla para la clave solicitada y su identidad está verificada | `3B_CO_vs_UTG` | Sí |
| `alias` | Existe una tabla alternativa declarada y su compatibilidad está validada | `4B_UTG_vs_MP → 4B_UTG_vs_HJ` | Solo bajo la política de alias |
| `coverage_gap` | La consulta es válida, la tabla debería existir, pero no está disponible | `Call_OR_MP_vs_UTG` | No |
| `impossible` | La consulta no aplica al estado de juego o a la secuencia de acciones | Una consulta de call frente a una apuesta inexistente | No se consulta esa tabla |
| `unknown` | No se puede determinar qué consulta corresponde o si es válida | Posición, acción o importe ilegible | No |

Todo resultado de cobertura debe declarar:

```text
state
reason
requested_key
source_key
```

Campos adicionales según corresponda:

```text
alias_of
alias_validation
unknown_reason
fallback_used
fallback_key
coverage_version
```

Reglas:
- `requested_key` identifica la consulta original.
- `source_key` identifica la tabla realmente consultada, cuando existe.
- `source_key` puede ser nulo cuando no hay tabla fuente.
- `alias_of` solo aparece cuando el estado es `alias`.
- `fallback_used` y `fallback_key` describen una aproximación; no cambian el estado de cobertura.
- `unknown_reason` explica por qué no se pudo resolver la consulta.
- `reason` es obligatorio para todos los estados.

### 1.1 `exact`

Se utiliza exclusivamente cuando:
- La clave solicitada existe.
- La tabla se ha identificado correctamente.
- Su versión y esquema son compatibles con el consumidor.
- No se ha sustituido silenciosamente por otra tabla.

Una tabla existente pero incompatible no se considera `exact` para ese consumidor.

### 1.2 `alias`

Un alias solo puede utilizarse si existe una declaración explícita y auditable de compatibilidad.

Debe registrar:
- Clave solicitada.
- Clave utilizada.
- Motivo del alias.
- Versión de la regla de alias.
- Evidencia o validación que autoriza su uso.
- Restricciones conocidas.

La existencia de una tabla parecida no autoriza crear un alias.

Un alias no se considera automáticamente equivalente a la clave original. Su utilización puede estar permitida para una operación y prohibida para otra.

Por ejemplo, una equivalencia aceptable para una consulta descriptiva no demuestra necesariamente que la tabla sea adecuada para seleccionar una acción.

### 1.3 `coverage_gap`

Se utiliza cuando:
- El spot es válido.
- La consulta está correctamente identificada.
- La tabla esperada no existe o no está disponible.
- No existe una regla de alias autorizada que resuelva la consulta.

Puede incluir:

```text
fallback_used
fallback_key
fallback_reason
```

Un fallback no cambia el estado `coverage_gap`.

Ejemplo:

```text
state = coverage_gap
requested_key = Call_OR_MP_vs_UTG
fallback_used = true
fallback_key = Call_OR_MP_vs_HJ
```

La tabla alternativa es una aproximación, no cobertura exacta.

### 1.4 `impossible`

Se utiliza cuando la consulta de tabla no corresponde al estado de juego.

Debe especificarse:
- El spot observado.
- La consulta que se intentó resolver.
- La condición que hace imposible esa consulta.
- La regla del contrato que lo determina.

Razones posibles:

```text
impossible_action_order
no_facing_bet
no_prior_limp
no_legal_decision
query_not_applicable
```

La imposibilidad pertenece a la consulta concreta, no necesariamente a toda la decisión del héroe.

Ejemplo: si no existe apuesta que enfrentar, una consulta `Call_OR` no aplica. Eso no significa que el héroe carezca de una decisión: puede tener que comprobar, pasar o realizar otra acción.

**Importante:** `OR_BB` no debe clasificarse universalmente como imposible. La BB puede tener una opción de check cuando no existen subidas ni limps, pero puede tener una oportunidad de raise frente a limps. La clasificación debe corresponder al contexto y a la clave solicitada.

La ausencia intencional de una tabla tampoco significa que todas las acciones del spot sean imposibles.

### 1.5 `unknown`

Se utiliza cuando no existe información suficiente para determinar si la consulta es válida o cuál debería ser su clave.

Ejemplos:
- Acción ilegible.
- Posición desconocida.
- Importe ambiguo.
- Orden de acciones contaminado.
- Contexto incompleto.
- Identidad del agresor no resuelta.

`unknown` no es `coverage_gap`.

Un error de lectura no debe contabilizarse como una tabla ausente.

---

## 2. Inventario de cobertura preflop

El inventario estático comunicado para `preflop.audit_engine_coverage` es:

| Estado | Claves |
|---|---:|
| `exact` | 107 |
| `alias` | 1 |
| `intentional_missing` | 2 |
| `impossible_missing` | 82 |
| `coverage_gap` | 30 |
| `unclassified_missing` | 0 |

Estas categorías son las etiquetas del inventario original. No deben confundirse automáticamente con los cinco estados de `CoverageState`.

En particular:
- `intentional_missing` debe mapearse a `impossible` solo cuando exista una regla contextual que demuestre que la consulta no aplica.
- `impossible_missing` debe revisarse para verificar que la imposibilidad corresponde al spot y no solo a una ausencia histórica.
- `unclassified_missing = 0` describe ese inventario, no garantiza que cualquier consulta futura pueda clasificarse.

**Cifras históricas de la base auditada:**

- 1.080 decisiones `facing_open` sin `Call_OR`:
  - 1.079 `missing`.
  - 1 `fallback_other_vs`.
- 78 decisiones `facing_3bet` sin `4B` ni `Call_3B`.
- 69 decisiones `facing_3bet` con `fallback_other_vs`.

Estas cifras deben conservarse como referencia histórica del snapshot auditado. No son valores permanentes: cualquier nueva auditoría debe declarar commit, hash de datos, versión del inventario y filtros aplicados.

### 2.1 Política para `fallback_other_vs`

`fallback_other_vs` no es un sexto estado.

Se representa como:

```text
state = coverage_gap
fallback_used = true
fallback_key = ...
```

Reglas:
- Nunca se contabiliza como cobertura exacta.
- Nunca se presenta como tabla específica del rival solicitado.
- No se utiliza en serving canónico estricto.
- Puede utilizarse en sombra para medir el efecto de la aproximación.
- Su uso experimental requiere identificar la tabla original y la sustituta.
- No se incorpora a una celda canónica de entrenamiento como si fuera observación exacta.
- No se utiliza para afirmar que una consulta tiene cobertura completa.

---

## 3. Separación de cobertura de tabla, rango y estimación

La cobertura de una tabla no determina por sí sola si existe un rango utilizable.

Deben distinguirse al menos estas etapas:

```text
PreflopDecision
      ↓
CoverageState
      ↓
RangeState
      ↓
EquityState
      ↓
EVState
      ↓
RecommendationState
```

Cada etapa puede fallar o quedar sin soporte independientemente de las anteriores.

Ejemplos:
- Una tabla exacta puede producir un rango vacío por blockers o filtros.
- Una tabla puede faltar aunque exista un prior genérico.
- Un rango válido puede no permitir calcular equity para el estado solicitado.
- Una equity válida no garantiza que exista EV calculable.
- Un EV calculable no garantiza que la política pueda recomendar una acción.

No se debe propagar automáticamente el estado de una etapa a las siguientes como si todas fueran equivalentes.

---

## 4. Política de consumidores

### 4.1 Decisión preflop live

| Estado de cobertura | Comportamiento |
|---|---|
| `exact` | Puede utilizarse la tabla, si es compatible con la consulta |
| `alias` | Puede utilizarse solo si la regla de alias autoriza esa operación |
| `coverage_gap` | No utilizar como tabla exacta; declarar falta de cobertura |
| `impossible` | No realizar esa consulta; continuar con la lógica correspondiente al spot si existe |
| `unknown` | No decidir utilizando esa consulta; declarar incertidumbre |

En modo estricto:
- `coverage_gap` no puede convertirse en una consulta exacta.
- `unknown` no puede utilizarse como si se conociera la tabla.
- Un fallback no autorizado no puede producir una recomendación canónica.
- Un estado `impossible` no debe convertirse en una acción arbitraria.

En modo sombra:
- Se permite calcular legacy para comparar.
- Se permite evaluar aproximaciones expresamente identificadas.
- El resultado legacy o aproximado no se presenta como recomendación canónica.
- Ninguna diferencia modifica la acción live.

La existencia de un prior genérico no transforma un `coverage_gap` en `exact`.

Si se autoriza una política de prior, debe registrarse como una fuente distinta y evaluarse con sus propias restricciones.

### 4.2 Rango live

El rango tiene un estado propio. No se deduce únicamente de `CoverageState`.

Estados conceptuales mínimos:

```text
RangeState =
    usable
  | empty
  | unavailable
  | unknown
  | incompatible
```

La implementación podrá utilizar otra representación equivalente, siempre que preserve estas distinciones.

| Situación | Estado | Comportamiento |
|---|---|---|
| Tabla y rango válidos | `usable` | Puede continuar a equity |
| Rango sin combos después de filtros válidos | `empty` | No calcular equity con ese rango |
| Tabla o modelo ausente | `unavailable` | No fabricar un rango |
| No se puede determinar el rango | `unknown` | Detener la etapa dependiente |
| Esquema o versión incompatible | `incompatible` | Rechazar para ese consumidor |

Un rango vacío debe incluir:

```text
empty_reason
source
coverage
filters_applied
```

Cuando corresponda, también:

```text
blockers
range_version
n_eff
```

Las causas deben distinguir al menos:
- `blocked_by_hero_cards`
- `blocked_by_board`
- `filters_removed_all_combos`
- `source_range_empty`
- `invalid_range`
- `unknown_empty_reason`

Un rango vacío no significa que el rival no tenga manos.

No se debe:
- Normalizar un rango vacío.
- Convertirlo en una distribución arbitraria.
- Interpretarlo como probabilidad cero.
- Calcular equity sobre una distribución vacía.
- Convertirlo en fold.

Si el rango es vacío, la equity queda sin soporte por esa causa. No debe reportarse como `0.0`.

### 4.3 Priors

Un prior puede utilizarse cuando la política del consumidor lo autorice y se identifique claramente su naturaleza.

Ejemplo:

```text
source_kind = prior
source_id = FLAT_PRIOR
```

Reglas:
- Un prior no es observación.
- Un prior no es una frecuencia observada.
- Un prior no resuelve automáticamente una ausencia de cobertura.
- Su utilización debe ser visible en el resultado.
- Deben conservarse su versión, parámetros y procedencia.
- No se presenta como predicción calibrada sin validación.
- No se utiliza silenciosamente como sustituto de un rango específico ausente.

La política que autorice un prior debe definir para qué operaciones sirve y qué incertidumbre conserva.

### 4.4 Entrenamiento

| Cobertura | Tratamiento |
|---|---|
| `exact` | Puede incluirse en la celda correspondiente, con procedencia |
| `alias` | Se identifica como alias y se conserva la clave original |
| `coverage_gap` | Se excluye de la celda exacta o se mantiene como dato de cobertura ausente |
| `impossible` | No genera una celda para una consulta que no aplica |
| `unknown` | Se excluye de la clasificación canónica o se conserva como caso unresolved |

Reglas:
- Una etiqueta no puede transformar un `coverage_gap` en frecuencia observada.
- Un prior se identifica como `prior`, nunca como `observed`.
- Una aproximación `fallback_other_vs` permanece fuera de la celda canónica exacta.
- Un mapeo de alias debe conservar su origen.
- Las muestras excluidas deben contabilizarse para no ocultar pérdida de cobertura.
- No se imputan frecuencias ausentes como cero.
- No se corrigen registros históricos automáticamente.

Si una aproximación se utiliza en un experimento de entrenamiento, debe mantenerse separada de los datos canónicos y declararse en el manifiesto del experimento.

### 4.5 Auditoría y sombra

La auditoría debe medir por separado:
- `exact`
- `alias`
- `coverage_gap`
- `impossible`
- `unknown`

Además, debe poder separar:
- Cobertura de tablas.
- Disponibilidad de rangos.
- Disponibilidad de equity.
- Disponibilidad de EV.
- Disponibilidad de recomendación.

Reglas:
- No sumar `impossible` y `unknown` como si fueran tablas cubiertas.
- No agrupar `unknown` con `coverage_gap`.
- No sumar aliases a exactos sin declarar la regla.
- No contabilizar fallbacks como exactos.
- No interpretar una etapa no ejecutada como una etapa exitosa.
- La sombra no modifica acciones ni datos.

Toda métrica agregada debe indicar su denominador y qué estados incluye.

---

## 5. Observación, estadística, prior, predicción y simulación

Son objetos distintos. Ninguno debe presentarse como otro.

| Tipo | Qué representa | Metadatos mínimos | No equivale a |
|---|---|---|---|
| Observación | Acción registrada en una mano | `hand_id`, `player`, `action`, `source`, `data_snapshot_hash` | Estimación |
| Estadística | Agregado de observaciones | `n`, denominador, filtros, frecuencia y método | Predicción |
| Prior | Distribución previa genérica o específica | `source`, versión, parámetros y cobertura | Observación |
| Predicción | Salida de un modelo | `model_version`, método, entrada y estado de calibración | Probabilidad calibrada automáticamente |
| Simulación | Resultado de un procedimiento de muestreo | `n`, método, parámetros y `seed` si es estocástica | Evidencia observada |

Reglas:

1. Una frecuencia observada sin denominador no es una estadística interpretable.
2. Un prior no se presenta como comportamiento observado del rival.
3. Una predicción no se presenta como observación.
4. Una simulación no se presenta como dato real.
5. Una puntuación de modelo no se denomina probabilidad salvo que su interpretación probabilística esté justificada.
6. `n_eff` de un rango no equivale al número de manos observadas.
7. El tamaño de muestra no demuestra por sí solo representatividad.
8. Los filtros y criterios de selección deben acompañar a los agregados.
9. Las muestras de entrenamiento y evaluación deben distinguirse.
10. Los resultados de simulación deben conservar su método y parámetros.

---

## 6. Contrato de incertidumbre

Cada estimación debe declarar los metadatos necesarios para comprender su origen, método y limitaciones.

Estructura conceptual:

```text
source_kind
source_id
source_version
coverage_state
data_snapshot_hash
method
```

Campos condicionales:

```text
n
n_eff
opportunities
denominator
ci_low
ci_high
seed
model_version
calibration_status
n_combos
n_runouts
```

No todos los campos aplican a todos los tipos de información.

### 6.1 Observaciones y estadísticas

Para una estadística deben poder conocerse:
- Número de observaciones.
- Denominador pertinente.
- Filtros aplicados.
- Frecuencia calculada.
- Fuente de los registros.
- Snapshot de datos.
- Método de agregación.

El denominador debe representar las oportunidades reales de la estadística.

No debe confundirse:
- Número de manos.
- Número de oportunidades.
- Número de acciones.
- Número de jugadores.
- Número efectivo de muestras.

### 6.2 Priors

Deben declarar:
- Fuente.
- Versión.
- Parámetros.
- Universo de aplicación.
- Restricciones.
- Cobertura.
- Si son planos, poblacionales o específicos de un perfil.

No se les asigna un número de observaciones ficticio para simular evidencia.

### 6.3 Predicciones

Deben declarar:
- Modelo y versión.
- Fuente de entrada.
- Método de generación.
- Estado de cobertura.
- Estado de calibración cuando se interpreten como probabilidades.
- Limitaciones conocidas.

Una predicción no calibrada puede ser una puntuación útil, pero no se presenta como probabilidad real.

### 6.4 Equity

Una equity debe declarar:
- Tipo de equity: actual o showdown.
- Fuente de rangos.
- Estado de cobertura.
- Método de cálculo.
- Número de combos considerados cuando aplique.
- Número de runouts cuando aplique.
- Semilla cuando el procedimiento sea estocástico.
- Incertidumbre o intervalo cuando el método permita estimarlos.

Una enumeración exacta no necesita semilla. Un cálculo determinista no debe recibir una semilla ficticia.

Una estimación por muestreo debe declarar tamaño de muestra y método. Su intervalo debe reflejar la incertidumbre de estimación y no confundirse con incertidumbre estratégica o de modelo.

### 6.5 EV

Un EV debe declarar:
- Acción evaluada.
- Estado de juego utilizado.
- Fuente y versión de rangos.
- Fuente de equity o método de evaluación.
- Estructura de bote y contribuciones.
- Supuestos sobre respuestas de rivales.
- Tratamiento de side pots cuando corresponda.
- Método de cálculo.
- Incertidumbre cuando sea estimada.

La semilla solo es obligatoria cuando interviene un componente estocástico.

No se acepta un EV presentado como exacto si depende de supuestos no declarados o de rangos sin soporte.

### 6.6 Valores numéricos legítimos

Un valor `0.0` puede ser válido si representa un resultado calculado y justificado.

Está prohibido utilizar `0.0` como sustituto de:
- Tabla ausente.
- Rango no disponible.
- Probabilidad desconocida.
- Error de parsing.
- Denominador inexistente.
- Cálculo no ejecutado.

El estado de disponibilidad debe ser independiente del valor numérico.

---

## 7. Fallbacks permitidos

| Fallback o condición | Permitido | Restricciones |
|---|---|---|
| Alias declarado | Sí | Compatibilidad validada y origen visible |
| `fallback_other_vs` | Solo sombra o experimento autorizado | Mantiene `coverage_gap`; nunca se declara exacto |
| `FLAT_PRIOR` | Sí como prior | Identificado como prior y no como observación |
| Perfil `UNKNOWN` | Sí como estado de incertidumbre | No asignar un perfil estrecho sin evidencia |
| Rango vacío | Sí como representación de ausencia | Causa explícita; no calcular equity |
| Aproximación experimental | Solo con autorización explícita | Etiquetada y separada de resultados canónicos |
| `0.0` por ausencia | No | Prohibido |
| Inventar categoría | No | Prohibido |
| Convertir `unknown` en `coverage_gap` | No | Prohibido |
| Convertir `coverage_gap` en `exact` por fallback | No | Prohibido |
| Convertir `unsupported` en fold | No | Prohibido |

### 7.1 Política de degradación

No se permite degradar silenciosamente entre niveles de evidencia.

Ejemplos de degradaciones prohibidas:
- Rango específico ausente → rango plano sin identificarlo como prior.
- Tabla exacta ausente → tabla de otro rival presentada como exacta.
- Rango vacío → distribución uniforme.
- Equity actual ausente → equity de showdown presentada como actual.
- Predicción no calibrada → probabilidad calibrada.
- Resultado desconocido → cero.
- Evaluación incompleta → recomendación aparentemente válida.

Una degradación explícita solo puede realizarse cuando exista una política autorizada para esa operación. Debe conservar la fuente original, el método alternativo y las limitaciones.

---

## 8. Relación con el contrato preflop

`PreflopDecision` y `CoverageState` son contratos distintos.

`PreflopDecision` describe:
- Estado de resolución.
- Categoría preflop.
- Denominador.
- `decision_plan`.
- `range_query`.
- Razones de incertidumbre.

`CoverageState` describe si la consulta de tabla correspondiente puede resolverse.

Reglas:
- `PreflopDecision.status=unresolved` no se convierte en una consulta válida por tener una tabla disponible.
- `PreflopDecision.status=resolved` no garantiza cobertura exacta.
- Una consulta `impossible` no invalida automáticamente toda la decisión del héroe.
- `unknown` en la clasificación no debe transformarse en `coverage_gap`.
- `coverage_gap` no modifica retrospectivamente la categoría preflop.
- La versión del contrato debe acompañar a la consulta y a la resolución.

El consumidor debe evaluar ambas dimensiones por separado.

---

## 9. Relación con HU y MW

Esta política no habilita multiway.

En HU y MW deben conservarse por separado:
- Cobertura de la consulta.
- Disponibilidad del rango de cada rival.
- Validez de la combinación de rangos.
- Disponibilidad de equity.
- Disponibilidad de EV.
- Estado de recomendación.

Un rango disponible para cada rival individual no demuestra que exista una distribución conjunta multiway válida.

No se permite:
- Sustituir una distribución conjunta por `RangeState.union()`.
- Tratar rangos marginales como distribución conjunta.
- Ignorar blockers compartidos.
- Convertir una aproximación HU en soporte MW.
- Declarar cobertura MW porque existan tablas HU.

Cualquier baseline de independencia debe identificarse como supuesto experimental y no como modelo conjunto validado.

`MULTIWAY_SOPORTADO` permanece `False`.

---

## 10. Criterios de aceptación

### 10.1 Cobertura

- El 100 % de las consultas recibe un estado de cobertura y una razón.
- Cada consulta conserva su clave solicitada.
- Los aliases tienen una declaración verificable.
- Los fallbacks conservan el estado original de cobertura.
- `unknown` no se agrupa con `coverage_gap`.
- `impossible` se justifica mediante el contexto de la consulta.
- Las métricas declaran denominadores y filtros.

### 10.2 Rangos

- Un rango vacío conserva su causa.
- Un rango vacío nunca produce equity.
- Un rango no disponible no se convierte en un rango uniforme.
- Un prior se identifica como prior.
- Los blockers no pueden producir una interpretación ficticia del rival.
- Un rango incompatible no se utiliza como si fuera válido.
- `n_eff` no se presenta como número de manos observadas.

### 10.3 Estadística y estimaciones

- Toda estadística tiene denominador y filtros.
- Toda predicción declara modelo y método.
- Una predicción no calibrada no se presenta como probabilidad calibrada.
- Toda simulación declara tamaño de muestra y método.
- Las semillas se registran cuando existe muestreo estocástico.
- La incertidumbre se informa cuando el método permite estimarla.
- La ausencia de intervalo no se oculta ni se sustituye por uno inventado.
- Una equity distingue actual y showdown.
- Un EV declara supuestos y procedencia.

### 10.4 Consumidores

- Ningún consumidor convierte ausencia de información en cero.
- Ningún consumidor convierte `unknown` en `coverage_gap`.
- Ningún consumidor utiliza un fallback como exacto.
- Ningún consumidor convierte `unsupported` en una acción.
- Ninguna etapa hereda automáticamente la validez de la etapa anterior.
- La sombra no cambia acciones ni modifica datos.
- Entrenamiento conserva las diferencias entre observación, prior, predicción y aproximación.

### 10.5 Reproducibilidad

- Los resultados declaran versiones y snapshots pertinentes.
- Los artefactos conservan sus dependencias.
- Las métricas pueden reproducirse sobre la misma fuente y filtros.
- Las diferencias entre snapshots no se atribuyen automáticamente a cambios de código.
- No se regeneran artefactos sin justificación y autorización.

---

## 11. Límites de esta política

Este documento define semántica y comportamiento esperado. No autoriza:
- Implementar resolvedores durante la fase documental.
- Cambiar la ruta live.
- Cambiar `motor/`.
- Modificar `data/`.
- Regenerar matrices, rangos, perfiles o modelos.
- Activar `MULTIWAY_SOPORTADO`.
- Corregir automáticamente registros históricos.
- Declarar validación estratégica por el mero cumplimiento de estos estados.

La implementación futura deberá contrastarse con las estructuras reales y los consumidores existentes antes de introducir cambios.

**Principio final:** la ausencia de evidencia es información sobre las limitaciones del sistema, no evidencia de que el valor sea cero. Cada consumidor debe conservar esa distinción hasta el resultado final.