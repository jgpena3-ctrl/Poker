# Línea base y plan técnico de calidad estratégica (HU/MW)

**Fecha:** 2026-11-10  
**Commit auditado:** `8594ed55c49b7452557d219a00d3c9fc63703379`  
**Estado:** auditoría de solo lectura. Este documento **no implementa** cambios ni autoriza a modificar datos canónicos.  
**Ejecución:** B0 cerrado el 2026-11-10 (ver `DOCS/B0_CIERRE_2026-11-10.md`). B1 sigue bloqueado y requiere autorización explícita.
**Objetivo:** separar lo que está probado de lo que no, y ordenar el trabajo para que las recomendaciones HU sean verificables y el multiway tenga un contrato propio.

---

## 0. Veredicto en una página

### Lo que sí está probado

- El motor postflop versionado es **reproducible**: 64 de 64 decisiones postflop del log se recalculan con el mismo EV y la misma acción. Diferencia máxima absoluta: `1,36e-07`. Mediana: `301 ms`; p95: `342 ms`; máximo: `355 ms`.
- El preflop probabilístico es **reproducible**: 86 de 86 decisiones preflop reproducen la acción muestreada con la semilla registrada.
- El log nuevo tiene información suficiente para recalcular el postflop: 64 decisiones con `reach_vector`, `ev_inputs`, `response_model_inputs` y `runout`.
- El evaluador actual sirve para integridad y disponibilidad, no para calidad estratégica.

### Lo que no está probado

- No está probada la **calidad estratégica** de las recomendaciones. La concordancia con la acción humana no es una prueba de corrección.
- El preflop **no es EV**: es una consulta de frecuencias en tablas manuales, con muestreo. No hay una comparación de EV entre fold/call/raise.
- Solo hay **34 decisiones HU postflop** versionadas (15 flop, 13 turn, 6 river). Es una muestra insuficiente para afirmar calidad o rentabilidad.
- El multiway sigue **no soportado**. Las 109 decisiones MW están marcadas `multiway_soportado=False`.

### Lo que está roto o desactualizado

- La base tiene **1344** líneas y SHA `3f0e7e5e...`; el manifiesto declara **1253** y SHA `c3172a14...`.
- Los derivados se regeneraron por última vez en `51a6fb9`; entre `51a6fb9` y HEAD cambiaron **107 de las primeras 900 manos**, con **15 cambios preflop** y **42 postflop**. Por tanto, los derivados de la ventana fiable están obsoletos.
- `CONTRATO_F72A.md` publica 512 puntos de política; la ventana actual mide **506**. El denominador se movió de 512 a 506 y el porcentaje de 41,2 % a 41,5 %.
- Hay **31 fallos deterministas** en `motor` y **26 en `tools`**, más **1 fallo dependiente del orden** de la suite completa (`test_decision_log`): **58 fallos** en total tras limpiar los diagnósticos temporales.
- El inventario de escritores de la base no declara **11 scripts** nuevos.
- El preflop puede consultar tablas en órdenes de acción imposibles y recomendar fuera de turno si el registro de acciones está incompleto.

### Decisión de orden

No se toca estrategia hasta cerrar la integridad de datos y la señal de tests. El orden es:

1. **B0:** baseline reproducible y tests que detecten de verdad.
2. **B1:** auditoría de la base, manifiesto y derivados (requiere autorización).
3. **B2/B3:** HU preflop con cobertura explícita y HU postflop con EV/incertidumbre.
4. **B4:** contrato multiway y motor conjunto, en sombra.
5. **B5/B6:** evaluador estratégico y sesión real corta.
6. **B7:** activación progresiva con reversión.

---

## 1. Línea base medida

### 1.1 Repositorio y datos

| Elemento | Valor medido |
|---|---|
| Rama | `main` |
| HEAD | `8594ed55c49b7452557d219a00d3c9fc63703379` |
| `origin/main` | `c1c1370` (`main` va 1 commit por delante) |
| `data/hands_db.jsonl` | **1344** líneas |
| SHA-256 de la base | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| Manifiesto declarado en `motor/learn.py` | **1253** líneas, SHA `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`, commit `51a6fb9` |
| Ventana fiable | primeras 900 líneas menos 23 exclusiones CM-004 = **877** |
| `RANGO_AUDITADO` | `H_1014`, 991 líneas |

La base cambió en `44acddb` y `8594ed5`. El manifiesto **no** se redeclaró. Los commits contienen scripts de corrección y mensajes que explican qué se corrigió, pero no actualizan `HANDS_DB_*` ni `DOCS/CANAL_MANUAL_CERRADO.md`.

**Medición de la deriva dentro de la ventana fiable:**

| Dato | Valor |
|---|---|
| Manos comparadas (primeras 900) | 900 |
| Manos cambiadas entre `51a6fb9` y HEAD | **107** |
| Con cambio en `streets.preflop` | **15** |
| Con cambio en flop/turn/river | **42** |
| Con cambio de `winner` | 1 |
| Con cambio de `final_pot` | 0 |

Esto no es un pin cosmético: **15 manos de la ventana cambian acciones preflop** y **42 cambian acciones postflop**. Los derivados `preflop_stats.json`, `behavior.json` y `observations.json` se calcularon antes de esos cambios.

### 1.2 Estado de los derivados

| Artefacto | Estado medido | Problema |
|---|---|---|
| `preflop_stats.json` | `hands = 877` | Calculado sobre una ventana anterior |
| `behavior.json` | `hands = 877`, `observaciones = 8742` | Obsoleto tras los cambios de la ventana |
| `observations.json` | 8742 filas | Obsoleto tras los cambios de la ventana |
| `profile_ranges.json` | `meta.code_commit = 0fcceed`, `meta.arbol_sucio = true`, `built_at = 2026-10-25` | Procedencia no limpia y anterior a la base actual |
| `player_stats.json`, `profiles.json`, `postflop_ranges.json` | Último cambio git en `51a6fb9` | No regenerados tras `44acddb`/`8594ed5` |

El último commit que tocó los derivados es `51a6fb9`. No se ha regenerado nada después de los cambios de base. No se ha ejecutado `tools/reconstruir_derivados.py regen` en esta auditoría porque escribiría en `data/`; queda como bloque B1 con autorización explícita.

### 1.3 Tests

| Suite | Resultado medido | Tiempo |
|---|---|---|
| `pytest motor -q` | **926 passed, 31 failed, 1 skipped, 5 xfailed** | 93,55 s |
| `pytest recorder -q` | **47 passed** | 1,61 s |
| `pytest tools` (sin `test_live.py` ni `test_mano6.py`) | **626 passed, 27 failed, 1 skipped** (antes de limpiar temporales; tras limpiar, 26 fallos) | 558,91 s |
| Suite completa `motor recorder tools` | **1599 passed, 58 failed, 2 skipped, 5 xfailed** | 648,96 s |

