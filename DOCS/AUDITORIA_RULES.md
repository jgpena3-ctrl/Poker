# AUDITORÍA DE `rules.py` — el camino de decisión, con estados sintéticos

> **Alcance:** cómo el motor pasa de las acciones disponibles a los
> candidatos, calcula el EV y elige la acción final. Y qué rutas devuelven una
> acción **sin cumplir su contrato**, y qué estados inválidos degradan en
> silencio.
>
> **Método:** estados **sintéticos y pequeños**, no la base. Y la razón es la
> de siempre: la pregunta es sobre el motor, y una comprobación que solo se
> puede construir con la base no es una comprobación.
>
> **Lo que NO se hace aquí:** arreglar nada. Las tres cosas que se han
> encontrado son de tres clases distintas, y solo una se puede resolver sin
> una decisión de alguien.

## 0. El camino, en tres pasos

```
las ACCIONES de la mesa
    -> plan()      -> los CANDIDATOS   (rules.py, la tabla RULES: 9 filas)
    -> select_best() -> la ACCION y su EV
```

Y el contrato de cada paso está en `DOCS/CONTRATOS_RULES.md` (C1-C5), y el
de la selección en `DOCS/CONTRATO_C4.md`, que está **firmado**.

MEDIDO, la tabla de reglas: **9 filas**, y los spots son `barrel`, `cbet`,
`donk`, `facing_bet`, `facing_raise`, `flop`, `probe`, `river` y `turn`.

## 1. El suelo del fold, y una etiqueta que puede no estar en el plan

**MEDIDO, con estados sintéticos:**

```
el plan ofrece ('check',) y el fold vale 5.0
    -> select_best devuelve ('fold', 5.0)
    y 'fold' NO está en rp.candidates
```

Y eso **no es un defecto**: es lo que dice el contrato firmado.

| | |
|---|---|
| `CONTRATO_C4.md` §2.1 | «Si todas las candidatas están por debajo, devuelve `('fold', <su EV real>)`» |
| `CONTRATO_C4.md` §2.4 | «Empate: gana el primero, y `fold` se considera siempre primero» |

Y el **resumen** dice otra cosa:

| | |
|---|---|
| `CONTRATOS_RULES.md` §C4 | «**`rp` dado** → la etiqueta devuelta está **siempre** en `rp.candidates`» |

> **Las dos cosas no pueden ser verdad a la vez**, y el código cumple la
> firmada. El resumen dice de más.

**Qué se hace:** se fija la conducta con un test
(`test_el_fold_es_el_suelo_y_puede_no_estar_en_el_plan`), para que no se mueva
en silencio. Y se deja constancia de la imprecisión del resumen, sin tocar el
contrato firmado.

**Qué NO se hace:** corregir el resumen, porque el resumen es de un documento
que apunta a un contrato firmado, y corregirlo es una decisión sobre cuál de
los dos manda. La medición está aquí para que la decisión se pueda tomar.

## 2. Las precondiciones: dos se comprueban, cinco no

**MEDIDO, con estados sintéticos:**

| estado | qué hace `plan()` | quién lo declare |
|---|---|---|
| `street='preflop'` | **lanza** `ValueError` | C2 lo declara |
| `to_call < 0` | **lanza** `ValueError` | el código lo comprueba |
| `facing_raise=True` con `to_call=0` | **lanza** `ValueError` | el código lo comprueba |
| board de 2 cartas | **devuelve un plan**, con la textura a `None` | C2 lo declara, y no se cumple |
| `pot` negativo | **devuelve un plan** | nadie lo declara |
| `stack` negativo o cero | **devuelve un plan** | nadie lo declara |
| `n_players = 0` | **devuelve un plan** | nadie lo declara |
| `n_players = 1` con `to_call > 0` | **devuelve un plan** de `facing_bet` | nadie lo declara |

Y el único rastro del board incompleto es **un `?` en la nota**:

```
nota = 'flop IP · bet tras check · ?'
```

> Un `?` en un texto es un rastro **débil**: es una nota, no un error, y
> pasar inadvertido es lo normal. Por eso los cinco estados inválidos que no
> se comprueban son un **hueco declarado** y no un fallo.

**Y cuáles son las cinco, y qué estado inválido representa cada una.** Y
la tabla va también en el test, que es donde se comprueba: una comprobación
que solo está escrita en un documento es una promesa.

| el cambio | el estado inválido que representa | quién lo declara |
|---|---|---|
| `board_codes` con 2 cartas | un board incompleto, de modo que la **textura es desconocida** | C2 lo declara, y no se cumple |
| `pot` negativo | un bote **negativo**, que no puede existir | nadie lo declara |
| `stack` negativo | un stack **negativo**, que no puede existir | nadie lo declara |
| `stack` cero | un stack de **cero**, sin fichas para actuar | nadie lo declara |
| `n_players` 0 | **cero jugadores** en la mesa, que no es una mesa | nadie lo declara |

