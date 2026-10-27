# FASE D — plan de calibración

**Estado:** vigente. Es la primera vez que Fase D tiene plan.
**Base:** revisión manual en `H_1070`; derivados regenerados.
**Baseline:** `a694eee3b79508b94b5fedfc5816c63895bccb4a`
**Derivados (sha256, primeros 16):**

| fichero | sha256 | bytes |
|---|---|---|
| `preflop_stats.json` | `e2c3b803b0f5ede6` | 149 053 |
| `player_stats.json` | `b176fc4890b1a85b` | 88 573 |
| `profiles.json` | `9915aeb0da7b9a59` | 78 020 |
| `profile_ranges.json` | `c912013c8aa1b194` | 93 649 |
| `postflop_ranges.json` | `ca954e5b399709f3` | 13 203 |
| `observations.json` | `c0a24d7146138bfd` | 4 896 333 |
| `behavior.json` | `4fbee70801443a03` | 27 550 |

> El baseline es un **SHA exacto**, no «HEAD». «El baseline es HEAD» es
> cierto el día que se escribe y falso el día que se ejecuta, que es el día
> que importa.
>
**Precedente:** este proyecto lleva diez bloques defendiendo que nada se
activa sin contrato, sin ventana declarada y sin criterio de parada. Una
calibración es una de las tres cosas que mas rompen eso, así que empieza
por escribir las reglas.

> **Sin este documento no se calibra.** `revision_1`: *«No calibres sin
> FASE_D_PLAN.md. Sin plan, la calibración es "tocar parámetros a ver qué
> pasa"»*. Y tiene razón: los cuatro puntos de §2 son los que hacen que esto
> sea reversible.

---

## 0. Antes de calibrar: lo que habia que cerrar, y lo que queda

### 0.1 Un jugador inventado en los derivados — CERRADO

Al regenerar los derivados apareció un jugador llamado **`CO`** en
`player_stats.json` y `profiles.json`, con `n: 0`, todos los bins en `n/a`,
`stack_mean: None`, y etiqueta **`TIBURON`** con confianza `0.0`.

`CO` no es un jugador: es una posición. Rastreado hasta el origen:

| | |
|---|---|
| manos | `H_0519` (turn) y `H_0846` (preflop) |
| causa | tienen acciones cuyo `pos` no corresponde a **ningún** jugador de la mano |
| efecto | el código usaba la **posición como nombre del jugador** |
| medido | 2 observaciones de 9252, y 2 `PreflopEvent` de 4561 |

Y el defecto ya estaba clasificado: son exactamente las dos
`ACCION_FANTASMA` que quedan. **El defecto y el síntoma son las mismas dos
manos.**

Un perfil con cero observaciones no debería llevar etiqueta. `TIBURON` con
confianza `0.0` y `stack_mean: None` es un número inventado con forma de dato,
y paraba justo en `profile_ranges.json`, que es de las tablas que esta fase
quiere calibrar.

> ⚠️ **No era un bug, eran TRES.** El patrón `x.get(pos, pos)` estaba en
> `motor/learn.py` (`preflop_events`), `motor/observations.py`
> (`extract_hand`) y `motor/stats.py` (`_collect_hand`). Arreglé uno y el `CO`
> seguía saliendo, porque en `stats.py` se usa en **dos** sitios y el segundo es
> el bucle **post**flop. Un patrón duplicado es exactamente como vuelve un bug.

**Cómo se cerró:**

| | |
|---|---|
| `learn.py` | `player = ''` cuando la posición no tiene jugador. El evento **sigue contando** en el denominador: la decisión ocurrió, lo que no se sabe es de quién |
| `observations.py` | la acción se **descarta**: no pertenece a nadie |
| `stats.py` | la acción se **descarta**: son estadísticas **por jugador** |

**Criterio, comprobado sobre los ficheros regenerados:**

```
player_stats.json   146 claves | posiciones como clave: NINGUNA
profiles.json        146 claves | posiciones como clave: NINGUNA
perfiles con n=0: ninguno
```

Y un invariante sobre las **1258** manos: ningún `PreflopEvent` usa su posición
como nombre. Antes había dos.

**Lo que queda, y es del mantenedor:** corregir los datos de `H_0519` y
`H_0846`. El código ya no los convierte en jugadores, pero las dos acciones
fantasma siguen ahí, y `tools/auditar_rango.py::accion_fantasma` sigue
reportándolas. Que es lo correcto: el guard es de «no inventes», no de
«borra el defecto».

### 0.2 Los 4 defectos sistémicos: medidos sobre `H_1070`

`revision_1` pedía confirmar que no bloquean. **Medido:**

| defecto | publicado | ahora | dentro de la ventana de 877 | fuera |
|---|---:|---:|---:|---:|
| `IMPORTE_SUBIDA` | 36 | **31** | 25 | 6 |
| `ACCION_FANTASMA` | 16 | **2** | 2 | 0 |
| `WINNER_FOLDEO` | 11 | **3** | 3 | 0 |
| `SHOWDOWN_SIN_WINNER` | 15 | **15** | 12 | 3 |
| **TOTAL** | **78** | **51** | **42** | 9 |