La suite completa tiene **58 fallos**:

- 31 fallos deterministas de `motor`.
- 1 fallo adicional de `motor` que solo aparece en la suite completa: `test_decision_log::test_recommendation_step_writes_sidecar_and_deduplicates_repeated_frame`. Pasa aislado; falla en la suite. Es un problema de aislamiento, no de la funcionalidad.
- 26 fallos de `tools`.

No se debe cerrar un bloque porque “los tests pasan”. Aquí hay que demostrar que los tests **detectan** los errores que dicen detectar.

### 1.4 Clasificación de los 58 fallos

| Módulo | Fallos | Clase | Evidencia |
|---|---:|---|---|
| `motor/test_accion_p.py` | 1 | Pin de base | 2702 postas vs 2522 declaradas |
| `motor/test_auditar_origen.py` | 12 | Pin de base | 1344 líneas vs 1253; SHA y conteos |
| `motor/test_canal_manual.py` | 4 | Manifiesto no redeclarado | SHA, líneas y commit; el script de reinterpretación ya no reconoce la base actual |
| `motor/test_cm004.py` | 1 | Pin de base | 1344 ciegas reconocidas vs 1253 |
| `motor/test_lista_saneamiento.py` | 2 | Pin de base | 1344 vs 1253 |
| `motor/test_quien_escribe.py` | 2 | **Contrato de integridad real** | 11 escritores no declarados; manifiesto contra disco |
| `motor/test_rango_fiable.py` | 1 | Métrica publicada obsoleta + deriva de ventana | 506 puntos vs 512 publicados |
| `motor/test_diagnostico_grabador.py` | 8 | Pin de base | 1344 vs 1253 |
| `motor/test_decision_log.py` | 1 (solo suite) | **Aislamiento de tests** | Pasa aislado; falla en suite |
| `tools/test_ejecutar_pytest.py` | 3 | **Inventario/higiene real** | 635 tests vs 616; línea 1908 vs 1365; 113 asignaciones vs 48. El fallo por 11 ficheros temporales fuera de inventario desapareció al limpiarlos. |
| `tools/test_auditoria_frentes.py` | 1 | **Declaración real** | `motor/test_asistente_live.py` modificado en `44acddb` y no declarado |
| `tools/test_barrido_documentos.py` | 1 | Documentación obsoleta | Frase retirada aún presente |
| `tools/test_bloqueo_orden_filtros.py` | 2 | Dato derivado obsoleto | Población B: 74 vs 76; 72/74 sin board |
| `tools/test_contrato_etiqueta.py` | 1 | Dato derivado obsoleto | Población B: 74 |
| `tools/test_decision_y_guardias.py` | 1 | Dato derivado obsoleto | Población B jugada: 326 |
| `tools/test_etiqueta_se_lee.py` | 3 | Dato derivado obsoleto | Población B: 210; 13 manos al AUC |
| `tools/test_fixture_duro.py` | 1 | Fixture a rediseñar | 0 conversiones vs 915; la base ya normalizó las ciegas a `p` |
| `tools/test_inc004_cerrado.py` | 1 | Manifiesto no redeclarado | SHA de la base |
| `tools/test_integrar_copia.py` | 5 | Fixture/controles obsoletos | 1344 vs 1253; conteos de categorías; control semántico |
| `tools/test_que_representa.py` | 2 | Dato derivado obsoleto | Cortes 631/233 vs 633/233; rivales 137 vs 139 |
| `tools/test_reduccion_auc.py` | 5 | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333 |

**Lectura correcta:** la mayoría son pines obsoletos, pero no todos. Los fallos de `test_quien_escribe`, `test_ejecutar_pytest`, `test_auditoria_frentes` y el aislamiento de `test_decision_log` son defectos de contrato o de señal de tests. Los de `test_integrar_copia` y `test_fixture_duro` indican que el fixture no se ha rediseñado tras la normalización de la base.

### 1.5 Log de decisiones

| Dato | Valor medido |
|---|---:|
| Eventos parseados | 506 |
| Decisiones | 358 |
| Resoluciones | 148 |
| Decisiones enlazadas | 148 |
| Pendientes | 210 |
| Canceladas | 2 |
| Malformadas | 0 |
| Duplicadas | 0 |
| Huérfanas | 0 |
| `motor_version_missing` | 208 |
| Decisiones con hash de motor | 150 |
| De ellas, resueltas | 147 |

**Reparto por ámbito (decisiones):**

| Ámbito | Total | Preflop | Flop | Turn | River |
|---|---:|---:|---:|---:|---:|
| Heads-up | 41 | 7 | 15 | 13 | 6 |
| Multiway | 109 | 79 | 22 | 5 | 3 |
| Desconocido | 208 | — | — | — | — |

**Decisiones postflop con inputs completos:** 64 (34 HU, 30 MW).  
**Decisiones preflop con frecuencias:** 86.  
**Decisiones preflop con alguna consulta `missing` o `fallback_other_vs`:** 25 de 86.

### 1.6 Reproducibilidad medida

#### Postflop

El replay reconstruye:

- `RangeState` desde `reach_vector`;
- el modelo de respuesta desde `response_model_inputs`;
- `compute_evs` con los mismos `ev_inputs`, `runout`, `n_runouts`, `bet_sizes`, `raise_to` y `villain_stack`;
- la acción con el mismo conjunto de candidatas.

| Resultado | Valor |
|---|---:|
| Decisiones replayables | 64 |
| Errores | 0 |
| Acciones coincidentes | 64 |
| Diferencia máxima absoluta de EV | `1,36e-07` |
| Diferencias > `1e-4` | 0 |
| Mediana | 301 ms |
| p95 | 342 ms |
| Máximo | 355 ms |

Esto demuestra que **el log es suficiente para recalcular el postflop**. No demuestra que el EV sea estratégicamente correcto: el modelo de respuesta es una heurística y el rango es una estimación.

#### Preflop

| Resultado | Valor |
|---|---:|
| Decisiones preflop | 86 |
| Muestreo reproducido con la semilla | 86 |
| Diferencias | 0 |
| Con `missing`/`fallback` | 25 |

El preflop reproduce la **política**, no un EV. La acción es una muestra de frecuencias; no hay comparación de EV.

### 1.7 Cobertura preflop

`audit_engine_coverage()` mide **222** comprobaciones del grammar preflop:

| Estado | N |
|---|---:|
| `exact` | 107 |
| `alias` | 1 |
| `intentional_missing` | 2 |
| `impossible_missing` | 82 |
| `coverage_gap` | 30 |
| `unclassified_missing` | 0 |

**Gaps observados en el log (6 consultas):**

