# Escenarios de referencia HU (2026-11-13)

**Estado:** especificación de fixtures. No implementa un harness, no cambia código, no escribe datos y no activa multiway.

**Objetivo:** establecer casos reproducibles para validar el contrato `PreflopDecision`, la resolución de cobertura, las etiquetas históricas, las consultas de rango y las diferencias entre legacy y canonical.

Los escenarios reales proceden de la base congelada utilizada en `DOCS/DISCREPANCIAS_AUDITORIA_2026-11-13.md`. Si cambia la base, los identificadores pueden dejar de representar el mismo contenido. Cada fixture real debe conservar una copia mínima suficiente de su secuencia y la identidad exacta del snapshot del que procede.

Este documento distingue:
- Estado del juego antes de la decisión del héroe.
- Clasificación canónica de la oportunidad de decisión.
- Acción histórica que realizó el héroe, si existe.
- Plan de consulta de tablas.
- Resolución de cobertura.
- Consulta de rango.
- Resultado legacy.

Una acción histórica no debe confundirse con la categoría canónica del estado de decisión.

---

## 1. Regla de comparación

Cada fixture debe declarar:

### 1.1 Identidad y procedencia

```text
fixture_id
source: real | synthetic
hand_id                 # obligatorio para real
data_snapshot_hash      # obligatorio para real
source_document
contract_version
fixture_version
```

Para fixtures sintéticas:

```text
synthetic_case_id
scenario_description
```

Los escenarios reales deben poder ejecutarse sin consultar la sesión viva ni depender de que el archivo histórico conserve el mismo orden o contenido.

### 1.2 Contexto de decisión

```text
hero_pos
hero_seat
button_seat
seat_order
players_at_table
active_positions
hero_index
prior_actions
```

Se incluyen los campos que el contrato necesite para resolver legalidad y orden. Los campos que no sean aplicables se declaran expresamente como no aplicables.

`prior_actions` contiene exclusivamente los eventos anteriores a la primera decisión voluntaria del héroe que se está evaluando.

La acción que el héroe terminó realizando, si existe, se registra por separado como resultado histórico:

```text
observed_hero_action
observed_hero_action_class
```

No se introduce esa acción en `prior_actions` para construir el estado que debía existir antes de tomarla.

### 1.3 Estado canónico esperado

```text
decision_present
decision_status
reason
spot_category
denom
decision_plan
range_query
```

Categorías canónicas admitidas según la especificación del contrato:

```text
OPEN
LIMP
CALL_LIMP
FACING_OPEN
FACING_3BET
FACING_4BET
ROL
SQUEEZE
CHECK_BB
OTHER_RESOLVED
```

La lista es una referencia al contrato, no autorización para inventar categorías nuevas.

Si una situación no puede clasificarse con las categorías existentes, se debe resolver mediante `unresolved` o mediante la categoría residual únicamente cuando el contrato lo permita.

### 1.4 Acción histórica

Cuando exista:

```text
observed_hero_action
observed_hero_action_class
observed_amount
observed_amount_semantics
observed_amount_precision
```

La acción histórica puede ser:
- fold;
- check;
- call;
- limp;
- open;
- raise;
- 3bet;
- 4bet;
- 5bet;
- otra acción reconocida por el contrato.

La clasificación de esa acción no sustituye a `spot_category`.

Ejemplo:

```text
spot_category = FACING_OPEN
observed_hero_action_class = CALL
```

El héroe se encontraba frente a una apertura y terminó pagando. La categoría canónica describe el contexto; la acción observada describe lo que hizo.

### 1.5 Cobertura y rango

Cada consulta de tabla debe declarar:

```text
requested_key
coverage_state
reason
source_key
alias_of
fallback_used
fallback_key
```

Los campos condicionales se omiten cuando no aplican.

La consulta de rango debe distinguir:

```text
range_query_status
range_source
range_status
range_reason
```

No se debe usar `no_range`, `empty`, `unavailable` y `not_applicable` como sinónimos.

