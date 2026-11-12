# P0-6 — corrección de contradicciones y auditoría de writers

**Estado:** completado para revisión. P0-1…P0-5 siguen en sombra. No se
modificaron la base canónica, derivados, matrices, manifiestos/pins ni los 11
scripts escritores investigados. Tampoco se activaron filtros, contratos ni
restricciones live.

Identidad de trabajo: base `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`;
ventana `reliable_only/first-900-minus-23=877`, hash
`ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed`.
`build_models` permanece `partial`; P0-6 no eleva la procedencia por
reproducibilidad o coincidencia de resultados.

## 1. Prioridad máxima — inventario de los 11 writers

### 1.1 Alcance reproducible

Se ejecutó `python tools/quien_escribe.py` y la prueba de autocomprobación del
instrumento. Reporta **18 fuentes que pueden escribir
`data/hands_db.jsonl`**: los 7 writers declarados antes y los 11 no declarados
que motivaron P0-6. La lista completa, incluidos operación, ejecución, posible
coincidencia con live, protecciones y riesgo, queda en
`motor/test_quien_escribe.py::ESCRITORES_DECLARADOS`; los tests exigen que ningún
campo de riesgo/protección quede vacío.

Los 11 examinados son todos writers de la base canónica. No se encontró que
escriban directamente los siete derivados, `preflop_matrices.json`,
`calibration_window.json`, manifiestos o pins. Todos hacen backups bajo
`data/_backup_*`; `eliminar_mano_H_1323.py` también archiva una fila en
`data/_eliminadas/H_1323.jsonl`.

### 1.2 Tabla archivo × función × efectos × salvaguardas