**Qué se hace:** un test que fija la conducta actual
(`test_los_estados_invalidos_degradan_en_silencio`), de modo que si mañana
`plan()` empieza a lanzar, **el test falla y obliga a revisar el contrato**.
Un hueco declarado es una cosa; un hueco que se cierra solo, sin que nadie lo
decida, es otra.

**Qué NO se hace:** añadirlos a las validaciones. Lanzar en vez de degradar es
un cambio de COMPORTAMIENTO de un motor con dos rutas de producción
(`recommend_loop.recommend` y `asistente_live._recomendacion_para`), y eso es
una decisión con nombre.

> Y la razón de que no se conviertan «automáticamente» en un resultado válido:
> **un plan que sale de un estado que no puede existir es un plan que parece
> una decisión y no lo es.** Y por eso el hueco se DECLARA con su estado
> inválido, y no se tapa declarando que el plan es válido.

## 3. El plan «unknown», que no se alcanza

`_decide` devuelve un plan `('unknown', ...)` con candidatas `('fold', 'check')`
si ninguna regla casa. Y con `to_call == 0`, ese plan violaría C3 («candidates
contiene `fold` solo si `to_call > 0`»).

**MEDIDO:** en **ninguno** de los 13 estados sintéticos probados sale un plan
`unknown`. De modo que la violación es **latente**, y no hay nada que arreglar
hoy.

**Qué se hace:** nada, y se declara. Un invariante que no se puede alcanzar
tampoco se puede violar.

> Y el riesgo, escrito, para que no se lea como una garantia: **C3 NO está
> demostrado para todos los estados posibles.** Lo que está medido es que en
> los 13 estados sintéticos probados el plan `unknown` no aparece. De modo que
> la invariante «`candidates` contiene `fold` solo si `to_call > 0`» **no está
> demostrada** en el plan de reserva, y lo único que la sostiene es que ese
> plan no se alcanza. Si algún día se alcanzara, C3 se violaría sin que nada
> lo dijera.

## 4. Lo que la auditoría NO ha mirado, y por qué

- **Con los datos de hoy**: si el suelo del fold llega a dispararse de verdad,
  es decir, si en alguna mesa de la base el fold gana a un check con
  `to_call == 0`. Requiere el pipeline de EV completo, y no se ha medido. **Queda
  pendiente, y se dice.**
- **`recommend_loop` y `asistente_live`**: las dos rutas de producción. No se
  han auditado en este bloque.
- **Las reglas que nunca casan**: las 9 filas se han probado con estados
  sintéticos, pero no se ha medido cuántas se alcanzan con los datos de hoy.

## 5. El resumen, y lo que sale de aquí

| # | hallazgo | clase | qué se ha hecho |
|---|---|---|---|
| 1 | el fold puede volver sin estar en el plan | **documentación**: el resumen dice más que el contrato firmado | el comportamiento queda fijado con un test, y la imprecisión queda declarada |
| 2 | cinco precondiciones no se comprueban | **hueco declarado** | la conducta actual queda fijada con un test, y el hueco queda declarado |
| 3 | el plan `unknown` es inalcanzable | **latente** | nada que hacer, y se dice |

Y lo que sale de aquí, en una frase:

> **La auditoría de un motor encuentra, sobre todo, contratos que no se
> hablan entre sí.** Y el arreglo de eso no es de código: es de documento, y
> es de quien lo firma.

## 6. Un cuarto hallazgo, que es de OTRO sitio, y que no se arregla aquí

Y este no es de `rules.py`, sino de `motor/learn.py`, y salió al trabajar con
la acción `p`: una **apuesta de 0.5 BB o menos** se CLASIFICA como `limp` —y
el docstring de `classify_first_action` dice que «no se cuenta como subida
real»— pero el contador de `preflop_events` la cuenta como **subida** de
todas maneras.

Y las dos cosas no pueden ser verdad, y el desacuerdo se reproduce en
`motor/test_defectos_declarados.py`.

**MEDIDO:** **52 de 1258** manos, y **43 de las 877 de la ventana fiable**, que
es la que alimenta las cifras publicadas.

### Y la condición de activación, que es la parte importante

> **Se corrige cuando las cifras publicadas se re-deriven contra la base
> adoptada, y no antes.**

Y el motivo, que es el de siempre: arreglarlo **recalibra**, y una cifra
publicada no se mueve como efecto secundario de un arreglo. De modo que el
defecto queda **declarado y fijado** —un test que afirma la conducta actual y
su medición—, y se corrige en el bloque de la recalibración, que es donde las
cifras se mueven de todas maneras.

Y mientras tanto, el defecto tiene que ser **visible**: un `def test_` que
afirma el comportamiento equivocado, con la medición en el mensaje, es la
forma de que no se olvide.

> Y una cosa más, MEDIDO: el 43 no es un número pequeño. Es el 4,9% de la
> ventana. Y el efecto no es un detalle de una categoría: un limp corto cuenta
> como subida, y una subida cambia la categoría de **todos los que vienen
> después** en esa mesa. O sea que el efecto se propaga.
