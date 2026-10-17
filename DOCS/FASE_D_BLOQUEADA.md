# FASE D — bloqueada, y con la razón escrita

> **Estado: el bloque 3 está REABIERTO.** Los otros tres siguen cerrados.
>
> `DEFAULT_ALPHA` sigue en 2,0 y **no tiene cota inferior**: la coherencia
> por celda se cumple para todo α ≥ 0 en la configuración que el motor
> ejecuta de verdad, porque sus priors dan `max S(c) = 0,45 < 1`. Lo que lo sostiene es solo que es el
> incumbent y no hay evidencia admisible que lo sustituya. No se calibra
> porque las métricas no lo distinguirían. Ver el final.

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

---

## Actualización: dos bloques cerrados desde aquí

El estado de arriba («bloque 0 es el que bloquea») era cierto cuando se
escribió. Ya no.

| # | bloque | estado |
|---|---|---|
| **0** | definir el objetivo de `L_sec` | **CERRADO.** Objetivo: **ranking**, no probabilidad. Población: hero continúa o checkea, en validación. [`CONTRATO_L_SEC.md`](CONTRATO_L_SEC.md) §8, [`AUC_INTERVALO.md`](AUC_INTERVALO.md) |
| **1** | camino de equity preflop | **DESBLOQUEADO.** El objetivo ya está, así que se puede implementar. Y sus dos decisiones abiertas —exacto o muestreado, y qué pasa con la varianza— están medidas: muestreado a 40 combos, varianza admisible. [`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md) |
| **2** | una métrica que sobreviva al 86 % de derrotas | **CERRADO como ELECCIÓN:** equity como *ranking*, que es la opción que el propio bloque 2 enumeraba, y el AUC **no** depende de la base rate. Que **ordene bien** es otra pregunta, y con 11 manos de validación **no se puede afirmar** |
| **3** | qué significa `matrix` | **REABIERTO, y por una razón mejor.** Dos veces se ha cerrado con pruebas que no se sostenían. Lo que **sí** está medido: las 117 tablas no suman 1 (solo 1 lo hace) y sus celdas **sí** están en `[0,1]`; `sum(matrix)` es 0,3× `sum(cnt)`; y la coherencia por celda **se cumple para todo α ≥ 0 en la configuración que el motor ejecuta** (0 de 1014 celdas con `S(c) > 1`, máximo 0,45), sin cota inferior. Lo que **no**: qué clase de cosa es, que no se deduce de datos ([`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md)) |

### Lo que queda bloqueando Fase D

**Solo el bloque 3.** Y no por falta de datos: porque
`alpha · prior` no son pseudo-conteos y nadie ha dicho qué representa el
campo `matrix`.

### Y la cobertura

El AUC cubre **57 de 160** manos (35,6 %). Las otras 98 son cortes preflop, y
quedan fuera porque su equity es **retrospectiva**: usa las cartas reales del
rival. El bloque 1 las cubre, y con la varianza ya escrita en el contrato.

> Antes se decía 38 %. La cifra medida es **57 / 160**, y los 3 repartos que
> el AUC binario no admite están contados aparte. Se corrige el número, no el
> criterio.

---

## Corrección: el bloque 2 está cerrado como **elección**, no como resultado

La tabla de arriba ponía el bloque 2 en «CERRADO» con la coletilla
«Afirmable: 0,8308 con IC [0,6991, 0,9364]». Ese número estaba mal: la
evaluación mezclaba calibración y validación
([`CONTRATO_L_SEC.md`](CONTRATO_L_SEC.md) §11).

| | estado correcto |
|---|---|
| **2** | **CERRADO como elección.** La métrica es el AUC — equity como *ranking* — que es la opción que el propio bloque enumeraba y que no depende de la base rate. Lo que **no** es un resultado es que ordene bien: con 11 manos de validación el intervalo incluye 0,5 |

Y el estado de Fase D cambia por debajo:

| | antes | **ahora** |
|---|---|---|
| lo que bloquea | el bloque 3 | **el bloque 3, y la muestra** |

Porque el bloque 3 no se resuelve con datos, y la muestra **sí** es un
problema medible: 14 de 41 manos de validación entran al AUC. Las 23 que
quedan fuera son cortes preflop con equity retrospectiva, y el camino
preflop observable es justo lo que las mete.

> **Antes de este bloque se creía que el bloqueo era de cobertura (38 %).**
> Ahora se sabe que es de las dos cosas: cobertura **y** tamaño. Y las dos se
> pueden atacar: la cobertura con el camino preflop, el tamaño con más manos,
> que es un commit con su motivo y no un ajuste.

---

## El bloque 3 también está cerrado, y lo que queda

La tabla de arriba ponía el bloque 3 como «abierto, y no se resuelve con
datos». Cerrado: **se resuelve, y la respuesta es que `DEFAULT_ALPHA` no es
calibrable.**

### La prueba, que es aritmética y no interpretación

`p_matrix = (cnt + α·prior) / (opp + α)`. Sumando sobre las 169 celdas:

```
sum_celdas p_matrix = [ N_k + α·S_k ] / (opp + α)
```

`p_matrix` es P(acción|mano, spot) y las acciones de un spot son mutuamente
excluyentes, así que no puede pasar de 1. Como `sum_k N_k ≤ opp`, la única
forma es **`sum_k S_k ≤ 1`**.

Y medido: el prior **plano** del fold da `S = 0,15 × 169 = 25,35`. Se pasa
**25 veces** por sí solo, sin tocar una sola de las 117 tablas.

| | |
|---|---|
| las 117 tablas suman | de **0,91** a **89,75**, mediana **10,00** |
| tablas que suman ≈1 | **1 de 117** |
| celdas fuera de `[0, 1]` | **0** de 19 773 |
| `sum(matrix)` contra `sum(cnt)` para `open` | **0,3×** — no es la misma escala |

Las celdas **sí** son probabilidades: lo que faltó fue normalizar. Pero
normalizar **no basta**: normalizadas darían `S_k = 1`, y dos acciones de un
spot darían 2.

### Lo que sale de eso

> **`alpha · prior` no son pseudo-conteos. `DEFAULT_ALPHA` NO SE CALIBRA NUNCA.**

Tres razones medidas e independientes: `matrix` no suma 1, la fórmula no puede
ser un shrinkage, y `L_prim` es monótona en `alpha` (224 de 256 celdas empujan
en el mismo sentido).

### Y lo que sigue abierto, que es distinto de bloqueante

Qué clase de cosa es `matrix` **no** se sabe, y no se puede saber con datos:
las celdas están en `[0,1]`, las tablas no suman 1 y no hay relación con `cnt`,
pero eso acota la forma y no la intención. *Proporciones relativas* y
*conteos con otra base* dan el mismo 89,75 con Remedies distintos.

Y `preflop_matrices.json` no lleva metadatos. Eso hay que preguntárselo a
quien lo generó, y es una pregunta, no un bloque.

## Entonces, ¿qué bloquea Fase D ahora?

| | |
|---|---|
| el bloque 3 | ~~cerrado~~ → **REABIERTO**, la prueba no se sostenía |
| la métrica | **elegida** (AUC, equity como ranking) |
| **`DEFAULT_ALPHA`** | **no se calibra**, pero porque las métricas no distinguirían, no porque `alpha` no sea un parámetro |

> **Los cuatro bloques estaban cerrados y el 3 se ha reabierto.** La prueba
> que lo cerraba sumaba sobre las 169 manos cuando la exclusión mutua es
> **por mano**. Corregida, no aparece ninguna contradicción. Abajo está el
> cierre corregido.

Lo que queda por hacer es lo otro, y es distinto de desbloquear:

| | |
|---|---|
| el camino preflop observable | sin implementar. Sus dos decisiones ya están medidas y son ejecutables (3,3 h) |
| la cobertura | **14 manos de 41** entran al AUC. Las 23 que faltan son cortes preflop |
| más manos de validación | el reparto es `sha256(hand_id) % 10 < 3`, y cambiarlo es cambiar de fase |

Y con 11 manos en el AUC, el intervalo va a ser ancho **por pequeño que sea el
error del estimador**. Ese es el límite real, y no es un problema de código.

---

## El bloque 3 se reabre: la prueba no se sostenía

El bloque anterior cerró el bloque 3 con «`DEFAULT_ALPHA` no se calibra
nunca», y lo hizo sobre esta prueba:

> los priors de un spot tienen que sumar ≤ 1, y el prior plano del fold da
> 25,35

`revision_2` §2 tiene razón: **la exclusión mutua es por mano**, no sobre las
169 manos. Yo salté de una cosa a otra. El contraejemplo lo dice exacto: 169
celdas con 0,15 de fold cada una darían 25,35 **sin contradicción**, porque
cada celda es una mano distinta.

| | |
|---|---|
| lo que afirmaba | `sum_k S_k ≤ 1`, sumando sobre las **169 celdas** |
| lo que es | `sum_k p_k(c) ≤ 1`, **para cada celda** `c` |

### Y la prueba correcta no encuentra nada

Medido, con el motor en vez de con álgebra:

| | |
|---|---|
| celdas de `p_matrix` que pasan de 1 | **0** de 2 028 |
| `p_matrix` máximo | **0,7571** |
| suma por celda sobre acciones excluyentes | **0,9500**, máximo |

> **No hay contradicción.** La afirmación «`alpha` no es un parámetro de
> regularización» queda **retirada**: no se deduce.

### Lo que aparece al corregir el fold, y al revés de lo que se decía

Antes, con el bug, la sección decía que *«la suma por celda se pasa de 1 por
debajo»* y a continuación traía una tabla que decía *«coherente: sí»* en
todas las filas. Las dos cosas no pueden ser verdad, y la segunda es la
correcta: el «se pasa de 1» venía de sumar el prior crudo del fold.

Medido, con `p_matrix(…, 'fold')` como hace el motor:

| `alpha` | coherencia por celda |
|---:|---:|
| 0,05 | 0,9955 |
| 0,25 | 0,9780 |
| 0,50 | 0,9577 |
| 1,00 | 0,9214 |
| **1,3636** | **0,9080** |
| 2,00 | 0,8625 |
| 5,00 | 0,7500 |

> **No hay borde.** Ni un solo `alpha` rompe la invariante. El umbral de
> 1,3636 del bloque anterior era un **artefacto** de sumar el prior crudo del
> fold, y queda **retirado**.

