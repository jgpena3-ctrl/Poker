# Migración y rollback del contrato preflop (2026-11-13)

**Estado:** diseño. No cambia la ruta live, no modifica `motor/`, no escribe en `data/` y no activa artefactos.

**Objetivo:** migrar progresivamente live y entrenamiento hacia `PreflopDecision`, evitando mezclar contratos, etiquetas, tablas y artefactos incompatibles. Toda transición debe ser reversible y verificable.

**Base de referencia declarada:**
- `motor/preflop_contract.py` contiene el contrato estricto y el modo `legacy=True`.
- `motor/asistente_live.py` utiliza `_preflop_spot` y `_preflop_raises` para la decisión actual; `first_decision` y `table_plan` se utilizan en sombra.
- `motor/learn.py::preflop_events` conserva etiquetas legacy.
- `ShadowPreflopLog` permite comparar resultados anteriores y nuevos sin escribir por defecto.

Estos puntos describen la base de diseño comunicada. Antes de implementar, deben verificarse contra el código y el commit efectivo. Este documento no certifica que las interfaces mencionadas tengan ya todos los comportamientos aquí especificados.

---

## 1. Principios de migración

1. **Primero sombra, después serving.** Ningún cambio en la ruta de decisión live hasta que la paridad mecánica, la cobertura y la validación estratégica HU hayan superado sus respectivas puertas de aceptación.

2. **Una sola fuente canónica.** La clasificación preflop se implementa una sola vez mediante `PreflopDecision`. Los consumidores no reproducen por separado las reglas de clasificación.

3. **Legacy explícito e inalterado.** La lectura histórica se conserva detrás de un adaptador identificable. No se corrige ni se mejora durante la migración: cualquier modificación invalidaría su función como referencia de rollback.

4. **Separación de responsabilidades.** La clasificación de la mano, la consulta de tablas, la cobertura, la estimación de rangos, la equity, el EV y la selección de acción son etapas diferentes. Ninguna debe presentarse como si sustituyera a las demás.

5. **Compatibilidad declarada.** Todo artefacto y consumidor debe declarar las versiones y dependencias necesarias para determinar si puede utilizarse con el contrato solicitado. La ausencia de metadatos no demuestra compatibilidad.

6. **Telemetría sin autoridad sobre los datos.** Los logs de diferencias no corrigen manos, no reescriben el historial, no generan etiquetas automáticamente y no constituyen por sí mismos una fuente de entrenamiento.

7. **Fail-closed ante incertidumbre.** Una clasificación unresolved, cobertura insuficiente o incompatibilidad de artefactos no puede convertirse silenciosamente en una decisión aparentemente válida.

8. **Rollback desde la primera migración.** Cada fase que introduzca un nuevo consumidor o artefacto debe conservar una ruta verificable para volver al comportamiento anterior.

9. **Datos dinámicos y correcciones manuales.** La base de manos puede recibir sesiones nuevas y correcciones históricas manuales. Ninguna fase regenerará derivados automáticamente por el mero hecho de detectar un cambio en la base.

---

## 2. Componentes y adaptadores

La arquitectura conceptual contiene tres adaptadores y etapas posteriores de resolución:

```text
                         ┌────────────────────────────┐
acciones + contexto ────▶│ CanonicalPreflopAdapter   │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                                  PreflopDecision
                                        │
                                        ▼
                                CoverageResolver
                                        │
                                        ▼
                                  RangeResolver
                                        │
                                        ▼
                              Equity / EV / Policy

                         ┌────────────────────────────┐
acciones + contexto ────▶│ LegacyPreflopAdapter      │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                              spot/action/n_raises

                                  PreflopDecision
                                        │
                                        ▼
                                TrainingLabelAdapter
                                        │
                                        ▼
                                  label_schema
```

Los adaptadores no deben convertirse en un lugar donde se mezclen clasificación, consulta de tablas y selección de acciones.

### 2.1 `CanonicalPreflopAdapter`

**Entrada:**
- Mano y fuente de acciones.
- Identidad y posición del héroe.
- Contexto de mesa requerido por el contrato.
- Información de orden de asientos y botón cuando esté disponible y sea necesaria.
- Versión explícita del contrato.
- Datos de procedencia y precisión de las acciones.

