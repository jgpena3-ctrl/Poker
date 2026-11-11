# B1-E — Revisión de integridad y nueva propuesta de adopción de la base de 1344

**Fecha:** 2026-11-11
**Estado:** revisión documental independiente, aceptada el 2026-11-11 como base
para la adopción del registro; no reabre B1-R.
**Base auditada:** `data/hands_db.jsonl`, 1344 líneas, SHA-256
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.
**Alcance:** los 98 cambios semánticos de `44acddb`, las importaciones de 45 y
47 manos de `8b44917` y `c1c1370`, la ventana provisional de 877, la eliminación
de `H_1323` y la aptitud analítica de la base completa.
**Restricciones:** revisión de solo lectura. No se modifica la base, el
manifiesto, los derivados canónicos, los hashes, los pines, la calibración, el
motor, las tablas, los rangos ni `MULTIWAY_SOPORTADO`. No se inicia B2 ni se
ejecutan sesiones reales.

**Nota de vigencia (2026-11-11):** revisión aceptada como base para la
adopción. La autorización permite redeclarar únicamente las tres constantes
del manifiesto de base —`HANDS_DB_COMMIT`, `HANDS_DB_SHA256` y
`HANDS_DB_LINEAS`— y añadir un verificador de solo lectura. Las condiciones de
§7.1.5, §7.2 (fila «Derivados/pines/manifiesto») y §7.4.1 se entienden
modificadas solo en ese punto: el manifiesto declara la base adoptada, pero no
se reanclan derivados, pines, hashes de derivados ni la calibración. Los
hallazgos, matrices y clasificaciones de este informe no cambian. El acto formal
está en `DOCS/CANAL_MANUAL_CERRADO.md`.

**Referencia cerrada:** B1-R, `DOCS/B1_PROCEDENCIA_FORENSE.md`, veredicto en
`0744ebd`. Este documento no reabre la investigación de las 23 manos allí
verificadas. La usa como dato de contenido y audita por separado la integridad
real y la aptitud de cada campo.

## 1. Veredicto y recomendación

**La procedencia sigue sin ser reproducible, pero la procedencia no es un
defecto de contenido.** Una mano no se excluye por haber sido modificada, por no
tener un script que reproduzca el cambio, ni por no tener un documento
individual. Se excluye un campo o un tipo de análisis cuando el dato concreto es
imposible, contradictorio o está ausente.

Recomendación:

**Adoptar la base de 1344 manos como registro canónico con excepción de
procedencia y limitaciones de campo; no adoptarla como base de calibración
validada ni regenerar derivados.**

La adopción propuesta es de **registro**. No certifica que las 98 correcciones
sean reproducibles, no certifica todos los botes y no autoriza reanclar la
ventana de 877. Si «adoptar» significa dejar validados la calibración y los
derivados en el mismo acto, la respuesta sigue siendo **no adoptar todavía**.

### 1.1 Qué cambia respecto de la propuesta anterior

La propuesta anterior trataba las 57 manos de la ventana, las 35 manos con bote
`NADA` y las 9 de riesgo alto como bloques de exclusión. Esta revisión separa
las dimensiones y corrige ese alcance:

- Las **57 manos de la ventana** no se excluyen por haber sido modificadas. Solo
  se encontró un defecto de secuencia en ese lote: `H_0926`, que ya existía en
  `8b44917`; `44acddb` no lo introdujo, pero tampoco lo corrigió.
- Las **23 manos nuevas** no se excluyen por clasificación de evidencia. Se
  encontraron dos secuencias imposibles, `H_1287` y `H_1310`, que además son
  anteriores a `44acddb`; y limitaciones de bote/auditoría en `H_1300` y
  `H_1311`.
- Las **35 manos `NADA`** se limitan solo en cálculos que necesiten el bote, el
  EV, el ROI o las pot odds. No se excluyen del registro ni de las acciones.
- Las **9 manos de riesgo alto** no se excluyen por riesgo. `H_1289`, `H_1293`,
  `H_1313` y `H_1324` no mostraron defecto real en las comprobaciones aplicadas.
  `H_1283` tiene una discrepancia de texto de showdown, no de ganador.
- `H_1304` no tiene stack recuperable; `H_1349` sí tiene un candidato
  documentado de 45.9. B1-R confirma su `final_pot` actual de 19.7; la
  resolución intermedia de 10.7 no se usa para corregirlo.
- La eliminación de `H_1323` sigue aceptada y no deja referencias activas ni
  decisiones huérfanas.

### 1.2 Resumen de evidencia

