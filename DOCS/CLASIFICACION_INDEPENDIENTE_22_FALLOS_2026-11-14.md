# Clasificación independiente de los 22 fallos de la suite completa

**Fecha:** 2026-11-14  
**Estado:** auditoría de solo lectura, terminada. No se corrige ningún fallo, no se actualizan tests, no se regeneran datos ni artefactos y no se inicia PR-03.  
**Base auditada:** `data/hands_db.jsonl` en `HEAD = 3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96`, 1344 líneas, SHA-256 `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.  
**Referencia histórica:** blob de `51a6fb9:data/hands_db.jsonl`, 1253 líneas, SHA-256 `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`.

---

## 1. Resumen ejecutivo

Los 22 fallos son reales, deterministas y reproducibles. No son una regresión de código, no dependen del orden de ejecución y no proceden de un artefacto derivado desactualizado: los 22 tests leen `data/hands_db.jsonl` directa o indirectamente.

La causa común es una **base canónica nueva con 91 manos más** que la base sobre la que se fijaron las expectativas. El subconjunto de las 1253 manos antiguas, dentro del fichero actual de 1344, reproduce **exactamente** todos los valores que esperan los 22 tests. Las diferencias aparecen solo al añadir las 91 manos nuevas.

La clasificación principal es:

- **19 fallos:** `DATOS_CAMBIADOS_LEGITIMAMENTE`; el test conserva un pin numérico de la base de 1253 y no contempla la adopción de la base de 1344. Llevan `TEST_OBSOLETO` como causa secundaria.
- **3 fallos:** `TEST_OBSOLETO` como causa principal:
  - el patrón de primeras calls SB/BB (test 7) no es un invariante estable;
  - el invariante I4 (test 10) convierte `stack: null` en `0.0`;
  - la comprobación de consistencia JSON/informe (test 11) lleva el literal `1253` dentro de la propia consistencia.

No hay ningún caso principal de `REGRESION_CODIGO`, `ARTEFACTO_DESACTUALIZADO`, `TEST_DEPENDIENTE_DEL_ESTADO` ni `OTRA_CAUSA`.

La base de 1344 está adoptada como **registro canónico con excepción de procedencia B**, no como base de calibración validada. “Legítimamente” significa aquí que el cambio de fuente está documentado y adoptado, no que las 91 manos nuevas estén libres de limitaciones. De hecho, hay defectos y limitaciones localizadas ya documentados en B1-E, y dos calls cortas nuevas (`H_1303`, `H_1365`) que B1-E no adjudica individualmente como defecto de secuencia. Esas limitaciones son relevantes para el valor futuro de algunos tests, pero no convierten los 22 fallos en una regresión de código.

No se ha modificado ningún dato, test, código, matriz ni artefacto. El único fichero nuevo es este informe.

---

## 2. Estado Git y hashes iniciales

### 2.1 HEAD y estado de trabajo

- `HEAD`: `3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96`
- `git status --short data`: vacío.
- `POKER_DB_PATH`, `PYTHONPATH` y `PYTEST_ADDOPTS`: vacíos.
- No se creó ningún commit.

El árbol de trabajo ya contenía cambios y ficheros no rastreados de PR-02B. Se conservaron sin tocarlos:

```text
 M DOCS/CONTRATOS_RANGO_EQUITY_EV_2026-11-13.md
 M DOCS/DISENO_TECNICO_MW_INTERFACES_2026-11-13.md
 M DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md
 M DOCS/ESPECIFICACION_CONTRATO_PREFLOP_2026-11-13.md
 M DOCS/MATRIZ_PRUEBAS_ACEPTACION_2026-11-13.md
 M DOCS/MIGRACION_ROLLBACK_PREFLOP_2026-11-13.md
 M DOCS/PLAN_IMPLEMENTACION_INCREMENTAL_2026-11-13.md
 M DOCS/POLITICA_COBERTURA_INCERTIDUMBRE_2026-11-13.md
 M motor/asistente_live.py
 M motor/preflop_contract.py
 M motor/test_preflop_cobertura.py
?? DOCS/CIERRE_PR_02B_2026-11-14.md
?? motor/preflop_coverage.py
?? motor/test_preflop_canonical_contracts.py
?? motor/test_preflop_coverage.py
```

### 2.2 Hashes de datos y artefactos

Solo `data/hands_db.jsonl` es entrada de los 22 tests. Los demás ficheros se hashearon como control de no modificación; no se usaron como fuente de verdad.

| Fichero | SHA-256 inicial | SHA-256 final |
|---|---|---|
| `data/hands_db.jsonl` | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| `data/preflop_matrices.json` | `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1` | `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1` |
| `data/calibration_window.json` | `7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1` | `7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1` |
| `data/decisions.jsonl` | `c6f8a18db358f3071fab7d5c4a17d3e1fdd88d17c54ce345592af9b5dd7ab841` | `c6f8a18db358f3071fab7d5c4a17d3e1fdd88d17c54ce345592af9b5dd7ab841` |
| `data/observations.json` | `86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3` | `86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3` |
| `data/profiles.json` | `24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b` | `24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b` |
| `data/profile_ranges.json` | `add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa` | `add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa` |
| `data/postflop_ranges.json` | `1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c` | `1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c` |
| `data/preflop_stats.json` | `53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749` | `53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749` |
| `data/behavior.json` | `efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae` | `efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae` |
| `data/behavior_probs.json` | `5de905ca0d4e3a25b0b16dd5db85e6de376711762bb52f3c1280dd6a16a05a1a` | `5de905ca0d4e3a25b0b16dd5db85e6de376711762bb52f3c1280dd6a16a05a1a` |

### 2.3 Manifiesto y hashes de control del código

`motor/learn.py` declara:

```python
HANDS_DB_COMMIT = '8594ed5'
HANDS_DB_SHA256 = '3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e'
HANDS_DB_LINEAS = 1344
```

Los tests y helpers que intervienen no se modificaron durante la auditoría:

| Fichero | SHA-256 |
|---|---|
| `motor/test_accion_p.py` | `847048ac85552a715a2ac65c304b23d74536c406fe79f06dd44316ef5c55788d` |
| `motor/test_auditar_origen.py` | `349035d0de6ef61454a6b48a440ec802192d47f3b975ae1d3ad4dba6ef17b04a` |
| `motor/test_cm004.py` | `e35cd705183e94f62b812bcec880e44de86768c4f13eddcfe36542746ce3efce` |
| `motor/test_diagnostico_grabador.py` | `6d58a170d07724076e1be8ca080297d6737cf55ce581fdd67febde19d3be2dbb` |
| `motor/test_lista_saneamiento.py` | `e7c2317f1a494850e1ad9139cbb089b2025ba5cd71261f3c19ca3af500a89047` |
| `tools/auditar_origen.py` | `6fd6b329b94f3d47e641b86187c49c520adb26eab042cad525a18ae292d31a82` |
| `tools/diagnostico_grabador.py` | `aceb6223f175dcb97d471ac7f1793aeb122b44262b8bb39007c412019b8029d5` |
| `tools/lista_saneamiento.py` | `4af5a617cd8cb0aabf8fa11f4ee4af2ff635a7ed9c72ac098a741974378211d8` |
| `motor/learn.py` | `9f1201ed5effdda1019be74dd0eb0b90c87b9bcef6b2707f09bc200785e60c89` |

---

## 3. Comandos y condiciones de reproducción

### 3.1 Suite completa

Se ejecutó la suite completa de `motor` en condiciones controladas, sin caché de pytest y sin escribir bytecode:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest motor -q --tb=no -p no:cacheprovider
```

Resultado:

```text
22 failed, 1222 passed, 1 skipped, 6 xfailed, 6 warnings in 191.57s (0:03:11)
```

Los 22 nodeids que fallan son exactamente los mismos que registró el cierre de PR-02B. El recuento de aprobados es 1222 frente a 1221 del cierre: hay un test aprobado más, no un fallo distinto. Esa diferencia de +1 no pertenece a los 22 y no se atribuye a este análisis.

Salida completa conservada en:

```text
C:\Users\Jorgito\AppData\Local\Temp\opencode\audit22_full_motor.txt
```

### 3.2 Reproducción individual

Cada uno de los 22 nodeids se ejecutó por separado con:

```powershell
python -m pytest <nodeid> -q --tb=long -p no:cacheprovider
```

Los 22 fallan también de forma aislada. Las salidas completas están en:

```text
C:\Users\Jorgito\AppData\Local\Temp\opencode\audit22\
```

### 3.3 Reproducción conjunta

Los 22 nodeids se ejecutaron juntos, en una sola invocación:

```text
22 failed in 3.62s
```