**Salida:**
- Una instancia de `PreflopDecision` conforme a la especificación canónica.

**Responsabilidades:**
- Normalizar las acciones de entrada según la semántica definida en el contrato.
- Clasificar exclusivamente los eventos y el estado preflop.
- Validar el prefijo de acciones anterior a la decisión del héroe.
- Declarar `resolved` o `unresolved` conforme a las reglas del contrato.
- Separar `decision_plan` de `range_query`.
- Conservar las razones de incertidumbre o contaminación cuando no pueda resolver el estado.

**Restricciones:**
- Debe ser determinista y puro respecto de sus entradas.
- No lee modelos ni consulta tablas.
- No selecciona acciones de póker.
- No decide si una tabla es válida.
- No convierte estados desconocidos en categorías conocidas.
- No debe inferir información ausente mediante heurísticas no autorizadas por el contrato.

La versión del contrato debe estar fijada explícitamente. No se permite que un mismo proceso cambie silenciosamente de versión según el consumidor.

### 2.2 `LegacyPreflopAdapter`

**Responsabilidad:** reproducir exactamente el comportamiento anterior de:
- `_preflop_spot`.
- `_preflop_raises`.
- La lógica histórica de limp utilizada por live.

**Reglas:**
- No se corrige ni se mejora.
- No se adapta para que sus resultados coincidan con el contrato canónico.
- Se identifica expresamente como `legacy`.
- Se conserva como referencia de comparación y rollback durante la ventana de migración.
- Sus resultados deben poder reproducirse sobre los mismos estados de entrada.

Si se modifica la lógica legacy, debe registrarse como un cambio separado y dejar de considerarse una referencia inalterada del comportamiento anterior.

### 2.3 `TrainingLabelAdapter`

**Entrada:**
- `PreflopDecision` resuelto.
- Versión del esquema de etiquetas de destino.
- Metadatos necesarios para determinar compatibilidad.

**Salida:**
- Etiqueta de entrenamiento conforme al `label_schema` declarado.

**Reglas:**
- El mapeo entre categorías canónicas y categorías históricas debe ser explícito.
- Todo mapeo que pierda información se identifica como `lossy`.
- Una categoría canónica sin representación compatible no se convierte en otra etiqueta por conveniencia.
- Los estados `unresolved`, `unknown` o contaminados no se convierten en etiquetas ordinarias.
- `training_category` actual, incluyendo compatibilidades como `5bet → 4bet`, permanece identificado como contrato histórico, no como categoría canónica.

El adaptador debe permitir conocer la categoría original, la categoría resultante y la transformación aplicada.

### 2.4 Resolvedores posteriores

La clasificación canónica no resuelve por sí sola la consulta de una tabla ni la decisión de póker.

Se mantienen separadas estas responsabilidades:

- `CoverageResolver`: determina si existe cobertura utilizable para la consulta solicitada.
- `RangeResolver`: obtiene el rango correspondiente y declara su procedencia y estado.
- Estimador de equity: calcula la magnitud de equity correspondiente, diferenciando equity actual y showdown.
- Evaluador de EV: calcula EV por acción a partir de los datos y supuestos declarados.
- Política de selección: compara acciones válidas y selecciona una recomendación cuando existe evidencia suficiente.

Los nombres son interfaces conceptuales. No se presupone que ya existan clases con esos nombres.

### 2.5 Adaptador de estados de `RangeQuery`

Los estados del código actual (`exact`, `alias`, `missing` en `motor/preflop.py`, y `available`, `no_range`, `no_table`, `unresolved` en `range_query_status`) no son idénticos a los estados canónicos propuestos (`available`, `no_range`, `no_table`, `unresolved`, `not_applicable` para `RangeQuery`, y `exact`, `alias`, `coverage_gap`, `impossible`, `unknown` para cobertura). El adaptador debe traducir explícitamente entre ambos contratos, sin renombrar silenciosamente `missing` como `unknown` ni `coverage_gap` como `no_table`.

