# QUÉ ES `matrix` — la respuesta, y la decisión

> **Resuelto con una prueba, no con una opinión.** Instrumento:
> [`tools/auditar_matrix.py`](../tools/auditar_matrix.py)
>
> La respuesta es **C**, y de las tres sub-opciones, la **tercera**:
> **`alpha` no es un parámetro de regularización. NO SE CALIBRA NUNCA.**

## La fórmula, y lo que obliga

El motor calcula

```python
p_matrix(perfil, spot, accion) = (cnt + alpha * prior) / (opp + alpha)
```

en [`motor/player_ranges.py`](../motor/player_ranges.py). `cnt` son **cuentas**
de manos, `opp` son las oportunidades. Sumando sobre las 169 celdas del grid:

```
sum_celdas p_matrix(spot, k) = [ N_k + alpha * S_k ] / (opp + alpha)
```

donde `N_k = sum_celdas cnt[spot, k]` y `S_k` es la suma de la tabla prior de
la acción `k`.

Ahora bien, `p_matrix` es **P(acción | mano, spot)**, así que no puede pasar de
1, y las acciones de un spot son **mutuamente excluyentes**. Además
`sum_k N_k ≤ opp`, porque una mano hace **una sola** acción. La única forma de
que todo eso se cumpla a la vez es:

> ### `sum_k S_k ≤ 1`

**Los priors de todas las acciones de un spot, sumados, tienen que dar 1.**

Y medido:

| | |
|---|---|
| el prior **plano** del fold: 0,15 × 169 celdas | **S = 25,35** |
| tablas de `preflop_matrices.json`: 117 | de **0,91** a **89,75**, mediana **10,00** |
| tablas que suman ≈1 | **1 de 117** |

> El prior plano del fold **se pasa 25 veces por sí solo**, sin tocar una sola
> de las 117 tablas. Eso no es una interpretación de los datos: es aritmética
> de la fórmula que ya está escrita.

## Las celdas SÍ son probabilidades. Lo que faltó fue normalizar

| | |
|---|---|
| celdas totales | 19 773 |
| celdas fuera de `[0, 1]` | **0** |
| celdas exactamente iguales a 1 | 1 294 (6,5 %) |
| tablas cuya celda máxima es exactamente 1 | **116 de 117** |

Las celdas son valores de probabilidad y el range es correcto. Lo que falló
fue la **suma**: hay una probabilidad por celda y la tabla no está
normalizada.

Eso **acota el problema**, y es lo que decide las opciones:

> **Normalizar NO basta.** Si cada tabla se normalizara a 1, tendríamos
> `S_k = 1`, y dos acciones de un spot darían `S = 2 > 1`. El problema no
> está solo en las tablas.

## Y el prior plano no es hipotético: se usa para lo más frecuente

| acción | prior | manos |
|---|---|---:|
| `fold` | **PLANO** | **221** |
| `fold_vs_open` | **PLANO** | 145 |
| `open` | tabla | 124 |
| `call_open` | tabla | 94 |
| `bb_check` | **PLANO** | 64 |
| `rol` | tabla | 57 |
| `limp` | tabla | 46 |
| `call_limp` | tabla | 34 |
| `3bet` | tabla | 17 |
| `fold_vs_3bet` | **PLANO** | 16 |
| `squeeze` | tabla | 8 |

`fold`, `fold_vs_open`, `bb_check` y `fold_vs_3bet` no están en `CAT_TABLE`, así
que `_prior_grid` les devuelve el plano **con un `RuntimeWarning` que el caller
puede no ver**.

> **El fold es la acción más frecuente del proyecto y es la que más se pasa de
> la raya**: `S = 25,35` donde la fórmula admite 1.

Es la misma trampa que el bloque anterior: *un fallback silencioso que produce
un número plausible*.

## Y `matrix` no viene de estos datos

Si `matrix` fueran **cuentas crudas** (opción B), su suma sería el número de
veces que se vio esa acción. Comparado contra `sum(cnt)` del mismo dataset:

| acción | `sum(cnt)` | `sum(matrix)` | ratio |
|---|---:|---:|---:|
| `open` | 124,0 | 38,75 | **0,3×** |

No es 1, ni se parece a 1, ni a ningún múltiplo limpio. **`matrix` no es una
tabla de conteos de este dataset.** Eso descarta la opción B como lectura
literal.

## Las tres opciones, con su respuesta

| | opción | veredicto |
|---|---|---|
| **A** | son priors normalizados; hay que normalizarlas | **NO BASTA**: normalizadas dan `S_k = 1` y dos acciones de un spot darían 2 |
| **B** | son cuentas crudas; `player_ranges.py` está mal | **DESCARTADA**: la suma no es `sum(cnt)` ni un múltiplo de ella (0,3×) |
| **C** | son otra cosa | **LA CORRECTA** |

### Y qué hacer: la sub-opción tercera

De las tres salidas de R1 para el caso C:

| | | |
|---|---|---|
| 1 | cambiar la fórmula para que `prior` sea una probabilidad real | exige rediseñar el shrinkage: **otra decisión** |
| 2 | cambiar la fuente de `prior` para que sea una probabilidad real | es una **decisión de poker**, no de datos |
| **3** | **declarar que `alpha` no es un parámetro de regularización** | **la elegida** |

> ## `DEFAULT_ALPHA` no se calibra. Nunca.
>
> No porque no haya datos, sino porque **`alpha · prior` no son pseudo-conteos**
> y comparar dos valores de `alpha` es comparar dos números sin unidad
> conocida.

### Tres razones medidas e independientes

1. **`matrix` no es una probabilidad.** Las celdas están en `[0, 1]` pero las
   tablas no suman 1. Un prior de probabilidad suma 1.
2. **La fórmula no puede ser un shrinkage.** Los priors de un spot no pueden
   sumar 1, y el prior plano del fold ya se pasa 25× solo.
3. **`L_prim` es monótona en `alpha`.** 224 de 256 celdas empujan en el mismo
   sentido: su ganador es siempre el candidato menor. Aunque la escala fuera
   correcta, no habría un ganador que distinguir.

## Lo que NO se resuelve aquí, y hay que decirlo

> **QUÉ clase de cosa es `matrix` sigue sin saberse.**

La medición acota la forma — celdas en `[0, 1]`, tablas sin normalizar, sin
relación con `cnt` — pero no dice cuál era la **intención**. *Proporciones
relativas* y *conteos con otra base* producen el mismo 89,75 y se corrigen de
forma distinta.

Y `preflop_matrices.json` **no lleva metadatos**: no hay campo `origen`,
`versión` ni `generado_por`. La respuesta a eso no está en el fichero, está en
quien lo generó.

Eso no bloquea Fase D. Bloqueaba que se **declarara** algo que no se puede
declarar con honestidad, y ya está declarado: `alpha` no es calibrable, y por
esa razón, no por falta de datos.

## Estado

| | |
|---|---|
| `DEFAULT_ALPHA` | **2,0**, y no se calibra. Con test que falla si alguien lo mueve |
| `data/preflop_matrices.json` | **intacto**. No se regenera nada |
| `matrix` en la fórmula | **queda como está**, con su diagnóstico escrito |
| opción 2 (fuente de prior) | **abierta**, y es una decisión de dominio |

## Reproducir

```
python tools/auditar_matrix.py
```