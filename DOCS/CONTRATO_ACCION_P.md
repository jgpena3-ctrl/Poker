# CONTRATO DE LA ACCIÓN `p` — una posta que no es una decisión

> **Estado:** propuesto. **No firmado**, y por tanto **no aplicado** a la base.
> La base canónica **no cambia** con este documento.
>
> **Alcance:** la SEMÁNTICA de `p` para el motor, y qué consumidores tienen
> que aprenderla. No es la adopción de la base, que es otra decisión y es de
> quien revise las 203 manos.

## 0. Por qué este documento existe

La copia normalizada de la base —`trabajo/hands_db_edicion.jsonl`— mete una
acción que el motor no conoce. MEDIDO:

```
la base canonica : b 2397   c 2558   f 4996   r 1019   x 2856
la copia          : b 1481   c 2569   f 4998   r  982   x 2883   p 2514
```

Y `motor/learn.py` **no menciona la acción `p` ni una vez**. De modo que si
esa copia pasase a ser la canónica, el motor **LANZARÍA**:

```
ValueError: acción preflop desconocida: 'p'
```

Y lanzando es lo mejor que puede pasar, pero es por casualidad: el motor no se
entera de que la base habla otro idioma. Lanza en mitad de una calibración, y
el motivo —que la codificación cambió— no está declarado en ningún sitio.

Este documento declara la semántica **para que el motor la entienda antes de
que la base la use**.

## 1. Qué es `p`

**Una posta: el jugador pone dinero en el bote sin que sea una decisión.**

Y las tres propiedades, y las tres se miden:

| | `p` | `b` | `c` | `r` | `f` | `x` |
|---|---|---|---|---|---|---|
| pone dinero en el bote | **sí** | sí | sí | sí | no | no |
| es una decisión | **no** | sí | sí | sí | sí | sí |
| sube el nivel del bote | **no** | sí | no | sí | no | no |

Y la fuente de esa tabla no es una opinion: es el **trabajo en paralelo**, que
ya la implementó en sus propias herramientas.

- `tools/interpretar_bote.py` (líneas 65-69): la acción entra en el cómputo
  (`com[pos] = v`) pero **no** marca subida (`ultimo_subio` solo para `b` y
  `r`).
- `tools/aritmetica_botes.py` (líneas 97-99): una `p` pone su importe en el
  bote, y no es un fold ni un check.

Y la tercera fila es la que la distingue de una apuesta: **una `p` no sube el
nivel**. Por eso la ciega, que es una posta, no hace que el resto de la mesa
«vea» una subida.

## 2. MEDIDO: la codificación NO cambia la aritmética del bote

Y esto corrige una hipótesis mía, que era falsa:

> Yo suponía que la codificación vieja calculaba mal el bote, porque una
> ciega grabada como `b` sube el nivel. **MEDIDO, con la herramienta del
> trabajo en paralelo, sobre las 1258 manos:**

```
la canonica  : el bote calculado coincide con el grabado en 1258 de 1258
la copia     : el bote calculado coincide con el grabado en 1258 de 1258
la diferencia: 0 manos
```

> **Ninguna de las dos codificaciones calcula mal el bote.** O sea que la
> diferencia entre ellas **no está en la aritmética**, y por tanto adoptarla
> no obliga a rehacer el bote: obliga a rehacer lo que dependa de **qué
> acciones hay**, que es otra cosa.

## 3. Lo que la copia SÍ añade, y es más que una recodificación

MEDIDO, y aquí está la parte que no es solo «escribirlo de otra manera»:

| | la canónica | la copia |
|---|---|---|
| acciones `p` en el preflop | 0 | **2514** |
| ciega del BB registrada | 921 de 1258 | **1258 de 1258** |
| ciega del SB registrada | 1 de 1258 | **1219 de 1258** |
| primera acción del preflop | 921 manos con `BB b` | 1219 con `SB p`, 39 con `BB p` |

> La copia **completa** la estructura de ciegas. En la base de hoy, **337 de
> 1258 manos no tienen la ciega del BB registrada**, y **1257 de 1258 no
> tienen la del SB**.

Y eso es lo que `FRONTERA_GRABADOR.md` mide: hay dos generaciones de grabador
en la misma base, y la vieja no emitía la ciega.

## 4. Los consumidores que tienen que aprender `p`