Salida conservada en:

```text
C:\Users\Jorgito\AppData\Local\Temp\opencode\audit22_together.txt
```

No se observó dependencia de orden: los 22 fallan aislados y juntos, y los tests son de solo lectura.

### 3.4 Controles que siguen pasando

Se ejecutaron seis tests de control de invariantes y casos concretos:

```text
6 passed in 2.17s
```

Incluyen:

- `motor/test_cm004.py::test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega`
- `motor/test_cm004.py::test_el_invariante_tiene_algo_que_mirar`
- `motor/test_auditar_origen.py::test_h001_es_el_ejemplo_del_informe`
- `motor/test_auditar_origen.py::test_h0546_ya_no_tiene_un_bote_que_no_aparece`
- `motor/test_diagnostico_grabador.py::test_h0546_el_allin_apunta_al_que_se_fue`
- `motor/test_lista_saneamiento.py::test_la_violacion_de_cm004_es_cero_y_el_cierre_esta_escrito`

Esto confirma que el invariante CM-004 sigue midiendo cero violaciones y que los casos concretos siguen bien; lo que falla es el pin de cobertura de 1253, no la regla.

### 3.5 Método de cálculo independiente

Los recuentos no se tomaron de los números declarados por los tests. Se recalcularon:

1. desde el JSONL actual, con `json.loads` línea a línea;
2. desde el blob histórico `git show 51a6fb9:data/hands_db.jsonl`;
3. desde el subconjunto de las 1253 manos antiguas dentro del fichero actual;
4. con las mismas funciones de producción que usan los tests (`AO.seccion_1`, `AO.seccion_2c`, `AO.seccion_3`, `AO.seccion_3c`, `DG.apuesta_viva`, `DG.calls_por_debajo`, `DG.clasificar_aportado`, `LS.construir`, `learn._es_ciega_bb`), pero sin usar sus literales como verdad.

Los desgloses de 1253 y 1344 se compararon con las constantes de los tests. El subconjunto de 1253 reproduce **todas** las constantes esperadas; las diferencias de 1344 son exactamente las aportadas por las 91 manos nuevas.

### 3.6 Comprobación de no modificación

Después de la suite completa y de las reproducciones, los hashes de `data/hands_db.jsonl` y de los artefactos de control siguen siendo los de la tabla §2.2. `git status --short data` sigue vacío.

---

## 4. Tabla individual de los 22 fallos

La columna “Causa principal” resume el dato decisivo. La evidencia individual completa está en §7; los mensajes de error reproducidos están en el Anexo A.

Códigos de clasificación:

- `DCL` = `DATOS_CAMBIADOS_LEGITIMAMENTE`
- `TO` = `TEST_OBSOLETO`
- `DCP` = `DATOS_CON_PROBLEMA`
- `CA` = `CONTRATO_AMBIGUO`
- `ART` = `ARTEFACTO_DESACTUALIZADO`
- `REG` = `REGRESION_CODIGO`
- `TDE` = `TEST_DEPENDIENTE_DEL_ESTADO`
- `OTRA` = `OTRA_CAUSA`

| # | Nodeid | Línea | Esperado (1253) | Obtenido (1344) | Causa principal | Clasificación | Confianza |
|---:|---|---:|---|---|---|---|---|
| 1 | `motor/test_accion_p.py::test_la_base_de_hoy_ya_usa_p` | 208 | `{'preflop': 2522}` | `{'preflop': 2702}` | +180 `p` preflop en las 91 manos nuevas | `DCL` / `TO` | Alta |
| 2 | `motor/test_auditar_origen.py::test_las_cifras_de_posiciones_estan_fijadas` | 127 | `len=1253`, `con_BB=1253`, `con_SB=1220`, `sin_SB=33` | `len=1344`, `con_BB=1344`, `con_SB=1309`, `sin_SB=35` | +91 manos; +89 SB; +2 sin SB (`H_1300`, `H_1369`) | `DCL` / `TO` | Alta |
| 3 | `motor/test_auditar_origen.py::test_un_jugador_sin_pos_es_uno_que_no_jugo` | 161 | `sin_pos=804`, `con_accion=0` | `sin_pos=861`, `con_accion=0` | +57 entradas de jugador sin `pos` en manos nuevas; la propiedad “sin posición no actúa” sigue | `DCL` / `TO` | Alta |
| 4 | `motor/test_auditar_origen.py::test_no_hay_mesa_corta_ni_ante_ni_straddle` | 183 | `{6: 1253}` | `{6: 1344}` | 91 manos nuevas, todas de 6 jugadores; el resto de la prueba pasa | `DCL` / `TO` | Alta |
| 5 | `motor/test_auditar_origen.py::test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | 214 | `BB {1.0: 1253}`, `SB {0.5: 1220}` | `BB {1.0: 1344}`, `SB {0.5: 1309}` | +91 BB y +89 SB; todos los importes e índices siguen válidos | `DCL` / `TO` | Alta |
| 6 | `motor/test_auditar_origen.py::test_las_calls_que_no_llegan_a_la_viva` | 302 | `total=42`, preflop/flop/turn/river `8/12/12/10` | `total=47`, `10/14/13/10` | +5 calls en `H_1287`, `H_1303`, `H_1310` (2) y `H_1365` | `DCL` / `DCP`, `CA` | Alta causa; media valor futuro |
| 7 | `motor/test_auditar_origen.py::test_el_patron_del_bb_es_exacto_no_aproximado` | 368 | `52` parejas; `{-8.0:1, 0.0:51}` | `60`; `{-28.0:1, -8.0:1, -2.0:1, 0.0:57}` | `-28` es artefacto de comparar primera call SB (limp) con primera call BB (call de subida) en `H_1365`; `-2` es `H_1310` | `TO` / `DCL`, `DCP`, `CA` | Alta |
| 8 | `motor/test_auditar_origen.py::test_el_bote_exacto_cuadra_en_373_de_1253` | 398 | `exactas=373`, `falta=3`, `sobra=877` | `exactas=394`, `falta=3`, `sobra=947` | +21 exactas y +70 sobrantes en manos nuevas; `falta` no cambia | `DCL` / `TO` | Alta |
| 9 | `motor/test_auditar_origen.py::test_el_rake_no_explica_el_bote` | 425 | `sin_rake=373`, `con_rake=268` | `sin_rake=394`, `con_rake=270` | +21 exactas sin rake y +2 con rake; la relación `con_rake < sin_rake` sigue | `DCL` / `TO` | Alta |
| 10 | `motor/test_auditar_origen.py::test_aportar_mas_que_el_stack_no_depende_del_rake` | 436 | `I4=12`, `I2=3`, `I1=true` | `I4=13`, `I2=3`, `I1=true` | `H_1349` tiene `UTG.stack=None`; el helper lo convierte en `0.0` y suma 3.0 | `TO` / `DCL`, `CA` | Alta |
| 11 | `motor/test_auditar_origen.py::test_el_json_y_el_informe_cuentan_lo_mismo` | 498 | sumas SB/BB `=1253` | sumas SB/BB `=1344` | la consistencia interna sigue; solo falla el literal `1253`; la primera aserción (total = exactas+sobra+falta) pasa | `TO` / `DCL` | Alta |
| 12 | `motor/test_cm004.py::test_el_invariante_de_cm004_puede_dispararse` | 516 | `CIEGAS_RECONOCIDAS=1253` | `con_ciega=1344` | las 91 manos nuevas también tienen ciega BB reconocida; la regla sigue activa | `DCL` / `TO` | Alta |
| 13 | `motor/test_diagnostico_grabador.py::test_la_base_son_dos_grabadores` | 642 | `con=1182`, `sin=71` | `con=1273`, `sin=71` | las 91 nuevas tienen campo `allin`; el grupo `record_hand` de 71 no cambia | `DCL` / `TO` | Alta |
| 14 | `motor/test_diagnostico_grabador.py::test_la_apertura_cambia_tras_la_normalizacion` | 680 | `hand 31/29/4`, `live b=100,c=520,r=467` | `hand 31/29/4`, `live b=100,c=561,r=514` | +41 `c` y +47 `r` en el grupo live; `b` y el grupo hand no cambian | `DCL` / `TO` | Alta |
| 15 | `motor/test_diagnostico_grabador.py::test_las_42_calls_por_debajo_de_la_viva` | 780 | `total=2603`, `cortas=42` | `total=2832`, `cortas=47` | +229 calls y +5 cortas por las manos nuevas | `DCL` / `DCP`, `CA` | Alta causa; media valor futuro |
| 16 | `motor/test_diagnostico_grabador.py::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | 796 | `len=42`, `uno=3`, `BB=10` | `len=47`, `uno=3`, `BB=10` | solo cambia el total; las demás conclusiones siguen | `DCL` / `DCP`, `CA` | Alta causa; media valor futuro |
| 17 | `motor/test_diagnostico_grabador.py::test_la_clasificacion_sobre_la_base` | 809 | `CALC=5001`, `SOSP=29`, `INDET=23` | `CALC=5417`, `SOSP=33`, `INDET=26` | +423 acciones clasificadas en manos nuevas | `DCL` / `TO` | Alta |
| 18 | `motor/test_diagnostico_grabador.py::test_el_desglose_por_accion_por_resultado_es_coherente` | 838 | matriz `b 1444/4`, `c 2559/21/23`, `r 998/4`; total `5053` | matriz `b 1541/4`, `c 2781/25/26`, `r 1095/4`; total `5476` | +423 acciones; la estructura de filas/columnas sigue coherente | `DCL` / `TO` | Alta |
| 19 | `motor/test_diagnostico_grabador.py::test_el_reparto_por_accion_suma_el_total_de_la_base` | 870 | `b=1448`, `c=2603`, `r=1002`, suma `5053` | `b=1545`, `c=2832`, `r=1099`, suma `5476` | +97 `b`, +229 `c`, +97 `r` en manos nuevas | `DCL` / `TO` | Alta |
| 20 | `motor/test_diagnostico_grabador.py::test_los_ids_se_resuelven_con_el_boton` | 930 | `resueltos=204`, `confirmados=46` | `resueltos=221`, `confirmados=49` | +17 IDs resueltos y +3 confirmados en manos nuevas | `DCL` / `TO` | Alta |
| 21 | `motor/test_lista_saneamiento.py::test_por_defecto_cubre_toda_la_base` | 190 | `manos=1253` | `manos=1344` | el rango por defecto cubre toda la base actual; solo cambia el total | `DCL` / `TO` | Alta |
| 22 | `motor/test_lista_saneamiento.py::test_el_rango_por_defecto_sigue_siendo_toda_la_base` | 270 | `manos=1253`; `H_1282` presente | `manos=1344`; `H_1282` presente | el rango sigue llegando a `H_1282`; solo cambia el total | `DCL` / `TO` | Alta |

