# Migración y rollback del contrato preflop (2026-11-13)

**Estado:** diseño. No cambia la ruta live, no modifica `motor/`, no escribe
`data/` y no activa artefactos.

**Objetivo:** migrar live y entrenamiento a `PreflopDecision` sin mezclar
contratos y con rollback verificable.

**Base actual:**

- `motor/preflop_contract.py` contiene el contrato estricto y el modo
  `legacy=True`.
- `motor/asistente_live.py` usa `_preflop_spot`/`_preflop_raises` para decidir
  y `first_decision`/`table_plan` solo para sombra.
- `motor/learn.py::preflop_events` conserva etiquetas legacy.
- `ShadowPreflopLog` ya permite comparar viejo/nuevo sin escribir por defecto.

## 1. Principios de migración

1. **Primero sombra, después serving.** Ningún cambio de acción en live hasta
   que la sombra y la validación HU estén aprobadas.
2. **Un solo contrato.** La etiqueta canónica no se reimplementa en cada
   consumidor.
3. **Legacy explícito.** La lectura vieja se conserva detrás de un adaptador
   nombrado; no se borra antes de la ventana de rollback.
4. **Artefactos versionados.** Un modelo o tabla declara con qué contrato se
   generó. Un consumidor no mezcla versiones en silencio.
5. **Logs sin datos.** La telemetría de diferencias no es una fuente de datos
   de entrenamiento ni una corrección automática.

## 2. Tres adaptadores

```
                 ┌────────────────────────────┐
acciones ───────▶│ CanonicalPreflopAdapter    │──▶ PreflopDecision
                 └────────────────────────────┘
                 ┌────────────────────────────┐
acciones ───────▶│ LegacyPreflopAdapter       │──▶ spot/action/n_raises
                 └────────────────────────────┘
                 ┌────────────────────────────┐
decision ───────▶│ TrainingLabelAdapter       │──▶ label_schema
                 └────────────────────────────┘
```

### 2.1 `CanonicalPreflopAdapter`

- Entrada: mano/fuente de acciones + `hero_pos` + versión de contrato.
- Salida: `PreflopDecision`.
- Debe ser puro: no lee modelos, no consulta tablas, no decide.
- La consulta de tablas y cobertura se hace en un resolvedor separado.

### 2.2 `LegacyPreflopAdapter`

- Reproduce exactamente `_preflop_spot`, `_preflop_raises` y el limp histórico
  que usa live.
- Se usa para comparación y rollback.
- No se mejora ni se corrige: si se toca, deja de ser legacy.
- Se etiqueta `legacy` en logs y salidas.

### 2.3 `TrainingLabelAdapter`

- Entrada: `PreflopDecision`.
- Salida: etiqueta para el modelo, según `label_schema`.
- Si el modelo no soporta una categoría, el mapeo es explícito y lossy; no se
  disfraza.
- `training_category` actual (`5bet→4bet`, etc.) queda como contrato de
  compatibilidad, no como categoría canónica.

## 3. Fases de migración

### Fase 0 — Congelar especificación

- Aprobar `PreflopDecision`, cobertura y escenarios.
- No tocar serving.

**Salida:** documentos y fixtures de referencia.

### Fase 1 — Contrato en sombra

- Añadir el adaptador canónico y el resolvedor de cobertura.
- Live sigue con legacy.
- Cada decisión preflop calcula también el canónico y registra diferencias.
- No se usa el canónico para recomendar.

**Validación:** paridad de fixtures; diferencias clasificadas; cero cambios de
acción.

### Fase 2 — Entrenamiento en sombra

- Entrenamiento genera etiquetas canónicas y legacy en paralelo.
- No se reemplaza el modelo.
- Se registra `label_schema` y `contract_version` en el artefacto.

**Validación:** comparar distribuciones y matriz de confusión; no declarar
mejora sin evaluación temporal.

### Fase 3 — Serving canónico con rollback

- Un router de configuración elige `legacy` o `canonical`.
- El valor por defecto sigue `legacy`.
- Solo tras aprobación se cambia el default.
- El canónico usa `decision_plan` y `range_query` según corresponda.
- La acción no se elige con una tabla de cobertura insuficiente.

**Validación:** cada decisión registra adaptador, contrato, tabla, cobertura,
semilla y versión. Rollback a legacy probado.

### Fase 4 — Retirada del legacy

