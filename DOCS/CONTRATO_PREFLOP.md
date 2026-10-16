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