| Writer y funciones principales | Operación/destinos | Condición de escritura | Automático / live | Protección y riesgo residual |
|---|---|---|---|---|
| `tools/corregir_anotaciones_20261110.py`: `corregir_h1303`, `corregir_h1327`, `corregir_h1351`, `construir_plan`, `aplicar` | Reescribe `recorder_audit`/`audit_notes` en H_1303/H_1327/H_1351. No edita acciones ni `final_pot`. DB canónica + `_backup_corregir_anotaciones_20261110/hands_db.jsonl`. | Solo `--apply`; dry-run por defecto; IDs fijos. | Manual CLI; no hay llamada desde recorder. Puede ejecutarse concurrentemente si se invoca manualmente; no hay lock. | Backup hash verificado al crearse, temp JSON validado y `os.replace`. Si el backup ya existe solo se conserva y se muestra su SHA, no se contrasta con el DB actual. |
| `tools/corregir_bote_inflado_fold.py`: `corregir_hand`, `construir_plan`, `aplicar` | Cambia audit y `final_pot` para folds con excedente no igualado y condiciones de bote/fold_win cumplidas. DB + `_backup_corregir_bote_inflado_fold`. | `--apply`; manos que no encajan con el bote calculado se dejan para revisión manual. | Manual, no scheduler; posible concurrente con live por ausencia de lock. | Dry-run, backup/hash inicial, temp JSON y replace; no fija el hash preimagen esperado. Backup preexistente no se coteja con DB actual. |
| `tools/corregir_folds_showdown.py`: `folds_removibles`, `corregir_mano`, `construir_plan`, `aplicar` | Puede retirar folds inferidos, cambiar `fold_win`, `winner`, `showdown`, auditoría, rake/bote y `final_pot`. DB + `_backup_corregir_folds_showdown`. | `--apply`; requiere fold inferido y aporte ya igualado al máximo de la calle. | Manual; posible concurrente; sin lock. | Dry-run, backup/hash, JSON temporal y rollback si falla `replace`; no valida un pin de base antes de aplicar. |
| `tools/corregir_mano_H_1333.py`: `corregir_mano`, `verificar`, `aplicar`, `restaurar` | Cambia una mano concreta: fold, ganador/showdown, resultado, bote y notas de corrección. DB + `_backup_corregir_mano_H_1333`. | `--apply`; exige H_1333 y comprobaciones de esa mano. | Manual; posible concurrente; sin lock. | Backup/hash, verificación completa en memoria y post-write, `--restore`. Protección fuerte y acotada a una fila; sigue siendo writer canónico de riesgo alto. |
| `tools/corregir_resultados_20261029.py`: `corregir_h1314`, `corregir_h1324`, `construir_plan`, `aplicar` | Inserta un fold inferido en H_1314 y cambia estados showdown/fold_win/audit/bote de H_1314/H_1324. DB + `_backup_corregir_resultados_20261029`. | `--apply`; IDs fijados; helper aritmético importado de `corregir_resultados_20261104.py`. | Manual; posible concurrente; sin lock. | Dry-run, backup/hash, temp JSON válido y replace; no verificación post-write global. |
| `tools/corregir_resultados_20261104.py`: `CORRECTORES`, `corregir_h1330`, `corregir_h1337`, `corregir_h1342`, `reclasificar_showdown`, `corregir_showdown`, `aplicar` | Puede insertar o recodificar acciones; cambiar winner/showdown/fold_win y recalcular audit/bote. DB + `_backup_corregir_resultados_20261104`. | `--apply`; mapa de IDs y cambios codificado para la sesión. | Manual; posible concurrente; sin lock. Sus helpers importados por otros scripts no invocan automáticamente `main`. | Dry-run, backup/hash, temporal JSON válido y replace; no verificación post-write global. |
| `tools/corregir_sesion_20261104.py`: `corregir_comision`, `limpiar_folds`, `limpiar_checks`, `construir_plan`, `aplicar` | Cambia rake/botes y marcas `ambiguous` de folds/checks en filas del DB. DB + `_backup_corregir_sesion_20261104/hands_db.jsonl`. | `--apply`; 5% rake solo en fecha 2026-11-04 e IDs H_1328..H_1341; folds/checks se proyectan por reglas del script. | Manual; posible concurrente; sin lock. | Dry-run, backup, verificación en memoria/post-write y temporal. **No ofrece `--restore` CLI**; respaldo exige restauración manual. Backup preexistente no se compara con el DB actual. |
| `tools/corregir_showdown_posicion.py`: `resolver_nombre`, `corregir_mano`, `construir_plan`, `aplicar` | Cambia solo texto `showdown.winner1` si nombre único y posición concuerda con `winner`. DB + `_backup_corregir_showdown_posicion`. | `--apply`; filas irresolubles se omiten, no se inventa el nombre. | Manual; posible concurrente; sin lock. | Dry-run, prueba de unicidad/ganador, backup/hash, JSON temporal y restore; sin pin de base. |
| `tools/eliminar_mano_H_1323.py`: `verificar_duplicacion`, `aplicar` | Elimina la línea H_1323 de DB, la guarda en `_eliminadas/H_1323.jsonl` y guarda el DB entero en `_backup_eliminar_H_1323`. | `--apply`; requiere comprobar tablero/jugadores/ganador frente a H_1322. | Manual; posible concurrente; sin lock. | Backup/hash y temp JSON; archivo de cuarentena se abre con modo escritura y puede sobreescribir una copia previa. Restore sustituye el DB desde el backup. |
| `tools/limpiar_anotaciones_ruido.py`: `limpiar_hand`, `construir_plan`, `aplicar` | Quita `capture`, `capture_sha256` y `award_display_ignored` del JSON de auditoría. No borra capturas ni índice externo. DB + `_backup_limpiar_anotaciones_ruido`. | `--apply`; solo claves enumeradas; dry-run por defecto. | Manual; posible concurrente; sin lock. | Backup/hash, temp JSON y replace; backup preexistente no se compara con la base actual. |
| `tools/limpiar_notas_inferidas.py`: `limpiar_hand`, `construir_plan`, `aplicar` | Quita ciertas ambigüedades inferidas/flags, conserva `inferred`; DB + `_backup_limpiar_notas_inferidas`. | `--apply`; códigos de inferencia enumerados; conserva discrepancias reales. | Manual; posible concurrente; sin lock. | Backup/hash, temp JSON y replace; backup preexistente no se compara con la base actual. |

### 1.3 Siete writers ya declarados (inventario total = 18)

