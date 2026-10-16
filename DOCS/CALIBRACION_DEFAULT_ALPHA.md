# CALIBRACION DE `DEFAULT_ALPHA` — NO CALIBRABLE CON LOS INSTRUMENTOS ACTUALES

## Veredicto

**`DEFAULT_ALPHA` se queda en `2.0`. No se calibra.**

> La conclusión correcta **no** es «2,0 es óptimo». Es **«con las métricas
> y la API disponibles no hay evidencia admisible para cambiar el 2,0
> actual»**. Lo segundo es una afirmación sobre los instrumentos; lo
> primero sería una afirmación sobre el poker que nadie ha medido.

No porque el parámetro no tenga recorrido, sino porque **no queda ningún
criterio admisible para cambiarlo**: la métrica primaria no puede
distinguir candidatos, y la secundaria no se puede calcular.

Eso se decidió midiendo, y hubo que **corregir dos veces el instrumento**
antes de poder decirlo. Las dos correcciones están abajo, y son la parte
importante de este bloque.

---

## 1. Lo que se ejecutó

```
python tools/auditar_importe_subida.py
python tools/auditar_muestra_lsec.py
python tools/calibrar.py particion --escribir
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 1.5 2.0 2.5 3.0 5.0
```

| | |
|---|---|
| ventana | 877 manos (`load_hands(reliable_only=True)`) |
| particion | versionada en [`PARTICION_FASE_D.md`](PARTICION_FASE_D.md), **sin cambios** |
| calibracion | 117 manos |
| validacion | 39 manos |
| eventos con cartas conocidas | 295 |

> `limp` esta sobreestimada en 25 eventos de 4561 (0,55 %). Las cifras de
> abajo **no son cifras limpias** (§5 de `FASE_D_PLAN.md`).

## 2. Las dos razones

### 2.1 `L_prim` no puede elegir una regularización

`L_prim` suma `log p` **solo sobre celdas observadas**, y ahí el prior es
pura dilución: `p = (cnt + alpha*prior) / (opp + alpha)`.

Medido celda a celda sobre las **256** celdas observadas:

| | celdas |
|---|---:|
| subir `alpha` **baja** `p` (empuja la pérdida arriba) | **224** |
| empujan al revés | **32** |

La curva no da una sola excepción entre `0,1` y `100`:

| `alpha` | `L_prim` |
|---:|---:|
| 0,1 | 0,232648 |
| 0,5 | 0,386909 |
| 1,0 | 0,528017 |
| **2,0** | **0,719521** |
| 3,0 | 0,847119 |
| 10,0 | 1,213548 |
| 100,0 | 1,568412 |

Ordena `alpha` por cuánto se diluyó el prior. Su «ganador» es el candidato
con menos regularización, que es el mismo decir que el más pequeño. **No
está eligiendo: está sumando.**

### 2.2 `L_sec` no se puede calcular

No hay API que devuelva la equity del motor en un punto de decisión
histórico. `asistente_live` construye la situación completa; no expone la
equity suelta.

Y aunque se pudiera, ya se midió que tiene que ganarle a un predictor
constante:

| | |
|---|---|
| reparto | el hero **gana 21 de 156** y pierde 135 (87 %) |
| Brier de un predictor constante `p = 0,135` | **0,1165** |

Un `L_sec` de 0,12 no es un resultado: es perder.

## 3. Las dos correcciones, que es lo importante

`revision_2` encontró dos P0 en el código de este bloque. Los dos eran
ciertos, y ninguno se habría visto sin medir.

### 3.1 La métrica estaba ciega de una forma que daba números

El grid de `p_matrix` no está indexado por acción ni por posición: está
indexado por **rango de carta** (`GRID_RANKS`). El código indexaba con
`g[ev.category, ev.pos]` — dos cadenas — y eso falla con `IndexError` en
las **295 de 295**. El `except` caía a `np.nanmax(g)`: el **máximo** del
grid.

Un máximo del grid es ≥ la probabilidad de cualquier celda, así que
**mejoraba la pérdida por construcción**. No era una métrica sesgada: era
una métrica que favorecía al candidato siempre, y que reaccionó a `alpha`
por el motivo equivocado.

Ahora usa `p_hand(...)` y **no hay fallback**: si el índice no vale,
`MedicionSinSentido` y código de salida 3. Un test recorre el árbol de
`l_prim` y falla si aparece un `nanmax` o un `max`.

### 3.2 La etiqueta no era la del hero

Había **dos definiciones cruzadas** de hero en el mismo fichero:

| | coincide con el hero en |
|---|---:|
| `'hero'` = `players[0]` (el id que usa `winner`) | 644 de 877 |
| «el primer jugador con cartas» | 845 de 877 |
| **el jugador nombrado en `learn.HERO_NAMES`** | **877 de 877** |

`'hero'` es **la butaca 0**, no una persona: en 232 de las 877 manos el hero
real está en otra butaca. Y «el primero con cartas» falla en 32, porque hay
manos donde el hero no tiene cartas.

Además, `showdown.winner1` se aceptaba por *existir y no parecer plural*,
sin comprobar a quién nombra. Ahora **se resuelve** contra la mesa: la
posición o el nombre tienen que estar.

