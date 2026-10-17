# LIMITACIÓN PERMANENTE — la población B en preflop es vacía

> `revision_1`, tarea 2: registrar el hallazgo como limitación permanente.
> Esto no es un bug. Es una propiedad de los datos, y tiene que estar
> escrito donde no se pierda, porque la próxima persona que vaya a medir un
> AUC preflop va a perder dos días descubriéndolo.

---

## 1. El hecho

**En esta base, la población B no tiene NINGUNA decisión preflop.** No «de
una sola clase»: ninguna. Hay 83 cortes preflop con acción jugada, y **0**
de ellos están en la muestra etiquetada.

> **Cuarta corrección de esta cifra, y la de fondo.** Se escribió antes que
> eran «78 con etiqueta, todas victorias, una sola clase» y que la
> población estaba «bloqueada, no vacía». Todo eso venía de **recalcular la
> etiqueta** en lugar de leerla. Las 83 que se contaban como victorias están,
> una a una, **fuera de `muestra()`**: no son «positivas sin etiqueta», son
> manos sin etiqueta. Medido identificador a identificador en
> [`REPRESENTATIVIDAD_23.md`](REPRESENTATIVIDAD_23.md) §6.3.

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

> **Tabla rehecha con la etiqueta de `muestra()`.** La anterior venía de
> una réplica de los filtros y contestaba una pregunta que no era la de
> este proyecto: de dónde se cae cada corte por la *réplica*, y no si la
> mano tiene etiqueta. Retirada entera.

| de las 83, motivo por el que no son observación | |
|---|---:|
| **sin etiqueta en la muestra** | **83** |
| — de ellas, **ganan por fold verificable** | **77** |
| — con etiqueta | **0** |

Y esa segunda fila es el error entero en una frase: **ganar por fold es
necesario y no suficiente**. El camino de fold verifica la victoria; la
etiqueta la da estar en `muestra()`, y de las 83 **ninguna** está.

**Y una consecuencia que no se había medido:** las 83 se caen **todas en el
mismo sitio**, y es el primero. Ninguna llega siquiera a los filtros: se
caen al leer la etiqueta. Los dos filtros que se adelantan existen y están
escritos más abajo, pero **no son la causa de este cero**, porque a ellos no
llega ninguna de las 83.

**La población está vacía, y no es por el filtro.** `gano_por_fold()`
funciona: verifica una victoria por fold sin las cartas de los demás. Lo que
no existe es la etiqueta, y no existe por un motivo anterior a cualquier
filtro:

> Si el héroe juega y la mano **se acaba ahí**, no se reparten cartas
> comunitarias. Sin board no hay ganador verificable. Sin ganador
> verificable no hay etiqueta.

Y el corte preflop, bajo el corte actual, **solo puede caer en una mano que
termina en el preflop**. De ahí el cero.

Los dos filtros que se adelantan existen, y son estos:

```python
if not board_completo(h):      continue   # <- 83 se caen aqui
if len(con_cartas(h)) < 2:     continue   # <- 82 se caen aqui
...
ok_fold, _mot = gano_por_fold(h, declarados)   # <- el unico que las acepta
```

> **Retirado, y con esto la cuarta corrección llega al último sitio donde
> quedaba cifra replicada.** Este documento decía: «las 78 son todas
> victorias, cero derrotas». **Medido: de las 83, cero con etiqueta.** No
> son 78 positivas y 0 negativas —**no hay ninguna observación**, y por eso
> no hay clase, y por eso `auc_de()` devuelve `None` y no `1,0`.

| de las 83, motivo por el que no son observación | |
|---|---:|
| **sin etiqueta en la muestra** | **83** |
| — de ellas, **ganan por fold verificable** | **77** |
| — **con etiqueta** | **0** |
| reparto (el AUC binario lo excluye) | 0 |

**Ganar por fold verificable es lo que hacen 77 de las 83.** Y eso es
justamente lo que la etiqueta NO premia por sí solo: la etiqueta la da
`muestra()`, y de estas 83 ninguna está en ella.

**O sea: ganar por fold verificable es NECESARIO y NO SUFICIENTE.** El
camino de fold verifica la victoria; la etiqueta la da estar en `muestra()`;
y ninguna de las 83 está. Por eso **el orden de los filtros no es la
causa** —a él no llega ninguna de las 83, porque se caen antes, al leer la
etiqueta—, y por eso moverlo no produciría ni una observación: produciría
las mismas cero.