La revisión manual arregló **27 de los 78**. Quedan **42 dentro de la
ventana de calibración**, que es el 4,8 % de 877 manos.

**No bloquean**, y el motivo está medido, no supuesto:

- `SHOWDOWN_SIN_WINNER` (12) vive en `showdown` y `winner`, que **no entran**
  en `learn.preflop_events` ni en `player_ranges.p_matrix`.
- `WINNER_FOLDEO` (3) vive en `winner`, por lo mismo.
- `IMPORTE_SUBIDA` (25) y `ACCION_FANTASMA` (2) se creyó que tampoco, y
  **era falso**. Ver §0.2.1.

### 0.2.1 Hecho: dos de las cuatro SÍ tocaban el denominador

**Cerrado en [`DEFECTOS_VS_DENOMINADORES.md`](DEFECTOS_VS_DENOMINADORES.md).**
Instrumento: `tools/auditar_defectos_vs_denominadores.py`. Cero «no verificado».

El método no es «quitar las manos defectuosas y comparar totales» — eso da que
todo cambia, y es aritmética, no contaminación. Es dejar cada mano y
**neutralizar su defecto**, y mirar si cambia lo que la calibración ve de ella.

| clase | manos | **que tocan** |
|---|---:|---:|
| `IMPORTE_SUBIDA` | 25 | **25** — categoría de un evento, celdas de `cnt` |
| `ACCION_FANTASMA` | 2 | **2** — eventos, jugadores, observaciones |
| `WINNER_FOLDEO` | 3 | **0** |
| `SHOWDOWN_SIN_WINNER` | 12 | **0** |

> **La hipótesis de esta misma sección era falsa para `IMPORTE_SUBIDA`.**
> Decía que el campo `amount` no entra en `preflop_events`. **Entra, en las 25
> manos**: una subida que no supera la apuesta viva se cuenta como `limp` en
> vez de `open`/`rol`.
>
> | desplazamiento | eventos |
> |---|---:|
> | `limp` → `open` | 24 |
> | `limp` → `rol` | 1 |
>
> 25 eventos desplazados de 4561, el **0,55 %**. Los denominadores
> (`no_raise`, `facing_open`, `facing_3bet`) **no** se mueven: un `limp` y un
> `open` cuentan en el mismo. Lo que se mueve es **la categoría**, que es lo
> que `player_ranges.p_matrix` mete en `cnt` — y **8 de esas 25 manos cambian
> celdas de `cnt`**, que es literalmente lo que `DEFAULT_ALPHA` pondera.

Consecuencia para el orden: el primer parámetro se va a medir contra un
baseline cuya `limp` está **sobreestimada en 25 eventos**. Eso hay que
declararlo ANTES de empezar, porque si se limpian esas manos a mitad de la
calibración el baseline cambia y las métricas dejan de ser comparables. Ver §5.

### 0.3 La calibración no toca `data/`

`REVISION_EN_CURSO = True` y la fase D van a convivir, y conviene decir por
qué no se contradicen:

| | |
|---|---|
| lo que protege `REVISION_EN_CURSO` | `data/hands_db.jsonl` — que **ningún SCRIPT** escriba mientras el mantenedor revisa |
| lo que hace la calibración | cambia constantes de `motor/` y mide sobre la ventana ya cargada |
| intersección | **ninguna** |

La calibración **lee** la base y **escribe** en `motor/` y en `tools/`. Si una
iteración necesitara regenerar derivados, eso es un bloque aparte, con su
backup y su commit —como el `57bbce9`— y en ese commit sí se tocaría `data/`.

> Escrib esto porque el primer efecto de leer el repo y ver
> `REVISION_EN_CURSO = True` es pensar «no se puede tocar nada». Se puede tocar
> casi todo; lo que no se puede es escribir la base con un script, y eso es
> otra cosa.

---

## 1. Qué se va a calibrar, y en qué orden

### 1.1 `BASE_WEIGHT_MAP` — y por qué NO es lo primero

`revision_1` lo propone, y el motivo es este:

> `BASE_WEIGHT` no se aplica al reach inicial. `RangeState.__init__` usa
> `np.zeros(1326)`, así que el rango inicial trata P(AA) = P(72o).

**Medido, y la premisa no se sostiene en producción:**

| | |
|---|---|
| `RangeState()` sin `reach` | 3 construcciones en todo el repo |
| `ranges.py:665` (`uniform_range`) | se rellena a mano justo después: `rs.reach[rs.legal_mask] = 1.0` |
| `recommend_loop.py:172` | rama muerta: `_build_multiway_range` solo se llama con `villain_ranges` no vacío |
| `test_ranges.py:489` | un test |
| `RangeState()` vacío de verdad | **ninguno en producción** |