---

## 5. Procedencia de las expectativas y de los datos

### 5.1 Cronología

| Commit | Fecha | Líneas | Hecho |
|---|---|---:|---|
| `51a6fb9` | 2026-10-25 | 1253 | Repara contratos de asiento y re-baselina pins. `test_auditar_origen` y `test_diagnostico_grabador` quedan con las constantes de 1253. |
| `b358d26` | 2026-10-25 | 1253 | Re-ancla F7.2; ajusta `test_accion_p` a 2522 `p`, `test_cm004` y `test_lista_saneamiento` a 1253. |
| `8b44917` | 2026-10-29 | 1298 | Importa 45 manos: `H_1283`–`H_1327`. |
| `44acddb` | 2026-11-04 | 1298 | 98 cambios semánticos y 21 cambios de campos no accionales; no cambia el número de líneas. |
| `c1c1370` | 2026-11-04 | 1345 | Importa 47 manos: `H_1328`–`H_1374`. |
| `8594ed5` | 2026-11-10 | 1344 | Elimina `H_1323`; anota `H_1303`/`H_1351`; corrige resultados. |
| `6ad9987` | 2026-11-11 | 1344 | Registra la base de 1344 como canónica con excepción B; actualiza solo manifiesto y documentación. |

Los cinco ficheros de test afectados no se tocaron después de `b358d26`. Entre `b358d26` y `HEAD` no hay ningún commit sobre:

```text
motor/test_accion_p.py
motor/test_auditar_origen.py
motor/test_cm004.py
motor/test_diagnostico_grabador.py
motor/test_lista_saneamiento.py
```

Por tanto, las expectativas son históricas: se fijaron sobre 1253 y no se actualizaron al adoptar 1344. El commit `6ad9987` actualizó el manifiesto y la documentación de adopción, pero no los cinco ficheros de test.

### 5.2 Composición de la base actual

- `data/hands_db.jsonl`: 1344 líneas, 1344 `hand_id` únicos, sin duplicados.
- 1253 IDs antiguos + 91 IDs nuevos.
- Los 91 nuevos son:
  - 45 de `8b44917`: `H_1283`–`H_1327`;
  - 47 de `c1c1370`: `H_1328`–`H_1374`;
  - menos `H_1323`, eliminada en `8594ed5`.
- Neto: `45 + 47 - 1 = 91`.
- Fechas de las manos nuevas: 2026-10-29 y 2026-11-04.

La eliminación de `H_1323` está documentada en B1-E y no deja referencias activas ni decisiones huérfanas.

### 5.3 Adopción documentada

`DOCS/CANAL_MANUAL_CERRADO.md` declara:

- commit canónico `8594ed5`;
- SHA-256 `3f0e7e5e...`;
- 1344 líneas;
- revisión manual de `H_0001`..`H_1282` cerrada el 2026-10-15;
- 45+47 manos importadas y 98 modificaciones semánticas no verificadas visualmente en bloque; 23 manos sí verificadas en B1-R;
- calibración de 877 provisional, no validada;
- derivados canónicos congelados sobre 1253, no regenerados sobre 1344.

`DOCS/B1_EXCEPCION_PROCEDENCIA.md` documenta la adopción con excepción B y las limitaciones de campo. “Legítimamente” en este informe significa exactamente eso: cambio de fuente documentado y adoptado, con limitaciones declaradas; no significa base de calibración validada ni ausencia de defectos.

### 5.4 El subconjunto de 1253 reproduce todas las expectativas

Este es el control decisivo. Si se toman las 1253 manos antiguas **dentro del fichero actual** y se aplican las funciones de producción actuales, se obtienen exactamente las constantes de los tests:

| Métrica | Subconjunto 1253 del fichero actual | Constante esperada |
|---|---:|---:|
| Manos | 1253 | 1253 |
| `p` preflop | 2522 | 2522 |
| `con_SB` / `sin_SB` | 1220 / 33 | 1220 / 33 |
| `con_BB` / `sin_BB` | 1253 / 0 | 1253 / 0 |
| `sin_pos` / `con_accion` | 804 / 0 | 804 / 0 |
| `allin` con / sin | 1182 / 71 | 1182 / 71 |
| Primer acción live `b/c/r` | 100 / 520 / 467 | 100 / 520 / 467 |
| Calls AO bajo vivo | 42 | 42 |
| Pares SB/BB | 52; `-8:1`, `0:51` | 52; `-8:1`, `0:51` |
| Bote exactas / falta / sobra | 373 / 3 / 877 | 373 / 3 / 877 |
| I4 / I2 / I1 | 12 / 3 / true | 12 / 3 / true |
| DG calls total / cortas | 2603 / 42 | 2603 / 42 |
| DG clasificación | 5001 / 29 / 23 | 5001 / 29 / 23 |
| DG matriz total | 5053 | 5053 |
| DG IDs resueltos / confirmados | 204 / 46 | 204 / 46 |
| CM-004 ciega reconocida | 1253 | 1253 |
| Rake sin / con | 373 / 268 | 373 / 268 |
| Lista saneamiento | 1253, “todas” | 1253 |

Esto también demuestra que los 98 cambios semánticos de `44acddb` no mueven ninguno de los agregados fijados: el subconjunto antiguo del fichero actual sigue dando los valores históricos. Las diferencias son solo las 91 manos nuevas.

---

## 6. Recuentos independientes y reconciliación

### 6.1 Definiciones y fuentes