- `not_applicable`: no corresponde realizar una consulta de rango.
- `not_requested`: el fixture no evalúa esa operación.
- `empty`: la consulta se realizó y el resultado fue un rango vacío.
- `unavailable`: no existe una fuente utilizable.
- `unknown`: no se puede determinar el rango.
- `usable`: existe un rango válido para la operación.

### 1.6 Legacy

Cuando corresponda:

```text
legacy_spot
legacy_n_raises
legacy_limps
legacy_table_plan
legacy_coverage
legacy_action
```

Legacy debe evaluarse con la implementación histórica sin modificarla para hacer coincidir los resultados.

---

## 2. Reglas de construcción de fixtures

### 2.1 Secuencia completa

Una fixture real no puede limitarse a una descripción como:

```text
3bet previo
```

Debe incluir los eventos anteriores al héroe suficientes para reproducir:
- número de subidas;
- número de limps;
- número de callers;
- último agresor;
- posición de los participantes;
- nivel de apuesta;
- aportaciones y posts;
- orden de acción.

La secuencia debe incluir los eventos necesarios para distinguir ciegas, antes, straddles y acciones voluntarias.

### 2.2 Importes

No se puede utilizar una secuencia con importes omitidos cuando el importe sea necesario para determinar si una acción fue limp, apertura, subida válida o subida sin incremento.

Los importes deben conservar:
- valor original;
- semántica de origen;
- representación normalizada;
- precisión declarada.

No se deben inventar importes para completar un ejemplo histórico.

Si la fuente no contiene información suficiente, la fixture debe probar el resultado `unresolved` correspondiente, no asumir un importe.

### 2.3 Separación temporal

Para cada fixture se distinguen:

1. Estado anterior al héroe.
2. Primera decisión voluntaria del héroe.
3. Acción histórica posterior del héroe, si existe.
4. Acciones posteriores de los demás jugadores, si se necesitan para otra prueba.

La clasificación canónica de la decisión se calcula con el estado anterior al héroe.

### 2.4 Estado de fixture

Cada escenario tendrá uno de estos estados de preparación:

```text
ready
needs_source_materialization
needs_contract_resolution
not_applicable
```

- `ready`: contiene entradas completas y expected definidos.
- `needs_source_materialization`: falta copiar evidencia original.
- `needs_contract_resolution`: existe una ambigüedad en la especificación que impide fijar expected.
- `not_applicable`: el caso prueba expresamente que no existe una decisión o consulta.

Una fixture no se considera ejecutable por el simple hecho de tener un ID y una expectativa textual.

---

## 3. Escenarios reales

Los siguientes escenarios conservan los identificadores del inventario original. Las secuencias resumidas son referencias de auditoría, no sustituyen las acciones completas que deben almacenarse en cada fixture.

Abreviaturas:
- `R`: subidas anteriores al héroe.
- `L`: limps anteriores al héroe.
- `C`: callers anteriores al héroe.
- `Plan`: plan de consulta de tabla.
- `Cov`: cobertura de las tablas solicitadas.
- `Action`: acción histórica del héroe, no categoría canónica.