---

## 3. Fases de migración
### Fase 0 — Congelar especificaciones y referencias

**Objetivo:** disponer de contratos y casos de referencia antes de modificar consumidores.

Requisitos:
- Aprobar la especificación de `PreflopDecision`.
- Aprobar la política de cobertura e incertidumbre.
- Aprobar los escenarios HU de referencia.
- Definir la versión inicial del contrato.
- Definir las versiones iniciales de los esquemas de etiquetas.
- Identificar el comportamiento legacy que servirá como referencia.
- Registrar el commit y los hashes de los datos y artefactos relevantes.

**Salida:**
- Documentos aprobados.
- Fixtures reproducibles.
- Inventario de dependencias.
- Referencia identificable del comportamiento anterior.

**Prohibición:** no cambiar serving ni regenerar artefactos.

### Fase 1 — Contrato canónico en sombra

**Objetivo:** calcular el estado canónico en paralelo sin alterar las recomendaciones.

Trabajo previsto:
- Incorporar el adaptador canónico.
- Incorporar el resolvedor de cobertura.
- Mantener legacy como única fuente de la decisión live.
- Calcular `PreflopDecision` para las mismas manos y estados que procesa live.
- Registrar las diferencias entre clasificación histórica y canónica.
- Identificar explícitamente diferencias de categoría, estado, denominador, plan y consulta de rango.

**Validación mecánica:**
- Todas las fixtures aprobadas producen el resultado canónico esperado.
- Los resultados son deterministas.
- Las entradas ambiguas permanecen unresolved.
- No se inventan posiciones, importes, agresores ni eventos.
- Las diferencias respecto de legacy están clasificadas y explicadas.
- No cambia ninguna recomendación live.

**Validación estadística:**
- Comparar distribuciones sobre una muestra identificada por snapshot.
- Separar manos resueltas y no resueltas.
- Informar denominadores y cobertura.
- No presentar la coincidencia con legacy como prueba de corrección estratégica.

**Salida:** contrato calculado y auditado en sombra, sin autoridad sobre serving.

### Fase 2 — Entrenamiento canónico en sombra

**Objetivo:** comprobar la traducción de las categorías canónicas al esquema de entrenamiento sin sustituir el modelo actual.

Trabajo previsto:
- Generar etiquetas canónicas en paralelo con las legacy.
- Aplicar `TrainingLabelAdapter`.
- Identificar mapeos exactos, alias y mapeos lossy.
- Separar registros no resueltos de las etiquetas utilizables.
- Registrar versiones del contrato y del esquema de etiquetas.
- Mantener intactos los artefactos que consume la ruta actual.

**Validación:**
- Comparación de distribuciones con denominadores explícitos.
- Matriz de confusión entre categorías canónicas y legacy.
- Recuento de etiquetas sin representación.
- Auditoría de los mapeos lossy.
- Evaluación temporal separada de las manos utilizadas para diseñar el contrato.
- Ninguna mejora se declara por una mera coincidencia de etiquetas o distribuciones.

**Salida:** pipeline de etiquetas canónicas evaluado en sombra. El modelo actual sigue siendo el utilizado por serving.

### Fase 3 — Integración canónica en una ruta controlada

**Objetivo:** permitir que el flujo canónico produzca recomendaciones en una ruta controlada, manteniendo legacy disponible y sin activación general.

La integración debe recorrer explícitamente:

```text
estado de mano
    ↓
PreflopDecision
    ↓
validación del estado
    ↓
CoverageResolver
    ↓
RangeResolver
    ↓
estimación y evaluación aplicables
    ↓
política de selección
    ↓
recomendación o unsupported
```

**Reglas:**
- Un `PreflopDecision` resuelto no implica automáticamente que exista cobertura.
- Una consulta de rango válida no implica que exista equity válida.
- Una equity calculada no implica que exista EV válido.
- Un EV calculado no implica que la política pueda seleccionar una acción.
- Cada etapa debe declarar su estado y procedencia.
- No se puede utilizar una tabla incompatible con el contrato o esquema requerido.
- No se puede utilizar una cobertura insuficiente como si fuera exacta.
- No se permite degradar silenciosamente de canónico a legacy.
- No se permite convertir `unsupported` en `fold`, `check`, `call` u otra acción arbitraria.