Además, `np.zeros(1326)` no da un rango **uniforme**: da un rango **vacío**
(`pesos no cero: 0 de 1326`). Que P(AA) = P(72o) es cierto, pero los dos son
cero, y un rango vacío no se puede normalizar.

**Conclusión:** `BASE_WEIGHT_MAP` (38 entradas, 18 valores distintos, de 0.12
a 1.0) está **sin usar**, pero no porque el reach inicial sea plano, sino
porque nadie lo llama. `class_weights_for_reach()` existe y está **DEPRECADO**
sin llamadores en producción.

> Por eso **«aplicar `BASE_WEIGHT_MAP` al reach inicial»** sería arreglar algo
> que no pasa. El sitio donde sí puede aportar es otro: ver §1.2.
>
> Esto es exactamente el tipo de conclusión que este proyecto ha rechazado
> cinco veces en diez bloques. El encargo decía «empieza por aquí» y el
> primer trabajo es comprobar si es verdad.

### 1.2 El orden que sí sale de la medición

| # | qué | por qué primero | tamaño del cambio |
|---|---|---|---|
| **0** | cerrar §0.1 | el jugador inventado va a `profile_ranges` | 2 manos, del mantenedor |
| **1** | verificar que las 42 no mueven los denominadores | es lo que convierte «no bloquean» en un hecho | una medición |
| **2** | `DEFAULT_ALPHA` (hoy 2.0, sin tocar desde el principio) | `alpha = 2.0` con `opp` de 15 en `PEZ facing_3bet` significa que el 11,8 % del peso viene de un prior que describe otro spot. **Es el número con más recorrido medido, y sigue sin tocar** | un parámetro |
| **3** | **sí o sí** `BASE_WEIGHT_MAP` — pero como **prior** del rango, no como reach inicial | el mapa es una priori sobre la fuerza de cada clase; el modelo actual (`player_ranges`) hereda de las matrices preflop y de un prior plano `0.15` | acotado |

El **2** va antes del **3** por una razón concreta y medida: es **un número**,
se puede cambiar y medir en minutos, y es reversible en un segundo. El 3 es
código. Empezar por código cuando hay un parámetro con recorrido medido es
empezar por lo difícil.

---

## 2. Los cuatro puntos que hacen que esto termine

### 2.1 Qué se mide

Ambas métricas son **pérdidas**: número positivo, **menor es mejor**. No es
cosmetismo: `revision_2` señaló que un «0,5 % de mejora» sobre una
log-verosimilitud *negativa* no significa nada, y es cierto. Con pérdidas, la
mejora relativa es `(L0 - L1) / L0` y siempre está en `[0, 1]`.

**Primaria — `L_prim`: log-verosimilitud del modelo de frecuencias.**

| | |
|---|---|
| fórmula | `L_prim = -Σ log p(observado) / nº de eventos` |
| dato | `player_ranges.cnt` contra `preflop_events`, en la partición de calibración |
| por qué | mide el ajuste del modelo al dato y es comparable entre valores de `alpha` sin depender de una mano concreta |
| unidades | nats por evento. Con 4561 eventos en la ventana y 156 manos utilizables |
| donde | **particion de calibracion**: el modelo se ajusta allí y se evalua allí, por construccion |
| que NO es | `L_prim` mide **AJUSTE**, no generalizacion. Una mejora de `L_prim` puede ser sobreajuste y no extrapola nada. |
| para que sirve | es la metrica de la derivada rapida, la que cambia en minutos. La de generalizacion es `L_sec` sobre validacion. Si un candidato mejora `L_prim` y empeora `L_sec`, es sobreajuste. |

**Secundaria — `L_sec`: score de Brier de `sit.equity`.**

| | |
|---|---|
| fórmula | `L_sec = mean((p - y)²)` |
| `p` | `sit.equity` del motor en el punto de decisión |
| `y` | **1,0** si el ganador es el hero, **0,0** si no. **No hay `y = 0,5`**: §2.1.1 |
| referencia | `winner` es una LISTA. Se compara el hero contra **todos** sus elementos, no contra el primero. Si hay varios, §2.1.1 decide si la mano es usable |
| manos | las **39 de validacion** de §2.1.1, NO las 156 |
| por que validacion | los umbrales de §2.3 se justifican con las manos de validacion. Medir sobre las 156 seria usar las mismas manos para ajustar y para decidir |
| referencia trivial | un predictor constante `p = 0,199` saca **0,1592**. Hay que ganarle: §2.1.1.b |
| por que | Brier es una regla de puntuacion *proper*: premia acertar y penaliza el exceso de confianza |

> ⚠️ Por qué **no** se mide el error de la acción recomendada, que era la
> propuesta original de este plan. `revision_2` la declaró no operacional y
> tenía razón: *«una acción como fold, call o raise no es lo mismo que el
> identificador del jugador ganador»*, y sobre todo — **la base no registra
> qué era lo óptimo, registra qué hizo el hero**. Comparar la recomendación con
> lo que se hizo mide **acuerdo**, no **corrección**, y el acuerdo se maximiza
> predecir siempre la acción más frecuente. Es una métrica que premia el
> modelo trivial.
>
> No se cambia en silencio por otra. Se declara que **la calidad de la acción
> no es medible con este dato**, y se mide lo que sí lo es.

