# AUDITORIA DE `preflop_matrices.json`: el mapa, los contratos y los hallazgos

> Y lo que se pide en esta auditoria no es una conclusión sobre el fichero,
> sino tres cosas: **el mapa real de quien lo lee**, **los contratos de
> lectura** que se examinan, y **la clasificación de cada hallazgo** en una de
> las cinco categorías del reparto.
>
> Y la regla del reparto, que es la de siempre: **A2 puede mejorar la
> capacidad del motor para interpretar los datos; no puede dar por ciertos los
> datos que A1 todavía no ha validado.** Y por eso en esta auditoría **no se
> toca ni una celda** del fichero, ni se regenera ninguna matriz, y la
> **intención** del fichero queda reservada para A1.

## 1. EL MAPA REAL, Y UNA CORRECCION

MEDIDO, `data/preflop_matrices.json` lo mencionan once ficheros del
repositorio. Y la cuenta de «siete módulos que dependen de él» que salió en
`AUDITORIA_FRONTES.md` **era demasiado generosa**, y aquí está la verdad:

| módulo | ¿lee el fichero? | qué hace con él |
|---|---|---|
| `motor/preflop.py` | **SÍ, es el lector** | carga las 117 tablas y las mapea a vectores de 1326 combos |
| `motor/player_ranges.py` | **SÍ, con su propio cargador** | saca de ahí el *prior* del shrinkage |
| `motor/profile.py` | **SÍ** | saca de ahí la tasa base de cada tabla, para el factor ω |
| `motor/asistente_live.py` | **SÍ, a través de `preflop.py`** | sortea la acción preflop con las frecuencias |
| `motor/learn.py` | no | solo se lo **menciona**: su agregación por (jugador, posición) es lo que permite **validar** el fichero contra la base |
| `motor/_procedencia.py` | no | lo **declara como fuente** en `RUTAS_RELEVANTES`, para la reproducibilidad |
| `motor/__init__.py` | no | solo lo **menciona** en el docstring del paquete |

> **Tres leen el fichero, uno lo lee a través de otro, y tres solo lo
> mencionan.** Y la distinción importa: los tres primeros son *consumidores*,
> y los otros tres son *documentación o validación*.

## 2. LA FORMA DEL FICHERO, MEDIDA

```
MEDIDO, 117 tablas, y 0 con algo que no cuadra
MEDIDO, las claves de cada tabla: ['action', 'matrix', 'pos', 'vs']
MEDIDO, por prefijo: 3B 15, 4B 15, 5B 15, Call 53, OR 5, Over 3, ROL 5, SQUEEZE 6
MEDIDO, las posiciones: BB, BTN, CO, MP, SB, UTG
MEDIDO, las tasas base ponderadas: de 0.0030 (Call_4B_BB_vs_UTG) a 0.4397 (OR_SB)
MEDIDO, y las 117 están dentro de [0, 1]
```

> **El fichero está entero.** Y eso no es una opinión: no le falta ni una
> celda, y ninguna celda es un texto.

## 3. LA COBERTURA, Y QUE ES ESTRUCTURAL Y QUE NO

MEDIDO, hay **324 spots** (prefijo × posición del héroe × posición del rival),
y **252 tienen tabla**: el **78 %**.

| prefijo | UTG | MP | CO | BTN | SB | BB |
|---|---:|---:|---:|---:|---:|---:|
| OR | 1 | 1 | 1 | 1 | 1 | **—** |
| ROL | **—** | 1 | 1 | 1 | 1 | 1 |
| 3B | **—** | 1 | 2 | 3 | 4 | 5 |
| Call_OR | **—** | **—** | **—** | 3 | **—** | 5 |
| 4B | 5 | 4 | 3 | 2 | 1 | **—** |
| 5B | **—** | 1 | 2 | 3 | 4 | 5 |

> Y el hueco es en buena parte **ESTRUCTURAL**: el UTG no puede enfrentarse a
> una apertura, y el BB no puede abrir. Y por eso `OR_BB` y `ROL_UTG` no
> existen, y no es un fallo del fichero: es que el spot no existe.
>
> Y **lo que NO es estructural**: `Call_OR` no tiene tabla para MP, CO ni SB.
> Y eso quiere decir que, en esos spots, el modelo dice «subir o foldear» y no
> «igualar una apertura». Y eso es una DECISIÓN del modelo, no un fallo, y
> está fijada por los tests (`motor/test_asistente_live.py`).

