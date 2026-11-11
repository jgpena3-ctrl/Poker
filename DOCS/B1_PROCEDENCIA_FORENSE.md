# B1-R — Procedencia forense de la base canónica

**Fecha:** 2026-11-11
**Estado:** cierre documental de B1-R. Revisión humana de las 23 manos
completada.
**Base auditada:** `data/hands_db.jsonl`, 1344 líneas, SHA-256
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.
**Commit que introdujo el blob:** `8594ed5`.
**Punto de control anterior:** `aa3fb73` (`B1_CHECKPOINT_2026-11-10.md`).

## 1. Veredicto

**Veredicto B, con excepción de procedencia explícita y alcance limitado.**

La base actual **no es reproducible exactamente** con los procedimientos
versionados. Sin embargo, la revisión visual humana de las 23 manos
investigadas concluyó que **las 23 versiones actuales coinciden con las
grabaciones originales** y que **no hay ninguna acción incorrecta** en ellas.

Por tanto:

- **A no aplica:** no existe una cadena de procedimientos identificados que
  reconstruya la base byte a byte.
- **C no aplica a las 23 manos:** no se ha identificado un error de contenido
  que exija reparación. Los dos casos que más lo parecían, `H_1328` y
  `H_1336`, quedaron resueltos por la revisión humana contra la grabación
  original.
- **D no aplica a las 23 manos:** hay evidencia suficiente para certificar su
  contenido, aunque no su procedencia exacta.
- **B sí aplica:** existen correcciones manuales legítimas en cuanto a su
  contenido, pero su reproducción histórica no es posible. La adopción de la
  base requeriría una excepción de procedencia aceptada explícitamente.

La excepción **no está concedida por este documento**. B1-R documenta la
evidencia y emite el veredicto; la adopción, el reanclaje del manifiesto y la
regeneración de derivados canónicos siguen requiriendo autorización posterior.

### 1.1 Tres preguntas distintas

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿El contenido actual es correcto? | **Sí, para las 23 manos revisadas** | Revisión visual humana contra las grabaciones originales, 2026-11-11 |
| ¿Sabemos qué procedimiento exacto produjo cada corrección? | **No** | Ningún script versionado produce los 23 cambios; no hay registro de operación |
| ¿Podemos reproducir la base desde los artefactos versionados? | **No** | La cadena de scripts falla y no cubre las 23 manos |

La conclusión central de B1-R es que **exactitud de datos, procedencia
histórica y reproducibilidad son tres cosas distintas**. Que una mano sea
correcta no demuestra que sepamos cómo se corrigió; que no sepamos cómo se
corrigió no demuestra que esté mal.

## 2. Método y evidencia utilizada

La investigación se hizo sin escribir sobre la base canónica:

- lectura de blobs históricos con `git show <commit>:data/hands_db.jsonl`;
- comparación por mano y por acción, no solo por SHA del archivo;
- inventario de commits que tocan la base;
- lectura de los backups `data/_backup_*/hands_db.jsonl`, ordenados por fecha;
- lectura del estado posterior a la sesión
  `pruebas/recorder/sesiones/sesion_validacion_1_20261104/hands_db_full_after_session.jsonl`;
- lectura del índice de capturas
  `pruebas/recorder/sesiones/ambiguedades/capturas/index.jsonl`;
- lectura de la documentación de correcciones, en especial
  `DOCS/DEFECTO_H1292.md`, `DOCS/AUDITORIA_ESTADO_JUGADORES.md` y
  `DOCS/CANAL_MANUAL_CERRADO.md`;
- revisión visual humana de las 23 manos contra las grabaciones originales,
  comunicada por el mantenedor el 2026-11-11.

Los backups se numeran en este documento de `B01` a `B12` por orden temporal.
`B00` (`data/_backup_aplicar_correcciones`) es un estado antiguo, anterior a
la secuencia que aquí se reconstruye, y no se usa para atribuir las 23
correcciones.

| Clave | Fecha | Archivo |
|---|---|---|
| B01 | 2026-11-04 12:47 | `pruebas/recorder/sesiones/sesion_validacion_1_20261104/hands_db_full_after_session.jsonl` |
| B02 | 2026-11-09 08:06 | `data/_backup_corregir_sesion_20261104/hands_db.jsonl` |
| B03 | 2026-11-09 08:37 | `data/_backup_corregir_mano_H_1333/hands_db.jsonl` |
| B04 | 2026-11-09 11:39 | `data/_backup_corregir_folds_showdown/hands_db.jsonl` |
| B05 | 2026-11-09 12:04 | `data/_backup_limpiar_anotaciones_ruido/hands_db.jsonl` |
| B06 | 2026-11-10 08:55 | `data/_backup_corregir_bote_inflado_fold/hands_db.jsonl` |
| B07 | 2026-11-10 09:53 | `data/_backup_limpiar_notas_inferidas/hands_db.jsonl` |
| B08 | 2026-11-10 10:02 | `data/_backup_corregir_resultados_20261104/hands_db.jsonl` |
| B09 | 2026-11-10 10:13 | `data/_backup_corregir_showdown_posicion/hands_db.jsonl` |
| B10 | 2026-11-10 10:34 | `data/_backup_corregir_resultados_20261029/hands_db.jsonl` |
| B11 | 2026-11-10 12:19 | `data/_backup_eliminar_H_1323/hands_db.jsonl` |
| B12 | 2026-11-10 12:24 | `data/_backup_corregir_anotaciones_20261110/hands_db.jsonl` |

