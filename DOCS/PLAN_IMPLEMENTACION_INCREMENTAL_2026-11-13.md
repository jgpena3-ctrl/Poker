# Plan de implementación incremental (2026-11-13)

**Estado:** diseño. Este documento **no implementa** nada. No modifica
`motor/`, no escribe `data/`, no regenera artefactos, no activa `canonical` y
no activa multiway.

**Objetivo:** ordenar la implementación futura en pasos pequeños, reversibles
y verificables, con la ruta actual intacta hasta la aprobación explícita.

## 1. Condiciones de entrada

Antes de escribir código:

1. Aprobar `ESPECIFICACION_CONTRATO_PREFLOP_2026-11-13.md`.
2. Aprobar `POLITICA_COBERTURA_INCERTIDUMBRE_2026-11-13.md`.
3. Aprobar `ESCENARIOS_REFERENCIA_HU_2026-11-13.md`.
4. Aprobar `CONTRATOS_RANGO_EQUITY_EV_2026-11-13.md`.
5. Aprobar `DISENO_TECNICO_MW_INTERFACES_2026-11-13.md`.
6. Aprobar `MATRIZ_PRUEBAS_ACEPTACION_2026-11-13.md`.
7. Aprobar `MIGRACION_ROLLBACK_PREFLOP_2026-11-13.md`.
8. Confirmar que `MULTIWAY_SOPORTADO=False` y que no se busca una acción MW.

La aprobación del plan de implementación no sustituye la aprobación del diseño
de migración y rollback. Si falta una aprobación, no se empieza el paso
siguiente.

## 2. Reglas de ejecución

- Un PR = una preocupación. No mezclar contrato, cobertura, serving y MW.
- Cada PR debe ser reversible con una bandera o un revert.
- Ningún PR de esta fase cambia la acción por defecto.
- Ningún PR escribe en `data/` salvo un PR explícito de artefactos, que no
  forma parte de la activación.
- Los tests puros van antes del adaptador de serving.
- Un test verde no autoriza activación.
- No se “cuadra” legacy para que coincida con el contrato.

## 3. Dependencias

```
DOCs aprobados
  └── PR-00 compatibilidad read-only
        └── PR-01 contrato canónico puro
              ├── PR-02 resolvedor de cobertura
              │     └── PR-03 adaptador de entrenamiento
              │           └── PR-04 compatibilidad de artefactos
              ├── PR-05 sombra preflop (sin acción)
              │     └── PR-06 router legacy/shadow
              │           └── PR-07 canonical detrás de bandera
              └── PR-08 contratos rango/equity/EV
                    └── PR-09 MW sombra (FieldState/VillainBelief)
                          └── PR-10 JointSampler/FieldEquity
                                └── PR-11 FieldResponse/EV
```

PR-03/PR-04 y PR-05/PR-06 son ramas parcialmente independientes. No se fuerza
una dependencia artificial entre ellas; solo comparten PR-01 como base
común. PR-08 depende de los contratos y de la política de cobertura ya
aprobados. PR-09…PR-11 dependen obligatoriamente de PR-08.

## 4. Pasos

### PR-00 — Compatibilidad read-only

**Alcance**

- Contrastar los documentos aprobados con el código, las estructuras y las
  fuentes reales del repositorio.
- Correspondencia entre los campos del contrato y los datos que realmente
  existen.
- Fuentes de cada campo: acciones, importes, posiciones, ciegas, botón y orden
  de asientos.
- Campos que no pueden obtenerse con certeza.
- Incompatibilidades entre el contrato propuesto y las estructuras actuales.
- Casos que requieren `unknown`, `unresolved` o abstención.
- Impacto sobre los consumidores existentes.
- Especialmente `amount`, contribuciones acumuladas, posts, straddles y orden
  de acción.

**No alcance**

- No implementa nada.
- No corrige código.
- No adapta datos.
- No escribe en `motor/` ni en `data/`.

**Tests / evidencia**

- Informe de compatibilidad read-only.
- Lista de campos no reconstruibles.
- Casos de abstención documentados.
- Commit de referencia.
- Estado de Git.
- Hashes de los documentos y datos examinados.
- No asumir que los hashes históricos siguen vigentes.