Y la lista **no se escribe de memoria**: sale de un experimento. Se coge la
base canónica, se recodifican sus ciegas como `p` —un cambio químico, sin
tocar la base ni la copia— y se mide qué consumidores dan otra respuesta.

```
MEDIDO, manos de 1258 cuya respuesta CAMBIA al recodificar las ciegas:

  la primera accion del preflop            921
  classify_first_action de la primera      921
  la secuencia preflop completa            922
  el dinero puesto (b + r)                 922
  la ciega reconocida (regla VIEJA)        921
  la ciega reconocida (regla NUEVA)          0   <-- retrocompatible
  el numero de acciones                    0
```

Y de ahí la lista, y el orden de los dos primeros:

| | consumidor | qué tiene que hacer con `p` |
|---|---|---|
| 1 | `learn._es_ciega_bb` | reconocerla como **la ciega del BB**: `act in ('b', 'p')` |
| 2 | `learn.preflop_events` | **saltarla**: una posta no es una decisión, y el jugador que posta la ciega sigue sin decidir |
| 3 | `learn.classify_first_action` | **no**: sigue lanzando ante una `p`, porque clasifica una DECISICIÓN y una posta no lo es. Quien la llame tiene que filtrar antes. |
| 4 | `motor/stats.py` y las herramientas de auditoría que cuentan dinero y decisiones | distinguir «posta» de «apuesta» al contar lo que sube el nivel |

Y el punto 3 es el que hay que entender bien, porque es el que parece un
contraste:

> `classify_first_action` **lanza** ante una `p`, y eso es lo correcto. Lo que
> cambia de sitio es **quién decide qué acción es la primera decisión**: la
> la posta no cuenta como decisión, y por tanto el filtro va un paso antes.

Y el resto de la lista —las herramientas de auditoría, `comparar_folds.py`,
`que_regla_da_1599.py`, `diagnostico_grabador.py`— son **auditorías**, no el
motor, y su Actualización depende de que la base se adopte. Quedan
**declarados** aquí, y se hacen cuando se adopte.

## 5. El invariante de CM-004, y cómo se traduce

En la codificación vieja, el invariante vigila **una `BB b` que no puede ser la
ciega**. Y en la nueva, la ciega es una `p`, de modo que **una `BB b` es
siempre una apuesta** y el invariante viejo no puede dispararse.

MEDIDO, el invariante viejo sobre la copia: **0 violaciones**, y 0 porque la
regla ya no puede dispararse (6 manos de 1258 con ciega reconocida, contra
921).

> **Un invariante que da cero porque ya no puede dispararse es peor que un
> rojo**, porque el rojo se ve. Ver `DOCS/LECCIONES_DE_INSTRUMENTACION.md` §26.

Y el invariante nuevo, que es el mismo defecto con otra codificación:

> **Una `BB p` DESPUES de una acción voluntaria.** Una ciega puesta tarde.

MEDIDO: **0 manos** en las dos codificaciones. De modo que la regla nueva se
cumple hoy, y se cumple en la copia.

## 6. Lo que este contrato NO hace, y por qué

1. **No adopta la base.** La base canónica no cambia, y su manifiesto tampoco.
2. **No fija el número esperado de la base normalizada.** Y la razón es
   concreta: ese número tiene que salir de **datos ya revisados**, y las 203
   manos las está revisando A1. Fijarlo ahora sería fijarlo sobre una copia
   que todavía no es la canónica.
3. **No recalcula frecuencias, rangos ni perfiles.** Y la razón: son
   derivados de la base, y la base no ha cambiado.
4. **No toca las 203 manos.** Lo que dependa de ellas queda pendiente, y
   declarado como pendiente.

## 7. Lo que queda hecho al motor cuando la base se adopte

En orden, y el orden importa:

1. **El motor aprende `p`** —que es lo que este contrato habilita— y se
   comprueba con manos **sintéticas**: ciega, fold, call y subida.
2. **La base canónica pasa a ser la copia**, y se redeclara el manifiesto
   (sha, commit, líneas) con el motivo escrito.
3. **Se re-derivan los números derivados** —frecuencias preflop, rangos,
   perfiles, AUC— contra la base nueva, y se comparan con los antiguos.
4. **Se fija el número esperado** de las invariantes que dependen de la base,
   a partir de los datos revisados.