| Clave | Consultas | Estado | Evidencia disponible |
|---|---:|---|---|
| `Call_OR_SB_vs_UTG` | 3 | `missing` / `coverage_gap` | 119 eventos, 27 con cartas conocidas |
| `Call_OR_SB_vs_CO` | 1 | `missing` / `coverage_gap` | 176 eventos, 34 con cartas conocidas |
| `4B_SB_vs_BTN` | 1 | `fallback_other_vs` | 31 eventos, 9 con cartas conocidas |
| `Call_3B_SB_vs_BTN` | 1 | `fallback_other_vs` | 31 eventos, 9 con cartas conocidas |

**Consultas por estado en el log preflop:**

| Estado/motivo | Consultas |
|---|---:|
| `exact` | 75 |
| `fallback_other_vs` / `fallback_to_other_vs` | 16 |
| `missing` / `impossible_action_order` | 16 |
| `missing` / `intentional_check_option` | 4 |
| `missing` / `coverage_gap` | 4 |
| `missing` / `intentional_no_prior_limp` | 1 |

Los 16 `impossible_action_order` no son huecos de tabla: son consultas a spots que no pueden existir con el orden de acciones registrado. Ejemplo medido: `H_1338`, héroe `UTG`, acciones `SB p`, `BB p`, `MP r`; el motor consulta `3B_UTG_vs_MP` y `Call_OR_UTG_vs_MP`, que son imposibles. El registro no contiene la acción de `UTG`, y el motor lo trata como si aún tuviera decisión abierta. Es un problema de elegibilidad/estado, no de frecuencias.

**Conclusión de cobertura:** los 30 gaps no se pueden rellenar con las muestras actuales. Los `Call_OR` tienen 24–49 manos con cartas conocidas; los `4B`/`Call_3B` tienen 0–9. Una tabla de 169 celdas no es identificable con esos datos. No se deben inventar frecuencias ni convertir la ausencia en fold.

### 1.8 Multiway

| Hecho | Valor |
|---|---|
| `MULTIWAY_SOPORTADO` | `False` |
| Decisiones MW versionadas | 109 |
| Marked `multiway_soportado=False` | 109 |
| Rango MW | `_build_multiway_range()` usa `RangeState.union()` |
| EV MW | `compute_evs()` contra **un** villano principal |
| `hierarchy.py` | Solo sombra; no corrige la equity conjunta |

`RangeState.union()` suma masas sin normalizar y no representa la distribución conjunta contra varios rivales. El contrato `DOCS/CONTRATO_F72A.md` lo prohíbe explícitamente. No se puede activar MW con la ruta actual.

`motor/hand_evaluator.py::evaluate_n_batch` sí acepta lotes de manos de 5–7 cartas y se puede reutilizar para el showdown multiway. Es la pieza reutilizable principal.

### 1.9 Hallazgos estratégicos que condicionan el plan

1. **`situation.equity` no es la equity de runout.**
   - `situation.equity` compara la fuerza actual contra el rango; `compute_evs` usa equity de runout cuando `runout=True`.
   - Ejemplo sintético medido: `AhKh` en `Qh7h2c` contra rango uniforme.
     - `situation.equity` actual: `0,5962`.
     - Equity de runout ponderada: `0,7244`.
     - Diferencia: `12,8` puntos porcentuales.
   - `rules.plan` recibe `range_advantage` calculado con `sit.equity`; puede restringir candidatas con una equity que no es la que usa el EV. Es una inconsistencia de contrato, no un detalle de presentación.
2. **El preflop no es EV.** Es una tabla de frecuencias manuales con muestreo. No hay comparación de EV entre acciones ni una noción de arrepentimiento.
3. **El modelo de respuesta es heurístico.** `_response_array` y `OracleResponse` mezclan una heurística con el perfil observado. El EV es “model-relative”, no una verdad.
4. **El evaluador mide concordancia, no calidad.** No recalcula EV, no comprueba legalidad, no mide arrepentimiento, no separa resultado de estrategia.
5. **Hay recomendaciones fuera de turno o sobre estados incompletos.** El gate `_alguna_hero_act` existe en el `step` de la GUI, pero `recomendaciones()` recorre todos los héroes y no verifica que cada uno tenga una decisión abierta. El log tiene 16 consultas imposibles como síntoma.

---

## 2. Arquitectura objetivo

### 2.1 Separación de capas

```
[snapshot de datos] -> [snapshot de derivados] -> [rango/equity] -> [decisión] -> [log] -> [evaluador]
        ^                       ^                      ^               ^
        |                       |                      |               |
   base + hash           ventana + hashes        joint/HU        policy/EV + incertidumbre
```

Regla: **calcular, recomendar, evaluar y ejecutar son cosas distintas**. Ninguna capa puede convertir una ausencia de dato en una acción.

### 2.2 Contratos que faltan

| Contrato | Contenido mínimo |
|---|---|
| `DataSnapshot` | commit, hash de base, líneas, hash de ventana fiable, hashes de derivados, fecha |
| `CoverageStatus` | `exact`, `alias`, `intentional`, `impossible`, `missing`, `fallback`; y política de decisión para cada uno |
| `EquityResult` | equity actual, equity de runout, modo, semilla, `n`, error estándar, intervalos |
| `Recommendation` | acción, fuente (`policy`/`ev`/`shadow`), confianza, incertidumbre, warnings, versión |
| `JointRange` | marginales por jugador, compatibilidad de cartas, blockers, muestreo/enumeración, diagnóstico |
| `MWDecision` | equity conjunta, EV conjunto, side pots, ties, supuestos, estado de soporte |

### 2.3 Incertidumbre explícita

Toda recomendación debe poder responder:

- ¿Qué modo de equity se usó?
- ¿Cuántas muestras/runouts?
- ¿Cuál es el error estándar o intervalo?
- ¿La cobertura era exacta o faltaba una tabla?
- ¿El modelo de respuesta era heurístico, de perfil o mixto?
- ¿La acción cambia si se perturban los parámetros del modelo?

Si la respuesta no está, la recomendación no es verificable.

### 2.4 Sombra y activación

Todo cambio estratégico nace en sombra:

- se calcula y se registra;
- **no** cambia la acción de producción;
- se compara contra la acción actual;
- se activa solo con criterios de aceptación y autorización.

`MULTIWAY_SOPORTADO` no cambia hasta que el contrato MW y sus pruebas exactas estén cerrados.

---

## 3. Plan por bloques

### B0 — Baseline reproducible y señal de tests

**Objetivo:** que la suite distinga un fallo real de un pin obsoleto y que el baseline se pueda repetir.

**Alcance:**

- `trabajo/` (limpiar diagnósticos temporales no rastreados).
- `motor/test_decision_log.py` (aislamiento).
- `tools/test_ejecutar_pytest.py` (inventario/declaraciones).
- `tools/test_auditoria_frentes.py` (declaración de tests modificados).
- Documento de fallos clasificados.

