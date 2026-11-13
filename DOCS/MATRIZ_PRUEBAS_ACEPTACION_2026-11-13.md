# Matriz de pruebas y aceptación (2026-11-13)

**Estado:** diseño. No implementa tests, no modifica `motor/`, no escribe
`data/` y no valida una versión nueva.

**Objetivo:** convertir el contrato y los escenarios en criterios verificables
para aceptar o rechazar la migración, sin confundir “pasa tests” con “mejora
la estrategia”.

## 1. Capas de prueba

```
contrato puro
  └── escenarios reales/sintéticos
        └── cobertura
              └── rango/equity/EV
                    └── MW (sombra)
                          └── migración/artefactos
                                └── shadow/live (sin activar)
```

Cada capa es independiente. Un fallo de contrato bloquea las siguientes.

## 2. Matriz

### 2.1 Contrato preflop

| ID | Fixture | Esperado | Nivel |
|---|---|---|---|
| PRE-001 | R01–R17 | estado/categoría/plan/range esperados | contrato |
| PRE-002 | `UTG b 2.5` | `open`, `raises=1`, agresor UTG | unitario |
| PRE-003 | `MP b 1.0` | `limp`, `short_limp=True`, no agresor | unitario |
| PRE-004 | `UTG c`, `MP f` | `fold`; no `fold_vs_open` | unitario |
| PRE-005 | open + call, `BB r` | `squeeze`; no `3bet` | unitario |
| PRE-006 | limp, `SB r` | `rol`; no `open` | unitario |
| PRE-007 | open + 3bet, `CO r` | `4bet`; raises=3 | unitario |
| PRE-008 | 3bet, `BTN c` | `call_4bet`; plan 5B/Call_4B | unitario |
| PRE-009 | 5bet, hero `BTN r` | `5bet`; plan 5B/Call_4B | unitario |
| PRE-010 | 6bet, hero `BB r` | `6bet_plus`; plan unsupported | unitario |
| PRE-011 | `BB x` sin raise | `bb_check`; `no_range` | unitario |
| PRE-012 | `BTN x` | `check_non_bb`; sin plan | unitario |
| PRE-013 | `BB x` con raise | `check_bb_facing_raise`; sin plan | unitario |
| PRE-014 | `p` inicial | `non_decision`, no `limp` | unitario |
| PRE-015 | `BB p`, `BB p` | `posta_repetida`; sin plan | unitario |

### 2.2 Ambigüedad

| ID | Entrada | Esperado |
|---|---|---|
| AMB-001 | importe ausente | `importe_ausente`; sin plan |
| AMB-002 | importe `0` | `importe_cero`; sin plan |
| AMB-003 | acción desconocida | `accion_desconocida`; sin plan |
| AMB-004 | posición `''` | `pos_ausente`; sin plan |
| AMB-005 | raise ≤ nivel | `subida_sin_incremento`; sin plan |
| AMB-006 | secuencia tainted | estado `unresolved`; no se hereda categoría |
| AMB-007 | sin primera decisión | `sin_decision`; no se inventa |

### 2.3 Cobertura

| ID | Consulta | Esperado |
|---|---|---|
| COV-001 | clave exacta | `exact`, `source_key` |
| COV-002 | `4B UTG vs MP` | `alias` a `4B_UTG_vs_HJ` |
| COV-003 | `Call_OR MP vs UTG` | `coverage_gap` |
| COV-004 | `OR BB` | `impossible`; no `gap` |
| COV-005 | `4B BTN vs CO` | `coverage_gap` + `fallback_other_vs`; no `exact` |
| COV-006 | acción sin posición | `unknown`; no `gap` |
| COV-007 | lookup con alias | `alias_of` visible |
| COV-008 | celda gap en entrenamiento | excluida/marcada; no `0` |

### 2.4 Escenarios de referencia

| ID | Fixture | Esperado |
|---|---|---|
| SCN-001 | R01–R14 | estado resuelto y planes esperados |
| SCN-002 | R15–R17 | sin plan canónico; `unknown` |
| SCN-003 | R02/R04/R07 | `Call_OR` gap, no usada como exacta |
| SCN-004 | R11/R12 | `gap` sin fallback vs `gap` con fallback distinguidos |
| SCN-005 | S01–S07 | sin categoría inventada |
| SCN-006 | S08–S13 | niveles, límites y unsupported correctos |
| SCN-007 | L01–L05 | alias/impossible/gap/fallback/unknown |

### 2.5 Rango y prior

| ID | Caso | Esperado |
|---|---|---|
| RNG-001 | rango vacío | `empty=True`, `empty_reason` |
| RNG-002 | rango vacío → equity | `unknown`; no `0.0` |
| RNG-003 | prior plano | `source_kind=prior`; no observación |
| RNG-004 | `prob_vec` vacío | no normaliza, no divide por cero |
| RNG-005 | blockers eliminan combos | masa baja; no se inventa |
| RNG-006 | `fallback_other_vs` | etiqueta de aproximación |
| RNG-007 | `n_eff` | no se reporta como `n` observado |

### 2.6 Equity

| ID | Caso | Esperado |
|---|---|---|
| EQ-001 | board actual | `CurrentEquity`; sin runouts futuros |
| EQ-002 | runout futuro | `ShowdownEquity`; `n_runouts` |
| EQ-003 | exacto vs MC | diferencia dentro del CI |
| EQ-004 | mismo seed | mismo resultado |
| EQ-005 | empate | `tie` separado; se reparte |
| EQ-006 | board/dead cards | entradas explícitas |
| EQ-007 | rango vacío | `unknown`; no 0 |
| EQ-008 | `current` vs `showdown` | no se mezclan |

