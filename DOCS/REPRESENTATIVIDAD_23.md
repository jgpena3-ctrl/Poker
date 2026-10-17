# REPRESENTATIVIDAD_23 — las 23 manos preflop no son lo que parecían

> **Este documento cierra la pregunta del AUC preflop: no se calcula, y la
> razón es el hallazgo de la §1, no la falta de tiempo.**
>
> Tarea 2 de `revision_1`: auditar si las 23 representan las decisiones
> preflop del motor, o son un subconjunto sesgado. «Si hay un sesgo, dilo.
> Si no lo hay, también».
>
> **Respuesta corta: sí hay un sesgo, y es total. Las 23 no son una muestra
> de las decisiones preflop del motor: son la población de los *folds*
> preflop del héroe. Las decisiones preflop que sí son de la población del
> AUC no existen en este conjunto.**
>
> Y como consecuencia, las Tareas 3, 4 y 5 de `revision_1` quedan respondidas
> sin número: el AUC «con preflop incluido» no se calcula, y en la §6 está
> por qué, medido.

Reproducible con `python tools/auditar_representatividad.py`, que **no
escribe nada**.

---

## 1. Lo que son las 23

El corte de decisión es `corte_de_decision()`: la **última** acción del
héroe, y acepta `'b'`, `'c'`, `'r'`, `'f'` y `'x'`.

| | validación | calibración |
|---|---:|---:|
| cortes preflop | 23 | 75 |
| acción del héroe en el corte | **`f` en los 23** | **`f` en los 75** |
| su etiqueta | `y = 0` en los 23 | `y = 0` en los 75 |

Las 23 de validación tienen `y = 0`. Las 23. Las 75 de calibración también:
**98 de 98**. Eso no sale por azar, y no es que el héroe pierda siempre.

Un *fold* tiene `y = 0` **por construcción**: el que foldea no puede ganar
el bote. Y la población del AUC es **B**, «el héroe **continúa** o
**checkea**» (`CONTRATO_L_SEC.md` §8). Un fold no es ninguna de las dos
cosas.

> Estas 23 manos están fuera de la población declarada, y con `y = 0`
> garantizado. Meterlas en un AUC no añade manos: añade la regla de
> selección.

## 2. La cadena de selección: no descarta nada

| | universo | corte | **juega** | cartas | rival | perfil |
|---|---:|---:|---:|---:|---:|---:|
| validación | 41 | 23 | **0** | 0 | 0 | 0 |
| calibración | 119 | 75 | **0** | 0 | 0 | 0 |

Ni una sola mano se cae por falta de cartas del héroe, por villano
identificable o por perfil en el modelo. El único filtro que descarta
algo es el de la **acción**, y descarta el 100 % de los dos grupos.

Esto importa para leer la tabla: el sesgo **no lo introduce el
instrumento**. No hay una criba escondida que se quede con las manos
fáciles. La población entera de cortes preflop de validación es de folds,
y el instrumento la tomaba entera.

## 3. Criterio, declarado antes de mirar

Se declararon tres umbrales: C1, ninguna proporción de spot separada de
la referencia en más de 10 pp; C2, el villano más frecuente no pasa del
doble; C3, la proporción de premium no se separa en más de 10 pp.

Y se escribió, **antes de calcular**, qué no se puede concluir pase lo que
pase:

> Con n = 23 esto no puede detectar un sesgo pequeño. Que pasen C1, C2 y C3
> significa «no se detecta sesgo con esta muestra», no «no hay sesgo».

Referencia: los cortes preflop de **calibración** (75), un grupo
**disjunto**. La partición es `sha256(hand_id) % 10 < 3`
(`tools/calibrar.py:66`): depende del identificador, no del contenido, así
que calibración es una muestra del mismo proceso que validación.

> Un error de esta auditoría, escrito: la primera versión comparó las 23
> contra **la ventana entera**, que contiene las propias 23. Un grupo
> comparado consigo mismo da «separación 278 pp, p = 1,0». La referencia
> tiene que ser disjunta.

## 4. C1 — mezcla de spot: **no se detecta sesgo**

