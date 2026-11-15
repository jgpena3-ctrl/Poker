# Política de mantenimiento de los tests afectados por el crecimiento de la base dinámica

**Fecha:** 2026-11-14  
**Tipo de trabajo:** diseño y análisis. **No implementa** la política.  
**Estado:** PR-02B cerrado; PR-03 no iniciado; los 22 fallos siguen sin corregir.  
**Base de referencia:** `data/hands_db.jsonl` en `HEAD = 3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96`, 1344 líneas, SHA-256 `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.  
**Base histórica de las expectativas:** blob de `51a6fb9f05394fcfecd3b3ee4fb9479ed4e9600f:data/hands_db.jsonl`, objeto Git `f52c09e294153e748f05d216bafcf6a779be4465`, 1253 líneas, 1,851,156 bytes, SHA-256 `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`.

> Este documento define política; no implementa cambios en tests, código, datos, matrices ni artefactos, no ejecuta saneadores ni writers y no inicia PR-03.

> **Nota de estado documental (revisión posterior):** las secciones 1–9 y la tabla original de §10 registran el análisis previo a resolver D1–D9 y D11; las menciones allí a decisiones “pendientes”, “no adjudicadas” o alternativas son históricas, no el estado vigente. Las resoluciones autoritativas están en §10.1.1, las puertas y su estado en §10.1.2, y el detalle en `DOCS/RESOLUCION_DECISIONES_D1_D9_D11_2026-11-14.md`. D8 sigue **pendiente de ratificación** y PR-03 sigue bloqueado.

---

## 1. Resumen ejecutivo

Los 22 fallos no son una regresión de código ni un problema de orden de ejecución: son **pines de la base histórica de 1253 conviviendo con la base canónica adoptada de 1344**. El subconjunto de 1253 manos dentro del fichero actual reproduce todas las expectativas antiguas; los deltas proceden de las 91 manos nuevas.

Actualizar en masa `1253` por `1344` —o `2522` por `2702`, etc.— volvería la suite verde, pero convertiría varios detectores en simples fotografías del dato. El diseño correcto no es sustituir constantes: es **separar cinco cosas que hoy están mezcladas**:

1. la identidad de la fuente;
2. la población seleccionada;
3. la regla de selección;
4. la versión del código;
5. el resultado esperado.

La política recomendada se apoya en cinco piezas pequeñas y verificables:

- **snapshots históricos inmutables**, identificados por commit + SHA-256 + número de líneas, que conservan su expectativa y no cambian cuando entran manos nuevas;
- **invariantes sobre la base dinámica**, que deben cumplirse con independencia del tamaño de la base;
- **cohortes identificadas por procedencia o pertenencia explícita**, no por rangos de líneas;
- **fixtures sintéticos** para contratos de código que no necesitan la base completa;
- **ledgers de anomalías conocidas** para los diagnósticos: el detector sigue detectando, pero cada anomalía debe estar declarada con su `hand_id`, su localización y su motivo; una anomalía nueva falla.

### 1.1 Reparto de recomendaciones

| Recomendación | Casos | Nº |
|---|---|---:|
| `CORREGIR_EXPECTATIVA_OBSOLETA` | 1 | 1 |
| `CONVERTIR_A_INVARIANTE` | 2, 3, 4, 5, 9, 11, 12, 17, 18, 19, 21, 22 | 12 |
| `REQUIERE_DECISION_MANUAL` | 6, 7, 10, 15, 16 | 5 |
| `CONSERVAR_SNAPSHOT` | 8 | 1 |
| `DEFINIR_SUBCONJUNTO` | 13, 14 | 2 |
| `REEMPLAZAR_POR_FIXTURE` | 20 | 1 |
| `SIN_CAMBIO_NECESARIO` | ninguno | 0 |

### 1.2 Los tres tests obsoletos

- **Caso 7:** el par SB/BB compara la primera call de cada posición aunque correspondan a niveles de apuesta distintos. No es una relación válida. El `-8` de `H_0104` y el `-28` de `H_1365` son artefactos de esa definición; el `-2` de `H_1310` sí coincide con una call corta real en el mismo nivel. La sustitución correcta es comparar cada call con la viva del momento, o emparejar solo calls que afrontan la misma viva, nunca “la primera de cada lista”.
- **Caso 10:** `stack: null` no significa `0.0`. El helper `AO.seccion_3c` convierte el nulo en cero y cuenta como violación I4 una aportación de 3.0 de `H_1349`. Además, el `12` histórico tampoco era “12 violaciones”: en la base actual hay **1 violación real conocida** (`H_0740`, 28.2 > 28.1) y **12 stacks desconocidos** contados como cero; en la base histórica eran 1 + 11. El contrato debe separar “stack conocido”, “stack desconocido” y “stack cero conocido”.
- **Caso 11:** el literal `1253` está dentro de una comprobación de consistencia interna. La primera aserción ya pasa con 1344; solo fallan los literales. Debe comprobar identidades (`total == exactas + sobra + falta`, `suma SB == total`, `suma BB == total`), no una constante histórica.

### 1.3 Los cinco valores pendientes

Los casos **6, 7, 10, 15 y 16** no se cierran en este documento con una cifra nueva. La evidencia disponible permite describir qué manos nuevas contribuyen y qué está confirmado, pero no adjudicar individualmente `H_1303` ni `H_1365`, ni decidir si una call corta es un defecto, una call parcial o un all-in por menos. Esas decisiones necesitan autorización y revisión de campo; no se convierten en constantes por comodidad.

### 1.4 Veredicto anticipado

La política es viable y no exige un sistema complejo: basta un manifiesto pequeño, snapshots explícitos, invariantes y ledgers de anomalías. No es aceptable ninguna solución que consista en actualizar los 22 números en masa, filtrar todos los tests a 1253 o relajar los diagnósticos para que dejen de mirar. PR-03 sigue bloqueado hasta que esta política se apruebe y se implemente en una tarea separada.

---

## 2. Evidencia y referencias utilizadas

### 2.1 Estado de partida preservado

- `HEAD`: `3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96`.
- `git status --short data`: vacío.
- No se creó ningún commit.
- El árbol ya tenía cambios y ficheros no rastreados de PR-02B, que se conservaron sin tocar:

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
?? DOCS/CLASIFICACION_INDEPENDIENTE_22_FALLOS_2026-11-14.md
?? motor/preflop_coverage.py
?? motor/test_preflop_canonical_contracts.py
?? motor/test_preflop_coverage.py
```

### 2.2 Hashes de datos, documentos y artefactos

Estos hashes se comprobaron al inicio y se volvieron a comprobar al cierre. Los artefactos derivados no son entrada de los 22 tests; se incluyen solo como control de no modificación.

| Fichero | SHA-256 |
|---|---|
| `data/hands_db.jsonl` | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| `DOCS/CIERRE_PR_02B_2026-11-14.md` | `d434254021ea15f0567c4dda8c7d2c5ccca82f6bc8ff720306dece7795019ef4` |
| `DOCS/CLASIFICACION_INDEPENDIENTE_22_FALLOS_2026-11-14.md` | `f4a6076a729d191278aa66ae88fecb2d80ddfa5de1b157ecd76e651c1fb700b0` |
| `DOCS/PLAN_IMPLEMENTACION_INCREMENTAL_2026-11-13.md` | `a3b1b0a0ee937ad5001d65597bfa1dca3d1f90c5317358d7040f76c66690799e` |
| `data/preflop_matrices.json` | `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1` |
| `data/calibration_window.json` | `7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1` |
| `data/decisions.jsonl` | `c6f8a18db358f3071fab7d5c4a17d3e1fdd88d17c54ce345592af9b5dd7ab841` |
| `data/observations.json` | `86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3` |

### 2.3 Documentos de referencia

- `DOCS/CIERRE_PR_02B_2026-11-14.md`: cierre de PR-02B y lista de los 22 fallos.
- `DOCS/CLASIFICACION_INDEPENDIENTE_22_FALLOS_2026-11-14.md`: reproducción individual y conjunta, cronología, deltas, clasificación causal y límites.
- `DOCS/PLAN_IMPLEMENTACION_INCREMENTAL_2026-11-13.md`: secuencia PR-02/PR-03, estado de PR-02B y criterios de no implementación.
- `DOCS/CANAL_MANUAL_CERRADO.md` y `DOCS/B1_EXCEPCION_PROCEDENCIA.md`: adopción de la base de 1344, excepción B y limitaciones de campo.
- `DOCS/CONTRATO_ACCION_P.md`: contrato de la acción `p`.
- `motor/learn.py`: manifiesto `HANDS_DB_*`, `load_hands`, `_preflop_sequence`, `_es_ciega_bb`.
- `tools/auditar_origen.py` (`AO`), `tools/diagnostico_grabador.py` (`DG`) y `tools/lista_saneamiento.py` (`LS`): instrumentos cuya semántica se analiza, no se modifica.

### 2.4 Reproducción ya documentada

La auditoría previa documentó:

- 22 fallos individuales reproducidos con su `nodeid`;
- 22 fallos juntos: `22 failed in 3.62s`;
- suite completa: `22 failed, 1222 passed, 1 skipped, 6 xfailed, 6 warnings`;
- ausencia de dependencia de orden;
- subconjunto de 1253 que reproduce exactamente todas las constantes;
- deltas atribuibles a 45 manos de `8b44917` + 47 de `c1c1370` − `H_1323`.

Esta tarea no vuelve a investigar esos fallos desde cero. Solo verifica, con scripts de lectura, los valores necesarios para diseñar la política.

### 2.5 Comprobaciones adicionales de esta fase

Sin escribir en la base:

- 1344 manos y 16486 acciones totales en la base actual.
- 2832 calls totales; 47 calls por debajo de la viva.
- Las 5 calls cortas nuevas son `H_1287` preflop (CO, 1.0 vs 6.0), `H_1303` turn (SB, 3.9 vs 6.2), `H_1310` preflop (SB, 1.0 vs 3.0), `H_1310` flop (SB, 4.3 vs 4.4) y `H_1365` flop (SB, 83.9 vs 84.6).
- I4 actual: 13 entradas = 1 violación real conocida (`H_0740`) + 12 stacks desconocidos tratados como cero; histórico: 12 = 1 + 11.
- CM-004: la regla reconoce la ciega del BB en 1344 de 1344 manos.
- Los tres pares SB/BB no nulos actuales: `H_0104` (−8; SB 1.0 en viva 1.0 frente a BB 9.0 en viva 9.0), `H_1310` (−2; SB 1.0 y BB 3.0 en la misma viva 3.0) y `H_1365` (−28; SB 1.0 en viva 1.0 frente a BB 29.0 en viva 29.0).
- `H_1303`: la SB acumula 10.3, exactamente su stack; la call corta de 3.9 es compatible con un all-in corto, pero `allin` declara a otro jugador.
- `H_1365`: la SB acumula 112.9, exactamente su stack; la call corta de 83.9 es compatible con un all-in corto, pero `allin` declara a otro jugador.

Estas comprobaciones no adjudican las manos; solo separan evidencia de interpretación.

---

## 3. Inventario semántico de los 22 tests

### 3.1 Criterio de lectura

Cada test se describe por:

- **contrato que protege**: la propiedad o decisión que no debería romperse;
- **fuente y población**: si lee toda la base, una cohorte o un fixture;
- **tipo de expectativa**: absoluta, relativa, estructural o semántica;
- **defecto que debe detectar**;
- **cambio legítimo que debe permitir**;
- **cambio que debe seguir haciendo fallar**.

Los tipos A–E son los del encargo:

- **A**: instantánea histórica de un conjunto identificado.
- **B**: invariante sobre datos dinámicos.
- **C**: subconjunto identificado por procedencia o pertenencia.
- **D**: comportamiento del código con fixtures.
- **E**: auditoría o diagnóstico que debe seguir detectando anomalías.

### 3.2 Tabla de inventario