| Recuento | Definición aplicada | Fuente / función | Limitación |
|---|---|---|---|
| Manos | Líneas JSON válidas con `hand_id` único | `data/hands_db.jsonl` | No se valida visualmente cada mano. |
| `p` preflop | Acciones `action == 'p'` en `streets.preflop.actions` | JSONL directo; `learn.load_hands` | `p` es la codificación normalizada de ciegas/limps; no equivale a “pass” voluntario. |
| `p` por posición | `pos` de cada `p` preflop | JSONL directo | `pos` vacía no se asigna. |
| SB/BB inventory | Presencia de posting `p` de SB/BB por mano | `AO.seccion_1` | “Sin SB” puede ser una captura incompleta, no una mano inválida. |
| `sin_pos` | Entradas de `players` sin `pos` | JSONL directo | Cuenta entradas, no jugadores activos únicos; B1-E cuenta “activos” con otro criterio. |
| `allin` | Presencia de la clave `allin` en el dict | JSONL directo | Presencia de clave no equivale a all-in real; 74 de las nuevas tienen lista vacía. |
| Primer acción live | Primera `b/c/r` preflop por mano, agrupada por presencia de `allin` | JSONL directo | `f`/`x`/`p` no cuentan. |
| Calls AO bajo vivo | `c` con `amount < viva` en la calle | `AO.acciones`, misma lógica del test | Un `c` parcial, un all-in corto y un undercall verdadero se cuentan igual. |
| Pares SB/BB | Primera `c` de SB menos primera `c` de BB | `AO.seccion_2c` | Compara importes que pueden pertenecer a niveles distintos (limp vs call de subida). |
| Bote exacto/falta/sobra | `final_pot` contra aportado total, con tolerancia 0.005 | `AO.seccion_3` | `final_pot` puede ser `NADA` o estar limitado; no es calibración. |
| I4 | Aportado total > stack inicial | `AO.seccion_3c` | `stack: null` se convierte en `0.0`; por eso `H_1349` cuenta. |
| DG calls | Calls y calls cortas por calle | `DG.apuesta_viva`, `DG.calls_por_debajo` | Misma ambigüedad de `amount` parcial/all-in. |
| DG clasificación | `CALCULABLE` / `SOSPECHOSA` / `INDETERMINADA` por acción que aporta | `DG.clasificar_aportado` | Es una clasificación de evidencia, no una verdad de la mano. |
| DG IDs | IDs `allin` resueltos con botón y confirmados por compromiso | `record_hand.PLAYER_IDS`, `get_position` | `stack: null` se salta; no se fuerza. |
| CM-004 | Manos con ciega BB reconocida por `_es_ciega_bb` | `learn._preflop_sequence`, `_es_ciega_bb` | Cuenta cobertura de la regla, no corrección de la mano. |
| Rake | `final_pot == aportado` o `aportado - min(5%, 2.5)` | `AO.aportar_por_jugador` | Es una regla del mantenedor, no una conciliación contable. |
| Lista saneamiento | Manos cubiertas por el rango por defecto | `LS.construir` | El rango por defecto es toda la base; no decide calidad. |

### 6.2 Reconciliación 1253 → 1344

| Métrica | 1253 | 1344 | Δ | Atribución |
|---|---:|---:|---:|---|
| Manos | 1253 | 1344 | +91 | 45 + 47 − `H_1323` |
| `p` preflop | 2522 | 2702 | +180 | 89 nuevas con 2 `p`; `H_1300` y `H_1369` con 1 `p` |
| `p` SB | 1220 | 1309 | +89 | 89 nuevas con SB |
| `p` BB | 1253 | 1344 | +91 | todas las nuevas tienen BB |
| `sin_SB` | 33 | 35 | +2 | `H_1300`, `H_1369` |
| `sin_pos` | 804 | 861 | +57 | entradas sin `pos` en nuevas |
| `allin` con / sin | 1182 / 71 | 1273 / 71 | +91 / 0 | las 91 nuevas tienen la clave |
| Primer live `b/c/r` | 100/520/467 | 100/561/514 | 0/+41/+47 | 3 nuevas sin primera acción voluntaria |
| Calls AO bajo vivo | 42 | 47 | +5 | `H_1287`, `H_1303`, `H_1310` (2), `H_1365` |
| Pares SB/BB | 52 | 60 | +8 | 6 pares cero nuevos; `H_1365` −28; `H_1310` −2 |
| Bote exactas | 373 | 394 | +21 | manos nuevas |
| Bote falta | 3 | 3 | 0 | sin cambio |
| Bote sobra | 877 | 947 | +70 | manos nuevas |
| I4 | 12 | 13 | +1 | `H_1349` |
| DG calls total | 2603 | 2832 | +229 | manos nuevas |
| DG calls cortas | 42 | 47 | +5 | los mismos 5 casos |
| DG `CALCULABLE` | 5001 | 5417 | +416 | manos nuevas |
| DG `SOSPECHOSA` | 29 | 33 | +4 | manos nuevas |
| DG `INDETERMINADA` | 23 | 26 | +3 | manos nuevas |
| DG matriz total | 5053 | 5476 | +423 | +97 `b`, +229 `c`, +97 `r` |
| DG IDs resueltos | 204 | 221 | +17 | nuevas listas `allin` |
| DG IDs confirmados | 46 | 49 | +3 | nuevas listas `allin` |
| CM-004 ciega | 1253 | 1344 | +91 | todas las nuevas |
| Rake sin / con | 373 / 268 | 394 / 270 | +21 / +2 | manos nuevas |
| Lista saneamiento | 1253 | 1344 | +91 | toda la base |

### 6.3 Manos nuevas que explican casos concretos

| Mano | Hecho | Efecto en los tests |
|---|---|---|
| `H_1300` | Sin SB; solo `BB p`; B1-E la marca por `recorder_audit` que referencia un SB inexistente y bote no reconciliado | +1 `sin_SB`, +1 `p` de una sola posta, `sin_pos` |
| `H_1369` | Sin SB; solo `BB p`; B1-E la incluye en conflicto de bote/auditoría, con `final_pot` confirmado por B1-R | +1 `sin_SB`, +1 `p` de una sola posta |
| `H_1349` | `UTG.stack = None`; B1-E documenta un candidato derivado de 45.9, no canónico | I4 12 → 13; el helper lo trata como stack 0 |
| `H_1287` | `CO c 1.0` con viva 6.0 y stack 20.0; B1-E la declara secuencia preflop imposible | +1 call corta |
| `H_1310` | `SB c 1.0` con viva 3.0 y luego `SB c 3.0`; llamadas duplicadas en preflop y flop; B1-E la declara imposible | +2 calls cortas; +1 par −2 |
| `H_1365` | B1-E la incluye en limitaciones de `allin`/bote; el flop tiene `SB c 83.9` con viva 84.6 | +1 call corta; +1 par −28 por comparar primera call SB (limp) con primera call BB (call de subida) |
| `H_1303` | B1-E la marca por conflicto de bote/auditoría; el turn tiene `SB c 3.9` con viva 6.2 y stack 10.3, sin all-in del SB | +1 call corta; candidata localizada no adjudicada por B1-E |
| `H_1323` | Eliminada en `8594ed5`; B1-E acepta la eliminación sin referencias activas | No está en la base actual; no explica ningún delta |

### 6.4 Límites de estos recuentos

- No se hizo una revisión visual de las 1344 manos. B1-E ya advierte que las 45+47 importadas y las 98 modificaciones semánticas no se verificaron visualmente en bloque.
- Los recuentos de “calls cortas” no distinguen un `c` parcial legítimo, un all-in por menos y un undercall verdadero. B1-E explica el caso `H_0589` precisamente para no confundirlos. Por eso el total 47 es un recuento del detector, no un “número de corrupciones”.
- El par SB/BB compara la primera `c` de cada posición, que puede ser un limp en SB y un call de subida en BB. El −28 de `H_1365` es un artefacto de esa definición, no una diferencia de 28 BB entre dos ciegas equivalentes.
- I4 convierte `stack: null` en `0.0`. El 13 mide “aportado > 0” para `H_1349`, no una violación real de stack conocida.
- `sin_pos` cuenta entradas de `players` sin `pos`; B1-E cuenta 55 manos/61 jugadores activos sin posición con otro criterio. No son la misma magnitud y no deben compararse directamente.
- Los derivados canónicos siguen congelados sobre 1253. No se usaron para estos tests, pero tampoco deben interpretarse como actualizados a 1344.

---

## 7. Clasificación individual y evidencia

### 7.1 Caso 1 — `test_la_base_de_hoy_ya_usa_p`

- **Nodeid:** `motor/test_accion_p.py::test_la_base_de_hoy_ya_usa_p`
- **Línea:** 208
- **Esperado:** `{'preflop': 2522}`
- **Obtenido:** `{'preflop': 2702}`
- **Evidencia:** las 91 manos nuevas añaden 180 `p` preflop; 89 tienen SB+BB y `H_1300`/`H_1369` solo BB. El subconjunto antiguo da 2522 exactos. No hay `p` en flop/turn/river.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.2 Caso 2 — `test_las_cifras_de_posiciones_estan_fijadas`

- **Nodeid:** `motor/test_auditar_origen.py::test_las_cifras_de_posiciones_estan_fijadas`
- **Línea:** 127
- **Esperado:** `len=1253`, `con_BB=1253`, `sin_BB=0`, `con_SB=1220`, `sin_SB=33`, postings 0, duplicadas 0.
- **Obtenido:** `len=1344`, `con_BB=1344`, `sin_BB=0`, `con_SB=1309`, `sin_SB=35`, postings 0, duplicadas 0.
- **Evidencia:** +91 manos; +89 SB; +2 sin SB (`H_1300`, `H_1369`). `sin_BB=0`, `BB_sin_posting=0`, `SB_sin_posting=0` y `con_pos_duplicada=0` siguen.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.3 Caso 3 — `test_un_jugador_sin_pos_es_uno_que_no_jugo`

