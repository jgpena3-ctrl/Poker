# F6.1.a — Inventario de `pending`

Artefacto previo a F6.1.b. **No modifica código**: deja constancia de cómo
está `pending` hoy, para proponer un contrato canónico sobre hechos y no sobre
suposiciones.

Generado con `python tools/inventario_pending.py` (solo lectura).

## Qué significa `pending` hoy

Un rival **activo** en la mano que **aún no ha actuado** en la calle actual, y
que no es el hero. Es decir, tiene una decisión pendiente: es una amenaza
activa, no un rival yaExposuredo.

Dos conceptos que no deben confundirse (ya documentados en `pegar_3 §1`):

- **activo**: sigue en la mano (`state == 'activo'` / `players[].active`).
- **pendiente**: no ha actuado en *esta* calle.

Estar activo no implica tener una decisión pendiente.

## Fuentes: hay cinco, y no son la misma

| # | sitio | cómo calcula el conjunto |
|---|---|---|
| 1 | `motor/asistente_live.py:744-752` | recorre `PLAYER_IDS`, filtra por `state == 'activo'` **y** `not in ya_actuaron` |
| 2 | `motor/hierarchy.py:321-325` | filtra `pending_positions` contra `acted` y `hero_pos` |
| 3 | `tools/auditar_anchor.py:27,34` | `players[].active` **y** `not in acted` |
| 4 | `tools/auditar_sombra.py:37,45` | idéntico a 3 |
| 5 | `tools/medir_multiway.py:84` | **otra definición**: posiciones que aparecen *después* del índice `i` en la lista |

La 5 no es la misma cosa: no mira quién está activo ni quién ha actuado, sino
la posición en la lista de acciones. Da un conjunto distinto.

## El doble cálculo dentro de `classify_villains`

`asistente_live._jerarquia` (fuente 1) calcula `pendientes` y lo pasa como
`pending_positions`. `classify_villains` (fuente 2) lo vuelve a filtrar:

```python
for pos in (pending_positions or ()):
    if pos and pos != hero_pos and pos not in acted and pos not in pending:
        pending.append(pos)
```

El filtro `not in acted` y `pos != hero_pos` ya los aplicó el llamador. Es el
mismo dato calculado dos veces, en dos sitios, con dos listas.

**Consecuencia:** la función no es autosuficiente. Si alguien la llama sin
`pending_positions` (el default es `()`), obtiene `pending == []` siempre — no
"no hay pendientes", sino "nadie me dijo cuáles eran". Es un default que
produce un resultado plausible y falso.

## El vocabulario de roles está muerto

`hierarchy.py:50-53` define `AGGRESSOR`, `CHECKER`, `CALLER` y `PENDING`.
`classify_villains` **nunca emite esas etiquetas**: devuelve claves separadas
(`aggressors`, `checkers`, `callers`, `pending`).

Verificado por el inventario: las cuatro constantes solo se usan en
`motor/test_hierarchy.py:16`. **Cero usos en producción.**

Son dos vocabularios conviviendo, y solo uno describe lo que el código hace.

## Consumidores

| sitio | qué hace con `pending` |
|---|---|
| `motor/hierarchy.py:232` | exige exactamente 1 pendiente (condición del ancla) |
| `motor/hierarchy.py:383` | `n_pending`, entra en el cálculo sombra |
| `motor/recommend_loop.py:297` | `n_pend`, idem |
| `motor/asistente_live.py:1059` | solo lo muestra en un log |

Ningún consumidor **muta** `pending`. Es de solo lectura en todas partes.

## Ciclo de vida

| fase | quién | cómo |
|---|---|---|
| **creación** | `asistente_live._jerarquia` | calcula la lista y la pasa |
| **refinado** | `classify_villains` | la vuelve a filtrar (redundante) |
| **consumo** | `shadow_equity`, `recommend_loop`, log | `len(...)` |
| **resolución** | — | **implícita**: se recalcula entero en cada llamada |
| **cancelación** | — | no existe como concepto |
| **limpieza** | — | no hay estado que limpiar: no se persiste |

No hay ciclo de vida porque `pending` no es estado: es un valor derivado que se
recalcula en cada llamada. Eso **simplifica** F6.1.b — no hay migración de
estado que hacer — pero también significa que "unificar" es sobre todo eliminar
el cálculo duplicado y fijar una única definición.

## Riesgo conocido ya documentado en el código