| # | Test y ubicación | Contrato que protege | Fuente / población | Expectativa | Defecto que detecta | Cambio legítimo permitido | Cambio que debe fallar |
|---:|---|---|---|---|---|---|---|
| 1 | `motor/test_accion_p.py::test_la_base_de_hoy_ya_usa_p` (208) | La base canónica usa `p` para postas y no hay `p` en calles postflop. | `learn.load_hands(reliable_only=False)`, base completa. | Absoluta: `{'preflop': 2522}`. | Recodificación silenciosa de ciegas/limps, o `p` en una calle que no es preflop. | Nuevas manos con postas preflop legales; una nueva versión de la base con su censo revisado. | `p` en flop/turn/river; postas eliminadas o convertidas a `b`; censo distinto sin revisión. |
| 2 | `motor/test_auditar_origen.py::test_las_cifras_de_posiciones_estan_fijadas` (127) | Inventario de posiciones y ciegas: toda mano tiene BB; no hay duplicados; las SB/BB presentes tienen posting. | `AO.cargar()`, base completa. | Mixta: absoluta (`1253`, `1220`, `33`) y estructural (postings y duplicados). | Pérdida de BB/SB, posting ausente, posición duplicada. | Nuevas manos 6-max con BB y, si procede, SB; nuevas ausencias de SB documentadas. | Una mano sin BB; un SB/BB presente sin posting; posiciones duplicadas; una ausencia de SB no declarada. |
| 3 | `motor/test_auditar_origen.py::test_un_jugador_sin_pos_es_uno_que_no_jugo` (161) | Un jugador sin `pos` no tiene acciones: `pos` es la única clave de atribución. | `AO.cargar()`, base completa. | Absoluta (`sin_pos=804`) + invariante (`con_accion=0`). | Acción de un jugador sin posición, que sería inasignable. | Nuevas entradas de jugador sin `pos` que no actúan. | Cualquier acción con `pos` vacía o de un jugador sin posición. |
| 4 | `motor/test_auditar_origen.py::test_no_hay_mesa_corta_ni_ante_ni_straddle` (183) | No hay mesas cortas, antes ni straddles; las postas son 0.5/1.0 y el BB está al principio o tras la SB. | `AO.seccion_1e` y `AO.cargar()`, base completa. | Absoluta (`{6: 1253}`) + estructural. | Mesa de menos de 6, ante/straddle o BB fuera de orden. | Nuevas manos de 6 jugadores con postas 0.5/1.0 y orden correcto. | Un `n_jugadores` distinto de 6; importe de posta distinto de 0.5/1.0; BB fuera de índice 0/1; primera acción distinta de SB `p` cuando el BB está en índice 1. |
| 5 | `motor/test_auditar_origen.py::test_la_ciega_del_bb_que_existe_es_siempre_la_misma` (214) | La ciega del BB vale 1.0 y la SB 0.5; el BB solo está en índice 0 o 1. | `AO.seccion_1`, base completa. | Absoluta (`{1.0: 1253}`, `{0.5: 1220}`) + estructural. | Importe de ciega cambiado o índice de BB inválido. | Nuevas manos con las mismas ciegas y el mismo orden. | Un BB de importe distinto de 1.0; una SB de importe distinto de 0.5; BB en índice distinto de 0/1. |
| 6 | `motor/test_auditar_origen.py::test_las_calls_que_no_llegan_a_la_viva` (302) | Detector de calls cuya caja no alcanza la viva, con reparto por calle y el caso `H_0058`. | `AO.cargar()`, base completa. | Absoluta (`42`; `8/12/12/10`) + fixture de `H_0058`. | Calls por debajo de la viva, incluidas lecturas obsoletas o secuencias imposibles. | Nuevas calls que sean parciales legítimas o all-in por menos, si el contrato las separa; nuevas calles con el mismo detector. | Una call corta nueva no declarada; una call que desaparece del detector sin justificación; un cambio en `H_0058` fuera de su fixture. |
| 7 | `motor/test_auditar_origen.py::test_el_patron_del_bb_es_exacto_no_aproximado` (368) | Comparación de importes de call SB/BB para detectar desalineación de cajas. | `AO.seccion_2c`, base completa. | Absoluta (`52` parejas; `-8:1`, `0:51`). | Desalineación de cajas entre ciegas. | Nada mientras la métrica compare niveles distintos; solo una comparación al mismo nivel puede admitir crecimiento. | Cualquier comparación que siga tomando la primera call de cada posición como equivalente; un `-8`/`-28` aceptado como si fuera una discrepancia de caja. |
| 8 | `motor/test_auditar_origen.py::test_el_bote_exacto_cuadra_en_373_de_1253` (398) | Reconciliación exacta/falta/sobra de `final_pot` contra lo aportado, en la base histórica de 1253. | `AO.seccion_3`, base completa; el nombre fija 1253. | Absoluta histórica (`373`, `3`, `877`). | Un detector que empieza a cuadrar más porque dejó de mirar; una pérdida de reconciliación. | Nuevas manos no deben cambiar el snapshot de 1253; la base dinámica se mide con un invariante aparte. | Que el snapshot de 1253 cambie sin cambiar de snapshot; que la partición current no sume el total. |
| 9 | `motor/test_auditar_origen.py::test_el_rake_no_explica_el_bote` (425) | La regla del rake (5% hasta 2.5) no explica mejor el bote que la ausencia de rake. | `AO.aportar_por_jugador`, base completa. | Absoluta (`373`, `268`) + relativa (`con_rake < sin_rake`). | Que el rake se convierta en una explicación universal; que el detector deje de mirar. | Nuevas manos si la relación `con_rake < sin_rake` se mantiene. | Que `con_rake >= sin_rake` (la regla dejaría de empeorar el ajuste) o que ambos sean cero por un detector apagado. |
| 10 | `motor/test_auditar_origen.py::test_aportar_mas_que_el_stack_no_depende_del_rake` (436) | Invariante I4 (aportado > stack), I2 (bote no supera aportado) e I1 (bote no negativo). | `AO.seccion_3c`, base completa. | Absoluta (`I4=12`, `I2=3`, `I1=true`). | Aportación superior al stack; bote negativo o superior a lo aportado. | Stacks conocidos que cumplan; stacks desconocidos tratados como desconocidos, no como cero. | Contar un `stack: null` como violación; perder una violación de stack conocido; convertir el nulo en 0.0 silenciosamente. |
| 11 | `motor/test_auditar_origen.py::test_el_json_y_el_informe_cuentan_lo_mismo` (498) | El reparto de §3 y los inventarios SB/BB cubren el mismo total que §1. | `AO.seccion_1` y `AO.seccion_3`, base completa. | Identidad interna + literal (`1253`). | Dos cálculos parecidos que dejan de hablar entre sí. | Cualquier total N, si las identidades se cumplen. | Que `total != exactas + sobra + falta`; que las sumas SB/BB no cubran el total. |
| 12 | `motor/test_cm004.py::test_el_invariante_de_cm004_puede_dispararse` (516) | La regla CM-004 sigue reconociendo la ciega del BB y no está apagada. | `learn.load_hands(path=...)`, base completa. | Absoluta (`CIEGAS_RECONOCIDAS=1253`). | Un invariante que da cero porque no hay nada que mirar; una regla desactivada. | Nuevas manos con BB reconocido; cobertura completa de la base. | Que la regla no reconozca la ciega en una mano; que `con_ciega` sea 0 o menor que el total sin justificación. |
| 13 | `motor/test_diagnostico_grabador.py::test_la_base_son_dos_grabadores` (642) | La base mezcla dos grabadores; el grupo sin `allin` es una cohorte fija de 71 manos. | Lectura directa de `data/hands_db.jsonl`, agrupada por presencia de `allin`. | Absoluta (`1182/71`) + cohorte fija de IDs. | Que se pierda la separación de grabadores o que el bloque de 71 cambie. | Nuevas manos live con `allin`; el grupo `record_hand` sigue siendo el mismo. | Que una mano del bloque de 71 gane `allin`; que aparezca/desaparezca un ID del bloque; que el grupo live se mezcle con el hand. |
| 14 | `motor/test_diagnostico_grabador.py::test_la_apertura_cambia_tras_la_normalizacion` (680) | La letra de la primera acción voluntaria ya no es huella del grabador; el grupo `hand` conserva su mezcla y el live cumple `c > r > b`. | Lectura directa, agrupada por `allin`. | Absoluta por grupo (`hand 31/29/4`; `live 100/520/467`) + relativa. | Que la normalización no haya cambiado la apertura; que la letra vuelva a separar grabadores. | Nuevas manos live si se mantiene `c > r > b`; cohorte hand sin cambios. | Que el grupo hand cambie; que en live `b >= c` o `r >= c`; que aparezca una primera acción fuera de `b/c/r`. |
| 15 | `motor/test_diagnostico_grabador.py::test_las_42_calls_por_debajo_de_la_viva` (780) | Detector de calls por debajo de la viva, con total de calls y calls cortas. | `DG.cargar()`, base completa. | Absoluta (`2603`, `42`). | Calls cortas, incluidas lecturas obsoletas y all-in por menos. | Nuevas calls si el contrato separa las parciales legítimas; nuevas calles con el mismo detector. | Una call corta nueva no declarada; un total de calls que deje de corresponder a las acciones `c`; una call que desaparezca sin justificación. |
| 16 | `motor/test_diagnostico_grabador.py::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` (796) | El hallazgo “no es solo del BB”: hay calls cortas en varias posiciones; `falta=1.0` y BB son un subconjunto, no la explicación única. | `DG.calls_por_debajo`, base completa. | Absoluta (`42`, `3`, `10`) + cualitativa. | Que el detector se convierta en una explicación única del BB. | Nuevas calls cortas en otras posiciones si el ledger se revisa. | Que todas las calls cortas sean del BB; que MP/CO/UTG desaparezcan; que `uno`/`BB` cambien sin revisión. |
| 17 | `motor/test_diagnostico_grabador.py::test_la_clasificacion_sobre_la_base` (809) | Cada acción con dinero recibe exactamente una clasificación calculable/sospechosa/indeterminada. | `DG.clasificar_aportado`, base completa. | Absoluta (`5001/29/23`). | Cambio de clasificador o pérdida de acciones. | Nuevas acciones limpias; nuevas sospechosas/indeterminadas declaradas con ID y motivo. | Una acción sin clasificación; una clasificación nueva no declarada; totales que no suman el total de acciones clasificadas. |
| 18 | `motor/test_diagnostico_grabador.py::test_el_desglose_por_accion_por_resultado_es_coherente` (838) | La matriz acción × resultado suma por filas y por columnas, y coincide con los totales absolutos. | `DG.clasificar_aportado`, base completa. | Absoluta (`b 1444/4`, `c 2559/21/23`, `r 998/4`; total `5053`) + estructural. | Que la matriz y los totales dejen de hablar entre sí. | Nuevas acciones si filas y columnas siguen cuadrando. | Una fila/columna que no suma el total; una acción fuera de `b/c/r`; un total de matriz distinto de la suma de clasificaciones. |
| 19 | `motor/test_diagnostico_grabador.py::test_el_reparto_por_accion_suma_el_total_de_la_base` (870) | Las acciones que aportan (`b/c/r`) suman exactamente el total de la matriz; `f`/`x` quedan fuera a propósito. | `DG.clasificar_aportado`, base completa. | Absoluta (`b=1448`, `c=2603`, `r=1002`, suma `5053`). | Que la exclusión de `f/x` sea la que se cree; que falte o sobre una acción. | Nuevas acciones que aportan, si la suma sigue cuadrando. | Que la suma no sea el total de la matriz; que se incluya `f`/`x`; que una acción desaparezca. |
| 20 | `motor/test_diagnostico_grabador.py::test_los_ids_se_resuelven_con_el_boton` (930) | `get_position(pid, btn_player)` resuelve IDs de `allin`; un ID resuelto puede contrastarse con su stack. | Base completa + `record_hand.get_position`. | Absoluta (`204` resueltos, `46` confirmados) + comportamiento. | Un fallo de resolución de IDs o una lista `allin` que no se puede atribuir. | Nuevos IDs de `allin` que resuelven a posiciones válidas. | Un ID que no resuelve; una posición inexistente; un compromiso que contradice el stack sin declaración. |
| 21 | `motor/test_lista_saneamiento.py::test_por_defecto_cubre_toda_la_base` (190) | El alcance por defecto de `LS.construir` es toda la base, no `H_1014` ni un rango recortado. | `LS.cargar()` y `LS.construir(..., None)`, base completa. | Absoluta (`1253`). | Que el alcance se recorte a lo que ya se conocía. | Nuevas manos: el alcance debe incluirlas. | Que `resumen['manos'] != len(manos)`; que se excluya una mano sin justificación. |
| 22 | `motor/test_lista_saneamiento.py::test_el_rango_por_defecto_sigue_siendo_toda_la_base` (270) | Además del alcance total, `H_1282` —última mano de la revisión manual— sigue dentro. | `LS.cargar()` y `LS.construir(..., None)`. | Absoluta (`1253`) + pertenencia (`H_1282`). | Que se recorte el alcance justo después de la revisión. | Nuevas manos posteriores a `H_1282`, si el alcance total se mantiene. | Que `H_1282` desaparezca del alcance; que el total no sea el de la base; que el rango se recorte. |

### 3.3 Lo que el inventario excluye

- Ninguno de los 22 tests usa `data/preflop_matrices.json`, `data/calibration_window.json` ni otro derivado como fuente. La causa no es un artefacto desactualizado.
- Ninguno de los 22 tests escribe datos ni comparte un fixture mutable. No hay dependencia de orden observada.
- El hecho de que un test contenga un literal de 1253 no lo convierte automáticamente en snapshot histórico. Hay que mirar qué propiedad protege.
- El hecho de que un test use la base completa no lo convierte automáticamente en invariante. Hay que mirar si su expectativa depende del número de manos.

---

## 4. Matriz de clasificación y recomendación individual

### 4.1 Tabla principal

Leyenda: **A** snapshot histórico; **B** invariante dinámico; **C** subconjunto identificado; **D** comportamiento con fixtures; **E** auditoría/diagnóstico.