- **Nodeid:** `motor/test_auditar_origen.py::test_un_jugador_sin_pos_es_uno_que_no_jugo`
- **Línea:** 161
- **Esperado:** `sin_pos=804`, `con_accion=0`.
- **Obtenido:** `sin_pos=861`, `con_accion=0`.
- **Evidencia:** +57 entradas sin `pos` en las manos nuevas. La propiedad que sostiene la conclusión —ningún jugador sin posición tiene acciones— sigue midiendo 0. B1-E documenta “activos sin posición” con otro criterio (55 manos/61 jugadores); no es la misma cuenta.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.4 Caso 4 — `test_no_hay_mesa_corta_ni_ante_ni_straddle`

- **Nodeid:** `motor/test_auditar_origen.py::test_no_hay_mesa_corta_ni_ante_ni_straddle`
- **Línea:** 183
- **Esperado:** `{6: 1253}`
- **Obtenido:** `{6: 1344}`
- **Evidencia:** las 91 nuevas son de 6 jugadores. El resto de la prueba —posiciones válidas, importes 0.5/1.0, BB al principio o tras SB— sigue pasando.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.5 Caso 5 — `test_la_ciega_del_bb_que_existe_es_siempre_la_misma`

- **Nodeid:** `motor/test_auditar_origen.py::test_la_ciega_del_bb_que_existe_es_siempre_la_misma`
- **Línea:** 214
- **Esperado:** `BB {1.0: 1253}`, `SB {0.5: 1220}`.
- **Obtenido:** `BB {1.0: 1344}`, `SB {0.5: 1309}`.
- **Evidencia:** +91 BB y +89 SB; todos los postings siguen en 1.0/0.5 y los índices 0/1 siguen válidos. No hay un importe nuevo.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.6 Caso 6 — `test_las_calls_que_no_llegan_a_la_viva`

- **Nodeid:** `motor/test_auditar_origen.py::test_las_calls_que_no_llegan_a_la_viva`
- **Línea:** 302
- **Esperado:** `total=42`; `preflop/flop/turn/river = 8/12/12/10`.
- **Obtenido:** `total=47`; `10/14/13/10`.
- **Evidencia:** las 5 calls nuevas son `H_1287` preflop CO 1.0, `H_1303` turn SB 3.9, `H_1310` preflop SB 1.0, `H_1310` flop SB 4.3 y `H_1365` flop SB 83.9. `H_1287` y `H_1310` son secuencias imposibles ya declaradas por B1-E; `H_1303` y `H_1365` no están adjudicadas como undercall por B1-E y pueden ser calls parciales o redondeo. `H_0058` sigue con la misma secuencia.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `DATOS_CON_PROBLEMA`, `CONTRATO_AMBIGUO`.
- **Confianza:** alta en la causa; media en el valor futuro (42 → 47 no es una sustitución mecánica si se quieren separar defectos de calls parciales).

### 7.7 Caso 7 — `test_el_patron_del_bb_es_exacto_no_aproximado`

- **Nodeid:** `motor/test_auditar_origen.py::test_el_patron_del_bb_es_exacto_no_aproximado`
- **Línea:** 368
- **Esperado:** `52` parejas; `{-8.0: 1, 0.0: 51}`.
- **Obtenido:** `60` parejas; `{-28.0: 1, -8.0: 1, -2.0: 1, 0.0: 57}`.
- **Evidencia:** `H_0104` sigue siendo el −8 antiguo. `H_1365` produce −28 porque la primera call SB es 1.0 (limp) y la primera call BB es 29.0 (call de la subida); no son dos ciegas equivalentes. `H_1310` produce −2 y B1-E ya la declara con llamadas duplicadas. Los otros 6 pares nuevos son 0.0.
- **Clasificación:** `TEST_OBSOLETO` / `DATOS_CAMBIADOS_LEGITIMAMENTE`, `DATOS_CON_PROBLEMA`, `CONTRATO_AMBIGUO`.
- **Confianza:** alta en la causa; media en la definición futura del par.

### 7.8 Caso 8 — `test_el_bote_exacto_cuadra_en_373_de_1253`

- **Nodeid:** `motor/test_auditar_origen.py::test_el_bote_exacto_cuadra_en_373_de_1253`
- **Línea:** 398
- **Esperado:** `exactas=373`, `falta=3`, `sobra=877`.
- **Obtenido:** `exactas=394`, `falta=3`, `sobra=947`.
- **Evidencia:** +21 manos exactas y +70 sobrantes en las nuevas; `falta` sigue en 3. La relación exactas + sobra + falta = total sigue dando 1344.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.9 Caso 9 — `test_el_rake_no_explica_el_bote`

- **Nodeid:** `motor/test_auditar_origen.py::test_el_rake_no_explica_el_bote`
- **Línea:** 425
- **Esperado:** `sin_rake=373`, `con_rake=268`.
- **Obtenido:** `sin_rake=394`, `con_rake=270`.
- **Evidencia:** +21 exactas sin rake y +2 con rake en las nuevas. La relación `con_rake < sin_rake` sigue siendo verdadera; el rake sigue empeorando el cuadre.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.10 Caso 10 — `test_aportar_mas_que_el_stack_no_depende_del_rake`

- **Nodeid:** `motor/test_auditar_origen.py::test_aportar_mas_que_el_stack_no_depende_del_rake`
- **Línea:** 436
- **Esperado:** `I4=12`, `I2=3`, `I1=true`.
- **Obtenido:** `I4=13`, `I2=3`, `I1=true`.
- **Evidencia:** `H_1349` tiene `UTG.stack=None`. `AO.seccion_3c` hace `float(p.get('stack') or 0.0)`, así que el aporte de 3.0 se compara contra 0 y entra en I4. B1-E §4.8 documenta el stack nulo y el candidato derivado 45.9, no canónico. No es una violación real demostrada; es un nulo tratado como cero.
- **Clasificación:** `TEST_OBSOLETO` / `DATOS_CAMBIADOS_LEGITIMAMENTE`, `CONTRATO_AMBIGUO`.
- **Confianza:** alta.

### 7.11 Caso 11 — `test_el_json_y_el_informe_cuentan_lo_mismo`

- **Nodeid:** `motor/test_auditar_origen.py::test_el_json_y_el_informe_cuentan_lo_mismo`
- **Línea:** 498
- **Esperado:** sumas SB/BB `=1253`.
- **Obtenido:** sumas SB/BB `=1344`.
- **Evidencia:** la primera aserción `s1['total'] == exactas + sobra + falta` pasa con 1344. La consistencia interna está bien; lo que falla es el literal `1253` en las otras dos aserciones. El mensaje “el reparto de §3 no cubre las 1253 manos” es texto obsoleto, no la causa.
- **Clasificación:** `TEST_OBSOLETO` / `DATOS_CAMBIADOS_LEGITIMAMENTE`.
- **Confianza:** alta.

### 7.12 Caso 12 — `test_el_invariante_de_cm004_puede_dispararse`

