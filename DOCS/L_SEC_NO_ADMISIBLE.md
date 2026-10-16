# L_SEC — no es admisible, y ahora por una razón medida

> Antes este fichero se llamaba `L_SEC_INVALIDA.md` y luego
> `L_SEC_INCOMPLETA.md`. Los dos nombres mentían. Este dice lo que
> corresponde: **no admisible**, y no por falta de datos sino porque el
> objetivo no está definido.

## La conclusión que se retiró, dos veces

**Primera retirada.** Se escribió que «`L_sec` pierde contra una constante
(0,1783 contra 0,1076), no es un criterio válido». El número era correcto;
la causa era falsa: al separar por método, la mitad que perdía era la
retrospectiva, con **0 victorias en 99 manos**, donde una constante saca
0 por construcción.

**Segunda retirada.** Corregido eso, se escribió que «en el 38 % observable
funciona: 0,1962 contra 0,2124». El número también era correcto; la
población no lo era.

## Lo que pasa al separar por lo que hace el hero

El observable son 60 manos postflop. Pero el hero hace cosas muy distintas
en su punto de decisión:

| población | n | Brier de la equity | constante | |
|---|---:|---:|---:|---|
| el hero **continúa** (`b`/`c`/`r`) | 28 | **0,2238** | 0,1974 | **pierde** |
| el hero **foldea** | 10 | 0,1982 | **0,0000** | pierde |
| el hero **check** | 22 | 0,1600 | 0,2500 | gana |
| **todas juntas** — lo que se midió | 60 | 0,1962 | 0,2124 | gana |

Tres poblaciones incompatibles en un solo número:

- La de **check** tiene **50 % de victorias** (11 de 22), contra el 12,4 %
 de la muestra. No es representativa de nada, y es la que arrastra el
 agregado a «gana».
- La de **fold** tiene **0 victorias** y la constante saca 0.
- La de **continúa** —la única donde el objetivo «¿ganó el bote?» tiene
 sentido— **pierde**: 0,2238 contra 0,1974.

> ### Conclusión
>
> **`L_sec`, tal como el plan la define, no es admisible.** No porque la
> equity sea mala, sino porque **mezcla tres poblaciones** y porque en la
> única homogénea **pierde**.

## Por qué «fold» no puede compartir la población

Si el hero foltea, la equity se mide **justo antes** de foldear —digamos
0,65— y la etiqueta es 0, porque ya no puede ganar el bote.

No es un error de cálculo: es que la equity estima *«probabilidad de ganar
si continúo contra este rango»*, y la etiqueta mide *«gané el bote»*. Tras
el fold la primera ya no se refiere a la segunda.

Unir ambas cosas no es que dé un número malo: es que **no mide ninguna
magnitud**.

## Lo que sí se sostiene: discrimina, pero no calibra

Sobre la población homogénea de «el hero continúa»:

| | |
|---|---:|
| equity mediana donde el hero **gana** | **0,7957** (n = 8) |
| equity mediana donde el hero **pierde** | **0,4952** (n = 17) |
| **diferencia** | **+0,3004** |

La equity **ordena** bien. Lo que no hace es **calibrar**: que 0,80
signifique «gana el 80 % de las veces». Y con 28 manos, ni una de las dos
cosas se puede afirmar con fuerza.

> **Discriminación y calibración son propiedades distintas.** Ordenar no es
> acertar. Y el Brier mide las dos a la vez, así que un Brier malo no dice
> cuál de las dos falla. Aquí falla la calibración; el orden funciona.

## Qué desbloquearía

| # | bloque |
|---|---|
| 1 | **definir el objetivo**: o equity contra el resultado, o equity contra «si continúo, ¿llegaba a ganar?». Son dos métricas distintas |
| 2 | **población homogénea**: solo manos donde el hero continúa |
| 3 | **camino de equity preflop en el motor** ([`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md)) |
| 4 | una métrica de **ranking**, que use la discriminación y no la calibración ([`METRICA_SECUNDARIA_ALTERNATIVA.md`](METRICA_SECUNDARIA_ALTERNATIVA.md)) |

El 1 va primero. **Más cobertura no arregla una métrica que compara dos
magnitudes que no son la misma**, y por eso el camino preflop no es lo
primero.

## La regla, mientras tanto

- `calibrar.py` **no acepta** ningún valor de `DEFAULT_ALPHA`: sin
 secundaria evaluable y válida, salida 2.
- `DEFAULT_ALPHA` sigue en **2,0**, con su test.
- Fase D bloqueada: [`FASE_D_BLOQUEADA.md`](FASE_D_BLOQUEADA.md).

## Reproducir

```
python tools/equity_preflop.py --comprobar
python tools/equity_de_mano.py --mano H_0798
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 2.0 5.0
```