> **Y una corrección de vocabulario, que es también una corrección de
> fondo.** Se escribió que el AUC «daría 1,0 por definición». **Eso es
> falso, y el código del proyecto ya lo hacía bien:**
> `auditar_auc.auc_de()` devuelve **`None`**, y lo dice en su docstring —
> *«None si falta una clase»*. Medido: 78 positivas y 0 negativas dan
> `None`; el caso normal da 1,0; cero positivas y 12 negativas también da
> `None`.
>
> El valor correcto es **INDEFINIDO**, no 1,0. `revision_2` tiene razón, y
> el documento estaba en contradicción con el instrumento del propio
> proyecto.

**El motivo real, y cabe en una frase.** El corte en la última acción
del héroe, cuando cae en preflop, **solo puede caer en una mano que
termina en el preflop**. Y una mano que termina en el preflop no tiene
board; sin board no hay ganador verificable; sin ganador verificable
`muestra()` no le pone etiqueta.

No es un problema de clase. No es un problema de filtros. No es un problema
de «faltan cartas de los demás». Es que la mano no llega a tener board.

Y el lado que sí funciona, para que el contraste quede escrito: el
**postflop** con etiqueta son **48** observaciones, **20 positivas y 28
negativas**. Las dos clases. Ese es el AUC que se publica.

### La corrección de fondo: la etiqueta se lee, no se calcula

Todo lo de arriba viene de una cosa: **la etiqueta estaba mal.** Y estaba mal
porque no se leía, sino que **se calculaba**.

**La etiqueta se lee.** Esa es la regla, en activa y en presente, porque es
la que hay que poder citar sin parafrasearla.

Y no se calcula. Eso es lo que estaba mal, y es la razón de la corrección.

El filtro de la herramienta replicaba los de `calibrar.muestra()` para decidir
si una observación era viable, y en el camino de victoria por fold devolvía
`y = 1.0` sin mirar dos cosas: si la mano era un reparto, que `muestra()`
acepta y el AUC binario excluye; y si la mano estaba siquiera en
`muestra()`. De ahí el 78.

**Ahora hay una sola fuente de verdad: `muestra()`.** El filtro decide si la
observación es viable y por qué no lo es; `muestra()` decide el valor.

Y esa separación no es de estilo, es el contrato. Antes `y` y el motivo
estaban **acoplados**: `y` era `None` siempre que la observación no era viable.
Con eso, una mano que **tiene** etiqueta y no es viable devolvía `None`, y eso
es indistinguible de «no tiene etiqueta».

| lo que devuelve `y` | lo que significa | antes |
|---|---|---|
| `None` | la mano no está en la muestra, o es un reparto | las dos cosas, y también «tiene etiqueta pero no era viable» |
| `0.0` / `1.0` | la etiqueta de `muestra()` | igual |

**Ahora son independientes.** `y` es la etiqueta y no depende del juicio de
viabilidad. `motivo` es el juicio, y ya no puede tocar `y`.

#### Y lo que se midió antes de cambiar nada

| | |
|---|---:|
| etiquetas **inventadas** (no hay etiqueta y devuelve una) | **0** |
| etiquetas **distintas** de las de `muestra()` | **0** |
| etiquetas **perdidas** (la hay y devuelve `None`) | **0** |

En una frase, y para que se pueda citar sin parafrasear: **hoy la medición da
0 inventadas, 0 distorsionadas y 0 perdidas.**

**Y aquí está el matiz que hay que leer con esos ceros: hoy no se pierde
ninguna, y por eso el contrato estricto pasaba. Pasaba por suerte.**

Si mañana una mano etiquetada deja de ser viable, el código antiguo la habría
devuelto como `None`, sin rastro y sin motivo. El arreglo no es que hoy no se
pierda ninguna: es que **ya no se puede perder aunque las hubiera**. El contrato se sostiene por construcción.

Y no por coincidencia.

Y esa es la diferencia entre «el test pasa» y «el contrato se sostiene».

### Y `y = 0`: las manos que el héroe pierde, por dos vías

