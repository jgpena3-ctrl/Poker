# CONTRATO PREFLOP — la firma, antes de tocar `motor/`

> **No se implementa aquí.** Esto es el contrato: qué tiene que hacer, con
> qué firma, y qué test demuestra que está hecho. Escribirlo primero es lo
> que impide decidir la firma después de haberla usado.

## Por qué

**El motor no tiene ningún camino de equity preflop.** Medido:

| lo que se intentó | por qué falla |
|---|---|
| `situation(hero, [], ...)` | `evaluate_batch` declara board de **3 a 5** cartas |
| `decision.runout_equity(hero, [], ...)` | `_villain_arrays` llama a `evaluate_batch` con 0 cartas y pide `_SUBSETS[2]` |

`_SUBSETS` tiene `{5, 6, 7}`. Cualquier camino que termine en
`evaluate_batch` con menos de 5 cartas revienta, y los dos lo hacen.

Consecuencia: `L_sec` cubre el 38 % de la muestra y no puede decidir.

## El objetivo, y por qué está en el contrato

Una cosa que hay que tener clara **antes** de escribir la firma:

> La equity preflop contra rango **no es** la enumeración de `C(48,5)`
> contra una mano. Es una **integral sobre los combos del rango**.

Y hay un segundo requisito, que es el que `revision_2`repitio explícito y que
va en el contrato porque no es opcional: **tiene que ser observable**. Con
cartas del rival reales es retrospectiva; contra el rango, no.

## Firma propuesta

En `motor/hand_evaluator.py`:

```python
def equity_preflop_rango(hero_codes, villain_reach=None,
             n_runouts=DEFAULT_RUNOUTS,
             n_combos=DEFAULT_RUNOUT_COMBOS,
             seed=7):
  """Equity del hero en preflop contra un RANGO. Sin board.

  hero_codes : (N, 2) o (2,) codigos de carta del hero
  villain_reach : (1326,) pesos de los combos rivales, como en
          `RangeState.reach`

  Devuelve float en [0, 1]. Determinista para el mismo `seed`.

  Lanza ValueError si el rango no tiene combos legales.
  """
```

Y el enganche, en `motor/situation.py`:

```python
def equity_vs_range(hero_codes, board_codes, villain_reach=None,
          villain_ids=None):
  """Si `board_codes` esta vacio, delega en `equity_preflop_rango`."""
```

> **Por qué en `situation` y no en `hand_evaluator`:** la firma que ya existe
> (`equity_vs_range`) es la que usa `decision`, y ya trata el caso sin board
> de forma que hoy revienta. Cambiar su comportamiento **para que no
> reviente** es la mínima superficie; añadir una entrada nueva obliga a
> tocar más sitios. Pero esa es una decisión de implementación y se revisa al
> escribir el código, no antes: **lo que no se cambia después es el
> contrato.**

## Dos decisiones que hay que tomar antes de codificar

| # | pregunta | por qué bloquea |
|---|---|---|
| 1 | **exacto o muestreado** | `equity_preflop.py` enumera las 1 712 304 manos y da el valor exacto contra una mano concreta. Contra un rango de 1326 combos son 2 270 millones de evaluaciones. Hay que muestrear, y **la varianza del muestreo tiene que entrar en el contrato** |
| 2 | **qué pasa con las 41 manos de validación** | `DEFAULT_ALPHA` se ajusta sobre calibración. Si la equity preflop se usa para decidir, su varianza puede supera el cambio que se quiere medir. Hay que declararlo ANTES de medir |

## Lo que este contrato NO resuelve

> **Más cobertura no arregla una métrica que compara dos magnitudes que no
> son la misma.**

Antes de implementar esto hay que cerrar el **objetivo** de `L_sec`
([`L_SEC_NO_ADMISIBLE.md`](L_SEC_NO_ADMISIBLE.md)): equity contra
«ganó el bote», o equity contra «si continúo, ¿llegaba a ganar?». Y la
población homogénea, sin las manos en las que el hero foldea.

**Este contrato da una puerta, no una dirección.** Implementarlo primero y
medir después sería repetir el bloque pasado: una cobertura del 100 % de
una métrica cuyo objetivo no está definido.

## El test que demuestra que está hecho

```python
def test_l_sec_cubriria_el_cien_por_cient(equity_preflop_rango, ...):
  """Sin manos preflop sin cobertura.

  Y el detalle que importa: con cartas REALES del rival la equity es
  retrospectiva y no cuenta. El test tiene que comprobar la cobertura
  OBSERVABLE, que es la de `detalle['observable'] == True`.
  """
```

Y el que importa más:

```python
def test_la_equity_preflop_no_usa_cartas_del_rival(monkeypatch, ...):
  """Si el rango se construye con las cartas del rival, esto falla.

  La tentación va a ser pasarle la mano real porque es más exacto. Este
  test es para que eso no pase por sin que se note: es una fuga de
  información y no se nota en el número, solo en que el número es
  demasiado bueno.
  """
```

## Reproducir el diagnóstico

```
python tools/equity_preflop.py --comprobar  # AA vs KK = 0,8195
python tools/equity_de_mano.py --mano H_0798
```

---

# Las dos decisiones, medidas

Las dos quedaron abiertas arriba con la palabra «antes». Ya se han medido, y
el resultado cambia el orden del trabajo: **el estimador no es el problema.**

Instrumento: [`tools/auditar_preflop_varianza.py`](../tools/auditar_preflop_varianza.py)