| Writer / función | Tipo y condición | Destinos/protección conocida | Ejecución live |
|---|---|---|---|
| `hand_editor.py::_guardar_base` | Rewrite de la base entera, edición manual/UI | DB + `.bak`; sin hash pin de DB declarado | Manual; posible simultaneidad, no se halló lock común |
| `recorder/record_hand.py::HandRecorder.finalize_hand` | Append de una mano al cerrar el recorder | DB canónica; no escribe derivados/manifiestos | Sí, evento live previsto |
| `recorder/recorder_live.py::HandRecorder.finalize_hand` | Append de mano(s) y registro de resultado | DB canónica; no escribe derivados/manifiestos | Sí, evento live previsto |
| `tools/aplicar_correcciones.py::aplicar` | Migraciones CM-001/003 y rewrite | CLI/dry-run, backup/hash y reemplazo; manifiestos pueden quedar stale | No automático; posible si se lanza concurrente, sin lock |
| `tools/aplicar_reinterpretacion.py::main` | Reconstruye/reinterpreta DB desde origen pinneado | CLI; valida SHA origen/candidato y backup; no sincroniza manifiesto | Procedimiento manual; sin lock live |
| `tools/sanear_base.py` (`construir`/aplicar) | Saneamiento/rewrite de JSONL | CLI dry-run, backup/temp; manifiesto requiere revisión | Manual; sin lock live |
| `tools/integrar_copia.py` (`integrar`/restore) | Swap temporal de candidato | SHA candidato precondición, backup y restauración verificada en `finally` | Procedimiento/test de integración; no garantiza coordinación con recorder |

Los siete se mantienen declarados para que el test compare el inventario entero
contra el instrumento. Su inclusión no equivale a calificación de “seguro”; el
campo `riesgo` del inventario mantiene la necesidad de control/revisión.

### 1.4 Conclusión de seguridad de writers

- Ninguno de los 11 se ejecuta automáticamente al importar ni desde el camino de
  serving; el instrumento clasifica usos directos/indirectos del path, y los
  scripts ejecutables tienen `main` protegido.
- Cada uno tiene dry-run predeterminado y exige `--apply` para la escritura. La
  prueba P0-6 ejecutó precisamente esa forma predeterminada, nunca `--apply`.
- **Los 11 podrían ejecutarse durante una sesión si una persona los lanza**:
  no hay exclusión/lock compartido con `record_hand` o `recorder_live`. El
  `os.replace` del rewrite y el append live pueden competir; el dry-run no
  prueba concurrencia segura.
- La mayoría verifica el SHA del backup al crearlo, pero si ya existe suele
  conservarlo e imprimirlo sin comprobar que sea snapshot del DB actual. Por
  tanto un backup no es por sí solo una autorización ni una prueba de restore.
- Ninguno de los 11 actualiza derivados/manifiestos/pins. Una edición del DB
  podría dejarlos stale; el script no los sincroniza.
- El riesgo de todos se declara alto/pendiente de control operacional. No se
  marca ninguno “seguro” por falta de evidencia. El test
  `test_cada_escritor_declara_que_escribe_y_donde` requiere `proteccion`,
  `durante_live` y `riesgo` no vacíos.

## 2. Importe común, sin conversión de ausencia a cero

Nuevo módulo común: `motor/action_amount.py`. Distingue estado del valor y
procedencia (dimensiones ortogonales):

| Campo | Valores | Interpretación |
|---|---|---|
| `value_status` | `known_zero`, `known_positive`, `absent`, `invalid` | valor numérico; `None` nunca se convierte a 0.0 |
| `origin_status` | `canonical_observed`, `derived`, `non_canonical`, `unknown` | origen declarado; falta de `amount_type` queda `unknown` |
| `action_inferred` | booleano independiente | inferencia de acción no cambia automáticamente origen del importe |

P0-1 `normalize_actions` y P0-2 `_indexed_seq`/`_raw_action` conservan `None`;
`_advance` no actualiza nivel con un valor ausente. `learn._preflop_sequence`,
`PreflopEvent`, `observations._seq`, `stats._actions` y el helper live
`_is_limp_short` dejaron de coalescer importe ausente a `0.0`. P0-2 Issues,
dependencias, filas de elegibilidad, P0-3 observation trace y P0-1 JSON llevan
los estados de valor/origen. Los consumidores que no necesitan sizing pueden
seguir describiendo la acción, pero la ausencia queda explícita y no aporta al
total ni sizing; las observaciones preflop cuyo categoría depende del importe
se marcan restringidas en la proyección P0-2.

Conocido `b 0.0` estricto → `importe_cero`; `b` sin amount →
`importe_ausente`; texto o no-finito → `importe_invalido`. Un amount numérico
con `amount_type` ausente mantiene su valor, pero su origen es `unknown`; no se
eleva a canónico ni se excluye del camino efectivo existente.

