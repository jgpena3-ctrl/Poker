# LOS CUATRO FRENTES INDEPENDIENTES, AUDITADOS Y CLASIFICADOS

> Y lo que se pide en cada uno no es una conclusión, sino la **clasificación**:
> qué parte se puede analizar desde el código, y qué parte depende de A1.
>
> Y la regla del reparto, que es la de siempre: **A2 puede mejorar la
> capacidad del motor para interpretar los datos; no puede dar por ciertos los
> datos que A1 todavía está validando.** Y por eso en ninguno de los cuatro se
> recalcula nada, y en ninguno se toca la base.

## 1. Las 5 manos con board divergente

Y la definición del problema, que está en `QUE_REPRESENTA_LA_PREDICCION.md`
§2.3: `tablero()` lee `comunitarias`, y `villain_hasta_corte()` lee
`streets.*.board`. Dos fuentes para el mismo tablero.

### Y primero, una correccion de la cuenta

MEDIDO, y la cuenta del documento **no se reproduce con el board entero**:

```
la ventana (877), comparando el board ENTERO   :  29 con numero distinto de cartas
la ventana (877), con la cuenta del documento  :   5
```

Y la diferencia está en **el corte**: la cifra del documento es por calle de
corte —el board hasta la calle en la que se decide—, y el board entero da 29.
Las 5 del documento están entre las 29 ✓.

> **Las dos cifras son correctas, y miden cosas distintas.** Y la que se cita
> en el documento es la que cuenta la divergencia **en el board que se usa**.
> Y por eso el alcance hay que decirlo, porque quien lo lea va a esperar 5 y
> va a medir 29.

### Y la clasificación, que es lo que se pedía

**DEL CÓDIGO, y se puede hacer ya:**

| | |
|---|---|
| las 29 de la ventana | `comunitarias` es un **subconjunto** de `streets`, y **nunca al revés**: el resumen está truncado, el board completo está en `streets` |
| 27 de ellas | el problema es una lista incompleta, no una contradicción. Y se puede **clasificar sin la grabación**: no hace falta el pantallazo para saber que una de las dos listas está truncada |
| qué fuente debe leer `tablero()` | es una decisión de instrumentación, y **cambia los números**, de modo que va con la recalibración |

**DE A1, y son dos:**

| | |
|---|---|
| `H_0915` | `comunitarias` dice `2s` y `streets` dice `6c`: **una carta distinta** |
| `H_0921` | `comunitarias` dice `2s` y `streets` dice `9c`: **una carta distinta** |

> Y en esas dos, cuál de las dos cartas es la buena **no lo decide el dato**:
> hace falta la grabación. Y eso es de A1, y es una decisión de una carta por
> mano, no de instrumentación.

**Y una consecuencia que hay que tener presente:** el número de manos afectadas
depende de la base que se adopte, y la copia tiene 1258 manos y no 877. De modo
que **la cuenta de este frente hay que repetirla después de la adopción**, y no
es un número que se pueda fijar ahora.

## 2. `matrix`

Y lo que se medido es el alcance del fichero, que es lo que hace la auditoría
útil:

**MEDIDO, `data/preflop_matrices.json` (328 548 bytes) lo leen ONCE ficheros:**

```
motor/__init__.py      motor/_procedencia.py    motor/asistente_live.py
motor/learn.py         motor/player_ranges.py   motor/preflop.py
motor/profile.py
tools/auditar_matrix.py
```

> **Siete módulos del motor dependen de él.** De modo que el frente de
> `matrix` no es «un fichero que hay que entender»: es **el fichero del que
> dependen siete módulos**, y cualquier cosa que se le cambie se propaga a
> todos.

Y lo que NO se hace, y por qué: no se regenera ninguna matriz, y no se cambia
la semántica de ninguna. La pregunta de `QUE_ES_MATRIX.md` —qué significa el
fichero— sigue siendo de quien lo generó, y hasta que la responda, auditar
«las dependencias del cálculo» es auditar **el grafo de dependencia**, que es
lo que está medido aquí.

**DE A1, o de quien generó el fichero:** la intención.
**DEL CÓDIGO:** el grafo de dependencia, que está medido.

## 3. La vía preflop del motor

Y lo que hay, medido, son **dos contratos ya escritos**: `CONTRATO_PREFLOP.md` y
`CONTRATO_L_SEC.md`. Y los dos tienen la misma forma, y la forma es la clave:

```
CONTRATO_PREFLOP.md
    ## Firma propuesta
    ## Dos decisiones que hay que tomar antes de codificar
    ## Lo que este contrato NO resuelve
    ## Lo que queda abierto
```

> **El contrato de la vía preflop está escrito y NO está firmado, y su propia
> sección de decisiones pendientes es lo que falta.** De modo que el frente no
> es «escribir el contrato» —está escrito— sino **tomar las dos decisiones que
> el contrato dice que hay que tomar antes de codificar**, y que son:
> muestreado con `n_combos = 40`, y que la varianza es admisible.

**DEL CÓDIGO:** la forma del contrato, sus dos decisiones pendientes y sus
apartados de «lo que NO resuelve».
**DE QUIEN DECIDE EL OBJETIVO:** las dos decisiones, porque son de alcance y no
de instrumentación.

## 4. El peso por rival

Y lo medido, y es poco, y es lo que importa: **el AUC usa la MEDIANA** de las
equities por rival, y hay **un solo sitio** donde se toma:

```
tools/auditar_auc.py:299
    filas.append((r[1]['mediana'], y, acts[idx].get('action')))
```

**MEDIDO, y las condiciones de aplicación, que son las del propio dato:**

| | |
|---|---|
| qué se agrega | la **mediana** de las equities de los rivales VIVOS en la calle de corte |
| dónde | `equity_de_mano()` la calcula, y `auditar_auc.py` la consume |
| por qué la mediana | con 415 de 877 cortes con más de un rival, «la equity del héroe» no es un número: es una lista |

**DEL CÓDIGO:** la lógica de agregación, que es una línea, y su condición de
aplicación, que es «los rivales vivos en la calle de corte».
**DE QUIEN DECIDE EL OBJETIVO:** si la mediana es la reducción correcta, que es
una cuestión de póquer y no de instrumentación. Y por eso **no se toca**: un
cambio de reducción cambia la métrica, y la métrica publicada no se mueve por
criterio de un bloque de instrumentación.

## 5. Y EL RESUMEN, que es lo que hay que llevarse

| frente | del código | de A1, o de quien decide |
|---|---|---|
| las 5 divergentes | 27 de 29 son un resumen truncado, y se clasifican sin la grabación | 2 cartas, una en `H_0915` y otra en `H_0921`. Y la cuenta hay que repetirla tras la adopción |
| `matrix` | el grafo: 7 módulos del motor dependen del fichero | la intención del fichero |
| la vía preflop | el contrato está escrito, con sus dos decisiones pendientes | las dos decisiones, y el alcance del contrato |
| el peso por rival | la agregación es una línea, y su condición son los rivales vivos | si la mediana es la reducción correcta |

> Y el patrón de los cuatro es el mismo, y es el del proyecto entero:
> **la parte que se puede decidir desde el código está medida y es pequeña; y
> la parte que depende de los datos es de otra persona, y no se toca.**