`hierarchy.py:195-200` avisa de que el ancla empírico se midió con **otra**
definición de `pending`, y de que por eso los "cero coincidencias" reportados
no son concluyentes. Este inventario confirma que el problema era estructural:
había (y hay) varias definiciones conviviendo.

## Qué NO hace este inventario

No propone el contrato canónico. Ese fue **F6.1.b**, abajo.

---

# F6.1.b — Contrato canónico (aplicado)

## La decisión que había que tomar

Las cinco fuentes no eran equivalentes. Dos incompatibles:

- el motor en vivo exige `estado == 'activo'` **y** no haber actuado;
- las herramientas solo pueden mirar `players[].active` y "no ha actuado",
  porque en `hands_db.jsonl` no existe el estado de mesa.

**Decisión: parámetro `activos` explícito.** El "sigue en la mano" pasa a ser
un dato de entrada declarado por el llamador, no una suposición del
calculador. Nadie adivina.

## Qué cambió

```python
def pending_positions(acts, hero_pos, activos) -> List[str]:
    """sigue en la mano Y no ha actuado en esta calle Y no es el hero."""
```

`activos` es **obligatorio y sin valor por defecto**. Antes el default `()`
devolvía `pending == []`, que se lee como "no hay nadie pendiente" cuando en
realidad es "nadie me dijo quiénes son". No se puede deducir de `acts`: las
acciones de la calle solo dicen quién **actuó**, nunca quién falta por actuar.

Ahora omitirlo es un `TypeError`: **falla ruido, no miente en silencio**.

| | antes | después |
|---|---|---|
| sitios que calculan el conjunto | 5 | **1** (`hierarchy.pending_positions`) |
| quién declara `activos` | — | motor en vivo, y las 2 herramientas |
| default sin datos | `()` → `[]` falso | imposible: `TypeError` |
| "cero" vs "no se sabe" | indistinguibles | clave `pending_known` |
| vocabulario de roles | 4 constantes, 0 usos en producción | **eliminadas** |

## Equivalencia de comportamiento

Quien antes pasaba candidatos pre-filtrados obtiene **lo mismo**: la función
canónica aplica esos mismos tres filtros. Está fijado en
`test_el_resultado_no_cambio_para_quien_ya_filtraba`. Si algún día cambia el
resultado de una decisión real, ese test lo dice.

## El vocabulario de roles eliminado

`AGGRESSOR`, `CHECKER`, `CALLER` y `PENDING` se han borrado.
`classify_villains` **nunca emitió** esas etiquetas: devuelve claves separadas.
Solo los importaba `test_hierarchy.py`, y sin usarlos.

Eran un segundo vocabulario que describía algo que el código no hace. `PENDING`
además confundía con la clave `pending`, que es una lista de posiciones, no
una etiqueta.

## `medir_multiway.py` se queda como estaba

Cuenta "posiciones que aparecen después del índice `i`", que **responde otra
pregunta**: quién *puede actuar todavía*, no quién *tiene una decisión
pendiente*. No es un conflicto de definiciones sino de alcance, y es el
territorio de F7 (multiway).

## Verificación

`tools/inventario_pending.py` sigue siendo ejecutable y ahora funciona como
**detector de regresión**: debe reportar exactamente 1 implementación de "no ha
actuado en la calle". Si aparece una segunda, salta.

```
   QUIEN IMPLEMENTA "no ha actuado en la calle": 1
   -> correcto: debe ser UNA (motor/hierarchy.py).

   OTRAS definiciones, con OTRA pregunta (no es un conflicto):
      tools/medir_multiway.py  -> posiciones posteriores en la lista
      Responde "quien puede actuar todavia", no "quien esta
      pendiente". Es el alcance multiway (F7), no `pending`.

   AGGRESSOR  (no definido)
   CHECKER    (no definido)
   CALLER     (no definido)
   PENDING    (no definido)
```

## Tests

`motor/test_pending.py`, 14 tests. No cubren solo el resultado, sino sobre todo
la **honestidad** del resultado:

- `activos=None` → `pending == []` **pero** `pending_known is False`;
- `activos=[]` → `pending == []` **y** `pending_known is True` (sí se sabe);
- omitir `activos` → `TypeError`;
- equivalencia con el comportamiento previo.

## Siguiente: F6.2

Conectar `equity_main` por una interfaz explícita, en modo sombra primero.
`pending` ya tiene un contrato estable sobre el que apoyarlo.