Conteo sobre la base canónica, solo lectura: 16.486 acciones; 7.963 ceros
conocidos/origen desconocido, 7.615 positivos/origen desconocido, 345 ceros y
563 positivos con `amount_type=observed`; 0 ausentes/invalidos. Los otros 15.578
no guardan `amount_type`, por lo que el origen queda `unknown`, no `observed`.
No hay ausencia en la base actual que pudiera cambiar el resultado efectivo.

Pruebas: `test_amount_value_and_origin_are_separate_and_not_imputed` y
`test_amount_absence_survives_preflop_and_p02_consumers` cubren cero, positivo,
ausente, inválido, derivado, no canónico y origen desconocido desde parser a
P0-1/P0-2/Observation. Las correcciones de datos one-off siguen auditadas como
writers y no se ejecutaron ni editaron en P0-6.

## 3. H_0357 — una sola interpretación, sin cambiar el DB

Secuencia raw: SB `p 0.5`; BB `p 1.0`; BB `b 0.5`; CO `f 0`; BTN `f 0`; SB
`b 3.0`; BB `f 0`.

- La primera acción BB establece `current_level=1.0` y `blind_posts` contiene BB.
- La segunda acción de ese mismo BB sucede antes de cualquier acción voluntaria
  y su `0.5` no supera el nivel/posta previa. Hay evidencia suficiente para no
  tratarla como otra ciega ni como un limp; la propia política B1/P0-2 la declara
  `subida_sin_incremento` inválida.
- P0-1 estricto aplica la misma condición: índice 2 → `unresolved`, reason
  `subida_sin_incremento`; el contexto posterior queda tainted. P0-2 mantiene
  el mismo issue raíz invalid y 4 dependientes (índices 3–6).
- La referencia efectiva legacy sigue usando su tratamiento anterior para no
  cambiar estadísticas/etiquetas. P0-2/P0-5 solo anotan y proyectan la
  restricción shadow; no filtran `build_models`.

Regresión: `motor/test_p06_transversal.py::test_h0357_has_one_common_unresolved_root_and_four_dependents`.
`H_0475` y `H_0738` tienen BB `b 1.5` después de la posta: P0-2 solo lo deja
ambiguo y no se generaliza la invalidación de H_0357 a esos casos.

Los recuentos de clasificación estricta cambian de forma explicada: P0-1 pasa a
4512 coincidentes / 49 diferencias / 33 unresolved; los cuatro adicionales
pertenecen a H_0357. Los 49 pares de diferencias legacy se mantienen.

## 4. Etiquetas: elegibilidad P0-2 y compatibilidad de procedencia

P0-5 calcula una **proyección sombra por evento** para `preflop_stats`, VPIP/PFR
y `profile_range`, guardando por jugador IDs, categoría, posición, razón y root
P0-2. El candidato usa `(opp, act)` tras restar solo los eventos que P0-2 marca
restringidos; no excluye manos/jugadores enteros ni se pasa a `build_models`.
La proyección de stack guarda filas numéricas, cero, ausentes e inválidas; los
stacks faltantes no se imputan. El candidato usa la media de filas numéricas
elegibles, y prueba que coincide con el n usado por el perfil.

En la ventana: 6 eventos restringidos P0-2 en 6 nombres (`CamiloG208`,
`HarryPoker18`, `Jarduan`, `pardoKing`, `vidents`, `RABBUNI`). Las etiquetas
candidatas shadow siguen iguales a las efectivas para los 138 jugadores; no hay
flip en este dataset al quitar esas filas. Esto no es licencia para usar el dato
restringido. Efectivas y candidatas: 78 PEZ/60 TIBURON, hash efectivo
`dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060`.

`label_provenance_compatible` exige simultáneamente: origen
`rebuilt_from_current_base`, status `verified`, `reliable_only`, base hash,
window hash, 877 manos, commit y árbol limpio.
`partial`, `unknown`, `incompatible`, histórico o metadato faltante jamás se
eleva por deterministicidad. Los campos quedan separados:

| Campo | Qué demuestra | Qué no demuestra |
|---|---|---|
| `reproducible` | el clasificador repite el resultado con sus inputs | evidencia elegible o procedencia compatible |
| `evidence_eligible` | los inputs requeridos pasan la proyección P0-2 | procedencia del dataset |
| `provenance_compatible` | regla explícita P0-4 de base/ventana/commit | suficiencia de muestra |
| `valid_for_serving` | conjunción de evidencia elegible, provenance compatible y muestra del estado aceptado | no es leído por producción |