| Test | Qué protege | Tipo de prueba | Recomendación | Evidencia | Riesgo | Decisión pendiente |
|---|---|---|---|---|---|---|
| 1. `test_la_base_de_hoy_ya_usa_p` | Adopción de `p` y ausencia de `p` postflop. | A | `CORREGIR_EXPECTATIVA_OBSOLETA` | 2522 en 1253; 2702 en 1344; +180; todo preflop. | Conservarlo deja rojo y no distingue crecimiento de recodificación; actualizarlo en masa lo vuelve frágil otra vez. | Aprobar el snapshot 1344 con 2702; no actualizar automáticamente en el futuro. |
| 2. `test_las_cifras_de_posiciones_estan_fijadas` | BB en todas; SB/BB con posting; sin duplicados. | B | `CONVERTIR_A_INVARIANTE` | 1344/1309/35; +89 SB; +2 sin SB (`H_1300`, `H_1369`); postings y duplicados en 0. | Conservar 1253 falla por crecimiento; quitar los recuentos sin un conjunto de ausencias declarado podría ocultar una pérdida de SB. | Aprobar el conjunto explícito de manos sin SB y el contrato de posting. |
| 3. `test_un_jugador_sin_pos_es_uno_que_no_jugo` | Un jugador sin `pos` no actúa. | B | `CONVERTIR_A_INVARIANTE` | `sin_pos` 804→861; `con_accion=0` en ambas bases. | Conservar 804 falla por crecimiento; eliminar la propiedad permitiría acciones inasignables. | Ninguna para la propiedad; el censo de `sin_pos` puede quedar como diagnóstico. |
| 4. `test_no_hay_mesa_corta_ni_ante_ni_straddle` | 6 jugadores; postas 0.5/1.0; BB en índice 0/1. | B | `CONVERTIR_A_INVARIANTE` | `{6: 1253}` → `{6: 1344}`; el resto de la prueba sigue pasando. | Conservar 1253 falla por crecimiento; aceptar cualquier `n_jugadores` debilitaría la detección de mesas cortas. | Confirmar que una mesa corta legítima, si existiera, requeriría una excepción explícita. |
| 5. `test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | BB 1.0, SB 0.5; índice 0/1. | B | `CONVERTIR_A_INVARIANTE` | BB 1.0 en 1344; SB 0.5 en 1309; no hay importes nuevos. | Conservar los recuentos falla; aceptar cualquier importe permitiría una ciega mal grabada. | Ninguna; el contrato de importes ya está claro. |
| 6. `test_las_calls_que_no_llegan_a_la_viva` | Detector de calls cortas y caso `H_0058`. | E | `REQUIERE_DECISION_MANUAL` | 42→47; 5 nuevas; `H_1287` y `H_1310` (2) confirmadas como secuencias anómalas; `H_1303`/`H_1365` no adjudicadas. | Conservar 42 falla; actualizar a 47 declararía como defecto dos posibles all-in cortos. | Decidir el contrato de call parcial/all-in corto y adjudicar `H_1303`/`H_1365`. |
| 7. `test_el_patron_del_bb_es_exacto_no_aproximado` | Comparación de cajas SB/BB. | E | `REQUIERE_DECISION_MANUAL` | 60 parejas; `H_0104` −8 y `H_1365` −28 son niveles distintos; `H_1310` −2 es una call corta en el mismo nivel. | Conservar la métrica produce falsos positivos y mezcla defectos; actualizar a 60 acepta un artefacto. | Definir comparación al mismo nivel y revisar `H_0104`/`H_1310`/`H_1365`. |
| 8. `test_el_bote_exacto_cuadra_en_373_de_1253` | Reconciliación exacta/falta/sobra en 1253. | A | `CONSERVAR_SNAPSHOT` | 1253: 373/3/877; 1344: 394/3/947; `falta` no cambia. | Conservar 1253 deja la base actual sin censo; actualizar a 394/947 repite el problema con la próxima growth. | Aprobar el snapshot 1253 y un invariante de partición para la base actual. |
| 9. `test_el_rake_no_explica_el_bote` | El rake no mejora el ajuste; `con_rake < sin_rake`. | B | `CONVERTIR_A_INVARIANTE` | 394/270; +21/+2; la relación sigue. | Conservar 373/268 falla; actualizar solo los números no prueba la regla. | Ninguna para la relación; los censos pueden ir a informe/snapshot. |
| 10. `test_aportar_mas_que_el_stack_no_depende_del_rake` | I4/I2/I1; aportado > stack. | B | `REQUIERE_DECISION_MANUAL` | 13 = 1 real (`H_0740`) + 12 null; histórico 12 = 1 + 11; `H_1349` añade el nulo nuevo. | Conservar 12 falla; actualizar a 13 consagra el nulo como cero. | Definir `stack` desconocido vs cero y adjudicar `H_1349`; corregir el helper antes de fijar I4. |
| 11. `test_el_json_y_el_informe_cuentan_lo_mismo` | Identidad entre §1 y §3. | B | `CONVERTIR_A_INVARIANTE` | Con 1344 la primera aserción pasa; solo fallan los literales; sumas SB/BB = 1344. | Conservar 1253 falla; cambiar 1253 por 1344 vuelve a fijar un literal. | Ninguna; el total debe salir de `s1['total']`/`len(manos)`. |
| 12. `test_el_invariante_de_cm004_puede_dispararse` | La regla CM-004 no está apagada. | E | `CONVERTIR_A_INVARIANTE` | 1253→1344 de 1344; todas las nuevas tienen BB reconocido; el invariante de violaciones sigue en 0. | Conservar 1253 falla; un `>0` toleraría el caso de 6/1258 que el test quiere distinguir. | Ninguna; el contrato es cobertura completa, no el literal 1253. |
| 13. `test_la_base_son_dos_grabadores` | Dos grabadores; cohorte fija sin `allin` de 71 manos. | C | `DEFINIR_SUBCONJUNTO` | 1182→1273 con `allin`; 71 sin `allin`; IDs `H_0001..H_0073` menos `H_0028`/`H_0072`. | Conservar 1182 falla; quitar la cohorte de 71 ocultaría una mezcla de grabadores. | Confirmar que `allin` es la huella de procedencia y que el bloque de 71 es cerrado. |
| 14. `test_la_apertura_cambia_tras_la_normalizacion` | La letra no separa grabadores; `hand` conserva mezcla; live `c > r > b`. | C | `DEFINIR_SUBCONJUNTO` | `hand` 31/29/4 sin cambios; live `b=100`, `c=561`, `r=514`; +41/+47. | Conservar los recuentos live falla; quitar la cohorte hand permitiría una regresión de normalización. | Confirmar la cohorte hand y el invariante live; los censos live van a informe. |
| 15. `test_las_42_calls_por_debajo_de_la_viva` | Detector de calls cortas y total de calls. | E | `REQUIERE_DECISION_MANUAL` | 2603→2832 calls; 42→47 cortas; mismas 5 nuevas. | Conservar 42 falla; actualizar a 47 declara como defecto dos posibles all-in cortos. | El mismo contrato pendiente de los casos 6/16 y la adjudicación de `H_1303`/`H_1365`. |
| 16. `test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | No es solo del BB; `falta=1.0` y BB son subconjuntos. | E | `REQUIERE_DECISION_MANUAL` | 47 cortas; `uno=3`; `BB=10`; MP/CO/UTG > 0; las nuevas añaden CO y SB. | Conservar 42 falla; actualizar los recuentos sin adjudicar mantiene la conclusión pero no el detalle. | Aprobar el ledger de calls cortas y conservar la propiedad cualitativa. |
| 17. `test_la_clasificacion_sobre_la_base` | Cada acción con dinero tiene una clasificación. | B | `CONVERTIR_A_INVARIANTE` | 5001/29/23 → 5417/33/26; total 5476; +423. | Conservar los totales falla; actualizarlos sin ledger oculta nuevas sospechosas/indeterminadas. | Aprobar el ledger de acciones sospechosas/indeterminadas. |
| 18. `test_el_desglose_por_accion_por_resultado_es_coherente` | Matriz acción × resultado coherente por filas y columnas. | B | `CONVERTIR_A_INVARIANTE` | Matriz 1541/4, 2781/25/26, 1095/4; total 5476; filas/columnas siguen. | Conservar 5053 falla; actualizar la matriz sin comprobar coherencia la vuelve una foto. | Ninguna para la coherencia; el censo exacto puede ser snapshot. |
| 19. `test_el_reparto_por_accion_suma_el_total_de_la_base` | `b/c/r` suman el total; `f/x` fuera. | B | `CONVERTIR_A_INVARIANTE` | 1545/2832/1099 = 5476; coincide con la matriz. | Conservar 5053 falla; actualizar los totales sin la suma permite que la exclusión se rompa. | Ninguna para la suma; los totales exactos pueden ir a informe. |
| 20. `test_los_ids_se_resuelven_con_el_boton` | `get_position` resuelve IDs de `allin`. | D | `REEMPLAZAR_POR_FIXTURE` | 204→221 resueltos; 46→49 confirmados; +17/+3. | Conservar 204 falla; quitar el contraste con datos podría ocultar IDs irresolubles. | Aprobar fixtures de resolución y un invariante de “ningún ID irresoluble”. |
| 21. `test_por_defecto_cubre_toda_la_base` | El alcance por defecto es toda la base. | B | `CONVERTIR_A_INVARIANTE` | 1253→1344; `resumen['manos'] == len(manos)`. | Conservar 1253 falla; un `>0` permitiría un rango recortado. | Ninguna; el contrato es la igualdad con el total actual. |
| 22. `test_el_rango_por_defecto_sigue_siendo_toda_la_base` | Alcance total y `H_1282` dentro. | B | `CONVERTIR_A_INVARIANTE` | 1344; `H_1282` presente. | Conservar 1253 falla; quitar `H_1282` perdería la garantía de la revisión manual. | Ninguna; conservar la pertenencia de `H_1282` y la igualdad con el total. |

### 4.2 Justificación, riesgos y aceptación por caso

#### Caso 1 — `test_la_base_de_hoy_ya_usa_p`

- **Justificación:** es un censo de adopción de la codificación `p`. El valor 2522 es el censo de 1253; el censo de la base adoptada de 1344 es 2702. No es un invariante: depende del número de manos y de sus postas.
- **Riesgo de conservarlo:** la suite sigue roja y el test se vuelve un recordatorio histórico que no describe la base actual.
- **Riesgo de modificarlo:** sustituir 2522 por 2702 sin identificar la fuente repite el fallo en la próxima growth; convertirlo en `p > 0` deja de detectar una recodificación silenciosa.
- **Evidencia:** subconjunto 1253 = 2522; base actual = 2702; +180; todas las `p` están en preflop; no hay `p` en flop/turn/river.
- **Comprobación conceptual:** cargar un snapshot `canonical-1344` por commit + SHA + líneas; comprobar el hash antes de leer; contar `p` por calle; exigir `{'preflop': 2702}` y cero en las demás calles.
- **Aceptación:** snapshot aprobado; el test falla si cambia el hash, si hay `p` postflop o si el censo del snapshot cambia; una base futura exige una entrada de snapshot nueva, no una edición automática.

#### Caso 2 — `test_las_cifras_de_posiciones_estan_fijadas`

- **Justificación:** el test mezcla invariantes (BB en todas, postings, sin duplicados) con un censo de SB. Los invariantes deben quedar; el censo de SB debe ser un conjunto explícito de ausencias o un snapshot.
- **Riesgo de conservarlo:** falla por crecimiento legítimo; el mensaje “alguien cambió la base” se vuelve ruido.
- **Riesgo de modificarlo:** eliminar `sin_SB` sin declarar las ausencias permitiría que una pérdida de SB pase como “sin SB legítimo”.
- **Evidencia:** 1344 manos; 1309 con SB; 35 sin SB; las nuevas sin SB son `H_1300` y `H_1369`; `BB_sin_posting=0`, `SB_sin_posting=0`, `con_pos_duplicada=0`.
- **Comprobación conceptual:** exigir `con_BB == total`, `sin_BB == 0`, `BB_sin_posting == 0`, `SB_sin_posting == 0`, `con_pos_duplicada == 0`; para las ausencias de SB, comparar el conjunto de IDs con un conjunto aprobado (33 históricas + `H_1300` + `H_1369`) y exigir motivo por ID. No usar `1253`.
- **Aceptación:** nuevas manos con SB pasan; una mano sin SB no declarada falla; una SB presente sin posting falla; el conteo se deriva del total y del conjunto de ausencias, no de un literal.

#### Caso 3 — `test_un_jugador_sin_pos_es_uno_que_no_jugo`

- **Justificación:** la propiedad que sostiene la conclusión de §1.4 es `con_accion == 0`; `sin_pos` es un censo. La propiedad no depende de que haya 804 u 861 entradas.
- **Riesgo de conservarlo:** falla por crecimiento; se confunde “hay más jugadores sin posición” con “la conclusión se cayó”.
- **Riesgo de modificarlo:** quitar la propiedad permitiría acciones de jugadores sin `pos`, que son inasignables.
- **Evidencia:** `sin_pos` 804→861; `con_accion=0` en 1253 y 1344; +57 entradas sin `pos` en las nuevas; B1-E cuenta “activos sin posición” con otro criterio y no es comparable.
- **Comprobación conceptual:** para cada jugador con `pos` vacía, recorrer todas las calles y exigir que no exista una acción suya; contar `sin_pos` solo como diagnóstico. Si se quiere un censo, incluirlo en el informe, no como condición de la propiedad.
- **Aceptación:** cualquier acción con `pos` vacía falla; nuevas entradas sin `pos` que no actúan pasan; el test no contiene 804.

#### Caso 4 — `test_no_hay_mesa_corta_ni_ante_ni_straddle`