**Trabajo:**

1. Eliminar los scripts temporales de diagnóstico que no formen parte del entregable. En esta auditoría se crearon `trabajo/gap_evidence.py`, `trabajo/log_repro_counts.py`, `trabajo/replay_audit.py`, `trabajo/replay_preflop.py` y ficheros de salida; **ya se han retirado** y el fallo de `test_ejecutar_pytest` por código fuera de inventario desapareció. No deben volver a quedar como código no inventariado.
2. Reproducir el fallo de `test_decision_log` en suite y aislado; identificar el estado compartido (`POKER_DECISIONS_PATH`, `PLAYER_NAMES`, `Asistente`, ficheros de `data/`). Corregir solo el aislamiento, sin relajar aserciones.
3. Separar los fallos de `tools/test_ejecutar_pytest` en:
   - causados por nuestros temporales;
   - causados por tests nuevos no declarados;
   - causados por líneas/documentación movidas.
4. Declarar cada test de motor modificado que dependa de `preflop_matrices.json` en `MODIFICACIONES_DECLARADAS`, con motivo.
5. No subir ningún pin de base todavía.

**Tests:**

- Ejecutar la suite completa dos veces y comparar el conjunto de fallos.
- Ejecutar cada test sospechoso aislado y en suite.
- Los dos guards ya existen (`test_el_codigo_fuera_del_inventario_esta_declarado` y `test_los_tests_de_motor_que_dependen_del_matrix_no_se_han_tocado`); no se duplican. Se comprobó que fallan al reintroducir la condición que vigilan.

**Aceptación:**

- El conjunto de fallos es idéntico aislado y en suite.
- No hay ficheros de código temporal sin declarar.
- Cada fallo restante está clasificado como pin, derivado, fixture o contrato.
- No se ha modificado ningún dato canónico.

**Riesgo:** tocar tests para que pasen puede ocultar regresiones. Solo se permite corregir aislamiento/inventario, nunca cambiar la propiedad que el test mide.

---

### B1 — Base canónica, manifiesto y snapshot de calibración

**Objetivo:** que la base, los derivados y la ventana de calibración tengan una procedencia reproducible.

**Requisito:** este bloque **requiere autorización explícita** porque puede reescribir el manifiesto y regenerar derivados. No se ejecuta en esta auditoría.

**Alcance:**

- `data/hands_db.jsonl` (solo lectura hasta autorización).
- `motor/learn.py` (`HANDS_DB_*`, `RELIABLE_HANDS`).
- `DOCS/CANAL_MANUAL_CERRADO.md`, `DOCS/HOJA_DE_RUTA_POST_ADOPCION.md`, `DOCS/CONTRATO_F72A.md`, `DOCS/FASE_D_PLAN.md`.
- `tools/reconstruir_derivados.py`.
- `motor/test_quien_escribe.py`, `tools/quien_escribe.py`.

**Trabajo:**

1. **Auditoría de procedencia de `44acddb` y `8594ed5`.**
   - En un worktree temporal, partir del commit anterior y ejecutar los scripts de corrección.
   - Comparar el resultado byte a byte con la base actual.
   - Si un script no reproduce el cambio, marcarlo como no verificado.
   - Resumir por mano: qué cambió (fold, winner, pot, check, nota), si está dentro de la ventana fiable y si afecta a preflop/postflop.
2. **Decisión sobre la legitimidad.**
   - Si los cambios son reproducibles y están justificados: declarar `HANDS_DB_LINEAS = 1344`, `HANDS_DB_SHA256 = 3f0e...`, `HANDS_DB_COMMIT = 8594ed5`, y escribir el motivo en `DOCS/CANAL_MANUAL_CERRADO.md`.
   - Si no lo son: no subir pines; revertir o reparar la base.
3. **Inventario de escritores.**
   - Declarar los 11 scripts nuevos en `ESCRITORES_DECLARADOS` con `escribe`, `destino`, `condicion`, `temporal`.
   - Si son scripts de una sola vez, decirlo y documentar que no se reejecutan.
   - No dejar ninguno como “escritor implícito”.
4. **Snapshot de calibración.**
   - Crear `data/calibration_window.json` (o documento equivalente) con:
     - IDs de las primeras 900 manos;
     - las 23 exclusiones CM-004;
     - SHA de las líneas seleccionadas;
     - hash de la base y commit;
     - hashes de los derivados.
   - Añadir `tools/verificar_ventana.py` (solo lectura) y un test que falle si la ventana cambia sin redeclaración.
   - Motivo: hoy la ventana se define por “primeras 900 líneas”; si la base cambia, las métricas cambian sin que nadie lo declare. Un snapshot lo hace reproducible.
5. **Regeneración controlada de derivados.**
   - Usar `tools/reconstruir_derivados.py backup/regen/comparar` en una rama/worktree, nunca directamente sobre la base canónica sin aprobación.
   - Comparar antes/después: `preflop_stats`, `behavior`, `observations`, `profiles`, `player_stats`, `profile_ranges`, `postflop_ranges`.
   - Guardar el informe de diferencias.
   - Corregir la procedencia: `profile_ranges.meta` no puede decir `arbol_sucio=true` ni `code_commit=0fcceed` si se regenera desde HEAD.
6. **Recomputar métricas F7.2.**
   - La ventana actual mide: 649 puntos, 506 de política, 210 MW, 41,5 %, cota 234.
   - Actualizar `CONTRATO_F72A.md` o declarar expresamente que las cifras antiguas describen otra base.
7. **Documentar la decisión.**

**Tests:**

- `test_canal_manual`: hash, líneas y commit declarados.
- `test_quien_escribe`: inventario y manifiesto.
- Test de snapshot de ventana: cambiar una línea de la ventana cambia el hash y falla hasta redeclarar.
- Test de derivados: los hashes declarados coinciden con los ficheros.
- Test de métricas: `CONTRATO_F72A` menciona 506/210/234 o declara que son históricas.
- Test de procedencia: cada script declarado tiene condición y, si es temporal, restauración.

**Aceptación:**

- No hay pines obsoletos.
- Cada cambio de base tiene un script/procedimiento y un motivo escrito.
- Los derivados se pueden regenerar desde el snapshot declarado.
- La ventana de calibración tiene hash y lista de IDs.
- La suite determinista queda verde salvo fallos explícitamente documentados como no estratégicos.

**Riesgos:**

- Regenerar derivados cambia perfiles y rangos; hay que conservar los antiguos para comparar.
- Cambiar la ventana puede invalidar métricas históricas; no se debe reescribir la historia sin marcarla.
- La autorización es obligatoria: sin ella, B1 no se ejecuta.

