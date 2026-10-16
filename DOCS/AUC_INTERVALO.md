# EL AUC DE LA EQUITY — corregido, y la conclusión ha cambiado

> ## AVISO: la versión anterior de este documento publicaba un resultado
> **incorrecto** y este lo sustituye entero.
>
> Decía AUC 0,8308 con intervalo [0,6991, 0,9364] y p = 0,0001, y lo
> calificaba de afirmable. Ese número mezclaba las manos de **calibración**
> con las de **validación**. La corrección la encontró `revision_2` §1.

## Lo que estaba mal

El código era:

```python
c, v = cal.muestra()
etiqueta = {i: y for i, y in c + v}      # <-- las dos
```

El modelo sí se ajustaba **solo** en calibración, pero las predicciones
evaluadas incluían también las manos con las que se ajustó. Eso es mezclar
dentro y fuera de muestra, y empuja el AUC **hacia arriba**: una equity
ajustada a una mano la subestima menos que la de una mano que nunca vio.

Y el documento afirmaba «solo validación». El código no lo hacía. Cuando el
texto y el código discrepan, el que se publica es el que engaña.

## Lo corregido

| | antes | **ahora** |
|---|---|---|
| manos evaluadas | 160 (119 cal + 41 val) | **41, solo validación** |
| manos que entran | 57 | **14** |
| regla de partición | dos copias del sha256 | **una**, `calibrar.es_validacion` |
| comprobación | ninguna | **una a una**, y lanza si falla |

No es un `assert`, que `python -O` se come. Es una función que lanza
`FugaDeValidacion`.

## El resultado corregido

**Población B — el hero continúa o checkea, validación:**

| | n | gana | pierde | AUC | 95 % IC | p (1 cola) |
|---|---:|---:|---:|---:|---|---:|
| A) continúa (`b`/`c`/`r`) | 6 | 2 | 4 | 0,8750 | [0,5000, 1,0000] | 0,1366 |
| **B) continúa o checkea** | **11** | **6** | **5** | **0,7667** | **[0,4333, 1,0000]** | **0,0896** |

| | |
|---|---|
| el IC excluye 0,5 | **NO** |
| el p rechaza H0 al 5 % | **NO** |

> ## NO AFIRMABLE.
>
> Con 11 manos de validación no se puede distinguir ordenamiento útil de
> azar. Y esa **es** la conclusión, no un fallo del análisis.

## Las otras cuatro correcciones de `revision_2` §2

No eran el error principal, pero las cuatro eran ciertas:

| # | qué estaba mal | qué hay ahora |
|---|---|---|
| 1 | «los dos métodos coinciden» — el veredicto **solo miraba el intervalo** | el IC y el p se **informin por separado**, con su pregunta distinta |
| 2 | el IC y el p no son dos intervalos: uno dice de qué valor puede ser el AUC, el otro si hay evidencia contra H0 | está dicho en el propio documento, y el código no vuelve a llamarlos «los dos métodos» |
| 3 | el bootstrap remuestreaba la muestra conjunta y **descartaba** las réplicas que perdían una clase | **estratificado**: se remuestrea por separado victorias y derrotas y no se tira ninguna réplica |
| 4 | el p era `ge / n`, que puede dar **0**, un valor imposible | **`(ge + 1) / (n + 1)`**, la corrección de Monte Carlo |

La cola única del test de permutaciones se declara a propósito: H0 es
**AUC ≤ 0,5**, una hipótesis direccional fijada en
[`CONTRATO_L_SEC.md`](CONTRATO_L_SEC.md) §8 antes de mirar los números. Con
dos colas habría que duplicar el p, y también estaría declarado.

## Por qué el intervalo es tan ancho

No es un defecto del bootstrap. Con 6 victorias y 5 derrotas hay **C(11, 6)
= 462 reparticiones** posibles de las manos en dos clases, y elbootstrap las
recorre todas muchas veces. El intervalo es ancho porque la muestra lo es.

Y esto **sigue siendo cierto** aunque la conclusión no se pueda afirmar:
> Un intervalo que incluye 0,5 no es un fallo del análisis: es la conclusión.

## La población, y por qué B

La elección **no** cambia. B tiene el doble de manos que A y el check es una
decisión legítima: el hero sigue en el bote, su equity se mide igual que en
cualquier otra decisión, y no aparecen las dos magnitudes del fold.

Lo que sí cambia es el número, y baja. Excluir los checks **seguía siendo**
una decisión de Brier y no de ranking — eso no se toca.

## Qué sí se sostiene

No es poco, aunque suene a menos de lo que sonaba:

| | |
|---|---|
| el punto del AUC es **alto y en la dirección correcta** | 0,7667 contra 0,5 |
| pero **no se puede afirmar** | el intervalo incluye 0,5 |
| y la exclusión **más grande** no es el intervalo | 23 de las 41 manos de validación son cortes **preflop**, y su equity es retrospectiva |

> **La cobertura es el problema real, no la significance.** 14 de 41. Con
> 11 manos en el AUC, cualquier intervalo va a ser ancho; lo que falta son
> manos, y las que faltan son las preflop.

## Y qué haría falta para poder afirmarlo

No es «más tiempo de cómputo» ni «otrobootstrap»:

1. **El camino preflop observable.** Metería las 23 manos que hoy se
   excluyen, y es lo que decide si la cobertura pasa de 34 % a algo útil.
   Su varianza ya está medida y es admisible
   ([`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md)).
2. **Más manos de validación.** El reparto es `sha256(hand_id) % 10 < 3`, y
   cambiarlo es cambiar de fase: es un commit con su motivo, no un ajuste.

## `DEFAULT_ALPHA`

**Sigue en 2,0.** Nada de esto dice que un `alpha` sea mejor que otro. Un
AUC mide orden; `alpha` es una escala.

## Reproducir

```
python tools/auditar_auc.py
```

Y el guardián de que no vuelva a pasar:

```
python -m pytest tools/test_auditar_auc.py -q
```

`test_no_evalua_manos_de_calibracion` falla si alguna mano evaluada no es de
validación. Es el test que faltaba cuando se publicó el número malo.