> **Lo que se decía, y lo que se retira:**
>
> «`y = 0` no es de los folds, es de los folds que no están en `muestra()``

Y un encabezado como el de arriba es el PEOR sitio para una frase que se
retira: es lo primero que se lee y lo último que se olvida. Si solo se lee
el título, el documento afirma lo contrario de lo que sostiene.

Un enunciado que se ha escrito aquí y que hay que corregir, porque se dio por
bueno sin medirlo, y al medirlo salió falso en las dos partes.

| | |
|---|---:|
| manos con un **fold** del héroe | **651** |
| — de ellas, **en** la muestra etiquetada | **108** |
| — de ellas, fuera de la muestra | 543 |
| manos con **`y = 0`** | **137** |
| — de ellas, **con** fold | **108** |
| — de ellas, **sin** fold: showdown perdido | **29** |

> **Lo que se decía, y lo que se retira:**
>
> «`y = 0` no es de los folds, es de los folds que no están en `muestra()`»

Y las dos mitades se caen:

- **La primera mitad** — la que excluye a los que no están en
  `muestra()`. No: hay **108 folds que sí están en la muestra** y reciben `y = 0` legítimo. Un fold es
  *suficiente* para `y = 0`, y si la mano está en la muestra, se le pone.
- **La segunda mitad** — la que excluye a los folds. No: de las 137
  manos con `y = 0`, **29 no tienen fold**: son showdowns perdidos.

> Y una cosa de forma, que sale de arreglar esto: el enunciado se escribe
> **una vez, y como cita**. Repetirlo para desmentir cada mitad es prosa
> buena y mala a la vez — el escáner ve tres afirmaciones, y basta una mal
> para que el documento se contradiga. Una retracción no repite lo que retira:
> lo señala una vez y luego trabaja con «la primera mitad» y «la segunda».

**Lo que sí es cierto, y es otra cosa:** `y = 0` significa *el héroe pierde*, y
eso pasa de dos maneras —**108 folds** y **29 showdowns perdidos**. El fold es
suficiente y no necesario.

Y esto es lo que explica por qué la población B del AUC **excluye** los folds:
no porque su etiqueta sea distinta —es `0`, y es una etiqueta legítima—, sino
porque **no hay showdown que verificar**.

Que es la misma distinción de la §4.3, aplicada a otro sitio: una cosa es lo
que el dato **dice** y otra es lo que el dato **permite concluir**. Aquí
también se estaban confundiendo. La etiqueta del fold es válida; su
observabilidad no.

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

1. **Que el registro traiga las cartas de los demás jugadores** — pero solo
   como condición de los **showdowns**, no como condición de todo.

   > **Se corrige.** Este documento decía antes que sin las cartas de los
   > demás «no hay showdown posible, ni verificable ni por fold». Eso es
   > falso, y está medido: **`gano_por_fold()` verifica la victoria por
   > fold sin ellas**, y funciona en **77 de las 83**. Las cartas de los
   > demás hacen falta para el camino de **showdown**, y nada más.
   >
   > En la población medida hay **una sola** mano con showdown verificable,
   > `H_0485`, y es precisamente la que sí trae las cartas de los demás.
   > Las otras 82 no las tienen, y 77 de ellas se etiquetan igual.

2. **Que los dos sitios donde vive el board sean uno solo.** En 2 de las 83
   el board está en `streets.*.board` y `comunitarias` está vacío, y
   `board_completo()` lee el que no se rellena. Dos representaciones del
   mismo campo, y el filtro depende de cuál se rellene.

> Y una lectura que cambia el diagnóstico: de las 83, **5 siguen sin
> etiqueta posible aunque se salten los dos filtros** —4 por fold no
> verificable y 1 por showdown sin las cartas de los demás—, y 1 de esas 4
> tiene dos jugadores sin foldear, o sea un registro incompleto y no una
> límite de información.

El punto 1 es un cambio de recorder. El punto 2 es una inconsistencia del
registro y se arregla decidiendo cuál de las dos representaciones es la
buena. **Ninguno de los dos es un cambio de `motor/`.**

**Y con las dos cosas sigue sin haber AUC**, por el motivo real:

> La población desbloqueada sería de **una sola clase**, porque el corte es
> la **última** acción del héroe. Para que ese corte sea una acción jugada
> en preflop, la mano tiene que **terminar ahí**: si el héroe siguiera, habría
> una acción posterior y el corte se movería de calle. Y si termina ahí con
> acción jugada, el héroe **gana**.

Es una propiedad **de cómo se define el corte**, y por eso tiene arreglo.
**Pero antes de afirmar que el arreglo funciona, se ha medido**, porque
`revision_2` tiene razón en que una hipótesis razonable no es una
medición:

> **Tabla rehecha con la etiqueta de `muestra()`.** La anterior venía de
> la réplica de los filtros y contaba manos sin etiqueta como si fueran
> victorias. Retirada entera.

| | última (lo que hay) | primera |
|---|---:|---:|
| cortes preflop de población B | 83 | 378 |
| — **con etiqueta** | **0** | **67** |
| — `y = 1` | 0 | **20** |
| — **`y = 0`** | 0 | **47** |
| postflop con etiqueta | **48** | **0** |

La hipótesis **se sostiene**: con el corte en la primera decisión hay
**67** observaciones preflop con etiqueta, **20 positivas y 47 negativas**,
que es justo lo que a un AUC binario le hace falta.

> Antes decía «270 observaciones con etiqueta y 54 derrotas». Eran las
> cifras de la réplica. Con la etiqueta leída, 67 y 47.

Y **no es un arreglo**, y esto hay que decirlo porque es lo que se le
criticó a B cuando se propuso. Lo que B1 hace **no es añadir el preflop al
objetivo**: es **sustituir una población por otra**.

| | A · última, lo que hay | B1 · primera, la alternativa |
|---|---:|---:|
| preflop con etiqueta | **0** | **67** |
| postflop con etiqueta | **48** | **0** |
| total | 48 | 67 |

Los 67 no se suman a los 48: los 48 **desaparecen**. Y lo que el AUC mide
hoy es justamente el postflop.
criticó a B cuando se propuso. Lo que B1 hace **no es añadir el preflop al
objetivo**: es **sustituir una población por otra**.

| | A · última, lo que hay | B1 · primera, la alternativa |
|---|---:|---:|
| preflop con etiqueta | **0** | **67** |
| postflop con etiqueta | **48** | **0** |
| total | 48 | 67 |

Los 67 no se suman a los 48: los 48 **desaparecen**. Y lo que el AUC mide
hoy es justamente el postflop.

Y con eso queda **un** problema, y no dos: el corte en la última acción,
cuando cae en preflop, solo puede caer en una mano que **termina** en el
preflop; y esa mano no tiene board; sin board no hay ganador verificable; sin
ganador verificable `muestra()` no le pone etiqueta.

> **Se retira la separación en dos problemas.** Este documento decía:
>
> | | problema | se arregla | qué da |
> |---|---|---|---|
> | 1 | **bloqueo de etiquetado**: el orden de los filtros deja fuera etiquetas verificables | moviendo filtros | 78 y 0 — que no es un AUC |
> | 2 | **sesgo de la selección del corte**: la última acción no trae derrotas preflop jugadas | cambiando el corte | 270 y 54 — las dos clases |
>
> **Arreglar el 1 no arregla el 2.**
>
> Era una distinción inventada sobre una **réplica equivocada de los
> filtros**. La columna 1 describía lo que hacía la réplica; la columna 2, lo
> que hacía la otra. Con la etiqueta **leída** de `muestra()`:
>
> | | |
> |---|---:|
> | cortes preflop de población B | 83 |
> | **con etiqueta** | **0** |
>
> No hay 78 etiquetas bloqueadas: no hay **ninguna** etiqueta. Y no hay un
> problema de clase: no hay **ninguna** clase.
>
> **Es un problema, y cabe en una frase:**
>
> > El corte en la **última** acción del héroe, cuando cae en preflop, solo
> > puede caer en una mano que **termina** en el preflop. Y una mano que
> > termina en el preflop no tiene board; sin board no hay ganador
> > verificable; sin ganador verificable `muestra()` no le pone etiqueta.
>
> Y la hipótesis del corte en la primera decisión se explica distinto de
> lo que se escribió. No es que «traiga las negativas»: es que **trae las
> manos que no terminan en preflop**. Ahí la mano continúa, se reparten
> cartas, hay board y hay etiqueta. 67 observaciones, 20 positivas y 47
> negativas.


Es **un** problema, y ya está escrito más arriba. La hipótesis del
corte en la primera decisión sigue siendo lo que era: una alternativa
medida que cambia la definición del objetivo, y que por eso va medida y no
implementada. Lo que corresponde es **decidirla**, y eso necesita un
contrato, y el de la muestra está firmado.

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