---

### B2 — HU preflop: cobertura, elegibilidad y política honesta

**Objetivo:** que una decisión preflop HU sea legal, esté dentro de turno y no convierta una tabla ausente en un fold.

**Alcance:**

- `motor/preflop.py` (`lookup_table`, `classify_missing_table`, `audit_engine_coverage`, `TABLE_ALIASES`).
- `motor/asistente_live.py` (`_heroes_conocidos`, `_next_to_act`, `_hero_act`, `recomendaciones`, ruta preflop, `_log_recommendation`).
- `data/preflop_matrices.json` y nuevo manifiesto de procedencia.
- `motor/test_preflop_cobertura.py`, `motor/test_asistente_live.py`.

**Trabajo:**

1. **Estado de cobertura explícito en la decisión.**
   - `lookup_table` ya distingue `exact`, `alias`, `missing`; extender el resultado de recomendación con `coverage_status`.
   - Si el estado es `missing` o `fallback_other_vs`, la recomendación **no** se muestrea.
   - Devolver `coverage_insufficient` con explicación, no `retirar`.
   - En el panel: “sin recomendación estratégica: falta tabla para esta posición/rival”, no un fold.
2. **Fallback con contrato.**
   - Mantener el fallback solo para auditoría/telemetría.
   - Si se quiere usar un fallback estratégico, debe ser una decisión explícita, documentada y con confianza baja; no silenciosa.
   - Propuesta conservadora: eliminarlo de la ruta de producción.
3. **Elegibilidad por turno.**
   - Añadir un gate `decision_open(hero_pid)` que verifique:
     - el héroe está activo;
     - no ha actuado ya en la ronda actual después de la última subida;
     - el orden de acciones es consistente;
     - si el estado es ambiguo, no se recomienda.
   - `recomendaciones()` debe recomendar solo a héroes con decisión abierta, no a todos los activos.
   - Registrar `decision_skipped_reason` cuando no se recomienda.
4. **Consultas imposibles.**
   - Si el héroe está antes del último raiser y no tiene acción registrada, marcar `state_inconsistent` y no consultar tablas.
   - Test con el patrón `H_1338`: `UTG` no puede consultar `3B_UTG_vs_MP`.
5. **Procedencia de las tablas.**
   - Crear `data/preflop_matrices_provenance.json` con:
     - clave;
     - fuente (`manual`, `data`, `externa`);
     - autor/fecha;
     - muestra (si aplica);
     - confianza;
     - notas.
   - Las 117 tablas actuales son manuales y no verificadas: no se declaran GTO.
   - Validador: 13×13, probabilidades en [0,1], suma 1, acciones legales, etiquetas conocidas.
6. **No generar tablas nuevas con datos insuficientes.**
   - Los 30 gaps tienen 0–49 manos con cartas conocidas; una tabla de 169 celdas no es identificable.
   - No se rellenan con frecuencias inventadas.
   - Si se quiere un modelo basado en datos, se diseña aparte, con estimador jerárquico, validación fuera de muestra y sombra; no es parte de B2.

**Tests que deben detectar el error estratégico:**

- Fixture con `Call_OR_SB_vs_UTG` ausente: la recomendación debe ser `coverage_insufficient`, no `retirar`.
- Fixture con fallback: no debe producir acción de producción; debe registrar `fallback_used`.
- Fixture de héroe que ya actuó: no debe recomendar.
- Fixture de orden imposible: no debe consultar la tabla.
- Replay de las 86 decisiones preflop: las elegibles siguen reproduciendo; las no elegibles quedan marcadas.
- Validador de tablas: una tabla con suma 0,9 o acción ilegal debe fallar.

**Aceptación:**

- 0 recomendaciones estratégicas con cobertura `missing`.
- 0 fallbacks silenciosos.
- 0 recomendaciones fuera de turno en los fixtures.
- Los 30 gaps aparecen en el informe y en el log.
- Las tablas existentes no se modifican sin autorización.
- La UI distingue “sin recomendación” de “fold”.

**Riesgo:** el usuario puede necesitar una acción incluso sin cobertura. La respuesta correcta es mostrar la limitación, no fabricar una frecuencia.

---

### B3 — HU postflop: EV, legalidad e incertidumbre

**Objetivo:** que el EV HU sea reproducible, legal y con incertidumbre declarada; y que la equity usada para el EV no se mezcle con la equity actual.

**Alcance:**

- `motor/situation.py` (`situation`, `equity_vs_range`).
- `motor/decision.py` (`compute_evs`, `_showdown_equity_by_combo`, `_response_array`, `OracleResponse`).
- `motor/rules.py` (`plan`, `select_best`, candidatas).
- `motor/recommend_loop.py` (dos pasadas, `runout`, `range_advantage`).
- `motor/decision_log.py` (snapshot).
- `motor/panel.py`.
- Nuevos tests de contrato HU.

**Trabajo:**

1. **Modo de equity.**
   - Añadir al snapshot y al panel: `equity_current`, `equity_runout`, `equity_mode`, `n_runouts`, `mc_stderr`, `seed`.
   - `compute_evs` ya usa runout; hacer explícito si la segunda pasada se ejecutó o si se quedó en la primera.
   - `range_advantage` debe declarar con qué equity se calcula. Si se usa `sit.equity` actual, etiquetarlo; si se usa runout, calcularlo aparte.
   - Test: un proyecto de color en flop debe mostrar `equity_runout > equity_current` y el EV debe usar runout. Si `runout=False`, marcar `current_only` y no presentar el EV como definitivo.
2. **Legalidad de acciones.**
   - Añadir `legal_actions(to_call, stack, villain_stack, pot)`.
   - Candidatas = intersección de plan y acciones legales.
   - Test: con `to_call=0`, no se ofrece fold ni raise ilegal; con `to_call>stack`, solo all-in/call/fold según corresponda; con `raise_to` fuera de rango, no se ofrece.
3. **Aritmética de bote y pot odds.**
   - Tests exactos para `call_pot`, `call_amount`, `effective_stack`, `raise_to`, `all_in`.
   - Test de propiedad: `call EV = equity * (pot + 2*to_call) - to_call` en el caso sin raise.
4. **Modelo de respuesta.**
   - Documentar `_response_array` y `OracleResponse`.
   - Añadir sensibilidad: perturbar `pf`, `pc`, `pr`, `alpha`, `sizing` en un rango declarado y comprobar si cambia el ranking.
   - Si cambia, `decision_stable=False` y advertencia; no ocultar la inestabilidad.
   - No presentar el EV como “verdadero”; es EV bajo el modelo.
5. **Sizing.**
   - Verificar que `bet_sizes` de `rules.plan` son legales, únicos y no inventados.
   - Test: tamaños duplicados o > stack se rechazan.
   - No añadir tamaños nuevos sin contrato.