### 2.1.1 Qué manos hay, medido

**Remedido dos veces**, y la segunda lo movió. La primera contaba 156
utilizables y dio por buena una definición del hero que era la equivocada:
el reparto de victorias salió mal y el suelo de la métrica también.

Las dos cosas se corrigen aquí, antes de elegir métrica.

#### Lo primero: quién es el hero

Había dos convenciones cruzadas en el mismo fichero, y no se parecían:

| | en cuántas de las 877 manos coincide con el hero |
|---|---:|
| `'hero'` = `players[0]` (el id que usa `winner`) | 644 |
| «el primer jugador con cartas» | 845 |
| el jugador nombrado en `learn.HERO_NAMES` | **877** |

La autoridad es `learn.HERO_NAMES = ('Jarduan',)`, y no una convención
derivada de los datos. **`'hero'` es la butaca 0**, no una persona: en 232
de las 877 manos el hero real está sentado en otra butaca.

Y «el primer jugador con cartas» falla en 32, porque hay manos donde el hero
no tiene cartas y otro jugador sí. Ahí la etiqueta `y` era de otro.

#### Lo segundo: el reparto se demuestra, no se lee

Había dos fuentes en conflicto: `winner` (una lista de ids) y
`showdown.winner1` (un texto que nombra a uno). El código aceptaba el
texto por *existir y no parecer plural*, lo que `revision_2` objetó por
dos motivos: la búsqueda por subcadena puede resolver al equivocado, y que
`winner1` nombre a uno no demuestra que los demás estén mal.

**Ninguna de las dos preguntas hace falta ya**, porque hay una tercera
fuente que sí demuestra: **el evaluador del motor**.

```
python tools/equity_preflop.py --comprobar     # el enumerador, aparte
```

Si los jugadores que `winner` declara ganadores hacen **la misma mano en el
board**, es un reparto, y el reparto es un hecho comprobable. Medido sobre
las 9 manos con dos ganadores en la ventana (re-anclado 2026-10-26; 8 de
ellas tienen todos los ganadores con cartas y son demostrables):

| | |
|---|---:|
| **empates demostrados** con el evaluador | **8 de 8** |

Ejemplo, `H_0798`: board `5d Qh 6s 2h 4s`, `BB` con `TsQs` y `SB` con
`ThQc`. **Score idéntico: 675194.** Las dos hacen pareja de queens con
kicker T. O sea que `winner` con dos elementos **es correcto** y
`showdown.winner1`, que nombra a uno solo, está **incompleto por
construcción**: el recorder escribe `showdown` únicamente cuando hay **un**
ganador.

> Mi respuesta anterior —*«sin texto no se puede distinguir "dos ganan" de
> "el registro se equivocó", y `y = 0,5` sería inventar»*— era una
> afirmación sin medir. **Los 7 son repartos, y `y = 0,5` es lo que dice
> el reparto.** La pregunta de `revision_2` llevaba tres bloques siendo la
> correcta y yo la había cerrado sin mirar las cartas.

Como comprobación de que el instrumento sirve: cuenta **17** manos con dos
ganadores distintos en la base entera tras la revisión manual.

#### Y un defecto que sale de mirar

`H_0173`: board `Th 2h 3c Qd Js`. El **hero** tiene `Qh3h` con score
**1031914** y los ganadores declarados hacen **423449**. El hero tiene la
mejor mano de la mesa y **no está en `winner`**.

Eso **no se corrige aquí**: `data/` no se toca en este bloque. Queda
declarado como defecto encontrado, con la mano y los números, para que se
mire aparte.

#### El desglose

| manos de la ventana de 877 | |
|---:|---|
| 579 | board incompleto (no hay showdown) |
| 132 | menos de 2 jugadores con cartas |
| 0 | sin ganador |
| 1 | el ganador no tiene cartas |
| **164** | **utilizables (18,7 %)** |

**Reparto 70/30 sobre las 164 utilizables:** **123 de calibración y 41 de
validación**, disjuntas por construcción (§2.2). La lista exacta está
versionada en [`PARTICION_FASE_D.md`](PARTICION_FASE_D.md).

### 2.1.1.b La etiqueta, y la referencia que tiene que ganarse

`y` para el hero: **1,0** si es el único ganador, **0,5** si el bote está
repartido y el hero es de los que lo comparten, **0,0** si no. Con las
tres definiciones ya corregidas:

| | |
|---|---|
| reparto | el hero **gana 21 de 164**, **reparte 3** y pierde 140 |
| Brier de un predictor **constante** `p = 0,137` | **0,1138** |

> Las cuentas anteriores decían 21 victorias y 0,1165. Cambiaron al poder
> usar las 7 manos que son repartos, y H_0798 pasó de `y = 1,0` a
> `y = 0,5`, que es lo correcto. **El error más caro no es medir mal, es
> medir la cosa equivocada con confianza.**