| ID | Mano / héroe | Contexto anterior al héroe | Categoría canónica esperada | Acción histórica | Plan esperado |
|---|---|---|---|---|---|
| R01 | `H_0001/UTG` | Sin acciones voluntarias previas | `OPEN` | Open | `OR` |
| R02 | `H_0001/MP` | UTG abrió | `FACING_OPEN` | Call | `3B/Call_OR` |
| R03 | `H_0002/MP` | UTG limp | `ROL` | Fold | `ROL` |
| R04 | `H_0003/CO` | UTG abrió | `FACING_OPEN` | Fold | `3B/Call_OR` |
| R05 | `H_0005/SB` | UTG, MP y CO limpearon | `CALL_LIMP` | Call | `ROL` |
| R06 | `H_0012/BB` | Dos limps anteriores | `CHECK_BB` | Check | No requiere consulta de apertura |
| R07 | `H_0022/CO` | UTG abrió | `FACING_OPEN` | 3bet | `3B/Call_OR` |
| R08 | `H_0032/SB` | UTG limp | `ROL` | Raise / ROL | `ROL` |
| R09 | `H_0033/SB` | Sin acciones voluntarias previas | `LIMP` | Limp | `OR` |
| R10 | `H_0066/SB` | Acciones anteriores de fold; sin subida ni limp | `OPEN` | Open | `OR` |
| R11 | `H_0124/BB` | Enfrenta una 3bet | `FACING_3BET` | Fold | `4B/Call_3B` |
| R12 | `H_0130/SB` | Enfrenta una 3bet | `FACING_3BET` | Call | `4B/Call_3B` |
| R13 | `H_0135/BB` | Open y dos callers anteriores | `SQUEEZE` | Raise / Squeeze | `3B/Call_OR` |
| R14 | `H_0004/MP` | Sin acciones voluntarias previas | `LIMP` | Limp corto | `OR` |
| R15 | `H_0056/BTN` | Check fuera de BB | `unresolved` | Check | Ninguno |
| R16 | `H_0357/SB` | Secuencia contaminada | `unresolved` | Acción ambigua | Ninguno |
| R17 | `H_0266/BB` | No existe decisión voluntaria del héroe | No hay decisión | No aplicable | Ninguno |

### 3.0 Clasificación de los fixtures reales R01–R14

Los escenarios reales se clasifican, según la evidencia disponible en la fuente congelada, en:

- **Fuente fiel:** la secuencia y los importes se copian sin reinterpretarlos; la clasificación canónica se calcula a partir de ellos.
- **Canónico resuelto:** existe evidencia suficiente para fijar categoría, plan y cobertura sin aproximación.
- **Parcialmente evaluable:** falta evidencia necesaria (semántica de importes, cartas, all-in, orden legal verificado); no se presenta como completamente resuelto.

| ID | Clasificación de fixture | Motivo principal |
|---|---|---|
| R01 | Fuente fiel / canónico resuelto | Secuencia completa y apertura sin subida previa |
| R02 | Fuente fiel / canónico resuelto | Apertura previa identificable |
| R03 | Fuente fiel / canónico resuelto | Limp previo identificable |
| R04 | Fuente fiel / canónico resuelto | Apertura previa identificable |
| R05 | Fuente fiel / canónico resuelto | Limps previos identificables |
| R06 | Fuente fiel / canónico resuelto | BB con limps previos |
| R07 | Fuente fiel / canónico resuelto | Apertura previa identificable |
| R08 | Fuente fiel / parcialmente evaluable | El raise sobre limps depende de importes cuya semántica debe verificarse |
| R09 | Fuente fiel / canónico resuelto | Sin acciones voluntarias previas |
| R10 | Fuente fiel / canónico resuelto | Folds previos no crean subida ni limp |
| R11 | Fuente fiel / canónico resuelto | 3bet previa identificable |
| R12 | Fuente fiel / parcialmente evaluable | El fallback continúa siendo `coverage_gap`; la acción histórica no demuestra cobertura |
| R13 | Fuente fiel / parcialmente evaluable | Squeeze requiere conservar open, callers y orden; la cobertura se fija solo si las consultas están demostradas |
| R14 | Fuente fiel / parcialmente evaluable | Limp corto depende de importe y semántica (`short_limp`) |

No se presenta como completamente resuelto un escenario que carece de evidencia necesaria.