| Elemento | Resultado |
|---|---|
| Cambios semánticos de `44acddb` | 98: 75 manos antiguas y 23 del bloque `H_1283`–`H_1327` |
| Dentro de la ventana de 877 | 57; fuera 41 |
| Evidencia de procedencia de las 98 | 84 G, 11 T, 3 U; ninguna V para el paso `44acddb` |
| Manos de B1-R | 23, contenido final verificado; solo `H_1143` coincide con las 98 |
| Importaciones 45 + 47 | 92 manos, fuera de la ventana; 35 con bote `NADA`; 2 con stack activo nulo |
| B1-R | Veredicto B, cerrado; 9 de sus 23 manos tienen bote `NADA` |
| `H_1323` | Eliminación aceptada; sin referencias activas ni decisiones |
| Defecto de secuencia en las 57 | 1: `H_0926`, preexistente; `44acddb` no lo corrigió |
| Defectos de secuencia en las 23 nuevas | 2: `H_1287` y `H_1310`, ambos preexistentes |

## 2. Criterios y dimensiones separadas

### 2.1 Cuatro dimensiones

| Dimensión | Pregunta | No se mezcla con |
|---|---|---|
| **Procedencia** | ¿De qué commit, sesión o intervención viene? | Calidad del contenido |
| **Exactitud** | ¿Se puede reproducir el cambio con un artefacto versionado? | Legalidad de la mano |
| **Integridad** | ¿La secuencia, el tablero, el ganador y los importes son posibles y coherentes? | Historia de la modificación |
| **Aptitud analítica** | ¿Para qué análisis sirve el campo tal como está? | Valoración global de la mano |

### 2.2 Reglas aplicadas

- Una modificación histórica no es un defecto.
- La ausencia de un script reproductor no es un defecto de contenido.
- La ausencia de documentación individual no es un defecto de contenido.
- Una mención genérica en un documento no es verificación visual.
- `PARTICION_FASE_D.md` es una partición operativa, no evidencia.
- Si una mano tiene un defecto localizado, se excluye el campo o el análisis
  afectado, no la mano completa, salvo que la secuencia entera deje de ser
  interpretable.
- Los niveles V/T/G/U/R de B1-R describen **procedencia**, no integridad.

### 2.3 Niveles de procedencia usados solo como procedencia

| Código | Significado |
|---|---|
| **V** | Verificación visual contra grabación |
| **T** | Evidencia técnica o documental específica |
| **G** | Patrón genérico o normalización sistemática |
| **U** | Procedencia desconocida; solo consistencia estructural |
| **R** | Dudoso o potencialmente incorrecto |

Estos niveles no se usan para decidir si una mano entra o no. Se usan para
describir qué se sabe de su origen.

## 3. Los 98 cambios de `44acddb`

### 3.1 Composición

`44acddb` modifica 119 manos existentes. De ellas, 98 cambian la secuencia de
acciones. Las otras 21 solo cambian campos no accionales.

| Grupo | Manos | Ventana | Evidencia de procedencia |
|---|---:|---:|---|
| Manos antiguas | 75 | 57 dentro / 18 fuera | 75 G |
| Bloque nuevo `H_1283`–`H_1327` | 23 | 0 dentro / 23 fuera | 11 T, 9 G, 3 U |
| **Total** | **98** | **57 dentro / 41 fuera** | **84 G, 11 T, 3 U** |

Campos modificados: `streets` en 98; `recorder_audit` en 23; `final_pot` en 22;
`winner` en 13; `players` en 8; `showdown` en 1.

Ninguna de las 98 está entre las 23 exclusiones CM-004 de la ventana.

### 3.2 Las 75 manos antiguas: checks y un defecto real

Las 75 manos antiguas tienen un patrón uniforme:

- 144 acciones modificadas, todas `x` (check);
- 128 checks eliminados, todos con `inferred: false`;
- 16 checks añadidos, todos con `inferred: true`;
- ninguna acción `f`, `c`, `r`, `b` o `p` cambia;
- ningún campo distinto de `streets` cambia;
- no hay script versionado que reproduzca el lote.

Eso describe una normalización sistemática de checks, no una verificación visual.
Pero la integridad actual no se decide por el patrón: se decide por la secuencia
resultante.

**Resultado de integridad:** de las 75, **solo `H_0926` tiene un defecto de
secuencia; no lo introdujo `44acddb`, ya estaba en `8b44917`.**

| Mano | Hecho histórico | Estado actual | Defecto |
|---|---|---|---|
| `H_0926` | En `8b44917` ya aparece `SB x` al inicio del turn, después de que `SB` se retiró en el flop. `44acddb` añade un `BB x` legal antes de `UTG b`, pero no retira el `SB x`. | `SB` se retiró en el flop y después aparece checkeando en el turn. | Acción de un jugador ya retirado; secuencia imposible. |

`H_0926` está dentro de la ventana de 877. Es el único defecto de secuencia en
las 57, pero es **preexistente**: el cambio de `44acddb` en esa mano (añadir
`BB x`) es legal y no crea el defecto; el defecto es el `SB x` que ya estaba y
que el cambio no eliminó. La corrección mínima sería retirar el `SB x`, no el
`BB x`. No se excluye la mano completa del registro; se excluye su secuencia de
acciones y, por tanto, su uso en frecuencias y calibración hasta que se corrija
o se elimine el campo.