6. **Coherencia de rango.**
   - Test: `RangeState` normalizado, blockers en cero, sin `union`.
   - Test: rango vacío lanza error, no se convierte en uniforme.
7. **`select_best`.**
   - Test: baseline fold = 0; check con EV ≥ 0 no pierde contra fold; NaN se ignora; candidata con EV mayor no se descarta sin regla documentada.
8. **Fixtures estratégicos.**
   - River nuts vs bluff-catcher: acción de máximo EV conocida.
   - Proyecto de color: equity de runout y EV.
   - Pot odds: call exacto.
   - Blockers: combos bloqueados a cero.
   - Tie: reparto 50/50.
   - Sensibilidad: acción que cambia con el modelo; debe marcarse inestable.
9. **Antes/después.**
   - Recalcular las 34 decisiones HU postflop con la equity/modo/legalidad corregidos.
   - Informar flips de acción y deltas de EV; no activar.

**Aceptación:**

- 64/64 replays siguen exactos.
- 0 acciones ilegales en fixtures.
- 100 % de snapshots HU postflop con `equity_mode`, `n_runouts` y `mc_stderr`.
- Toda decisión con ranking inestable queda marcada.
- Los fixtures exactos pasan.
- No se declara calidad estratégica con 34 decisiones.

**Riesgo:** el modelo de respuesta puede dominar el resultado. La sensibilidad es obligatoria; sin ella, el EV no es verificable.

---

### B4 — Multiway: contrato y motor conjunto

**Objetivo:** sustituir la unión de rangos por una distribución conjunta validada, sin activar producción.

**Alcance:**

- Nuevo `DOCS/CONTRATO_MULTIWAY.md`.
- Nuevo `motor/joint_ranges.py`.
- Nuevo `motor/decision_mw.py`.
- `motor/recommend_loop.py` (solo sombra).
- `motor/hand_evaluator.py` (`evaluate_n_batch` reutilizado).
- `motor/multiway.py` (clasificación, sin cambios de política).

**Contrato mínimo:**

1. **Jugadores y orden.** Conjunto activo, orden de acción, all-in, side pots, ties.
2. **Distribución conjunta.** `P(h1,...,hn) ∝ ∏ w_i(hi) * [cartas distintas]`, con marginales declaradas. No es `union()`.
3. **Blockers.** Cartas del héroe, board y otros villanos excluidas; si un rango queda vacío, error.
4. **Equity.** Equity del héroe contra la distribución conjunta; ties repartidos; side pots.
5. **EV.** Árbol de acciones con modelo de respuesta por villano; supuestos explícitos; no se presenta como GTO.
6. **Muestreo.** Enumeración exacta si el espacio es pequeño; Monte Carlo con semilla, tamaño, error estándar e intervalo.
7. **Incertidumbre.** Si los intervalos de dos acciones se solapan, `uncertain`; no se elige una como “mejor”.
8. **Activación.** `MULTIWAY_SOPORTADO=False` hasta que el contrato y las pruebas exactas pasen.

**Implementación:**

- `JointRange`:
  - marginales dispersas;
  - `validate()`;
  - `sample_joint(n, rng, dead_cards)`: muestreo secuencial ponderado sin reemplazo;
  - `enumerate_joint()` para espacios pequeños;
  - diagnóstico de duplicados, masa, marginales.
- `joint_equity`:
  - muestrear manos conjuntas;
  - completar board;
  - evaluar con `evaluate_n_batch` (5–7 cartas);
  - comparar scores; ties;
  - devolver equity, error estándar, n, seed.
- `multiway_ev`:
  - acciones candidatas legales;
  - respuesta por villano;
  - side pots;
  - presupuesto anytime;
  - intervalo.
- Sombra:
  - `recommend_loop` calcula `shadow_mw_equity`/`shadow_mw_ev`;
  - la acción de producción no cambia;
  - el log guarda diagnóstico.

**Pruebas exactas:**

- Dos villanos con un combo cada uno y board conocido: equity calculada a mano.
- Blockers: dos combos que comparten carta tienen probabilidad 0.
- Marginales: la marginal de cada villano coincide con su rango.
- Permutación: cambiar el orden de villanos no cambia la equity del héroe.
- Ties: dos villanos empatan; el bote se reparte.
- Side pots: stack corto all-in gana el bote principal; los grandes reparten el lateral.
- Convergencia: Monte Carlo vs enumeración exacta dentro del intervalo.
- Negativo: `RangeState.union()` produce masa > 1 y se rechaza.
- Negativo: el EV de un solo villano no coincide con el EV conjunto en un caso construido; el motor no debe usar el primero.

**Aceptación:**

- Contrato firmado.
- Todas las pruebas exactas pasan.
- `MULTIWAY_SOPORTADO` sigue `False`.
- Las 109 decisiones MW se recalculan en sombra sin cambiar la acción.
- El log incluye `shadow_mw` y `multiway_soportado=False`.

**Riesgo:** la independencia condicional de los rangos es un supuesto. Si los rangos están correlacionados por la historia, el modelo es aproximado; debe declararse.

---

### B5 — Evaluador estratégico

**Objetivo:** que el evaluador distinga integridad, reproducibilidad, legalidad, cobertura, EV model-relative y resultado.

**Alcance:**

- `tools/evaluar_decisiones.py`.
- Nuevos tests de evaluador.
- Logs sintéticos con defectos inyectados.

**Trabajo:**

1. **Replay.**
   - Reconstruir `RangeState`, `response_fn` y `compute_evs`.
   - Comparar EV y acción; tolerancia `1e-6`.
   - Reportar `replay_status`: `exact`, `mismatch`, `not_replayable`, `legacy`.
2. **Chequeos estratégicos.**
   - Acciones legales.
   - Cobertura preflop (`exact`/`missing`/`fallback`).
   - Modo de equity (`current`/`runout`).
   - Rango normalizado y blockers.
   - Aritmética de bote/pot odds.
   - Latencia.
3. **Pérdida model-relative.**
   - `loss = EV(mejor legal) - EV(recomendada)` bajo el mismo modelo.
   - Intervalo bootstrap.
   - Etiqueta: “model-relative, no verdadera”.
4. **Sensibilidad.**
   - Perturbar respuesta/rango; reportar flips.
5. **Resultado.**
   - Separar `outcome` de `quality`.
   - No usar resultado como prueba de corrección.
6. **Calibración.**
   - Equity predicha vs showdown realizado; Brier; n.
   - No calcular con n insuficiente.
7. **Versiones.**
   - `motor_version`, `base_hash`, `derived_hash`, `window_hash`.
8. **Legacy.**
   - Las decisiones sin `motor_version` se reportan como `not_replayable`, no como cero.

