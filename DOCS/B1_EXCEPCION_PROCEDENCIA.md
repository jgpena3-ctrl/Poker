# B1-E — Excepción de procedencia: inventario y alcance

**Fecha:** 2026-11-11
**Estado:** revisión documental independiente, previa a autorización humana.
**Base auditada:** `data/hands_db.jsonl`, 1344 líneas, SHA-256
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.
**Alcance:** los 98 cambios semánticos de `44acddb`, las importaciones de 45 y
47 manos de `8b44917` y `c1c1370`, y la eliminación de `H_1323`.
**Restricciones:** revisión de solo lectura. No se modifica la base, el
manifiesto, los derivados canónicos, los hashes, los pines, la calibración, el
motor, las tablas, los rangos ni `MULTIWAY_SOPORTADO`. No se inicia B2 ni se
ejecutan sesiones reales.

**Referencia cerrada:** B1-R, `DOCS/B1_PROCEDENCIA_FORENSE.md`. Este documento
no reabre la investigación de las 23 manos allí verificadas; la usa como dato y
audita por separado el lote de `44acddb`, las importaciones y `H_1323`.

## 1. Veredicto y recomendación

**La excepción puede delimitarse, pero no cubre toda la base con la misma
fuerza.**

Recomendación: **adoptar con exclusiones**; no adoptar la base como canónica
plena ni regenerar derivados. La base puede conservarse como registro candidato
y usarse solo fuera de las limitaciones de §7. No puede declararse que las 98
correcciones estén verificadas contra grabación ni que la base sea reproducible.

La distinción es importante:

- **Adopción documental/registro:** posible con las exclusiones de §7.
- **Adopción para calibración y derivados:** no autorizada mientras las 57
  manos de la ventana afectadas por `44acddb` sigan sin revisión visual y los 35
  botes `NADA` sigan sin reconciliar.
- **Reproducibilidad:** no demostrada. Este documento no la afirma.

Si la definición de «adoptar» exige que la ventana de 877 quede validada y que
los derivados se reanelen, la respuesta cambia a **no adoptar todavía**.

### 1.1 Resumen de evidencia

| Elemento | Resultado |
|---|---|
| Cambios semánticos de `44acddb` | **98**: 75 manos antiguas y 23 del bloque nuevo `H_1283`–`H_1327` |
| Dentro de la ventana de calibración de 877 | **57** (todas antiguas); 41 quedan fuera |
| Evidencia de las acciones | **84 G** (patrón de checks), **11 T** (técnica directa), **3 U** (sin evidencia suficiente) |
| Manos de riesgo alto | **9**: `H_1283`, `H_1287`, `H_1289`, `H_1293`, `H_1300`, `H_1310`, `H_1311`, `H_1313`, `H_1324` |
| Importaciones 45 + 47 | **92** manos; estructura actual sin clases de auditoría, pero **35 con bote `NADA`** y **2 con stack activo nulo** |
| `H_1323` | Eliminación coherente; sin referencias activas ni decisiones; archivo de eliminación conserva el estado del backup previo |
| Afirmación de contenido | Solo las 23 de B1-R; de los 98, únicamente `H_1143` coincide con ese conjunto |

La tabla anterior no dice que las 98 sean erróneas. Dice que **la evidencia no
es homogénea**: una parte tiene soporte técnico, otra solo un patrón genérico, y
una minoría no tiene evidencia suficiente para elevarla a contenido verificado.

### 1.2 Qué no se afirma

- No se afirma que las 98 correcciones de `44acddb` sean correctas por el hecho
  de que las 23 de B1-R lo sean. **Son conjuntos distintos**: solo `H_1143`
  aparece en ambos.
- No se afirma que las 75 manos antiguas hayan sido revisadas visualmente. No lo
  fueron en B1-R.
- No se afirma que las 35 manos con bote `NADA` estén mal; se afirma que su
  aritmética no está reconciliada con ninguna lectura del bote.
- No se afirma que `H_1323` fuera un duplicado byte a byte de `H_1322`; era una
  captura fantasma de la misma mesa y tablero, con stacks parcialmente distintos.
- No se autoriza B2, ni sesiones reales, ni cambios de calibración.

## 2. Método y niveles de evidencia

La revisión se hizo sin escribir sobre la base canónica:

- lectura de los blobs `8b44917`, `44acddb`, `c1c1370` y `8594ed5` con
  `git show <commit>:data/hands_db.jsonl`;
- comparación por mano y por acción, incluyendo posición, acción, importe,
  orden y marca `inferred`;
- `tools/auditar_rango.py --db <copia> --hasta H_9999 --json <salida>` sobre los
  cuatro estados;
