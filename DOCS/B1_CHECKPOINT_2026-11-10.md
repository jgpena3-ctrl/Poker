# B1 — Punto de control: procedencia, escritores, snapshot y derivados

**Fecha:** 2026-11-10
**Base actual:** `data/hands_db.jsonl` de 1344 líneas, SHA-256
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`
(commit que introdujo el blob: `8594ed5`; HEAD de trabajo: `1544249`).
**Autorización:** B1 autorizado para procedencia, auditoría, snapshot,
regeneración en copias y corrección de métricas F7.2.

## 1. Veredicto

**La reproducción exacta de la base no está demostrada.** El intento con los
11 scripts versionados de `8594ed5` no llega al estado actual y se detiene en
una precondición. Además, el commit `8594ed5` contiene cambios de acciones que
ninguno de los 11 scripts produce, y los commits `44acddb` y `c1c1370` no
incluyen scripts de corrección de base.

Por tanto:

- **No se actualiza el manifiesto** de `motor/learn.py`.
- **No se reanclan pines** de base, derivados ni métricas.
- **No se adoptan derivados regenerados**: solo se compararon en copias.
- **No se modifica** la base canónica, la estrategia, las tablas preflop, los
  rangos manuales ni `MULTIWAY_SOPORTADO` (sigue en `False`).
- Se crea un snapshot **provisional** de la ventana y un verificador de solo
  lectura, precisamente para que la decisión posterior no dependa de memoria.

## 2. Reproducción: qué se intentó y por qué no cierra

### 2.1 Estados exactos

| Commit | Líneas | SHA-256 | Papel |
|---|---:|---|---|
| `51a6fb9` | 1253 | `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09` | Base declarada por el manifiesto |
| `44acddb` | 1298 | `4002ca236a850d159d43c6c9b756c3fbafd1d33d208ff1d7605ba89420b58af8` | Primera expansión; sin scripts de base |
| `c1c1370` | 1345 | `797c85e1408962eb2d6c01aa5bbc3de49502618a2c28305b359a317b9c52f332` | Punto de partida del intento |
| `8594ed5` / HEAD | 1344 | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` | Base actual |

### 2.2 Intento de orden histórico

En un worktree temporal detached en `8594ed5`, con el blob de `c1c1370`:
`C:\Users\Jorgito\AppData\Local\Temp\opencode\b1_repro_worktree`.

Orden lógico aplicado, con `--apply` y backup:

1. `corregir_sesion_20261104.py`
2. `corregir_folds_showdown.py`
3. `corregir_mano_H_1333.py`
4. `corregir_resultados_20261029.py`
5. `corregir_resultados_20261104.py`

El paso 5 **falla** con:

```text
H_1336: no hay dos jugadores vivos (['BB'])
```

También se probó cada script por separado sobre `c1c1370`:

- `corregir_mano_H_1333.py` falla solo: la verificación en memoria dice
  `FALLO: la mano sigue ambigua`; necesita una limpieza previa.
- `corregir_resultados_20261104.py` falla solo en `H_1336`, y después
  encontraría el mismo problema en otras manos que el estado base todavía
  muestra como folds.
- Los otros nueve scripts terminan con código 0 en esa copia.

### 2.3 La causa no es el orden: faltan cambios que no están en los scripts

Comparación `c1c1370` → `8594ed5` (evidencia completa en
[`B1_REPRO_DIFF.json`](B1_REPRO_DIFF.json)):

| Medida | Valor |
|---|---:|
| Manos modificadas | 144 |
| Manos modificadas dentro de las primeras 900 líneas | 50 |
| Manos modificadas dentro de la ventana fiable (900 menos 23) | 49 |
| Manos modificadas en una exclusión CM-004 | 1 (`H_0147`) |
| Manos con cambio semántico de acciones fuera del frame de metadatos | 30 |
| De esas 30, explicadas por los 11 scripts | 7 |
| De esas 30, **no explicadas por ningún script** | **23** |

Las 7 que sí tienen cobertura scriptada son:
`H_1314`, `H_1330`, `H_1333`, `H_1337`, `H_1344`, `H_1355`, `H_1361`.