**Tests:**

- Log sintético con EV incorrecto: detectado.
- Acción ilegal: detectada.
- Cobertura missing usada como fold: detectada.
- Rango con masa != 1: detectado.
- Pot odds incorrectas: detectado.
- Log válido: sin falsos positivos.
- 64/64 replay exacto.
- No se calcula calidad con n < umbral.

**Aceptación:**

- El evaluador detecta todos los defectos inyectados.
- Reporta reproducibilidad, legalidad, cobertura, incertidumbre y resultado por separado.
- No usa concordancia como prueba de calidad.

---

### B6 — Sesión real corta y validación progresiva

**Objetivo:** comprobar que el sistema escribe un log evaluable en condiciones reales, sin activar cambios estratégicos.

**Alcance:**

- `POKER_DECISIONS_PATH` independiente.
- Sesión corta (50–100 manos o límite temporal declarado).
- Sombra activa.
- Evaluador B5.

**Checklist previo:**

- Commit limpio.
- Base/manifiesto/derivados declarados.
- Snapshot de ventana.
- Suite verde o fallos documentados.
- Informe de cobertura preflop.
- Aviso MW visible.
- `MULTIWAY_SOPORTADO=False`.
- Log nuevo, no `data/decisions.jsonl`.

**Durante:**

- Deadline de decisión 8 s.
- Objetivo de captura/proceso ~0,5 s.
- Registrar `motor_version`, `base_hash`, `derived_hash`, `window_hash`, `coverage_status`, `equity_mode`, `runout`, `uncertainty`, `latency`.
- No activar ninguna recomendación nueva.

**Después:**

- Verificar `motor_version` en el 100 % de las decisiones.
- Verificar resoluciones y enlaces.
- Evaluar reproducibilidad, cobertura, legalidad, latencia y calibración.
- Comparar con el baseline.
- No extraer conclusiones de calidad si n es insuficiente.

**Aceptación:**

- 0 decisiones sin `motor_version`.
- Resoluciones enlazadas (o causa documentada).
- 0 recomendaciones MW presentadas como soportadas.
- 0 decisiones con cobertura missing sin advertencia.
- Latencia dentro del límite.
- Informe con n y intervalos.

**Riesgo:** la sesión real puede no producir resoluciones suficientes; en ese caso no se declara calidad.

---

### B7 — Activación y reversión

**Objetivo:** activar solo lo que haya pasado las pruebas y poder volver atrás.

**Trabajo:**

- Feature flags separadas:
  - `HU_PREFLOP_COVERAGE_POLICY`
  - `HU_POSTFLOP_EV_V2`
  - `MW_JOINT_SHADOW`
  - `MW_SUPPORTED` (sigue `False`)
- Criterios de activación por flag.
- Rollback: commit anterior, flags, backup de derivados, log.
- Documento de activación con fecha, versión y evidencia.

**Aceptación:**

- Ninguna flag se activa automáticamente.
- Cada activación tiene un informe before/after.
- `MW_SUPPORTED` no cambia hasta B4 completo + validación real.

---

## 4. Orden y dependencias

| Bloque | Depende de | Se puede paralelizar | Gate |
|---|---|---|---|
| B0 | — | — | Suite determinista y fallos clasificados |
| B1 | B0 + autorización | Auditoría de base y diseño MW | Manifiesto/derivados/ventana declarados |
| B2 | B1 | B3, B4 (diseño) | Cobertura y elegibilidad HU |
| B3 | B1 | B2, B4 (diseño) | EV HU legal y con incertidumbre |
| B4 | B1 (contrato) | B2/B3 | Contrato MW y pruebas exactas |
| B5 | B1, B3 | B4 | Evaluador detecta defectos |
| B6 | B2, B3, B5 | — | Sesión real evaluable |
| B7 | B6 | — | Activación autorizada |

El diseño MW (B4) puede avanzar en paralelo con B2/B3, pero **no** se integra en producción hasta que B3 y B5 estén cerrados.

---

## 5. Criterios de aceptación globales

No se puede declarar “motor estratégicamente fiable” hasta que se cumplan todos:

1. **Datos:** base, ventana y derivados con hash y procedencia; suite determinista.
2. **HU preflop:** 0 folds por cobertura ausente; 0 fallbacks silenciosos; elegibilidad por turno.
3. **HU postflop:** 100 % de replays exactos; 0 acciones ilegales; equity/modo/incertidumbre en el log; fixtures exactos.
4. **MW:** contrato firmado; pruebas exactas de distribución conjunta, blockers, ties y side pots; sombra sin cambio de acción.
5. **Evaluador:** detecta defectos inyectados; separa calidad de resultado; no usa concordancia como prueba.
6. **Sesión real:** log con versiones y resoluciones; latencia; muestra suficiente.
7. **Sin afirmaciones de rentabilidad** sin evidencia suficiente.

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Regenerar derivados cambia perfiles y recomendaciones | Backup, comparación before/after, sombra, no activación automática |
| La base cambia dentro de la ventana | Snapshot de ventana con hash; redeclaración obligatoria |
| Los pines obsoletos ocultan regresiones | B0: suite determinista; tests que detecten el defecto |
| El preflop no tiene EV | Etiquetar como política; no presentar como EV; no inventar tablas |
| El modelo de respuesta es heurístico | Sensibilidad; etiqueta model-relative; intervalos |
| Monte Carlo cambia decisiones cercanas | Error estándar; intervalos; `uncertain` |
| MW con supuestos de independencia | Declararlo; validar con casos exactos; no activar |
| Latencia MW | Anytime; presupuesto; muestras adaptativas |
| Recomendaciones fuera de turno | Gate de elegibilidad; estado inconsistente = no recomendación |
| El evaluador mide solo concordancia | B5: replay, legalidad, cobertura, pérdida model-relative, resultado separado |

---

## 7. Acciones inmediatas

1. Limpiar los diagnósticos temporales de `trabajo/` y volver a ejecutar la suite completa; guardar el conjunto exacto de fallos.
2. Reproducir el fallo de `test_decision_log` en suite y aislado; corregir el aislamiento.
3. Preparar el informe de procedencia de `44acddb`/`8594ed5` en un worktree, sin tocar la base canónica.
4. Pedir autorización para B1: redeclarar manifiesto, regenerar derivados y actualizar métricas.
5. Construir el inventario de cobertura y el manifiesto de procedencia de las 117 tablas preflop (solo lectura).
6. Convertir el replay de 64 postflop + 86 preflop en un harness dentro de `tools/`, con tests y sin depender de scripts temporales.
7. Añadir los fixtures HU postflop de legalidad/equity/runout antes de tocar la lógica.
8. Redactar `DOCS/CONTRATO_MULTIWAY.md` y las pruebas exactas; no implementar producción.
9. No activar ninguna flag ni cambiar `MULTIWAY_SOPORTADO` hasta B6/B7.