- **Nodeid:** `motor/test_cm004.py::test_el_invariante_de_cm004_puede_dispararse`
- **Línea:** 516
- **Esperado:** `CIEGAS_RECONOCIDAS=1253`.
- **Obtenido:** `con_ciega=1344` (1344 de 1344).
- **Evidencia:** la regla `_es_ciega_bb` reconoce la ciega en todas las manos nuevas; el invariante CM-004 sigue midiendo 0 violaciones. Lo que cambia es la cobertura del guard, no la regla. `CIEGAS_RECONOCIDAS` es un literal de test, no un contrato de la base.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.13 Caso 13 — `test_la_base_son_dos_grabadores`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_la_base_son_dos_grabadores`
- **Línea:** 642
- **Esperado:** `con=1182`, `sin=71`.
- **Obtenido:** `con=1273`, `sin=71`.
- **Evidencia:** las 91 nuevas tienen la clave `allin`; 74 la tienen vacía y 17 con contenido. El grupo `record_hand` sigue siendo el mismo bloque de 71 (`H_0001..H_0073` menos `H_0028`/`H_0072`). La conclusión estructural “dos grabadores” sigue siendo válida; solo cambia el tamaño del grupo live.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.14 Caso 14 — `test_la_apertura_cambia_tras_la_normalizacion`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_la_apertura_cambia_tras_la_normalizacion`
- **Línea:** 680
- **Esperado:** `hand 31/29/4`; `live b=100,c=520,r=467`.
- **Obtenido:** `hand 31/29/4`; `live b=100,c=561,r=514`.
- **Evidencia:** el grupo `hand` no cambia; en `live`, `b` sigue en 100 y solo suben `c` (+41) y `r` (+47). 3 de las nuevas no tienen primera acción `b/c/r`. La relación `c > r > b` sigue.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.15 Caso 15 — `test_las_42_calls_por_debajo_de_la_viva`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_las_42_calls_por_debajo_de_la_viva`
- **Línea:** 780
- **Esperado:** `total=2603`, `cortas=42`.
- **Obtenido:** `total=2832`, `cortas=47`.
- **Evidencia:** +229 calls y +5 cortas por las nuevas. Las 5 cortas son las mismas del caso 6. `H_1287` y `H_1310` son defectos de secuencia ya declarados; `H_1303`/`H_1365` quedan como candidatas de call parcial/redondeo no adjudicadas. El total 2832 no es un “número de defectos”; es el total del detector.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `DATOS_CON_PROBLEMA`, `CONTRATO_AMBIGUO`.
- **Confianza:** alta en la causa; media en el valor futuro.

### 7.16 Caso 16 — `test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb`
- **Línea:** 796
- **Esperado:** `len=42`, `uno=3`, `BB=10`.
- **Obtenido:** `len=47`, `uno=3`, `BB=10`.
- **Evidencia:** solo cambia el total. `uno=3` y `BB=10` siguen; MP, CO y UTG siguen con calls. La conclusión cualitativa “no es solo del BB” se mantiene.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `DATOS_CON_PROBLEMA`, `CONTRATO_AMBIGUO`.
- **Confianza:** alta en la causa; media en el valor futuro.

### 7.17 Caso 17 — `test_la_clasificacion_sobre_la_base`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_la_clasificacion_sobre_la_base`
- **Línea:** 809
- **Esperado:** `CALCULABLE=5001`, `SOSPECHOSA=29`, `INDETERMINADA=23`.
- **Obtenido:** `CALCULABLE=5417`, `SOSPECHOSA=33`, `INDETERMINADA=26`.
- **Evidencia:** +423 acciones clasificadas en las nuevas: +416 calculables, +4 sospechosas, +3 indeterminadas. No hay cambio de clasificador.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.18 Caso 18 — `test_el_desglose_por_accion_por_resultado_es_coherente`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_el_desglose_por_accion_por_resultado_es_coherente`
- **Línea:** 838
- **Esperado:** matriz `b 1444/4`, `c 2559/21/23`, `r 998/4`; total `5053`.
- **Obtenido:** matriz `b 1541/4`, `c 2781/25/26`, `r 1095/4`; total `5476`.
- **Evidencia:** +97 `b`, +229 `c`, +97 `r` en las nuevas. La matriz sigue sumando por filas y columnas; solo cambian los totales. No hay una fila nueva ni una acción fuera de `b/c/r`.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.19 Caso 19 — `test_el_reparto_por_accion_suma_el_total_de_la_base`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_el_reparto_por_accion_suma_el_total_de_la_base`
- **Línea:** 870
- **Esperado:** `b=1448`, `c=2603`, `r=1002`, suma `5053`.
- **Obtenido:** `b=1545`, `c=2832`, `r=1099`, suma `5476`.
- **Evidencia:** los tres totales suben por las manos nuevas; la suma sigue igual al total de la matriz. No hay desajuste entre acciones y matriz.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.20 Caso 20 — `test_los_ids_se_resuelven_con_el_boton`

- **Nodeid:** `motor/test_diagnostico_grabador.py::test_los_ids_se_resuelven_con_el_boton`
- **Línea:** 930
- **Esperado:** `resueltos=204`, `confirmados=46`.
- **Obtenido:** `resueltos=221`, `confirmados=49`.
- **Evidencia:** +17 IDs resueltos y +3 confirmados en las nuevas listas `allin`. El mecanismo de resolución con botón sigue funcionando; no hay un fallo de `get_position`.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.21 Caso 21 — `test_por_defecto_cubre_toda_la_base`

- **Nodeid:** `motor/test_lista_saneamiento.py::test_por_defecto_cubre_toda_la_base`
- **Línea:** 190
- **Esperado:** `manos=1253`.
- **Obtenido:** `manos=1344`.
- **Evidencia:** el rango por defecto sigue cubriendo toda la base; solo cambia el total. La propiedad que protege el test —no recortar el alcance— se mantiene.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

### 7.22 Caso 22 — `test_el_rango_por_defecto_sigue_siendo_toda_la_base`

- **Nodeid:** `motor/test_lista_saneamiento.py::test_el_rango_por_defecto_sigue_siendo_toda_la_base`
- **Línea:** 270
- **Esperado:** `manos=1253`; `H_1282` presente.
- **Obtenido:** `manos=1344`; `H_1282` presente.
- **Evidencia:** el rango sigue llegando a `H_1282`; el total es 1344. No hay recorte de alcance.
- **Clasificación:** `DATOS_CAMBIADOS_LEGITIMAMENTE` / `TEST_OBSOLETO`.
- **Confianza:** alta.

---

## 8. Causas raíz compartidas y lo que no es causa

### 8.1 Causa raíz compartida

La causa raíz es la convivencia de dos verdades:

1. La base canónica actual es de 1344 manos, adoptada el 2026-11-11.
2. Los 22 tests siguen fijando números de la base de 1253, porque no se actualizaron después de `b358d26`.

El subconjunto de 1253 dentro del fichero actual reproduce todos los valores esperados. Las 91 manos nuevas aportan exactamente los deltas observados. Eso descarta una explicación genérica de “los tests están mal” y permite atribuir cada fallo a un dato concreto.

### 8.2 Lo que no es causa

- **No es una regresión de código.** El código actual, aplicado al subconjunto de 1253, reproduce todas las constantes. `tools/auditar_origen.py`, `tools/diagnostico_grabador.py` y `tools/lista_saneamiento.py` no cambiaron entre `51a6fb9` y `HEAD`. `motor/learn.py` cambió, pero conserva la compatibilidad de estas métricas.
- **No es un artefacto derivado desactualizado.** Los 22 tests leen `data/hands_db.jsonl`, no `preflop_matrices.json`, `calibration_window.json` ni otro derivado. Los derivados congelados son un problema documentado de otra etapa, no la causa de estos 22.
- **No es dependencia de estado.** Los 22 fallan aislados y juntos; no escriben datos; no comparten un fixture mutable.
- **No es una mano nueva “contaminando” una base limpia.** Las 91 manos están documentadas y adoptadas. Algunas tienen limitaciones conocidas; otras dos calls cortas quedan como candidatas locales. Eso es un problema de calidad de datos localizado, no una explicación única para los 22.
- **No es una razón para reducir la base a 1253.** El cambio de fuente está documentado y el subconjunto antiguo no explica los fallos por sí solo: la base actual es la que se adoptó.

### 8.3 Limitaciones de datos que sí existen

Estas limitaciones son reales, pero no convierten los 22 fallos en `DATOS_CON_PROBLEMA` principal:

- `H_1287` y `H_1310`: secuencias imposibles ya declaradas por B1-E.
- `H_1300`: `recorder_audit` referencia un SB inexistente; bote no reconciliado.
- `H_1303`: conflicto de bote/auditoría; call corta de turn no adjudicada.
- `H_1349`: stack nulo documentado; candidato derivado 45.9 no canónico.
- `H_1365`: limitaciones de `allin`/bote; call corta de flop no adjudicada.
- `H_1369`: conflicto de bote/auditoría; B1-R confirma el `final_pot`.
- `H_1323`: eliminada; sin referencias.

Ninguna de estas limitaciones explica por sí sola que 22 tests fallen: los tests fallan porque sus pines son de 1253. Las limitaciones explican por qué algunos valores nuevos no deben actualizarse mecánicamente.

---

## 9. Impacto y riesgo de las posibles soluciones

No se ejecutó ninguna de estas opciones. Se analizan por impacto y riesgo.

### 9.1 Opción A — Actualizar los 22 literales a los valores actuales

**Impacto:** la suite volvería a verde.

**Riesgo:** alto si se hace en masa. En los casos 6, 7, 10, 15 y 16 el valor nuevo no es una simple sustitución: hay que decidir si las 5 calls cortas son defectos, calls parciales o all-in por menos; si el par SB/BB debe comparar la primera call o la call del mismo nivel; y si `stack: null` debe excluirse o contarse aparte. Actualizar solo los números convertiría un detector en una foto y podría ocultar defectos locales.