- `tools/aritmetica_botes.py` sobre los estados históricos, ejecutado en una
  copia temporal para no escribir en `trabajo/`;
- lectura de la documentación de correcciones y de la ventana de calibración;
- comprobación de IDs, referencias de `decisions.jsonl`, duplicados y stacks.

No se usó una mención genérica en un documento como prueba de una corrección.
Tampoco se usó `PARTICION_FASE_D.md`: su lista es una partición operativa, no
una verificación.

### 2.1 Niveles usados en este documento

| Código | Significado | Qué permite afirmar |
|---|---|---|
| **V** | Verificación visual contra grabación | Contenido correcto para esa mano |
| **T** | Evidencia técnica o documental específica | La corrección elimina una contradicción o está descrita para esa mano; no prueba por sí sola la grabación |
| **G** | Evidencia genérica o de patrón | Hay una regla documentada y un patrón sistemático; no hay verificación individual |
| **U** | Procedencia desconocida, consistencia estructural | El estado posterior pasa la auditoría; no hay evidencia de contenido |
| **R** | Dudoso o potencialmente incorrecto | No debe usarse como verificado |

**Ninguna de las 98 modificaciones de `44acddb` tiene nivel V para ese paso.**
Las 23 de B1-R tienen V sobre su estado final, pero no sobre el paso intermedio
de `44acddb`. De las 98, solo `H_1143` pertenece a las 23 de B1-R, y su cambio
de `44acddb` no es el que se verificó visualmente.

## 3. Los 98 cambios semánticos de `44acddb`

### 3.1 Composición

`44acddb` modifica 119 manos existentes. De ellas, **98 cambian la secuencia de
acciones** (posición, acción, importe u orden). Las otras 21 solo cambian campos
no accionales. Los 98 se reparten así:

| Grupo | Manos | Ventana de 877 | Evidencia de acción |
|---|---:|---:|---|
| Manos antiguas (`H_0*`/`H_1*`) | 75 | 57 dentro / 18 fuera | 75 G |
| Bloque nuevo `H_1283`–`H_1327` | 23 | 0 dentro / 23 fuera | 11 T, 9 G, 3 U |
| **Total** | **98** | **57 dentro / 41 fuera** | **84 G, 11 T, 3 U** |

Campos modificados entre las 98:

| Campo | Manos |
|---|---:|
| `streets` | 98 |
| `recorder_audit` | 23 |
| `final_pot` | 22 |
| `winner` | 13 |
| `players` | 8 |
| `showdown` | 1 |

Ninguna de las 98 está entre las 23 exclusiones CM-004 de la ventana. Las 57
manos antiguas dentro de la ventana **sí afectan la calibración**: cambiar un
check cambia el número de acciones, el cierre de la calle y las frecuencias que
se derivan de ella.

### 3.2 Manos antiguas: 75 cambios, todos de checks

Las 75 manos antiguas tienen un patrón único y muy cerrado:

- **144 acciones modificadas, todas `x` (check)**;
- **128 checks eliminados**, todos con `inferred: false`;
- **16 checks añadidos**, todos con `inferred: true`;
- ninguna acción `f`, `c`, `r`, `b` o `p` cambia;
- ningún campo distinto de `streets` cambia;
- ninguna de las 75 resuelve una clase de `auditar_rango.py`: las clases que ya
  existían antes siguen existiendo después;
- no hay documento que describa el cambio de check de cada mano.

Esto es compatible con una **normalización sistemática de checks** (retirar
checks no inferidos y añadir checks inferidos en los casos que el recorder
considera no ambiguos), pero **no hay un script versionado que la reproduzca**.
La evidencia es genérica: mensaje de commit, patrón uniforme y consistencia
estructural. No es verificación visual.

**Impacto:** 57 de las 75 están dentro de la ventana de 877. Son las que
justifican que la adopción para calibración quede excluida en §7.

### 3.3 Bloque nuevo: 23 cambios heterogéneos

Las 23 manos nuevas no son un lote homogéneo:

- **9 son solo de checks** (`H_1283`, `H_1284`, `H_1287`, `H_1289`, `H_1293`,
  `H_1310`, `H_1313`, `H_1315`, `H_1322`);
- **14 mezclan checks con folds, calls, bets o raises**;
- **11 tienen una corrección técnica directa** de una contradicción detectada
  (`H_1285`, `H_1292`, `H_1298`, `H_1305`, `H_1306`, `H_1312`, `H_1317`,
  `H_1318`, `H_1320`, `H_1325`, `H_1327`);
- **14 tienen además una corrección técnica de campos** (ganador, bote,
  jugador o auditoría); el solape con las 11 anteriores es parcial;
- **3 no tienen evidencia suficiente**: `H_1300`, `H_1311`, `H_1324` (los tres
  con bote `NADA`);