- **Justificación:** “no hay mesa corta, ante ni straddle” es una propiedad estructural; `{6: 1253}` es solo el censo de la base histórica.
- **Riesgo de conservarlo:** falla por crecimiento; el censo tapa la propiedad.
- **Riesgo de modificarlo:** aceptar `n_jugadores >= 6` o cualquier importe debilitaría la detección de mesas cortas, antes y straddles.
- **Evidencia:** `{6: 1344}`; todas las postas siguen en 0.5/1.0; el BB sigue en índice 0/1; cuando está en 1, la primera acción es SB `p`.
- **Comprobación conceptual:** exigir que todas las manos tengan 6 jugadores; que cada `p` preflop tenga `pos` válida e importe 0.5/1.0; que el posting del BB exista y esté en índice 0/1; que la primera acción sea SB `p` si el BB está en 1.
- **Aceptación:** nuevas manos 6-max pasan; una mesa de 5, un ante/straddle o un BB fuera de orden fallan; no se exige un total de manos.

#### Caso 5 — `test_la_ciega_del_bb_que_existe_es_siempre_la_misma`

- **Justificación:** la propiedad es el conjunto de importes y el orden, no el número de postings. `{1.0: 1253}` y `{0.5: 1220}` son censos.
- **Riesgo de conservarlo:** falla por crecimiento; el mensaje “la ciega cambió” se dispara por manos nuevas.
- **Riesgo de modificarlo:** aceptar cualquier importe o cualquier índice permitiría una ciega mal grabada.
- **Evidencia:** BB 1.0 en 1344; SB 0.5 en 1309; no hay importes nuevos; los índices siguen válidos.
- **Comprobación conceptual:** exigir `set(bb_importes) <= {1.0}` y `set(sb_importes) <= {0.5}`; recorrer los postings y exigir índice 0/1; la existencia de BB/SB se cubre en el caso 2.
- **Aceptación:** nuevas ciegas con 1.0/0.5 pasan; un importe distinto o un índice inválido fallan; el test no contiene 1253/1220.

#### Caso 6 — `test_las_calls_que_no_llegan_a_la_viva`

- **Justificación:** es un detector de anomalías, no un censo estable. El total 42 es una medición de la base de 1253; 47 es la medición actual, pero no todo 47 es un defecto demostrado.
- **Riesgo de conservarlo:** rojo permanente; el detector se lee como “42 defectos” cuando ya hay 47 calls cortas y la base creció.
- **Riesgo de modificarlo:** actualizar a 47 sin adjudicar `H_1303`/`H_1365` convierte dos posibles all-in cortos en defectos; eliminar el test deja de detectar calls cortas.
- **Evidencia:** 42→47; reparto 8/12/12/10→10/14/13/10; `H_1287` (CO 1.0 vs 6.0) y `H_1310` (SB 1.0 vs 3.0; SB 4.3 vs 4.4) son secuencias anómalas ya declaradas; `H_1303` y `H_1365` no están adjudicadas. `H_0058` sigue igual.
- **Comprobación conceptual:** conservar `H_0058` como fixture literal; para el resto, comparar el conjunto de calls cortas con un **ledger aprobado** de `(hand_id, calle, índice, pos, amount, viva, motivo)`. Una entrada nueva falla; una entrada del ledger que desaparece exige una baja aprobada. El total 47 se reporta, no se usa como contrato.
- **Aceptación:** el ledger está aprobado y cada call corta tiene estado (defecto confirmado, parcial legítima, all-in corto, pendiente); una call no declarada falla; `H_1303`/`H_1365` tienen decisión manual; no se actualiza 42→47 en masa.

#### Caso 7 — `test_el_patron_del_bb_es_exacto_no_aproximado`

- **Justificación:** la relación que pretende medir es “la caja de la SB y la del BB se alinean con la misma viva”, no “la primera call de cada posición es comparable”. La posición en la lista no garantiza el mismo nivel.
- **Riesgo de conservarlo:** falsos positivos (`H_0104`, `H_1365`) y un falso negativo conceptual: un defecto real puede quedar oculto si ambas primeras calls coinciden por casualidad.
- **Riesgo de modificarlo:** actualizar a 60 y aceptar `-28`/`-8` como diferencias conocidas consagra un artefacto; mantener la comparación por orden cambia solo el número, no el contrato.
- **Evidencia:** `H_0104`: SB 1.0 en viva 1.0, BB 9.0 en viva 9.0; `H_1365`: SB 1.0 en viva 1.0, BB 29.0 en viva 29.0; `H_1310`: SB 1.0 y BB 3.0 en la misma viva 3.0, con call posterior de SB a 3.0. Los tres no nulos actuales no son la misma clase de hecho.
- **Comprobación conceptual:** para cada call, comprobar `amount == viva_antes` dentro de tolerancia; si se emparejan SB y BB, hacerlo solo cuando ambas calls tengan la misma `viva_antes` en la misma calle y sean calls; entonces exigir que sus importes coincidan o que ambas alcancen la viva. No usar `sb[0]`/`bb[0]` como equivalencia.
- **Aceptación:** `H_0104` y `H_1365` no forman pareja; `H_1310` se detecta por su call corta al mismo nivel; el `-8` histórico no se conserva como “diferencia conocida”; el número 60 no se fija como contrato; la decisión sobre `H_0104`/`H_1310`/`H_1365` es manual.

#### Caso 8 — `test_el_bote_exacto_cuadra_en_373_de_1253`

- **Justificación:** el nombre y el propósito son un snapshot histórico de 1253. La expectativa 373/3/877 no debe cambiar cuando entren manos nuevas.
- **Riesgo de conservarlo:** la base actual no queda cubierta por este test; hay que añadir un invariante de partición para 1344.
- **Riesgo de modificarlo:** actualizar a 394/3/947 sin snapshot repite el ciclo y puede ocultar un cambio del detector.
- **Evidencia:** 1253 = 373/3/877; 1344 = 394/3/947; `falta` sigue en 3; +21 exactas y +70 sobrantes en las nuevas.
- **Comprobación conceptual:** cargar el snapshot 1253 por commit/SHA; exigir 373/3/877; en la base actual, exigir `exactas + sobra + falta == total` y un ledger de las manos con `falta` distinto de cero. El snapshot no se actualiza; el invariante sí se ejecuta sobre la base actual.
- **Aceptación:** el snapshot 1253 es inmutable; la partición actual no pierde manos; una mano nueva exacta no obliga a cambiar el snapshot; una mano nueva con falta no declarada falla el invariante.

#### Caso 9 — `test_el_rake_no_explica_el_bote`

- **Justificación:** la propiedad es la relación `con_rake < sin_rake`, no los recuentos 373/268. Los recuentos son censos de la base.
- **Riesgo de conservarlo:** falla por crecimiento; se confunde “más manos” con “el rake empezó a explicar el bote”.
- **Riesgo de modificarlo:** actualizar 373/268 sin la relación deja la regla del rake sin prueba; quitar la relación permitiría que el rake se vuelva una explicación universal.
- **Evidencia:** 394/270; +21 exactas sin rake y +2 con rake; `con_rake < sin_rake` sigue siendo verdadero.
- **Comprobación conceptual:** calcular ambos ajustes; exigir `sin_rake > 0`, `con_rake > 0` y `con_rake < sin_rake`; comprobar que ambos conjuntos particionan las manos con `final_pot` numérico; reportar los recuentos exactos sin fijarlos como contrato.
- **Aceptación:** nuevas manos pasan si la relación se mantiene; si el rake deja de empeorar el ajuste, el test falla para revisar la regla; no se fijan 373/268.

#### Caso 10 — `test_aportar_mas_que_el_stack_no_depende_del_rake`

- **Justificación:** I4 debe comparar aportación contra stack **conocido**. Un `stack: null` es un valor desconocido, no un cero. El helper actual `float(p.get('stack') or 0.0)` borra esa distinción.
- **Riesgo de conservarlo:** el test sigue rojo y, peor, su 12 histórico se lee como “12 violaciones” cuando en realidad es 1 violación real + 11 nulos; el 13 actual es 1 + 12 nulos.
- **Riesgo de modificarlo:** actualizar a 13 consagra el nulo como cero; excluir todos los nulos sin contarlos pérdida de información; usar 45.9 como stack de `H_1349` sin aprobación convierte un candidato en dato.
- **Evidencia:** `H_1349` UTG stack `None`, aportación 3.0; `H_0740` SB 28.2 > 28.1 es la única violación real; 12 stacks desconocidos en la base actual (11 históricos + `H_1349`); I2=3 e I1=true no cambian.
- **Comprobación conceptual:** para cada jugador, clasificar el stack en `conocido`, `cero_conocido` o `desconocido`. Si es conocido/cero, comparar aportación y contar violación si supera; si es desconocido, contar en `I4_no_evaluable` con ID y no comparar. Prohibir `float(None or 0)`. Mantener I2/I1 como invariantes separados.
- **Aceptación:** `H_0740` sigue siendo violación conocida; `H_1349` aparece como desconocido, no como violación; una violación nueva de stack conocido falla; el contrato de nulo está aprobado; no se fija un único `I4=13`.

#### Caso 11 — `test_el_json_y_el_informe_cuentan_lo_mismo`

- **Justificación:** la prueba debe comprobar que dos cálculos hablan del mismo total, no que el total sea 1253.
- **Riesgo de conservarlo:** falla por crecimiento; el mensaje “el reparto no cubre las 1253” es falso para la base actual.
- **Riesgo de modificarlo:** cambiar 1253 por 1344 vuelve a crear un literal frágil; quitar las identidades permitiría que §1 y §3 se separen.
- **Evidencia:** con 1344, `s1['total'] == exactas + sobra + falta` pasa; las sumas SB/BB dan 1344; solo fallan los literales.
- **Comprobación conceptual:** `s1['total'] == len(manos)`; `s1['total'] == s3['exactas'] + s3['sobra'] + s3['falta']`; `sum(SB) == s1['total']`; `sum(BB) == s1['total']`. Sin constantes numéricas de base.
- **Aceptación:** cualquier total N pasa si las identidades se cumplen; una partición incompleta o una suma SB/BB distinta del total falla; no aparece 1253 ni 1344.

#### Caso 12 — `test_el_invariante_de_cm004_puede_dispararse`

- **Justificación:** el guard debe demostrar que la regla CM-004 no está apagada. Eso se consigue exigiendo cobertura de la ciega en **todas** las manos, no un literal de 1253.
- **Riesgo de conservarlo:** falla por crecimiento; sigue midiendo una foto.
- **Riesgo de modificarlo:** un `> 0` toleraría que la regla solo reconozca 6 de 1258, que es exactamente el “verde que miente” que el test quiere evitar.
- **Evidencia:** 1253→1344 de 1344; todas las nuevas tienen BB reconocido; el invariante de violaciones CM-004 sigue en 0.
- **Comprobación conceptual:** `con_ciega == len(manos)` y `con_ciega > 0`; opcionalmente, para cada mano, comprobar que existe al menos una acción de BB reconocida o un motivo declarado. No usar `CIEGAS_RECONOCIDAS=1253` como contrato.
- **Aceptación:** nuevas manos con BB pasan; una regla apagada o una mano sin BB reconocido falla; no se tolera un cero ni una cobertura parcial.

#### Caso 13 — `test_la_base_son_dos_grabadores`

- **Justificación:** la conclusión importante es que el bloque `record_hand` de 71 manos sigue siendo el mismo y que el grupo live crece. El total 1182 es un censo del grupo live.
- **Riesgo de conservarlo:** falla por crecimiento; el 1182 se vuelve el contrato y no el bloque de 71.
- **Riesgo de modificarlo:** quitar la cohorte de 71 y limitarse a `sin > 0` permitiría que una mano del bloque gane `allin` o que se mezclen grabadores.
- **Evidencia:** 1182→1273 con `allin`; 71 sin `allin`; IDs `H_0001..H_0073` menos `H_0028`/`H_0072`; las 91 nuevas tienen la clave, 74 vacía y 17 con contenido.
- **Comprobación conceptual:** seleccionar la cohorte por ausencia de `allin`; exigir que su conjunto de IDs sea exactamente el declarado y que ninguna de esas líneas tenga `allin`; exigir `con == total - 71` o simplemente `con = total - len(cohorte)`; no fijar 1182.
- **Aceptación:** nuevas manos live pasan; un ID del bloque que cambie de grupo falla; una mano sin `allin` fuera del bloque falla; la cohorte y su motivo están documentados.

#### Caso 14 — `test_la_apertura_cambia_tras_la_normalizacion`

- **Justificación:** la cohorte `hand` es fija; el grupo live es dinámico. La propiedad live es `c > r > b`; los recuentos 100/520/467 son un censo.
- **Riesgo de conservarlo:** falla por crecimiento; el censo live se confunde con el contrato.
- **Riesgo de modificarlo:** conservar solo `c > r > b` sin la cohorte hand perdería la comprobación de que la normalización no cambió el grupo antiguo; actualizar los recuentos live repite el problema.
- **Evidencia:** `hand` 31/29/4 sin cambios; live `b=100`, `c=561`, `r=514`; +41 `c` y +47 `r`; 3 nuevas sin primera acción voluntaria.
- **Comprobación conceptual:** separar por `allin`; en la cohorte hand, exigir 31/29/4; en live, exigir `c > r > b`, que `b` no crezca de forma desproporcionada y que ninguna primera acción quede fuera de `b/c/r`; reportar los recuentos live.
- **Aceptación:** nuevas manos live pasan si la relación se mantiene; un cambio en la cohorte hand falla; una regresión de la letra que invierta `c/r/b` falla; no se fijan 520/467.