**Uso recomendado:** solo después de un contrato explícito por métrica, con tests de invariante separados de los pines.

### 9.2 Opción B — Revertir la base a 1253

**Impacto:** los 22 tests volverían a pasar, pero se perderían las 91 manos adoptadas y se rompería el manifiesto, el SHA, la adopción de 1344, los pines y posiblemente los derivados.

**Riesgo:** muy alto. No hay evidencia de que la base de 1344 sea inválida en bloque; B1-E la acepta como registro con excepción B. Revertir ocultaría el cambio real y contradiría la decisión documentada.

**Uso recomendado:** no.

### 9.3 Opción C — Filtrar los tests a las 1253 manos antiguas

**Impacto:** los tests seguirían midiendo la base histórica y no la base canónica actual.

**Riesgo:** alto. Puede ser útil como test histórico explícito, pero no como comportamiento por defecto: daría verde sin cubrir la base vigente y haría que las 91 manos nuevas no tuvieran guard.

**Uso recomendado:** solo si se declara como “regresión histórica 1253” separada de la cobertura actual.

### 9.4 Opción D — Derivar los recuentos de la fuente y del manifiesto

**Impacto:** reduce los literales frágiles y hace que los tests sigan la base declarada.

**Riesgo:** medio. Un test que solo compara la fuente consigo misma puede volverse tautológico y dejar de detectar cambios silenciosos. Habría que mantener pines explícitos para los contratos y usar invariantes para las propiedades.

**Uso recomendado:** sí, como parte de una actualización revisada, no como sustituto de todos los pines.

### 9.5 Opción E — Corregir primero los defectos localizados de las manos nuevas

**Impacto:** permitiría que los valores nuevos sean más interpretables: `H_1287`, `H_1310`, `H_1303`, `H_1365`, `H_1349`, etc.

**Riesgo:** alto. Implica tocar datos, actualizar hashes/manifiesto, reabrir B1 y decidir qué es corrección canónica. Está fuera del alcance de esta auditoría y no es necesario para explicar los 22 fallos.

**Uso recomendado:** solo con autorización explícita y después de decidir el contrato de campos.

### 9.6 Opción F — No hacer nada y mantener los 22 fallos

**Impacto:** la suite sigue roja; los 22 quedan visibles, pero se mezclan con fallos nuevos si aparecen.

**Riesgo:** medio. Es aceptable como estado temporal documentado, pero no como estado indefinido: un rojo permanente deja de ser señal.

**Uso recomendado:** mantener solo como incidencias clasificadas y con una tarea separada de actualización contractual.

### 9.7 Impacto sobre PR-03

PR-03 sigue bloqueado. Los 22 fallos no son de PR-02B ni de PR-03; son pines históricos. Iniciar PR-03 sin resolver el contrato de estos recuentos dejaría una suite roja y una base de cobertura ambigua. La secuencia correcta es: cerrar esta clasificación, decidir el contrato de actualización y solo después autorizar PR-03.

---

## 10. Casos no resueltos y ambigüedades

No hay ningún fallo sin clasificación principal. Los 22 tienen causa identificada y evidencia. Lo que queda abierto es el **valor futuro** de cinco casos y la clasificación de dos calls nuevas:

1. **Casos 6, 15 y 16 — calls cortas.** El total pasa de 42 a 47. No se puede decidir mecánicamente si el nuevo valor correcto es 47, si se deben excluir las calls de `H_1287`/`H_1310` por secuencias imposibles, o si `H_1303`/`H_1365` son calls parciales/redondeo. Requiere contrato de `amount` y de exclusión de defectos.
2. **Caso 7 — par SB/BB.** El −28 de `H_1365` es un artefacto de comparar primera call SB (limp) con primera call BB (call de subida). El test no define si el par debe ser “primera call” o “call del mismo nivel”. El −2 de `H_1310` sí toca una secuencia ya declarada imposible.
3. **Caso 10 — stack nulo.** `H_1349` tiene `stack: null`; el test lo convierte en 0.0. No está decidido si el invariante debe excluir nulos, contarlos aparte o usar el candidato derivado 45.9. B1-E no escribe el 45.9 en la base.
4. **`H_1303` y `H_1365` — calls cortas no adjudicadas por B1-E.** Son candidatas localizadas. No se clasifican como corrupción demostrada; tampoco se declaran limpias. Quedan para revisión de campo.
5. **`H_1300`/`H_1369` — ausencia de SB.** B1-E documenta el problema de asiento/auditoría; no se ha demostrado que la mano sea inválida. Afecta al recuento `sin_SB`, no a la causa de los 22.

Ningún caso se deja como `CONTRATO_AMBIGUO` principal. `CONTRATO_AMBIGUO` aparece solo como secundaria en los casos 6, 7, 10, 15 y 16, porque la causa del fallo es clara pero el valor futuro no.

---

## 11. Hashes finales y comprobación de no modificación

### 11.1 Estado final

- `HEAD`: `3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96` (sin cambios).
- `git status --short data`: vacío.
- No se creó ningún commit.
- El único fichero nuevo de esta auditoría es `DOCS/CLASIFICACION_INDEPENDIENTE_22_FALLOS_2026-11-14.md`.
- Los cambios preexistentes de PR-02B siguen exactamente como estaban.

### 11.2 Hashes finales

Los hashes de datos y artefactos son idénticos a los iniciales de §2.2. En particular:

```text
3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e  data/hands_db.jsonl
075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1  data/preflop_matrices.json
7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1  data/calibration_window.json
c6f8a18db358f3071fab7d5c4a17d3e1fdd88d17c54ce345592af9b5dd7ab841  data/decisions.jsonl
86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3  data/observations.json
24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b  data/profiles.json
add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa  data/profile_ranges.json
1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c  data/postflop_ranges.json
53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749  data/preflop_stats.json
efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae  data/behavior.json
5de905ca0d4e3a25b0b16dd5db85e6de376711762bb52f3c1280dd6a16a05a1a  data/behavior_probs.json
```

### 11.3 Qué no se tocó

- No se modificó `data/hands_db.jsonl`.
- No se modificaron tests.
- No se modificó código de producción.
- No se modificaron matrices, calibración, decisiones, observaciones, perfiles ni derivados.
- No se regeneraron artefactos.
- No se ejecutaron writers.
- No se redujo la base.
- No se actualizaron números en masa.
- No se inició PR-03.
- `MULTIWAY_SOPORTADO` no se tocó.

---

## 12. Veredicto general

Los 22 fallos son **pines históricos de la base de 1253 conviviendo con la base canónica de 1344**. No son una regresión de código, no son un artefacto desactualizado y no dependen del orden de ejecución.

La clasificación principal es:

- **19 `DATOS_CAMBIADOS_LEGITIMAMENTE`**: la fuente cambió de forma documentada y adoptada; el test no contempla el cambio.
- **3 `TEST_OBSOLETO`**: el caso 7 (par SB/BB), el caso 10 (stack nulo como cero) y el caso 11 (literal 1253 dentro de una consistencia) tienen una métrica o un literal que ya no representa el contrato actual.
- **0 `REGRESION_CODIGO`**.
- **0 `ARTEFACTO_DESACTUALIZADO`**.
- **0 `TEST_DEPENDIENTE_DEL_ESTADO`**.
- **0 `OTRA_CAUSA`**.

La base de 1344 está adoptada como registro canónico con excepción B, no como base de calibración validada. Las limitaciones de `H_1287`, `H_1310`, `H_1300`, `H_1303`, `H_1349`, `H_1365` y `H_1369` son reales y deben seguir documentadas; no justifican revertir la base ni actualizar los tests en masa sin contrato.

**Recomendación:** mantener los 22 como incidencias clasificadas, no corregirlos en esta auditoría y no iniciar PR-03 hasta que exista una decisión explícita sobre el contrato de recuentos. Cualquier actualización futura debe distinguir pines contractuales, invariantes y exclusiones por defectos conocidos; no debe limitarse a sustituir 1253 por 1344.

La auditoría termina aquí. No se ha ejecutado ninguna corrección.

---

## Anexo A — Mensajes de error reproducidos