### 3.1 Cobertura esperada de escenarios reales
| ID | Cobertura esperada | Rango |
|---|---|---|
| R01 | `exact` para `OR` | Consulta de rango correspondiente a `OPEN` |
| R02 | `exact` para `3B`; `coverage_gap` para `Call_OR` | Consulta correspondiente a `FACING_OPEN` |
| R03 | `exact` para `ROL` | No debe inferirse rango del hecho de que el héroe haya foldeado |
| R04 | `exact` para `3B`; `coverage_gap` para `Call_OR` | No se necesita rango para justificar la acción histórica de fold |
| R05 | `exact` para `ROL` | Consulta correspondiente a `CALL_LIMP` |
| R06 | No aplica una tabla de apertura | No requiere rango para la acción histórica de check |
| R07 | `exact` para `3B`; `coverage_gap` para `Call_OR` | Consulta correspondiente a `FACING_OPEN` |
| R08 | `exact` para `ROL` | Consulta correspondiente a `ROL` |
| R09 | `exact` para `OR` | Consulta correspondiente a `LIMP` |
| R10 | `exact` para `OR` | Consulta correspondiente a `OPEN` |
| R11 | `coverage_gap` para `4B` y `Call_3B` | No requiere rango para justificar la acción histórica de fold |
| R12 | `coverage_gap` con `fallback_other_vs` en las consultas afectadas | La aproximación debe permanecer identificada como fallback |
| R13 | `exact` para las consultas indicadas | Consulta correspondiente a la oportunidad de squeeze |
| R14 | `exact` para `OR` | Consulta correspondiente a `LIMP`, con `short_limp=True` |
| R15 | `unknown` para cualquier consulta que dependa del estado inválido | No hay consulta canónica |
| R16 | `unknown` | No hay consulta canónica |
| R17 | No aplica | No hay decisión ni consulta |

Los estados de cobertura son los esperados según el inventario comunicado. Antes de convertir estos casos en fixtures ejecutables, deben confirmarse las claves y las fuentes reales en el snapshot identificado.

### 3.2 Notas por escenario

**R01 — Apertura desde UTG**

- El estado se construye sin acciones voluntarias previas.
- `spot_category=OPEN`.
- La acción histórica `open` se registra aparte.
- La consulta `OR` debe resolverse como exacta.

**R02 — Call frente a apertura**

- El contexto anterior contiene la apertura de UTG.
- `spot_category=FACING_OPEN`.
- La acción observada es `call`.
- La falta de `Call_OR` debe permanecer como `coverage_gap`.
- No se puede inferir que la tabla existe porque la acción histórica sea un call.

**R03 — Fold frente a limp**

- El contexto anterior contiene un limp.
- La oportunidad del héroe corresponde a `ROL`.
- La acción histórica es fold.
- El plan de tabla y la acción histórica no se confunden.
- La ausencia de consulta de rango por haber foldeado debe declararse como decisión del fixture, no como inexistencia de rango.

**R04 — Fold frente a open**

- El estado es `FACING_OPEN`.
- La acción observada es fold.
- La consulta de tablas debe reflejar la cobertura de `3B` y `Call_OR`, aunque la acción histórica haya sido fold.

**R05 — Call frente a limps**

- Deben conservarse todos los limps anteriores y las aportaciones correspondientes.
- La categoría describe una oportunidad de completar o jugar frente a limps, no la acción posterior del héroe.
- No se deben sumar importes acumulados como si fueran incrementos.

**R06 — Check de BB**

- Deben conservarse los limps anteriores.
- El héroe es BB.
- La acción observada es check.
- No debe asignarse una tabla de apertura como si el héroe estuviera ante un bote sin limps.
- El `range_query` se determina según la operación evaluada. No se infiere una consulta de rango por el mero hecho de existir la decisión.

**R07 — 3bet frente a open**

- El estado antes del héroe es `FACING_OPEN`.
- La acción observada es 3bet.
- `3B` puede estar cubierta aunque `Call_OR` no lo esté.
- La cobertura de una rama no debe ocultar la ausencia de la otra.

**R08 — ROL**

- Debe existir al menos un limp anterior.
- La acción observada del héroe es un raise sobre los limps.
- La categoría y el plan corresponden a la oportunidad de ROL.

**R09 — Limp desde SB**

- No existen acciones voluntarias previas.
- La acción observada es limp.
- La categoría describe la oportunidad de entrar sin subida previa.
- No se clasifica como `CALL_LIMP`, porque no hay limps anteriores.

**R10 — Apertura desde SB**