La ruta canónica debe poder ejecutarse de forma aislada y compararse con legacy sobre los mismos escenarios.

**Router conceptual:**

```text
PreflopRouter:
    mode: legacy | shadow | canonical

    canonical_adapter
    legacy_adapter
    coverage_resolver
    downstream_pipeline
    decision_sink

    decide(state):
        if mode == legacy:
            return legacy_pipeline(state)

        legacy_result = legacy_pipeline(state)
        canonical = canonical_adapter.build(state)

        if mode == shadow:
            compare_and_log(legacy_result, canonical)
            return legacy_result

        if canonical.status != resolved:
            return unsupported(canonical.reason)

        coverage = coverage_resolver.resolve(canonical.range_query)

        if coverage blocks the requested operation:
            return unsupported(coverage.reason)

        return downstream_pipeline(
            canonical,
            coverage
        )
```

Este pseudocódigo expresa el flujo lógico. No define una API lista para implementar ni presupone que `legacy_pipeline` y `downstream_pipeline` existan como objetos actuales.

**Importante sobre `unsupported`:**

`unsupported` es un estado de la evaluación, no una acción de póker.

Debe incluir:
- Motivo.
- Etapa donde se produjo.
- Datos o cobertura que faltan.
- Si existe o no una recomendación válida procedente de otra ruta autorizada.

La interfaz live debe distinguir claramente entre:
- Recomendación válida.
- Evaluación no disponible.
- Error de cálculo.
- Estado incompleto o desconocido.

No se debe mostrar una recomendación canónica cuando el flujo no ha podido justificarla. Tampoco se debe bloquear indefinidamente la interfaz: el comportamiento operativo ante falta de recomendación debe definirse fuera de este contrato estratégico y no inventarse mediante una acción automática.

**Puerta de aprobación antes de serving:**
- Paridad mecánica aprobada.
- Cobertura auditada y sin degradaciones ocultas.
- Compatibilidad de artefactos demostrada.
- Escenarios HU de referencia aprobados.
- Validación estratégica held-out aprobada con métricas y umbrales fijados previamente.
- Rendimiento dentro del presupuesto operativo.
- Rollback probado de extremo a extremo.
- Autorización explícita para cambiar el modo de serving.

El valor predeterminado permanece en `legacy` mientras no exista esa autorización.

### Fase 4 — Retirada controlada de legacy

Solo se considera cuando:
- La ruta canónica ha superado las puertas anteriores.
- Existe una ventana de observación definida.
- No hay regresiones no explicadas.
- El rollback ha sido probado.
- Se conservan fixtures, logs y referencias necesarias para auditoría.

El adaptador legacy puede permanecer como herramienta de auditoría aunque deje de participar en serving.

No se eliminan los datos históricos de comparación ni se altera la referencia de comportamiento anterior.

---

## 4. Modos del router y autoridad

Los modos tienen semánticas distintas:

| Modo | Clasificación canónica | Fuente de recomendación |
|---|---|---|
| `legacy` | No necesaria para serving | Ruta legacy |
| `shadow` | Calculada y comparada | Ruta legacy |
| `canonical` | Obligatoria y validada | Ruta canónica |

Reglas:
- `legacy` no debe depender de que el adaptador canónico funcione.
- `shadow` nunca cambia la acción recomendada.
- `canonical` no cae a legacy en silencio.
- Un cambio de modo debe quedar registrado con versión de configuración y momento de aplicación.
- No se permite activar `canonical` por una variable no versionada o un cambio accidental de configuración.
- La selección del modo debe poder auditarse y revertirse.
- Ningún modo habilita por sí mismo multiway.

`MULTIWAY_SOPORTADO` permanece `False`. Esta migración HU no autoriza modificarlo ni tratar una clasificación preflop canónica como soporte de equity multiway.

---

## 5. Log de diferencias

El log sirve para comparar resultados, no para decidir qué resultado es correcto.

