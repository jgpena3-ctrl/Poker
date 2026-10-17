# LIMITACIÓN PERMANENTE — la población B en preflop es vacía

> `revision_1`, tarea 2: registrar el hallazgo como limitación permanente.
> Esto no es un bug. Es una propiedad de los datos, y tiene que estar
> escrito donde no se pierda, porque la próxima persona que vaya a medir un
> AUC preflop va a perder dos días descubriéndolo.

---

## 1. El hecho

**En esta base, la población B no tiene ninguna decisión preflop *con
etiqueta*.** Las decisiones **existen** —83— pero están bloqueadas por el
orden de filtros, y desbloqueadas serían de **una sola clase**. Las dos
cosas se miden abajo, y las dos importan.

La población B es la del AUC: «el héroe **continúa** (`b`/`c`/`r`) o
checkea (`x`)», en la partición de validación
([`CONTRATO_L_SEC.md`](CONTRATO_L_SEC.md) §8).

| | |
|---|---:|
| cortes preflop de validación, en total | 23 |
| de ellos, población B | **0** |
| los 23 que había | folds, con `y = 0` por construcción |

En la ventana fiable entera (877 manos):

| | |
|---|---:|
| continuaciones preflop (`b`/`c`/`r`/`x`) | 83 |
| de ellas `b`/`c`/`r` | 81 |
| de ellas checks | 2 |
| **con etiqueta** | **0** |
| con etiqueta y `y = 1` | **0** |

Un AUC necesita las dos clases. Con cero observaciones de la clase
positiva, **no hay nada que ordenar**.

---

## 2. La razón, medida y no theoriesada

Las 83 se caen en el **mismo** filtro, y es el primero de todos:

```python
def board_completo(h):
    return len((h.get('comunitarias') or {}).get('river') or []) >= 1
```

Se comprueba **antes** del camino de victoria por fold. De modo que una
victoria por fold limpia —que es exactamente lo que produce una decisión
preflop jugada— no puede tener etiqueta: se pide el board antes de llegar
al único camino que la aceptaría.

Dónde está el board, en las 83:

| | |
|---|---:|
| `comunitarias.river` con cartas | 0 |
| el board **sí** está, en `streets.*.board`, y `comunitarias` vacío | **2** |
| no hay board en ninguna parte | 81 |

### Y aquí se corrige una conclusión que era falsa

> **Se retira.** Este documento decía:
>
> «82 de las 83 no tienen las cartas de ningún otro jugador. […] **Ni con
> otra regla** la pregunta es respondible: **una observación** no es un
> AUC.»
>
> `revision_2` parrafo 2 lo señaló sin tener la Medición delante. Las dos
> partes están mal, y por partida doble.

**Medido, saltando los dos filtros que se adelantan al camino de fold:**

| | |
|---|---:|
| de las 83, con etiqueta posible | **78** |
| — victorias por fold verificables | 77 |
| — showdown verificable (`H_0485`) | 1 |
| fold no verificable (dos jugadores sin foldear) | 4 |
| showdown sin cartas de los demás | 1 |

**La población no está vacía: está BLOQUEADA.** `gano_por_fold()` existe
precisamente para verificar una victoria por fold **sin** las cartas de los
demás jugadores, y funciona en 77 de las 83. Lo que las deja fuera son dos
filtros que se **adelantan** a ese camino:

```python
if not board_completo(h):      continue   # <- 83 se caen aqui
if len(con_cartas(h)) < 2:     continue   # <- 82 se caen aqui
...
ok_fold, _mot = gano_por_fold(h, declarados)   # <- el unico que las acepta
```

Y la segunda parte es peor: **las 78 son todas victorias, cero derrotas.**

| | |
|---|---:|
| `y = 1` | 78 |
| `y = 0` | **0** |

Así que un AUC binario daría **1,0 por definición**, que es tan poco
informativo como 0,5. **La razón por la que no hay AUC no es que falten
manos: es que la población tiene una sola clase.**

### Una explicación que se retiró, y por qué importa

Este documento antes daba una explicación que era **falsa**:

> «Si el héroe juega y gana, vuelve a actuar y el corte se mueve de calle.
> Para que el corte se quede en preflop con una acción jugada, la mano
> tiene que terminar ahí mismo. Las dos cosas a la vez no se dan.»

Medido, en 81 de las 83 la mano **sí** termina en preflop —porque todos
foldean a la apuesta del héroe— y el héroe **sí** gana por fold, con
`winner` declarado. `H_0043`, entero:

```
preflop        UTGf MPc COc BTNb SBf BBf MPf COf
winner         ['p1']
showdown       {'winner1': 'BTN (Jarduan)'}
comunitarias   {'flop': [], 'turn': [], 'river': []}
```

El corte se queda en preflop por eso, no porque el héroe vuelva a actuar.

Y la generalización «no puede pasar» era **imposible de sostener**:
`calibrar.muestra()` tiene un camino de victoria por fold precisamente
para eso. Lo que se puede decir es lo medido: **en esta ventana, cero**.
Nada más.

> Una explicación causal que no se ha medido no es una explicación: es una
> historia que encaja con los datos que se han mirado y con los que no. Y
> una historia escrita en un `.md` se hereda: el próximo que lea esto la
> repitirá sin mirar.

---

## 3. La consecuencia

**El AUC preflop no se puede calcular con esta base.** No es que falte el
número, y no es un problema de código del camino de equity, que está
implementado y medido en
[`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md).

El instrumento además **se niega a hacerlo**: `ACCIONES_JUGADAS` descarta
y cuenta los folds, de modo que la población preflop que produce es **0**,
con el motivo en el informe. Se prefierio que un instrumento se quede en
cero diciendo por qué a que produzca veintitrés observaciones que no
responden a la pregunta.

**Y esto no mueve `DEFAULT_ALPHA`.** Sigue en **2,0**, por el argumento (3).
Ni el argumento (2) ni el AUC dependían de él.

---

## 4. Qué lo desbloquearía

**No** hace falta un recorder que capture el momento de la decisión —eso se
dijo al principio y no es lo que falta—. Lo que falta, medido, son dos
cosas distintas:

1. **Que el registro de una mano jugada en preflop lleve las cartas de los
   demás jugadores.** 82 de las 83 no las tienen: solo la del héroe. Sin
   ellas no hay showdown posible, ni verificable ni por fold, y sin
   ganador verificable no hay etiqueta. Mientras el recorder solo conserve
   las cartas del héroe cuando la mano muere en preflop, esta población no
   se puede construir.

2. **Que los dos sitios donde vive el board sean uno solo.** En 2 de las 83
   el board está en `streets.*.board` y `comunitarias` está vacío, y
   `board_completo()` lee el que no se rellena. Dos representaciones del
   mismo campo, y el filtro depende de cuál se rellene.

El punto 1 es un cambio de recorder. El punto 2 es una inconsistencia del
registro y se arregla decidiendo cuál de las dos representaciones es la
buena. **Ninguno de los dos es un cambio de `motor/`.**

**Y con las dos cosas sigue sin haber AUC**, por el motivo real:

> La población desbloqueada sería de **una sola clase**, porque el corte es
> la **última** acción del héroe. Para que ese corte sea una acción jugada
> en preflop, la mano tiene que **terminar ahí**: si el héroe siguiera, habría
> una acción posterior y el corte se movería de calle. Y si termina ahí con
> acción jugada, el héroe **gana**.

Es una propiedad **de cómo se define el corte**, y por eso tiene arreglo:
un corte que fuera *la primera decisión* del héroe en lugar de *la última*
traería las manos en las que jugó y perdió —que son las que hacen falta para
tener la clase negativa—. Ese sí es un cambio de definición, y hay que
decidirlo antes de hacerlo, porque cambia la muestra.

Que hoy haya **cero** derrotas no es una imposibilidad del poker: es cómo
se comporta **este** registro, donde además las acciones de los demás
jugadores faltan a menudo —de las 83, 82 no tienen ninguna carta de otro
jugador—. En un conjunto donde la acción del héroe se guardara aunque
después perdiera, habría las dos clases.

Y para que la pregunta merezca la pena hacen falta más manos: hoy son 83
en 877, y el héroe foldea en 554 de los 637 cortes preflop de la ventana.
**El fondo del problema no es la métrica.**

---

## Cómo reproducirlo

```
python tools/auditar_representatividad.py
```

§0 comprueba el detector de cartas y se niega a seguir si falla. §6 tiene
los dos recuentos con nombre —`b/c/r` (acciones) y `b/c/r/x` (población B)—
que no se pueden confundir. §7 tiene el filtro a filtro y el contrafactual.

El script **no escribe nada**.

Y hay un test que fija el hecho, para que si algún día la base cambia
alguien mire **por qué** antes de quitarlo:
`tools/test_fold_no_es_poblacion.py::test_en_la_poblacion_real_no_entra_ninguna_mano_preflop`.