#### Caso 15 — `test_las_42_calls_por_debajo_de_la_viva`

- **Justificación:** es un diagnóstico de calls cortas con un total de calls. El total 2603 y las 42 cortas son censos; 2832/47 es la medición actual, no un contrato de defectos.
- **Riesgo de conservarlo:** rojo permanente; el 42 se lee como “defectos” y el total de calls no se actualiza.
- **Riesgo de modificarlo:** actualizar a 2832/47 sin adjudicar las nuevas calls cortas; eliminar el test deja de detectar calls cortas.
- **Evidencia:** 2603→2832 calls; 42→47 cortas; las mismas 5 nuevas; `H_1287`/`H_1310` confirmadas; `H_1303`/`H_1365` pendientes.
- **Comprobación conceptual:** derivar el total de calls del detector/source; comparar el conjunto de calls cortas con el ledger aprobado; comprobar que el total de calls es la cuenta de acciones `c` parseables; reportar el reparto por calle; no usar 2603/42 como contrato.
- **Aceptación:** el total se deriva; el ledger está aprobado; una call corta nueva falla; una call resuelta exige baja del ledger; `H_1303`/`H_1365` tienen decisión manual.

#### Caso 16 — `test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb`

- **Justificación:** la conclusión “no es solo del BB” es cualitativa y estable; los recuentos 42/3/10 son censos. El test debe conservar la propiedad y no una foto.
- **Riesgo de conservarlo:** falla por crecimiento; se confunde el hallazgo cualitativo con los totales.
- **Riesgo de modificarlo:** actualizar 47/3/10 sin ledger; quitar `BB`/`uno` podría ocultar que el detector volvió a una explicación única.
- **Evidencia:** 47 cortas; `uno=3`; `BB=10`; MP/CO/UTG > 0; las nuevas añaden CO (+1) y SB (+4); BB y `falta=1.0` no cambian.
- **Comprobación conceptual:** mantener un ledger de calls cortas; exigir que `BB` no sea igual al total (`BB < len(calls)`) y que MP/CO/UTG tengan al menos una call; reportar `uno` y `BB` desde el ledger; no fijar 42.
- **Aceptación:** nuevas calls en otras posiciones pasan si el ledger se revisa; si todas las calls cortas son del BB, falla; `uno`/`BB` exactos se reportan, no se convierten en contrato.

#### Caso 17 — `test_la_clasificacion_sobre_la_base`

- **Justificación:** la propiedad es que cada acción con dinero recibe una clasificación y que las clasificaciones suman el total; los totales 5001/29/23 son censos.
- **Riesgo de conservarlo:** falla por crecimiento; el total se vuelve una foto.
- **Riesgo de modificarlo:** actualizar 5417/33/26 sin un ledger de sospechosas/indeterminadas puede ocultar una acción nueva mal clasificada.
- **Evidencia:** 5001/29/23→5417/33/26; +423; el clasificador no cambió; la suma es 5476.
- **Comprobación conceptual:** recorrer todas las acciones con dinero; exigir exactamente un resultado por acción y que esté en `{CALCULABLE, SOSPECHOSA, INDETERMINADA}`; exigir que los totales por resultado sumen el total; mantener un ledger de IDs sospechosos/indeterminados con motivo; `CALCULABLE` se deriva.
- **Aceptación:** nuevas acciones limpias pasan; una acción sin clasificación o un resultado desconocido falla; una nueva sospechosa/indeterminada no declarada falla; no se fijan 5001/29/23.

#### Caso 18 — `test_el_desglose_por_accion_por_resultado_es_coherente`

- **Justificación:** la coherencia fila/columna es un invariante; la matriz exacta es un censo. El test ya contiene las comprobaciones correctas además del pin.
- **Riesgo de conservarlo:** falla por crecimiento; el 5053 se vuelve el contrato.
- **Riesgo de modificarlo:** actualizar la matriz sin conservar la coherencia permitiría que dos números dejen de hablar entre sí.
- **Evidencia:** matriz actual `b 1541/4`, `c 2781/25/26`, `r 1095/4`; total 5476; filas y columnas siguen cuadrando; +423 acciones.
- **Comprobación conceptual:** construir la matriz; exigir que cada fila sume su total, que las columnas sumen los totales absolutos y que el total de la matriz sea la suma de clasificaciones; la matriz exacta puede ir a un snapshot/reporte.
- **Aceptación:** nuevas acciones pasan si la matriz sigue coherente; una fila/columna que no suma falla; una acción fuera de `b/c/r` falla; no se exige 5053.

#### Caso 19 — `test_el_reparto_por_accion_suma_el_total_de_la_base`

- **Justificación:** la exclusión de `f/x` y la suma de `b/c/r` son el contrato; los totales 1448/2603/1002 son censos.
- **Riesgo de conservarlo:** falla por crecimiento; el total exacto se confunde con la exclusión.
- **Riesgo de modificarlo:** actualizar los totales sin la suma permitiría que `f/x` entren o que una acción desaparezca.
- **Evidencia:** 1545/2832/1099; suma 5476; coincide con la matriz actual; +97 `b`, +229 `c`, +97 `r`.
- **Comprobación conceptual:** contar `b/c/r` en las acciones clasificadas; exigir que sumen el total de la matriz; comprobar que no se incluyen `f/x`; reportar los totales exactos.
- **Aceptación:** nuevas acciones pasan si la suma se mantiene; una discrepancia entre acciones y matriz falla; no se exigen 1448/2603/1002.

#### Caso 20 — `test_los_ids_se_resuelven_con_el_boton`

- **Justificación:** `get_position(pid, btn_player)` es comportamiento de código; se prueba mejor con fixtures controlados. Los 204/46 son censos de la base.
- **Riesgo de conservarlo:** falla por crecimiento; el test mezcla una función estable con un censo.
- **Riesgo de modificarlo:** eliminar el contraste con la base podría ocultar un `allin` con ID irresoluble; actualizar 221/49 repite el problema.
- **Evidencia:** 204→221 resueltos; 46→49 confirmados; +17/+3; el mecanismo de `get_position` sigue funcionando.
- **Comprobación conceptual:** fixtures con `btn_player` y IDs conocidos, incluyendo todos los asientos y un ID inválido; exigir la posición esperada o `None`; en la base, exigir que todo ID de `allin` resuelva a una posición válida o esté declarado irresoluble; los recuentos van a un informe.
- **Aceptación:** los fixtures pasan; un ID irresoluble no declarado falla; el test no depende de 204/46.

#### Caso 21 — `test_por_defecto_cubre_toda_la_base`

- **Justificación:** el contrato es que el alcance por defecto sea toda la base, no que la base tenga 1253 manos.
- **Riesgo de conservarlo:** falla por crecimiento; el total se confunde con el alcance.
- **Riesgo de modificarlo:** un `>0` o un rango fijo permitiría un alcance recortado.
- **Evidencia:** 1253→1344; `resumen['manos'] == len(manos)`; el alcance sigue siendo “todas”.
- **Comprobación conceptual:** `resumen['manos'] == len(manos)` y `resumen['hasta'] == 'todas'`; opcionalmente, comprobar que todos los IDs cargados están en el resultado; no usar 1253.
- **Aceptación:** nuevas manos pasan; un alcance recortado falla; no se exige un total histórico.

#### Caso 22 — `test_el_rango_por_defecto_sigue_siendo_toda_la_base`

- **Justificación:** además del alcance total, la revisión manual dejó una garantía concreta: `H_1282` sigue dentro. El total 1253 es un censo.
- **Riesgo de conservarlo:** falla por crecimiento; se pierde la distinción entre “alcance total” y “total histórico”.
- **Riesgo de modificarlo:** quitar `H_1282` perdería la garantía de que el rango no se recortó justo después de la revisión; cambiar 1253 por 1344 repite el literal.
- **Evidencia:** 1344; `H_1282` presente; el rango sigue llegando a la última mano revisada.
- **Comprobación conceptual:** `resumen['manos'] == len(manos)`; `H_1282 in manos`; opcionalmente, `H_0001..H_1282` siguen presentes; no usar 1253.
- **Aceptación:** nuevas manos pasan; `H_1282` ausente o alcance recortado falla; no se exige un total.

---

## 5. Análisis de los tres tests obsoletos

### 5.1 Caso 7 — par SB/BB: qué relación se pretendía y cuál es válida

**Qué mide hoy.** `AO.seccion_2c` busca la primera `c` de SB y la primera `c` de BB, en cualquier punto del preflop, y resta sus importes. No comprueba que ambas calls afronten la misma apuesta viva, ni que sean la misma decisión. La posición en la lista no garantiza equivalencia.

**Qué pretendía proteger.** La normalización debía alinear las cajas de SB y BB: si el grabador registraba una caja distinta para cada ciega, el test lo vería como una diferencia distinta de cero. La idea era buena; la definición de “pareja” es la que no lo es.

**Evidencia actual.**

| Mano | Primera call SB | Primera call BB | Viva de cada call | Lectura |
|---|---:|---:|---|---|
| `H_0104` | 1.0 | 9.0 | SB en viva 1.0; BB en viva 9.0 | No son comparables; el −8 es un artefacto de niveles distintos. |
| `H_1310` | 1.0 | 3.0 | Ambas en viva 3.0 | La SB llama 1.0 cuando la viva es 3.0; luego vuelve a llamar 3.0. Es una call corta/duplicada, no una diferencia de caja entre ciegas equivalentes. |
| `H_1365` | 1.0 | 29.0 | SB en viva 1.0; BB en viva 29.0 | No son comparables; el −28 es un artefacto de niveles distintos. |

**Consecuencia.** El `-8` de `H_0104` no debe conservarse como “diferencia conocida”: es el mismo tipo de artefacto que el `-28` de `H_1365`, solo que estaba en la base histórica. El `-2` de `H_1310` sí es una señal real de una call corta, pero pertenece al detector de calls cortas, no a una comparación SB/BB por orden.

**Contrato que debe protegerse.** Para cada call de una ciega, el importe debe alcanzar la viva del momento (`amount == viva_antes` dentro de la tolerancia acordada). Si se quiere una comparación SB/BB, solo se emparejan calls de la misma calle que afrontan la misma `viva_antes`; entonces se exige que ambas alcancen esa viva, no que la primera de cada lista sea igual.

La viva debe definirse una sola vez y aplicarse igual en todos los diagnósticos. Hoy `AO` y `DG` la mueven con `b/r/c` y no con `p`; eso es una limitación declarada, no una equivalencia. Si se adopta una viva que incluya las postas obligatorias, hay que recalcular los casos 6, 15 y 16 y no mezclar ambos denominadores. La comparación SB/BB no puede usar una viva distinta de la del detector sin declararlo.

**Casos positivos y negativos necesarios.**

- **Positivo:** SB y BB llaman 1.0 cuando la viva es 1.0; ambas alcanzan la viva; no hay anomalía.
- **Positivo:** SB y BB llaman 3.0 cuando la viva es 3.0; ambas alcanzan la viva; no hay anomalía.
- **Negativo:** SB limpia 1.0 en viva 1.0 y BB llama 9.0 en viva 9.0; no se emparejan; si el test las empareja, produce un falso positivo.
- **Negativo:** SB llama 1.0 con viva 3.0; es una call corta; debe fallar el detector de calls cortas, no una comparación de ciegas.
- **Negativo:** SB y BB afrontan viva 3.0; SB llama 1.0 y BB llama 3.0; la SB no alcanza la viva; debe fallar.
- **Negativo:** SB y BB afrontan viva 3.0; ambas llaman 1.0; ambas no alcanzan; debe fallar.
- **Negativo:** una mano sin BB o sin posting de BB; debe fallar en el inventario, no en el par.

**Recomendación.** `REQUIERE_DECISION_MANUAL`: la comparación válida se puede especificar, pero `H_0104`, `H_1310` y `H_1365` necesitan revisión de campo y la decisión de si el detector de calls cortas sustituye por completo a este test. No se debe fijar 60 ni aceptar −8/−28 como conocidos.

### 5.2 Caso 10 — `stack: null` no es `0.0`

**Qué mide hoy.** `AO.seccion_3c` construye `stacks[pos] = float(p.get('stack') or 0.0)`. Para `None`, el `or 0.0` produce cero. Luego compara la aportación total con ese cero. I4 cuenta como violación cualquier aportación positiva de un jugador con stack nulo.

**Evidencia actual.**

- `H_1349`: `UTG.stack = None`; aportación 3.0; el helper la compara contra 0.0 y la cuenta como I4.
- `H_0740`: `SB.stack = 28.1`; aportación 28.2; es la única violación real conocida.
- Base actual: 13 entradas I4 = 1 violación real + 12 stacks desconocidos.
- Base histórica: 12 entradas = 1 violación real + 11 stacks desconocidos.
- I2=3 e I1=true no cambian.

**Dónde está el problema.** En los tres sitios, con distinta responsabilidad:

1. **En el helper:** `or 0.0` convierte “desconocido” en “cero”. Es el defecto principal.
2. **En la expectativa:** el test fija `I4=12` y no distingue las dos poblaciones; el 12 no significa “12 violaciones”.
3. **En el dato:** `H_1349` tiene un stack nulo; B1-E documenta un candidato derivado 45.9, no canónico. No se debe escribir 45.9 sin autorización.

**Contrato que debe protegerse.** Un stack `None`, ausente o no numérico es **desconocido**: no se compara y se cuenta en `I4_no_evaluable` con ID. Un stack numérico —incluido 0.0— es **conocido**: si la aportación lo supera, es violación. No se usa `float(None or 0.0)`.

**Casos positivos y negativos necesarios.**

- **Positivo:** stack conocido 100, aportación 90; no es violación.
- **Positivo:** stack conocido 0, aportación 0; no es violación.
- **Positivo:** stack desconocido (`None`), aportación 3.0; no es violación; se cuenta como desconocido.
- **Negativo:** stack conocido 100, aportación 101; violación.
- **Negativo:** stack conocido 0, aportación 1.0; violación.
- **Negativo:** `None` convertido a 0.0 y contado como violación; el test debe fallar contra esa implementación.

**Recomendación.** `REQUIERE_DECISION_MANUAL`: se debe aprobar el contrato de nulo y la disposición de `H_1349`; después, corregir el helper y separar `I4_violaciones` de `I4_no_evaluable`. No se debe fijar 13 ni mantener 12.

### 5.3 Caso 11 — el literal 1253 dentro de una consistencia

**Qué comprueba hoy.** Dos aserciones de identidad y dos literales:

- `s1['total'] == s3['exactas'] + s3['sobra'] + s3['falta']` (identidad útil);
- `sum(SB) == 1253` y `sum(BB) == 1253` (literales históricos).

**Evidencia.** Con 1344, la primera aserción pasa; las sumas SB/BB dan 1344; solo fallan los literales. El mensaje “el reparto de §3 no cubre las 1253 manos” es texto obsoleto, no la causa.

**Contrato que debe protegerse.** El reparto de §3 y los inventarios SB/BB deben cubrir el mismo total que §1, sea cual sea el total. No hay una identidad útil en el número 1253.

**Casos positivos y negativos necesarios.**

- **Positivo:** total N; `exactas + sobra + falta == N`; `sum(SB) == N`; `sum(BB) == N`; pasa.
- **Negativo:** `exactas + sobra + falta != total`; falla.
- **Negativo:** una mano con SB y BB cuenta en §1 pero no en §3; falla.
- **Negativo:** una mano sin SB/BB rompe la suma; falla.

**Recomendación.** `CONVERTIR_A_INVARIANTE`: sustituir los literales por `s1['total']`/`len(manos)` y conservar las identidades. No se necesita ningún número histórico.

---

## 6. Análisis de los cinco valores pendientes

### 6.1 Criterio

Para cada caso se separa:

- **magnitud** que mide;
- **población y denominador**;
- **manos nuevas** que intervienen;
- **contribuciones confirmadas** frente a **no adjudicadas**;
- **efecto de `H_1303` y `H_1365`** cuando corresponde;
- **si puede definirse un resultado exacto** con la evidencia disponible;
- **información que falta**.

No se inventa una adjudicación para `H_1303` ni `H_1365`.

### 6.2 Tabla de los cinco pendientes

| Caso | Magnitud | Población / denominador | Manos nuevas | Confirmado | No adjudicado | `H_1303` / `H_1365` | ¿Resultado exacto? |
|---|---|---|---|---|---|---|---|
| 6 | Calls `c` con `amount < viva` por calle | Base completa; el test cuenta el numerador, no un denominador; 16486 acciones y 2832 calls en la base actual | `H_1287`, `H_1303`, `H_1310` (2), `H_1365` | `H_1287` y `H_1310` (2) son secuencias anómalas ya declaradas | `H_1303` turn 3.9 vs 6.2; `H_1365` flop 83.9 vs 84.6 | +2 calls cortas; ambas compatibles con all-in corto por aritmética, pero `allin` declara a otro jugador | No para “defectos”; sí para el recuento bruto del detector (47) |
| 7 | Pares SB/BB: primera `c` de cada posición y su diferencia | Manos con primera `c` de SB y de BB; 60 parejas actuales | `H_1310`, `H_1365` (y `H_0104` histórico) | `H_1310` −2 es una call corta en la misma viva 3.0 | `H_0104` −8 y `H_1365` −28 son niveles distintos; no son comparables | `H_1365` añade −28 artefactual; `H_1303` no forma pareja | No; la métrica actual no define una población válida |
| 10 | I4: aportación > stack; I2; I1 | Todas las aportaciones por jugador; 13 entradas I4 actuales | `H_1349` (nulo); `H_0740` real histórico | `H_0740` 28.2 > 28.1 | 12 stacks desconocidos contados como cero; `H_1349` es el nuevo | No intervienen: sus aportaciones igualan su stack, no lo superan | No; depende del contrato de nulo y de `H_1349` |
| 15 | Total de calls y calls cortas | Base completa; 2832 calls, 47 cortas | Las mismas 5 del caso 6 | Las mismas 3 de `H_1287`/`H_1310` | Las mismas `H_1303`/`H_1365` | +2 calls cortas; misma ambigüedad | No para “defectos”; sí para los totales brutos 2832/47 |
| 16 | Distribución de calls cortas por posición y `falta=1.0` | Base completa; 47 cortas | Las mismas 5 | `uno=3` y `BB=10` no cambian; MP/CO/UTG siguen >0 | `H_1303`/`H_1365` son SB; su estado cambia el total de SB y el total general | +2 SB; si se excluyen, el total baja a 45 y SB a 5; no se fija | La conclusión cualitativa sí; los totales exactos no |

### 6.3 Caso 6 — calls por debajo de la viva

**Magnitud.** `AO` recorre cada calle, mantiene una viva que solo sube con `b/r/c` y cuenta una call cuando `amount < viva - 1e-6`. La viva no incorpora las postas `p`; es la viva del detector, no una viva de mesa completa. El test fija el total por calle y el caso `H_0058`. No calcula un denominador de calls; el “42 de 13826” del docstring es el total histórico de acciones, no una tasa que el test compruebe.

**Población.** Base completa de 1344 manos. En la base actual hay 16486 acciones y 2832 calls. El detector da 47 calls cortas: 10 preflop, 14 flop, 13 turn, 10 river.

**Manos nuevas.** Las 5 calls cortas nuevas:

- `H_1287` preflop: CO 1.0, viva 6.0, stack 20.0; no es all-in.
- `H_1303` turn: SB 3.9, viva 6.2, stack 10.3.
- `H_1310` preflop: SB 1.0, viva 3.0, stack 92.4; luego SB vuelve a llamar 3.0.
- `H_1310` flop: SB 4.3, viva 4.4, stack 92.4; luego SB vuelve a llamar 4.4.
- `H_1365` flop: SB 83.9, viva 84.6, stack 112.9.

**Confirmado.** `H_1287` y `H_1310` (dos calls) están en manos que B1-E ya declara con secuencia imposible o llamadas duplicadas. Son anomalías confirmadas de secuencia/lectura.

**No adjudicado.** `H_1303` y `H_1365` no están adjudicadas por B1-E. La aritmética es compatible con un all-in corto: en `H_1303` la SB acumula 2.0 + 4.4 + 3.9 = 10.3, exactamente su stack; en `H_1365` la SB acumula 29.0 + 83.9 = 112.9, exactamente su stack. Pero el campo `allin` declara a otro jugador (`p5`/CO en `H_1303`; `p2`/UTG en `H_1365`), así que no se puede concluir que sean all-in cortos legítimos. Tampoco se puede concluir que sean corrupción.

**Efecto de `H_1303` y `H_1365`.** Añaden +2 al recuento bruto. Si se adjudicaran como all-in corto legítimo, el contrato podría excluirlas y el número de defectos nuevos sería 3, no 5; el total bruto seguiría siendo 47. Si se adjudicaran como defecto, serían 5. No hay una respuesta única sin contrato.

**¿Resultado exacto?** El recuento bruto 47 es exacto y reproducible. El “número de defectos” no lo es. Falta decidir si una call corta que iguala el stack acumulado es un all-in corto legítimo, si el campo `allin` mandato o no, y si las calls duplicadas de `H_1310` se cuentan una o dos veces.

### 6.4 Caso 7 — pares SB/BB

**Magnitud.** Para cada mano con al menos una `c` de SB y una `c` de BB, se toma la primera de cada posición, se resta y se agrupa por diferencia. No se comprueba la viva. Actual: 60 parejas; 57 con diferencia 0.0, una −8.0 (`H_0104`), una −2.0 (`H_1310`) y una −28.0 (`H_1365`).

**Población.** Manos con ambas primeras calls. Las 8 parejas nuevas: 6 con diferencia 0.0, `H_1310` −2.0 y `H_1365` −28.0. `H_0104` es histórica.

**Confirmado.** `H_1310`: la primera call de SB (1.0) y la de BB (3.0) afrontan la misma viva 3.0; la SB no alcanza la viva y luego vuelve a llamar 3.0. Es una call corta/duplicada real, ya declarada por B1-E.

**No adjudicado / artefacto.** `H_0104` y `H_1365` comparan calls en niveles distintos: SB 1.0 en viva 1.0 frente a BB 9.0/29.0 en viva 9.0/29.0. No son una diferencia de cajas entre ciegas equivalentes. El −8 histórico tampoco es una anomalía de caja al mismo nivel.

**Efecto de `H_1303`/`H_1365`.** `H_1303` no forma pareja (la SB sube, no llama en el primer nivel). `H_1365` añade la pareja −28, que es artefactual. `H_1303` no contribuye al caso 7; `H_1365` sí, pero no como defecto de caja.

**¿Resultado exacto?** No. La población “primera call de cada posición” no es una relación semántica válida. Se puede definir un resultado exacto con el contrato “misma viva”: entonces `H_0104` y `H_1365` no se emparejan, y `H_1310` se detecta por call corta. Falta aprobar ese contrato y revisar `H_0104`/`H_1310`/`H_1365`.

### 6.5 Caso 10 — I4, I2, I1 y el stack nulo

**Magnitud.** I4 cuenta jugadores cuya aportación total supera su stack inicial; I2 cuenta manos donde el bote declarado no supera lo aportado; I1 comprueba que el bote no es negativo.

**Población.** Base completa; todas las aportaciones por jugador. Actual: 13 entradas I4. De ellas, **1 es una violación real** (`H_0740`, 28.2 > 28.1) y **12 son stacks desconocidos** convertidos a 0.0 (11 históricos + `H_1349`). Histórico: 12 = 1 + 11. I2=3; I1=true.

**Manos nuevas.** `H_1349` añade el stack nulo de UTG y una aportación de 3.0. `H_1303` y `H_1365` no intervienen en I4: sus aportaciones acumuladas igualan su stack, no lo superan.

**Confirmado.** `H_0740` es una violación real de stack conocido. `H_1349` tiene `stack: None` y B1-E documenta un candidato derivado 45.9, no canónico.

**No adjudicado.** No está decidido si `H_1349` debe quedar como desconocido, corregirse a 45.9, o excluirse. Tampoco está decidido si los 12 desconocidos deben reportarse aparte o si alguno tiene un stack cero legítimo.

**Efecto de `H_1303`/`H_1365`.** Ninguno en I4; sus compromisos no superan su stack. Esto es importante para no atribuirles un delta que no producen.

**¿Resultado exacto?** No con un solo número. El resultado exacto con el contrato propuesto sería: `I4_violaciones = {H_0740}` (1), `I4_no_evaluable = 12 IDs`, `I2 = 3`, `I1 = true`. Si `H_1349` se corrige a 45.9, el desconocido baja a 11 y no hay violación nueva. Falta aprobar el contrato y la disposición de `H_1349`.

### 6.6 Caso 15 — total de calls y calls cortas

**Magnitud.** `DG` cuenta todas las acciones `c` y, dentro de ellas, las que no alcanzan la viva. Actual: 2832 calls, 47 cortas. Histórico: 2603 calls, 42 cortas.

**Población.** Base completa; calls de todas las calles. El total 2832 es la cuenta de acciones `c`; no es un “número de defectos”. El reparto por calle de las cortas es 10/14/13/10.

**Manos nuevas.** Las mismas 5 del caso 6. `H_1287` y `H_1310` (2) confirmadas; `H_1303`/`H_1365` no adjudicadas.

**Confirmado / no adjudicado.** Igual que el caso 6. Las calls de `H_1287` y `H_1310` son anomalías de secuencia; las de `H_1303`/`H_1365` son candidatas a all-in corto, con la contradicción del campo `allin`.

**Efecto de `H_1303`/`H_1365`.** +2 calls cortas; el total de calls no cambia por su adjudicación (las calls existen en el dato), solo el subconjunto de “cortas que son defecto”.

**¿Resultado exacto?** El total bruto 2832 y las 47 cortas son exactos. El “número de defectos” no. Falta el mismo contrato que el caso 6 y decidir si las calls de `H_1310` se cuentan una o dos veces.

### 6.7 Caso 16 — distribución de calls cortas