### 5.1 Campos de identificación y procedencia

```text
hand_id
hero_pos
source
code_commit
contract_version
legacy_adapter_version
canonical_adapter_version
data_snapshot
timestamp
```

### 5.2 Campos legacy

```text
legacy_spot
legacy_action
legacy_n_raises
legacy_limps
legacy_table
legacy_model_version
```

Los campos que no existan o no se calculen en una fase se omiten o se registran como no disponibles. No se inventan valores.

### 5.3 Campos canónicos

```text
canonical_status
canonical_reason
canonical_category
canonical_denom
canonical_decision_plan
canonical_range_query
canonical_coverage
```

### 5.4 Campos de comparación y etapas posteriores

```text
difference_kind
difference_detail

table_chosen_legacy
table_chosen_canonical

action_legacy
action_canonical

range_status
equity_status
ev_status
recommendation_status

seed
model_version
artifact_versions
```

Los campos de tabla, acción, equity, EV y modelo solo se registran cuando esas etapas se han ejecutado. En la fase 1 no se debe aparentar que existe una comparación de acciones canónicas si todavía no se ha ejecutado la ruta de evaluación completa.

`seed` se registra solo cuando intervenga un proceso estocástico. No es un campo obligatorio de la clasificación determinista.

### 5.5 Categorías de diferencia

Como mínimo:

- `classification`: distinta clasificación preflop.
- `status`: resolved frente a unresolved.
- `denominator`: distinto denominador o contexto de consulta.
- `coverage`: cobertura distinta o ausente.
- `table`: distinta tabla o resolución.
- `range`: distinto rango o estado de rango.
- `equity`: distinta estimación o método de equity.
- `ev`: distinta evaluación de EV.
- `action`: distinta recomendación final.
- `provenance`: incompatibilidad o diferencia de procedencia.
- `execution`: una etapa no pudo ejecutarse.

Una misma mano puede tener más de una diferencia. El log debe permitir identificar cada una sin reducirlas a una única categoría genérica.

### 5.6 Política de persistencia

- El log no corrige manos ni modifica el historial.
- No reescribe acciones.
- No alimenta entrenamiento automáticamente.
- No se mezclan resultados de contratos distintos sin identificar sus versiones.
- La telemetría permanece en memoria por defecto.
- La escritura persistente requiere una decisión explícita y un destino separado de `data/`.
- La persistencia debe conservar procedencia suficiente para reproducir la comparación.
- La ausencia de log no puede interpretarse como ausencia de diferencias.

---

## 6. Versionado y compatibilidad de artefactos

No todos los artefactos tienen las mismas dependencias. Por tanto, no se debe imponer `label_schema` como requisito universal a artefactos que no consumen etiquetas de entrenamiento.

### 6.1 Metadatos comunes

Todo artefacto generado debe declarar, como mínimo:

```text
schema_version
code_commit
data_snapshot_hash
source_window
created_at
artifact_type
dependency_manifest
```

### 6.2 Metadatos condicionales

Cuando corresponda:

```text
contract_version
label_schema
coverage_inventory
aliases
range_schema
equity_schema
model_version
generation_parameters
```

- `contract_version` es obligatorio para artefactos cuya generación o interpretación dependa de la clasificación preflop.
- `label_schema` es obligatorio para artefactos entrenados con etiquetas.
- `coverage_inventory` es obligatorio cuando el artefacto representa tablas o cobertura de consultas.
- `range_schema` es obligatorio para artefactos que almacenan rangos.
- `equity_schema` es obligatorio cuando se almacenen resultados de equity.
- `generation_parameters` debe conservar los parámetros que afecten a la reproducción del artefacto.

Los campos condicionales no se sustituyen por valores ficticios para satisfacer un esquema común.

### 6.3 Política de compatibilidad

Consumidores relevantes, entre ellos:

- `ProfileRangeModel.load`
- `PostflopRangeModel`
- `preflop.load_tables`
- entrenamiento de matrices

deben comprobar las dependencias que realmente utilizan.