### 2.7 EV

| ID | Caso | Esperado |
|---|---|---|
| EV-001 | fold | valor de nodo declarado |
| EV-002 | call | equity + bote |
| EV-003 | raise sin respuesta | inválido; no EV |
| EV-004 | raise con respuesta | `FieldResponse` declarado |
| EV-005 | árbol truncado | `tree_depth` visible |
| EV-006 | cobertura gap | no se compara con exact sin etiqueta |
| EV-007 | una muestra | no se acepta como decisión |
| EV-008 | mismo seed | mismo EV/CI |

### 2.8 Multiway

| ID | Caso | Esperado |
|---|---|---|
| MW-001 | `union()` como campo | **prohibido**; test falla si se usa |
| MW-002 | dos rivales | creencias separadas |
| MW-003 | blockers compartidos | sample válido solo sin duplicados |
| MW-004 | colisión | rechazo contado; no reparación parcial |
| MW-005 | independencia | etiqueta `independence_baseline` |
| MW-006 | correlación | `correlation_model` obligatorio |
| MW-007 | all-in | sigue elegible para bote |
| MW-008 | side pot | cálculo por contribución |
| MW-009 | tie/odd chip | regla determinista |
| MW-010 | folded | no gana bote |
| MW-011 | rango vacío | `unknown`; no 0 |
| MW-012 | EV sin respuesta | inválido |
| MW-013 | mismo seed | mismos samples |
| MW-014 | UI | `MULTIWAY_SOPORTADO=False` |

### 2.9 Migración y artefactos

| ID | Caso | Esperado |
|---|---|---|
| MIG-001 | artefacto sin `contract_version` | legacy/`unknown_contract`; no mezcla |
| MIG-002 | artefacto con versión distinta | rechazo o marca |
| MIG-003 | router `legacy` | acción legacy |
| MIG-004 | router `shadow` | acción legacy; log canónico |
| MIG-005 | router `canonical` sin cobertura | `unsupported`; no fold |
| MIG-006 | rollback de serving | vuelve a legacy |
| MIG-007 | rollback de artefacto | restaura por hash |
| MIG-008 | regeneración selectiva | solo ventana afectada; manifiesto |
| ART-001 | manifiesto sin versión | marca `unknown_contract` |
| ART-002 | hash de snapshot distinto | rechazo explícito |
| ART-003 | inventario de cobertura distinto | reporte de deriva |

### 2.10 Sombra y no regresión

| ID | Caso | Esperado |
|---|---|---|
| SHW-001 | log por defecto | memoria; no escribe `data/` |
| SHW-002 | diferencia de acción | registrada; no corregida |
| SHW-003 | modo shadow | no cambia recomendación |
| SHW-004 | fixture de contrato | falla bloquea activación |
| SHW-005 | `MULTIWAY_SOPORTADO` | `False` |
| SHW-006 | hashes de datos | sin cambios |
| REG-001 | `_preflop_spot` | sin cambios |
| REG-002 | `_preflop_raises` | sin cambios |
| REG-003 | `table_plan` | no se “arregla” para cuadrar live |
| REG-004 | acción HU live | idéntica con router legacy |

### 2.11 Calibración

| ID | Caso | Esperado |
|---|---|---|
| CAL-001 | sin dataset | no calibrar |
| CAL-002 | split temporal | sin fuga |
| CAL-003 | features posteriores | prohibidas |
| CAL-004 | test visto | no se reajusta sin documentar |
| CAL-005 | métricas | Brier/log loss/ECE + CI |
| CAL-006 | EV held-out | no se sustituye por accuracy |
| CAL-007 | comparación | baseline declarado |

## 3. Criterios de aceptación

### 3.1 Mecánicos

- 100 % de fixtures de contrato y escenarios pasan.
- Campos obligatorios presentes; estados y coberturas explícitos.
- Ningún `gap`/`unknown` se convierte en `0`, fold o tabla.
- Mismo seed → mismo resultado.
- Sin escritura en `data/` ni cambio de `motor/`.

### 3.2 Estadísticos

- Toda estimación declara `n`, cobertura y CI.
- Exacto vs MC: diferencia dentro del CI; no igualdad forzada.
- Calibración solo con dataset congelado y test no visto.
- No se acepta una métrica agregada sin curvas/reliabilidad y CI.
- `n_eff` no se presenta como muestra observada.

### 3.3 Estratégicos

- Evaluación held-out por temporal split.
- EV/utility con baseline declarado (flat, tabla, legacy).
- No se declara mejora por paridad con legacy.
- No se declara mejora por accuracy si el EV held-out empeora.
- Los escenarios R01–R17 y S01–S13 se revisan, no solo el agregado.

### 3.4 Operativos

- `MULTIWAY_SOPORTADO=False`.
- Modo `shadow` no cambia la acción.
- Router legacy reproduce la acción previa en la muestra de regresión.
- Rollback de serving y de artefactos probado.
- Logs de diferencias no se usan como datos de entrenamiento.

## 4. Regla de bloqueo

Un fallo en PRE, AMB, COV o MIG bloquea SCN, RNG, EQ, EV y MW. No se
compensa con tests de capas superiores.

Un test verde no autoriza a activar `canonical` ni MW; la activación requiere
aprobación separada y evidencia held-out.

## 5. Evidencia a conservar

- versión de contrato y commit;
- hash de snapshot;
- fixtures y expected;
- configuración de semillas;
- reporte de cobertura por estado;
- reporte de rechazos/blockers;
- curvas y CI;
- diff de acciones en sombra;
- rollback ejecutado.