**Magnitud.** Total de calls cortas, cuántas tienen `falta ≈ 1.0`, y reparto por posición. Actual: 47; `uno=3`; `BB=10`; MP/CO/UTG > 0. Histórico: 42; `uno=3`; `BB=10`.

**Población.** Las calls cortas del detector. Las 5 nuevas: `H_1287` CO, `H_1303` SB, `H_1310` SB (2), `H_1365` SB. Añaden +1 CO y +4 SB; no cambian BB ni `falta=1.0`.

**Confirmado.** La conclusión cualitativa “no es solo del BB” sigue siendo verdadera: hay calls en MP, CO, UTG, BTN, SB y BB. `BB=10` y `uno=3` no cambian con las nuevas.

**No adjudicado.** El total exacto de “calls cortas que son defecto” depende de `H_1303`/`H_1365`. Si se excluyen como all-in corto legítimo, el total baja a 45 y SB a 5; si se quedan, 47 y SB 7. `H_1310` aporta dos calls; si se deduplican, baja otro tanto.

**Efecto de `H_1303`/`H_1365`.** Son dos calls de SB; afectan al total y al conteo de SB, no a BB ni a `falta=1.0`.

**¿Resultado exacto?** La propiedad cualitativa sí se puede fijar: `BB < len(calls)` y MP/CO/UTG > 0. Los totales exactos no; dependen del ledger y de la adjudicación.

---

## 7. Política para snapshots y base dinámica

### 7.1 Principio

Una prueba debe declarar, de forma separable:

1. **identidad de la fuente** — qué fichero, commit, SHA-256 y número de líneas;
2. **población** — todas las manos, un snapshot histórico, una cohorte o un ledger de anomalías;
3. **regla de selección** — cómo se pasa de la fuente a la población;
4. **versión del código** — commit o versión de la función que produce el resultado;
5. **resultado esperado** — valor, tolerancia y motivo, aprobado por una persona.

No se debe inferir la población a partir del orden del fichero. `load_hands(reliable_only=True)` usa las primeras 900 líneas como ventana de calibración; es una regla heredada de calibración, **no** una procedencia histórica. Para snapshots y cohortes se usan `hand_id`, commit o una regla de procedencia explícita, no límites de líneas.

### 7.2 Tipos de descriptor

| Descriptor | Contenido mínimo | Uso |
|---|---|---|
| `source` | `path`, `commit`, `sha256`, `lineas` | Identidad de la fuente. |
| `snapshot` | `source` + `snapshot_id` + `expected_lineas` + `expected_metrics` | Base histórica inmutable. |
| `cohort` | `source` + `nombre` + `regla_de_seleccion` + `expected_ids` o `expected_count` + `motivo` | Población con procedencia conocida. |
| `current_invariant` | `source` + propiedad + tolerancia | Base dinámica actual. |
| `anomaly_ledger` | `source` + `lista` de `(hand_id, calle, índice, pos, amount, viva, motivo, estado)` | Diagnóstico con anomalías conocidas. |
| `fixture` | mano(s) sintética(s) + resultado esperado | Contrato de código. |

### 7.3 Reglas de mantenimiento

1. **Snapshot histórico:** se identifica por commit + SHA-256 + número de líneas. El test comprueba el hash antes de leer. No se actualiza cuando entran manos nuevas. Si el snapshot no está disponible, el test falla; no cae silenciosamente a la base actual.
2. **Base actual:** se lee a través del manifiesto `HANDS_DB_*`. Si el SHA del disco no coincide con el declarado, el test falla antes de medir. Un cambio de fuente exige actualizar el manifiesto y revisar los censos, no editar el test a ciegas.
3. **Crecimiento legítimo:** las manos nuevas deben poder entrar sin tocar los invariantes. Si un invariante falla, es una señal; si solo cambia un censo, se actualiza el snapshot o el ledger con revisión explícita.
4. **Correcciones manuales:** el usuario puede corregir una mano histórica. Después debe actualizar el hash/manifiesto y, si cambia una expectativa, dejar constancia del `hand_id`, motivo y fecha. Ningún script corrige o reescribe la base; no se automatiza la revisión.
5. **Anomalías conocidas:** un diagnóstico no se “arregla” subiendo el número. Se declara cada anomalía con ID y motivo. La prueba exige que el detector produzca exactamente el ledger; una anomalía nueva falla; una anomalía que desaparece exige una baja aprobada.
6. **Cohortes:** se definen por una regla de procedencia (por ejemplo, ausencia de `allin` para `record_hand`) y se contrasta su conjunto de IDs. No se usa “las primeras N líneas” ni “las manos hasta `H_1282`” como sustituto de procedencia, salvo que ese corte sea el contrato histórico explícito.
7. **Artefactos derivados:** no son fuente de estos tests. Si en el futuro se usan, deben llevar `contract_version`, `data_snapshot_hash` y `code_commit`; no se mezclan con la base canónica. Eso pertenece a PR-04, no a esta política.
8. **Código:** los contratos de funciones se prueban con fixtures; la versión de código se registra en el manifiesto o en el nombre del snapshot. Un cambio de regla debe romper la prueba de contrato, no un censo global.

### 7.4 ¿Hash, manifiesto o ambos?

**Ambos, con funciones distintas.**

- **Hash solo** verifica bytes, pero no dice qué población se seleccionó, qué regla se aplicó ni qué resultado se espera. Un hash correcto con una selección equivocada sigue siendo un test mal definido.
- **Manifiesto solo** puede quedar desincronizado con el fichero; una edición manual o un cambio de línea no se detecta si el manifiesto se actualiza por costumbre.
- **Hash + manifiesto** permite comprobar que se lee exactamente el fichero declarado y que la población, la regla, la versión de código y la expectativa son las aprobadas.

Para snapshots históricos, el commit es necesario para recuperar el blob; el SHA-256 y el número de líneas son la verificación de contenido. Para la base actual, el SHA-256 y el manifiesto `HANDS_DB_*` ya existen; la política añade población y expectativa, no un segundo hash.

### 7.5 Distinciones que no se deben mezclar

| Concepto | Pregunta | Ejemplo |
|---|---|---|
| Identidad de la fuente | ¿Qué bytes se están leyendo? | `3f0e7e5e...`, 1344 líneas, commit `8594ed5`. |
| Población | ¿Qué subconjunto? | 1253 históricas; 71 sin `allin`; todas las actuales. |
| Regla de selección | ¿Cómo se obtiene? | `hand_id` explícito; ausencia de `allin`; commit `51a6fb9`. |
| Versión de código | ¿Con qué regla se mide? | `learn._es_ciega_bb` en el commit actual; `AO.seccion_3c` versión X. |
| Resultado esperado | ¿Qué se exige? | 373/3/877 en el snapshot; `con_ciega == total`; ledger de 47 calls. |

### 7.6 Lo que no se debe hacer

- No reducir la base a 1253 para que pasen los tests.
- No actualizar los 22 números en masa.
- No cambiar `1253` por `1344` dentro de un test sin declarar la población.
- No usar `H_1014` o `H_1282` como límite de línea si lo que se quiere es una cohorte.
- No convertir `stack: null` en `0.0`.
- No aceptar cualquier call corta como “dato nuevo legítimo” sin ledger.
- No borrar un test de diagnóstico para que la suite pase.
- No convertir un snapshot histórico en la base actual por comodidad.

---

## 8. Arquitectura de pruebas recomendada

### 8.1 Capas

1. **Contratos unitarios con fixtures (D).** Manos sintéticas pequeñas, sin base. Prueban `_es_ciega_bb`, `p`, `get_position`, el clasificador y las funciones de contrato. Siempre en la suite habitual.
2. **Integración con snapshot histórico (A).** Un snapshot identificado (por ejemplo, 1253) con expectativas históricas. No cambia con las manos nuevas. En la suite habitual si es rápido; si no, en el job de snapshots.
3. **Invariantes sobre la base actual (B).** Propiedades que deben cumplirse con cualquier número de manos. Leen el manifiesto y fallan si el hash no coincide. Siempre en la suite habitual.
4. **Cohortes identificadas (C).** Poblaciones con procedencia conocida: bloque `record_hand` de 71, manos importadas de un commit, conjunto histórico de 1253. Se comparan por `hand_id`, no por línea.
5. **Auditorías y diagnósticos (E).** Ledgers de anomalías y informes de recuentos. Se ejecutan en la suite habitual con comparación de ledger; el informe completo se ejecuta como auditoría explícita y se revisa antes de adoptar una base.

### 8.2 Qué va a la suite habitual

- Contratos con fixtures.
- Invariantes actuales (BB, SB, `p`, posiciones, alcance, coherencia de matriz).
- Snapshot histórico (si su coste es aceptable; los 22 actuales tardan segundos).
- Cohortes fijas (71 sin `allin`, bloque hand).
- Ledgers de anomalías: igualdad exacta con lo aprobado.
- Comprobación de hash/manifiesto antes de leer.

### 8.3 Qué va a auditoría explícita

- Informe completo de calls cortas por calle, posición y `falta`.
- Informe de reconciliación de botes y clasificación por acción/resultado.
- Diferencias entre la base actual y el snapshot anterior: IDs nuevos, IDs eliminados, cambios de procedencia, cambios de clasificación.
- Censos que se espera que cambien con el crecimiento.
- Aprobación de un nuevo snapshot o de un nuevo ledger.

La auditoría explícita **no es un cajón para que la suite pase**. Debe seguir siendo obligatoria antes de adoptar datos y debe fallar si aparece una anomalía nueva o si un ID conocido cambia de estado sin declaración.

### 8.4 Organización sugerida

No se crean ficheros en esta tarea; los nombres son ilustrativos:

```text
motor/test_contract_accion_p.py          # fixtures de p/orden
motor/test_contract_ids.py               # get_position con fixtures
motor/test_snapshot_1253.py              # snapshot histórico A
motor/test_invariants_base_actual.py     # B
motor/test_cohort_grabadores.py          # C
motor/test_audit_calls_cortas.py         # E + ledger
motor/test_audit_clasificacion.py        # E + ledger
```

La suite puede mantener los nombres actuales y marcar los grupos con `pytest.mark.snapshot`, `pytest.mark.audit`, etc. Lo importante es la separación semántica, no el nombre.

### 8.5 Reglas de diseño de cada prueba

- **Un test, un contrato.** No mezclar un invariante con un censo.
- **Una expectativa, una fuente.** Si un test compara dos cálculos, ambos deben salir del mismo source y de la misma población.
- **Nada de tautologías.** Un test que calcula la expectativa con la misma función que mide no comprueba nada; la expectativa debe estar aprobada o derivarse de una propiedad independiente.
- **Nada de `> 0` como sustituto de cobertura.** Para CM-004, cobertura completa o fallo.
- **Nada de tolerancias silenciosas.** Las tolerancias (0.005, 0.05, 0.15) deben estar declaradas y justificadas.
- **Nada de actualizaciones automáticas.** Un cambio de censo exige una revisión humana y un diff visible.

### 8.6 Criterios para elegir entre tipos

- Si la expectativa cambia con el número de manos y no hay una propiedad independiente: **snapshot**.
- Si la propiedad debe cumplirse con cualquier número de manos: **invariante**.
- Si la población tiene procedencia conocida y membresía fija: **cohorte**.
- Si lo que se prueba es una función o decisión del motor: **fixture**.
- Si lo que se prueba es la capacidad de detectar un defecto: **ledger de anomalías**.

---

## 9. Plan de implementación incremental

La implementación queda fuera de esta tarea. El plan siguiente solo describe el orden y las puertas de aprobación.

### Fase 0 — Aprobación de la política

- Ratificar D8 (gobierno del ledger) y el diseño de política reflejado en §10.1.1.
- D1–D7 y D9 ya tienen resolución documental; no repetir su adjudicación.
- No autorizar PR-03 hasta satisfacer G1–G5 y dar autorización explícita (D11).
- No tocar tests, datos ni código.
- PR-03 sigue bloqueado.

### Fase 1 — Descriptores y manifiesto de pruebas

- Definir el esquema pequeño de `source`, `snapshot`, `cohort`, `current_invariant`, `anomaly_ledger` y `fixture`.
- Añadir pruebas de lectura que validen el esquema y el hash; no medir aún los 22.
- Verificar que el manifiesto actual `HANDS_DB_*` coincide con el disco.
- Sin cambios en `data/`, sin writers.

**Salida:** un descriptor reproducible y una prueba que falla si el hash no coincide.

### Fase 2 — Contratos y fixtures

- Migrar el caso 20 a fixtures de `get_position`.
- Añadir fixtures para `_es_ciega_bb` y `p` si no existen ya.
- Mantener los tests de base actual que sean invariantes.
- No actualizar censos.

**Salida:** comportamiento de código desacoplado de recuentos globales.

### Fase 3 — Invariantes actuales

- Convertir 2, 3, 4, 5, 11, 12, 18, 19, 21 y 22.
- Separar en cada uno la propiedad del censo.
- Añadir los conjuntos explícitos de ausencias de SB y el ledger de anomalías de clasificación.
- Ejecutar contra 1344; no exigir 1253.

**Salida:** suite actual con invariantes que pasan en 1344 y fallan ante una regresión real.

### Fase 4 — Snapshots históricos y cohortes