## 4. LOS CONTRATOS DE LECTURA, Y CADA UNO DICE LO SUYO

Y esta es la tabla que importa, porque es donde los consumidores se distinguen:

| | tabla ausente | matriz dañada | quién lo lee |
|---|---|---|---|
| `preflop.prob` | **`None`** | **lanza** al cargar | el motor entero |
| `preflop.prob_or_fallback` | vector uniforme + `fuente='uniform'` | lanza | quien necesite un número |
| `player_ranges._prior_grid` | prior plano + **aviso** | **prior plano + aviso** (corregido aquí) | el shrinkage de perfiles |
| `profile.load_base_rates` | la tabla **no está** en las tasas | **la tabla no está** (corregido aquí) | el factor ω |
| `asistente_live._pf_freq` | **`None`** | lanza (hereda de `preflop`) | la recomendación preflop |

> Y las **tres respuestas distintas a la misma pregunta** —«la tabla de
> apertura del BB»—: `preflop` dice `None`, el asistente dice `None`, y
> `player_ranges` dice «prior plano de 0.15» **con un aviso**. Y las tres son
> defendibles por separado, y lo que faltaba era que cada una dijera cuál es
> la suya.

## 5. LOS HALLAZGOS, Y SU CATEGORÍA

| # | hallazgo | categoría | qué se ha hecho |
|---|---|---|---|
| **H1** | `profile.load_base_rates` se comía las filas y celdas dañadas y devolvía una **tasa plausible y falsa**: MEDIDO, con una fila de 12 celdas la tasa salía 0.10, sin decir nada | *Fallback sin respaldo* | **corregido**: una tabla dañada es una tabla **ausente**, y se avisa. Y la ausencia la ve `omega`, que la devuelve como `None` |
| **H2** | `player_ranges._prior_grid` no miraba la **forma** de la matriz: una de (12, 13) pasaba como prior, y el fallo aparecía más tarde y lejos —una suma de formas que no encaja, o un índice fuera de rango al mapear a combos— | *Contrato de lectura incumplido* | **corregido**: la forma se comprueba, y si no es 13×13 cae en el prior plano con aviso, que es su propio contrato |
| **H3** | `asistente_live._recom_preflop` convierte la **ausencia de tabla en frecuencia cero** con `or 0.0`: MEDIDO, `ROL_UTG` no existe, y un UTG con un limp delante se leía como «over-limp 0 %», o sea «retirar 100 %» | *fallback declarado* | **NO se toca el comportamiento**: la convención está **fijada por los tests** (`test_recom_preflop_sb_no_pide_call_sin_tabla`: «no se inventa un call, lo más apegado a las tablas») y es coherente con la rama de la apertura, que ya devolvía `None`. Lo que faltaba era que la convención estuviera **escrita en un sitio**, y ahora está en `motor/test_lectura_matrices.py` |
| **H4** | Tres lectores con **tres reglas de elección** de tabla, y ninguna que las compare | *Dependencia indirecta no documentada* | **documentado y probado**: `motor/test_lectura_matrices.py` fija, caso por caso, qué tabla elige cada uno |
| **H5** | **Qué significa una celda**, y si el número de la tabla tiene que sumar 1 | *Valor estadístico cuya validez depende de la intención* | **RESERVADO PARA A1**, sin modificar nada |

> Y H3 es el hallazgo más instructivo del bloque, y no por lo que dice, sino
> por lo que **no** dice: **no es un defecto**. Es una convención declarada
> por los tests, y el error era mío, que la iba a «arreglar» sin haberlos
> leído. Y la lección queda en `LECCIONES_DE_INSTRUMENTACION.md` §31.

## 6. LAS PRUEBAS, Y CON QUE DATOS

Y el fichero nuevo es `motor/test_lectura_matrices.py`, con **10 tests**, y
todos con **datos sintéticos**:

| | qué comprueba |
|---|---|
| `test_una_matriz_con_una_fila_dana_no_da_una_tasa_falsa` | H1, la regresión |
| `test_una_matriz_con_una_celda_no_numerica_no_da_una_tasa_falsa` | H1, la otra mitad |
| `test_una_matriz_entera_si_da_una_tasa` | que el camino bueno no se ha roto |
| `test_un_prior_con_la_matriz_dana_cae_en_el_prior_plano` | H2, la regresión |
| `test_el_lector_distingue_ausencia_de_cero` | que `None` y `0.0` son cosas distintas |
| `test_el_lector_del_asistente_tambien_distingue` | lo mismo en el segundo lector |
| `test_el_fallback_uniforme_dice_de_donde_sale` | que el fallback declara su fuente |
| `test_los_tres_lectores_responden_distinto_a_lo_mismo` | el grafo, por comportamiento |
| `test_cada_lector_elige_la_tabla_exacta_y_no_otra` | la regla de elección de cada uno |
| `test_el_fichero_real_esta_entero` | que el fichero real no le falta ni una celda |

