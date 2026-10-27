# QUÉ REPRESENTA LA PREDICCIÓN, EN CADA CORTE

> Esto es lo que `revision_2` pide antes de decidir si se adopta el corte en
> la primera decisión: **qué representa exactamente la predicción evaluada en
> cada corte**. No estaba escrito en ningún `.md`.
>
> **No es un contrato y no propone nada.** Es lo que el código hace, medido.
> La decisión de si B es un cambio de objetivo sigue siendo de otro sitio,
> y este documento no la toca.

## 1. El corte

`corte_de_decision(h, hero_pos)` devuelve `(calle, indice)`: la **última**
acción del héroe entre `b`/`c`/`r`/`f`/`x`, recorriendo las calles al revés.

El índice es dentro de esa calle, y hace falta. El docstring lo dice y es
correcto: si el héroe y el rival juegan en la misma calle, la acción del
rival puede ser posterior, y mirarla sería mirar al futuro.

**Medido sobre las 877 manos de la ventana fiable:**

| | |
|---|---:|
| cortes con la misma calle en A y en B | 633 |
| **cortes con calle distinta** | **233** |
| — de esos, con board de tamaño distinto | **230** |
| — de esos, con número de rivales distinto | **142** |

**Por eso A y B no son un recorte del mismo conjunto: son evaluaciones
distintas.** De 233 cortes, 230 miran un tablero de otro tamaño y 142
contestan a otro conjunto de rivales. El ejemplo más claro:

| | corte en la **última** | corte en la **primera** |
|---|---|---|
| `H_0001` | river, 5 cartas, 2 rivales | **preflop**, 0 cartas, 4 rivales |

Cambiar el corte no cambia *qué se pregunta*: cambia la pregunta.

## 2. La predicción postflop: qué es y qué sabe

Es la equity del héroe **en el instante de su acción**, contra el rango
modelado de un rival. Concretamente, y todo esto sale de
[`tools/equity_de_mano.py`](../tools/equity_de_mano.py):

| pieza | de dónde sale | qué es |
|---|---|---|
| cartas del héroe | `cartas_de()` | las del registro |
| board | `tablero()` | cartas públicas **hasta la calle del corte inclusive** |
| rango del rival | `modelo.prob_vec(perfil, spot, action)` | el alcance preflop de ese rival, por su perfil |
| cartas conocidas | `rs.set_known_cards(hero + board)` | **solo** las del héroe y el board |
| refinado postflop | `villain_hasta_corte()` | las acciones **observadas** del rival hasta el corte |

### 2.1 Lo que deliberadamente NO entra

`rango_del_rival()` lleva un comentario que vale por sí solo, y se conserva
aquí porque es una decisión de información, no un detalle:

> No se puede hacer mejor con estos datos: el registro guarda las cartas
> finales de cada jugador y no dice EN QUÉ MOMENTO se revelaron. Añadir las
> de terceros sería inventar que se sabían.

Antes se metían las cartas de todos los demás con cartas en el registro: 216
cartas que en la calle del punto de decisión no se conocían de nadie, y el
héroe entrando dos veces. **310 cartas contadas de más.**

Eso importa para el AUC: un AUC con 310 cartas fantasma no mide la decisión
del héroe, mide una decisión con información que no existía.

### 2.2 El marcador `observable`

`equity_contra()` marca cada predicción:

| vía | `observable` | qué significa |
|---|---|---|
| `situation(...)` postflop | `True` | se puede reproducir con lo que se sabía en ese instante |
| enumeración preflop | `False` | usa las cartas **reales** del rival |

El preflop es retrospectivo por necesidad, no por comodidad: el motor **no
tiene camino de equity preflop**. `evaluate_batch` declara board de 3 a 5
cartas, así que `situation` no tiene camino preflop y `runout_equity` con
board vacío falla por la misma causa (`_SUBSETS` tiene 5, 6 y 7, y pide el 2).

La enumeración contra las cartas reales «sirve para auditar el evaluador y
para estudiar manos. NO es la equity de una decisión».

### 2.3 Y el board tiene DOS fuentes, y discrepan

Este es un hallazgo, y no estaba escrito.

- `tablero()` lee **`comunitarias`**.
- `villain_hasta_corte()` lee **`streets.*.board`**.

Dos fuentes para el mismo tablero, en la misma función, para el mismo
cálculo. Y no coinciden.

**Medido: 5 manos de 877 donde difieren.**

