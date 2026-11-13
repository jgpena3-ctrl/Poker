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
7. Confirmar que `MULTIWAY_SOPORTADO=False` y que no se busca una acción MW.

Si falta una aprobación, no se empieza el paso siguiente.

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
  └── PR-01 contrato canónico puro
        ├── PR-02 resolvedor de cobertura
        │     └── PR-03 adaptador de entrenamiento
        │           └── PR-04 manifiesto de artefactos
        ├── PR-05 sombra preflop (sin acción)
        │     └── PR-06 router legacy/shadow
        │           └── PR-07 canonical detrás de bandera
        └── PR-08 contratos rango/equity/EV
              └── PR-09 MW sombra (FieldState/VillainBelief)
                    └── PR-10 JointSampler/FieldEquity
                          └── PR-11 FieldResponse/EV
```

## 4. Pasos

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

### PR-04 — Manifiesto de artefactos

**Alcance**

- Metadatos `contract_version`, `label_schema`, `code_commit`,
  `data_snapshot_hash`, `coverage_inventory`.
- Lectura que rechaza o marca artefactos sin versión.

**Tests**

- MIG-001…MIG-008; ART-001…ART-003.
- Un artefacto legacy no se mezcla con canónico.

**Criterio de salida**

- Ningún consumidor asume compatibilidad por nombre de archivo.

**Rollback**

- El manifiesto es aditivo; se puede ignorar y volver al loader anterior.

### PR-05 — Sombra preflop

**Alcance**

- Calcular `PreflopDecision` en paralelo a legacy.
- Log de diferencias en memoria.
- No cambia la acción.

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
  `CurrentEquity`, `ShowdownEquity`, `EvByAction`.
- Cálculo HU con method/seed/CI.
- Sin integración live.

**Tests**

- RNG-001…RNG-007; EQ-001…EQ-008; EV-001…EV-008.
- Exacto vs MC dentro del CI.
- Rango vacío → `unknown`.

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
- `tree_depth`, `n`, seed y CI.
- Sin activación live.

**Tests**

- MW-012, MW-014; EV multiway.
- EV sin respuesta inválido.
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

**No se ejecuta en este plan.** No se activa `canonical` ni MW solo por este
documento.

## 5. Hitos

| Hito | Contenido | Condición |
|---|---|---|
| H0 | Diseño aprobado | 8 docs revisados |
| H1 | Contrato zócalo | PR-01/02 verdes |
| H2 | Sombra preflop | PR-03…PR-06; acción intacta |
| H3 | HU rango/equity/EV | PR-08; sin live |
| H4 | MW sombra | PR-09…PR-11; sin recomendación |
| H5 | Evaluación | dataset y test no visto |
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

La fase de diseño termina cuando los 8 documentos están revisados y aprobados.
La fase de implementación empieza solo con PR-01, no con una activación.