Los mensajes siguientes son la primera aserción que falla. Cuando el test tiene aserciones posteriores que también fallan, se indican después. La salida completa de pytest está en `C:\Users\Jorgito\AppData\Local\Temp\opencode\audit22\`.

### A.1 Caso 1

```text
motor/test_accion_p.py:208: AssertionError
>       assert dict(por_calle) == {'preflop': 2522}, dict(por_calle)
E       AssertionError: {'preflop': 2702}
E       assert {'preflop': 2702} == {'preflop': 2522}
E         Differing items:
E         {'preflop': 2702} != {'preflop': 2522}
```

### A.2 Caso 2

```text
motor/test_auditar_origen.py:127: AssertionError
>       assert len(manos) == 1253
E       AssertionError: assert 1344 == 1253
```

También fallan: `con_BB` 1344 vs 1253, `con_SB` 1309 vs 1220, `sin_SB` 35 vs 33.

### A.3 Caso 3

```text
motor/test_auditar_origen.py:161: AssertionError
>       assert sin_pos == 804, sin_pos
E       AssertionError: 861
E       assert 861 == 804
```

`con_accion == 0` sigue pasando.

### A.4 Caso 4

```text
motor/test_auditar_origen.py:183: AssertionError
>       assert e['n_jugadores'] == {6: 1253}, e['n_jugadores']
E       AssertionError: {6: 1344}
E       assert {6: 1344} == {6: 1253}
```

El resto de la prueba de mesa/ante/straddle sigue pasando.

### A.5 Caso 5

```text
motor/test_auditar_origen.py:214: AssertionError
>       assert s1['bb_importes'] == {1.0: 1253}, s1['bb_importes']
E       AssertionError: {1.0: 1344}
E       assert {1.0: 1344} == {1.0: 1253}
```

También falla `sb_importes` 1309 vs 1220. Los índices de posting siguen válidos.

### A.6 Caso 6

```text
motor/test_auditar_origen.py:302: AssertionError
>       assert total == 42, total
E       AssertionError: 47
E       assert 47 == 42
```

También falla el reparto por calle: `10/14/13/10` vs `8/12/12/10`.

### A.7 Caso 7

```text
motor/test_auditar_origen.py:368: AssertionError
>       assert s2c['total_parejas'] == 52, s2c['total_parejas']
E       AssertionError: 60
E       assert 60 == 52
```

También falla `diferencias`: `{-28.0: 1, -8.0: 1, -2.0: 1, 0.0: 57}` vs `{-8.0: 1, 0.0: 51}`.

### A.8 Caso 8

```text
motor/test_auditar_origen.py:398: AssertionError
>       assert s3['exactas'] == 373, s3['exactas']
E       AssertionError: 394
E       assert 394 == 373
```

`falta == 3` sigue pasando; también falla `sobra` 947 vs 877.

### A.9 Caso 9

```text
motor/test_auditar_origen.py:425: AssertionError
>       assert sin_rake == 373, sin_rake
E       AssertionError: 394
E       assert 394 == 373
```

También falla `con_rake` 270 vs 268; `con_rake < sin_rake` sigue pasando.

### A.10 Caso 10

```text
motor/test_auditar_origen.py:436: AssertionError
>       assert inv['I4_aporta_mas_que_stack'] == 12, inv['I4_aporta_mas_que_stack']
E       AssertionError: 13
E       assert 13 == 12
```

`I2 == 3` e `I1 is True` siguen pasando.

### A.11 Caso 11

```text
motor/test_auditar_origen.py:498: AssertionError
>       assert sum(v for k, v in s1['inventario'].items()
E       assert 1344 == 1253
E        +  where 1344 = sum(<generator object ...>)
```

La primera aserción de consistencia (`s1['total'] == exactas + sobra + falta`) pasa. También falla la suma BB 1344 vs 1253.

### A.12 Caso 12

```text
motor/test_cm004.py:516: AssertionError
>       assert con_ciega == CIEGAS_RECONOCIDAS, (
E       AssertionError: el motor reconoce la ciega en 1344 de 1344 manos, y el declarado es 1253.
E       assert 1344 == 1253
```

El invariante CM-004 sigue midiendo cero violaciones; el test de invariante que no usa el pin de 1253 pasa.

### A.13 Caso 13

```text
motor/test_diagnostico_grabador.py:642: AssertionError
>       assert len(con) == 1182, 'manos de recorder_live: %d' % len(con)
E       AssertionError: manos de recorder_live: 1273
E       assert 1273 == 1182
```

`len(sin) == 71` y los IDs de las 71 siguen pasando.

### A.14 Caso 14

```text
motor/test_diagnostico_grabador.py:680: AssertionError
>       assert dict(c['live']) == {'b': 100, 'c': 520, 'r': 467}, dict(c['live'])
E       AssertionError: {'b': 100, 'c': 561, 'r': 514}
E       assert {'b': 100, 'c': 561, 'r': 514} == {'b': 100, 'c': 520, 'r': 467}
```

El grupo `hand` 31/29/4, `b=100` y la relación `c > r > b` siguen pasando.

### A.15 Caso 15

```text
motor/test_diagnostico_grabador.py:780: AssertionError
>       assert total == 2603, total
E       AssertionError: 2832
E       assert 2832 == 2603
```

También falla `cortas` 47 vs 42.

### A.16 Caso 16

```text
motor/test_diagnostico_grabador.py:796: AssertionError
>       assert len(calls) == 42, len(calls)
E       AssertionError: 47
E       assert 47 == 42
```

`uno == 3`, `BB == 10` y MP/CO/UTG > 0 siguen pasando.

### A.17 Caso 17

```text
motor/test_diagnostico_grabador.py:809: AssertionError
>       assert tot[DG.CALCULABLE] == 5001, dict(tot)
E       AssertionError: {'CALCULABLE': 5417, 'INDETERMINADA': 26, 'SOSPECHOSA': 33}
E       assert 5417 == 5001
```

También fallan `SOSPECHOSA` 33 vs 29 e `INDETERMINADA` 26 vs 23.

### A.18 Caso 18

```text
motor/test_diagnostico_grabador.py:838: AssertionError
>       assert {k: dict(v) for k, v in matriz.items()} == {
E       AssertionError: {'b': {'CALCULABLE': 1541, 'SOSPECHOSA': 4}, 'c': {'CALCULABLE': 2781, 'INDETERMINADA': 26, 'SOSPECHOSA': 25}, 'r': {'CALCULABLE': 1095, 'SOSPECHOSA': 4}}
E       assert {'b': {'CALCU...SPECHOSA': 4}} == {'b': {'CALCU...SPECHOSA': 4}}
E         Differing items:
E         {'c': {'CALCULABLE': 2781, 'INDETERMINADA': 26, 'SOSPECHOSA': 25}} != {'c': {'CALCULABLE': 2559, 'SOSPECHOSA': 21, 'INDETERMINADA': 23}}
E         {'r': {'CALCULABLE': 1095, 'SOSPECHOSA': 4}} != {'r': {'CALCULABLE': 998, 'SOSPECHOSA': 4}}
E         {'b': {'CALCULABLE': 1541, 'SOSPECHOSA': 4}} != {'b': {'CALCULABLE': 1444, 'SOSPECHOSA': 4}}
```

También falla `total_matriz` 5476 vs 5053.

### A.19 Caso 19

```text
motor/test_diagnostico_grabador.py:870: AssertionError
>       assert tot['b'] == 1448, dict(tot)
E       AssertionError: {'b': 1545, 'c': 2832, 'r': 1099}
E       assert 1545 == 1448
```

También fallan `c` 2832 vs 2603, `r` 1099 vs 1002 y la suma 5476 vs 5053.

### A.20 Caso 20

```text
motor/test_diagnostico_grabador.py:930: AssertionError
>       assert resueltos == 204, resueltos
E       AssertionError: 221
E       assert 221 == 204
```

También falla `confirmados` 49 vs 46.

### A.21 Caso 21

```text
motor/test_lista_saneamiento.py:190: AssertionError
>       assert resumen['manos'] == len(manos) == 1253
E       AssertionError: assert 1344 == 1253
```

### A.22 Caso 22

```text
motor/test_lista_saneamiento.py:270: AssertionError
>       assert resumen['manos'] == 1253
E       assert 1344 == 1253
```

`H_1282` sigue presente.

---

## Anexo B — Trazabilidad de la conclusión

La conclusión se apoya en cinco comprobaciones independientes:

1. **Fuente actual:** 1344 líneas, 1344 IDs únicos, SHA `3f0e7e5e...`, manifiesto `8594ed5`/1344.
2. **Fuente histórica:** 1253 líneas, SHA `c3172a14...`, blob `51a6fb9`.
3. **Subconjunto actual de 1253:** reproduce todas las constantes esperadas por los 22 tests.
4. **Deltas:** las 91 manos nuevas aportan exactamente los cambios observados en cada métrica.
5. **Código:** los helpers de auditoría no cambiaron; el código actual sobre el subconjunto de 1253 reproduce las constantes; no hay regresión.

La conclusión no depende de los números declarados por los tests: se recalcularon desde la fuente y se contrastaron contra el subconjunto histórico. Los 22 fallos quedan clasificados individualmente y la base no se modificó.