Las 23 sin cobertura son:
`H_1143`, `H_1303`, `H_1328`, `H_1336`, `H_1338`, `H_1340`, `H_1341`,
`H_1342`, `H_1343`, `H_1345`, `H_1346`, `H_1348`, `H_1349`, `H_1350`,
`H_1351`, `H_1353`, `H_1354`, `H_1356`, `H_1363`, `H_1365`, `H_1366`,
`H_1368`, `H_1369`.

Ejemplo mínimo, `H_1336`:

- En `c1c1370`, el river es `SB b 1.5`, `BB r 5.0`, `SB f`; solo queda `BB`
  vivo y `fold_win: true`.
- En `8594ed5`, el river es `SB b 1.5`, `BB r 5.0`, `SB c 5.0`; hay dos
  vivos, `fold_win: false`, `showdown: BB (LaloMora)`.
- Ningún script de los 11 cambia ese `SB f` por `SB c`. El script
  `corregir_resultados_20261104.py` solo reclasifica; no edita esa acción.

Las 50 manos modificadas dentro de las primeras 900 no tienen cambios
semánticos de acciones, pero sí cambios de metadatos, bote, ganador, `showdown`
y marcas de ambigüedad. Eso ya altera los derivados, aunque la ventana tenga el
mismo número de manos.

### 2.4 La expansión de la base tampoco está scriptada

- `44acddb` añade 45 manos y no incluye ningún script de corrección de
  `data/hands_db.jsonl`; solo `hand_editor.py` y cambios de recorder/motor.
- `c1c1370` añade 47 manos y solo toca `data/hands_db.jsonl` y
  `data/decisions.jsonl`; no incluye scripts.
- La base pasa de 1253 a 1298 y después a 1345 sin un procedimiento
  versionado que pueda reejecutarse.

### 2.5 Resultado de la comparación byte a byte

No se alcanza el estado `8594ed5`. No se corrige nada a mano para forzar el
match. El manifiesto queda como está y la base canónica no se toca.

### 2.6 Manifiesto: valores propuestos, no aplicados

Los valores que corresponderían a la base actual son:

```text
HANDS_DB_COMMIT = '8594ed5'
HANDS_DB_SHA256 = '3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e'
HANDS_DB_LINEAS = 1344
```

No se escriben en `motor/learn.py` porque la condición de B1 era reproducir la
base byte a byte antes de reanclar. El manifiesto sigue declarando `51a6fb9` /
1253 / `c3172a14…`; por eso los tests de manifiesto siguen rojos y no se
consideran resueltos.

## 3. Auditoría individual de los 11 escritores

Todos escriben `data/hands_db.jsonl`. Ninguno es parte del flujo de producción;
son correcciones históricas de una sola vez. Todos requieren dry-run y backup
antes de un `--apply`. La columna «Reversión» indica si existe `--restore` o
solo backup interno.

| Escritor | Destino | Condición / alcance | Temporalidad | Motivo | Reversión |
|---|---|---|---|---|---|
| `corregir_anotaciones_20261110.py` | Base | `H_1303`, `H_1327`, `H_1351`; notas de bote y `audit_notes` | Una sola vez | Aclarar lecturas de bote obsoletas; no toca acciones ni `final_pot` | `--restore` |
| `corregir_bote_inflado_fold.py` | Base | Victorias por fold con `final_pot == matched - rake` y excedente no igualado | Una sola vez, pero selectivo | Reponer el excedente no igualado en el bote final | `--restore` |
| `corregir_folds_showdown.py` | Base | Folds inferidos sin apuesta pendiente | Una sola vez | Retirar folds espurios de showdowns | `--restore` |
| `corregir_mano_H_1333.py` | Base | `H_1333` | Una sola vez | Corregir fold espurio, rake 5 % y bote 37.1 | `--restore` |
| `corregir_resultados_20261029.py` | Base | `H_1314`, `H_1324` | Una sola vez | Separar victoria por fold de showdown | `--restore` |
| `corregir_resultados_20261104.py` | Base | 14 manos del 4/11: `H_1330`, `H_1336`, `H_1337`, `H_1342`, `H_1343`, `H_1344`, `H_1345`, `H_1348`, `H_1351`, `H_1354`, `H_1355`, `H_1356`, `H_1361`, `H_1366` | Una sola vez | Reclasificar resultados y rellenar `showdown` | `--restore` |
| `corregir_sesion_20261104.py` | Base | `H_1328`..`H_1341` comisión 5 %; folds/checks inferidos | Una sola vez | Ajustar rake real y retirar ambigüedades ya aplicadas | Backup interno; no tiene `--restore` |
| `corregir_showdown_posicion.py` | Base | Manos con etiqueta de posición de `showdown.winner1` incorrecta | Una sola vez | Corregir la etiqueta, no el ganador | `--restore` |
| `eliminar_mano_H_1323.py` | Base y `data/_eliminadas/H_1323.jsonl` | `H_1323` | Una sola vez | Quitar la mano fantasma duplicada de `H_1322` | `--restore` |
| `limpiar_anotaciones_ruido.py` | Base | Ambigüedades con `capture`, `capture_sha256` o `award_display_ignored` | Una sola vez | Quitar ruido de revisión; las capturas siguen en el índice | `--restore` |
| `limpiar_notas_inferidas.py` | Base | Ambigüedades y marcas `ambiguous` solo por inferencia | Una sola vez | Conservar `inferred` como procedencia y retirar avisos históricos | `--restore` |