Las otras 74 manos antiguas no muestran un defecto de secuencia en las
comprobaciones aplicadas. Eso no las convierte en verificadas visualmente: siguen
siendo procedencia G. Pero no hay motivo de integridad para excluirlas.

Limitaciones de campo en este lote:

| Mano | Campo | Qué pasa | Análisis afectado |
|---|---|---|---|
| `H_0832` | `preflop.actions[2]` | `CO b 1.0` con BB en 1.0; es un limp/call codificado como apuesta, no una subida. | Frecuencias de agresión preflop. |
| `H_0430`, `H_0589`, `H_0662`, `H_0847` | `comunitarias` | Es un resumen truncado; el board completo está en `streets.*.board`. No es una contradicción de acciones. | Análisis que lean `comunitarias` en vez de `streets.*.board`. |
| `H_0136` | `players[5].pos` | `Juanfelipe1` está activo sin posición y sin acciones. | Estado/asiento del jugador; no la secuencia. |
| `H_1140` | `comunitarias` | Igual que el grupo anterior, fuera de la ventana. | Board/equity basado en `comunitarias`. |

`H_0589` **no** tiene un defecto de undercall: su `BB c 5.9` es un aporte
parcial sobre la ciega de 1.0 para llegar a 6.9. La aritmética de botes ya
contempla lectura parcial. No se incluye como defecto de secuencia.

### 3.3 Las 23 manos nuevas: integridad real, no clasificación de evidencia

Las 23 están fuera de la ventana actual. No se excluyen por ser G/T/U ni por
tener bote `NADA`. Se evalúan por lo que realmente contienen.

