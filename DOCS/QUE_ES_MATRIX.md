# QUÉ ES `matrix` — sin resolver, y una cota medida

> ## CORRECCIÓN. Este documento antes afirmaba que `DEFAULT_ALPHA` **nunca**
> se calibra, y **retira esa afirmación.**
>
> La prueba que la sostenía estaba mal planteada. `revision_2` §2 tiene razón
> y la objeción es de fondo.

## Lo que estaba mal

Yo afirmaba:

```
sum_k S_k ≤ 1,   con S_k = la suma de las 169 celdas del prior de k
```

Y de ahí: *«el prior plano del fold son 0,15 × 169 = 25,35, se pasa 25 veces
por sí solo»*.

**La exclusión mutua es por mano**, no sobre las manos:

```
para cada celda c:   sum_k p_k(c) ≤ 1
```

Yo salté de *«para cada celda»* a *«sumando las 169 celdas»*. El contraejemplo
es exacto: si cada una de las 169 combinaciones tuviera 0,15 de hacer fold, la
suma daría 25,35 y **no habría contradicción**, porque cada celda describe una
mano distinta.

> El 25,35 era aritmética mía, no un defecto. Y `alpha · prior` no son
> pseudo-conteos porque las tablas no sumen 1: eso no se deduce.
>
> **La afirmación «`alpha` no es un parámetro de regularización» queda
> RETIRADA.** Y con ella la conclusión «no se calibra nunca».

## La prueba correcta, y el resultado

De la fórmula, sin discusión:

```
p_k(c) = (cnt_k(c) + α·prior_k(c)) / (opp(c) + α)

para cada celda c:  sum_k p_k(c) ≤ 1
  ⟺  N(c) + α·sum_k prior_k(c) ≤ opp(c) + α
  ⟺  sum_k prior_k(c) ≤ 1 + (opp(c) − N(c)) / α
```

> **La equivalencia que este documento tenía antes era falsa.** Escribía
> `sum_k prior_k(c) ≤ 1` como *equivalente*, y `revision_2` §2 tiene razón:
> es **suficiente**, y en estos datos también **necesaria**, pero no
> equivalente celda a celda.
>
> Y `opp` resultó ser un **array por celda**, no un escalar. El margen
> `min (opp(c) − N(c))` sobre las celdas medidas es **0**: hay celdas donde
> `N(c) = opp(c)`, o sea manos que siempre hicieron esa misma acción. Para
> esas el límite cae a 1 exacto, y por eso `S(c) ≤ 1` es necesaria aquí.
>
> En las celdas con margen > 0 el límite es **más laxo que 1**, y ahí no es
> equivalente. Esa diferencia es exactamente la que hace que el umbral de
> abajo sea un **límite observado** y no deducido.

**Por celda, sumando acciones.** Y en vez de álgebra, lo que el motor produce:

| | |
|---|---|
| celdas de `p_matrix` evaluadas | 2 028 |
| celdas que pasan de 1 | **0** |
| `p_matrix` máximo | **0,7571** (`TIBURON`, `no_raise`, `open`) |
| suma por celda sobre acciones excluyentes, máximo | **0,9500** |

> **No hay contradicción.** Con α = 2 el motor respeta el contrato de
> probabilidades por celda.

## Y esto sí es nuevo: hay una cota inferior para `alpha`

Barriendo `alpha` y mirando si la suma por celda se pasa de 1:

| `alpha` | `p` máximo | suma por celda | coherente |
|---:|---:|---:|:---:|
| 0,50 | 0,9227 | 1,0864 | **NO** |
| 1,00 | 0,8583 | 1,0333 | **NO** |
| 1,25 | 0,8300 | 1,0100 | **NO** |
| 1,30 | 0,8246 | 1,0056 | **NO** |
| **1,3636** | — | **1,0000** | ← el borde |
| 1,50 | 0,8038 | 0,9885 | sí |
| 2,00 | 0,7571 | 0,9500 | sí |
| 3,00 | 0,6812 | 0,8875 | sí |
| 200,00 | 0,1707 | 0,4671 | sí |