> Y **el fichero real no se lee para medir nada**: los datos son sintéticos y
> controlados, celda a celda, y se sabe exactamente qué son. Y la razón es la
> de siempre: **la intención del fichero no está fijada**, y un test que
> dependiera de sus números heredaría esa falta.

## 7. LO QUE ESTA RESERVADO PARA A1

| | |
|---|---|
| **qué significa una celda** | MEDIDO, las 117 tablas dan tasas base de 0.0030 a 0.4397, y todas en [0, 1]. Y eso es una comprobación de **integridad**, no de **significado**: qué quiere decir una celda, y si su valor es una probabilidad, una frecuencia o un peso, es lo que `QUE_ES_MATRIX.md` deja abierto |
| **el 22 % de spots sin tabla** | si la ausencia es «no modelado» o «no ocurre», y si el modelo debe cubrir esos spots, es una decisión del modelo, no de instrumentación |
| **la regla de `Call_OR`** | que MP, CO y SB no tengan tabla de «igualar una apertura» puede ser una decisión («subir o foldear») o un hueco. Y es lo que decide si el asistente debe recomendar igualar en esos spots |

## 8. DECISIONES PENDIENTES DE A1

Y son tres, y cada una con tres cosas: **qué se decide**, **qué depende de
la decisión** y **qué no se toca mientras no se decida**. Y la tercera es la
que importa: sin ella, «pendiente» es una palabra, y con ella es una
frontera.

### D1 — QUÉ SIGNIFICA UNA CELDA

| | |
|---|---|
| **qué se decide** | si el valor de una celda es una probabilidad, una frecuencia o un peso; y si la tabla tiene que sumar 1 |
| **qué depende** | `preflop.prob` la usa como P(A\|H) y la mete en un update bayesiano; `player_ranges` la usa como prior de un shrinkage; `profile` la pondera por combos para el factor ω |
| **qué NO se toca** | ninguna celda, ninguna matriz regenerada, y **ninguna regla de selección**: el grafo de lectores no se mueve hasta que esto esté declarado |

> Y lo que ya está medido, y es una integridad y no un significado: las 117
> tablas dan tasas base de 0.0030 a 0.4397, y todas en [0, 1], y a ninguna le
> falta una celda.

### D2 — EL 22 % DE SPOTS SIN TABLA

| | |
|---|---|
| **qué se decide** | si la ausencia es «no modelado» o «no ocurre»; y si el modelo debe cubrir esos spots |
| **qué depende** | la recomendación preflop: MEDIDO, `Call_OR` no tiene tabla para MP, CO ni SB, de modo que en esos spots el modelo no contempla «igualar una apertura» |
| **qué NO se toca** | la **convención** de la ausencia —que una tabla ausente es un 0 para esa acción—, que está declarada por los tests de `asistente_live`, y que por eso no se cambia a ciegas |

### D3 — LA REGLA DE `Call_OR`

| | |
|---|---|
| **qué se decide** | si MP, CO y SB sin tabla de «igualar una apertura» es una decisión del modelo («subir o foldear») o un hueco |
| **qué depende** | lo mismo que D2, y por eso van juntas: la respuesta a D3 es una parte de la de D2 |
| **qué NO se toca** | las tablas de `Call_*`, y su contenido; y la **fórmula** por rival, que es de otra decisión |

> Y las tres son de A1, y no de instrumentación, y el motivo es el mismo de
> siempre: **la intención no está en el fichero**, y deducirla del fichero es
> adivinar.

## 9. Y LO QUE NO SE HACE, Y POR QUÉ

| | |
|---|---|
| tocar una celda | la intención es de A1, y un cambio sin ella es un cambio a ciegas |
| regenerar las matrices | exige recalibrar, y la recalibración es post-adopción |
| cambiar la regla de selección de un lector | es el grafo, y el grafo no se toca sin la intención |
| «arreglar» la convención de la ausencia | está declarada por los tests, y una excepción declarada no se toca: se documenta |