| | `comunitarias` | `streets.*.board` |
|---|---|---:|
| `H_0349` | 0 | 5 |
| `H_0358` | 4 | 5 |
| `H_0367` | 0 | 3 |
| `H_0387` | 3 | 5 |
| `H_0590` | 0 | 4 |

En esas manos el rango del rival se refina con un board que `tablero()` no
ve. **No se corrige aquí**: es un cambio de instrumentación, exige medir de
nuevo y no es lo que R2 pide. Se deja medido y escrito, que es lo que hace
falta para poder decidir.

> **Y esto NO es lo mismo que el otro board que se ha medido.** El de la
> población preflop son 2 manos de las 76; este son 5 de las 877 y son
> postflop. No son el mismo problema y no se mezclan.

## 3. La predicción NO es un número por mano

`candidatos()` da **todos** los rivales que siguen en la mano en la calle del
corte, en el orden de la mesa. `equity_de_mano()` devuelve una equity **por
rival**, más `dispersion` (máx − mín) y `mediana`.

**Medido:**

| rivales vivos en la calle del corte | manos |
|---:|---:|
| 0 | 139 |
| 1 | 331 |
| 2 | 264 |
| 3 | 102 |
| 4 | 27 |
| 5 | 3 |

**396 de 877 tienen más de un rival.** Es decir: para casi la mitad de las
manos, «la predicción» no es un número, es una lista, y **reducirla a uno es
una decisión de quien mide**.

Y esa decisión **no está escrita en ningún sitio**. El propio código lo
reconoce:

> Devuelve un dict `rival_pos -> equity` más la dispersión, porque la
> elección de rival es una decisión de quien mide y tiene que quedar a la
> vista.

La `mediana` la usan seis herramientas (`auditar_auc`, `auditar_matrix`,
`auditar_origen`, `auditar_preflop_varianza` y dos tests). Lo que **no**
está escrito es si esa es la elección correcta para el AUC, ni por qué.

**Esto es lo que hay que decidir antes de B**, y no es un detalle de
implementación: cambiar el corte cambia el conjunto de rivales (142 de los
233 cortes que cambian de calle), así que la elección de reducir a un número
deja de ser neutra.

## 4. Qué reducción se usa, y cuánto importa

**La que se usa es la mediana, sin ponderar.** Está en una línea:

```python
# tools/auditar_auc.py:299
filas.append((r[1]['mediana'], y, acts[idx].get('action')))
```

Y no estaba escrita en ningún `.md`. Ahora sí.

### 4.1 Y cuánto mueve

Medido sobre las seis reducciones razonables, en la **población del AUC**:

| reducción | n | AUC | IC |
|---|---:|---:|---|
| **mediana** — la que se usa | 11 | **0,7667** | [0,4333; 1,0000] |
| media | 11 | 0,7667 | [0,4333; 1,0000] |
| primer rival de la mesa | 11 | 0,7667 | [0,4333; 1,0000] |
| último rival de la mesa | 11 | 0,8000 | [0,5000; 1,0000] |
| mínimo | 11 | 0,7667 | [0,4333; 1,0000] |
| máximo | 11 | 0,8000 | [0,5000; 1,0000] |

**Recorrido: 0,0333. Amplitud del IC ya publicado: 0,5667.**

Y el motivo por el que el recorrido es tan pequeño: **1 de las 11
observaciones** tiene más de un rival. Las otras 10 tienen una sola equity, y
para una sola equity todas las reducciones coinciden.

En la muestra etiquetada postflop entera, sin el filtro de validación, **11 de
47** tienen más de un rival y el recorrido es **0,0169**. Menor todavía.

**Para este AUC, la elección es un detalle.** Y conviene decirlo con sus
palabras exactas: *para este AUC y con estas manos*. Con 11 observaciones,
cualquier cosa mueve un AUC.

### 4.2 Cómo se midió, y el rodeo que hubo que deshacer

La primera medición dio 47 observaciones y 0,8308. Dos filtros posibles:

- **los folds**: `resto_de_muestra` etiqueta los folds, porque una victoria
  por fold tiene etiqueta. Medido: las 48 postflop con etiqueta son las 48 de
  población B. **Cero folds.** No era eso.
- **la partición**: `muestra()` devuelve calibración **y** validación, y
  `resto_de_muestra` etiqueta las dos porque las dos tienen etiqueta. Pero el
  AUC se publica sobre la validación. **Era ese.**