Lectura de la auditoría:

- Los 11 son escritores reales; el instrumento los detecta.
- No se declaran en `motor/test_quien_escribe.py` en este checkpoint: hacerlo
  sin una reproducción exacta legitimaría la base actual sin resolver su
  procedencia.
- `corregir_sesion_20261104.py` y `corregir_mano_H_1333.py` tienen una
  dependencia de estado y una discrepancia de rake (`1.15` frente a `1.95`)
  que impide fijar un orden único con los artefactos versionados.

## 4. Snapshot de calibración

Creado en `data/calibration_window.json`.

| Campo | Valor |
|---|---|
| Estado | `provisional` / procedencia no verificada |
| Base | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| Líneas totales | 1344 |
| Regla | Primeras 900 líneas físicas; JSON válido con `players` y `streets`; se excluyen las 23 CM-004 |
| Manos válidas en el corte | 900 |
| Exclusiones | 23 |
| Ventana seleccionada | 877 |
| SHA-256 de las líneas seleccionadas | `ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed` |

El snapshot guarda IDs, hashes de línea seleccionados y excluidos, el hash
agregado y los hashes canónicos de los siete derivados. No cambia la ventana
ni las exclusiones.

Verificador de solo lectura:

```text
python tools/verificar_ventana_calibracion.py
VENTANA DE CALIBRACION: provisional
  base      : 3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e
  lineas    : 1344
  validas   : 900
  excluidas : 23
  ventana   : 877
  hash      : ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed
OK: la ventana coincide con el snapshot
```

Se probó el caso negativo sobre una copia con `H_0001` alterada: el
verificador devuelve código 1 y nombra la línea cambiada. No escribe archivos.

## 5. Derivados: regeneración en copias y comparación

Se regeneraron los siete derivados en un worktree detached en `1544249`, con
`data/` copiado. No se escribió en la base canónica ni se reemplazó ningún
derivado canónico.

Comando base:

```text
python tools/reconstruir_derivados.py backup
python tools/reconstruir_derivados.py regen
```

### 5.1 Hashes

```text
profile_ranges.json
  canónico   add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa
  actual     5988542b71adebe8bf003189d6bb545e2aa46afb4b01ec6690289c72405a0174
  51a6fb9    3572994bfa0b5150022fdb0bf177eaf9cde2098548a31ef6c4306d5c35bda5a0

postflop_ranges.json
  canónico   1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c
  actual      55803655e68dbc52f259752bbcae737515952ba9fc81fc941fa15c3b03d41a70
  51a6fb9     54a837b5c06c67cc01e7df48dde1c09b4dc0f761ec1342cc81bac6d2e2c4255d

preflop_stats.json
  canónico   53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749
  actual      bc3af87f92b86df959d289e24c37b53e378c4bc86c776ef0ef19dd7a3b47eaf0
  51a6fb9     53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749

player_stats.json
  canónico   ae6babbcbf94d018f5ba4590c7cc9143ca244836a14cf5370c55f56d55306e44
  actual     678bd42d2ff24a170ee9a89564dacab7edfde76e764d8e0400fe99530785a108
  51a6fb9     ae6babbcbf94d018f5ba4590c7cc9143ca244836a14cf5370c55f56d55306e44

profiles.json
  canónico   24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b
  actual      b5d691af7a87dbbbaf0e325c129be367c7550cce3ce7267aeccadaa85f51131e
  51a6fb9     24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b

behavior.json
  canónico   efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae
  actual     41ce0c53433724691425753d14e257044e1901ebe36e571090fbdebdfaeb31ab
  51a6fb9     efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae

observations.json
  canónico   86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3
  actual      f199bea94bfe856122fd80ba9ab50277bca76b524cfbebd3f3716a2b3ba31a0d
  51a6fb9     86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3
```

