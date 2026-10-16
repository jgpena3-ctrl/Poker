# CONTRATO L_SEC — objetivo, población, etiqueta, referencia y exclusiones

> Esto es lo que `revision_2` pide antes de volver a medir: **la pregunta
> estadística bien definida**. No es un instrumento ni un número. Es lo que
> hace que el próximo número signifique algo.
>
> **No se implementa aquí.** Y no se amplía la cobertura hasta que esté
> firmado: más cobertura de una métrica ambigua solo da más números
> malos.

## Por qué existe

`L_sec` nació como «el Brier de `sit.equity` contra si el hero ganó el
bote». Y ese nombre esconde **tres objetivos distintos**, que se han estado
midiendo como si fueran uno:

| | pregunta | magnitud |
|---|---|---|
| **A** | ¿la equity estima la probabilidad de ganar el bote? | probabilidad |
| **B** | ¿la equity ordena las manos? | ranking |
| **C** | ¿la acción del motor fue buena? | calidad de decisión |

Medidos juntos dan un número que no se refiere a nada. Y eso está medido:
la métrica agrupada «gana» y la población homogénea «pierde»
([`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md)).

## La decisión: cuál de los tres

**Se elige B, y se declara que A queda descartada.**

| | por qué no |
|---|---|
| **A — probabilidad** | requiere 1 326 manos de referencia por decisión para calibrar. Hay 28. Y la equity no es un estimador de «gana el bote»: es un estimador de «gana el bote **si continúo contra este rango**» |
| **C — calidad de decisión** | necesita etiqueta de optimalidad, que la base no tiene. Es lo que el plan descartó en §2.1 y sigue descartado |
| **B — ranking** | **la que la equity hace bien, y está medido: +0,3004 sobre 28 manos.** Y no depende de la escala, así que el 86 % de derrotas deja de importar |

Que B funcione en 28 manos es **débil**, y no se presenta como otra cosa. Lo
que hace este contrato es fijar *qué habría que medir* para poder afirmarlo.

## El objetivo, escrito

> **Ordenar** las manos de la partición de validación por
> `sit.equity` en el punto de decisión, y comprobar que **las que ganan
> están por encima de las que pierde**.

Eso es un **AUC**, y solo un AUC.

### Lo que NO es este objetivo

- **No** es «la equity es una buena probabilidad». Se ha medido que no
 calibra, y no se vuelve a preguntar con este nombre.
- **No** es «el motor decide bien». Eso es C y queda fuera.
- **No** es un Brier. Un Brier mide A y B a la vez, y por eso no decía cuál
 fallaba.

## Población

| | regla |
|---|---|
| ventana | las 877 de `load_hands(reliable_only=True)` |
| utilizables | las **160** de [`PARTICION_FASE_D.md`](PARTICION_FASE_D.md): 119 calibración, 41 validación |
| **en la evaluación** | **solo validación.** `L_prim` se ajusta en calibración; la secundaria decide en validación. Nunca las dos |

### Y el filtro que hay que aplicar antes de nada

**Solo manos donde el hero continúa.** Es decir, su acción en el punto de
corte es `b`, `c` o `r`.

El motivo está medido y es de, no de gusto:

| población | n | Brier equity | constante | |
|---|---:|---:|---:|---|
| hero continúa | 28 | 0,2238 | 0,1974 | — |
| hero foldea | 10 | 0,1982 | 0,0000 | degenerada: 0 victorias |
| hero check | 22 | 0,1600 | 0,2500 | no representativa: 50 % victorias |

- Si el hero **foldea**, su equity está medida *antes* de abandonar y la
 etiqueta es 0 porque ya no puede ganar. **Son dos magnitudes.**
- Si el hero solo **checkea**, gana el 50 % contra el 12 % de la muestra: es
 una población distinta, no una submuestra.

> **Cualquier número que mezcle esas tres no se publica.** Ni con un
> promedio, ni con un «global».

## Etiqueta

| | |
|---|---|
| `y = 1,0` | el ganador declarado es el hero |
| `y = 0,5` | reparto demostrado: los ganadores hacen la misma mejor mano, y **siguen siendo todos** los que la hacen |
| `y = 0,0` | el hero no está entre los ganadores |

Y la coherencia con las cartas es **condición de aceptación**, no un
detalle:

1. Si el ganador llegó al showdown y tiene cartas, tiene que hacer **la
  mejor mano de la mesa**, y los declarados tienen que ser exactamente
  quienes la alcanzan.
2. Si **ningún** ganador declarado llegó al showdown, hace falta
  **evidencia positiva** de victoria por fold: que quede un único jugador
  sin foldear en toda la mano y que sea el declarado.
3. Si no hay ninguna de las dos, **la mano no se etiqueta**. No se acepta
  «el registro dice que ganó» sin comprobar, porque es exactamente el
  error que ya se cometió dos veces.

## Referencia

El AUC no tiene referencia de la misma manera que el Brier, pero sí tiene
un contrajuego que hay que declarar:

| | |
|---|---|
| **contra qué se compara** | **0,5**, el azar |
| **y con qué mano** | **la misma mano de validación**, con la misma etiqueta |
| **y el azar de la muestra** | con 41 manos de validación, un AUC de 0,60 y otro de 0,80 son **indistinguibles**. Hay que declarar el intervalo, no el punto |

> **La última línea es la que bloquea.** Si el intervalo del AUC incluye
> 0,5, el resultado no dice nada, se diga como se diga. Y con 41 manos,
> muy probablemente lo incluya. Eso hay que verlo ANTES de celebrarlo.

## Exclusiones, todas contadas

| | |
|---|---|
| board incompleto | 580 |
| menos de 2 jugadores con cartas | 134 |
| sin ganador declarado | 1 |
| ganador sin cartas | 1 |
| **reparto incompleto** (los declarados no son todos los que hacen la mejor mano) | 0 |
| **ganador incoherente con las cartas** | 1 (`H_0909`) |
| **sin evidencia de victoria por fold** | 2 |
| **quedan** | **160** |

Y las dos cosas que se declaran sin ocultar:

- **`H_0909`** es un defecto real de la base y queda fuera. No se corrige
 `data/`.
- **Dos manos** sin evidencia de fold salen de la muestra. No es que sean
 malas: es que **no se pueden demostrar**. Cuesta una mano de la muestra
 y es el precio correcto.

## Lo que falta para poder afirmarlo

| # | falta | por qué |
|---|---|---|
| 1 | **el intervalo del AUC**, no el punto | con 41 manos el punto no significa nada |
| 2 | **más manos de validación** | 41 es poco para cualquier métrica |
| 3 | **que la equity sea observable en preflop** | hoy el 62 % es retrospectiva ([`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md)) |

El 1 es barato y va primero: **calcular el intervalo y publicarlo, aunque
no se pueda afirmar nada**. Un AUC de 0,62 con un intervalo de 0,41 a 0,79
es un resultado honesto y es información.

## Lo que NO se hace

- **No** se amplía la cobertura preflop hasta que esto esté firmado.
- **No** se vuelve a mirar `L_prim` para buscar un ganador.
- **No** se toca `data/`.
- **No** se mueve `DEFAULT_ALPHA`: sigue en **2,0**.

## Reproducir

```
python tools/calibrar.py particion
python tools/equity_de_mano.py --mano H_0798
```