**Criterio de salida**

- Existe un informe que identifica qué partes del contrato son implementables
  con la evidencia disponible y cuáles requieren `unknown`/`unresolved`.
- No se ha modificado código ni datos.

**Rollback**

- No aplica: no hay cambios.

### PR-01 — Contrato canónico puro

**Alcance**

- `PreflopDecision` y tipos asociados.
- `classify_decisions` puro, sin tablas.
- Serialización estable y `schema_version`.
- No toca serving.

**Tests**

- PRE-001…PRE-015; AMB-001…AMB-007.
- Invariantes de índices, raises/limps/callers.

**Criterio de salida**

- 100 % de fixtures de contrato.
- Cero imports de serving/modelos en el módulo de contrato.

**Rollback**

- Revert del PR; no hay ruta que lo use.

### PR-02 — Resolvedor de cobertura

**Estado (2026-11-14):** cerrado, con PR-02B.4 aprobado. Ver
`DOCS/CIERRE_PR_02B_2026-11-14.md`. PR-03 no iniciado.

**Alcance**

- `CoverageState` y resolución de alias/gap/impossible/unknown.
- Separación `decision_plan` / `range_query`.
- No toca serving.

**Tests**

- COV-001…COV-008; L01–L05.
- `impossible` vs `gap` vs `unknown` distinguidos.

**Criterio de salida**

- Toda consulta devuelve estado y razón.
- `fallback_other_vs` no se etiqueta exacto.

**Rollback**

- Revert; el contrato puro sigue sin consumidores.

### PR-03 — Adaptador de entrenamiento

**Alcance**

- Etiquetas canónicas y `label_schema`.
- Mapeo explícito de categorías no soportadas.
- No entrena ni regenera artefactos.

**Tests**

- Matriz de etiquetas; `5bet`/`6bet_plus` no se disfrazan.
- `coverage_gap` excluido; no `0`.

**Criterio de salida**

- Misma mano produce etiqueta determinista.
- `label_schema` visible en la salida.

**Rollback**

- Volver al adaptador anterior; no hay artefacto nuevo.

### PR-04 — Compatibilidad de artefactos

**Alcance**

- Lectura y validación de metadatos: `contract_version`, `label_schema`,
  `code_commit`, `data_snapshot_hash`, `coverage_inventory`.
- Identificar versiones, detectar incompatibilidades y rechazar o marcar
  artefactos desconocidos.
- Lectura que rechaza o marca artefactos sin versión como `unknown_contract`.
- No modifica artefactos existentes ni escribe en `data/`.

**No alcance**

- Creación o modificación de manifiestos/sidecars.
- Regeneración de artefactos.
- Escritura en `data/`.

Si se necesita escribir o modificar un manifiesto, eso requiere una
autorización y un PR específico posterior.

**Tests**

- MIG-001…MIG-008; ART-001…ART-003.
- Un artefacto legacy no se mezcla con canónico.
- Un artefacto sin versión verificable queda `unknown_contract`.

**Criterio de salida**

- Ningún consumidor asume compatibilidad por nombre de archivo.
- Ningún artefacto existente fue modificado.

**Rollback**

- La lectura de compatibilidad es aditiva; se puede ignorar y volver al
  loader anterior.

### PR-05 — Sombra preflop

**Alcance**

- Calcular `PreflopDecision` en paralelo a legacy.
- Log de diferencias en memoria.
- No cambia la acción.

**Restricciones de sombra**

- El registro de diferencias es temporal, acotado y no persistente por
  defecto.
- No alimenta entrenamiento.
- No escribe en `hands_db.jsonl`.

**Tests**

- SHW-001…SHW-006; SCN-001…SCN-007.
- La acción live se mantiene idéntica.

**Criterio de salida**

- Cero cambios de acción en la muestra de regresión.
- Diferencias clasificadas.

**Rollback**

- Desactivar la sombra; legacy sigue.

### PR-06 — Router legacy/shadow

**Alcance**

- `PreflopRouter` con `legacy`, `shadow`, `canonical`.
- Default `legacy`.
- `shadow` no cambia acción.

**Tests**

- MIG-003…MIG-005; REG-001…REG-004.
- Rollback de serving.

**Criterio de salida**