### 5.2 Prueba de control: los canónicos vienen de `51a6fb9`

Regenerando desde el blob de `51a6fb9` con el código actual:

- `preflop_stats.json`, `player_stats.json`, `profiles.json`,
  `behavior.json` y `observations.json` salen **byte a byte idénticos** a los
  canónicos.
- `profile_ranges.json` y `postflop_ranges.json` solo difieren en
  `meta.built_at` y `meta.code_commit`; el contenido es el mismo.

Esto demuestra que los derivados canónicos corresponden a la base declarada
de 1253 líneas, no a la base actual de 1344. La diferencia no nace de B1: la
base cambió después de generar los derivados.

### 5.3 Diferencias individuales con la base actual

| Derivado | Diferencia medida | Ejemplos |
|---|---|---|
| `profile_ranges.json` | `HERO` desaparece; 98 valores `omega` cambian; 1 celda `cnt` y 1 `opp`; `hands_used` 866 → 864 | `ALKILADO.no_raise` 0.9909 → 0.9863; `ANJO2017.no_raise` 0.7006 → 0.6874 |
| `postflop_ranges.json` | `HERO` desaparece; 25 celdas `opp` y 25 `cnt` cambian; `hands_used` 866 → 864 | `PEZ|flop|none|0|x` 15 → 14; `PEZ|river|none|0|x` 12 → 13 |
| `preflop_stats.json` | `HERO` desaparece; 12 jugadores cambian en `cats`, `denoms`, `cats_pos` y `denoms_pos`; `known_denoms.Jarduan` cambia | `Jarduan.bb_check` 46 → 44; `DominoSaurio.bb_check` 5 → 4; `Jeffer30bog.fold` 1 → 2 |
| `player_stats.json` | `HERO` desaparece; 27 jugadores cambian | `Arquejandro.vpip` 19 → 18; `Arquejandro.pfr` 19 → 18; `Arquejandro.wtsd` 11 → 10 |
| `profiles.json` | `HERO` desaparece; 25 perfiles cambian | `Arquejandro.n` 19 → 18; `Arquejandro.vpip` 0.3684 → 0.3889; `ANJO2017.cbet` 0.5 → 0.6667 |
| `behavior.json` | `HERO` desaparece; observaciones 8742 → 8657; 26 buckets `granular` (81 valores) y 8 `por_facing` (26 valores) cambian | `PEZ|flop|monotone|none.n` 29 → 28; `PEZ|flop|rainbow+pair|none.n` 58 → 52 |
| `observations.json` | 8742 → 8657: 94 observaciones antiguas desaparecen y 9 nuevas aparecen | `H_0060` pasa de `HERO` a `Jeffer30bog`; se pierden observaciones de `H_0918`, `H_0650`, `H_0841`, etc. |

### 5.4 Consecuencias estratégicas posibles

- Cualquier consumidor de `profiles`, `profile_ranges`, `postflop_ranges`,
  `preflop_stats`, `player_stats`, `behavior` u `observations` vería perfiles,
  rangos o frecuencias distintas para 25–27 jugadores y perdería la entrada
  `HERO`.
- `HERO` era una etiqueta de jugador en `H_0060`; la base actual la corrige a
  `Jeffer30bog`. No es una mejora estratégica demostrada: es un cambio de dato.
- `profile_ranges` y `postflop_ranges` pasan de 866 a 864 manos usadas; los
  rangos de los jugadores afectados no son comparables sin revisar la muestra.
- No hay validación de calidad, EV ni rentabilidad. **No se puede afirmar** que
  los derivados nuevos sean mejores; solo que son distintos y más coherentes
  con la base actual.
