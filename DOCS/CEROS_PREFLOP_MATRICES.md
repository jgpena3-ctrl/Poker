# CEROS EN `preflop_matrices.json` — y por debajo, un problema mayor

## Resumen

`p = 0` en **1 991 de 22 308** celdas del grid (8,9 %), y **también con
`alpha = 20`**. Los ceros no vienen de la regularización: vienen de que las
matrices de `data/preflop_matrices.json` **no son priors normalizados**.

Eso es un hallazgo distinto del que se buscaba, y es más grave.

| | |
|---|---:|
| tablas en `preflop_matrices.json` | 117 |
| con clave `matrix` | 117 |
| celdas de matriz revisadas | 19 773 |
| celdas con `0` | **17 150 (86,7 %)** |
| suma de una matriz | de **0,91** a **89,75** |
| valores que aparecen | `{0, 0.25, 0.33, 0.5, 0.66, 0.75, 1.0}` |

Un prior sobre las 1 326 manos posibles debería sumar **1**. Estas suman
hasta 89,75, y sus valores son un grid de cuatro pasos. **No son
distribuciones de probabilidad.** Son pesos gruesos, de una codificación
antigua.

## Por qué importa, en tres niveles

### 1. Hoy no contamina `L_prim`

Medido sobre los 295 eventos de la partición de calibración:

| | |
|---|---:|
| eventos con `p = 0` | **0** |
| eventos sin celda en el grid | 0 |
| eventos que caen al prior por falta de `opp` | 0 |

Porque `L_prim` solo mira celdas **observadas**, y una celda observada
tiene `cnt >= 1`. Con `cnt >= 1`, `p = (cnt + α·prior)/(opp + α)` es
positivo para cualquier `α`, aunque el prior sea 0.

### 2. Muerde donde `cnt = 0` **y** el prior es 0

Esas son **446 celdas** en las matrices reales, y ahí `p = 0` para todos
los valores de `α`. No hay palanca de regularización que las saque.

### 3. Y por debajo: `α` no mezcla con una probabilidad

Esto es lo que el diagnóstico destapa, y no estaba en la pregunta.

`p_matrix` hace el shrinkage:

```
p = (cnt + alpha * prior) / (opp + alpha)
```

`α` son pseudo-conteos: se suman al lado de `cnt`, que sí es un conteo.
Para que esa suma signifique algo, `prior` tiene que estar en la misma
unidades — tiene que ser una **frecuencia sobre las manos observadas**.

No lo está. `prior` viene de una matriz que suma hasta 89,75 y cuyos valores
son `{0, 0.25, 0.5, 0.75, 1.0}`. Así que `α·prior` no son pseudo-conteos:
son pesos de una escala que no se sabe qué es.

> **Y eso refuerza por separado el `NO SE CALIBRA` de `DEFAULT_ALPHA`.**
> Antes el motivo era que `L_prim` no puede distinguir candidatos. Este es
> otro e independiente: **la magnitud que se está calibrando mezcla contra
> algo que no es una probabilidad.** Son dos razones distintas, y las dos
> apuntan al mismo sitio.

## La hipótesis

La pregunta era: *¿manos imposibles, tablas mal generadas, o acciones que no
ocurren en ese spot?*

**Ninguna de las tres, y se descarta cada una con una medición:**

| hipótesis | comprobación | resultado |
|---|---|---|
| son la diagonal (pares, imposibles) | ceros con rango igual | 4 de 112 en la tabla de ejemplo |
| son mitades sin usar | la mitad de abajo casi siempre 0, la de arriba con masa | **es al revés**: los ceros se concentran en las filas bajas, que son las más pocas |
| son tablas de un spot raro | tablas con más ceros | `Call_4B_*` con 164-168 ceros de 169: sí, pero **las 117 tablas tienen ceros**, ninguna se libra |

Lo que sí es cierto, mirando una tabla (`3B_BB_vs_BTN`):

```
        A      K      Q      J      T      9      8      7  ...
     A  1.00   1.00   1.00   0.75   0.00   0.00   0.00   0.00
     K  1.00   1.00   1.00   0.00   0.25   0.00   0.00   0.25
     Q  0.75   0.00   1.00   0.00   0.00   0.00   0.25   0.25
     8  0.00   0.00   0.00   0.00   0.00   0.00   0.00   0.00
     3  0.00   0.00   0.00   0.00   0.00   0.00   0.00   0.00
```

Los ceros se concentran en **las filas de rango bajo** (8, 7, 6, 5, 4, 3, 2
casi todas a cero) y en la mitad superior de la triangular. Eso tiene forma de
**tabla rellenada a ojo o de una conversión perdida**, no de poker: una
prior real de un 3bet del BB contra BTN da masa de sobra a manos como 85o
contra A2s.

