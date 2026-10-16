# FASE D — bloqueada, y con la razón escrita

> **Estado al final de este bloque: los cuatro bloques están cerrados.**
>
> `DEFAULT_ALPHA` no se calibra porque `matrix` no es una probabilidad, y eso es un **resultado medido**, no un bloqueo.
> Lo que queda no es «desbloquear»: es más manos y el camino preflop. Abajo está el cierre.

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
| **3** | qué significa `matrix` | **abierto, y no se resuelve con datos** ([`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md)) |

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
| el bloque 3 | **cerrado** |
| la métrica | **elegida** (AUC, equity como ranking) |
| **`DEFAULT_ALPHA`** | **cerrado como NO CALIBRABLE**, con test |

> **Los cuatro bloques están cerrados. Fase D ya no está bloqueada por una
> decisión pendiente: está parada porque no se puede calibrar `alpha`, y eso
> es un resultado, no un bloqueo.**

Lo que queda por hacer es lo otro, y es distinto de desbloquear:

| | |
|---|---|
| el camino preflop observable | sin implementar. Sus dos decisiones ya están medidas y son ejecutables (3,3 h) |
| la cobertura | **14 manos de 41** entran al AUC. Las 23 que faltan son cortes preflop |
| más manos de validación | el reparto es `sha256(hand_id) % 10 < 3`, y cambiarlo es cambiar de fase |

Y con 11 manos en el AUC, el intervalo va a ser ancho **por pequeño que sea el
error del estimador**. Ese es el límite real, y no es un problema de código.