| | antes | ahora |
|---|---:|---:|
| victorias del hero | 31 | **21** |
| Brier trivial | 0,1592 | **0,1165** |

El **recuento de la muestra no cambió**: 156 / 117 / 39, y la partición
versionada tampoco. Lo que cambió fue *de quién es la etiqueta*.

Como comprobación de que el instrumento sirve: cuenta **147** manos con dos
ganadores distintos en la base entera, que es exactamente lo que declara
`learn.py` (`winner con 2+ en la base entera: 179 -> 147`).

## 4. La premisa que resultó falsa

> *Afirmé que la monotonía era matemática. No lo es.*

32 de 256 celdas la resisten. Lo que se observa es que no llegan a dar la
vuelta al agregado en el rango medido. Un guardián que razona con una
premisa falsa es peor que ninguno, y por eso el §2.1.3 del plan lo dice
con su contraparte al lado.

La segunda premisa falsa era más grave y estaba en el código: *«el
índice es `g[category, pos]`»*. También es falsa, y esa sí salía en
números.

## 5. El sesgo de la muestra

| | |
|---|---|
| utilizables | **156** de 877 (17,8 %) |
| calibracion | 117 |
| validacion | 39 |
| exclusiones | 580 sin board · 134 con menos de 2 cartas · 5 sin texto de showdown · 1 sin ganador · 1 con el ganador sin cartas |

De las 7 manos con dos ganadores en la ventana, solo `H_0798` trae
`showdown.winner1`, y resuelve: `'BB (Jarduan)'`, `BB` está en esa mesa, y
ese jugador es el hero. Las otras 6 se quedan sin etiqueta, porque sin texto
no se distingue *«dos ganan»* de *«el registro se equivocó»*.

## 6. Hallazgo lateral: los ceros del grid

`p = 0` en **1 991 de 22 308** celdas, **también con `alpha = 20`**. La
causa no es la regularización: `data/preflop_matrices.json` tiene matrices
que **no son priors normalizados** — 86,7 % de sus celdas son 0 y cada
matriz suma entre 0,91 y 89,75, cuando una frecuencia sobre 1 326 manos
debería sumar 1.

Además **no contamina `L_prim` hoy**: de los 295 eventos de calibración,
**ninguno** cae en un cero, porque `L_prim` solo lee celdas observadas y
ahí `cnt >= 1`.

Diagnóstico en [`CEROS_PREFLOP_MATRICES.md`](CEROS_PREFLOP_MATRICES.md). No
se toca nada: cambiar cómo se interpretan esas matrices cambia el rango que
el motor da **en vivo**.

## 6.b La secundaria existe, y aun así `L_sec` no sale

[`tools/equity_de_mano.py`](../../tools/equity_de_mano.py) es lo que faltaba
para la §8. Reconstruye la situación desde la mano histórica y devuelve
`sit.equity`, **sin partida y sin captura**, siguiendo la misma cadena que
`asistente_live`: rango preflop → blockers → refinado postflop →
`situation`.

Que exista la equity del motor **no** depende del bote: en `situation()`,
`equity = wins + 0.5*ties` sale de las cartas y del rango, y el bote solo
alimenta `pot_odds` y `spr`. Eso es lo que permite que la herramienta exista
sin reconstruir las apuestas — una aritmética que, medida, **no converge**
(26 de 877 coinciden con `final_pot`).

Y funciona, comprobado por fuera:

| | |
|---|---:|
| equity mediana donde el hero **gana** | **0,7680** (n = 20) |
| equity mediana donde el hero **pierde** | **0,4309** (n = 38) |

La equity ordena. Un instrumento que devuelve números sin que nadie mire si
significan algo no vale nada; este sí significa algo.

**Y aun así `L_sec` no es usable, por dos razones medidas:**

1. **Cobertura del 37 %.** 58 de las 156 manos. Las 96 que faltan son
   **todas preflop**, y la causa es declarada en el propio motor:
   `hand_evaluator.evaluate_batch` dice *«board (b ids, 3..5)»* y sus subsets
   son de 5, 6 y 7 cartas. **No hay camino preflop.**
2. **La cobertura está sesgada.** Cubre **20 de las 21 victorias (95 %)** y
   solo **38 de las 135 derrotas (28 %)**. La tasa de victoria de lo
   cubierto es 34,5 %; la de la muestra, 13,5 %.

Medir `L_sec` sobre las 58 sería medir contra la base rate equivocada — que
es exactamente el error que §2.1.1.b dice que no se va a cometer otra vez.

> Dos tests escritos sobre esto: que la equity ordena, y que el sesgo de
> cobertura sigue ahí. Si el sesgo desaparece, hay que reescribir esta
> conclusión.

## 6.c Con el camino preflop, `L_sec` ya se calcula. Y **pierde**

`tools/equity_preflop.py` llena el hueco y las tres fugas quedan cerradas.
La cobertura sube a **158 de 160 (98,8 %)** y el sesgo **desaparece**:
cubre el 95 % de las victorias, el 100 % de los repartos y el 99 % de las
derrotas. Antes eran 95 % contra 28 %.

