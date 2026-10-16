# EL AUC DE LA EQUITY — con intervalo, y afirmable

## El resultado

| población | n | gana | pierde | **AUC** | **95 % IC** | p (permutaciones) |
|---|---:|---:|---:|---:|---|---:|
| **A)** el hero continúa (`b`/`c`/`r`) | 25 | 8 | 17 | 0,8015 | [0,5965, 0,9559] | 0,0071 |
| **B)** el hero continúa o checkea | **47** | 19 | 28 | **0,8308** | **[0,6991, 0,9364]** | **0,0001** |

**Se elige la población B.** El intervalo **no incluye 0,5** en ninguna de
las dos, y los dos métodos de incertidumbre coinciden.

> **La equity ordena las manos mejor que el azar.** Eso es afirmable con
> estas 47 manos, y no lo era hace dos bloques.

## La población, y por qué B

| | A (continúa) | B (continúa + check) |
|---|---:|---:|
| n | 25 | **47** |
| victorias | 8 | **19** |
| intervalo | [0,60, 0,96] | **[0,70, 0,94]** |
| ancho | 0,36 | **0,24** |

**B**, por tres razones:

1. **Más manos** y por tanto un intervalo más estrecho. Con 25 y 8
  victorias, el punto del AUC dice poco.
2. **El check es una decisión legítima.** El contrato excluye las manos
  donde el hero **foldea**, porque su equity se mide antes de abandonar y
  la etiqueta es 0: dos magnitudes. El check **no** tiene ese problema: el
  hero sigue en el bote, y su equity sigue siendo relevante.
3. **La exclusión de la Brier sigue justificada por otra razón** que no
  afecta al AUC. El subgrupo de check tenía 50 % de victorias contra el
  12 % de la muestra, lo que lo hacía **no representativo para un Brier**
  (que es sensible a la base rate). Un **AUC no lo es**: mide el orden, y
  el orden no depende de cuántas victorias haya en la clase.

> **Excluir los checks era una decisión de Brier, no de ranking.** Y al
> cambiar de métrica, la decisión cambia. Eso es lo que significa que el
> objetivo estuviera escondido.

## Qué entra y qué no, contado

De las **160** manos de la muestra:

| | manos |
|---|---:|
| **entra al AUC** | **57** |
| excluida: **preflop retrospectiva** | **98** |
| excluida: reparto (`y = 0,5`, el AUC binario no lo admite) | 3 |
| excluida: el hero no actuó | 1 |
| excluida: sin equity | 1 |

Y las 57 se reparten así: river 45, flop 6, turn 6.

### Las reglas fijadas antes de calcular

| regla | por qué |
|---|---|
| **el reparto se excluye, no se convierte** | `y = 0,5` no es una victoria ni una derrota. Convertirlo en una de las dos sería inventar la etiqueta, y el recuento de 3 queda publicado |
| **solo validación** | el modelo se ajusta en calibración. Evaluar en la misma muestra con la que se ajusta sería medir recuerdo, no generalización |
| **el intervalo se publica aunque incluya 0,5** | un intervalo ancho no es un fallo del análisis: es la conclusión |

## Los dos métodos de incertidumbre

**No se publica un AUC con un solo intervalo.** Dos, y tienen que coincidir:

| método | qué es | por qué |
|---|---|---|
| **bootstrap percentil** | 10 000 remuestreos con reemplazo, semilla 7 | el estándar para intervalos |
| **permutaciones** | 10 000 barajados de las etiquetas, semilla 7 | la respuesta no paramétrica pura: no hace ninguna suposición de forma |

> **Un tercer método se intentó y se descartó**: Hanley-McNeil dio un error
> estándar de **0,42** para un AUC de 0,80, y un z de 0,71. La fórmula se
> degrada cuando el AUC se aleja de 0,5 en muestras pequeñas. Citar un
> intervalo que no se ha mirado es el error que este bloque lleva quince
> bloques corrigiendo.

Y un error propio que salió al el método: la primera versión del test de
permutaciones usaba `|AUC − observado| ≥ |0,5 − observado|`, que con un
observado de 1,0 contaba las permutaciones con AUC ≤ 0,5 — **la mitad**.
Daba p = 0,51 con una separación perfecta. Se cazó porque en un caso
sintético con AUC = 1,0 el p tiene que ser minúsculo, y no lo era.

## Lo que este resultado NO dice

> **AUC es discriminación. No es calibración.**

La equity ordena las manos. Eso **no** significa que 0,80 signifique «gana
el 80 % de las veces». Y desde luego no significa que el motor decida bien:
ese es el objetivo **C** del contrato, que sigue fuera porque no hay
etiqueta de optimalidad.

Y hay una exclusión que pesa mucho más que el tamaño del intervalo:

> **98 de las 160 manos son preflop, y quedan fuera porque su equity es
> RETROSPECTIVA**: usa las cartas reales del rival, que al decidir no se
> conocían. Este AUC es, de hecho, **de postflop**.

El camino preflop del motor sigue sin existir
([`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md)), y sin él este resultado
cubre el **36 %** de la muestra. Afirmable, sí. Completo, no.

## Y `DEFAULT_ALPHA`

**Sigue en 2,0.** Un AUC afirmable dice que la equity ordena; **no** dice
que un valor de `alpha` sea mejor que otro. Para eso hacen falta los otros
dos bloques: qué significa `matrix`
([`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md)) y una métrica que mida al
**candidato**, no al modelo entero.

## Reproducir

```
python tools/auditar_auc.py
```