Cada backup se toma **antes** de que el script de su nombre escriba. Por eso,
si una mano ya tiene su estado actual en `Bxx`, el cambio ocurrió antes de ese
script; si aparece en `Bxx+1`, el cambio ocurrió en la ventana en la que se
ejecutó el script `Bxx`. Esa ventana no demuestra por sí sola que el script sea
el autor: hay que comprobar además que su regla pueda producir el cambio.

## 3. Reconstrucción histórica 1253 → 1298 → 1345 → 1344

### 3.1 Estados exactos

| Commit | Fecha | Líneas | Manos únicas | SHA-256 | Papel |
|---|---|---:|---:|---|---|
| `51a6fb9` | 2026-10-25 | 1253 | 1253 | `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09` | Base declarada por el manifiesto; revisión manual H_0001–H_1282 |
| `8b44917` | 2026-10-29 | 1298 | 1298 | `21b14d4d23aaf4636435d1c66aef9355fc22d57d35ae0b011a34b17bf26fc068` | Importa 45 manos nuevas, H_1283–H_1327 |
| `44acddb` | 2026-11-04 | 1298 | 1298 | `4002ca236a850d159d43c6c9b756c3fbafd1d33d208ff1d7605ba89420b58af8` | Corrige 119 manos existentes; no añade ni quita manos |
| `c1c1370` | 2026-11-04 | 1345 | 1345 | `797c85e1408962eb2d6c01aa5bbc3de49502618a2c28305b359a317b9c52f332` | Importa 47 manos nuevas, H_1328–H_1374 |
| `8594ed5` | 2026-11-10 | 1344 | 1344 | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` | Corrige 144 manos, elimina H_1323, añade 11 scripts |
| `1544249` | 2026-11-10 | 1344 | 1344 | `3f0e7e5e...` | Solo documentación de B0; no toca la base |
| `aa3fb73` | 2026-11-10 | 1344 | 1344 | `3f0e7e5e...` | Checkpoint B1; no toca la base |

En todos los estados, **líneas físicas = manos únicas**; no hay IDs duplicados.
La aritmética cierra:

```text
1253 + 45 + 47 - 1 = 1344
```

### 3.2 Qué ocurrió en cada transición

#### 1253 → 1298: `8b44917`, no `44acddb`

El salto de 1253 a 1298 lo produce `8b44917` (“seccion prueba 1”), del
2026-10-29:

- añade exactamente 45 manos, `H_1283`–`H_1327`;
- no modifica ninguna mano existente;
- añade también `data/decisions.jsonl`;
- no incluye ningún script de corrección de `hands_db.jsonl`.

Las 45 manos nuevas tienen fechas de la sesión del 2026-10-29. Es una
**importación de un bloque de sesión**, no una reconstrucción manual de las
manos anteriores.

#### 1298 → 1298: `44acddb`, corrección masiva sin script

`44acddb` (“Corrige recomendaciones, recorder y base hands_db”) **no añade ni
quita manos**. Sin embargo:

- modifica **119 manos existentes**;
- **98** de esas modificaciones cambian la secuencia de acciones
  (posición, acción, cantidad o orden);
- de esas 98, **75** son manos antiguas `H_0*`/`H_1*` y **23** son manos nuevas
  `H_1283`–`H_1327`;
- no incluye ningún script que reejecute las correcciones de la base.

El mensaje del commit y `DOCS/DEFECTO_H1292.md` documentan familias de
corrección: folds fantasma, ganadores múltiples, botes no inflados, checks
faltantes, lecturas de bote y ambigüedades. `DEFECTO_H1292.md` detalla, entre
otras cosas, 29 correcciones de ganador, 10 botes inflados y 45 lecturas de
bote. Pero **no hay un registro por mano que permita reconstruir las 98
secuencias de acciones**. En particular, las 75 manos antiguas no quedan
individualizadas en ese documento.

Por tanto, `44acddb` es una **segunda laguna de procedencia**, anterior a las
23 manos de B1-R. No se ha demostrado que contenga errores; simplemente no se
puede reproducir su procedimiento exacto ni se ha hecho en B1-R una revisión
visual individual de esas 75 manos.

#### 1298 → 1345: `c1c1370`, importación de 47 manos

`c1c1370` (“seccion prueba 2”) añade exactamente 47 manos,
`H_1328`–`H_1374`:

- no modifica ninguna mano existente;
- solo toca `data/hands_db.jsonl` y `data/decisions.jsonl`;
- no incluye scripts;
- las manos nuevas tienen fechas de la sesión del 2026-11-04.

Es una **importación de sesión**, no una corrección manual de la base
preexistente.

#### 1345 → 1344: `8594ed5`, corrección y eliminación

`8594ed5` sí es un commit de corrección:

- elimina **una** mano, `H_1323`, que era un duplicado fantasma de `H_1322`;
- modifica **144** manos existentes;
- **30** de esas modificaciones cambian la secuencia de acciones;
- de esas 30, **7** tienen cobertura por alguno de los 11 scripts
  (`H_1314`, `H_1330`, `H_1333`, `H_1337`, `H_1344`, `H_1355`, `H_1361`);
- **23** no tienen cobertura scriptada: son las manos de B1-R;
- añade los 11 scripts de corrección y cambios de recorder/documentación.

`H_1323` se guarda en `data/_eliminadas/H_1323.jsonl`. El script
`tools/eliminar_mano_H_1323.py` documenta que era una mano fantasma creada al
arrancar el recorder en un frame de resultado: no tenía ganador, su bote era
1.0 y repetía mesa, tablero y stacks de `H_1322`. Su eliminación sí tiene
procedimiento versionado.

### 3.3 Lo que la evidencia permite y lo que no

**Permite afirmar:**

- qué commit introdujo cada bloque de manos;
- cuántas manos se añadieron, quitaron o modificaron;
- qué manos cambiaron semánticamente en cada transición;
- que las 23 manos de B1-R no fueron producidas por los 11 scripts;
- que las 23 versiones actuales coinciden con las grabaciones originales según
  la revisión humana;
- que `H_1323` fue eliminada por un script identificado.

**No permite afirmar:**

- qué operación manual exacta produjo cada una de las 23 correcciones;
- qué operación exacta produjo las 98 correcciones semánticas de `44acddb`;
- que las 75 manos antiguas de `44acddb` hayan sido revisadas visualmente en
  B1-R;
- que la cadena completa de scripts reproduzca la base;
- que el manifiesto o los derivados canónicos deban reanclarse sin una decisión
  posterior.

## 4. Exactitud, procedencia y reproducibilidad de las 23 manos

### 4.1 Revisión humana

La revisión visual humana comparó las 23 versiones actuales con las
grabaciones originales. El resultado comunicado es:

- **23/23 versiones actuales coinciden con la grabación;**
- **ninguna acción actual se identificó como incorrecta.**

Esta es la evidencia de **exactitud de contenido**. No es evidencia de
procedencia: la revisión confirma el resultado, no el camino que llevó a él.

### 4.2 Capturas automáticas versus grabaciones originales

Las capturas versionadas en
`pruebas/recorder/sesiones/ambiguedades/capturas/` son estados intermedios del
recorder, no la verdad final de la mano. Dos casos ilustran por qué no se usan
como autoridad de contenido:

- **`H_1328`:** la captura de turn registra `fold_missing_at_close` y un bote
  de 8.2/8.3; la versión actual continúa hasta river y tiene bote 21.7. La
  revisión humana contra la grabación original confirma la versión actual.
- **`H_1336`:** las capturas de river registran `fold_missing_at_close` y
  discrepancias de bote; la versión actual cambia `SB f` por `SB c 5.0` y
  termina en showdown. La revisión humana contra la grabación original confirma
  la versión actual.

Esto no significa que las capturas sean inútiles: documentan qué dudaba el
recorder y por qué la mano entró en revisión. Significa que **no son la fuente
final** cuando la grabación original dice otra cosa.

### 4.3 Lo que no se puede reconstruir

Para las 23 manos no existe:

- un script versionado que produzca el cambio;
- un log de operación de `hand_editor.py` que identifique la edición;
- un commit intermedio que aísle la corrección;
- una grabación de la edición misma.

Solo existen los estados antes/después y la revisión humana del resultado. Por
eso la procedencia exacta queda en **certeza baja**, aunque la exactitud del
contenido quede en **certeza alta**.

## 5. Registro de las 23 modificaciones

### 5.1 Hechos comunes

- Todas las 23 cambian en `8594ed5` respecto de `c1c1370`.
- Ninguno de los 11 scripts de `8594ed5` produce sus cambios de acciones.
- `H_1143` también había cambiado en `44acddb`.
- `H_1303` fue añadida en `8b44917` y corregida en `8594ed5`.
- `H_1328`–`H_1369` fueron añadidas en `c1c1370` y corregidas en `8594ed5`.
- Todas fueron verificadas visualmente por el humano contra la grabación
  original el 2026-11-11.
- Los cambios de `recorder_audit`, `showdown`, `final_pot` o cartas se indican
  solo cuando acompañan al cambio semántico; no sustituyen la verificación de
  acciones.

### 5.2 Fichas individuales

#### H_1143

- **Antes (`c1c1370`):** preflop `BB x`; flop `BB x` marcado como inferido.
- **Después (HEAD):** preflop `BB f`; sin check de `BB` en flop.
- **Diferencia semántica:** se sustituye un check preflop por fold y se retira
  el check inferido de flop.
- **Otros campos:** sin cambio de bote ni de showdown.
- **Origen:** `44acddb` introdujo dos checks de `BB`; `8594ed5` los sustituyó
  por el estado actual. Ningún script produce este cambio de acciones. Ventana de backups
  B10→B11.
- **Evidencia:** revisión humana; sin captura versionada; estados B10/B11.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar el contenido; registrar como edición manual no
  reproducible. No atribuirla a `hand_editor.py` ni a los scripts.

#### H_1303

- **Antes (`c1c1370`):** turn con `CO r 6.2` inferido; `final_pot` 26.7.
- **Después (HEAD):** se retira la acción duplicada `CO r 6.2`; `final_pot`
  29.0; notas de auditoría actualizadas; showdown de `CO` sin cambios.
- **Diferencia semántica:** eliminación de una acción repetida de turn.
- **Origen:** edición manual en `8594ed5`; ventana B10→B11. El script
  `corregir_anotaciones_20261110.py` **solo ajusta notas y auditoría**: no
  retira acciones ni cambia `final_pot`. Su docstring documenta la corrección,
  pero no la ejecuta.
- **Evidencia:** docstring del script; `DOCS/AUDITORIA_ESTADO_JUGADORES.md`;
  revisión humana; sin captura versionada; B10/B11.
- **Certeza:** contenido alta; procedencia media (corrección manual
  documentada, procedimiento no reproducible).
- **Decisión:** aceptar el contenido; conservar la nota documental; no
  atribuir la eliminación al script de anotaciones.

#### H_1328

- **Antes (`c1c1370`):** turn `CO f` inferido; `final_pot` 8.3. La captura B01
  registra `fold_missing_at_close` en turn.
- **Después (HEAD):** turn `BB x`, `CO x`; river `BB x`, `CO b 3.0`,
  `BB r 11.0`, `CO f`; `final_pot` 21.7.
- **Diferencia semántica:** se reemplaza un cierre por fold en turn por una
  secuencia de checks y apuestas hasta river.
- **Origen:** edición manual entre B01 y B02, antes de ejecutar el primer
  script. Ningún script produce este cambio de acciones; la captura es un estado intermedio.
- **Evidencia:** revisión humana contra la grabación original; captura
  `1:turn:fold_missing_at_close`; B01/B02.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar el contenido; no usar la captura como verdad final;
  mantener documentada la discrepancia entre captura y grabación.

#### H_1336

- **Antes (`c1c1370`):** river `SB b 1.5`, `BB r 5.0`, `SB f`; `final_pot`
  13.2; sin showdown.
- **Después (HEAD):** river `SB c 5.0`; `final_pot` 16.2; cartas de `BB`
  `3hKd`; showdown `BB (LaloMora)`.
- **Diferencia semántica:** el fold de `SB` se convierte en call de 5.0; la
  mano deja de ser victoria por fold y pasa a showdown.
- **Origen:** edición manual entre B03 y B04. Ningún script edita esa acción:
  `corregir_resultados_20261104.py` solo reclasifica; los scripts de folds
  retiran folds inferidos, no convierten un fold en call. Ventana B03→B04.
- **Evidencia:** revisión humana contra la grabación original; capturas
  `19:river:pot_read_vs_contributions`, `20:river:fold_missing_at_close`,
  `21:river:pot_read_vs_calculated`; B03/B04. Las capturas documentan la
  ambigüedad intermedia, no la decisión final.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar el contenido; conservar la explicación de por qué la
  captura automática no coincide; no atribuir el cambio a ningún script.

#### H_1338

- **Antes (`c1c1370`):** sin folds preflop de `UTG`/`MP`; river `UTG f` y
  `MP f` inferidos; `final_pot` 78.3.
- **Después (HEAD):** preflop `UTG f`, `MP f`; se retiran los folds de river;
  `final_pot` 76.1; cartas de `CO` `4cAc` y `SB` `AsQs`.
- **Diferencia semántica:** se mueven folds de river a preflop y se corrigen
  cartas/cierre.
- **Origen:** edición manual entre B03 y B04; ventana B03→B04. Ningún script
  produce esta reubicación.
- **Evidencia:** revisión humana; capturas 24–27; B03/B04.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener como edición manual no reproducible.

#### H_1340

- **Antes (`c1c1370`):** flop `SB b 1.0`, `BB c 1.0`; `final_pot` 15.1.
- **Después (HEAD):** flop `SB x`, `BB b 1.0`, `SB c 1.0`; `final_pot` 14.9.
- **Diferencia semántica:** se reordena la agresión del flop: check de `SB`,
  apuesta de `BB` y call de `SB`.
- **Origen:** edición manual entre B03 y B04; ventana B03→B04. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 28–30; B03/B04.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; no atribuir al script de folds.

#### H_1341

- **Antes (`c1c1370`):** turn `BTN b 37.8` inferido; `final_pot` 11.2.
- **Después (HEAD):** flop `BTN c 37.8`; `final_pot` 84.6; cartas de `CO`
  `2sKs`.
- **Diferencia semántica:** la apuesta inferida de turn se convierte en call de
  flop; cambia el cierre y el bote.
- **Origen:** edición manual entre B03 y B04; ventana B03→B04. Ningún script
  produce ese movimiento.
- **Evidencia:** revisión humana; capturas 31–32; B03/B04.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; registrar la reubicación como manual.

#### H_1342

- **Antes (`c1c1370`):** flop `SB b 1.0`, `BB c 1.0`; turn `BB b 1.0`
  inferido; `final_pot` 3.9; sin showdown.
- **Después (HEAD):** flop `SB x`, `BB b 1.0`, `SB c 1.0`; turn `BB x`;
  showdown `BB (Jarduan)`; cartas de `SB` `5d8c`.
- **Diferencia semántica:** reordena flop, convierte la apuesta de turn en
  check y añade showdown/cartas.
- **Origen:** edición manual entre B03 y B04; ventana B03→B04. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 33–34; B03/B04.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener la traza manual.

#### H_1343

- **Antes (`c1c1370`):** river `BB f` inferido; `final_pot` 140.0; sin
  showdown.
- **Después (HEAD):** se retira el fold de `BB`; showdown `UTG (Elperron)`;
  cartas de `BB` `AhQh` y `UTG` `JdQd`; `final_pot` 140.0.
- **Diferencia semántica:** se elimina un fold inferido de river y se declara
  showdown.
- **Origen:** edición manual entre B03 y B04; ventana B03→B04. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 35–36; B03/B04.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; no atribuir al script de folds.

#### H_1345

- **Antes (`c1c1370`):** turn `UTG r 28.6` inferido; river `UTG f` inferido;
  `final_pot` 87.8; sin showdown.
- **Después (HEAD):** turn `UTG c 20.6`; river `UTG c 18.0`; `final_pot` 97.9;
  showdown `CO (Elperron)`; cartas de `CO` `3hQh`.
- **Diferencia semántica:** se sustituyen una subida y un fold inferidos por
  calls; cambia el cierre y el bote.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. El script que se
  ejecuta en esa ventana (`limpiar_anotaciones_ruido.py`) solo retira ruido de
  auditoría; no edita acciones.
- **Evidencia:** revisión humana; capturas 38–40; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; documentar que la ventana no implica autoría del
  script.

#### H_1346

- **Antes (`c1c1370`):** flop `SB f`; `final_pot` 16.7.
- **Después (HEAD):** flop `UTG x`, `MP x`, `SB c 1.0`, `SB f`;
  `final_pot` 17.7.
- **Diferencia semántica:** se añaden checks y un call de `SB` antes de su
  fold; cambia el bote.
- **Origen:** edición manual en la ventana B04→B05. Allí se ejecuta
  `corregir_folds_showdown.py`, pero su regla **solo retira folds inferidos**;
  aquí se añaden checks y se convierte un fold no inferido en call, por lo que
  no puede ser su efecto. No se atribuye al script.
- **Evidencia:** revisión humana; capturas 41–42; B04/B05; lectura de la regla
  del script.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; dejar constancia de que la cercanía temporal al script
  no es autoría.

#### H_1348

- **Antes (`c1c1370`):** turn `BB r 6.2`, `BTN c 6.2` inferidos; river
  `BTN x`, `BTN f` inferidos; `final_pot` 17.6.
- **Después (HEAD):** turn `BB x`, `BB c 1.8`; river `BTN b 4.4`,
  `BB c 4.4`; showdown `BB (Elperron)`; cartas de `BB` `As5s`;
  `final_pot` 17.6.
- **Diferencia semántica:** se reconstruye turn y river completos; el bote final
  no cambia.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. El script de esa
  ventana solo limpia anotaciones.
- **Evidencia:** revisión humana; capturas 43–47; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener la traza manual.

#### H_1349

- **Antes (`c1c1370`):** preflop `UTG c 2.0` inferido; sin acciones de flop ni
  river de `UTG`; `UTG` inactivo; `final_pot` 10.7.
- **Después (HEAD):** preflop `UTG c 1.0` y `UTG c 2.0`, ambos no inferidos;
  flop `UTG x`; river `UTG f`; `UTG` activo; `final_pot` 19.7.
- **Diferencia semántica:** se separa el call preflop en dos acciones, se añaden
  check y fold, y se corrige el estado del jugador.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 48–49; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; documentar la corrección manual.

#### H_1350

- **Antes (`c1c1370`):** preflop `UTG c 2.5` inferido; flop `UTG b 0.5`
  inferido; `final_pot` 5.8.
- **Después (HEAD):** se retira el call preflop; flop `UTG x`; `final_pot` 8.7.
- **Diferencia semántica:** elimina una inversión preflop y convierte la apuesta
  de flop en check; cambia el bote.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; captura 50; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener la traza manual.

#### H_1351

- **Antes (`c1c1370`):** flop `SB c 1.9` y `SB c 2.0`; turn `BB b 12.0`,
  `CO c 2.0`, `BB r 83.3` inferido; river `CO f`, `SB f` inferidos;
  `final_pot` 105.0.
- **Después (HEAD):** flop `SB c 2.0` (una sola); turn `BB x`, `CO b 2.0`,
  `SB f`, `BB r 12.0`; river `BB b 16.8`, `CO c 16.8`; showdown
  `BB (Jarduan)`; `final_pot` 67.2.
- **Diferencia semántica:** se corrige el flop, se reconstruyen turn y river y
  se elimina el cierre por folds.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. El script
  `corregir_anotaciones_20261110.py` se ejecuta después y **solo ajusta notas**
  de bote; no edita acciones ni `final_pot`. La corrección de acciones es
  manual.
- **Evidencia:** revisión humana; capturas 51–58; B05/B06; docstring del script
  de anotaciones.
- **Certeza:** contenido alta; procedencia media (hay documentación del bote,
  pero no del procedimiento de las acciones).
- **Decisión:** aceptar el contenido; no atribuir las acciones al script de
  anotaciones.

#### H_1353

- **Antes (`c1c1370`):** flop `BB b 2.0`, `UTG b 2.0`, `MP b 2.0`, `CO f`,
  `BTN f`, `SB c 0.5`, `SB f`; river `BB f`; `final_pot` 11.0.
- **Después (HEAD):** preflop `UTG r 2.0`, `MP c 2.0`, `CO f`, `BTN f`,
  `SB f`, `BB c 2.0`; flop `BB x`, `UTG x`, `MP x`; river `BB f`;
  `final_pot` 12.7.
- **Diferencia semántica:** se reubican las acciones de flop a preflop y se
  normaliza la secuencia de la calle.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 59–62; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; dejar constancia de la reubicación manual.

#### H_1354

- **Antes (`c1c1370`):** river `BB f` inferido; `final_pot` 3.9; sin showdown.
- **Después (HEAD):** river `SB x`, `BB x`; showdown `SB (Elperron)`; cartas
  de `SB` `Ks5c`; `final_pot` 3.9.
- **Diferencia semántica:** se retira el fold inferido y se declara showdown.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 63–64; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; no atribuir al script de folds.

#### H_1356

- **Antes (`c1c1370`):** preflop `SB r 120.7` inferido; river `BB f`
  inferido; `final_pot` 196.6; sin showdown.
- **Después (HEAD):** preflop `SB c 3.0`; flop `SB x`; se retira el fold de
  river; showdown `SB (25289472)`; cartas de `SB` `7c7s`; `final_pot` 78.8.
- **Diferencia semántica:** se convierte una subida preflop en call, se añade
  check de flop y se elimina el fold de river.
- **Origen:** edición manual entre B05 y B06; ventana B05→B06. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 66–72; B05/B06.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener la traza manual.

#### H_1363

- **Antes (`c1c1370`):** flop `CO x` inferido y `CO f`; `final_pot` 11.9.
- **Después (HEAD):** preflop `CO f`; se retiran el check y el fold de flop;
  `final_pot` 11.9.
- **Diferencia semántica:** el fold de `CO` se mueve de flop a preflop y se
  elimina el check inferido.
- **Origen:** edición manual entre B06 y B07; ventana B06→B07. El script de esa
  ventana (`corregir_bote_inflado_fold.py`) solo recalcula botes de victorias
  por fold; no edita acciones.
- **Evidencia:** revisión humana; capturas 78–79; B06/B07.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; no atribuir al script de bote.

#### H_1365

- **Antes (`c1c1370`):** preflop `SB r 36.0` inferido; flop `SB b 50.0`;
  flop `CO f`, `BTN f`; turn `SB b 76.9` inferido; `final_pot` 157.7.
- **Después (HEAD):** preflop `CO f`, `BTN f`, `SB c 1.0`, `BB r 15.0`,
  `SB r 29.0`; flop `SB b 57.0`; flop `SB c 83.9`; cartas de `BB` `KsJs`;
  `final_pot` 225.6.
- **Diferencia semántica:** se reconstruye la secuencia preflop/flop y se
  corrige el cierre.
- **Origen:** edición manual entre B06 y B07; ventana B06→B07. El script de esa
  ventana solo ajusta botes de folds; no produce esta reconstrucción.
- **Evidencia:** revisión humana; capturas 80–82; B06/B07.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; documentar como reconstrucción manual.

#### H_1366

- **Antes (`c1c1370`):** river `CO f` inferido; `final_pot` 8.8; sin showdown.
- **Después (HEAD):** se retira el fold; showdown `BB (Jarduan)`;
  `final_pot` 8.8.
- **Diferencia semántica:** se elimina un fold inferido y se declara showdown.
- **Origen:** edición manual entre B06 y B07; ventana B06→B07. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; captura 83; B06/B07.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; no atribuir al script de bote.

#### H_1368

- **Antes (`c1c1370`):** turn `SB f`; `final_pot` 18.7; sin showdown.
- **Después (HEAD):** preflop `SB f`; flop `BTN c 13.5`; showdown
  `BTN (Jarduan)`; cartas de `BB` `QdTc`; `final_pot` 45.8.
- **Diferencia semántica:** se mueve el fold de `SB` a preflop y se añade un
  call de `BTN` en flop; cambia el cierre y el bote.
- **Origen:** edición manual entre B06 y B07; ventana B06→B07. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 84–87; B06/B07.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; mantener la traza manual.

#### H_1369

- **Antes (`c1c1370`):** preflop `SB p 0.5`, `SB c 1.0`, `SB f`; `SB` era
  `Juris55`, `BB` era `Jhon. As`; `final_pot` 4.5.
- **Después (HEAD):** se retiran las acciones de `SB`; se añade `UTG f`;
  `Juris55` pasa a `BB` y `Jhon. As` a `UTG`; `final_pot` 3.5.
- **Diferencia semántica:** se elimina la secuencia de `SB` y se reasignan
  posiciones; cambia el bote.
- **Origen:** edición manual entre B06 y B07; ventana B06→B07. Ningún script
  produce este cambio de acciones.
- **Evidencia:** revisión humana; capturas 88–90; B06/B07.
- **Certeza:** contenido alta; procedencia baja.
- **Decisión:** aceptar; documentar la reasignación de posiciones como manual.

## 6. Clasificación B1-R

Se usa una **clasificación dual** para no confundir contenido con procedencia.
Una misma mano puede ser categoría 3 en contenido y categoría 5 en procedencia.

| Categoría | Significado | Aplicación en B1-R |
|---|---|---|
| 1 | Reproducida por escritor versionado | 7 manos fuera de las 23; no cubre la cadena completa |
| 2 | Reproducida por otro procedimiento identificado | No para las 23; el lote de `44acddb` está identificado como corrección manual/recorder, pero no es reejecutable |
| 3 | Corrección manual con evidencia suficiente | **23/23 en contenido**, por revisión humana contra la grabación |
| 4 | Modificación identificada pero sin justificación suficiente | No se asigna a las 23: la revisión humana aporta justificación de contenido; las 98 de `44acddb` quedan como deuda de documentación, no como error demostrado |
| 5 | Modificación de origen desconocido | **23/23 en procedimiento exacto**: no hay log de la operación manual |
| 6 | Posible error de datos | No se asigna a las 23 tras la revisión humana; `H_1328`/`H_1336` se revisaron y quedaron confirmadas |

### 6.1 Tabla de las 23

| Mano | Contenido | Procedencia | Categoría | Decisión |
|---|---|---|---|---|
| `H_1143` | Correcta verificada | Manual; `44acddb` + `8594ed5`; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1303` | Correcta verificada | Manual; nota documental; sin script de acción | 3 + 5 | Aceptar; no atribuir al script de notas |
| `H_1328` | Correcta verificada | Manual B01→B02; sin script | 3 + 5 | Aceptar; captura no es verdad final |
| `H_1336` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; documentar discrepancia con captura |
| `H_1338` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1340` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1341` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1342` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1343` | Correcta verificada | Manual B03→B04; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1345` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1346` | Correcta verificada | Manual B04→B05; el script de folds no puede producirla | 3 + 5 | Aceptar; no atribuir |
| `H_1348` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1349` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1350` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1351` | Correcta verificada | Manual B05→B06; script de notas no edita acciones | 3 + 5 | Aceptar; no atribuir al script |
| `H_1353` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1354` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1356` | Correcta verificada | Manual B05→B06; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1363` | Correcta verificada | Manual B06→B07; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1365` | Correcta verificada | Manual B06→B07; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1366` | Correcta verificada | Manual B06→B07; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1368` | Correcta verificada | Manual B06→B07; sin script | 3 + 5 | Aceptar; no atribuir |
| `H_1369` | Correcta verificada | Manual B06→B07; sin script | 3 + 5 | Aceptar; no atribuir |

### 6.2 Las 7 manos con cobertura scriptada

Fuera de las 23, el análisis `c1c1370` → `8594ed5` encontró 7 manos con cambio
semántico cubierto por scripts:

`H_1314`, `H_1330`, `H_1333`, `H_1337`, `H_1344`, `H_1355`, `H_1361`.

Eso no convierte la base en reproducible: el intento de aplicar los 11 scripts
en orden histórico falla en `H_1336` y no alcanza el blob actual. La cobertura
scriptada es **parcial**, no una cadena completa.

## 7. Evaluación de la base actual

### 7.1 Alternativas A/B/C/D

| Alternativa | ¿Aplica? | Motivo |
|---|---|---|
| A. Reconstrucción exacta con procedimientos identificados | **No** | Los 11 scripts no producen las 23 correcciones y la cadena falla |
| B. Correcciones manuales legítimas, reproducción histórica imposible; adopción por excepción | **Sí, con reservas** | Las 23 están verificadas en contenido; la procedencia es manual y no reproducible |
| C. Modificaciones dudosas que requieren reparación | **No para las 23** | La revisión humana no encontró acciones incorrectas; `H_1328` y `H_1336` quedaron confirmadas |
| D. Evidencia insuficiente para adoptar | **No para las 23** | Hay evidencia suficiente de contenido y una traza documental de los huecos |

### 7.2 Veredicto y alcance

**Veredicto B.**

La base actual puede considerarse **candidata a adopción mediante una
excepción de procedencia explícita**, siempre que la excepción cubra:

1. las **23 correcciones manuales** de `8594ed5` verificadas visualmente;
2. las **98 correcciones semánticas de `44acddb`**, que no fueron objeto de la
   revisión visual de las 23 y no tienen registro por mano;
3. las importaciones de 45 y 47 manos de `8b44917` y `c1c1370`, que son
   bloques de sesión, no reconstrucciones manuales;
4. la eliminación de `H_1323`, que sí tiene script y expediente.

La excepción no debe afirmar que la base es reproducible. Debe decir
exactamente lo contrario: **es correcta en contenido según la evidencia
disponible, pero no reproducible con los artefactos versionados**.

### 7.3 Condiciones antes de adoptar

- Revisión independiente de este documento y de la revisión humana.
- Aceptación explícita de la excepción, con mención separada de `44acddb`.
- No actualizar el manifiesto ni los pines hasta esa aceptación.
- No sustituir derivados canónicos hasta una autorización posterior.
- No declarar los 11 escritores en el manifiesto como si la base fuese
  reproducible.
- No presentar la aprobación de contenido como validación estratégica,
  rentabilidad, HU/MW ni sesión real.

## 8. Confirmación de archivos canónicos intactos

Al cierre de B1-R:

```text
data/hands_db.jsonl
  3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e

