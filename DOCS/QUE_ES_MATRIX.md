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
p_k(c) = (cnt_k(c) + α·prior_k(c)) / (opp + α)

para cada celda c:  sum_k p_k(c) ≤ 1
  ⟺  N(c) + α·sum_k prior_k(c) ≤ opp + α
  ⟺  sum_k prior_k(c) ≤ 1        (porque N(c) ≤ opp)
```

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

Bisección, 22 iteraciones: el borde inferior es **α ≈ 1,3636**.

> ### Por debajo de 1,3636 el motor produce probabilidades incoherentes.
>
> Para una mano dada, asigna más probabilidad total a acciones que son
> mutuamente excluyentes. Eso no es una uncommon: es imposible.

**Y `DEFAULT_ALPHA = 2,0 está 1,47× por encima del borde.** No está pegado al
límite, pero tampoco es arbitrario: hay una razón medida para no bajar.

## Lo que se sabe y lo que no, con la prueba buena

### Se sabe

| | |
|---|---|
| `matrix` **no es una distribución** sobre las 169 celdas | 1 de 117 tablas suma ≈1; van de **0,91 a 89,75**, mediana **10,00** |
| las celdas **sí** son probabilidades | **0** de 19 773 fuera de `[0,1]`; 116 de 117 tablas tienen celda máxima = 1 |
| `sum(matrix)` no es `sum(cnt)` ni un múltiplo | **0,3×** para `open` |
| con α = 2 el motor **no viola** el contrato por celda | máximo 0,7571 y 0,9500 |
| **α < 1,3636 sí lo viola** | borde medido |

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

La conclusión **«no se calibra» se sostiene**, pero por otra razón, y hay que
decirla porque es **mucho más débil**:

| | razón | fuerza |
|---|---|---|
| 1 | `L_prim` es **monótona** en α: 224 de 256 celdas empujan en el mismo sentido, así que su ganador es siempre el candidato **menor**, por definición | no **distingue** entre valores |
| 2 | no hay métrica secundaria **admisible** para arbitrar: el Brier se pierde contra el predictor constante en la mitad retrospectiva, y el AUC no es afirmable con 11 manos | no hay **árbitro** |

> **`DEFAULT_ALPHA` no se calibra porque las métricas disponibles no lo
> distinguirían, no porque `alpha` no pueda ser un parámetro de
> regularización.**
>
> Eso es un cambio grande respecto a lo que este documento afirmaba antes. Si
> alguien arregla `matrix` **y** trae una métrica que no sea monótona, la
> pregunta vuelve a plantearse. **No es «nunca».**

Y lo que sí es permanente, y ahora está **medido**:

> **No se baja de 1,3636.** Por debajo, el motor produce probabilidades que no
> pueden existir. Eso no es una preferencia de calibración: es una
> contradicción medible.

## Estado

| | |
|---|---|
| `DEFAULT_ALPHA` | **2,0**. Se queda por estar **1,47× por encima del borde de coherencia** y por ser el incumbent. **No** porque esté calibrado |
| cota inferior | **1,3636**, medida por bisección |
| `data/preflop_matrices.json` | **intacto** |
| qué es `matrix` | **abierto**. Era cerrado en el bloque anterior sobre una prueba que no se sostenía |

## Reproducir

```
python tools/auditar_matrix.py
```