La equity sigue ordenando —**0,7673 donde gana, 0,4056 donde pierde,
diferencia +0,3618**— y aun así:

| | |
|---|---:|
| Brier con la mediana de la equity | **0,1783** |
| Brier del predictor constante | **0,1076** |

**Pierde contra decir «el hero va a perder»**, y no por poco. Con un 86 % de
derrotas en la muestra y la equity mediana del hero entre 0,41 y 0,77, la
equity **sobreestima** su chance.

O sea: `L_sec`, tal como el plan la define, **no es un criterio válido**
para seleccionar `alpha`. Se puede calcular y aun así mediría al motor por
debajo de una constante. Detalle en [`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md).

## 7. Las barreras, que son código

`tools/calibrar.py` no publica cuando no puede:

| situación | salida | qué hace |
|---|---:|---|
| `L_prim` no cambia con `alpha` | 3 | aborta, **no imprime la tabla** |
| `L_prim` no se puede medir | 3 | aborta |
| curva monótona | 2 | `NO SE CALIBRA` |
| `L_sec` no evaluable, aunque no sea monótona | 2 | `NO SE CALIBRA` |
| todo evaluable, sin `--aplicar` | 0 | dry-run |

Las dos primeras y la cuarta se las pidió `revision_2`. Antes, una curva no
monótona pasaba el control de la autovalidación y podía llegar a `--aplicar`
a elegir el mínimo de `L_prim` **sin ninguna métrica secundaria**.

Y `--aplicar` ahora **escribe de verdad**: `DEFAULT_ALPHA` es la única línea
que toca, en `motor/player_ranges.py`, y avisa de qué línea a qué línea.

## 8. Los dos motivos, y son independientes

Hay **dos** razones por las que `DEFAULT_ALPHA` no se calibra. Se
encontraron en bloques distintos y **ninguna depende de la otra**: si
mañana se arregla una, la otra sigue bloqueando.

### Motivo 1 — `L_prim` no puede elegir una regularización

`L_prim` suma `log p` **solo sobre celdas observadas**, y ahí el prior es
pura dilución. Celda a celda sobre las **256** celdas observadas:

| | celdas |
|---|---:|
| subir `alpha` **baja** `p` | **224** |
| empujan al revés | **32** |

La curva no da una sola excepción entre `0,1` y `100`. Ordena `alpha` por
cuánto se diluyó el prior, que no es una respuesta sobre el poker.

**Se arreglaría** con una métrica que scoree también las celdas no
observadas, o que mida en partición de validación.

### Motivo 2 — `alpha` mezcla contra algo que no es una probabilidad

`p = (cnt + alpha * prior) / (opp + alpha)`. `alpha` son pseudo-conteos: se
suman al lado de `cnt`, que sí es un conteo. Para que eso signifique algo,
`prior` tiene que estar en las mismas unidades.

No lo está:

| | |
|---|---:|
| celdas de `matrix` con `0` | **17 150 de 19 773 (86,7 %)** |
| suma de una matriz | de **0,91** a **89,75** |
| valores que aparecen | `{0, 0.25, 0.33, 0.5, 0.66, 0.75, 1.0}` |

Una frecuencia sobre las 1 326 manos posibles debería sumar 1. Estas suman
hasta 89,75. **No son priors normalizados**, así que `alpha * prior` no son
pseudo-conteos: son pesos de una escala que no se sabe qué es.

**Se arreglaría** decidiendo qué es `matrix` y normalizándola, o
cambiando el shrinkage para que no la use como si fuera una frecuencia.
Ver [`CEROS_PREFLOP_MATRICES.md`](CEROS_PREFLOP_MATRICES.md).

> **Los dos siguen vivos.** Arreglar la métrica no arregla la escala, y
> normalizar las matrices no arregla el hecho de que `L_prim` solo mire
> donde el prior molesta. Por eso `DEFAULT_ALPHA` sigue en `2.0` aunque se
> cerrara cualquiera de los dos.

## 8.b Qué reabriría esto

`DEFAULT_ALPHA` se puede recalibrar cuando **una** de estas sea cierta:

1. **La equity histórica cubre la muestra.** Ya existe
   ([`equity_de_mano.py`](../../tools/equity_de_mano.py)) y funciona, pero
   cubre el 37 % y sesgada hacia las victorias. Hacen falta **las dos**:
   que no sesgue, y que sea utilizable.
2. **La métrica primaria cambia de forma**: que scoree también las celdas
   **no observadas** —las que hoy son invisibles para `L_prim`— o que mida
   en partición de validación.

Mientras no: `2.0`, el valor que lleva desde el principio y el único con
justificación escrita (§1.2 del plan). Con un test que falla si alguien lo
mueve sin pasar por aquí.

## 9. Reproducir

```
python tools/auditar_importe_subida.py
python tools/auditar_muestra_lsec.py
python tools/calibrar.py particion
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 1.5 2.0 2.5 3.0 5.0
```

Ninguno escribe nada en `data/` ni en el motor. `particion --escribir` es lo
único que toca disco, y escribe un documento, no datos.