| Mano | Defecto real o limitación | Campo exacto | Tratamiento |
|---|---|---|---|
| `H_1283` | No hay defecto de acciones ni de ganador. El reparto es split: SB y BB empatan con dos pares J/4 y kicker T. `winner` incluye a ambos; `showdown.winner1` solo nombra a SB. | `showdown.winner1` | Limitar el texto de showdown; usar `winner` y las cartas. Bote `NADA` solo para cálculos de bote. |
| `H_1284` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1285` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1287` | `CO c 1.0` con apuesta viva 6.0 y stack 20.0; no es all-in corto. Después `CO f 0.0` después de `SB c 6.0`, sin nueva apuesta. | `preflop.actions[4]` y `preflop.actions[8]` | Excluir secuencia preflop, frecuencias y bote/EV de esta mano. |
| `H_1289` | Sin defecto real detectado en acciones, ganador ni tablero. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1292` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1293` | Sin defecto real detectado. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1298` | Sin defecto de acciones detectado. `final_pot` 67.2 no coincide con `recorder_audit.pot_calculated` 33.5. | `final_pot` | Limitar bote/EV/ROI. |
| `H_1300` | No se detectó secuencia imposible. Pero `recorder_audit.ambiguities[4].pos = "SB"` y la mano no tiene SB; `final_pot` 180.1 frente a `pot_calculated` 181.1. | `recorder_audit`, `final_pot` | Limitar bote/auditoría; no restringir la secuencia por este campo. |
| `H_1305` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1306` | Sin defecto de acciones detectado. `final_pot` 24.3 frente a `pot_calculated` 8.9. | `final_pot` | Limitar bote/EV/ROI. |
| `H_1310` | `SB c 1.0` con apuesta viva 3.0 y stack 92.4; después `SB c 3.0`. En flop `SB c 4.3` y `SB c 4.4`: llamadas duplicadas sin nueva apuesta. | `preflop.actions[4]`, `preflop.actions[6]`, `flop.actions[3]`, `flop.actions[5]` | Excluir secuencia, frecuencias y bote/EV de esta mano. |
| `H_1311` | Sin secuencia imposible detectada. `final_pot` 58.5 frente a `pot_calculated` 55.4. | `final_pot` | Limitar bote/EV/ROI. |
| `H_1312` | Sin defecto de acciones detectado. `final_pot` 4.0 frente a `pot_calculated` 4.5. | `final_pot` | Limitar bote/EV/ROI. |
| `H_1313` | Sin defecto real detectado. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1315` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1317` | Sin defecto de acciones detectado. `final_pot` 3.0 frente a `pot_calculated` 2.0. | `final_pot` | Limitar bote/EV/ROI. |
| `H_1318` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1320` | Sin defecto real detectado. | — | Sin restricción de integridad. |
| `H_1322` | Sin defecto real detectado. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1324` | El fold añadido es legal: `SB x`, `UTG b 7.7`, `BTN f`, `SB f`. No hay defecto de secuencia. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1325` | Sin defecto real detectado. | — | Bote `NADA`: limitar bote/EV/ROI. |
| `H_1327` | Sin defecto real detectado. | — | Bote `NADA`: limitar bote/EV/ROI. |

**Conclusión de las 23:** `H_1287` y `H_1310` tienen secuencias imposibles.
`H_1283` tiene un texto de showdown incompleto, no un ganador incorrecto.
`H_1300` y `H_1311` tienen campos de bote/auditoría no reconciliados. Las demás
no muestran un defecto real en las comprobaciones aplicadas; las que están en
`NADA` solo quedan limitadas para cálculos de bote.

### 3.4 Las 57 manos de la ventana: validez por secuencia, no por procedencia

La ventana de 877 contiene 57 de las 98. La revisión no las excluye en bloque.
El resultado es:

| Mano | Situación | Efecto en la ventana |
|---|---|---|
| `H_0926` | `SB x` en turn después de `SB f` en flop; preexistente en `8b44917`; `44acddb` no lo corrigió. | No usar su secuencia para frecuencias/calibración hasta corregir o excluir la acción. |
| `H_0832` | `CO b 1.0` preflop con BB en 1.0; limp codificado como apuesta. | No contar ese `b` como subida en frecuencias preflop. |
| `H_0430`, `H_0589`, `H_0662`, `H_0847` | `comunitarias` truncada; `streets.*.board` conserva el board completo. | Limitar análisis que lean `comunitarias`; no hay defecto de acciones. |
| `H_0136` | Jugador activo sin posición y sin acciones. | Limitar estado/asiento; no la secuencia. |
| Las otras 50 | Sin defecto de secuencia detectado en las comprobaciones aplicadas. | No se excluyen por procedencia. |

**La ventana 877 no queda validada como conjunto**, pero no por las 57
modificaciones en bloque: queda provisional porque `H_0926` tiene una acción
imposible y porque hay limitaciones de campo en `H_0832` y en el board truncado.
La calibración de frecuencias puede plantearse solo después de corregir o
excluir la acción de `H_0926` y de tratar `H_0832` como limp, no como subida.
La calibración que dependa del bote sigue bloqueada por los `NADA`.

### 3.5 Las 9 manos de riesgo alto: el riesgo no sustituye al defecto

| Mano | Defecto real encontrado | Restricción |
|---|---|---|
| `H_1283` | Reparto split; `showdown` solo nombra a SB. | Texto de showdown; no el ganador. Bote `NADA`. |
| `H_1287` | Secuencia preflop imposible. | Acciones, frecuencias y bote/EV. |
| `H_1289` | Sin defecto real detectado. | Bote `NADA`. |
| `H_1293` | Sin defecto real detectado. | Bote `NADA`. |
| `H_1300` | `recorder_audit` referencia SB inexistente; bote no reconciliado. | Bote/auditoría. |
| `H_1310` | Llamadas duplicadas en preflop y flop. | Acciones, frecuencias y bote/EV. |
| `H_1311` | Sin secuencia imposible; bote no reconciliado. | Bote/EV. |
| `H_1313` | Sin defecto real detectado. | Bote `NADA`. |
| `H_1324` | Sin defecto real detectado; el fold añadido es legal. | Bote `NADA`. |

## 4. Defectos reales fuera de los 98

La base completa de 1344 conserva defectos que no nacen de `44acddb`. Se
registran para que la adopción del registro no los oculte. El detalle exacto
está en `DOCS/B1_EXCEPCION_INVENTARIO.json`.

### 4.1 Secuencias imposibles

Además de `H_0926`, `H_1287` y `H_1310`, hay diez manos antiguas con una acción
que no puede ocurrir en una secuencia de póker según las comprobaciones
aplicadas. No es un barrido visual exhaustivo de las 1344:

`H_0005`, `H_0059`, `H_0214`, `H_0226`, `H_0327`, `H_0357`, `H_0834`,
`H_0925`, `H_0946`, `H_1141`.

Ejemplos exactos:

| Mano | Campo | Hecho |
|---|---|---|
| `H_0005` | `turn.actions[4]` | `MP b 13.0` después de `MP x 0.0` en la misma calle, sin nueva apuesta. |
| `H_0059` | `preflop.actions[6]` | `BTN c 2.5` después de que SB y BB se retiran; no queda rival ni apuesta viva. |
| `H_0214` | `turn.actions[2]` | `BB b 1.0` después de `BB x 0.0` en la misma calle. |
| `H_0226` | `river.actions[2]` | `SB c 4.9` después de que MP se retira; no hay apuesta que igualar. |
| `H_0327` | `river.actions[2]` | `MP b 0.0`: apuesta de importe cero, sin all-in. |
| `H_0357` | `preflop.actions[2]` | `BB b 0.5` después de `BB p 1.0`; no supera la ciega y el jugador actúa dos veces. |
| `H_0834` | `preflop.actions[5]` | `BTN r 4.0` después de `BTN b 1.0` y dos folds, sin nueva apuesta. |
| `H_0925` | `river.actions[4]` | `MP f 0.0` después de `MP c 9.0`, sin nueva apuesta. |
| `H_0946` | `flop.actions[3]` | `UTG x 0.0` enfrentando `MP b 7.1`. |
| `H_1141` | `preflop.actions[4]` | `SB x 0.0` enfrentando la ciega BB de 1.0. |

Estas manos se conservan en el registro. Se excluye su secuencia de acciones de
los análisis que la usen; no se excluyen por procedencia.

### 4.2 Orden o codificación de acción

| Mano | Campo | Hecho | Análisis afectado |
|---|---|---|---|
| `H_0832` | `preflop.actions[2]` | `CO b 1.0` con BB en 1.0; limp codificado como apuesta. | Frecuencias de agresión preflop. |
| `H_1328` | `flop.actions[0]` | `BB b 1.4` antes de `SB x 0.0`; falta la acción de SB antes de la apuesta o el orden está desplazado. | Orden y frecuencias postflop. |
| `H_1354` | `turn.actions[1]` | `BB b 1.0` con apuesta viva 1.0; no es subida. | Frecuencias de subida en turn. |
| `H_1300` | `recorder_audit.ambiguities[4]` | Referencia `SB` inexistente en una mesa sin SB. | Auditoría de bote, no la secuencia. |

`H_1328` y `H_1354` pertenecen a B1-R. B1-R sigue cerrado y no se reabre. Estas
observaciones son de campos que su alcance no cubrió: orden de flop, board de
river y código/importe de una acción. No cambian el veredicto de procedencia.
En `H_1328`, B1-R confirma el `final_pot` actual de 21.7; la captura y la
resolución intermedia de 8.2/8.3 no se usan como verdad final.

### 4.3 Contradicciones de tablero

| Mano | Campo | Contradicción |
|---|---|---|
| `H_0093` | `comunitarias.flop` | `Js 2c 2c` (2c duplicada) frente a `streets.flop` `Js 2c 2d`. |
| `H_0297` | `comunitarias.turn` | `As` frente a `streets.turn` `Ah`. |
| `H_0812` | `comunitarias.flop` | `2s 6c 2s` (2s duplicada) frente a `streets.flop` `2s 6c Td`. |
| `H_0915` | `comunitarias.flop` | `As 6s 2s` frente a `streets.flop` `As 6s 6c`. |
| `H_0921` | `comunitarias.river` | `2s` frente a `streets.river` `9c`. |

### 4.4 Tableros ausentes con acciones

| Mano | Campo | Qué falta |
|---|---|---|
| `H_0372` | `river.board` | Hay `river.actions` y el board está vacío. |
| `H_0587` | `turn.board`, `river.board` | Hay acciones en turn y river; ambos boards vacíos. |
| `H_0590` | `river.board` | Hay acciones en river; board vacío; `comunitarias` también vacía. |
| `H_0909` | `river.board` | Hay acciones en river; board vacío. |
| `H_1008` | `flop.board` | El board está en `preflop.board` (`8c Qs Js`) y `flop.board` está vacío. |
| `H_1328` | `river.board` | Hay acciones en river; board vacío. |

Estos campos impiden calcular equity o evaluar el showdown con el board
completo. Las acciones pueden seguir siendo legibles; el tablero no.

### 4.5 `comunitarias` truncada: representación conocida, no defecto de acción

Hay 45 manos en las que `comunitarias` es un prefijo del board de
`streets.*.board`. `AUDITORIA_FRONTES.md` ya describe este patrón: el resumen
está truncado y el board completo está en `streets`. No es una contradicción y
no se cuenta como defecto de acciones. Sí limita cualquier análisis que lea
`comunitarias` en vez de `streets.*.board`.

### 4.6 Bote: `NADA` y conflictos internos

`aritmetica_botes.py` clasifica 35 manos actuales como `NADA`: el bote declarado
no sale con ninguna combinación de lectura absoluta/parcial, con o sin comisión,
ni con o sin la ciega del SB. Es una falta de reconciliación aritmética, no una
prueba de que la mano entera esté mal.

Las 35 son:

`H_1283`, `H_1287`, `H_1288`, `H_1289`, `H_1293`, `H_1295`, `H_1296`,
`H_1298`, `H_1300`, `H_1301`, `H_1302`, `H_1310`, `H_1311`, `H_1313`,
`H_1322`, `H_1324`, `H_1325`, `H_1327`, `H_1343`, `H_1344`, `H_1345`,
`H_1346`, `H_1348`, `H_1349`, `H_1351`, `H_1355`, `H_1356`, `H_1357`,
`H_1358`, `H_1361`, `H_1365`, `H_1368`, `H_1371`, `H_1372`, `H_1374`.

Además, 17 manos tienen `final_pot` distinto de
`recorder_audit.pot_calculated` en más de 0.2:

`H_1298`, `H_1300`, `H_1303`, `H_1306`, `H_1311`, `H_1312`, `H_1317`,
`H_1328`, `H_1330`, `H_1341`, `H_1346`, `H_1349`, `H_1350`, `H_1353`,
`H_1365`, `H_1368`, `H_1369`.

Este conflicto **no autoriza a declarar incorrecto el `final_pot`** por sí solo.
Diez de esas manos son de B1-R (`H_1303`, `H_1328`, `H_1341`, `H_1346`,
`H_1349`, `H_1350`, `H_1353`, `H_1365`, `H_1368`, `H_1369`). En ellas la
revisión humana confirma el `final_pot` actual y el lado obsoleto es
`recorder_audit.pot_*` o una captura intermedia. No se reabre B1-R y no se usa
ese conflicto para corregir el importe: solo se limita el uso de
`recorder_audit.pot_*`. Que B1-R confirme el `final_pot` de una mano no levanta
su clasificación `NADA`: `NADA` mide si la aritmética se puede reconstruir, no
solo si el valor final fue visto en la grabación. Por eso `H_1349`, `H_1365` y
`H_1368` siguen limitadas para EV/ROI aunque su `final_pot` actual esté
confirmado.

Las siete restantes no tienen verificación B1-R: `H_1298`, `H_1300`, `H_1306`,
`H_1311`, `H_1312`, `H_1317`, `H_1330`. Cuatro de ellas no estaban ya en `NADA`:
`H_1306`, `H_1312`, `H_1317`, `H_1330`. Por tanto, el conjunto de bote no
confiable para EV, ROI, pot odds o resultado económico es **35 `NADA` + 4 = 39
manos**. El detalle de los 17 conflictos internos, con `pot_read` y `uncalled`,
está en el inventario.

### 4.7 Marcas `allin` ausentes

Hay 23 manos en las que un jugador agota su stack pero no queda marcado en
`allin` para ese jugador:

`H_0006`, `H_0008`, `H_0022`, `H_0034`, `H_0036`, `H_0055`, `H_0058`,
`H_0070`, `H_0145`, `H_0185`, `H_0293`, `H_0311`, `H_0321`, `H_0383`,
`H_0441`, `H_0713`, `H_0883`, `H_0906`, `H_0963`, `H_1112`, `H_1118`,
`H_1231`, `H_1365`.

No impide reconstruir el all-in desde el stack y los aportes, pero invalida
cualquier análisis que dependa directamente del campo `allin`. La clase
`SIN_ALLIN` de la auditoría antigua no es equivalente: incluye manos sin
all-in real y no todas las de esta lista.

### 4.8 Stacks nulos

Hay 25 jugadores activos con `stack: null` en 25 manos:

`H_0016`, `H_0022`, `H_0061`, `H_0198`, `H_0415`, `H_0421`, `H_0430`,
`H_0515`, `H_0526`, `H_0547`, `H_0557`, `H_0697`, `H_0824`, `H_0834`,
`H_0853`, `H_0863`, `H_0906`, `H_0932`, `H_1076`, `H_1096`, `H_1113`,
`H_1141`, `H_1149`, `H_1304`, `H_1349`.

- `H_1304` (`Tonytruco`, BTN): `decisions.jsonl` mantiene `p5` en `null`; no
  hay valor recuperable.
- `H_1349` (`LaloMora`, UTG): en la segunda decisión, `p5` vale 44.9 y tiene
  `bets.p5 = 1.0`; `p2` pasa de 206.3 a 205.3 tras aportar 1.0. Eso permite
  derivar un stack inicial de **45.9**. No se escribe en la base: es un valor
  derivado, no canónico. B1-R confirma el `final_pot` actual de 19.7; la
  resolución intermedia de 10.7 no se usa para corregirlo. El bote sigue en
  `NADA` y queda limitado para cálculos de bote.

### 4.9 Jugadores activos sin posición

Hay 61 jugadores activos sin `pos` en 55 manos. En la mayoría no actúan; el
efecto es de estado/asiento y de composición de la mesa, no de secuencia. No se
excluyen manos por este campo. El listado exacto está en el inventario.

### 4.10 Showdown: texto incompleto en splits

Cuatro manos tienen un split cuyo `winner` es correcto pero cuyo texto
`showdown` solo nombra a uno de los ganadores:

`H_0798`, `H_1283`, `H_1337`, `H_1342`.

En `H_1283`, las cartas lo confirman: SB `Jd5s` y BB `Jc8c` sobre
`Tc 6h Js 4d 4c` comparten dos pares J/4 con kicker T. El ganador
`["p2","p3"]` es correcto; el texto `winner1: SB` es incompleto. No se excluye
la mano ni se corrige el ganador.

## 5. Matriz de defectos reales y evidencia

| Defecto | Manos | Campo exacto | Evidencia | Análisis afectado | Tratamiento |
|---|---:|---|---|---|---|
| Secuencia imposible | 13 | `streets.<calle>.actions[...]` | Acción después de fold, check enfrentando apuesta, llamada duplicada, apuesta 0 o acción tras cierre de mano | Secuencia, frecuencias, calibración | Excluir la secuencia de esas manos; no la mano completa del registro |
| Orden/codificación de acción | 3 | `H_0832` preflop; `H_1328` flop; `H_1354` turn | `b` igual a la ciega, orden BB-SB, `b` igual a apuesta viva | Frecuencias/orden | Limitar el campo o la frecuencia concreta |
| `recorder_audit` inválido | 1 | `H_1300.recorder_audit.ambiguities[4]` | Referencia a `SB` inexistente | Auditoría de bote | No usar ese campo |
| Contradicción de tablero | 5 | `comunitarias`/`streets` | Carta distinta o duplicada | Board/equity/showdown | Excluir board/equity de esas manos |
| Tablero ausente con acciones | 6 | `river.board`, `turn.board`, `flop.board` | Acciones sin carta | Board/equity/showdown | Excluir board/equity de esas manos |
| `comunitarias` truncada | 45 | `comunitarias` | Prefijo del board de `streets` | Solo análisis que lean `comunitarias` | Usar `streets.*.board`; no es defecto de acciones |
| Bote `NADA` | 35 | `final_pot`/bote | Ninguna lectura reproduce el bote | EV/ROI/pot odds | Limitar bote |
| Conflicto interno de bote | 17 | `final_pot` vs `recorder_audit.pot_calculated` | Diferencia >0.2 | EV/ROI/pot odds | En 10 B1-R el `final_pot` está verificado y el `recorder_audit` es obsoleto; en 7 no B1-R, 4 se suman al bote no confiable |
| Bote no confiable | 39 | `final_pot`/bote | 35 `NADA` + 4 conflictos no B1-R | EV/ROI/pot odds/resultado económico | Limitar bote |
| `allin` no marcado | 23 | `allin` | Stack agotado sin marca | Análisis que usen `allin` | Derivar del stack; no usar el campo |
| Stack nulo | 25 | `players[].stack` | `null` con `active: true` | Stack efectivo/SPR | Limitar; `H_1349` admite 45.9 derivado |
| Activo sin posición | 55 manos / 61 jugadores | `players[].pos` | `active: true` sin `pos` | Estado/asiento | Limitar; no excluir la mano |
| Texto de showdown incompleto | 4 | `showdown` | Split con un solo nombre | Texto de showdown | Usar `winner` y cartas |

## 6. Matriz de aptitud por análisis

| Análisis | Base permitida | Restricciones | Manos/campos excluidos |
|---|---|---|---|
| Secuencia de acciones | 1344 como registro | Excluir las 13 secuencias imposibles y las 3 discrepancias de orden/código | `H_0005`, `H_0059`, `H_0214`, `H_0226`, `H_0327`, `H_0357`, `H_0834`, `H_0925`, `H_0926`, `H_0946`, `H_1141`, `H_1287`, `H_1310`, `H_0832` (solo preflop), `H_1328` (flop), `H_1354` (turn) |
| Frecuencias preflop | Base menos restricciones | `H_0832` no cuenta `b 1.0` como subida; `H_0926` no afecta preflop | `H_0832`; secuencias imposibles |
| Frecuencias postflop | Base menos restricciones | `H_0926` fuera; `H_1328` flop fuera; `H_1354` turn fuera | `H_0926`, `H_1328`, `H_1354`; secuencias imposibles |
| Board/equity | `streets.*.board` cuando esté completo | No usar `comunitarias` truncada; excluir contradicciones y boards ausentes | `H_0093`, `H_0297`, `H_0812`, `H_0915`, `H_0921`, `H_0372`, `H_0587`, `H_0590`, `H_0909`, `H_1008`, `H_1328` |
| Showdown/ganador | `winner` y cartas | Usar `winner`, no el texto incompleto de split | `H_0798`, `H_1283`, `H_1337`, `H_1342` solo para el texto |
| Bote/EV/ROI/pot odds | Base menos restricciones | 35 `NADA` + 4 conflictos internos no B1-R; 10 B1-R solo limitan `recorder_audit.pot_*` | Unión de 39 manos; ver §4.6 |
| Stack efectivo/SPR | Base con stacks no nulos | 25 stacks nulos; `H_1349` solo con 45.9 derivado; `H_1304` no recuperable | 25 manos; `H_1304`, `H_1349` |
| `allin` | Base con marcas completas | 23 sin marca para el jugador que agota stack | Ver §4.7 |
| Estado/asiento | Base con posición | 55 manos con activo sin posición | Ver §4.9 |
| Calibración 877 | Ventana provisional | No validada como conjunto; `H_0926` fuera de frecuencias; `H_0832` limp; board truncado; bote bloqueado | `H_0926`, `H_0832`, `H_0430`, `H_0589`, `H_0662`, `H_0847`; bote 35/39 |
| Registro completo / procedencia | 1344 | Excepción B documentada; no reproducibilidad | Ninguna mano excluida por procedencia |
| Derivados canónicos | Bloqueados | No reanclar, no regenerar, no actualizar pins | Sujeto a autorización humana |

## 7. Nueva propuesta de adopción de la base de 1344

### 7.1 Propuesta

1. **Adoptar `data/hands_db.jsonl` de 1344 líneas como registro canónico** con
   la excepción de procedencia B ya documentada.
2. **No excluir ninguna mano por procedencia, historia de modificación,
   ausencia de script o ausencia de documento individual.** La única mano ya
   eliminada sigue siendo `H_1323`.
3. **Aplicar exclusiones de campo/análisis**, no de mano completa, según §5 y
   §6. La base no se reescribe en este acto.
4. **No declarar reproducibilidad.** Las 98 correcciones de `44acddb` no tienen
   un procedimiento exacto versionado; las importaciones son bloques de sesión.
5. **No reanclar ni regenerar derivados canónicos, pins, hashes o manifiesto**
   en este acto.
6. **Mantener la ventana de 877 como provisional.** No es una ventana validada:
   contiene el defecto de `H_0926` y limitaciones de campo.
7. **Mantener `MULTIWAY_SOPORTADO=False`.** No iniciar B2 ni ejecutar sesiones
   reales con esta base como si estuviera plenamente validada.

### 7.2 Qué se adopta y qué no

| Objeto | Decisión propuesta |
|---|---|
| Registro de 1344 manos | Adoptado como registro canónico con excepción B |
| Contenido de las 23 de B1-R | Verificado en su estado final; no atribuido al paso `44acddb` |
| Las 75 manos antiguas | Aceptadas como registro; no verificadas visualmente; solo `H_0926` con defecto de secuencia preexistente |
| Las 23 nuevas | Aceptadas como registro; `H_1287`/`H_1310` con secuencia limitada; `H_1300`/`H_1311` con bote/auditoría limitados |
| Ventana 877 | Provisional; no validada como conjunto |
| Botes `NADA` | No usar para EV/ROI/pot odds |
| Stacks nulos | No usar para stack efectivo/SPR; `H_1349` admite 45.9 derivado |
| Derivados/pines/manifiesto | Sin cambios en este acto |
| B2 y sesiones reales | Bloqueados |

### 7.3 Exclusiones justificadas, por campo

- **Secuencia de acciones:** las 13 manos de §4.1, más `H_0832` (solo
  preflop), `H_1328` (flop) y `H_1354` (turn).
- **Bote/EV/ROI/pot odds:** unión de 39 manos de §4.6; no se excluyen sus
  acciones. En las 10 manos B1-R con conflicto interno solo se limita
  `recorder_audit.pot_*`, no el `final_pot` verificado.
- **Board/equity:** 5 contradicciones y 6 tableros ausentes de §4.3 y §4.4.
  `comunitarias` truncada no se trata como defecto; se usa `streets.*.board`.
- **Stack efectivo/SPR:** 25 stacks nulos de §4.8; `H_1304` no recuperable;
  `H_1349` solo con 45.9 derivado.
- **`allin`:** 23 manos de §4.7; derivar del stack si el análisis lo necesita.
- **Estado/asiento:** 55 manos de §4.9; no afecta la secuencia.
- **Texto de showdown:** 4 splits de §4.10; el ganador no se excluye.

### 7.4 Condiciones

1. No actualizar el manifiesto de `motor/learn.py`, los pines ni los hashes
   canónicos.
2. No sustituir los derivados canónicos ni reanclar la ventana de calibración.
3. No declarar las 98 correcciones como verificadas visualmente.
4. No declarar la base como reproducible.
5. No usar la ventana de 877 como calibración validada mientras `H_0926` no se
   corrija o se excluya su acción, y mientras no se trate `H_0832` como limp.
6. No usar las 39 manos de bote no confiable para EV, ROI, pot odds ni resultado
   económico. En las 10 manos B1-R con `recorder_audit` obsoleto, el
   `final_pot` verificado no se corrige; solo se evita ese campo de auditoría.
7. No usar `H_1304` para análisis de stack; `H_1349` solo con el valor derivado
   documentado.
8. Mantener `MULTIWAY_SOPORTADO=False`.
9. No iniciar B2 ni ejecutar sesiones reales con esta base como si estuviera
   plenamente validada.

## 8. `H_1323`, decisiones y referencias

- `H_1323` fue eliminada en `8594ed5` y archivada en
  `data/_eliminadas/H_1323.jsonl`; el archivo coincide con el backup previo.
- No está en la base actual.
- No hay referencias activas en tests, fixtures, decisiones ni código.
- `data/decisions.jsonl` tiene 506 filas y 91 `hand_id` no nulos; los 91 existen
  en la base actual. Hay 3 filas con `hand_id: null`, no relacionadas con
  `H_1323`.
- La eliminación no deja decisiones huérfanas.

## 9. Recomendación final

**Adoptar la base de 1344 como registro canónico con excepción de procedencia y
limitaciones de campo.**

No se recomienda la adopción plena como base de calibración validada. La
diferencia es decisiva:

- **Registro:** sí, con el ledger de §5 y las restricciones de §6.
- **Calibración/derivados:** no, mientras `H_0926` no se corrija o se excluya y
  mientras los botes no reconciliados sigan fuera de los cálculos.
- **Reproducibilidad:** no demostrada; no se afirma.

Este documento termina aquí. No concede la excepción, no modifica la base y no
inicia B2. La autorización humana es el siguiente paso.