- Los folds previos no crean una subida ni un limp.
- La categoría es `OPEN`.
- La acción observada es una apertura.
- El fixture debe incluir la secuencia completa de folds y la información de posición necesaria.

**R11 — Fold frente a 3bet**

- La categoría es `FACING_3BET`.
- La acción observada es fold.
- El plan de decisión puede existir aunque el héroe haya foldeado.
- La falta de cobertura no convierte el estado en `unresolved`.

**R12 — Call frente a 3bet con fallback**

- La categoría es `FACING_3BET`.
- La acción observada es call.
- La cobertura continúa siendo `coverage_gap`.
- El fallback debe conservar la tabla realmente utilizada y no contabilizarse como exacto.
- La acción histórica no demuestra que el fallback sea estratégicamente correcto.

**R13 — Squeeze**

- Debe conservarse el open inicial y los dos callers anteriores.
- La oportunidad es de squeeze.
- La acción observada es un raise.
- No se debe clasificar como squeeze por el mero hecho de existir varios jugadores en la mano: debe respetarse el orden y la relación entre open, callers y decisión del héroe.

**R14 — Limp corto**

- `short_limp=True`.
- La acción histórica es un limp corto.
- No se convierte en apertura por superar un umbral de importe.
- El importe debe conservar la semántica y precisión originales.

**R15 — Check fuera de BB**

- La secuencia anterior a la acción debe demostrar la ilegalidad. La posición por sí sola no basta: se requiere el estado previo (por ejemplo, una subida vigente cuando el jugador está en BB, o una posición no BB).
- `decision_status=unresolved`.
- `reason=check_fuera_de_BB` o `check_bb_facing_raise`, según el estado previo.
- No se consulta tabla.
- No se transforma en `CHECK_BB`.
- Esta conclusión se sostiene por el estado previo y la posición declarada, no por importes cuya semántica sea desconocida.
**R16 — Subida sin incremento**

- La secuencia se conserva como contaminada.
- `decision_status=unresolved`.
- `reason=secuencia_ambigua:subida_sin_incremento`.
- No se intenta reconstruir el nivel de apuesta mediante heurísticas posteriores.
- No se consulta tabla.
- La ausencia de incremento solo se afirma cuando la semántica del importe está establecida o demostrada; en caso contrario, la razón correspondiente es la de incertidumbre de importe, no `subida_sin_incremento`.
**R17 — Sin decisión**

- No existe una primera decisión voluntaria del héroe que evaluar.
- `decision_status = no_decision`, con `reason = sin_decision_voluntaria`.
- No equivale a `unresolved`: `unresolved` se reserva para una decisión existente que no pudo resolverse por falta de evidencia.
- La fixture debe comprobar que no se crea una decisión ficticia ni una categoría aproximada.
- No se consulta tabla ni rango.
---

## 4. Escenarios sintéticos

Los escenarios sintéticos prueban reglas aisladas. Deben utilizar entradas completas y consistentes con la semántica de importes, posts, posiciones y orden del contrato.

Las secuencias que siguen son descripciones de los casos. Antes de implementarlas, deben materializarse con los campos obligatorios del contrato, incluyendo eventos de ciegas y orden de asientos cuando sean necesarios.