## Decisión 1 — **muestreado**, con `n_combos = 40`

Exacto son 1326 × C(48,5) = **2,3 × 10⁹** evaluaciones por mano. Muestreado a
40 combos son 65 600. Y el sigma del estimador, medido con el rango real de un
villano:

| `n_combos` | error medio | desv. típica | error **máximo** |
|---:|---:|---:|---:|
| 5 | 0,0561 | 0,0429 | 0,2258 |
| 10 | 0,0389 | 0,0295 | 0,1882 |
| 20 | 0,0274 | 0,0208 | 0,1410 |
| 30 | 0,0221 | 0,0167 | 0,1089 |
| **40** | **0,0195** | **0,0148** | **0,0989** |

> **σ(n = 40) = 0,0934.** Ese es el número que va en el contrato, no uno
> supuesto. Y la curva es 1/√n: cuadruplicar los combos solo parte el error
> en dos.

Con el prior plano el sigma es el mismo (0,1037 a 40 combos, medido): el
muestreo lo domina la dispersión de la equity, no la forma del rango.

## Decisión 2 — **la varianza es admisible**

### La vara equivocada, y por qué casi importa

El enfoque natural es preguntar *cuántos combos hacen falta para que el ruido
no reordene dos manos*. Está mal planteado, y medido:

| vara | valor | qué es |
|---|---:|---|
| hueco **mínimo** entre dos manos contiguas | **0,0004** | el par de manos más cercano que hay |
| hueco mediano entre dos manos contiguas | 0,0105 | la resolución de verdad |
| **semiancho del IC del AUC** | **0,1180** | lo que el AUC ya **no sabe** por tener 47 manos |

Contra el hueco mínimo haría falta **337 308 combos por mano**, 51 días por
mano. Y sería exigir precisión para nada: dos manos a 0,0004 de distancia no
las distingue ninguna métrica, y que se reordenen no cambia ninguna conclusión.

### La vara correcta

> **El criterio: el ruido del estimador tiene que mover el AUC menos que lo
> que la muestra ya no sabe.** O sea, menos que el semiancho de su propio
> intervalo.

Medido, inyectando ruido gaussiano de σ en las 47 equities de la población
declarada:

| σ | AUC medio | movimiento del AUC | vs semiancho |
|---:|---:|---:|---:|
| 0,005 | 0,8298 | 0,0025 | 0,02× |
| 0,010 | 0,8271 | 0,0048 | 0,04× |
| 0,020 | 0,8227 | 0,0097 | 0,08× |
| 0,040 | 0,8187 | 0,0133 | 0,11× |
| 0,060 | 0,8134 | 0,0199 | 0,17× |
| **0,0934** ← `n_combos = 40` | **0,8024** | **0,0303** | **0,26×** |
| 0,150 | 0,7809 | 0,0527 | 0,45× |
| 0,250 | 0,7330 | 0,1007 | 0,85× |

Y por la **cola**, que es la que importa cuando lo que se decide es si un
intervalo incluye 0,5:

| | movimiento | vs semiancho |
|---|---:|---:|
| típico con 40 combos | 0,0303 | **0,26×** |
| percentil 95 con 40 combos | 0,0499 | **0,42×** |

> **Los dos por debajo de 1.** A 40 combos la conclusión aguanta por los dos
> lados: el ruido típico mueve el AUC 0,26× su semiancho y el percentil 95 lo
> mueve 0,42×.

### Y más combos no hacen falta

Lo contrario de lo que se suele suponer: **aquí el cuello de botella son las
47 manos, no los 40 combos.** Bajarlos a 10 daría σ = 0,0295, pero su error
**máximo** sería 0,1882, más que el semiancho: la cola se dispara. Hay un
punto óptimo, y está por debajo de 40.

### El coste

```
98 manos × 40 combos × 13 s = 50 960 s = 14,2 horas
```

**Un solo pase**: la cache de `equity_preflop.py` es por par *(hero, rival)*,
así que la segunda medición es gratis. Y son 13 s por combo porque cada uno
es una enumeración de C(48,5) = 1 712 304 tableros.

## Una trampa que se encontró midiendo

`prob_vec_player` espera un **nombre de jugador**, no un puesto. Pasándole
`'BB'` — que no es el nombre de nadie — cae al prior plano **en silencio**: la
masa sale 198,900, los 1326 combos a 0,150000, un solo peso distinto, y ningún
aviso. El rango parece bueno y no dice nada del rival.

> Es el mismo error que el proyecto ya declaró en otra forma: *«hero» es el
> puesto 0, no una persona*. Un puesto no identifica a nadie.

## Lo que queda abierto

| | |
|---|---|
| la firma `equity_preflop_rango(hero_codes, villain_reach, …)` | **sin tocar** |
| `_SUBSETS` y el camino de `hand_evaluator` | sin tocar |
| `DEFAULT_RUNOUT_COMBOS = 200` de `decision.py` | **no** se cambia a 40 |

Ese último es un desacuerdo con la firma propuesta y queda declarado: el
contrato propone `n_combos` con su propio defecto, y `decision.py` ya usa 200
para el postflop. **No se baja a 40** sin medir el postflop, que es otro
problema.

Y lo que sigue sin saberse, y no lo decide este contrato:

> Si la equity preflop **observable** ordena las manos. Que el estimador tenga
> la varianza correcta no dice que la señal sea buena. Eso se mide con el
> mismo AUC y el mismo intervalo, **después** de implementarla.
