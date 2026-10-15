# FASE D — plan de calibración

**Estado:** vigente. Es la primera vez que Fase D tiene plan.
**Base:** `bf60aa8` (revisión manual en `H_1070`), derivados regenerados en
`57bbce9`.
**Precedente:** este proyecto lleva diez bloques defendiendo que nada se
activa sin contrato, sin ventana declarada y sin criterio de parada. Una
calibración es una de las tres cosas que mas rompen eso, así que empieza
por escribir las reglas.

> **Sin este documento no se calibra.** `revision_1`: *«No calibres sin
> FASE_D_PLAN.md. Sin plan, la calibración es "tocar parámetros a ver qué
> pasa"»*. Y tiene razón: los cuatro puntos de §2 son los que hacen que esto
> sea reversible.

---

## 0. Antes de calibrar: dos cosas que hay que cerrar

### 0.1 Un jugador inventado en los derivados

Regenerando los derivados apareció un jugador llamado **`CO`** en
`player_stats.json` y `profiles.json`, con `n: 0`, todos los bins en `n/a`,
`stack_mean: None`, y etiqueta **`TIBURON`** con confianza `0.0`.

`CO` no es un jugador: es una posición. Rastreado hasta el origen:

| | |
|---|---|
| manos | `H_0519` (turn) y `H_0846` (preflop) |
| causa | tienen acciones cuyo `pos` no corresponde a **ningún** jugador de la mano |
| efecto | `extract_hand` no puede mapear `pos` → nombre y **usa la posición como nombre** |
| medido | **2** observaciones de 9252 tienen una posición en el campo `player` |

Y el defecto ya estaba clasificado: son exactamente las dos
`ACCION_FANTASMA` que quedan. **El defecto y el síntoma son las mismas dos
manos.**

Un perfil con cero observaciones no debería llevar etiqueta. `TIBURON` con
confianza `0.0` y `stack_mean: None` es un número inventado con forma de dato,
y va a parar justo a `profile_ranges.json`, que es una de las dos tablas que
esta fase quiere calibrar.

**Antes de calibrar:** decidir qué se hace con esas dos manos. Corregirlas es
del mantenedor (son datos); no las puede tocar la calibración.

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

- `IMPORTE_SUBIDA` (25) y `SHOWDOWN_SIN_WINNER` (12) viven en campos
  —`amount`, `showdown`, `winner`— que **no entran** en `learn.preflop_events`
  ni en `player_ranges.p_matrix`. Contaminan la lectura humana del dato, no la
  frecuencia que se calibra.
- `ACCION_FANTASMA` (2) y `WINNER_FOLDEO` (3) **sí** contaminan el pipeline,
  y son las 5 de §0.1.

**Verificación que hay que hacer antes de dar esto por bueno:** comprobar que
las 42 no mueven los denominadores de `learn.py`. Es media hora y es la
diferencia entre «no bloquean» y «no he comprobado que no bloqueen».

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

**Primaria — `DEFAULT_ALPHA` (punto 3):**

| | |
|---|---|
| métrica | log-verosimilitud de las frecuencias observadas en `player_ranges.p_matrix` sobre `cnt`/`opp`, con y prior `FLAT_PRIOR` fijo |
| por qué | mide el ajuste del modelo al dato, y es comparable entre valores de `alpha` sin depender de ninguna mano concreta |

**Secundaria — y la que manda para decidir:**

| | |
|---|---|
| métrica | **error de la acción recomendada**, sobre las manos con showdown en la ventana |
| unidad | fracción de manos en las que la acción recomendada por el motor es la del ganador registrado |
| por qué | es lo que le importa a quien juega. Una calibración que mejora la verosimilitud y no esto no se ha Improved de nada |

> ⚠️ **Lo que NO se va a medir, y por qué:** *win rate* global. Es la métrica
> que cualquiera propondría y es la peor: depende del rival, del stacks y de
> cuánto se juega, así que un cambio de `DEFAULT_ALPHA` la mueve por casualidad
> y no por causa. Se mide error de acción, y punto.

### 2.2 Cómo se mide

| | |
|---|---|
| ventana | las **877** manos de `load_hands(reliable_only=True)`. Declarada, no incidental |
| **fuera** | las 381 restantes, aunque el motor las use en vivo. Calibrar sobre ellas y medir sobre la ventana es medir en una muestra distinta a la que se ajustó |
| partición | la ventana se parte en **calibración** y **validación**, por `hand_id`, de forma determinista y fija |
| baseline | el estado de `HEAD` al empezar Fase D, con su SHA. **Se anota en el documento y en el commit**, como se hizo con la base |
| reproducibilidad | todo el proceso va en `tools/`, `--dry-run` por defecto, y su salida se versiona. Un número que no se puede reproducir no es un número |
| ruido | cada métrica se calcula con la **semilla fija** que ya usa `runout_equity`. Sin ella, dos ejecuciones no se comparan |

La partición es la parte que más se olvida: si se calibra y se mide sobre las
mismas manos, el número que sale mide cómo de bien se memoriza la muestra, no
cómo de bien se decide.

### 2.3 Cuándo se para

**Se para en cuanto se cumpla una:**

| | criterio |
|---|---|
| **P1** | dos iteraciones consecutivas sin mejorar la primaria en **más de 0,5 % relativo** |
| **P2** | **20** iteraciones en total, se haya mejora o no |
| **P3** | la secundaria **empeora** respecto al baseline, en cualquier iteración |
| **P4** | una iteración mejora la primaria y empeora la secundaria. **Se acepta solo si la mejora de la primaria supera el 2 % relativo**; si no, se revierte y se para |

**P3 y P4 son la parte importante.** Sin ellos, «mejorar la verosimilitud» es
una forma elegante de empeorar el motor: se puede subir la verosimilitud
ajustando el prior a un spot y arruinando el resto.

Y hay un tope de etapa que **no es** un criterio de calidad:

> **Se para y se escribe el motivo en cuanto se toque un número que no tenga
> una justificación escrita en su sitio.** Un parámetro que nadie sabe por
> qué tiene ese valor no se calibra: se investiga. Si aparece uno, Fase D se
> para aquí y vuelve al inventario.

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
- **No dice que `BASE_WEIGHT_MAP` sea el primer objetivo.** §1.1 explica por
  qué no, con la medición que lo contradice. El encargo lo daba por hecho.
- **No toca los 4 defectos sistémicos.** Los mide, dice cuántos caen en la
  ventana y propone la verificación de §0.2. Arreglarlos es del mantenedor.
- **No recalibra nada.** Esto es el plan. El primer número que se mueve es
  `DEFAULT_ALPHA`, y solo después de escribir la partición.

---

## 4. Documentos de referencia

| | |
|---|---|
| [`RANGO_VIGENTE.md`](RANGO_VIGENTE.md) | las tres ventanas, y por qué son tres |
| [`CANAL_MANUAL_CERRADO.md`](CANAL_MANUAL_CERRADO.md) | estado canónico de la base y el canal manual |
| [`HALLZGOS_H0001_H1014.md`](HALLZGOS_H0001_H1014.md) | los 4 defectos, con identificadores |
| [`CONTRATO_C4.md`](CONTRATO_C4.md) · [`CONTRATO_F72A.md`](CONTRATO_F72A.md) | los contratos del motor que la calibración no puede romper |
| [`APARCADO_DB.md`](APARCADO_DB.md) | lo que sigue aparcado |