- **6 son solo de checks pero con campos desconocidos**: `H_1283`, `H_1287`,
  `H_1289`, `H_1293`, `H_1310`, `H_1313` (los seis con bote `NADA`).

Las 23 están fuera de la ventana actual. No afectan la calibración de 877, pero
sí el contenido del registro completo y cualquier uso futuro que amplíe la
ventana.

### 3.4 Inventario completo de las 75 manos antiguas

La columna «Ventana» indica si la mano está dentro de la ventana de 877. La
columna «Bote actual» es la clase de `aritmetica_botes.py` en el estado actual.
El detalle exacto de cada acción, con antes/después e `inferred`, está en
`DOCS/B1_EXCEPCION_INVENTARIO.json`.

| Mano | Ventana | Cambio de acciones | Ev. | Bote actual | Riesgo | Nota |
|---|---|---|---|---|---|---|
| `H_0048` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0069` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0088` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0092` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0098` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0099` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0120` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0123` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0130` | 877 | quita 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0136` | 877 | quita 2 check(s) (flop 2) | G | UNICA_TOL | medio | — |
| `H_0140` | 877 | quita 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0144` | 877 | quita 3 check(s) (flop 2, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0153` | 877 | quita 4 check(s) (flop 4) | G | UNICA_EXACTA | medio | — |
| `H_0186` | 877 | quita 1 check(s) (river 1) | G | UNICA_EXACTA | medio | — |
| `H_0188` | 877 | añade 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0194` | 877 | quita 1 check(s) (river 1) | G | UNICA_TOL | medio | — |
| `H_0205` | 877 | quita 1 check(s) (river 1) | G | UNICA_EXACTA | medio | — |
| `H_0228` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0240` | 877 | quita 2 check(s) (flop 2) | G | UNICA_TOL | medio | — |
| `H_0265` | 877 | quita 2 check(s) (river 2) | G | UNICA_EXACTA | medio | — |
| `H_0266` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0269` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0270` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0272` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0274` | 877 | quita 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0276` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0300` | 877 | quita 3 check(s) (flop 1, turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0306` | 877 | quita 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0315` | 877 | quita 2 check(s) (turn 1, river 1) | G | UNICA_EXACTA | medio | — |
| `H_0319` | 877 | quita 1 check(s) (preflop 1) | G | UNICA_EXACTA | medio | — |
| `H_0376` | 877 | quita 3 check(s) (turn 3) | G | UNICA_EXACTA | medio | — |
| `H_0415` | 877 | quita 4 check(s) (flop 2, river 2) | G | UNICA_EXACTA | medio | — |
| `H_0430` | 877 | quita 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0445` | 877 | quita 3 check(s) (flop 3) | G | UNICA_TOL | medio | — |
| `H_0486` | 877 | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0527` | 877 | quita 1 check(s) (turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0589` | 877 | quita 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0614` | 877 | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0617` | 877 | quita 1 check(s) (turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0640` | 877 | quita 2 check(s) (flop 1, turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0650` | 877 | quita 6 check(s) (flop 2, turn 2, river 2) | G | UNICA_EXACTA | medio | — |
| `H_0662` | 877 | quita 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0691` | 877 | quita 2 check(s) (flop 2) | G | UNICA_TOL | medio | — |
| `H_0708` | 877 | quita 3 check(s) (flop 3) | G | UNICA_EXACTA | medio | — |
| `H_0711` | 877 | quita 1 check(s) (turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0715` | 877 | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0773` | 877 | quita 2 check(s) (flop 2) | G | UNICA_TOL | medio | — |
| `H_0826` | 877 | quita 2 check(s) (flop 1, turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0832` | 877 | quita 1 check(s) (turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0841` | 877 | quita 4 check(s) (flop 2, river 2) | G | UNICA_EXACTA | medio | — |
| `H_0847` | 877 | quita 1 check(s) (flop 1) | G | UNICA_EXACTA | medio | — |
| `H_0852` | 877 | añade 1 check(s) (flop 1) | G | UNICA_TOL | medio | — |
| `H_0855` | 877 | añade 1 check(s) (river 1) | G | UNICA_EXACTA | medio | — |
| `H_0886` | 877 | quita 2 check(s) (flop 1, turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0889` | 877 | quita 2 check(s) (flop 1, turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0918` | 877 | quita 6 check(s) (flop 2, turn 2, river 2) | G | UNICA_EXACTA | medio | — |
| `H_0926` | 877 | añade 1 check(s) (turn 1) | G | UNICA_EXACTA | medio | — |
| `H_0931` | fuera | quita 1 check(s) (turn 1) | G | UNICA_EXACTA | bajo | — |
| `H_0957` | fuera | quita 3 check(s) (flop 3) | G | UNICA_TOL | bajo | — |
| `H_0964` | fuera | quita 3 check(s) (flop 3) | G | UNICA_EXACTA | bajo | — |
| `H_0965` | fuera | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | bajo | — |
| `H_0967` | fuera | añade 1 check(s) (river 1) | G | UNICA_EXACTA | bajo | — |
| `H_0985` | fuera | quita 5 check(s) (flop 5) | G | UNICA_EXACTA | bajo | — |
| `H_0997` | fuera | quita 6 check(s) (flop 2, turn 2, river 2) | G | UNICA_EXACTA | bajo | — |
| `H_1000` | fuera | quita 3 check(s) (flop 3) | G | UNICA_EXACTA | bajo | — |
| `H_1029` | fuera | quita 4 check(s) (flop 2, turn 2) | G | UNICA_EXACTA | bajo | — |
| `H_1030` | fuera | añade 1 check(s) (river 1) | G | UNICA_EXACTA | bajo | — |
| `H_1039` | fuera | quita 4 check(s) (flop 2, turn 2) | G | UNICA_EXACTA | bajo | — |
| `H_1085` | fuera | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | bajo | — |
| `H_1110` | fuera | añade 1 check(s) (flop 1) | G | UNICA_EXACTA | bajo | — |
| `H_1139` | fuera | quita 2 check(s) (turn 2) | G | UNICA_EXACTA | bajo | — |
| `H_1140` | fuera | quita 2 check(s) (flop 2) | G | UNICA_TOL | bajo | — |
| `H_1143` | fuera | añade 1 check(s) (flop 1) | G | UNICA_TOL | bajo | B1-R final; paso 44acddb no verificado |
| `H_1155` | fuera | quita 2 check(s) (flop 2) | G | UNICA_EXACTA | bajo | — |
| `H_1227` | fuera | añade 2 check(s) (flop 2) | G | UNICA_EXACTA | bajo | — |

### 3.5 Inventario completo de las 23 manos nuevas

Todas están fuera de la ventana de 877. «Ev. acción/campos» usa los niveles de
§2.1. La columna «Auditoría» muestra la clase detectada antes y después en el
paso `44acddb`; no es una verificación de grabación. La columna «Evidencia
específica» puede cubrir solo un campo: por ejemplo, `DEFECTO_H1292.md` documenta
el bote de `H_1284`, no sus checks; `AUDITORIA_ESTADO_JUGADORES.md` documenta el
estado de `H_1327`, no todas sus acciones.

| Mano | Cambio de acciones | Campos | Ev. acción/campos | Auditoría | Bote | Riesgo | Evidencia específica |
|---|---|---|---|---|---|---|---|
| `H_1283` | añade 3 check(s) (turn 3) | final_pot, players, recorder_audit, streets, winner | G/U | — | NADA | alto | — |
| `H_1284` | añade 2 check(s) (flop 2) | final_pot, recorder_audit, streets, winner | G/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | DEFECTO_H1292.md |
| `H_1285` | quita BTN r 51.2 | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | — |
| `H_1287` | quita 1 check(s) (turn 1) | final_pot, players, recorder_audit, streets | G/U | — | NADA | alto | — |
| `H_1289` | añade 2 check(s) (flop 2) | final_pot, players, recorder_audit, streets | G/U | — | NADA | alto | — |
| `H_1292` | quita UTG f | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | DEFECTO_H1292.md |
| `H_1293` | quita 1 check(s) (turn 1) | final_pot, players, recorder_audit, streets | G/U | — | NADA | alto | — |
| `H_1298` | añade BB c 16.8 | final_pot, recorder_audit, streets | T/T | ACTIVO_SIN_ACCION_CALLE → limpio | NADA | medio | — |
| `H_1300` | reconstruye preflop, flop, turn, river; 7 quitadas / 9 añadidas | final_pot, players, recorder_audit, streets | U/R | — | NADA | alto | — |
| `H_1305` | añade BB f | final_pot, recorder_audit, showdown, streets | T/T | AUSENCIA_RESPUESTA_BB → limpio | UNICA_EXACTA | medio | — |
| `H_1306` | añade CO c 1, CO c 7, SB b 8.5, CO f | final_pot, players, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | — |
| `H_1310` | añade 2 check(s) (river 2) | final_pot, recorder_audit, streets | G/U | — | NADA | alto | — |
| `H_1311` | reconstruye preflop, flop, turn, river; 5 quitadas / 14 añadidas | final_pot, players, recorder_audit, streets | U/R | — | NADA | alto | — |
| `H_1312` | quita SB c 1, SB f; añade CO f, SB f | final_pot, recorder_audit, streets, winner | T/T | ACTIVO_SIN_ACCION, ACTIVO_SIN_ACCION_CALLE, WINNER_FOLDEO → limpio | UNICA_EXACTA | medio | — |
| `H_1313` | añade 1 check(s) (flop 1) | final_pot, players, recorder_audit, streets | G/U | — | NADA | alto | — |
| `H_1315` | añade 2 check(s) (turn 2) | final_pot, recorder_audit, streets, winner | G/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | — |
| `H_1317` | quita SB c 1; añade SB r 2 | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_EXACTA | medio | — |
| `H_1318` | quita UTG r 93.5; añade BB x | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_TOL | medio | — |
| `H_1320` | quita SB f | recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | UNICA_EXACTA | medio | DEFECTO_H1292.md |
| `H_1322` | añade 2 check(s) (flop 2) | final_pot, recorder_audit, streets, winner | G/T | WINNER_FOLDEO → limpio | NADA | medio | — |
| `H_1324` | añade SB f | final_pot, recorder_audit, streets | U/R | — | NADA | alto | — |
| `H_1325` | quita CO f | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | NADA | medio | DEFECTO_H1292.md |
| `H_1327` | quita UTG f; añade UTG c 2.1, UTG f | final_pot, recorder_audit, streets, winner | T/T | WINNER_FOLDEO → limpio | NADA | medio | AUDITORIA_ESTADO_JUGADORES.md |

### 3.6 Lo que cambia y lo que no cambia en la calibración

- **57 manos antiguas dentro de la ventana**: su secuencia de acciones cambia
  solo en checks. No hay revisión visual ni documento por mano. La calibración
  actual no puede declararse validada con estas 57 sin una decisión explícita.
- **18 manos antiguas fuera de la ventana**: no afectan la ventana de 877, pero
  siguen siendo parte del registro completo.
- **23 manos nuevas fuera de la ventana**: no afectan la ventana actual; 13 de
  ellas tienen bote `NADA`.
- **23 manos de B1-R**: están fuera de la ventana; 9 de ellas tienen bote
  `NADA`. La verificación visual de B1-R certifica sus acciones, no la
  aritmética del bote.

Por tanto, la ventana de 877 **no es una ventana verificada**: contiene 57
modificaciones de `44acddb` sin revisión visual. El snapshot provisional de B1
sigue siendo un snapshot, no una adopción.

## 4. Importaciones de 45 y 47 manos

### 4.1 Validación estructural

| Bloque | Rango | Manos | IDs únicos | 6 jugadores | Defectos de auditoría al importar | Defectos actuales | Bote `NADA` actual | Stack activo nulo actual |
|---|---|---:|---:|---|---:|---:|---:|---|
| `8b44917` | `H_1283`–`H_1327` | 45 | 45 | 45/45 | 33/45 con alguna clase | 0 | 18 | `H_1304`; `H_1323` fue eliminada |
| `c1c1370` | `H_1328`–`H_1374` | 47 | 47 | 47/47 | 8/47 con alguna clase | 0 | 17 | `H_1349` |

Lectura correcta de la tabla:

- **Al importar no estaban limpias.** El bloque de 45 tenía 33 manos con al
  menos una clase de auditoría, sobre todo `WINNER_FOLDEO`; además `H_1303`
  tenía `IMPORTE_SUBIDA`, `H_1323` `WINNER_VACIO`, `H_1312` problemas de
  `ACTIVO_SIN_ACCION` y `H_1305` `AUSENCIA_RESPUESTA_BB`.
- El bloque de 47 tenía 8 manos con clases: `H_1349` con `IMPORTE_SUBIDA` e
  `INACTIVO_QUE_ACTUA`, y siete manos con `ACTIVO_SIN_ACCION_CALLE`.
  `H_1356` y `H_1365` tenían además violaciones de stack en el análisis
  aritmético.
- **El estado actual no tiene clases de auditoría en ninguno de los 92.** Las
  correcciones posteriores (`44acddb`, `8594ed5`) resolvieron esas clases. Eso
  no convierte las importaciones en verificadas visualmente: solo elimina las
  contradicciones detectadas.
- **No hay IDs duplicados ni duplicados exactos** en los bloques. `H_1323` era
  un duplicado de captura, no una fila idéntica: coincide en mesa, tablero y
  jugadores/posiciones con `H_1322`, pero no en todos los stacks.
- **Las 92 están fuera de la ventana de 877.** Por eso los 35 `NADA` no afectan
  la calibración actual; sí afectan el registro completo y cualquier ventana
  futura.

### 4.2 Botes `NADA`

`aritmetica_botes.py` clasifica 35 manos actuales como `NADA`: el bote declarado
no sale con ninguna combinación de lectura absoluta/parcial, con o sin comisión,
ni con o sin la ciega del SB. No es lo mismo que «mano incorrecta»: es una
**falta de reconciliación aritmética**. Para esta excepción se excluyen de
cualquier uso que dependa del bote, EV, equity o resultado económico.

- **Bloque 45 (18):** `H_1283`, `H_1287`, `H_1288`, `H_1289`, `H_1293`, `H_1295`, `H_1296`, `H_1298`, `H_1300`, `H_1301`, `H_1302`, `H_1310`, `H_1311`, `H_1313`, `H_1322`, `H_1324`, `H_1325`, `H_1327`
- **Bloque 47 (17):** `H_1343`, `H_1344`, `H_1345`, `H_1346`, `H_1348`, `H_1349`, `H_1351`, `H_1355`, `H_1356`, `H_1357`, `H_1358`, `H_1361`, `H_1365`, `H_1368`, `H_1371`, `H_1372`, `H_1374`

De las 23 manos de B1-R, **9** están en esta lista: `H_1343`, `H_1345`,
`H_1346`, `H_1348`, `H_1349`, `H_1351`, `H_1356`, `H_1365`, `H_1368`.
La verificación visual de B1-R no reconcilia sus botes.

### 4.3 Stacks activos nulos

- `H_1304` (`Tonytruco`, BTN) sigue con `stack: null` y `active: true`. Está en
  el bloque de 45 y no está entre las 23 de B1-R.
- `H_1349` (`LaloMora`, UTG) tiene `stack: null` en el estado actual. Sus
  acciones fueron verificadas por B1-R, pero el stack no. No debe usarse en
  cálculos que dependan del stack efectivo.

No se inventa un stack ni se reinterpreta la mano. Se excluye de los usos que
lo necesiten.

### 4.4 Decisiones y referencias

`data/decisions.jsonl` tiene 506 filas y 91 `hand_id` no nulos. Los 91 existen
en la base actual; no hay referencias huérfanas a manos inexistentes. Hay 3
filas con `hand_id: null` (`fa6c3648ae2946899f75ff9cc924233e`,
`8f217fb9aba6487286690cebb403d4f4`, `82ec509c6f14491099f07aa17a53ddea`), un
defecto no relacionado con `H_1323` y fuera del alcance de esta revisión.
Ninguna decisión referencia `H_1323`.

## 5. `H_1323`: eliminación y dependencias

`H_1323` fue eliminada en `8594ed5` y archivada en
`data/_eliminadas/H_1323.jsonl`. La eliminación tiene procedimiento versionado:
`tools/eliminar_mano_H_1323.py`.

Hechos comprobados:

- No está en la base actual de 1344 líneas.
- El archivo de eliminación coincide con el backup previo a la eliminación
  (`data/_backup_eliminar_H_1323/hands_db.jsonl`).
- Difiere de la versión de `c1c1370` solo en que le falta
  `recorder_audit.award_display_ignored: []`, un campo vacío. No hay diferencia
  de acciones, ganador, bote ni jugadores.
- No tiene ganador, su bote es 1.0, tiene `recorder_audit.fold_win: true`, 7
  acciones preflop y 0 postflop; no es una mano jugada completa.
- Coincide con `H_1322` en mesa, tablero y jugadores/posiciones, pero **no
  exactamente en stacks**: `BB` pasa de 150.2 a `null`, `CO` de 101.3 a 96.2 y
  `SB` de 52.6 a 52.1. El script de eliminación verifica tablero y conjunto
  `pos/name`, no igualdad de stacks. La eliminación sigue siendo coherente, pero
  la frase «repite los stacks» de la documentación anterior es imprecisa.
- No hay referencias activas en tests, fixtures, decisiones ni código. Las
  apariciones son documentales o históricas: `DOCS/AUDITORIA_ESTADO_JUGADORES.md`,
  `DOCS/B1_CHECKPOINT_2026-11-10.md`, `DOCS/B1_PROCEDENCIA_FORENSE.md`,
  `DOCS/B1_REPRO_DIFF.json`, `DOCS/PLAN_TECNICO_MOTOR_2026-11-10.md`, la sesión
  histórica `hands_db_full_after_session.jsonl`, el comentario de
  `recorder/recorder_live.py` y el propio script de eliminación.
- No hay decisiones que la referencien.

**Conclusión:** la eliminación es aceptable y no deja referencias huérfanas. La
observación sobre los stacks no cambia el veredicto; corrige una descripción.

## 6. Matriz de evidencia y riesgo

### 6.1 Por tipo de evidencia

| Evidencia | Manos | Dentro de 877 | Fuera | `NADA` | Uso permitido |
|---|---:|---:|---:|---:|---|
| **V** — 23 de B1-R (estado final) | 23 | 0 | 23 | 9 | Contenido verificado; no atribuir a `44acddb`; excluir bote/stack cuando aplique |
| **T** — técnica directa en acciones | 11 | 0 | 11 | 3 | Registro con soporte técnico; no es verificación visual |
| **G** — patrón genérico de checks | 84 | 57 | 27 | 7 | Solo normalización genérica; las 57 de la ventana no son base de calibración |
| **U** — desconocida | 3 | 0 | 3 | 3 | Solo registro; no usar como verificado |

Los 23 de B1-R no son los 23 nuevos de `44acddb`. La única intersección con los
98 es `H_1143`; las demás manos de B1-R están en `H_1303` y dentro del bloque
`H_1328`–`H_1374`, no en el bloque `H_1283`–`H_1327`.

### 6.2 Por riesgo

| Riesgo | Manos | Composición |
|---|---:|---|
| Bajo | 18 | Las 18 manos antiguas fuera de la ventana; cambios solo de checks |
| Medio | 71 | 57 antiguas dentro de la ventana + 11 técnicas + 3 con campos técnicos (`H_1284`, `H_1315`, `H_1322`) |
| Alto | 9 | `H_1283`, `H_1287`, `H_1289`, `H_1293`, `H_1300`, `H_1310`, `H_1311`, `H_1313`, `H_1324` |

Las 9 de riesgo alto combinan ausencia de evidencia específica con bote `NADA`;
`H_1300` y `H_1311` son reconstrucciones grandes y `H_1324` añade un fold sin
documento. No se afirma que estén mal: se afirma que no hay base suficiente
para elevarlas a contenido verificado.

### 6.3 Deuda preexistente del registro

El estado actual conserva defectos de formato/ausencia que no nacen de este
lote y que no se atribuyen a las 98 ni a las importaciones:

- `ACTIVO_SIN_POSICION`: 55 manos antiguas;
- `SIN_ALLIN`: 71 manos antiguas;
- `AUSENCIA_RESPUESTA_BB`: 1 mano (`H_1241`), documentada como falso positivo
  porque el BB está all-in.

Los bloques importados no aparecen en esas listas. Esta deuda sigue siendo una
limitación del registro completo, pero queda fuera del alcance de esta excepción.

## 7. Alcance exacto de la excepción

### 7.1 Cubierto con verificación de contenido

- Las **23 manos de B1-R**, con su alcance: contenido final verificado, procedencia
  manual y no reproducible. No se reabre su investigación. Son:
  `H_1143`, `H_1303`, `H_1328`, `H_1336`, `H_1338`, `H_1340`, `H_1341`,
  `H_1342`, `H_1343`, `H_1345`, `H_1346`, `H_1348`, `H_1349`, `H_1350`,
  `H_1351`, `H_1353`, `H_1354`, `H_1356`, `H_1363`, `H_1365`, `H_1366`,
  `H_1368`, `H_1369`.
- La **eliminación de `H_1323`**, con script versionado, archivo de eliminación y
  ausencia de referencias activas.

### 7.2 Cubierto con evidencia técnica, sin verificación visual

- **11 correcciones de acción** del bloque nuevo:
  `H_1285`, `H_1292`, `H_1298`, `H_1305`, `H_1306`, `H_1312`, `H_1317`,
  `H_1318`, `H_1320`, `H_1325`, `H_1327`.
- **14 correcciones de campos** con soporte técnico:
  `H_1284`, `H_1285`, `H_1292`, `H_1298`, `H_1305`, `H_1306`, `H_1312`,
  `H_1315`, `H_1317`, `H_1318`, `H_1320`, `H_1322`, `H_1325`, `H_1327`.
- Las importaciones de 45 y 47 manos, en cuanto a **estructura actual**: sin
  clases de auditoría, sin IDs duplicados y sin duplicados exactos.

Estas correcciones se aceptan como **técnicamente soportadas**, no como
verificadas contra grabación. Las que tengan bote `NADA` siguen excluidas de
los usos aritméticos.

### 7.3 Cubierto solo como normalización genérica

- Las **75 manos antiguas** de `44acddb`, con 144 checks cambiados.
- De ellas, **57 están dentro de la ventana de 877** y quedan **excluidas de
  cualquier afirmación de calibración validada** hasta revisión visual:
  `H_0048`, `H_0069`, `H_0088`, `H_0092`, `H_0098`, `H_0099`, `H_0120`, `H_0123`, `H_0130`, `H_0136`, `H_0140`, `H_0144`, `H_0153`, `H_0186`, `H_0188`, `H_0194`, `H_0205`, `H_0228`, `H_0240`, `H_0265`, `H_0266`, `H_0269`, `H_0270`, `H_0272`, `H_0274`, `H_0276`, `H_0300`, `H_0306`, `H_0315`, `H_0319`, `H_0376`, `H_0415`, `H_0430`, `H_0445`, `H_0486`, `H_0527`, `H_0589`, `H_0614`, `H_0617`, `H_0640`, `H_0650`, `H_0662`, `H_0691`, `H_0708`, `H_0711`, `H_0715`, `H_0773`, `H_0826`, `H_0832`, `H_0841`, `H_0847`, `H_0852`, `H_0855`, `H_0886`, `H_0889`, `H_0918`, `H_0926`.
- Las **18 restantes** están fuera de la ventana y se aceptan solo como registro:
  `H_0931`, `H_0957`, `H_0964`, `H_0965`, `H_0967`, `H_0985`, `H_0997`, `H_1000`, `H_1029`, `H_1030`, `H_1039`, `H_1085`, `H_1110`, `H_1139`, `H_1140`, `H_1143`, `H_1155`, `H_1227`.

No se atribuye este lote a un script inexistente. La excepción reconoce que es
una normalización de checks no reproducible con los artefactos versionados.

### 7.4 Cubierto solo como importación de sesión

- **45 manos `H_1283`–`H_1327`** de `8b44917`.
- **47 manos `H_1328`–`H_1374`** de `c1c1370`.
- Se aceptan como bloques de sesión, no como reconstrucciones manuales.
- **35 manos con bote `NADA`** quedan excluidas de todo uso que dependa del
  bote, EV, equity o resultado económico:
  `H_1283`, `H_1287`, `H_1288`, `H_1289`, `H_1293`, `H_1295`, `H_1296`, `H_1298`, `H_1300`, `H_1301`, `H_1302`, `H_1310`, `H_1311`, `H_1313`, `H_1322`, `H_1324`, `H_1325`, `H_1327`, `H_1343`, `H_1344`, `H_1345`, `H_1346`, `H_1348`, `H_1349`, `H_1351`, `H_1355`, `H_1356`, `H_1357`, `H_1358`, `H_1361`, `H_1365`, `H_1368`, `H_1371`, `H_1372`, `H_1374`.
- **`H_1304` y `H_1349`** quedan excluidas de los usos que dependan del stack
  efectivo por tener stack activo nulo.

### 7.5 No cubierto como contenido verificado

Las siguientes 9 manos quedan fuera de toda afirmación de contenido verificado
hasta revisión específica:

`H_1283`, `H_1287`, `H_1289`, `H_1293`, `H_1300`, `H_1310`, `H_1311`, `H_1313`, `H_1324`

Dentro de ellas:

- reconstrucciones grandes sin documento: **`H_1300`, `H_1311`**;
- fold añadido sin documento: **`H_1324`**;
- checks con campos desconocidos y bote `NADA`: **`H_1283`, `H_1287`,
  `H_1289`, `H_1293`, `H_1310`, `H_1313`**.

Se conservan en el registro, pero no se usan para calibrar, calcular EVs ni
declarar que la base está verificada.

### 7.6 Condiciones

1. No actualizar el manifiesto de `motor/learn.py`, ni los pines, ni los hashes
   canónicos.
2. No sustituir los derivados canónicos ni reanclar la ventana de calibración.
3. No declarar las 98 correcciones como verificadas visualmente.
4. No declarar la base como reproducible.
5. No usar las 57 manos de §7.3 como base de una calibración validada.
6. No usar las 35 manos `NADA` para aritmética de bote/EV/equity.
7. No usar `H_1304` ni `H_1349` para análisis dependientes del stack.
8. Mantener `MULTIWAY_SOPORTADO=False`.
9. No iniciar B2 ni ejecutar sesiones reales con esta base como si estuviera
   plenamente validada.

## 8. Recomendación final

**Adoptar con exclusiones.**

La base de 1344 manos puede aceptarse como **registro candidato con excepción de
procedencia delimitada**, siempre que la adopción se limite a los usos de §7 y
no se presente como calibración validada. Las exclusiones son las 57 manos de la
ventana, las 35 manos con bote `NADA`, las 2 manos con stack nulo y las 9 manos
sin evidencia suficiente.

No se recomienda la adopción plena. Si el mantenedor exige que la ventana de 877
y los derivados canónicos queden validados en el mismo acto, la recomendación es
**no adoptar todavía**: primero deben revisarse las 57 manos antiguas de la
ventana y reconciliarse o excluirse formalmente los 35 botes `NADA`.

Este documento termina aquí. No concede la excepción, no modifica la base y no
inicia B2. La autorización humana es el siguiente paso.