**El motor tiene que estar por debajo de 0,1111.** Si no, `L_sec` no mide
calidad: mide la base rate, y el mejor modelo es decir *«el hero va a
perder»*.

Por eso la comparación contra esa referencia se **reporta en cada
iteración**, al lado de `L_sec` y no en una nota al pie.

> **41 manos de validación, con un 87 % de derrotas.** Un cambio del 2 %
> en `L_sec` no es distinguible del ruido. Está escrito aquí antes de
> medir, no después de ver qué salía: si el resultado no se
> distingue, **se dice que no se distingue**.

### 2.1.2 Lo que no se mide

| | |
|---|---|
| **calidad de la acción** | no medible: la base no tiene etiqueta de optimalidad (§2.1) |
| **win rate global** | descartado: depende del rival, del stack y de cuánto se juega. Un cambio de `DEFAULT_ALPHA` la mueve por casualidad |
| **equity de spots multiway** | no comparable: `CONTRATO_F72A.md` §6 — la equity del motor es HU contra **un** rival |
| **equity preflop histórica** | no medible: `hand_evaluator.evaluate_batch` declara board de 3 a 5 cartas y sus subsets son de 5, 6 y 7. **No hay camino preflop**, y preflop son 96 de las 156 manos. `equity_de_mano.py` funciona postflop; cubre el 37 % y sesgada |

### 2.1.3 Lo que `L_prim` no puede hacer, medido

> Se descubrió al intentar usar la métrica, no antes. Y hubo que
> corregirla dos veces para poder decir esto.

#### La avería que la tapaba

La primera versión de `l_prim` indexaba el grid con `g[ev.category,
ev.pos]`, que son dos cadenas. Eso es `IndexError` en las **295** de 295,
y el `except` caía a `np.nanmax(g)`: el **máximo** del grid, no la
probabilidad de la acción observada.

El grid de `p_matrix` no está indexado por acción ni por posición: está
indexado por **rango de carta** (`player_ranges.GRID_RANKS`). La
probabilidad de lo observado la da `p_hand(perfil, spot, action, cartas)`.

Un máximo del grid es ≥ la probabilidad de cualquier celda, así que
**mejoraba la pérdida por construcción**. No era un error pequeño: era una
métrica que siempre favorecía al candidato, y que además reaccionó a `alpha`
por el motivo equivocado.

Ahora no hay fallback: si el índice no es válido, `l_prim` lanza
`MedicionSinSentido` y el comando sale con código 3 sin publicar nada. Y un
test recorre el árbol de `l_prim` y falla si aparece un `nanmax`, un `max` o
cualquier otro sustituto — el docstring sí lo nombra, a propósito, para
explicar el bug.

#### La avería que queda

`L_prim` suma `log p` **solo sobre celdas observadas**, y toda celda
observada tiene `cnt >= 1`. Sobre esas celdas el término del prior es pura
dilución:

```
p(alpha) = (cnt + alpha*prior) / (opp + alpha)
```

Medido celda a celda sobre las **256** celdas observadas de la partición de
calibración:

| | celdas |
|---|---:|
| subir `alpha` **baja** `p` (empuja la pérdida arriba) | **224** |
| empujan al revés | **32** |

La monotonía **no es una garantía matemática** —32 celdas la resisten— pero
sobre los valores medidos de `0,1` a `100` la curva no da una sola
excepción. Y eso basta para lo que importa:

> **La métrica primaria no puede elegir un parámetro de regularización.**
> Ordena `alpha` por cuánto se diluyó el prior, que no es una respuesta
> sobre el poker. Su "ganador" es siempre el candidato con menos
> regularización, que es el mismo decir que el más pequeño.

Por eso `tools/calibrar.py` tiene un **guardián de monotonía** que se niega
a nombrar ganador y sale con código 2. Es código, no una nota: un comentario
se puede saltar sin que nadie se entere.

Y hay un segundo bloqueo, independiente: **`L_sec` no se puede calcular**
(§2.1), así que aunque la curva no fuera monótona, el plan no admite aceptar
un valor sin las dos métricas. `--aplicar` comprueba las dos.

Para recalibrar `alpha` haría falta una métrica que scoree también las
celdas **no observadas**, o que mida sobre validación. Las dos cosas están
en [CALIBRACION_DEFAULT_ALPHA.md §7](CALIBRACION_DEFAULT_ALPHA.md).

#### Un hallazgo lateral que no es de `alpha`

`p = 0` en **1 991 de 22 308** celdas del grid (8,9 %), **también con
`alpha = 20`**. La tabla de priors tiene 127 ceros de 169; donde el prior
es 0 y no hay conteo, `p = 0` para todos los valores. `alpha` no es la
palanca que los arregla.

Medido también lo contrario: en los 295 eventos de la partición de
calibración **ninguno cae en un cero**, ni tiene celda ausente, ni cae al
prior. O sea que los ceros **no contaminan `L_prim` aquí**. Se mediría en
una ventana más ancha. Está en
[CALIBRACION_DEFAULT_ALPHA.md §6](CALIBRACION_DEFAULT_ALPHA.md).