---

## Apéndice A — Los 30 gaps de cobertura preflop

Medido sobre las 1344 manos actuales. `n` = eventos que caen en el spot; `known` = eventos con cartas conocidas. No se ha generado ninguna tabla.

| Clave | n | known | Categorías observadas |
|---|---:|---:|---|
| `Call_OR_MP_vs_UTG` | 138 | 24 | call_open 26, fold_vs_open 105, 3bet 7 |
| `Call_OR_CO_vs_UTG` | 131 | 26 | fold_vs_open 102, 3bet 3, call_open 26 |
| `Call_OR_CO_vs_MP` | 175 | 36 | fold_vs_open 117, call_open 50, 3bet 8 |
| `4B_CO_vs_MP` | 7 | 0 | fold_vs_3bet 7 |
| `Call_3B_CO_vs_MP` | 7 | 0 | fold_vs_3bet 7 |
| `4B_BTN_vs_MP` | 8 | 2 | call_3bet 1, fold_vs_3bet 7 |
| `Call_3B_BTN_vs_MP` | 8 | 2 | call_3bet 1, fold_vs_3bet 7 |
| `4B_BTN_vs_CO` | 11 | 0 | call_3bet 1, fold_vs_3bet 10 |
| `Call_3B_BTN_vs_CO` | 11 | 0 | call_3bet 1, fold_vs_3bet 10 |
| `Call_OR_SB_vs_UTG` | 119 | 27 | call_open 32, fold_vs_open 81, 3bet 5, squeeze 1 |
| `Call_OR_SB_vs_MP` | 150 | 36 | call_open 47, fold_vs_open 95, 3bet 3, squeeze 5 |
| `4B_SB_vs_MP` | 8 | 1 | fold_vs_3bet 7, call_3bet 1 |
| `Call_3B_SB_vs_MP` | 8 | 1 | fold_vs_3bet 7, call_3bet 1 |
| `Call_OR_SB_vs_CO` | 176 | 34 | fold_vs_open 127, call_open 43, 3bet 4, squeeze 2 |
| `4B_SB_vs_CO` | 11 | 2 | fold_vs_3bet 10, call_3bet 1 |
| `Call_3B_SB_vs_CO` | 11 | 2 | fold_vs_3bet 10, call_3bet 1 |
| `Call_OR_SB_vs_BTN` | 196 | 49 | fold_vs_open 139, call_open 46, 3bet 11 |
| `4B_SB_vs_BTN` | 31 | 9 | fold_vs_3bet 26, call_3bet 5 |
| `Call_3B_SB_vs_BTN` | 31 | 9 | fold_vs_3bet 26, call_3bet 5 |
| `Call_5B_SB_vs_BTN` | 0 | 0 | — |
| `4B_BB_vs_MP` | 8 | 2 | fold_vs_3bet 7, call_3bet 1 |
| `Call_3B_BB_vs_MP` | 8 | 2 | fold_vs_3bet 7, call_3bet 1 |
| `4B_BB_vs_CO` | 11 | 2 | fold_vs_3bet 10, call_3bet 1 |
| `Call_3B_BB_vs_CO` | 11 | 2 | fold_vs_3bet 10, call_3bet 1 |
| `4B_BB_vs_BTN` | 32 | 7 | call_3bet 7, fold_vs_3bet 25 |
| `Call_3B_BB_vs_BTN` | 32 | 7 | call_3bet 7, fold_vs_3bet 25 |
| `Call_5B_BB_vs_BTN` | 0 | 0 | — |
| `4B_BB_vs_SB` | 31 | 3 | fold_vs_3bet 31 |
| `Call_3B_BB_vs_SB` | 31 | 3 | fold_vs_3bet 31 |
| `Call_5B_BB_vs_SB` | 0 | 0 | — |

**Lectura:** los `Call_OR` tienen muestra para estimar una política gruesa, pero no para una rejilla de 169 celdas. Los `4B`/`Call_3B` tienen 0–9 manos con cartas conocidas: no hay evidencia para fijar frecuencias. La política correcta es declarar cobertura insuficiente, no inventar.

---

## Apéndice B — Escritores no declarados detectados

`tools/quien_escribe.py` detecta 11 scripts que escriben `data/hands_db.jsonl` y no están en `ESCRITORES_DECLARADOS`:

- `tools/corregir_anotaciones_20261110.py`
- `tools/corregir_bote_inflado_fold.py`
- `tools/corregir_folds_showdown.py`
- `tools/corregir_mano_H_1333.py`
- `tools/corregir_resultados_20261029.py`
- `tools/corregir_resultados_20261104.py`
- `tools/corregir_sesion_20261104.py`
- `tools/corregir_showdown_posicion.py`
- `tools/eliminar_mano_H_1323.py`
- `tools/limpiar_anotaciones_ruido.py`
- `tools/limpiar_notas_inferidas.py`

Todos aparecen en `8594ed5` o en su entorno inmediato. B1 debe decidir, para cada uno:

- declararlo como escritor autorizado con condición y motivo; o
- retirarlo del árbol activo y dejar constancia de que fue una corrección de una sola vez.

No se puede dejar el inventario incompleto: un escritor no declarado puede volver a cambiar la base sin que el guard lo vea.

---

## Apéndice C — Evidencia de replay

### Postflop

- Decisiones replayables: 64.
- Errores: 0.
- Acciones coincidentes: 64.
- Diferencia máxima absoluta: `1,3630619744020578e-07`.
- Mediana: `301,49 ms`.
- p95: `342,28 ms`.
- Máximo: `354,83 ms`.

El replay reconstruye `response_fn` desde `response_model_inputs`; sin esa reconstrucción, las acciones agresivas no coinciden. Esto es importante para el evaluador: el log debe seguir guardando `pf_p`, `pc_p`, `pr_p`, `alpha`, `sizing`, `profile`, `street`, `facing` y `texture`.

### Preflop

- Decisiones: 86.
- Muestreo reproducido: 86.
- Con `missing`/`fallback`: 25.
- Consultas exactas: 75.
- Consultas con fallback: 16.
- Consultas imposibles: 16.
- Consultas intencionales: 5.

---

## Apéndice D — Qué no se ha hecho

- No se ha modificado `data/hands_db.jsonl`.
- No se han regenerado derivados.
- No se han cambiado tablas preflop.
- No se ha cambiado `MULTIWAY_SOPORTADO`.
- No se ha implementado el motor conjunto.
- No se ha activado ninguna recomendación nueva.
- No se ha jugado la sesión real.
- No se ha declarado calidad estratégica ni rentabilidad.

Este documento es el plan; la ejecución empieza por B0 y B1, con autorización explícita para B1.
