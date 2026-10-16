# MÉTRICA SECUNDARIA ALTERNATIVA — la pregunta, y una hipótesis

> Bloque declarado, no resuelto. Su pregunta se escribe **antes** de
> buscar la respuesta, para que la respuesta no se acomode a la métrica.

## La pregunta

`L_sec` —el Brier de `sit.equity` contra «el hero ganó el bote»— **no es
admisible**, medido:

| población | n | Brier de la equity | constante | |
|---|---:|---:|---:|---|
| el hero continúa | 28 | 0,2238 | 0,1974 | **pierde** |
| el hero foldea | 10 | 0,1982 | 0,0000 | pierde |
| el hero check | 22 | 0,1600 | 0,2500 | gana |

Sobre la única población homogénea, la equity **pierde**. Detalle en
[`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md).

## Lo que sí se sostiene

En la población de «el hero continúa» la equity **ordena**:

| | |
|---|---:|
| equity donde el hero gana | 0,7957 (n = 8) |
| equity donde el hero pierde | 0,4952 (n = 17) |
| **diferencia** | **+0,3004** |

Es decir: **discrimina bien y calibra mal**. Y son dos cosas distintas; el
Brier las mide juntas, así que no dice cuál falla.

## Hipótesis 1 — usar la equity como *ranking*, no como probabilidad

En vez de `mean((p - y)²)`, medir **si las manos con mayor equity ganan más
que las de menor**.

| a favor | en contra |
|---|---|
| usa lo que la equity hace bien | con 28 manos, medir ranking no tiene potencia |
| no depende de la escala, así que el 86 % de derrotas deja de importar | no mide «acertar», mide «ordenar», que es otra cosa |
| es lo que el motor necesita: elegir, no predecir | no valida la magnitud que se usa para decidir el *tamaño* |

**Cómo se comprobaría:** AUC sobre las 28 manos homogéneas, contra el 0,5
de azar. Si queda claramente por encima, la hipótesis aguanta.

## Hipótesis 2 — medir la decisión, no el equity

Comparar **la acción que recomienda el motor** contra lo que hizo el hero.
Es lo que el plan propuso al principio y descartó
(`CONTRATO_F72A.md`): la base no tiene etiqueta de optimalidad.

**Cómo se podría resolver:** generar la etiqueta a partir del propio motor
con una muestra de runouts distinta de la del ajuste. Sería
auto-referencia, y eso hay que decirlo antes de hacerlo, no después.

## Hipótesis 3 — salir de la equity

Que la secundaria mida otra cosa del motor: el **error de EV** en las
decisiones que sí son comparables, o la **consistencia** del rango frente a
la fuerza observada.

**Cómo se comprobaría:** si una métrica nueva ordena mejor que la equity
sobre las mismas 28 manos, es candidata. Si no, la equity sigue siendo lo
mejor que hay, y hay que decirlo.

## Lo que hay que decidir primero

**El objetivo**, antes que la métrica:

- ¿«la equity estima la probabilidad de ganar el bote»? Entonces es un
 problema de calibración, y hay que corregir la equity.
- ¿«la equity ordena las manos»? Entonces es un problema de métrica, y hay
 que medir ranking.

Son dos preguntas distintas con dos respuestas distintas, y elegir la
métrica antes de contestarla es cómo se acaba midiendo lo que no se quería.

## Bloqueante de orden

Este bloque va **antes** que
[`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md): más cobertura no arregla un
objetivo mal definido.