> ## CORRECCIÓN: esta cota **no existe**, y se retira.
>
> `revision_2` §2 encontró que `coherencia()` sumaba el **prior crudo** del
> fold (`_prior_grid('fold', …)` = 0,15 por celda) en vez de su
> **probabilidad** (`p_matrix(…, 'fold')`, que está suavizada con sus 221
> manos de conteo). Sumar 0,15 por celda fuera de la fracción es lo que
> producía el umbral.
>
> Con el fold bien tratado:
>
> ```
> sum_a p_a(c) = [ N(c) + α·S(c) ] / (opp(c) + α)
> ```
>
> y **`N(c) ≤ opp(c)` por construcción**: una mano no hace una acción más
> veces de las que tuvo oportunidades. El término del prior no empuja la suma
> hacia arriba al crecer `α`. Medido:

| `α` | coherencia |
|---:|---:|
| 0,05 | 0,9955 |
| 0,10 | 0,9910 |
| 0,25 | 0,9780 |
| 0,50 | 0,9577 |
| 1,00 | 0,9214 |
| **1,3636** | **0,9080** |
| 2,00 | 0,8625 |
| 5,00 | 0,7500 |

> **Ni un solo `α` la rompe.** El «1,3636» era un artefacto del bug.

**Y lo que se sostiene, y lo que es medida y qué es deducida.** La
diferencia importa: si alguien cambia `preflop_matrices.json`, la coherencia
puede romperse y no habría nada que lo avisara.

| | | |
|---|---|---|
| `N(c) ≤ opp(c)` | por construcción: una mano no hace una acción más veces de las que tuvo oportunidades | **deducida** |
| la coherencia por celda se cumple para todo `α ≥ 0` | malla de 99 puntos de 0,05 a 5,00 | **medida** |
| la coherencia es monótona **decreciente** | 98 de 98 pasos no crecientes | **medida**, y la derivada dice por qué |

### Por qué la suma decrece

```
d/dα [ (N + α·S) / (opp + α) ] = [ S·opp − N ] / (opp + α)²
```

La suma decrece **si y solo si** `S·opp < N`: el ritmo agregado del prior
por debajo del empírico. Eso **no** se deduce de `N ≤ opp`; se cumple en
estos datos, y por eso la malla lo ve.

### Una corrección

El texto de este bloque decía *«más α es menos probabilidad de cualquier
acción, porque el prior pesa menos»*. **Es al revés.** En
`p_k = (N_k + α·S_k)/(opp + α)` el prior pesa **más** al subir α, y la
probabilidad de cada acción sube o baja según cómo quede su frecuencia
empírica frente a su prior. **No hay regla general para el signo.** Lo que
es cierto, y se acaba de derivar, es que la SUMA decrece.

### Y la coherencia necesita DOS cosas, no una

| | |
|---|---|
| `N(c) ≤ opp(c)` | **sí**, por construcción |
| `S(c) ≤ 1` | **no**: las tablas de `preflop_matrices.json` no suman 1, van de 0,91 a 89,75 |

Así que *«coherente para todo α»* es una **medición sobre estos datos**, no
una consecuencia de la fórmula. En el bloque anterior se presentó como
deducción, y no lo es.

## Lo que se sabe y lo que no, con la prueba buena

### Se sabe

| | |
|---|---|
| `matrix` **no es una distribución** sobre las 169 celdas | 1 de 117 tablas suma ≈1; van de **0,91 a 89,75**, mediana **10,00** |
| las celdas **sí** son probabilidades | **0** de 19 773 fuera de `[0,1]`; 116 de 117 tablas tienen celda máxima = 1 |
| `sum(matrix)` no es `sum(cnt)` ni un múltiplo | **0,3×** para `open` |
| con α = 2 el motor **no viola** el contrato por celda | máximo 0,7571 y 0,9500 |
| **no hay `α` que lo viole** | `N(c) ≤ opp(c)` por construcción |

### No se sabe, y no se puede saber con datos

> **QUÉ clase de cosa es `matrix`.**