### 2.2 Cómo se mide

`revision_2` pidió concretar cinco cosas de la partición. Las cinco están:

| | |
|---|---|
| **regla** | `particion(hand_id) = 'validacion' if sha256(hand_id) % 10 < 3 else 'calibracion'` |
| **proporción** | 70 % calibración / 30 % validación, por construcción del módulo |
| **disjuntos** | **garantizado por construcción**: una función de `hand_id` no puede devolver dos valores. Hay un test que lo comprueba sobre las 877 manos |
| **lista exacta** | `tools/calibrar.py particion --escribir` la **versiona** en `DOCS/PARTICION_FASE_D.md`. Si la ventana cambia, ese fichero cambia, y el diff se ve |
| **comparar candidatos** | **siempre sobre las mismas manos**: un candidato y el baseline se evalúan en la partición indicada, sobre los mismos `hand_id`, en la misma ejecución |

Lo demás:

| | |
|---|---|
| ventana | las **877** manos de `load_hands(reliable_only=True)`. Declarada, no incidental |
| **fuera** | las 381 restantes, aunque el motor las use en vivo |
| baseline | `a694eee3b79508b94b5fedfc5816c63895bccb4a`, **escrito arriba** |
| reproducibilidad | todo en `tools/`, `--dry-run` por defecto, salida versionada |
| ruido | semilla fija, la que ya usa `runout_equity` |

> **La partición no se toca una vez escrita.** Es lo que impide que la
> validación se convierta en una segunda muestra de calibración: si se
> reasignan manos para «ver si improves», la validación ya no es validación.
> Cambiar la partición es cambiar de fase, y eso es un commit con su motivo,
> no un ajuste de un 5 %.

### 2.3 Cuándo se para

`revision_2` señaló, con razón, que **P3 y P4 se contradecían**: P3-era «se para
si la secundaria empeora» y P4-era «se acepta si la primaria mejora un 2 %»,
sin que el texto estableciera la prioridad. Aquí la jerarquía es explícita y
los umbrales son **números escritos antes de empezar**, no fracciones informales.

**Definiciones, fijadas antes de la primera iteración:**

```
mejora(L0, L1) = (L0 - L1) / L0        # ambas perdidas, L0 > 0
empeora(L0, L1) = (L1 - L0) / L0

# `mejora` NO esta acotada a [0, 1]: es NEGATIVA cuando L1 > L0, es decir
# cuando la perdida empeora. `empeora` es negativa cuando la perdida
# mejora. Decir que estan en [0, 1] era incorrecto (`revision_2` §3.1) y
# habia llevado a una regla de parada mal leida. Aqui se comparan con 0:
# `mejora > 0` es "ha mejorado", `mejora < 0` es "ha empeorado".
```

### 2.3.1 Estado de `L_sec`: no aplicable

**`L_sec` no es utilizable como criterio de aceptación**, y P1/P4/P5 —que
dependen de ella— **no son evaluables**.

| | n | Brier de la equity | constante óptima | |
|---|---:|---:|---:|---|
| observable (postflop, contra el rango) | 60 | **0,1962** | 0,2124 | **gana** |
| retrospectiva (preflop, contra la mano real) | 99 | 0,1674 | **0,0000** | pierde |

La retrospectiva tiene **0 victorias en 99 manos**, así que la constante
sale 0 por construcción y "gana" siempre. **Esa mitad no es la equity de
una decisión**: usa las cartas que el rival escondía al decidir.