Reglas:
1. Un artefacto sin metadatos suficientes se identifica como `unknown_contract` o `legacy`, según la evidencia disponible.
2. `legacy` no significa automáticamente compatible con canonical.
3. `unknown_contract` no se interpreta como compatible.
4. La compatibilidad debe declararse mediante una regla explícita y verificable.
5. Un loader puede rechazar el artefacto o cargarlo en un modo de auditoría no utilizable para serving.
6. No se mezclan artefactos de versiones incompatibles sin una transformación declarada y validada.
7. Las versiones de contrato, etiquetas y esquema de artefacto son dimensiones independientes.

No se debe asignar retrospectivamente una versión canónica a un artefacto histórico si no hay evidencia de que fue generado con ese contrato.

---

## 7. Regeneración selectiva y linaje

La base de manos es dinámica. Una sesión nueva o una corrección manual no autoriza regenerar todos los derivados.

### 7.1 Procedimiento

1. Identificar el cambio en la fuente y su alcance.
2. Registrar el hash de la fuente anterior y de la nueva.
3. Identificar qué registros o ventanas fueron afectados.
4. Consultar el manifiesto de dependencias para determinar qué derivados dependen de esos datos.
5. Evaluar si el cambio afecta al contrato, a las etiquetas, a los rangos, a las matrices o a otros artefactos.
6. Proponer la regeneración mínima necesaria.
7. Obtener autorización antes de ejecutar cualquier regeneración.
8. Generar el artefacto con metadatos y manifiesto de dependencias completos.
9. Comparar distribución, cobertura y compatibilidad con la versión anterior.
10. Conservar el artefacto anterior y su identificación para rollback.

### 7.2 Linaje mínimo

Cada derivado debe permitir reconstruir:

```text
artifact_id
artifact_type
artifact_hash
source_snapshot_hash
source_window
code_commit
contract_version
label_schema
dependency_artifacts
generation_parameters
created_at
```

Los campos no aplicables se omiten o se declaran expresamente como no aplicables. No se rellenan con valores inventados.

### 7.3 Restricciones

- No regenerar automáticamente al detectar un hash distinto.
- No modificar ni normalizar automáticamente el historial.
- No asumir que una corrección histórica afecta únicamente a una mano.
- No declarar equivalencia por igualdad de tamaño o nombre de archivo.
- No sustituir un artefacto sin conservar su identidad anterior.
- No propagar una regeneración a todos los consumidores sin comprobar dependencias.
- No declarar una regeneración equivalente sin comparar distribución, cobertura y semántica.

La regeneración debe ser selectiva y explícitamente autorizada.

---

## 8. Rollback

El rollback no consiste únicamente en cambiar un selector de modo. Debe recuperar un conjunto coherente de código, configuración, artefactos y dependencias.

### 8.1 Rollback de serving

Procedimiento conceptual:

1. Desactivar la ruta canónica mediante una configuración identificable.
2. Seleccionar el adaptador y pipeline legacy previamente registrados.
3. Restaurar las referencias a artefactos compatibles con esa ruta.
4. Verificar hashes y versiones de los artefactos cargados.
5. Ejecutar fixtures de referencia sobre la ruta recuperada.
6. Comparar las recomendaciones con la referencia legacy previa.
7. Registrar el resultado y cualquier diferencia.
8. Confirmar que la ruta canónica ya no tiene autoridad sobre la recomendación.

No se declara rollback exitoso solo porque `PreflopRouter.mode=legacy`.

### 8.2 Rollback de artefactos

- Restaurar el artefacto anterior identificado por hash.
- Comprobar que corresponde al código y contrato esperados.
- Verificar sus dependencias.
- No mezclar artefactos de snapshots distintos sin compatibilidad demostrada.
- No reconstruir un artefacto anterior a partir de datos actuales y llamarlo rollback.
- Si el artefacto anterior no existe o no puede verificarse, declarar `rollback_unavailable`.

### 8.3 Rollback de entrenamiento

- Conservar el modelo anterior y su artefacto identificable.
- Restaurar el esquema de etiquetas compatible con ese modelo.
- Verificar que el consumidor vuelve a interpretar las etiquetas como antes.
- No sustituir un modelo histórico por uno reentrenado con etiquetas nuevas aunque su nombre sea igual.