Resultado actual: 138 reproducibles; 138 evidencia elegible en la proyección;
0 procedencia compatible porque el source actual permanece `partial`; 0
`valid_for_serving`; 138 `contract_label=UNKNOWN`. `label` sigue guardando la
etiqueta efectiva exclusivamente para comparación. Los históricos conservan su
`label` y posible `reproducible=True` desde campos, pero siempre
`contract_label=UNKNOWN`, evidencia elegible false y validez serving false.
`HERO` sigue incompatible/no reproducible con evidencia actual.

Pruebas: `motor/test_label_contract.py` cubre fallback efectivo separado de
`UNKNOWN`, proyección P0-2, `partial`/unknown/incompatible fail-closed y caso
histórico reproducible sin promoción a serving.

## 5. Range lab falla cerrado

`tools/range_lab_gui.py::load_models()` revisa antes de cargar. Si existe
cualquiera de `data/profile_ranges.json` o `data/postflop_ranges.json`, lanza un
`RuntimeError` explicando que los persistidos no tienen compatibilidad
verificada; no carga el rango histórico ni reinyecta Oracle actual. Si ambos
faltan, el fallback construye los modelos desde el mismo input, sin convertir
`partial` en `verified`. Sigue declarado `not_suitable`.

Prueba: `test_range_lab_fails_closed_instead_of_mixing_current_and_historical`.
No se regeneraron, borraron ni alteraron esos JSON.

## 6. Pruebas, fingerprints y no intervención

### Pruebas enfocadas

```text
python -m pytest motor/test_label_contract.py motor/test_p06_transversal.py -q
33 passed

python -m pytest motor/test_preflop_contract.py motor/test_field_eligibility.py \
  motor/test_observations.py motor/test_stats.py motor/test_learn.py \
  motor/test_asistente_live.py motor/test_postflop_evidence.py \
  motor/test_provenance_contract.py motor/test_quien_escribe.py \
  motor/test_p06_transversal.py -q
263 passed, 1 xfailed
```

```text
python -m pytest motor/test_label_contract.py motor/test_p06_transversal.py -q
34 passed
```

Las dos advertencias son las pruebas preexistentes de `_prior_grid`/
`FLAT_PRIOR=0.15`.

### Suite completa y clasificación individual

Repetición final: `python -m pytest motor -q` → **1047 passed, 1 skipped,
6 xfailed, 22 failed**. Las 22 siguen fijando el corte histórico de 1.253 manos;
se reprobaron los valores emblemáticos en memoria sobre las primeras 1.253
líneas actuales (sin copia ni escritura). Son expectativas antiguas/scope
desactualizado, no fallos P0-6:

