# APARCADO_DB — lo que queda de la base de datos fuera del camino

**Estado:** vigente.
**Origen:** `revision_1`.
**Motivo del documento:** que la próxima sesión no lea «la DB está aparcada» y
lo interprete como «la DB está resuelta».

> **Esto no está resuelto, está aparcado.**
>
> Aparcado quiere decir: *no se ha decidido, y la decisión no se ha tomado*.
> Ninguna fila de esta tabla está cerrada. Si alguien necesita una cifra que
> sale de la DB, vuelve aquí antes de usarla.

---

## 1. Lo que se aparca (y no se toca)

La tabla va tal como la dictó `revision_1`, sin reescribir.

| # | Tema | Estado | Por qué se aparca |
|---|---|---|---|
| 1 | Discrepancia de rangos (877 vs 991 vs 900) | abierto | decisión de calibración, no de motor |
| 2 | Canal manual (68 cambios sin declarar) | abierto | decisión de gobernanza de datos |
| 3 | Test que detecte edición manual | pendiente | va con #2 |
| 4 | 4 defectos sistémicos (36+16+15+11) | clasificados, sin resolver | datos |
| 5 | Defectos 45 y 8 sin código de origen | abierto | datos |
| 6 | Enlaces rotos | pendiente | cosmético |

**Condición de `revision_1`, literal:** «esto no se ha resuelto, se ha aparcado.
Si en algún momento del trabajo de motor alguien necesita una cifra que sale de
la DB, hay que volver aquí antes. Si no, se calibra sobre 877 con 68 cambios
sin declarar y todo el trabajo de motor se construye sobre arena».

---

## 2. Estado medido de cada fila

La tabla de arriba es el encargo. Esta es su foto **en el momento de escribir
esto**, porque dos filas ya se movieron y documentarlas como estaban sería
mentir sobre el estado real.

| # | Estado que dice §1 | Estado real hoy | Dónde se comprueba |
|---|---|---|---|
| 1 | abierto | **abierto, y ahora con tres rangos y no dos** | [`RANGO_VIGENTE.md`](RANGO_VIGENTE.md) — 1258 líneas · ventana 877 · rango auditado 991 · las tres son cosas distintas |
| 2 | abierto | **cerrado.** El canal manual tiene norma, documento canónico, SHA y 12 guards | [`CANAL_MANUAL_CERRADO.md`](CANAL_MANUAL_CERRADO.md) |
| 3 | pendiente | **hecho.** `motor/test_canal_manual.py`, 12 tests | `motor/test_canal_manual.py` |
| 4 | clasificados, sin resolver | **clasificados, sin resolver** | [`HALLZGOS_H0001_H1014.md`](HALLZGOS_H0001_H1014.md) §3 |
| 5 | abierto | **abierto** | [`DEFECTO_45.md`](DEFECTO_45.md), [`DEFECTO_8.md`](DEFECTO_8.md) |
| 6 | pendiente | **pendiente** | sin documento |
| 7 | *(no existía)* | **`9b5905a` con la base «congelada»: resuelto** | §3 de este documento |

### Sobre la fila 2 y la 3

`revision_1` llama a la fila 3 «la tarea más importante del bloque», y se hizo:
`motor/test_canal_manual.py` es lo que hoy pone rojo el árbol cuando alguien
toca `hands_db.jsonl` sin declararlo.

La fila 2 quedó cerrada de verdad: los 63 cambios de `9b5905a` se **aceptan**,
se miden y se declaran con su hash y su motivo, que es lo que la fila pedía.
Ver §3.

---

## 3. Lo que el aparcamiento no cubrió: `9b5905a`

> Esta sección no estaba en el encargo. Está porque la fila 2 no se puede
> decir «abierta» cuando su commit ya está dentro, y un documento que dice
> «la DB está aparcada» mientras el manifiesto va a medias sería la forma
> exacta de mentir que este fichero pretende evitar.

`revision_1` aparcó la base **para no tocarla**. Después, el commit `9b5905a`
la tocó: **63 líneas**, con `learn.REVISION_PENDIENTE` todavía en `True`. Eso
dejó el repo en rojo y descuadró la métrica publicada.

**Se ha resuelto. Opción A: se acepta el estado y se declara.**

| | `5c41b23` | `9b5905a` |
|---|---|---|
| manos con una `BB b` mal ordenada (**el invariante de CM-004**) | 2 · `H_0103`, `H_0236` | **0** |
| manos sin ganador declarado | 1 | **0** |
| `winner` con 2+ ganadores, en las 63 tocadas | 14 | **1** |
| jugadores `active:false` que conservan `pos` | 29 | **20** |
| líneas del fichero | 1258 | 1258 |

No era un cambio accidental: era la revisión manual avanzando de `H_1014` a
`H_1029`, y **medida**, mejora. Revertir habría devuelto dos violaciones del
invariante de CM-004 y perdido trabajo real.

Lo que se movió con ella:

| | |
|---|---|
| manifiesto canónico | `learn.HANDS_DB_*` → sha `36dce9fe…`, commit `9b5905a`, 1258 líneas |
| `CONTRATO_F72A.md` §5 | recalculada: **521** puntos de política, **239** MW, **45,9 %**, cota **268** |
| ancla de `test_cm004.py` | 23 → **34** acciones, y el porqué desglosado en el propio test |
| el congelamiento | **eliminado**, por ser autocontradictorio (§3.1) |

### 3.1 El congelamiento era imposible, no solo incómodo

`REVISION_PENDIENTE = True` decía dos cosas:

> «el mantenedor está revisando las manos una a una» — **y** — «la base no se modifica»

Revisar las manos una a una **es** modificarlas. El congelamiento prohibía
exactamente la actividad de la revisión, así que tenía que reventar en el
primer commit de revisión. No era un guard: era una bomba de relojería.

Las dos meanings están separadas ahora:

| | antes | ahora |
|---|---|---|
| el mantenedor edita a mano | **prohibido** | **es la revisión** |
| un script escribe | prohibido | prohibido (`--apply` → 4) |
| el manifiesto se redeclara | imposible mientras dure la revisión | en cada avance, con su motivo |

Lo que protege las ediciones del mantenedor no es un congelamiento, es
`test_el_hash_de_la_base_es_el_declarado`: obliga a que cada cambio lleve su
hash, su commit y su motivo. Dos guards del mismo invariante no son más
seguridad, son dos sitios donde el invariante puede estar mal.

`REVISION_PENDIENTE` **no existe ya**. Era el estado «hay una decisión a medias
y no se sabe cuál», y un pendiente que nadie puede resolver no es un estado
defendible en un repositorio. Lo que queda es `REVISION_EN_CURSO`, que solo
significa «ningún script escribe».

---

## 4. Condición de vuelta

`revision_1` la formula así, y sigue en pie:

> Si en algún momento del trabajo de motor alguien necesita una cifra que sale
> de la DB, hay que volver aquí antes.

Leída al revés, esa condición aplicada a lo que viene dice algo útil:
**este bloque de motor no ha necesitado ninguna cifra de la DB.** F7.2.b marca
la política multiway sin leer una sola mano. Esa es la prueba de que el
aparcamiento funcionó — y también su límite: en cuanto una tarea del motor
necesite el dato, el redo empieza por esta tabla, no por el código.

Con una excepción que sí se ha dado, y conviene no disimular: para **cerrar**
el fila 2 hubo que leer las cifras de la DB. Se leyó para *declarar* el estado,
no para *calibrar* nada. La diferencia es la misma que separa `HANDS_DB_SHA256`
de un peso de rango: uno dice qué hay, el otro decide qué hacer.