- `legacy` y `shadow` reproducen la acción previa.
- `canonical` no cae a legacy en silencio.

**Rollback**

- `mode=legacy` o revert del router.

### PR-07 — Canonical detrás de bandera

**Alcance**

- `canonical` solo con bandera explícita y cobertura suficiente.
- `unsupported` con motivo; no fold.
- La bandera no se activa en este plan.

**Restricciones de bandera**

- La bandera permanece desactivada por defecto.
- No puede habilitarse accidentalmente mediante configuración ordinaria.
- El código puede existir y probarse en condiciones controladas, pero no debe
  cambiar la ruta efectiva de decisiones.

**Tests**

- MIG-005; SHW-005; fixtures de cobertura.
- `unsupported` no es una acción.

**Criterio de salida**

- El default sigue `legacy`.
- No hay cambio de UI ni de recomendación.

**Rollback**

- Bajar la bandera; no se borra el código.

### PR-08 — Contratos de rango/equity/EV

**Alcance**

- Tipos `ObservedRange`, `EstimatedRange`, `GenericPrior`,
  `CurrentBoardStrength`, `EquityToShowdown`, `EvByAction`.
- `EquityToShowdown` es el tipo canónico para la probabilidad de ganar, empatar
  o perder hasta showdown. `ShowdownEquity` no es un tipo independiente; solo
  designa una realización de `EquityToShowdown` con un método concreto.
- Cálculo HU con método declarado; seed e intervalo de confianza solo cuando
  el método de cálculo los requiera.
- Sin integración live.

**Nomenclatura y métodos**

- `CurrentBoardStrength`: evaluación de la fuerza de la mano en el board
  actual.
- `EquityToShowdown`: probabilidad de ganar, empatar o perder considerando
  runouts hasta showdown.
- `ShowdownEquity` solo se usa si el contrato la define explícitamente como
  estimación de esa equity mediante un método determinado; no se confunde con
  la fuerza actual del board.
- Enumeración exacta: método, espacio evaluado y número de combinaciones; no
  necesita seed ni intervalo de confianza de muestreo.
- Monte Carlo: método, muestras, seed e intervalo de confianza.
- Rango vacío: debe llevar una razón explícita (`no_range`,
  `unsupported`, `empty_after_filter`, `blockers_exhausted`, `parse_error`,
  etc.). No basta con `unknown`.

**Tests**

- RNG-001…RNG-007; EQ-001…EQ-008; EV-001…EV-008.
- Exacto vs MC dentro del CI.
- Rango vacío con razón explícita.

**Criterio de salida**

- Ningún `0.0` por ausencia.
- `current` y `showdown` separados.

**Rollback**

- Revert; no hay consumidor live.

### PR-09 — MW sombra: `FieldState`/`VillainBelief`

**Alcance**

- Construir `FieldState` y `MultiwayRangeSet` por rival.
- No usar `union()` como campo.
- No recomendar.

**Distinción de elegibilidad**

- Distinguir jugadores que pueden actuar de jugadores que siguen siendo
  elegibles para el bote.
- Un jugador all-in no puede actuar, pero continúa participando en los botes
  a los que tiene derecho.

**Tests**

- MW-001, MW-002, MW-007, MW-010.
- Creencias separadas y cobertura por rival.

**Criterio de salida**

- `MULTIWAY_SOPORTADO=False`.
- UI sin cambios.

**Rollback**

- Desactivar el cálculo sombra; no hay ruta de acción.

### PR-10 — `JointSampler`/`FieldEquity`

**Alcance**

- Muestreo conjunto con blockers, rechazos y diagnóstico.
- Independencia como baseline etiquetado.
- Side pots, ties y all-ins.

**Requisitos formales del muestreo**

- Declarar distribución objetivo y distribución propuesta.
- Aportar evidencia de que el estimador corresponde a la distribución objetivo
  declarada.
- Establecer antes de evaluar resultados los criterios de rechazo e
  insuficiencia estadística.
- Declarar política de muestreo: independencia, correlación o
  condicionamiento.
- Definir tratamiento de colisiones y normalización.
- Declarar pesos de las muestras, si corresponden.
- Calcular ESS (tamaño efectivo de muestra).
- Reportar tasa de rechazo y criterios para declarar el resultado no fiable.
- Definir comportamiento cuando no se puede obtener una distribución conjunta
  válida.