Y el motor no tiene ningún camino de equity preflop: `situation` y
`runout_equity` fallan los dos porque `evaluate_batch` pide `_SUBSETS[2]`,
que no existe. Detalle en
[`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md).

**Consecuencia: sin secundaria, no hay criterio admisible para aceptar un
valor**, y el plan no admite aceptar sin las dos.

### 2.3.2 P0 — el criterio que se añadió

> **P0 — si la métrica secundaria pierde contra el predictor constante de la
> misma muestra, Fase D se para.**

Es una **adición**, no un cambio: P1–P7 se quedan como están, y P0 va
antes que ellos.

Se añadió después de medir. Lo que pasó fue peor que lo que el criterio
buscaba: la secundaria «perdía», pero al separarla se vio que la mitad que
perdía era un subconjunto **sin ninguna victoria que predecir**. Así que P0
tiene que llevar la separación dentro, o repetiría el error:

| si | entonces |
|---|---|
| `L_sec` **conjunto** gana al constante | vale |
| `L_sec` **conjunto** pierde | medir por separado: observable y retrospectiva |
| la **observable** pierde | parar: es un fallo real |
| la **retrospectiva** pierde con 0 victorias | no cuenta: el subconjunto no tiene nada que predecir |

Que P0 haya nacido de un hallazgo equivocado es justo lo que lo hace
interesante: la primera versión habría parado Fase D por un agrupamiento.

**Se aplica en este orden. El primero que se cumple decide:**

| | regla | acción |
|---|---|---|
| **P1** | `empeora(L_sec) > TOL_SEC` | **revertir y parar** |
| **P2** | dos iteraciones seguidas con `mejora(L_prim) < 0,5 %` | parar |
| **P3** | 20 iteraciones en total | parar |
| **P4** | `empeora(L_sec) > 0` **y** `mejora(L_prim) < UMBRAL` | **revertir y parar** |
| **P5** | `empeora(L_sec) > 0` **y** `mejora(L_prim) ≥ UMBRAL` | **se acepta, y se escribe por qué** |
| **P6** | se toca un parámetro sin justificación escrita | parar y volver al inventario |
| **P7** | `mejora(L_prim) < 0` en una iteracion suelta | **revertir y parar** |

**P7 no estaba escrito, y era un efecto accidental.** `revision_2` lo señaló:
P2 solo paraba
tras dos iteraciones *seguidas* con mejora primaria pequeña, asi que una
iteracion que **empeora** `L_prim` no activaba nada. Eso es una
decision —revertir la iteracion que empeora— y por eso se escribe.

**Los umbrales, declarados aquí para que no se ajusten a posteriori:**

| | valor | por qué ese |
|---|---:|---|
| `TOL_SEC` | **2 %** | con 44 manos de validación, menos de eso es ruido medible |
| `UMBRAL` | **5 %** | tiene que superar el ruido por dos veces: el de la tolerancia y el de la muestra |

> **P5 es una excepción, y está limitada por dos cosas a la vez.** No
> es «P3 pero con un hueco»: es el único caso en que se acepta una regresión
> de calidad, y para aceptarla hacen falta las dos condiciones —una mejora
> grande de la primaria **y** una regresión dentro de la tolerancia—. Con 44
> manos, una regresión de calidad puede ser real y no saberlo; por eso el
> umbral es 5 % y no 2 %.
>
> **`revision_2` tenía razón en una cosa más:** el plan no decía si los
> criterios producían el mismo veredicto en dos ejecuciones. Sí: todo se
> calcula sobre las mismas manos fijadas por §2.2, con la semilla que ya usa
> `runout_equity`, y sin ninguna elección dentro del bucle. Repetir el
> protocolo da el mismo número o da un bug.

**Y hay un tope que no es de calidad:**

> **Se para y se escribe el motivo en cuanto se toque un número que no tenga
> una justificación escrita en su sitio.** Un parámetro que nadie sabe por
> qué tiene ese valor no se calibra: se investiga. Si aparece uno, Fase D
> vuelve al inventario.

### 2.4 Cómo se revierte

| | |
|---|---|
| granularidad | **un commit por parámetro.** Un commit que cambia tres parámetros no se puede deshacer a medias, y deshacer a medias es justo lo que hace falta |
| reversibilidad | todo parámetro vive en **una constante con nombre** en `motor/`, nunca en un literal dentro de la fórmula. Sin eso, revertir es buscar el número |
| verificación | cada commit lleva un test que falla si el parámetro sale del rango que ese commit declara justifiable. El rango está **escrito antes** de calibrar, no después |
| red de seguridad | `git revert` del commit. El estado previo está en git, que es la única garantía de reversibilidad que existe aquí |
| datos | la calibración **no toca `data/`**. Si un cambio necesita regenerar derivados, es un bloque aparte, con su backup, como el de hoy |
| interrupted | si la fase se para a medias, el último commit en verde es el estado. No hay estado intermedio sin commitear |

> «Reversible» no es «se puede deshacer con `git revert`»: es **«se puede
> deshacer y saber que se ha deshacido bien»**. Por eso el test con el rango
> declarado es parte del contrato de reversibilidad, no decoración.

---

## 3. Lo que este plan NO dice

- **No dice que Fase D vaya a funcionar.** Dice cómo se mide y cómo se para.
  Que el resultado sea una mejora es lo que hay que demostrar, no lo que este
  documento puede prometer.
- **No dice que la calidad de la acción sea medible.** No lo es con este
  dato, y §2.1 dice por qué en vez de inventar una etiqueta. La secundaria
  mide la **exactitud de la equity**, que es otra cosa.
- **No dice que 147 manos basten.** No bastan para cambios pequeños. Está
  escrito antes de empezar, no después de no ver diferencia.
- **No dice que `BASE_WEIGHT_MAP` sea el primer objetivo.** §1.1 explica por
  qué no, con la medición que lo contradice.
- **No toca los 4 defectos sistémicos.** Los mide (§0.2.1) y dice qué queda
  abierto (§5). Arreglarlos es del mantenedor.
- **No recalibra nada.** Esto es el plan. El primer número que se mueve es
  `DEFAULT_ALPHA`, y solo después de escribir la partición y de decidir §5.

## 4. Documentos de referencia

| | |
|---|---|
| [`RANGO_VIGENTE.md`](RANGO_VIGENTE.md) | las tres ventanas, y por qué son tres |
| [`CANAL_MANUAL_CERRADO.md`](CANAL_MANUAL_CERRADO.md) | estado canónico de la base y el canal manual |
| [`HALLZGOS_H0001_H1014.md`](HALLZGOS_H0001_H1014.md) | los 4 defectos, con identificadores |
| [`CONTRATO_C4.md`](CONTRATO_C4.md) · [`CONTRATO_F72A.md`](CONTRATO_F72A.md) | los contratos del motor que la calibración no puede romper |
| [`DEFECTOS_VS_DENOMINADORES.md`](DEFECTOS_VS_DENOMINADORES.md) | los 42 defectos de la ventana, clasificados, con el instrumento |
| [`APARCADO_DB.md`](APARCADO_DB.md) | lo que sigue aparcado |

## 5. DECIDIÓ: B — congelar y declarar

> Esta seccio estaba escrita como "una decision pendiente". **Ya esta
> decidida**, y no por preferencia: por medicion.

### 5.1 La pregunta que la decidia, y la respuesta

`revision_2` condiciono la opcion A a algo comprobable: que **los importes
correctos se puedan demostrar con evidencia disponible, y no
reconstruirlos por conjetura**. Eso es medible, y se midio.

```
python tools/auditar_importe_subida.py
```

| | |
|---|---:|
| casos de `IMPORTE_SUBIDA` en la ventana de 877 | **33** en 25 manos |
| importes **demostrables** | **0** |

**Ninguno.** El registro guarda, por evento, el importe grabado, el stack
del jugador al inicio y la secuencia. No hay un segundo importe para el
mismo evento, ni medida del pantallazo, ni nada. La unica magnitud que
podria deducir un importe es el stack —para reconocer un all-in— y
**ninguno de los 33 coincide con el stack**: los stacks van de 9,5 a 166,9 y
los importes sospechosos son siempre 1,0 o 0,5, que es la ciega.

Asi que **A no es posible** en el sentido en que se pidio. Corregir los
importes seria inventarlos.

### 5.2 Lo que SI seria posible, y por que no es A

El proyecto ya tiene una regla exacta y validada para un caso casi identico
(`verificar_cm004.py`): *una subida a un importe menor o igual que la ciega
nominal, sin que nadie haya subido antes, no es una apertura.*

| | casos |
|---|---:|
| sin subida antes — la regla aplica | **25** |
| con una subida antes — la regla no aplica | 8 |

Esos 25 se podrian **reetiquetar** `r` → `c` **sin tocar el importe**. Pero
un reetiquetado **no es la opcion A**: A es migrar la base, y un
reetiquetado parcial deja la base en un estado que no es el de antes ni el
de A. Es trabajo con su backup y su hash, y se hace **despues**, no
durante.

### 5.3 Decision

**B — se calibra con la ventana tal como esta, y se declara el sesgo.**

No porque sea mas barata. Porque es la unica que no requiere inventar.

### 5.4 Regla de bloqueo

> **Mientras la calibracion este en curso, `IMPORTE_SUBIDA` no se toca.**
> Ni por el mantenedor, ni por un script, ni por nadie.

Si algun momento se decide limpiar los 33 casos:

1. **se para la calibracion**;
2. se regeneran los derivados;
3. se actualizan los hashes declarados (`HANDS_DB_SHA256`, `HANDS_DB_COMMIT`);
4. se **regenera la particion** (`DOCS/PARTICION_FASE_D.md`);
5. se **reinicia desde la iteracion 1**.

No se mezclan. Un cambio de datos a mitad de fase no rompe el motor:
rompe la lectura de los resultados, que es peor porque no se nota.

### 5.5 El sesgo, en la cabecera de la tabla y no en una nota al pie

Cada iteracion reporta `L_prim` y `L_sec` con esta cabecera pegada:

> **`limp` esta sobreestimada en 25 eventos de 4561 (0,55 %).** Las 25
> manos de `IMPORTE_SUBIDA` desplazan 24 eventos de `limp` a `open` y 1 a
> `rol`; 8 de ellas cambian celdas de `cnt`, que es lo que `DEFAULT_ALPHA`
> pondera. Los numeros de abajo **no son cifras limpias** y no se comparan
> con ninguna otra corrida de esta fase.

Si no esta en la cabecera, el primer consumidor de las tablas las lee como
si fueran limpias. Y las metricas que salen de `limp` no se tocan: se
declaran.

### 5.6 Lo que esta decision NO dice

No dice que el sesgo sea pequeno. Dice que es **conocido y uniforme**: las
33 ocurrencias son el mismo defecto, con el mismo sintoma, en 25 manos de
una sola sesion. Eso es lo que lo hace declarable en vez de ruido.

No dice que `limp` sea correcta. Dice que se sabe **en que direccion** y
**cuanto** se equivoca.

No dice que el reetiquetado sea una mala idea. Dice que es otro trabajo,
con otro riesgo, y que se hace cuando la calibracion este parada.