**Hipótesis, y es una hipótesis:** `matrix` guarda una puntuación de fuerza
por celda, no una frecuencia, y `p_matrix` la está usando como si fuera una
frecuencia. Encaja con que los valores sean cuatro pasos y con que la suma
llegue a 89.

## Cómo se comprueba, y cómo se refuta

Está escrito antes de tocar nada, para que no se acepte por ser la explicación
cómoda:

| si | entonces |
|---|---|
| `matrix` fuera una frecuencia sobre las 1 326 manos | sumaría ~1 por tabla. **Suma hasta 89,75.** Descartada |
| los ceros fueran un hueco de captura | las 169 celdas del grid tienen alguna observación. Descartada |
| fueran tablas rotas | ninguna de las 117 está libre de ceros. Descartada |

## Radio de impacto

`_prior_grid` no es una cosa aislada. Lo usan:

`player_ranges.p_matrix` → `preflop.py`, `profile.py`, `recommend_loop.py`,
`asistente_live.py`, `equity_de_mano.py`, y por persistencia
`data/profile_ranges.json`.

O sea que **cualquier cambio en cómo se interpretan estas matrices cambia el
rango que el motor da en vivo.** No se toca nada aquí.

## La acción elegida: **B**

Había tres caminos y se elige **B**.

| | opción | coste |
|---|---|---|
| **A** | regenerar las matrices como priors normalizados | alto: recalcular desde `hands_db.jsonl` |
| **B** | **declarar que no son priors, y cambiar el shrinkage para que no se usen como si lo fueran** | **acotado: un cambio en `player_ranges.py`, no en las matrices** |
| C | dejarlo como está y no calibrar hasta resolverlo | gratis, y deja el bug puesto |

**Se elige B, y no porque sea la más barata.**

La razón es que el diagnóstico apunta a que **el problema no son los
números, es el contrato que se les supone**. Una matriz que suma 89,75
puede ser una fuerza, o una puntuación, o un marcador de muchas manos. Lo
que no puede ser es una frecuencia sobre 1 326 manos, y **eso es lo que
`_prior_grid` la trata de ser** al usarse como pseudo-conteo.

Cambiar las matrices (A) es cambiar la respuesta sin saber la pregunta.
Dejarlas (C) deja un `alpha` que se puede mover y no significa nada, que
es exactamente el estado en el que está el proyecto ahora mismo y la razón
de que este documento exista.

> **Y B es la única que separa las dos cosas.** A cerraría los 17 150 ceros
> *y* dejaría sin tocar el hecho de que `L_prim` solo mira celdas
> observadas. C no cierra nada. B dice la verdad sobre el dato y ajusta el
> código a esa verdad.

### Qué implica B, exactamente

`p_matrix` deja de hacer `cnt + alpha * prior` sobre una escala que no es
una frecuencia. Hay que decidir el sustituto, y **esa decisión no se puede
tomar sin saber qué significa `matrix`**: si es una puntuación de fuerza,
el shrinkage tiene que ir sobre una escala declarada; si es un conteo
muestreado, hay que dividir por su tamaño de muestra.

Mientras tanto, y hasta que eso se decida con evidencia:

- **`DEFAULT_ALPHA` no se mueve.** Sigue en `2.0` con su test.
- **`_prior_grid` deja de fingir** que devuelve una probabilidad, o el
  shrinkage se apaga donde la escala no sea creíble. Lo que haga falta
  para eso está en el bloque siguiente.

### Cómo se sabría que B está bien

| si | entonces |
|---|---|
| B es correcto | cambiar la escala de `matrix` **no cambia** el orden de los candidatos que `L_prim` prefiere, porque `L_prim` ya es monótona y no distingue. O sea: **B no puede arreglar por sí sola** |
| A sería necesario | `matrix` resultara ser una frecuencia mal formada y normalizarla **cambia** el comportamiento |

Que la propia B no baste para desbloquear la calibración es lo que hace que
los **dos** motivos sigan siendo independientes, y no uno con dos nombres.

## Qué haría falta, y por qué no se hizo

1. **Decidir qué es `matrix`.** Es una pregunta para quien generó el
   fichero, no para un script: no se deduce del dato, se deduce de quien lo
   escribió.
2. **Si es una frecuencia, normalizarla** y con eso desaparecerían los 17 150
   ceros y la escala de `α` volvería a significar pseudo-conteos.
3. **Si no es una frecuencia, cambiar el shrinkage** para que no la use como
   si lo fuera.

Los tres son cambios de `data/` y de `motor/`. Fuera de alcance en este
bloque, y con el motivo escrito: **no se sabe todavía qué significa el
campo**, y cambiar el shrinkage contra un significando inventado es
exactamente lo que este proyecto no hace.

## Reproducir

```
python tools/auditar_muestra_lsec.py     # la muestra y el suelo trivial
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 2.0 5.0
```

`calibrar.py` reporta en cada corrida las celdas con `p = 0` de los eventos
que mide, para que esto se pueda volver a comprobar.