La prueba de que el filtro es la **causa** de la diferencia no es que
«parezca». Son **dos**, y la segunda es la que convence:

| | n | AUC |
|---|---:|---:|
| con el filtro de partición | 11 | **0,7667** — el publicado |
| **sin** el filtro | 47 | **0,8308** — el de la versión **incorrecta** |

El mismo AUC a cuatro decimales, y no uno cualquiera. `AUC_INTERVALO.md`
cuenta que la versión anterior de ese documento publicó 0,8308 porque el
código mezclaba calibración y validación.

**Y esto es lo que hace que la prueba sea una prueba y no una
coincidencia.** Una medición sin el filtro de partición no da un número
aleatorio: **da el número del bug**, que es un número que ya se sabe cuál
es. Si tu medición te da *ese*, y con el filtro te da el otro, has
encontrado exactamente la línea que los separa.

Y tiene una consecuencia más allá de este caso: si el 0,8308 se puede
reproducir a mano, se puede reproducir en cualquier sitio donde el código
corra sin el filtro. El guard de `test_auditar_auc.py` —
`test_no_evalua_manos_de_calibracion`— no es una comprobación de estilo:
**es lo único que separa los dos números.**

> Y una precisión que hace falta aquí, porque sin ella el documento se
> contradice cuarenta líneas más abajo: esto prueba que el filtro es la
> **causa** de la diferencia, y **no** que sea el correcto. Lo que no está
> demostrado, y de dónde sale la validez, está en §4.3.

**Y esa es la regla que hay que aplicarle a toda medición que se compare
con una cifra publicada: que la reproduzca.** Una medición que no
reproduce la cifra publicada no mide lo que dice medir, y el siguiente paso
es siempre mirar la población antes que el número.

### 4.3 Y lo que esta prueba NO demuestra

Porque hay que separar dos cosas que se parecen y no son lo mismo:

**El filtro es la CAUSA de la diferencia.** Eso está demostrado, y es una
prueba causal: quitarlo produce 0,8308, ponerlo produce 0,7667, y 0,8308 es
el número que `AUC_INTERVALO.md` dice que se publicó por error. No es una
coincidencia y no es una correlación: es el mecanismo.

**El filtro es el CORRECTO.** Eso **no** está demostrado, y no lo puede
estar con esta prueba. «El filtro explica por qué los dos números difieren»
no es «el filtro está bien». Son dos afirmaciones distintas, y confundirlas
es el error que este proyecto lleva cuatro bloques corrigiendo en otro
sitio: creer que una explicación correcta es una conclusión correcta.

De dónde sale la validez, entonces: de
[`CONTRATO_L_SEC.md`](CONTRATO_L_SEC.md) §«Población», que es lo que declara
que la población es «solo manos donde el héroe continúa» y por qué el check
cuenta aparte. **Eso es un hecho del contrato, no una consecuencia de que el
AUC salga con dos decimales.**

Y hay una consecuencia práctica que conviene tener presente: si alguien
cambia la definición de la población en el contrato, **el filtro no dejará de
ser la causa de la diferencia** —seguirá explicando por qué 0,8308 y 0,7667
difieren—, pero dejará de ser el filtro correcto. **La prueba que hay aquí no
lo detecta.** Lo que lo detectaría es el contrato, y por eso el contrato está
firmado y no se toca en un bloque de auditoría.

## 5. Lo que queda sin escribir

Tres, de los cuatro que había. El primero ya está:

1. ~~Qué reducción a un número se usa en el AUC~~ → **§4: es la mediana, y
   para este AUC no importa.**
2. **Qué se hace con las 5 manos de board divergente.** Hoy se refina el
   rango con un board que el cálculo no ve. Es medible y es corregible, pero
   corregirlo mueve las cifras, y eso es otro bloque.
3. **Si el preflop entra alguna vez**, con qué vía. Hoy la única es
   retrospectiva y marcada como tal, y el motor no tiene la otra.
4. **Si la predicción se pondera por rival.** Con 4 rivales y una equity
   para cada una, «la equity del héroe» no tiene un valor único salvo que se
   declare cuál. Y nótese que §4 no contesta esto: que la reducción *no mueva
   el AUC* no significa que la *ponderación* no importe, porque la ponderación
   no está medida.

Ninguno de los tres se resuelve aquí. Los tres son prerequisites de la
decisión, y la decisión sigue siendo de otro sitio.