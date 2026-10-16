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
| **2** | **sí o sí** `BASE_WEIGHT_MAP` — pero como **prior** del rango, no como reach inicial | el mapa es una priori sobre la fuerza de cada clase; el modelo actual (`player_ranges`) hereda de las matrices preflop y de un prior plano `0.15` | acotado |
| **3** | `DEFAULT_ALPHA` (hoy 2.0, sin tocar desde el principio) | `alpha = 2.0` con `opp` de 15 en `PEZ facing_3bet` significa que el 11,8 % del peso viene de un prior que describe otro spot. **Es el número con más recorrido medido, y sigue sin tocar** | un parámetro |
| **4** | ω individual | `Pipaaf182` tiene ω=0.537 y se queda con la mitad de la masa sin renormalizar por celda | una fórmula |

El **3** va antes del **2** por una razón concreta y medida: es **un número**,
se puede cambiar y medir en minutos, y es reversible en un segundo. El 2 es
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
| unidades | nats por evento. Con 4561 eventos en la ventana, y 147 utilizables (§2.1.1) |

**Secundaria — `L_sec`: score de Brier de `sit.equity`.**

| | |
|---|---|
| fórmula | `L_sec = mean((p - y)²)` |
| `p` | `sit.equity` del motor en el punto de decisión |
| `y` | 1 si el hero ganó el bote, 0 si lo perdió, **0,5 si hubo empate** |
| referencia | `hand['winner'][0]` — un resultado **grabado**, no derivado |
| manos | las **147** de §2.1.1 |
| por qué | Brier es una regla de puntuación *proper*: premia acertar y penaliza el exceso de confianza, y se descompone en calibracion y nitidez |

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

No se supone: se cuenta.

| manos de la ventana de 877 | |
|---:|---|
| 580 | board incompleto (no hay showdown) |
| 134 | menos de 2 jugadores con cartas |
| 10 | el ganador no tiene cartas |
| 6 | ganadores múltiples — no se puede etiquetar un único `y` |
| **147** | **utilizables (16,8 %)** |

De las 147, **el 100 % tiene las cartas del hero**. Repartidas 70/30 salen
**103 de calibración y 44 de validación**.

> 44 manos de validación es **poco**. Con ese número, un cambio del 2 % en
> `L_sec` no es distinguible del ruido. Está escrito aquí antes de elegir la
> métrica, no después de ver que no salía nada: si el resultado no se
> distingue, **se dice que no se distingue**.

### 2.1.2 Lo que no se mide

| | |
|---|---|
| **calidad de la acción** | no medible: la base no tiene etiqueta de optimalidad (§2.1) |
| **win rate global** | descartado: depende del rival, del stack y de cuánto se juega. Un cambio de `DEFAULT_ALPHA` la mueve por casualidad |
| **equity de spots multiway** | no comparable: `CONTRATO_F72A.md` §6 — la equity del motor es HU contra **un** rival |

### 2.2 Cómo se mide

`revision_2` pidió concretar cinco cosas de la partición. Las cinco están:

| | |
|---|---|
| **regla** | `particion(hand_id) = 'validacion' if sha256(hand_id) % 10 < 3 else 'calibracion'` |
| **proporción** | 70 % calibración / 30 % validación, por construcción del módulo |
| **disjuntos** | **garantizado por construcción**: una función de `hand_id` no puede devolver dos valores. Hay un test que lo comprueba sobre las 877 manos |
| **lista exacta** | `tools/calibrar.py particion` la imprime y la **versiona** en `data/` — no, en `DOCS/` — como `DOCS/PARTICION_FASE_D.md`. Si la ventana cambia, ese fichero cambia, y el diff se ve |
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
```

**Se aplica en este orden. El primero que se cumple decide:**

| | regla | acción |
|---|---|---|
| **P1** | `empeora(L_sec) > TOL_SEC` | **revertir y parar** |
| **P2** | dos iteraciones seguidas con `mejora(L_prim) < 0,5 %` | parar |
| **P3** | 20 iteraciones en total | parar |
| **P4** | `empeora(L_sec) > 0` **y** `mejora(L_prim) < UMBRAL` | **revertir y parar** |
| **P5** | `empeora(L_sec) > 0` **y** `mejora(L_prim) ≥ UMBRAL` | **se acepta, y se escribe por qué** |
| **P6** | se toca un parámetro sin justificación escrita | parar y volver al inventario |

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

## 5. Una decisión pendiente, escrita antes de empezar

> No es una tarea: es una cosa que hay que **decidir antes** de mover nada, y
> que si se decide mal invalida la calibración entera.

Las 25 manos con `IMPORTE_SUBIDA` mueven la categoría `limp` a `open`/`rol`
(§0.2.1). Hay dos caminos y son excluyentes:

| | |
|---|---|
| **A — limpiar antes** | el mantenedor corrige el importe de esas 25 manos. Los derivados se regeneran, el baseline cambia, y la calibración mide contra una ventana sin el sesgo. Es lo correcto, y **cuesta una migración** |
| **B — declarar el sesgo** | se calibra con la ventana tal como está y se escribe que `limp` está sobreestimada en 25 eventos sobre 4561. Más barato, y la comparación de iteraciones sigue siendo válida **mientras nadie limpie a mitad** |

> **El riesgo de B no es teórico, es de procedimiento:** si a la iteración 7
> alguien limpia las 25 manos «porque sí», el baseline cambia y las métricas de
> la 1 a la 6 dejan de ser comparables con las de la 7 en adelante. No se
> rompe el motor: se rompe la lectura de los resultados, que es peor porque no
> se nota.
>
> **B es lo que el plan asume por defecto**, y por eso está escrito. Si se
> elige A, es una migración con su commit, su hash y su backup, y este
> documento se actualiza con el nuevo baseline **antes** de la primera
> iteración.