- Solo después de una ventana sin regresiones y con evidencia.
- El adaptador legacy puede quedar como herramienta de auditoría, no como ruta
  de serving.
- No se borran logs ni fixtures de comparación.

## 4. Router de serving

Concepto:

```
PreflopRouter:
  mode: legacy | shadow | canonical
  canonical_adapter
  legacy_adapter
  coverage_resolver
  decision_sink

  decide(state):
    legacy = legacy_adapter.decide(state)
    if mode == legacy:
      return legacy
    canonical = canonical_adapter.build(state)
    if mode == shadow:
      log_compare(legacy, canonical)
      return legacy
    if canonical.status != resolved:
      return unsupported(canonical)
    if canonical.coverage blocks decision:
      return unsupported(canonical)
    return canonical
```

Reglas:

- `shadow` no cambia la acción.
- `canonical` no cae a legacy en silencio; si no puede decidir, devuelve
  `unsupported` con motivo.
- Un `unsupported` no es un fold; no se inventa una acción.
- El router no escribe en `data/`; si hay log, es telemetría declarada.

## 5. Log de diferencias

Cada comparación registra:

```
hand_id
hero_pos
source
contract_version
legacy_spot
legacy_action
legacy_n_raises
legacy_limps
canonical_status
canonical_category
canonical_denom
canonical_decision_plan
canonical_range_query
canonical_coverage
difference_kind              # classification | table | action | coverage
table_chosen_legacy
table_chosen_canonical
action_legacy
action_canonical
seed
model_version
data_snapshot
timestamp
```

Reglas:

- El log no corrige la mano ni reescribe acciones.
- Una diferencia de acción se registra, no se “arregla” automáticamente.
- No se mezclan logs de contratos distintos sin `contract_version`.
- El log por defecto va a memoria; escribir un archivo es una decisión
  explícita del operador.

## 6. Metadatos de artefactos

Todo artefacto generado por el pipeline debe declarar:

```
schema_version
contract_version
label_schema
code_commit
data_snapshot_hash
source_window
created_at
coverage_inventory
aliases
```

Consumidores:

- `ProfileRangeModel.load`
- `PostflopRangeModel`
- `preflop.load_tables`
- entrenamiento de matrices

Si un artefacto no declara `contract_version` o `label_schema`, se trata como
legacy y no se mezcla con canónico. El loader puede rechazar o marcar
`unknown_contract`; nunca asumir compatibilidad.

## 7. Regeneración selectiva

La base es dinámica. Una corrección manual o una sesión nueva no regenera todo
automáticamente.

Regla:

1. Se identifica la ventana afectada.
2. Se calcula el hash de la nueva fuente.
3. Se decide qué derivados dependen de esa ventana.
4. Se regenera solo lo afectado, con nuevo `data_snapshot_hash` y
   `created_at`.
5. Se conserva el artefacto anterior y su hash para rollback.
6. Se anota la dependencia en el manifiesto.

No se declara una regeneración “equivalente” sin comparar distribuciones y
cobertura.

## 8. Rollback

### 8.1 Rollback de serving

- `PreflopRouter.mode=legacy`.
- El artefacto anterior se conserva y se carga por hash.
- No se borran logs.
- Se verifica que la acción vuelve al comportamiento previo en una muestra
  de fixtures.

### 8.2 Rollback de artefactos

- Restaurar el archivo anterior por hash.
- Revalidar que el `contract_version` coincide.
- No mezclar artefactos de ventanas distintas.
- Si el artefacto anterior no existe, no se inventa: se declara
  `rollback_unavailable`.

### 8.3 Criterio de rollback

Se activa si:

- una fixture de contrato falla;
- una acción cambia sin diferencia explicada;
- la cobertura empeora de forma no declarada;
- el artefacto no coincide con el snapshot;
- el rendimiento estratégico held-out se degrada más allá del umbral
  predefinido.

## 9. Prohibiciones de esta fase

- No cambiar `_preflop_spot`, `_preflop_raises` ni `_recom_preflop`.
- No cambiar `first_decision`/`table_plan` para “cuadrar” live.
- No cambiar `MULTIWAY_SOPORTADO`.
- No escribir en `data/`.
- No regenerar matrices, `profile_ranges`, `postflop_ranges` ni `behavior`.
- No declarar migración completada por pasar fixtures.