- La independencia es un baseline etiquetado, no una verdad sobre los rivales.
- `RangeState.union()` sigue prohibido como sustituto de una distribución
  conjunta.

**Tests**

- MW-003…MW-006, MW-008, MW-009, MW-011, MW-013.
- Rechazos visibles; mismo seed → mismo resultado.

**Criterio de salida**

- No hay equity MW por unión.
- `coverage_by_player` y `rejection_rate` visibles.

**Rollback**

- Revert; sigue sin recomendación.

### PR-11 — `FieldResponse`/`MultiwayActionEV`

**Alcance**

- Respuesta por rival y EV por acción.
- `tree_depth`, `n`, seed y CI cuando el método lo requiera.
- Sin activación live.

**Criterio de EV**

- Toda rama de EV debe modelar las respuestas necesarias para esa acción.
- Las acciones sin respuesta posterior necesaria (por ejemplo, fold en el nodo
  actual) no deben rechazarse por carecer de un modelo de respuesta.
- Si una rama requiere respuestas y no hay modelo válido, su EV será
  `unsupported` o no disponible; nunca se sustituirá por cero.
- `tree_depth`, `n`, seed e intervalo de confianza no son obligatorios
  indiscriminadamente: el método exacto y el método de muestreo tienen
  requisitos distintos.

**Tests**

- MW-012, MW-014; EV multiway.
- `unsupported` no es fold.

**Criterio de salida**

- Reporte sombra, no recomendación.
- `MULTIWAY_SOPORTADO=False`.

**Rollback**

- Desactivar el reporte; no hay acción MW.

### PR-12 — Evaluación y activación (fuera de esta fase)

**Alcance**

- Dataset de evaluación congelado.
- Curvas, CI y EV held-out.
- Decisión de activación separada.

**Requisitos del dataset**

- SHA-256 del snapshot.
- Versión del dataset.
- Identificación de manos y sesiones.
- Separación verificable entre entrenamiento y evaluación.
- Registro de exclusiones y duplicados.
- Invalidación de resultados cuando cambie la fuente de datos.

**Restricciones**

- La evaluación estratégica requiere aprobación propia.
- Dataset congelado y separado por sesiones o manos para evitar contaminación
  entre entrenamiento y evaluación.
- Pasar tests mecánicos o estadísticos no autoriza activación.

**No se ejecuta en este plan.** No se activa `canonical` ni MW solo por este
documento.

## 5. Hitos

| Hito | Contenido | Condición |
|---|---|---|
| H0 | Diseño aprobado | documentos de diseño revisados, incluida migración/rollback |
| H1 | Contrato zócalo | PR-01/02 verdes |
| H2 | Sombra preflop | PR-03…PR-06; acción intacta. PR-03/04 y PR-05/06 son ramas parcialmente independientes; no se fuerza dependencia artificial entre ellas |
| H3 | HU rango/equity/EV | PR-08; sin live; respeta contratos y cobertura aprobados |
| H4 | MW sombra | PR-09…PR-11; sin recomendación; dependencia obligatoria de PR-08 |
| H5 | Preparación de evaluación | dataset y test no visto; no se ejecuta validación estratégica ni se declara aptitud para serving |
| H6 | Activación | aprobación separada |

## 6. Criterios de “no implementado”

Este plan no se considera ejecutado si:

- se modificó `motor/` antes de la aprobación;
- se escribió en `data/`;
- `MULTIWAY_SOPORTADO` cambió;
- la acción live cambió;
- se declaró mejora sin held-out;
- se usó `union()` como equity MW;
- se convirtió un `gap` en cero o fold.

## 7. Evidencia por PR

Cada PR debe adjuntar:

- alcance y no-alcance;
- fixtures/tests;
- salida de tests;
- diff de acciones en sombra (si aplica);
- cobertura por estado;
- rollback probado;
- confirmación de `data/` sin cambios.

## 8. Definición de terminado

La fase de diseño termina cuando los documentos de diseño están revisados y
aprobados, incluida migración y rollback. La fase de implementación empieza
solo con PR-00, no con una activación.