| spot | A (23) | B (75) | dif. | sigmas |
|---|---:|---:|---:|---:|
| `facing_3bet` | 34,8 % | 16,0 % | +18,8 pp | 1,7 |
| `facing_open` | 39,1 % | 61,3 % | −22,2 pp | −1,9 |
| `no_raise` | 26,1 % | 22,7 % | +3,4 pp | 0,3 |

Mayor separación observada: **22,2 pp**. **p por permutación = 0,1145**
(20 000 barajados de la etiqueta, semilla 11).

El umbral declarado de 10 pp **fallaba** en dos de tres spots. Pero con
n = 23 el error típico de una proporción está entre 10 y 10 pp: el umbral
estaba más allá del ruido. Un criterio sin calibrar contra el tamaño de la
muestra no es un criterio, es una moneda.

**C1 no se pasa, y el contraste dice que la diferencia no se distingue del
azar.** Se reporta el fallo del criterio declarado y el resultado del
contraste, los dos. No se cambia el umbral después de ver el número: eso
sería el error que este bloque lleva tres veces cometiendo.

## 5. C2 y C3

**C2 — villanos: el umbral falla, y no importa.**

| | A (23) | B (75) |
|---|---|---|
| más frecuente | DominoSaurio, 3 de 23 (13,0 %) | Franco1603, 4 de 75 (5,3 %) |
| villanos distintos | **20 de 23** | 48 de 75 |
| HHI | 0,059 | 0,026 |

Ratio 2,45×, y el umbral de «no pasar del doble» **falla**. Pero son
**tres** manos, y en el grupo A hay **20 villanos distintos para 23 manos**:
la concentración es baja en términos absolutos. Las tres son `H_0041`,
`H_0110`, `H_0121`.

**C3 — cartas del héroe: sin señal, que no es lo mismo que sin sesgo.**
Premium 0 % en ambos (0,0 pp); pares 0 % contra 1,3 % (−1,3 pp, −1,0 σ);
suited 30,4 % contra 21,3 % (+9,1 pp, 0,9 σ).

> Y aquí hay que decir la segunda cosa, que es la que importa: **los dos
> grupos tienen CERO manos premium.** No hay ni una sola. Las 23 son
> `43 53 54 62 65 82 86 86 86 92 93 A6 J7 K2 K9 Q3 Q3 Q7 Q8 T3 T4 T6 T7`:
> sueltas, sin palo, y **ni un par**. En calibración, 75 manos y un único
> par, el `66`.
>
> C3 compara 0 % contra 0 %. Eso no es «sin sesgo», es **sin señal**: no hay
> nada que discriminar porque la población es de manos flojas. Y es lo
> esperable: son 554 folds de 637 cortes preflop, casi todos de manos
> que no se juegan. Un criterio que compara dos ceros no ha comparado nada, y
> decirlo de otro modo es como se publica un número que no significa
> nada.

> Y aquí el criterio **pasaba en falso**, dos veces seguidas. El detector
> comparaba `s[:2]` con `'AA'`, `'KK'`… sobre cadenas como `'Qh3c'`, donde
> `s[2:4]` es `'3c'` y nunca puede ser un par de rangos: devolvía `False`
> **siempre**. Después el par se montaba como `'Q3'` en vez de `'AK'`, y
> seguía devolviendo `False` siempre.
>
> Y una tercera, que encontró `revision_2`: el par se ordenaba con
> `sorted()`, que es **alfabético**, y los premiums son `'KJ'`, `'AK'`…
> Con `sorted()`, `'K' > 'J'` es `'JK'`, que no es `'KJ'`. De los nueve
> premiums, **`KJ` era el único inalcanzable**; los otros ocho llegaban por
> casualidad, porque sus letras ya salen en orden alfabético. Un detector
> que funciona en ocho de nueve casos parece correcto.
>
> Un criterio que no puede fallar no es un criterio. Lo que lo destapó fue
> una tabla de casos con cartas de verdad —`'AhKs'`, `'KhJs'`,
> `'QcJc'`, `'ThTs'`— escrita *antes* de mirar el resultado. Y esa tabla,
> la tercera vez, tenía **mis expectativas** mal, no el detector: tres de
> ocho casos fallaron porque yo había escrito `'KhJs'` esperando *suited*
> cuando es sin palo. El detector acertaba las tres y la tabla de pruebas
> fallaba las tres: el problema estaba de mi lado, en las expectativas.