data/profile_ranges.json
  add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa

data/postflop_ranges.json
  1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c

data/preflop_stats.json
  53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749

data/player_stats.json
  ae6babbcbf94d018f5ba4590c7cc9143ca244836a14cf5370c55f56d55306e44

data/profiles.json
  24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b

data/behavior.json
  efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae

data/observations.json
  86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3

data/calibration_window.json
  7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1
```

Verificación de la ventana:

```text
VENTANA DE CALIBRACION: provisional
  base      : 3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e
  lineas    : 1344
  validas   : 900
  excluidas : 23
  ventana   : 877
  hash      : ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed
OK: la ventana coincide con el snapshot
```

`MULTIWAY_SOPORTADO` sigue en `False` en `motor/rules.py`.

No se modificaron:

- `data/hands_db.jsonl`;
- el manifiesto de `motor/learn.py`;
- los siete derivados canónicos;
- las tablas preflop;
- los rangos manuales;
- las calibraciones;
- la lógica estratégica;
- `MULTIWAY_SOPORTADO`;
- el snapshot `data/calibration_window.json`.

No se ejecutaron sesiones reales ni se inició B2.

## 9. Deudas de trazabilidad que permanecen

1. **Las 23 correcciones de `8594ed5`:** contenido verificado, operación exacta
   desconocida. No hay log de `hand_editor.py` ni script que las produzca.
2. **Las 98 correcciones semánticas de `44acddb`:** lote manual/recorder
   identificado por commit y documentación, pero sin registro por mano. Las 75
   manos antiguas no fueron revisadas visualmente en B1-R.
3. **Las 11 scripts de `8594ed5`:** no están declarados en el manifiesto ni en
   `motor/test_quien_escribe.py`. No deben declararse como si la reproducción
   exacta estuviese demostrada.
4. **Las capturas automáticas:** son parciales e intermedias. No sustituyen las
   grabaciones originales ni la revisión humana.
5. **La diferencia `H_1328`/`H_1336` entre captura y estado actual:** queda
   documentada y resuelta solo por la revisión humana; si aparece evidencia
   contraria, debe reabrirse.
6. **La suite:** sigue con los fallos conocidos de B1. B1-R no los repara ni los
   declara resueltos.

## 10. Recomendación final

1. Aceptar el contenido de las 23 manos como **correcto y verificado
   visualmente**.
2. No afirmar que la base es reproducible.
3. No atribuir las 23 correcciones a scripts que no las realizaron.
4. Si se decide adoptar la base, emitir una **excepción de procedencia
   explícita** que cubra las 23 correcciones, el lote de `44acddb` y las
   importaciones.
5. Mantener el manifiesto, los pines y los derivados canónicos sin cambios hasta
   que esa excepción sea aceptada por revisión independiente.
6. No avanzar a B2, no ejecutar sesiones reales y no iniciar calibraciones
   estratégicas con esta base como si estuviese plenamente validada.

B1-R termina aquí. La conclusión es deliberadamente limitada: **sabemos que el
contenido de las 23 manos es correcto; no sabemos reproducir cómo se corrigió;
la base puede adoptarse solo con una excepción documentada y revisada.**