- Adoptarlos sin revisión independiente cambiaría recomendaciones en spots
  afectados y mezclaría la base actual con una procedencia aún no reproducida.
  Por eso no se sustituyen.

## 6. Métricas F7.2

Medición de solo lectura sobre la base actual y la ventana de 877 manos:

```text
python tools/auditar_solapamiento_multiway.py
```

| Métrica | Actual (base 1344) | Histórica (base 1253) |
|---|---:|---:|
| Puntos de decisión | 649 | 664 |
| Puntos de política | 506 | 512 |
| HU no fold | 296 | 301 |
| MULTIWAY no fold | 210 | 211 |
| MULTIWAY | 41,5 % | 41,2 % |
| Cota | 234 | 235 |

`DOCS/CONTRATO_F72A.md` queda con una nota B1 que separa las cifras actuales
de las históricas. No se cambia la política ni la firma. El test
`motor/test_rango_fiable.py::test_las_cifras_publicadas_coinciden_con_la_ventana_vigente`
pasa con la nota actual.

## 7. Fallos de la suite: clasificación actualizada

Antes de este checkpoint: 53 fallos. La corrección documental de F7.2 hace
pasar `motor/test_rango_fiable.py::test_las_cifras_publicadas_coinciden_con_la_ventana_vigente`.
La incorporación del verificador añadió un fichero a `tools`; el inventario se
actualizó de 147 a 148, sin cambiar la propiedad que mide.

Clasificación de los 52 fallos que quedan:

| Causa | Fallos | Estado |
|---|---:|---|
| Pin de base (1344 vs 1253, SHA, conteos) | 24 | No se reancla: reproducción no exacta |
| Manifiesto no redeclarado | 5 | No se reancla |
| Contrato de integridad (`test_quien_escribe`) | 2 | Los 11 escritores están auditados, pero no se declaran todavía |
| Dato derivado obsoleto | 14 | Derivados solo comparados en copia |
| Fixture o control semántico a rediseñar | 6 | No se tocan |
| Documentación histórica obsoleta | 1 | `pruebas/recorder/sesiones/sesion_validacion_1_20261104/informe_sesion_1.md:394`; no se reescribe historia |
| **Total** | **52** | |

No se corrige ningún pin para “hacer verde” la suite. Los fallos son
consecuencia de la base no reproducida y de los derivados no adoptados.

## 8. Confirmación de no cambios estratégicos

- `data/hands_db.jsonl`: sin cambios; 1344 líneas y SHA `3f0e...`.
- `data/preflop_matrices.json`: sin cambios; SHA
  `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1`.
- Los siete derivados canónicos: sin cambios; hashes de la sección 5.
- `MULTIWAY_SOPORTADO = False`.
- No se modificó lógica de `motor/`, `recorder/`, tablas preflop, rangos
  manuales ni contratos estratégicos.
- No se ejecutó ninguna sesión real ni calibración estratégica.
- No se avanzó B2.

## 9. Repositorio, commit y tests

- Rama: `main`.
- HEAD antes de este checkpoint: `1544249`.
- Cambios de este checkpoint: snapshot, verificador, nota F7.2, evidencia de
  reproducción, este informe y actualización del inventario de ficheros.
- Suite final: `52 failed, 1605 passed, 2 skipped, 5 xfailed`, con el comando
  canónico y `--tb=line`. El conjunto es el de B0 menos
  `motor/test_rango_fiable.py::test_las_cifras_publicadas_coinciden_con_la_ventana_vigente`;
  no aparecen fallos nuevos.
- `git status --short` queda limpio tras el commit de este checkpoint. No se
  commitea ningún derivado regenerado.

## 10. Punto de control y autorización necesaria

B1 queda **detenido en el checkpoint obligatorio**. Para continuar hace falta
una decisión independiente entre:

1. Localizar y versionar los cambios manuales que faltan, hasta reproducir
   `8594ed5` byte a byte; después reanclar manifiesto y derivados.
2. Aceptar la base actual como canónica por decisión explícita, documentar la
   excepción de procedencia y reanclar pines/derivados con revisión.
3. Rechazar total o parcialmente `8594ed5` y reparar la base antes de adoptar
   derivados.

No se sustituyen derivados canónicos, no se actualiza el manifiesto y no se
declaran los 11 escritores hasta que esa revisión ocurra.
