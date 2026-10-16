# FASE D — bloqueada, y con la razón escrita

## El estado

**Fase D no puede continuar con las métricas actuales.**

No porque el trabajo esté mal hecho, sino porque el contrato de aceptación
—§2.3— exige **las dos** métricas, y la secundaria solo se puede calcular
en el **38 %** de la muestra. El resto es retrospective: usa cartas del
rival que al decidir no se conocían.

Y lo que da la mitad observable **es bueno**: la equity gana al predictor
constante, 0,1962 contra 0,2124, y ordena con +0,3300.

Detalle en [`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md).

## La opción elegida: **C**, con **A** como trabajo siguiente

| | opción | por qué no |
|---|---|---|
| A | buscar otra métrica secundaria | es el trabajo **siguiente**, no el de hoy |
| B | medir sin secundaria, con otro criterio | ver abajo: **no es admisible** |
| **C** | **declarar Fase D bloqueada** | **elegida** |

### Por qué no B, aunque suena razonable

B suena razonable: aceptar un valor de `DEFAULT_ALPHA` si mejora `L_prim` y
no empeora las claves de `opp`.

**No es admisible, por dos razones medidas:**

1. **`L_prim` es monótona.** Ordena `alpha` por cuánto se diluyó el prior: no
   distingue calidad, y su ganador es siempre el candidato menor. Aceptar
   «el que mejor mejora `L_prim`» es aceptar *el más pequeño*, por definición.
2. **`L_prim` mezcla contra una escala que no es una probabilidad.** Las
   matrices de `preflop_matrices.json` suman entre 0,91 y 89,75 y el 86,7 %
   de sus celdas son 0. `alpha * prior` no son pseudo-conteos
   ([`CEROS_PREFLOP_MATRICES.md`](CEROS_PREFLOP_MATRICES.md)).

O sea: B no es un criterio distinto, es **el mismo criterio sin la
comprobación que lo delata**. El plan lo dice ya en §2.3: no se
admite aceptar un valor sin las dos métricas.

### Por qué C y no A ahora

A es el camino correcto, pero necesita dos cosas que no existen todavía:
una métrica que no dependa del 86 % de derrotas, y un camino de equity
preflop en el motor. Las dos son bloques con su propio `.md`. Meterlas en
este bloque es exactamente lo que §5 del plan prohíbe: decidir el contrato
a mitad de fase.

## Qué trabajo desbloquea Fase D

En orden de dependencia:

| # | bloque | qué resuelve |
|---|---|---|
| **0** | **definir el objetivo de `L_sec`** | equity contra "gano el bote" o contra "si continuo, ganaba?". Son dos magnitudes y se eligio una sin decirlo. Ver `METRICA_SECUNDARIA_ALTERNATIVA.md` |
| **1** | **`hand_evaluator` con camino preflop** | que `_SUBSETS` tenga entrada para menos de 5 cartas, o una ruta que calcule la equity preflop contra rango. Sin esto, `L_sec` cubre el 38 % |
| **2** | **una métrica que sobreviva al 86 % de derrotas** | el Brier está dominado por la clase mayor. Opciones: comparar contra la mediana de la propia equity, o usar `equity` como *ranking* y no como probabilidad |
| **3** | **qué significa `matrix`** | sin eso, `DEFAULT_ALPHA` no se puede calibrar ni aunque haya secundaria ([`CEROS_PREFLOP_MATRICES.md`](CEROS_PREFLOP_MATRICES.md)) |

El 0 es el que bloquea: implementaría el 1 para medir mejor una magnitud que no está definida, que es exactamente lo que pasó en los dos bloques anteriores.

Y mientras tanto: **`DEFAULT_ALPHA` sigue en `2.0`**, con un test que falla
si alguien lo mueve sin pasar por aquí.

## Lo que NO se hace

- **No** se fuerza un valor de `alpha`.
- **No** se cambia P1–P7. Solo se añade **P0**, y es una adición.
- **No** se empieza otro parámetro. Con el contrato así, todos darían igual.
- **No** se toca `data/`: los 25 repartos incompletos quedan declarados.