## 6. Lo que hay de verdad, y si el preflop cabe

La última acción del héroe en las 877 manos fiables:

| calle | b | c | r | **f** | x | total |
|---|---:|---:|---:|---:|---:|---:|
| preflop | 30 | 3 | 48 | **554** | 2 | 637 |
| flop | 12 | 1 | 1 | 46 | 2 | 62 |
| turn | 37 | 1 | 0 | 28 | 1 | 67 |
| river | 35 | 16 | 3 | 22 | 31 | 107 |

- Decisiones preflop **jugables** (`b`/`c`/`r`) en toda la ventana: **81**.
- De las cuales **tienen etiqueta: 0**.
- Checks preflop: **2**. Con etiqueta: 0.

> **La población B en preflop no es pequeña: en este conjunto es vacía.**

### 6.1 Por qué no hay etiqueta — y una explicación que era falsa

> **Se retira.** Este párrafo decía antes:
>
> «Si el héroe **juega y gana**, vuelve a actuar, y entonces el corte se
> mueve de calle. Para que el corte se quede en preflop con una acción
> jugada, la mano tiene que terminar ahí mismo. […] Las dos cosas a la vez
> no se dan.»
>
> `revision_2` dijo que era demasiado fuerte. Era más que eso: **era otra**.
> Medido, las dos mitades son falsas.

Lo que ocurre, filtro a filtro, en las 83:

| | |
|---|---:|
| `b/c/r` (acciones) | 81 |
| `x` (checks) | 2 |
| con etiqueta | **0** |

**Las 83 se caen en el mismo sitio: el primer filtro de `muestra()`.**

| dónde está el board | |
|---|---:|
| `comunitarias.river` con cartas | 0 |
| el board **sí** está en `streets.*.board`, `comunitarias` vacío | 2 |
| no hay board en ninguna parte | 81 |

`board_completo()` exige `len(comunitarias.river) >= 1`, y se comprueba
**antes** del camino de victoria por fold. O sea que una victoria por fold
limpia no puede tener etiqueta: el board se pide antes de llegar al único
camino que la aceptaría.

Y el caso que desmonta mi explicación, `H_0043`:

```
preflop   UTGf MPc COc BTNb SBf BBf MPf COf
winner    ['p1']        showdown  {'winner1': 'BTN (Jarduan)'}
comunitarias  {'flop': [], 'turn': [], 'river': []}
```

La mano **termina en preflop** porque todos foldean a la apuesta del héroe,
y el héroe **gana por fold** con ganador declarado. El corte se queda en
preflop por eso —no porque el héroe vuelva a actuar— y no hay board porque
no se repartieron cartas comunitarias, que es lo correcto.

> **Este contrafactual se retira, y la tabla con él.** Preguntaba qué
> pasaría si los dos filtros se comprobaran *después* del camino de fold.
> La pregunta estaba mal: la etiqueta no la da el orden de los filtros,
> la da estar en `muestra()`.

| de las 83, motivo por el que no son observación | |
|---|---:|
| **sin etiqueta en la muestra** | **83** |
| — de ellas, **ganan por fold verificable** | **77** |
| — **con etiqueta** | **0** |
| reparto (el AUC binario lo excluye) | 0 |

**Y el contrafactual con la pregunta correcta**, que sí tiene respuesta
interesante: de las 83, **77 ganan por fold verificable**. O sea que el
camino de fold funciona y el orden de los filtros **no es la causa** del
cero: a él no llega ninguna de las 83, porque se caen antes, al leer la
etiqueta.