- Formalizar el blob inmutable de 1253 para el caso 8 y el censo histórico de `p`; mantener la base actual separada con sus invariantes.
- Formalizar las cohortes 13 y 14: 71 sin `allin`, bloque hand.
- Aplicar la resolución D9: snapshot histórico 1253 + invariante actual; no fijar 2702 ni crear `canonical-1344` por defecto.
- No actualizar 394/947 ni 5417/33/26 como si fueran contratos.

**Salida:** snapshots inmutables y cohortes explícitas; la base actual no se confunde con la histórica.

### Fase 5 — Ledgers de diagnóstico conforme a las adjudicaciones

- Crear el ledger de calls cortas para 6, 15 y 16.
- Incorporar las adjudicaciones D2/D3/D5: `H_1303` y `H_1365` all-in por menos; `H_1310` frames; retirar el par SB/BB por orden.
- Aplicar D4: `stack: null` desconocido; `H_1349` en `I4_no_evaluable`; no escribir 45.9.
- Corregir el helper `AO.seccion_3c` solo si se autoriza; no convertir `None` en `0.0`.
- No tocar datos históricos sin autorización.

**Salida:** ledgers exactos construidos con las decisiones ya documentadas; el ledger es la expectativa, no un total global. Su gobierno D8 requiere ratificación del propietario.

### Fase 6 — Cierre de la política

- Eliminar los literales obsoletos.
- Ejecutar la suite completa y la auditoría explícita.
- Comprobar que el número de fallos es 0 por las razones correctas: no porque se hayan eliminado pruebas, sino porque cada contrato está separado.
- Revisar que los snapshots históricos y la base actual siguen siendo distinguibles.
- Solo después, autorizar PR-03.

**Rollback:** cada fase es reversible; los snapshots y ledgers son datos de prueba, no datos canónicos. Si una conversión debilita la detección, se revierte y se vuelve al contrato anterior.

---

## 10. Riesgos y decisiones que requieren autorización

### 10.1 Decisiones

| ID | Decisión | Por qué requiere autorización | Estado previo (antes de la revisión) |
|---|---|---|---|
| D1 | ¿La base canónica para los tests es 1344, con 1253 como snapshot histórico? | Afecta a qué se considera “actual” y a la cobertura. | Adoptada documentalmente; confirmar para tests. |
| D2 | ¿Una call corta que iguala el stack acumulado es all-in corto legítimo? | Cambia el contrato de 6, 15 y 16. | Pendiente; `H_1303`/`H_1365` no adjudicadas. |
| D3 | ¿Cómo se tratan las calls duplicadas de `H_1310`? | Una o dos anomalías; afecta a 6, 15 y 16. | Pendiente. |
| D4 | ¿`stack: null` se excluye, se cuenta aparte o se corrige con 45.9? | Cambia I4 y la validez de `H_1349`. | Pendiente. |
| D5 | ¿El par SB/BB se define por misma viva o por primera call de cada posición? | El caso 7 es inválido con la definición actual. | Pendiente; propuesta: misma viva. |
| D6 | ¿Se conserva el snapshot 1253 en la suite habitual? | Afecta a cobertura histórica y tiempo de suite. | Pendiente. |
| D7 | ¿La ausencia de `allin` es huella suficiente de `record_hand`? | Afecta a la cohorte 71 y a la separación de grabadores. | Pendiente de confirmar. |
| D8 | ¿Quién aprueba un ledger de anomalías y cómo se añade/quita una entrada? | Sin gobierno, el ledger se convierte en una lista de excusas. | Pendiente. |
| D9 | ¿Se actualiza el censo 2702 de `p` como snapshot 1344 o se mantiene 1253? | Afecta al caso 1 y a la distinción histórico/actual. | Pendiente. |
| D10 | ¿Se usarán artefactos derivados en alguna de estas pruebas? | Hoy no; si se usan, necesitan versión y hash. | Fuera de alcance; PR-04. |
| D11 | ¿Cuándo se autoriza PR-03? | Depende de que la suite quede verde por contratos, no por relajación. | Bloqueado. |

#### 10.1.1 Estado tras la revisión (2026-11-14)

La tabla anterior conserva el estado en que se escribió la política. La revisión de las manos ambiguas y del snapshot se registra en `DOCS/RESOLUCION_DECISIONES_D1_D9_D11_2026-11-14.md`; este es el estado que la sustituye para D1–D9 y D11:

| ID | Resolución | Estado |
|---|---|---|
| D1 | 1344 es la base dinámica; 1253 es snapshot histórico del blob `51a6fb9`. | Resuelta |
| D2 | All-in por menos = stack conocido + acumulado == stack + sin acción posterior. `H_1303` y `H_1365` son all-in por menos; no son calls cortas defectuosas. | Resuelta |
| D3 | Una call por jugador/calle con el valor final; `H_1310` son dos frames, no dos defectos. | Resuelta |
| D4 | `stack: null` es desconocido; `H_1349` va a `I4_no_evaluable`; no se escribe 45.9. | Resuelta |
| D5 | Comparación por misma viva; el par por orden se retira como contrato. `H_0104`/`H_1365` no se emparejan; `H_1310` es frame. | Resuelta |
| D6 | Sí: snapshot 1253 como fixture inmutable en la suite habitual. | Resuelta |
| D7 | La ausencia de `allin` solo vale para la cohorte histórica cerrada de 71 IDs; no es regla general. | Resuelta con matiz |
| D8 | Ledger propuesto: aprobación del propietario, diff y revisión humana; sin auto-update. | Pendiente de ratificación |
| D9 | 2522 al snapshot 1253; invariante actual de `p`; 2702 se reporta, no se fija. | Resuelta |
| D11 | PR-03 bloqueado; G1–G5 no satisfechos; pendiente de autorización explícita. | Bloqueado |

#### 10.1.2 Puertas de PR-03 — estado documental

La resolución define criterios verificables, pero **ninguna puerta se satisface por defecto**. Todas parten de `NO SATISFECHO`; la comprobación del blob en esta revisión no sustituye las pruebas automatizadas ni una aprobación.

| Puerta | Evidencia necesaria | Estado |
|---|---|---|
| G1 | Matriz de 22 casos y resolución A–E aprobadas explícitamente por el propietario y registradas en el cierre. | **NO SATISFECHO** — no consta aprobación de cierre. |
| G2 | Descriptores/fixtures/ledgers implementados y ejecución registrada que valide hashes, líneas y membresías exactas. | **NO SATISFECHO** — no implementados ni validados. |
| G3 | Salida de la suite completa en verde y revisión del diff que confirme que no se eliminaron ni debilitaron checks. | **NO SATISFECHO** — no implementado ni ejecutado. |
| G4 | Pruebas negativas/mutaciones que fallen ante cada defecto especificado, con resultados registrados y datos canónicos intactos. | **NO SATISFECHO** — pruebas no implementadas. |
| G5 | Verificación automatizada de identidad snapshot/base y ledger exacto, más firma explícita del propietario después de G1–G4. | **NO SATISFECHO** — no existe evidencia implementada ni firma de cierre. |

La autorización explícita de D11 es una condición adicional, no una consecuencia automática de que se documenten estos criterios. PR-03 sigue bloqueado.

Evidencia nueva que cambia la lectura anterior:

- Las 42 calls históricas son 39 all-in por menos + 3 calls cortas con fichas detrás. No son 42 defectos.
- Las 47 actuales son 41 all-in + 2 frames + 4 calls cortas reales. Las 5 nuevas son 2 all-in (`H_1303`, `H_1365`), 2 frames (`H_1310`) y 1 corta real (`H_1287`).
- `H_1303`: `p5` es la SB (`players[5]`), no el CO; está marcada y agota 10.3.
- `H_1365`: `p2` es el BB, también all-in; la SB está omitida y B1-E §4.7 la documenta. La aritmética manda.
- El snapshot 1253 es el blob `51a6fb9`, no las primeras 1253 líneas actuales: los IDs coinciden, pero 127 manos tienen contenido distinto.
- La verificación de Git confirma que `51a6fb9` resuelve al commit completo `51a6fb9f05394fcfecd3b3ee4fb9479ed4e9600f`, contiene `data/hands_db.jsonl` (objeto `f52c09e294153e748f05d216bafcf6a779be4465`) y su blob extraído tiene 1253 líneas, 1,851,156 bytes y el SHA-256 declarado.
- La corrección del all-in acumulado cambia los totales del clasificador; no se fijan 5001/29/23 ni 5417/33/26.

### 10.2 Riesgos de las alternativas

| Alternativa | Riesgo | Valor |
|---|---|---|
| No hacer nada | Suite roja permanente; los 22 se mezclan con fallos nuevos; se normaliza el rojo. | Ninguno a largo plazo. |
| Actualizar los 22 números en masa | Convierte detectores en fotos; oculta calls cortas, nulos y pares inválidos; el siguiente crecimiento vuelve a romper. | Alto riesgo. |
| Filtrar todos los tests a 1253 | Verde sin cubrir la base actual; las 91 manos nuevas quedan sin guard. | Solo como snapshot histórico separado. |
| Solo invariantes, sin snapshots | Se pierde la reproducibilidad histórica y la detección de cambios de censo. | Insuficiente. |
| Solo snapshots, sin invariantes | La base actual no se cubre; cada growth exige actualizar números. | Insuficiente. |
| Ledger de anomalías sin gobierno | Se convierte en una lista de excepciones que acepta cualquier cosa. | Peligroso si no hay aprobación. |
| Política de snapshots + invariantes + cohortes + fixtures + ledger | Más piezas, pero cada una tiene un contrato claro y verificable. | Recomendado. |

### 10.3 Riesgos específicos

- **Falso verde:** un invariante demasiado débil (`> 0`, `set` vacío, `sum` tautológica) puede pasar con el detector apagado. Mitigación: cobertura completa, ledgers exactos y casos negativos.
- **Falso rojo:** un snapshot histórico que se actualiza con cada growth vuelve a fallar. Mitigación: separar snapshot de actual.
- **Deriva de cohorte:** usar `allin` como huella sin verificar que el grabador no cambió. Mitigación: IDs explícitos y revisión de procedencia.
- **Nulo como cero:** el bug de I4 puede reaparecer en cualquier helper. Mitigación: prueba de contrato específica y prohibición de `or 0.0` para stacks.
- **Confusión de niveles:** el par SB/BB puede volver a comparar decisiones distintas. Mitigación: comparar con la viva, no con la posición en la lista.
- **Pérdida de la revisión manual:** recortar el alcance a `H_1282` o a 1253. Mitigación: invariante de alcance total + `H_1282` presente.
- **Automatización indebida:** un writer que “arregle” datos para que pase un test. Mitigación: prohibición explícita; el canal manual sigue siendo el único.

---

## 11. Veredicto

La política es viable y necesaria, pero **no se implementa en esta tarea**.

- Los 22 fallos son pines históricos, no una regresión de código.
- No se debe sustituir `1253` por `1344` en masa.
- Tras la revisión, la distribución primaria es: 15 invariantes, 2 cohortes, 1 fixture, 2 ledgers de calls cortas, 1 reemplazo de métrica por invariante y 1 snapshot histórico; no queda ningún caso en `REQUIERE_DECISION_MANUAL`.
- Los tres tests obsoletos tienen contrato propuesto: caso 7, invariante por call con la comparación al mismo nivel solo como diagnóstico; caso 10, separar stack conocido/desconocido/cero; caso 11, identidades sin literal.
- Los cinco valores pendientes quedan adjudicados en `DOCS/RESOLUCION_DECISIONES_D1_D9_D11_2026-11-14.md`: `H_1303` y `H_1365` son all-in por menos; `H_1310` son frames; `H_1349` es stack desconocido; `H_0104` es un all-in en otro nivel. El campo `allin` no es exhaustivo (`H_1365` omite a la SB), pero no contradice la aritmética.
- La suite no debe debilitarse: los diagnósticos siguen detectando mediante ledgers; los snapshots siguen siendo inmutables; los invariantes siguen siendo falsables.
- PR-03 sigue bloqueado hasta que se apruebe esta política y se implemente en una tarea separada.

**Recomendación inmediata:** ratificar D8/D11 y empezar por las fases 1 y 2 (descriptores y fixtures) sin tocar los datos. La primera actualización de un censo debe ser una decisión revisada, no una consecuencia automática del crecimiento.

---

## Anexo A. Estado de archivos y no modificación

- **Documentación de esta revisión:** `DOCS/POLITICA_MANTENIMIENTO_TESTS_BASE_DINAMICA_2026-11-14.md` y `DOCS/RESOLUCION_DECISIONES_D1_D9_D11_2026-11-14.md`.
- No se modificó `data/hands_db.jsonl`.
- No se modificaron tests.
- No se modificó código de producción.
- No se modificaron matrices, calibración, decisiones, observaciones, perfiles ni derivados.
- No se regeneraron artefactos.
- No se ejecutaron writers ni saneadores.
- No se redujo la base.
- No se actualizaron números en masa.
- No se creó commit de implementación de la política; la integración documental se realiza por instrucción explícita del propietario.
- No se inició PR-03.

Los cambios preexistentes de PR-02B siguen como estaban. El hash de `data/hands_db.jsonl` y de los artefactos de control es el de §2.2. El hash de este documento se reporta en la entrega de la tarea; cualquier edición posterior cambia ese hash.
