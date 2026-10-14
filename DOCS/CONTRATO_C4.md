# CONTRATO C4 — `select_best` cuando no hay EV con el que decidir

**Estado:** firmado. Opción **(b)**, `EvInvalido`.
**Implementación:** `motor/rules.py` → `EvInvalido`, `_ev_finito`, `select_best`.
**Tests:** `motor/test_rules_contratos.py`.
**Lo que sustituye:** el `TODO(F5)` que decía *«con `evs.ev` vacío devuelve
`('fold', 0.0)`. Ese 0.0 es un EV que no existe»*.

> Este contrato es el último bloqueante declarado de Fase D. Sin él,
> `select_best` podía devolver una acción que nadie había medido.

---

## 1. Las tres opciones y cuál se eligió

| | opción | por qué no |
|---|---|---|
| (a) | devolver `None` y que el llamador decida | Cambia la firma de todos los llamadores para mover la decisión fuera de la función que la tiene. Y devuelve un valor que hay que comprobar: quien no lo compruebe, reproduce el bug en otro sitio. |
| **(b)** | **lanza `EvInvalido`, subclase de `ValueError`** | **elegida** |
| (c) | degrada a `('check',)` con `motivo = 'evs_vacio'` en `rp.note` | Elige una acción **concreta** sin dato. `check` puede ser la peor jugada disponible: es la que pierde el bote cuando hay una apuesta. Además muta `rp`, que es entrada, para arrastrar el motivo. |

### Por qué (b)

«No hay datos para decidir» y «la mejor acción evaluada es fold» son dos
cosas distintas, y (a) y (c) las confunden de dos maneras distintas: (c)
inventa una acción concreta; (a) devuelve un centinela que depende de que
todos los llamadores se acuerden de mirarlo.

La opción que hace que el error se vea **antes** de que llegue al bote es la
que lanza. Un `ValueError` en el punto donde se decide es un fallo ruidoso y
trazable; un `None` es un fallo que se propaga hasta que alguien lo desempaca.

**Subclase de `ValueError` a propósito:** el contrato dice «lanza
`ValueError`», y quien prefiera el tipo genérico lo sigue pudiendo capturar.
No es un detalle: fija el contrato en algo reconocible sin obligar a nadie a
conocer el nombre propio.

---

## 2. El contrato

### 2.1 El baseline es el EV **real** del fold, no 0.0

Si todas las candidatas están por debajo, devuelve `('fold', <su EV real>)`,
que puede ser negativo. Devolver `0.0` ahí sería **inventar un número**: le
dice al llamador que el fold es break-even cuando no lo es.

### 2.2 Un EV no finito **no es un EV**

`NaN`, `+inf`, `-inf`, y cualquier valor que no sea `int`/`float`, **se
ignoran como candidato**: no se eligen y no se comparan.

Esto no es teórico. El defecto más grave que arregla este contrato no era un
número inventado en un informe, era una **decisión equivocada**:

```python
best_ev = evs.ev.get('fold', 0.0)     # -> nan
for label in labels:
    if val > best_ev:                 # nan > 3.0  es False, SIEMPRE
        best_label, best_ev = label, val
return 'fold', nan                    # teniendo 'check' con 3.0
```

Comparar contra `NaN` da `False` para todo, así que el bucle entero se queda
sin mejorar y devuelve el `NaN` **como si fuera la decisión**. El guard de
esto es `test_c4_fold_nan_no_hace_perder_a_la_alternativa_real`.

### 2.3 Si ningún candidato tiene EV finito, lanza

`evs` vacío, o todos `NaN`, o un plan cuyas candidatas no se han calculado:
**lanza `EvInvalido`.** No devuelve una acción por defecto.

```
select_best: ninguna accion tiene un EV finito (evs con 3 clave(s): ['all_in', 'check', 'fold']). No hay datos para decidir; devolver una accion aqui seria inventarla.
```

El mensaje **distingue las dos cosas** y **nombra las claves que hubo**, para
que se pueda diagnosticar sin depurar. Lo fija
`test_c4_el_motivo_dice_que_no_hay_datos`.

### 2.4 Empate: gana el primero, y `fold` se considera siempre primero

La comparación es estricta (`>`), así que el resultado es **determinista**.
No hay orden de diccionario ni nada que dependa de cómo se haya construido el
plan. Lo fija `test_c4_empate_gana_el_primero`.

### 2.5 Sin plan, todas las claves de `evs.ev`

Si `rp is None`, se consideran todas las claves presentes en `evs.ev`. Una
clave que **no está** en `evs.ev` no se elige: no tiene EV, y elegirla sería
lo mismo que inventarlo (`test_c4_las_candidatas_ausentes_no_se_inventan`).

---

## 3. Lo que este contrato **no** arregla

**`EvTable.best()` sigue sin contrato propio.** `motor/decision.py:425` tiene
el mismo `self.ev.get('fold', 0.0)` y el mismo `val > best_ev`, y por tanto el
mismo problema con `NaN`.

No se toca aquí, y la razón está escrita: `best()` solo se usa **cuando no
hay plan**, y en ese camino la validación de `decision.compute_evs` ya
rechaza entradas no finitas antes de construir la tabla. Es una garantía de
*calla* mientras siga siendo cierto, no una garantía del contrato.

> **Si algún día `compute_evs` deja de validar, esto se rompe en silencio.**
> Es deuda declarada, en `PROYECTO.md` §6.2.

---

## 4. Cómo se comprueba

```python
python -m pytest motor/test_rules_contratos.py -q
```

Las tres ramas que pedía el encargo, más el defecto que no se había pedido
buscar:

| test | qué fija |
|---|---|
| `test_c4_evs_vacio_lanza_ev_invalido` | `evs` vacío |
| `test_c4_todos_nan_lanza_ev_invalido` | todos `NaN` |
| `test_c4_un_solo_elemento_valido` | un único EV real, se devuelve bien |
| `test_c4_fold_nan_no_hace_perder_a_la_alternativa_real` | **el defecto real**: `fold` NaN no puede ganar |
| `test_c4_infinito_se_ignora` | `±inf` no es un EV |
| `test_c4_todos_infinito_lanza` | todos `±inf` |
| `test_c4_el_motivo_dice_que_no_hay_datos` | el mensaje dice «no hay datos» y nombra las claves |
| `test_c4_ev_invalido_es_valueerror` | la subclase, para no romper a quien capture el tipo genérico |
| `test_c4_empate_gana_el_primero` | determinismo |
| `test_c4_ninguna_accion_legal_tambien_lanza` | plan sin nada evaluable |
| `test_c4_las_candidatas_ausentes_no_se_inventan` | una clave que no está en `ev` no se elige |

> Los dos tests que **cambian de contrato** respecto al anterior
> (`test_c4_tabla_vacia_devuelve_fold_con_cero` y su hermano) se han
> **eliminado**, no relajado. Un contrato que se cumple con las dos reglas a
> la vez no es un contrato: es una indefinición con test.