### 8.4 Criterios de activación

Debe detenerse la promoción o ejecutarse rollback cuando ocurra cualquiera de estas condiciones:

- Falla una fixture contractual obligatoria.
- Aparece una diferencia de comportamiento no explicada.
- Se utiliza una tabla o artefacto incompatible.
- La cobertura empeora respecto de la referencia sin una justificación y aprobación explícitas.
- La procedencia o el snapshot del artefacto no coinciden con lo declarado.
- La ruta canónica produce una recomendación cuando alguna etapa obligatoria está unresolved o unsupported.
- Se incumple el presupuesto operativo de forma que compromete la decisión.
- La evaluación estratégica held-out supera el umbral de degradación definido antes de la prueba.

**Distinción importante:** una fixture obligatoria fallida impide avanzar y puede exigir desactivar la ruta candidata. No significa necesariamente que deba revertirse una ruta legacy que nunca dejó de ser autoridad.

Los umbrales estratégicos no se inventan en este documento. Deben quedar definidos en el plan de validación antes de ejecutar la evaluación y antes de autorizar serving.

---

## 9. Prohibiciones y límites de esta fase

Durante el trabajo documental y las fases de diseño:

- No cambiar `_preflop_spot`, `_preflop_raises` ni `_recom_preflop`.
- No cambiar `first_decision` o `table_plan` para hacer coincidir artificialmente sus resultados con live.
- No cambiar `MULTIWAY_SOPORTADO`.
- No escribir en `data/`.
- No regenerar matrices, `profile_ranges`, `postflop_ranges`, `behavior` ni otros artefactos.
- No activar el contrato canónico en serving.
- No modificar automáticamente etiquetas ni registros históricos.
- No convertir unresolved, unknown o unsupported en categorías o acciones ordinarias.
- No declarar que la estrategia ha mejorado por pasar fixtures o reproducir etiquetas.
- No confundir paridad mecánica, cobertura estadística y validación estratégica.
- No ejecutar writers reales como parte de esta migración documental.
- No reabrir ni ampliar la auditoría F0 como requisito para este trabajo read-only.

La migración HU no autoriza cambios de arquitectura multiway ni su activación.

---

## 10. Entregables y criterios de aceptación

Antes de implementar:

1. Especificación canónica de `PreflopDecision` aprobada.
2. Política de cobertura e incertidumbre aprobada.
3. Escenarios HU de referencia aprobados.
4. Contrato de etiquetas y mapeos legacy documentados.
5. Inventario de consumidores y dependencias actualizado.
6. Versionado de artefactos definido por tipo.
7. Plan de rollback verificable.
8. Puertas de aceptación mecánicas, estadísticas y estratégicas definidas.

Antes de promover a serving:

1. Paridad contractual aprobada.
2. Diferencias legacy/canonical explicadas.
3. Cobertura y estados de incertidumbre auditados.
4. Artefactos compatibles y trazables.
5. Evaluación estratégica held-out aprobada.
6. Rendimiento dentro del presupuesto.
7. Rollback probado sobre código, configuración y artefactos.
8. Autorización explícita del cambio de modo.

**Un resultado positivo en una dimensión no sustituye la aprobación de las demás.**

---

## 11. Estado final esperado

Al completar la migración:

- Existe una única fuente canónica de clasificación preflop.
- Live y entrenamiento consumen el contrato mediante adaptadores explícitos.
- Legacy permanece identificable y reproducible durante la ventana de rollback.
- Las tablas y artefactos declaran las dependencias necesarias.
- La cobertura y la incertidumbre se propagan sin degradaciones silenciosas.
- La ruta canónica solo recomienda cuando todas las etapas necesarias han producido resultados válidos.
- El rollback recupera una combinación coherente de código, configuración y artefactos.
- Las correcciones manuales de datos siguen bajo control explícito.
- `MULTIWAY_SOPORTADO` permanece `False`.

**La migración se considera completada únicamente cuando la ruta canónica ha superado las validaciones y puertas de aprobación, no cuando el adaptador o sus fixtures están implementados.**