| ID | Contexto anterior al héroe | Héroe | Categoría canónica | Acción de prueba / resultado |
|---|---|---|---|---|
| S01 | Sin acciones voluntarias previas | UTG | `LIMP` | Limp corto; `short_limp=True`; plan `OR` |
| S02 | UTG abrió | BB | `unresolved` | Check ilegal frente a subida; sin plan |
| S03 | Importe de apertura ausente | UTG | `unresolved` | `importe_ausente`; sin plan |
| S04 | Importe de apertura igual a cero | UTG | `unresolved` | `importe_cero`; sin plan |
| S05 | MP intenta subir sin incremento frente a UTG | MP | `unresolved` | `subida_sin_incremento`; sin plan |
| S06 | Post BB duplicado | BB | `unresolved` | `posta_repetida`; sin plan |
| S07 | Acción sin posición | Desconocida | `unresolved` | `pos_ausente`; sin plan |
| S08 | UTG abrió, MP 3beteó y CO 4beteó | BTN | `FACING_4BET` | Acción de prueba: 5bet; plan `5B/Call_4B` |
| S09 | UTG y MP limpearon | CO | `ROL` | Acción de prueba: raise / ROL |
| S10 | UTG abrió, MP y CO pagaron | BTN | `SQUEEZE` | Acción de prueba: raise / squeeze |
| S11 | UTG abrió y MP 3beteó | CO | `FACING_3BET` | Acción de prueba: 4bet; plan `4B/Call_3B` |
| S12 | UTG abrió, MP 3beteó y CO 4beteó | BTN | `FACING_4BET` | Acción de prueba: call; plan `5B/Call_4B` |
| S13 | BB enfrenta una secuencia con cinco subidas anteriores | BB | `OTHER_RESOLVED` o estado de soporte definido por contrato | Consulta de nivel 6bet no soportada |
| S14 | UTG abrió, MP 3beteó y CO pagó | BTN | `FACING_3BET` | Acción de prueba: raise; no clasificar automáticamente como squeeze |

### 4.1 Correcciones semánticas importantes

**S01 — Limp corto**

El héroe está en posición de entrar en un bote sin subida previa. La acción que se prueba es un limp corto. La categoría del estado y la acción observada se mantienen separadas.

**S02 — BB frente a subida**

El héroe BB no puede realizar un check cuando existe una subida que debe enfrentar. Debe producirse el estado de error contractual indicado, sin plan de tabla.

**S03 y S04 — Importe inválido**

La ausencia de importe y el importe cero son errores distintos. Ambos impiden construir una clasificación fiable, pero deben conservar razones diferentes.

**S05 — Subida sin incremento**

El contrato no debe aceptar una subida cuyo importe no supere el nivel vigente, cuando la semántica de la fuente y la regla de apuestas indiquen que no hubo incremento.

**S06 — Post repetido**

La fixture debe contener dos eventos identificados como posts de BB para el mismo participante y contexto. No debe resolverlos como dos acciones voluntarias.

**S07 — Posición ausente**

La posición desconocida no se sustituye por una posición inferida a partir del orden parcial de acciones.

**S08 — 5bet**

Antes de la decisión de BTN ya ocurrieron:
- Apertura UTG.
- 3bet MP.
- 4bet CO.

Por tanto, BTN está enfrentando una 4bet. La categoría canónica es `FACING_4BET`. Si la acción de prueba es raise, esa acción se clasifica como 5bet. El plan de consulta corresponde a `5B/Call_4B`.

**S09 — ROL**

CO enfrenta limps previos. La categoría es `ROL`; la acción de prueba es el raise sobre los limps.

**S10 — Squeeze**

BTN enfrenta una apertura y dos callers. La oportunidad se clasifica como squeeze. La acción de prueba puede ser raise. No se debe contar a los callers como subidas adicionales.

**S11 — 4bet**

CO enfrenta la 3bet de MP. La categoría es `FACING_3BET`; si la acción de prueba es raise, la acción observada es 4bet. El plan corresponde a `4B/Call_3B`.

**S12 — Call frente a 4bet**

BTN enfrenta una 4bet. La categoría es `FACING_4BET`; la acción de prueba es call. El plan de decisión corresponde a `5B/Call_4B`, si el contrato y la tabla admiten esa consulta.

**S13 — Nivel no soportado**

La secuencia debe materializar cinco subidas anteriores al héroe. La consulta de nivel 6bet no debe degradarse a una tabla 5bet ni a una tabla de otro nivel.

La clasificación del estado y el soporte de tabla son dimensiones distintas. Si el contexto es comprensible y legal, no debe marcarse `unresolved` únicamente porque falte una tabla. Debe declararse el estado de cobertura o soporte correspondiente.

**S14 — Caller después de 3bet**