| # | Prueba | Esperado → actual | Clasificación |
|---:|---|---|---|
| 1 | `test_accion_p::test_la_base_de_hoy_ya_usa_p` | 2522 → 2702 `p` | snapshot de 1.253; prefijo actual reproduce 2522 |
| 2 | `test_auditar_origen::test_las_cifras_de_posiciones_estan_fijadas` | 1253 → 1344 manos | alcance histórico fijo |
| 3 | `test_auditar_origen::test_un_jugador_sin_pos_es_uno_que_no_jugo` | 804 → 861 | prefijo da 804 |
| 4 | `test_auditar_origen::test_no_hay_mesa_corta_ni_ante_ni_straddle` | 1253 → 1344 | alcance histórico fijo |
| 5 | `test_auditar_origen::test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | 1253 → 1344 BB | prefijo da 1253 |
| 6 | `test_auditar_origen::test_las_calls_que_no_llegan_a_la_viva` | 42 → 47 | prefijo da 42; 5 casos del resto de la base no atribuidos aquí |
| 7 | `test_auditar_origen::test_el_patron_del_bb_es_exacto_no_aproximado` | 52 → 60 | prefijo da 52 |
| 8 | `test_auditar_origen::test_el_bote_exacto_cuadra_en_373_de_1253` | 373 → 394 | prefijo da 373 |
| 9 | `test_auditar_origen::test_el_rake_no_explica_el_bote` | 373 → 394 | prefijo da 373 |
| 10 | `test_auditar_origen::test_aportar_mas_que_el_stack_no_depende_del_rake` | 12 → 13 | prefijo da 12; caso adicional no investigado |
| 11 | `test_auditar_origen::test_el_json_y_el_informe_cuentan_lo_mismo` | 1253 → 1344 | alcance histórico fijo |
| 12 | `test_cm004::test_el_invariante_de_cm004_puede_dispararse` | 1253 → 1344 | prefijo reconoce 1253; regla no modificada |
| 13 | `test_diagnostico_grabador::test_la_base_son_dos_grabadores` | 1182 con allin → 1273 | prefijo: 1182 live + 71 manual |
| 14 | `test_diagnostico_grabador::test_la_apertura_cambia_tras_la_normalizacion` | live `100/520/467` → `100/561/514` | prefijo reproduce valores esperados |
| 15 | `test_diagnostico_grabador::test_las_42_calls_por_debajo_de_la_viva` | 2603 → 2832 calls | prefijo da 2603 |
| 16 | `test_diagnostico_grabador::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | 42 → 47 | prefijo da 42; casos adicionales no atribuidos |
| 17 | `test_diagnostico_grabador::test_la_clasificacion_sobre_la_base` | 5001 → 5417 calculables | prefijo: 5001/29/23 calculables/sospechosas/indeterminadas |
| 18 | `test_diagnostico_grabador::test_el_desglose_por_accion_por_resultado_es_coherente` | matriz `1444/2559/998` y estados → matriz de 1344 | prefijo reproduce matriz histórica |
| 19 | `test_diagnostico_grabador::test_el_reparto_por_accion_suma_el_total_de_la_base` | `b/c/r=1448/2603/1002` → `1545/2832/1099` | prefijo reproduce `1448/2603/1002` |
| 20 | `test_diagnostico_grabador::test_los_ids_se_resuelven_con_el_boton` | 204 → 221 IDs | prefijo resuelve 204; 46 confirmados |
| 21 | `test_lista_saneamiento::test_por_defecto_cubre_toda_la_base` | 1253 → 1344 | alcance histórico fijo |
| 22 | `test_lista_saneamiento::test_el_rango_por_defecto_sigue_siendo_toda_la_base` | 1253 → 1344 | alcance histórico fijo |

La falla 23 de P0-5 (`test_quien_escribe::test_el_inventario_coincide_con_el_instrumento`)
ya no aparece: se amplió el inventario declarado a los 18 paths que el
instrumento detecta y se añadieron campos de riesgo/protección. No se cambiaron
las 22 expectativas de datos sin justificar ni se marcaron como verdes.

### No intervención efectiva

- `model_fingerprint`: `profile_range=1070d92669a90818b50a940ac4202ecb796ec27e06aa129db5d83849c425e7f9`;
  `oracle=50b254d7cce40ad3b9a97dc156505624aeeb3745d312335fd43b6e3f73f6edf5`;
  `postflop_range=0369560a2da2f4b1a2c9eb75ff3306d8ddfd24360354c7f5ec36434b5829d413`.
- Labels efectivas: 78 PEZ / 60 TIBURON, hash `dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060`.
- P0-3 mantiene fingerprints de tablas, las 580 estimaciones y Oracle; el
  importe sidecar no entra a `opp`, `cnt`, shrinkage ni `p_action`.
- P0-1 y P0-3 mantienen pruebas deterministas de EV/acción/texto; P0-6 no
  conecta `label_contract` a serving. Además,
  `test_all_five_audits_leave_deterministic_recommendation_unchanged` toma
  snapshot de distribución Oracle, vectores/rangos/labels, ejecuta los cinco
  auditores y compara snapshot más texto visible, mapa EV y acción elegida antes
  y después: todos iguales.
- Los tests de P0-2/P0-6 verifican modelos iguales con/sin hook y todos los
  ficheros en `data/` sin cambios en auditoría/dry-runs.

## 7. Archivos y restricciones

Modificados: contratos/utilidades de importe, proyección P0-2 → P0-5, guard
`range_lab_gui`, pruebas y documentación. Ninguno de los 11 writers investigados
se modificó. No se cambió la base, derivados, hashes, manifiestos, pins, ventana
877, matrices, rangos, priors, selección efectiva, probabilidades, etiquetas
efectivas ni recomendaciones. `MULTIWAY_SOPORTADO=False` sigue intacto.

No se ejecutaron `--apply`, generación de derivados, B2, calibraciones ni
sesiones reales. No se activó P0-1…P0-5.

**P0-6 se detiene aquí para revisión.** No se activa ningún contrato ni se
continúa a otro bloque sin autorización explícita.