Que las tablas no sumen 1 dice que **no son una distribución**. No dice que
sean inválidas para un shrinkage: *pesos relativos por celda* es un prior
perfectamente utilizable en esa fórmula y daría exactamente las mismas sumas.

Y `preflop_matrices.json` **no lleva metadatos**: no hay campo `origen`,
`version` ni `generado_por`.

### La pregunta, para quien generó el fichero

> *«En `preflop_matrices.json`, ¿qué representa `matrix`? Las celdas están en
> `[0,1]` pero las tablas suman entre 0,91 y 89,75, y solo 1 de 117 suma ≈1.
> ¿Son una distribución que se normalizó mal, pesos relativos por celda, o
> una magnitud distinta? Y si son pesos relativos, ¿contra qué se normalizan?»*

## Y `DEFAULT_ALPHA`, con la formulación honesta

`revision_2` §3 pide separar tres afirmaciones, y tiene razón: son cosas
distintas y confundirlas es lo que hace que una decisión de ingeniería parezca
una demostración.

### (1) Coherencia — **medida**, no deducida

Los valores probados respetan la invariante por celda. Con α = 2 el máximo es
**0,7571** y la suma por celda **0,8625**. Y **no hay ningún `α` que la
viole**: se cumple para todo `α ≥ 0`.

Que se cumpla para todo `α` es una **medición sobre estos datos**, no una
consecuencia de la fórmula: haría falta también `S(c) ≤ 1`, y las tablas
no lo cumplen.

### (2) Discriminación — **medida sobre la función agregada**

Antes se decía «224 de 256 celdas empujan en el mismo sentido». Eso **no**
demuestra que `L_prim` sea monótona: importan las **magnitudes y los pesos**
de las que quedan. Medido sobre `L_prim` completa:

| `alpha` | `L_prim` |
|---:|---:|
| 0,5 | 0,387150 |
| 1,0 | 0,527915 |
| 1,3636 | 0,607984 |
| 1,5 | 0,634504 |
| **2,0** | **0,719102** |
| 3,0 | 0,846569 |
| 5,0 | 1,010302 |
| 10,0 | 1,212890 |

**8 de 8 pasos estrictamente crecientes.** La agregada sí es monótona, y no
tiene mínimo interior: la curva crece sin parar. Su «mejor» es siempre el
**menor** α.

> **Discriminación: ninguna.** `L_prim` ordena α por cuánto se diluyó el
> prior, no por calidad.

### (3) Decisión — **de ingeniería, y no depende de (2)**

Se conserva α = 2,0 porque **no hay evidencia admisible que justifique
sustituirlo**. Eso es una decisión de ingeniería, y puede ser buena aunque (2)
no estuviera probada.

> Que (3) no dependa de (2) es lo que hace que la decisión siga en pie. Lo
> que no es admisible es presentar (3) como si **fundara** (2). No lo hace.

> **`DEFAULT_ALPHA` no se calibra porque las métricas disponibles no lo
> distinguirían, no porque `alpha` no pueda ser un parámetro de
> regularización.**
>
> Eso es un cambio grande respecto a lo que este documento afirmaba antes. Si
> alguien arregla `matrix` **y** trae una métrica que no sea monótona, la
> pregunta vuelve a plantearse. **No es «nunca».**

Y lo que sí es permanente, y ahora está **medido**:

> **No hay cota que lo acote.** La coherencia por celda se cumple para todo
> `α ≥ 0`. El umbral de 1,3636 se ha retirado: era un artefacto de sumar el
> prior crudo del fold, y el motor usa su probabilidad suavizada.

## Estado

| | |
|---|---|
| `DEFAULT_ALPHA` | **2,0**. Se queda por ser el incumbent y porque no hay evidencia admisible que lo sustituya. **No** porque esté calibrado, y **ya no** por una cota: no hay ninguna |
| cota inferior | **ninguna**: la coherencia se cumple para todo `α ≥ 0` |
| `data/preflop_matrices.json` | **intacto** |
| qué es `matrix` | **abierto**. Era cerrado en el bloque anterior sobre una prueba que no se sostenía |

## Reproducir

```
python tools/auditar_matrix.py
```