5. **Se actualizan las herramientas de auditoría** del punto 4 de §4.

Y el punto 3 es el que más cuesta, y por un motivo que ya se ha medido: el
reparto por acción cambia de `b 2397` a `b 1481`, y `p` aparece 2514 veces. O
sea que **el conjunto de acciones que el motor ve es otro**, y todo lo que
se mida sobre acciones se mueve.

## 8. La prueba, y qué tiene que Fallar

La prueba de este contrato son manos **sintéticas** y pequeñas, y no la base:

| caso | qué tiene que pasar |
|---|---|
| ciega del BB como `p`, y luego el BB sube | el BB tiene dos acciones, y la segunda es la subida |
| ciega del SB como `p`, y luego el SB foldea | el SB pliega, y **no** cuenta como limp |
| `p` en el preflop, y nada más | el jugador que posta sigue **sin decidir**, y no hay ningun evento suyo |
| `BB p` después de una acción voluntaria | es la **analogía de CM-004**, y se detecta |
| una `b` normal | se sigue clasificando como antes: `open`, `rol`, `limp`… |

Y la comprobación de que el motor **no ha cambiado** con la base de hoy: las
921 manos con ciega reconocida siguen siendo 921, y las frecuencias del
preflop no se mueven. Que es lo que hace que este cambio sea **preparatorio**
y no una recalibración.
## 9. Un defecto que este trabajo ha destapado, y que NO se arregla aquí

Y sale de la semántica de `p`, y no de buscarla: al preguntar «qué es una
posta», y ver que la ciega del SB es una posta, aparece que **en la
codificación vieja la ciega del SB se cuenta como un limp** —y que el motor
además la cuenta como una **subida**.

Y las dos cosas no pueden ser verdad. El propio docstring de
`classify_first_action` dice lo contrario:

> Un 'b'/'r' de a lo sumo 1BB sin subida previa es un limpe corto grabado
> como bet. **No se cuenta como subida real.**

Y el código, en `preflop_events`, cuenta cualquier `b` como subida:

```python
        if act in ('b', 'r'):
            raises += 1
```

Y el caso mínimo, MEDIDO:

```
un SB que postea 0.5 y un UTG que sube 2.5
    codificacion VIEJA (SB b 0.5)  ->  SB 'limp'   y UTG '3bet'
    codificacion NUEVA (SB p 0.5)  ->  el SB no decide, y UTG 'open'
```

Y el alcance, MEDIDO:

| | |
|---|---|
| eventos de primera decisión de categoría `limp` | 571 |
| de los cuales son **limps cortos** (un `b` de ≤ 1.0 BB) | **52** |
| manos de la base con un limp corto | **52 de 1258** |
| **manos de la ventana fiable** | **43 de 877** |

> Y 43 de las 877 es la cifra que alimenta las métricas publicadas. De modo
> que **arreglar este defecto las mueve**, y una cifra publicada no se mueve
> como efecto secundario de un arreglo.

Y por eso **no se arregla aquí**, y por qué la decisión es de otro:

1. Es un **defecto del motor**, no de los datos: el motor se cuenta mal a si
   mismo cuando un limp se grabó como apuesta. Y eso se puede arreglar sin
   tocar la base.
2. Pero **arreglarlo recalibra**, y la recalibración está bloqueada hasta
   que A1 cierre la revisión de las 203 manos: las cifras se re-derivan
   contra la base que se adopte, y no tiene sentido fijarlas dos veces.
3. Y la **semántica que hay que decidir** es de fondo, y no es mecánica: ¿un
   limp corto cuenta como subida para los que vienen después? El docstring
   dice que no. Pero eso cambia la categoría de los jugadores siguientes, y
   por tanto las frecuencias.

Y lo que este bloque hace, en vez de arreglarlo:

- **lo declara**, con la medición;
- **lo deja escrito en el motor**, junto a la regla, para que no se pierda;
- y **lo anota como pendiente de la recalibración**, no como un bug olvidado.

> Y esto es lo que quiere decir «A2 puede mejorar la capacidad del motor para
> interpretar correctamente los datos»: puede DECLARAR que el motor se
> interpreta mal a sí mismo en 43 manos, y puede arreglarlo; lo que no puede
> es cambiar las cifras publicadas sin que alguien lo decida, porque un número
> que se mueve sin decisión es un número que nadie ha medido.