Lo que **sí** tiene una condición es la afirmación universal: se deduce si
`S(c) ≤ 1`, y en la configuración que el motor ejecuta eso se cumple
(0 de 1014 celdas, máximo 0,45). Con las **tablas de posición** `no_raise`
llega a `S = 1,30` y ahí sí habría una cota superior. Ver
[`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md).

### El estado corregido

| bloque | estado |
|---|---|
| 0 · objetivo de `L_sec` | cerrado |
| 1 · camino preflop | desbloqueado, decisiones medidas |
| 2 · métrica que sobreviva | cerrado como **elección** |
| **3 · qué significa `matrix`** | **REABIERTO, y por una razón mejor**. Las dos veces que se cerró fue con una prueba que no se sostenía. Ahora sí hay cosas medidas —la forma de las tablas, la coherencia por celda para todo α ≥ 0— y sigue sin saberse qué clase de cosa es `matrix`, que no se deduce de datos |

> **«No se calibra» se sostiene, pero por una razón mucho más débil:** las
> métricas disponibles **no distinguirían**, porque `L_prim` es monótona y no
> hay árbitro secundario. No porque `alpha` deje de ser un parámetro de
> regularización. Y no es «nunca»: si alguien arregla `matrix` y trae una
> métrica no monótona, la pregunta vuelve.

### Lo que queda bloqueando Fase D

El bloque 3, otra vez, **y ahora por una razón mejor**: no es que las tablas
sean raras, es que **no sabemos qué son**. Eso hay que preguntárselo a quien
las generó, y no se resuelve con datos.


---

## El bloque 1: el camino está, y la métrica no se puede calcular

El bloque 1 («camino de equity preflop») sigue **DESBLOQUEADO**: el
objetivo ya está, la equity preflop está implementada en `motor/` y sus
decisiones abiertas —exacto o muestreado, y qué hacer con la varianza—
están medidas y escritas en [`CONTRATO_PREFLOP.md`](CONTRATO_PREFLOP.md).

Lo que se ha medido después es que **la métrica que ese camino iba a
servir no se puede calcular con esta base**. No es que falte trabajo, ni
que falte un número: es que la población que la métrica necesita **no
existe**.

| | |
|---|---:|
| cortes preflop de validación | 23 |
| los que son población B | **0** |
| los 23 que entran | folds, y con `y = 0` por construcción |

Y en la ventana fiable entera, de 877 manos:

| | |
|---|---:|
| continuaciones preflop (`b`/`c`/`r`/`x`) | 83 |
| con etiqueta | **0** |

> **«Desbloqueado» sin destino no es un desbloqueado.** Lo que se
> desbloqueó fue *implementar el camino*. Lo que se iba a medir con él no
> se puede medir. El bloque 1 no se cierra: se le quita el trabajo que
> tenía encima y se le deja el que sí tiene, que es la equity preflop
> como observable, sin AUC detrás.

### Por qué, y es una limitación de datos con una salvedad

`revision_1` lo describe como «una limitación de datos, no de código».
Medido, es **casi todo** eso, y no del todo:

| | |
|---|---:|
| las 83 se caen en el primer filtro de `muestra()`, `board_completo()` | 83 |
| de ellas, las que no tienen board de verdad porque la mano termina en preflop | 81 |
| de ellas, las que **sí** tienen board, en `streets.*.board`, con `comunitarias` vacío | **2** |

`board_completo()` exige `comunitarias.river >= 1` y se comprueba **antes**
del camino de victoria por fold, así que una victoria por fold limpia no
puede tener etiqueta. Eso es una decisión de **orden de filtros**, escrita
en el contrato firmado.

Y el contrafactual, que es lo que hace falta para poder decir «no se
calcula» sin excusas: si `board_completo()` se comprobara después, de las
83 **una sola** tendría etiqueta (`H_0485`, una call, `y = 1`), porque las
82 otras no tienen las cartas de ningún otro jugador. **Ni con otra regla
la pregunta es respondible.**

Detalle completo, con el caso a mano y el contador:
[`REPRESENTATIVIDAD_23.md`](REPRESENTATIVIDAD_23.md) §6.1, y
[`LIMITACION_PREFLOP_AUC.md`](LIMITACION_PREFLOP_AUC.md) para lo que la
desbloquearía.

### Y `DEFAULT_ALPHA` no se mueve

Se mantiene **2,0**, por el argumento (3): es el titular y ninguna
evidencia admisible justifica sustituirlo. Ni el argumento (2) ni este
AUC dependían de él, y este AUC **no se ha calculado**, así que no puede
informar. Lo que este bloque añade es una razón más para **no** tocarlo.

### El estado, una vez más

| bloque | estado |
|---|---|
| 0 · objetivo de `L_sec` | cerrado |
| 1 · camino preflop | **desbloqueado para implementar; su métrica NO es calculable con esta base** |
| 2 · métrica que sobreviva | cerrado como **elección** |
| 3 · qué significa `matrix` | **REABIERTO**, y sin cambio: no se deduce de datos |

**Lo que sigue bloqueando Fase D no ha cambiado: el bloque 3.** Lo que se
ha añadido es que el bloque 1 no puede cerrar el hueco por el lado de los
datos, porque en esta base no hay población que medir.