El caller posterior a la 3bet no convierte automáticamente la oportunidad del héroe en squeeze.

BTN enfrenta una 3bet y un caller de esa 3bet. La categoría canónica permanece `FACING_3BET`, salvo que el contrato defina expresamente otra categoría para esa situación. La acción de raise se registra por separado.

---

## 5. Fixtures de cobertura aislada

Estos casos prueban la resolución de tablas. No son necesariamente decisiones completas del héroe.

| ID | Consulta | Resultado esperado |
|---|---|---|
| L01 | `_pf_table_lookup('4B','UTG','MP')` | `alias` a `4B_UTG_vs_HJ`, con `source_key` y regla de alias visibles |
| L02 | Consulta `OR_BB` en contexto sin oportunidad legal de apertura | `impossible`, con razón contextual |
| L03 | `_pf_table_lookup('Call_OR','MP','UTG')` | `coverage_gap` |
| L04 | `_pf_table_lookup('4B','BTN','CO')` | `coverage_gap` con fallback identificado, si el inventario confirma esa sustitución |
| L05 | Acción sin posición | `unknown` |

### 5.1 Restricciones

- L01 no demuestra que todos los usos del alias sean estratégicamente equivalentes.
- L02 no declara imposible cualquier acción de BB: prueba únicamente la consulta de apertura en el contexto especificado.
- L03 no debe producir un valor cero ni una tabla inventada.
- L04 no puede contabilizarse como exacto.
- L05 no puede transformarse en `coverage_gap`.

---

## 6. Comparación con legacy

Para cada fixture se registra:

```text
fixture_id
contract_version
legacy_adapter_version
canonical_adapter_version

canonical_status
canonical_reason
canonical_category
canonical_denom
canonical_decision_plan
canonical_range_query
canonical_coverage

legacy_spot
legacy_n_raises
legacy_limps
legacy_table_plan
legacy_coverage

observed_hero_action
legacy_action
canonical_action_if_computed

difference_kind
difference_detail
```

Categorías de diferencia:

```text
classification
status
denominator
table
coverage
range
action
provenance
no_comparable
```

Reglas:
- No se exige paridad total entre legacy y canonical.
- Toda diferencia debe estar explicada.
- Un estado `unresolved` no puede convertirse en una categoría con tabla.
- Un estado `impossible` no puede contabilizarse como tabla ausente.
- Una diferencia de acción solo puede evaluarse cuando ambas rutas han producido una recomendación comparable.
- Una acción histórica no se compara directamente con una recomendación como si ambas fueran resultados del mismo tipo.
- No se modifica legacy para hacer coincidir los resultados.

La comparación debe separar las diferencias de clasificación de las diferencias posteriores de tabla, rango, equity, EV y política.

---

## 7. Frecuencias, equity y EV

### 7.1 Frecuencias

Una frecuencia solo se compara cuando:
- La celda tiene una definición canónica estable.
- La cobertura es `exact` o un alias autorizado para esa operación.
- Existe un denominador correcto.
- Los filtros y la ventana de datos son comparables.
- Las etiquetas utilizadas pertenecen al mismo esquema o se ha declarado la transformación.

No se mezclan en una misma frecuencia canónica:
- `coverage_gap`;
- `impossible`;
- `unknown`;
- `fallback_other_vs`;
- priors;
- predicciones.

Un alias se informa separadamente o con una dimensión explícita que permita identificarlo.

### 7.2 Equity

Una equity solo se compara si ambas estimaciones representan el mismo objeto:

- Equity actual con equity actual.
- Showdown con showdown.
- Misma definición de rangos.
- Mismo tratamiento de blockers.
- Método y parámetros declarados.

Una comparación entre equity actual y showdown no constituye una comparación directa.

### 7.3 EV

El EV debe declarar:
- Acción evaluada.
- Estructura de bote.
- Supuestos sobre respuestas rivales.
- Rangos utilizados.
- Método de cálculo.
- Parámetros de simulación cuando existan.
- Incertidumbre cuando corresponda.