> **Y aquí se retira una conclusión que era falsa.** Este documento decía
> antes «ni con otra regla: una observación no es un AUC». Lo único cierto
> es la conclusión; el número y el motivo no lo eran.
> `gano_por_fold()` verifica la victoria por fold **sin** las cartas de los
> demás —por eso existe—, así que la población **no está vacía: está
> bloqueada** por dos filtros que se adelantan a ese camino.
>
> **Y aquí se retira lo que decía este párrafo.** Se escribió que
> desbloqueada daría «78 victorias contra 0 derrotas» y un AUC indefinido.
> **El 78 estaba mal.** Venía de recalcular la etiqueta en vez de leerla.
>
> Con la etiqueta de `muestra()`: **cero**. De los 83 cortes preflop de
> población B, ninguno está en la muestra etiquetada. No es un problema de
> clase: **no hay ninguna observación aplicable**.
>
> La razón, que ya estaba medida en la §6 y no se había conectado: si el
> héroe juega y la mano se acaba ahí, no se reparten cartas; sin board no hay
> ganador verificable; sin ganador verificable no hay etiqueta. Y el corte
> preflop, bajo el corte actual, **solo cae en una mano que termina en
> preflop**.
>
> Y el otro camino está **medido**, no afirmado: con el corte en la
> *primera* decisión hay **67** observaciones con etiqueta, **20 positivas y
> 47 negativas**.
>
> > Antes este párrafo decía «con el corte en la primera decisión hay **270**
> > observaciones con etiqueta, **216 victorias y 54 derrotas**». Retirado:
> > con la etiqueta leída son 67, 20 y 47.
>
> Es un cambio de la definición del objetivo, así que va medido y no
> implementado. Detalle en
> [`LIMITACION_PREFLOP_AUC.md`](LIMITACION_PREFLOP_AUC.md) §4.

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

### 6.2 Un problema, y su enunciado

`revision_2` pide que no se confundan, y tienen nombres distintos:

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

La **hipótesis** de que el corte en la primera las trae se ha medido y **se
sostiene**: **67** observaciones con etiqueta, **20 positivas y 47 negativas**,
frente a las **0** del corte en la última. No está implementada, y no se
implementa aquí: es un cambio de la definición del objetivo y va en un
contrato.

> Antes decía «270 con etiqueta, 216 victorias y 54 derrotas, frente a 78,
> 78 y 0». Las tres cifras venían de la réplica. Con la etiqueta leída: 67,
> 20 y 47 frente a 0.

**Y que se sostenga no la convierte en un arreglo.** Lo que hace B1 **no es
añadir el preflop al objetivo**: es **sustituir una población por otra**.

| | A · última, lo que hay | B1 · primera, la alternativa |
|---|---:|---:|
| preflop con etiqueta | **0** | **67** |
| postflop con etiqueta | **48** | **0** |
| total | 48 | 67 |

Los 67 no se suman a los 48: los 48 **desaparecen**. Y lo que el AUC mide
hoy es justamente el postflop.

**Y el motivo por el que el preflop no aporta nada, que es la misma causa que
en el corte en la última**: una mano que **termina** en el preflop no tiene
board; sin board no hay ganador verificable; sin ganador verificable
`muestra()` no le pone etiqueta. Ganar por fold verificable es **necesario
y no suficiente**: de las 83 cortes preflop, **77 ganan por fold** y **ninguna
tiene etiqueta**. El camino de fold verifica la victoria; la etiqueta la da
estar en `muestra()`.

> No se cambia nada. `board_completo()` es parte de una muestra firmada en
> `CONTRATO_L_SEC.md`: moverlo cambia los 160, la partición, el modelo
> ajustado y el AUC ya publicado. Lo que se mide aquí es si la pregunta
> *sería* respondible con otra regla.
>
> **Y la respuesta es que no, pero no por lo que se pensaba.** No por
> falta de manos: por falta de la **clase negativa**. Detalle y qué lo
> arreglaría en [`LIMITACION_PREFLOP_AUC.md`](LIMITACION_PREFLOP_AUC.md) §4.

## 7. Conclusión

**Las 23 no son representativas de las decisiones preflop de la población
B, porque las decisiones preflop de la población B no existen en este
conjunto.** Son representativas de otra cosa, y esa cosa está bien
definida: los folds preflop del héroe.

Sobre los tres umbrales declarados, tal cual:

| | veredicto |
|---|---|
| C1 mezcla de spot | el umbral **falla**; el contraste dice **p = 0,11**, no se distingue del azar |
| C2 villanos | el umbral **falla** (2,45×); son 3 manos y hay 20 villanos distintos |
| C3 cartas | no se detecta sesgo — y el detector estaba roto, dos veces |

**El sesgo que sí existe no está en ninguno de los tres.** Está en la
población entera, y se mide en la §6: la población B preflop son cero
manos.

### Y lo que esto responde de `revision_1`

| tarea | estado |
|---|---|
| 1. Dejar terminar la corrida | **parada a 11 de 23**, con motivo medido (§8) |
| 2. Auditar representatividad | este documento |
| 3. AUC de la población completa | **no se calcula**, y no por falta de tiempo |
| 4. ¿Cambia algo para Fase D? | **no**, y por qué (§9) |
| 5. `AUC_PREFLOP.md` | **no escrito**, a propósito (§9) |

### 8. Por qué se paró la corrida

La corrida iba 11 de 23 con 430 equities por combo en caché. A 31,5 s por
combo —medido, y los 40 de una mano salen todos igual, ninguno patológico—
las 12 que faltaban eran **4,2 h de CPU** para producir la equity de 23
manos que no pueden entrar en el AUC: las 98 con etiqueta son todas folds,
y 23 de ellas son la mitad de una población que, con la etiqueta
correcta, tiene **cero** observaciones aplicables.

**El motivo real, y cabe en una frase.** El corte en la última acción
del héroe, cuando cae en preflop, **solo puede caer en una mano que
termina en el preflop**. Y una mano que termina en el preflop no tiene
board; sin board no hay ganador verificable; sin ganador verificable
`muestra()` no le pone etiqueta.

No es un problema de clase. No es un problema de filtros. No es un problema
de «faltan cartas de los demás». Es que la mano no llega a tener board.

La caché por combo se conserva. Si algún día la pregunta es otra —por
ejemplo, si la equity predice la fuerza del villano en un *fold*— el trabajo
sirve. Para **esta** pregunta no.

> El número de combos por mano subió de 13,3 s a 31,5 s en mitad de la
> corrida, sin que nada en el código cambiara y sin que hubiera otro
> proceso. No está explicado y queda abierto. No se escribe una causa que no
> se ha medido.

### 9. Lo que NO se escribe, y por qué

**No hay `AUC_PREFLOP.md`.**

`revision_1` dice: primero el número, después el documento. Aquí **no hay
número**, y no es que falte: es que el número se podría calcular y no
mediría nada. Con 23 observaciones de una clase garantizada por
construcción, el AUC compararía «la equity de manos que el héroe foldeó»
contra «la equity de manos que el héroe jugó». Eso es una propiedad de la
regla de selección, no de la equity.

Escribir el documento con un número dentro sería escribir el número y
adjuntarle una advertencia. Un número con una advertencia al lado se lee
como número.

**Fase D no cambia.** `DEFAULT_ALPHA` sigue en **2,0**, por el argumento (3):
es el titular y ninguna evidencia admisible justifica sustituirlo. Ni (2)
ni este AUC dependían de él, y este AUC **no se ha calculado**, así que
tampoco puede moverlo. Lo que este bloque añade es una razón más para no
tocarlo, no una razón para cambiarlo.

## 10. Lo que se cambió en el código

| | |
|---|---|
| `ACCIONES_JUGADAS = ('b', 'c', 'r', 'x')` | la condición de la población B, escrita con el motivo y el `CONTRATO_L_SEC` al lado |
| etapa `0_accion_jugada` | el descarte por fold se **cuenta y se nombra** (`CLAVE_FOLD`), no se pierde en un `sin_rango` anónimo |
| `huella_de()` | huella del rango efectivo en la identidad de la caché (ver el commit anterior) |
| `--solo-recaudo` | enseña los ceros donde antes enseñaba 23 |

La tabla por etapas ahora tiene una columna más, y enseña `23` en «corte» y
`0` en «juega». Antes de este filtro enseñaba `23` y `23`, y no se veía
dónde se perdía la población.