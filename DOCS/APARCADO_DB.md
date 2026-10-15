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
| 2 | abierto | **cerrado como canal, y reabierto por una excepción** | [`CANAL_MANUAL_CERRADO.md`](CANAL_MANUAL_CERRADO.md), pero ver §3 |
| 3 | pendiente | **hecho** | `motor/test_canal_manual.py` — 11 tests |
| 4 | clasificados, sin resolver | **clasificados, sin resolver** | [`HALLZGOS_H0001_H1014.md`](HALLZGOS_H0001_H1014.md) §3 |
| 5 | abierto | **abierto** | [`DEFECTO_45.md`](DEFECTO_45.md), [`DEFECTO_8.md`](DEFECTO_8.md) |
| 6 | pendiente | **pendiente** | sin documento |

### Sobre la fila 2 y la 3

`revision_1` llama a la fila 3 «la tarea más importante del bloque», y se hizo:
`motor/test_canal_manual.py` es lo que hoy hace rojo el árbol cuando alguien
toca `hands_db.jsonl` sin declararlo. La fila 2 está cerrada *como norma*, con su
documento canónico, su SHA-256 y sus 11 guards.

Pero «cerrado el canal» y «la base intacta» no son lo mismo, y ahora mismo no
coinciden. Ver §3.

---

## 3. Lo que el aparcamiento no cubrió

> Esta sección no estaba en el encargo. Está porque el árbol está en rojo y un
> documento que dice «la DB está aparcada» mientras seis guards disparan sería
> la forma exacta de mentir que este fichero pretende evitar.

`revision_1` aparcó la base **para no tocarla**. Desde entonces la base **se ha
tocado**. El commit `9b5905a` («db actualizada H_1029») cambió **63 líneas** de
`data/hands_db.jsonl`, y `learn.REVISION_PENDIENTE` sigue en `True` con
`REVISION_HASTA = 'H_1014'`.

Los guards dicen exactamente eso, y por eso el árbol está rojo:

```
711 passed, 6 failed, 1 skipped, 5 xfailed     # antes de este bloque
731 passed, 6 failed, 1 skipped, 5 xfailed     # después: +20 tests de F7.2.b
```

Los **6 fallos son los mismos antes y después**, y ninguno es de motor.

| test | qué está diciendo |
|---|---|
| `test_el_hash_de_la_base_es_el_declarado` | sha real `36dce9fe`, declarado `202a1f54` |
| `test_el_ultimo_commit_que_toco_la_base_tiene_el_hash_declarado` | idem, contra el blob del commit |
| `test_la_base_no_cambia_mientras_hay_revision_manual` | la base cambió con la revisión abierta |
| `test_aplicar_reinterpretacion_no_puede_sobrescribir_un_ajeno` | el fichero ya no es «ajeno» |
| `test_cada_mano_editada_cambia_una_sola_accion_del_bb` | 34 acciones de preflop cambiadas, el ancla esperaba 23 |
| `test_las_cifras_publicadas_coinciden_con_la_ventana_vigente` | la ventana hoy da **521 / 239 / 268**; publicado: 519 / 238 / 267 |

**Lo que esto significa, sin interpretarlo de más:** la revisión manual de las
manos de CM-004 ha seguido avanzando (de `H_1014` a `H_1029`), el manifiesto
del estado canónico no se ha movido con ella, y la métrica de `CONTRATO_F72A.md`
—publicada sobre la ventana anterior— ya no es la que sale de la ventana de hoy.

**Esto no se arregla desde aquí.** Es la fila 2 de la tabla: una decisión de
gobernanza de datos, no de motor. Lo que sí queda es escrito, que es lo que
pedía el encargo.

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