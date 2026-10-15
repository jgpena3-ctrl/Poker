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

## 3. `EvTable.best()` — el otro camino, y su propio contrato

`decision.EvTable.best()` hacía la misma cuenta que `select_best` y **tenía el
mismo bug que este contrato arregla**, sin arreglar:

```python
best_label, best_ev = 'fold', self.ev.get('fold', 0.0)   # 0.0 INVENTADO
for label in labels:
    val = self.ev.get(label)
    if val is not None and val > best_ev:                 # nan > 0.0 es False
        best_label, best_ev = label, val
return best_label, best_ev
```

Con un `NaN` en el fold, `nan > 0.0` es `False` **siempre**, así que el bucle
entero se queda sin mejorar y devuelve `('fold', nan)`: un NaN disfrazado de
decisión. Y sin fold, el baseline era `0.0`, un EV que nadie midió — el
`TODO(F5)` que este contrato sustituye en `select_best`.

### 3.1 ¿Mismo contrato o distinto?

**Distinto, y en un solo punto: cómo se falla.** La regla de selección es la
misma; la diferencia es qué hace la función cuando no hay nada que decidir.

| | `rules.select_best` | `EvTable.best` |
|---|---|---|
| quién lo llama | el motor, para **decidir** | el panel y la GUI, para **pintar** |
| sin ningún EV finito | **lanza `EvInvalido`** | devuelve `('fold', nan)` |
| por qué | «no hay datos» ≠ «la mejor acción es fold» | pintar un hueco no es lo mismo que decidir |
| si levantara | — | el panel se caería entero para pintar un `nan` |

Medido, los llamadores reales:

| | |
|---|---|
| **pintan** | `panel.format_insight`, `panel.format_evs`, `asistente_live_gui` ×2 |
| **decidían** | `recommend_loop.recommend` ×2, cuando `rp is None` |

Que una función esté en las dos listas **es el defecto**, y por eso el arreglo
no es solo arreglar `best()`: es que **`best()` ya no decide nunca**.

### 3.2 El contrato

> `EvTable.best(candidates=None)` devuelve la etiqueta con el mejor EV
> **finito**, para pintarla. **No es una recomendación.**

| | regla |
|---|---|
| baseline | el EV **real** del fold; si no hay fold, o no es finito, `nan` |
| candidatos | un EV no finito, o de un tipo raro, **se ignora**: no es un EV |
| comparación | estricta (`>`), así que **gana el primero**, y `fold` se considera primero |
| sin ningún EV finito | `('fold', nan)`. **NaN, nunca 0.0** |
| `candidates` | si se pasa, solo se consideran esas etiquetas |
| **nunca lanza** | para eso está `select_best` |

`nan` y no `0.0` por lo mismo que §2.1: `0.0` le dice al lector que el fold es
break-even, y eso es un número que nadie midió. `nan` dice «no hay dato», y en
el panel sale impreso como `nan`, que es exactamente lo que es.

### 3.3 Y quién decide

`recommend_loop.recommend()` usaba `evs.best()` cuando `rp is None`. Eso no es
un caso defensivo: `rules.plan()` lanza con `street='preflop'` y el `except`
de arriba lo convierte en `rp=None`, que es un camino de producción.

Ahora las dos pasadas llaman a `rules.select_best(evs, None)`, que es el
contrato de §2, con su `EvInvalido`. Un motor sin plan y sin datos **falla
ruido**, en vez de devolver un NaN disfrazado de acción.

Lo fija `test_c4b_el_motor_no_decide_con_best`, con AST: la primera versión
buscaba el texto `evs.best()` en el fuente y fallaba por el comentario que
explica el cambio. Un guard que se dispara por su propia documentación no
vigila nada.

### 3.4 Cómo se comprueba

```python
python -m pytest motor/test_rules_contratos.py -q
```

| test | qué fija |
|---|---|
| `test_c4b_best_ignora_el_nan` | **el defecto real**: el NaN del fold no se lleva la decisión |
| `test_c4b_best_devuelve_nan_y_no_cero_sin_datos` | sin datos sale `nan`, no el `0.0` inventado |
| `test_c4b_best_no_lanza_donde_select_best_s_i` | el mismo `evs` imposible: uno lanza y el otro contesta |
| `test_c4b_best_ignora_los_tipos_raros` | un EV que no es número no es un EV |
| `test_c4b_best_es_el_mismo_ganador_que_select_best` | en todo lo decidible, **los dos coinciden** |
| `test_c4b_best_respeta_candidates` | el filtro sigue funcionando |
| `test_c4b_el_panel_aguanta_el_nan` | pintar un NaN no revienta el panel |
| `test_c4b_el_motor_no_decide_con_best` | el motor no vuelve a decidir con `best()` |

> `test_c4b_best_es_el_mismo_ganador_que_select_best` es el que sostiene la
> frase «misma regla, distinto fallo». Sin él, «misma regla» sería una
> frase: bastaría con que los dos métodos dejaran de coincidir en algún
> `evs` raro y nadie se enteraría de que el EV que se pinta y el que se
> decide son cosas distintas.

---

## 4. Cómo se comprueba el de `select_best`

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

> Un solo test ha cambiado de contrato, y se ha **eliminado**, no relajado:
> `test_c4_tabla_vacia_devuelve_fold_con_cero` (eliminado) afirmaba que una
> tabla vacía devolvía `('fold', 0.0)`. Era la mitad del `TODO(F5)` que este
> contrato sustituye, y el `0.0` era precisamente el número inventado que el
> contrato prohíbe.
>
> Un contrato que se cumple con las dos reglas a la vez no es un contrato: es
> una indefinición con test. Por eso no se relajó: se borró.