No se declara ganador por una suma agregada sin analizar los escenarios y la distribución de diferencias.

Una acción histórica no demuestra que su EV fuera correcto ni que la acción alternativa hubiera sido mejor.

---

## 8. Criterios de aceptación

### 8.1 Integridad de fixtures

1. Los 17 escenarios reales conservan sus IDs y referencias de origen.
2. Los 14 escenarios sintéticos tienen secuencias completas y reproducibles.
3. Cada fixture real conserva el hash del snapshot y la secuencia mínima.
4. Los importes tienen semántica y precisión declaradas.
5. Las posiciones y el orden de acción son suficientes para evaluar legalidad.
6. Las acciones del héroe están separadas de `prior_actions`.
7. Cada escenario declara si es ejecutable, incompleto o no aplicable.

### 8.2 Contrato

1. R15 y R16 producen `unresolved` y no consultan tablas.
2. R17 no crea una decisión ficticia.
3. R02, R04 y R07 mantienen el `coverage_gap` de `Call_OR`.
4. R11 y R12 distinguen un gap sin fallback de un gap con fallback.
5. R12 no contabiliza el fallback como exacto.
6. R14 conserva `short_limp=True`.
7. S01–S07 no inventan categorías ni tablas.
8. S08–S14 cuentan correctamente las subidas anteriores al héroe y separan la acción posterior.
9. S13 no degrada el nivel 6bet a una tabla de otro nivel.
10. S14 no se convierte automáticamente en squeeze por la presencia de un caller posterior a la 3bet.

### 8.3 Cobertura y rango

1. Cada consulta devuelve estado y razón.
2. Los aliases muestran su fuente y regla.
3. Los fallbacks conservan su estado original.
4. `unknown` no se contabiliza como `coverage_gap`.
5. `impossible` se determina por contexto.
6. Un rango vacío no produce equity.
7. La ausencia de rango no se interpreta como frecuencia cero.

### 8.4 Comparación

1. Las diferencias legacy/canonical se clasifican.
2. No se exige paridad artificial.
3. Las acciones históricas no se confunden con recomendaciones.
4. No se comparan frecuencias con denominadores distintos.
5. No se comparan equity actual y showdown como si fueran equivalentes.
6. No se declara una mejora estratégica por pasar fixtures.

---

## 9. Materialización pendiente antes de implementar

El documento de origen contiene resúmenes de secuencias, no todos los datos necesarios para fixtures ejecutables.

Antes de crear el harness, debe realizarse una fase read-only de materialización:

1. Recuperar la secuencia original completa de cada mano real.
2. Identificar el hash exacto del snapshot.
3. Copiar los eventos anteriores al héroe.
4. Separar la acción del héroe y las acciones posteriores.
5. Conservar posiciones, asientos y orden.
6. Conservar posts, ciegas, antes y straddles.
7. Conservar importes originales y su semántica.
8. Verificar las claves de tablas y sus estados de cobertura.
9. Confirmar que los expected corresponden a la versión aprobada del contrato.
10. Registrar las discrepancias sin corregir automáticamente la base.

Si un dato no está presente en la fuente, debe quedar como desconocido y el escenario debe probar el tratamiento correspondiente. No se reconstruye por intuición.

---

## 10. Límites de esta fase

Este documento define escenarios y expectativas. No autoriza:
- Implementar el harness en esta fase documental.
- Modificar `motor/`.
- Modificar `data/`.
- Corregir registros históricos.
- Regenerar artefactos.
- Cambiar la ruta live.
- Activar multiway.
- Cambiar `MULTIWAY_SOPORTADO`.
- Declarar validación estratégica por coincidencia de fixtures.

Los escenarios HU no demuestran soporte multiway ni validan por sí solos la rentabilidad de las recomendaciones.

**Principio final:** cada fixture debe probar un estado de decisión reproducible, no una interpretación retrospectiva de la acción que el héroe terminó realizando. La clasificación del contexto, la acción histórica, la cobertura y la recomendación son resultados diferentes y deben permanecer separados.