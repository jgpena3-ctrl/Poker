# QUÉ ES `matrix` — la pregunta, y por qué bloquea

> Bloque declarado, no resuelto. Es el tercer bloque que impide calibrar
> `DEFAULT_ALPHA`, y el más barato de los tres.

## Lo medido

`data/preflop_matrices.json` tiene **117 tablas**, cada una con clave
`matrix` de 13×13.

| | |
|---|---:|
| celdas de `matrix` revisadas | 19 773 |
| celdas con `0` | **17 150 (86,7 %)** |
| suma de una matriz | de **0,91** a **89,75** |
| valores que aparecen | `{0, 0.25, 0.33, 0.5, 0.66, 0.75, 1.0}` |

Una frecuencia sobre las 1 326 manos posibles debería sumar **1**. Estas
suman hasta 89,75, y sus valores son un grid de cuatro pasos.

## Por qué bloquea

`p_matrix` hace el shrinkage:

```
p = (cnt + alpha * prior) / (opp + alpha)
```

`alpha` son pseudo-conteos: se suman al lado de `cnt`, que sí es un conteo.
Para que eso signifique algo, **`prior` tiene que estar en las mismas
unidades**.

Y no lo está. Así que `alpha * prior` no son pseudo-conteos: son pesos de
una escala cuyo significado nadie ha escrito.

> `DEFAULT_ALPHA` se queda en `2.0` por **dos** motivos independientes, y
> este es el segundo. Arreglar la métrica no arregla la escala.

## La pregunta

> **¿Qué representa la clave `matrix` de `preflop_matrices.json`?**

Y las tres subpreguntas que la acompañan, porque sin ellas la respuesta no
sirve:

1. **¿Sobre qué universo se calcula?** Si fuese una frecuencia de manos
  observadas, sumaría el número de manos de la tabla.
2. **¿Qué significan los ceros?** ¿Imposibilidad, falta de datos, o
  frecuencia observada igual a cero?
3. **¿Quién lo escribió y cuándo?** Eso está en `CANAL_MANUAL_CERRADO.md`
  y en la historia de `learn.py`. **No se deduce del dato.**

## Hipótesis, y cómo se refuta

| hipótesis | cómo se prueba | refutación |
|---|---|---|
| **es una frecuencia mal formada** | debería sumar el número de manos observadas por tabla | suma hasta 89,75 y los valores son un grid de 4 pasos. **Descartada** |
| **es una puntuación de fuerza por celda** | los ceros se explicarían como «esta combinación no está en la tabla de referencia» | posible, y encaja con que los ceros se concentren en las filas de rango bajo |
| **es un residuo de una conversión** | los valores {0, 0.25, 0.5, 0.75, 1.0} parecen un redondeo | posible, y encaja con que las 117 tablas tengan ceros |

**La segunda y la tercera no se distinguen con el dato.** Y esa es la
razón por la que esto no se resuelve midiendo: hace falta la intención de
quien lo generó.

## Qué se decide cuando se responda

| si `matrix` es | entonces |
|---|---|
| una **frecuencia** mal formada | opción **A**: regenerarla normalizada. Se van los 17 150 ceros y `alpha` vuelve a significar pseudo-conteos |
| una **puntuación** de fuerza | opción **B**: el shrinkage tiene que ir sobre una escala declarada, y `p_matrix` deja de fingir que devuelve una probabilidad |
| un **residuo** de conversión | hay que regenerarla desde `hands_db.jsonl`. Es lo más caro y lo más limpio |

La opción elegida provisionalmente está en
[`CEROS_PREFLOP_MATRICES.md`](CEROS_PREFLOP_MATRICES.md) — **B**, por ser
la acotada. Y **B no desbloquea la calibración por sí sola**: `L_prim` ya
es monótona y no distingue.

## Lo que NO se hace

- **No se toca `preflop_matrices.json`.** Cambiar los números sin saber qué
 significan es inventar.
- **No se mueve `DEFAULT_ALPHA`.** Sigue en `2.0`, con su test.
- **No se regenera nada.** Es un bloque con su migración, su hash y su
 backup.

## Reproducir

```
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 2.0 5.0
```

El comando reporta en cada corrida las celdas con `p = 0` de los eventos que
mide, para que esto se pueda volver a comprobar.
