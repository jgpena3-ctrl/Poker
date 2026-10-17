# APUESTAS: CHIPS, NO TOTALES — y por qué la mezcla no es una mezcla

**Estado:** vigente. Base `33ab8ee`, sha `35727961646dfaba`.
**Alcance:** las 1258 manos.

---

## 1. La pregunta

> ¿Qué significa `streets[s].actions[i].amount`: lo que se pone **ahora**, o el
> **total** que lleva puesto ese jugador en la calle?

Lo que dice el repo hoy es lo segundo. `tools/auditar_rango.py` lo afirma en su
propia cabecera:

> `streets[s].actions[i].amount` es el importe TOTAL puesto por esa accion,
> no un delta.

Y el comentario de `importe_subida` lo refuerza: «POSTFLOP se mide por calle,
porque `amount` es el total puesto en esa calle».

**Medido, el repo dice lo contrario.** Y no por poco.

---

## 2. Cómo se mide, sin Interpretationes

La señal limpia es una **call de alguien que ya tenía fichas puestas en esa
calle**. Si el jugador tiene `ya` y la apuesta viva es `viva`, entonces:

| lectura | lo que debería decir el importe |
|---|---|
| **CHIPS** | `viva - ya` — lo que le faltaba para igualar |
| **TOTAL** | `viva` — lo que lleva puesto en la calle |

Las dos dan números distintos, así que la acción discrimina. Cuando el jugador
**no** tenía nada puesto —una apertura, o una call sin ciega grabada— las dos
coinciden y la acción no dice nada. Eso no es un fallo del método: es que esa
acción, por sí sola, no puede.

Por eso la cuenta se hace **por calle y por grupo**, y el grupo que decide es
el de las manos con la ciega del BB grabada: el BB postea y luego vuelve a
actuar, y es el único que siempre tiene `ya > 0`.

> El primer intento de esta medición clasificó las etiquetas al revés y
>Llegó a la conclusión contraria. Queda escrito porque el error es el que hace
> el asunto confuso: si el BB ya posteó 1.0 y la viva es 2.5, un `c 1.5` son
> **CHIPS**, no total. Nombrar bien las dos lecturas es medio del trabajo.

---

## 3. El resultado

### 3.1 Las manos CON la ciega del BB grabada: 921

De las 400 calls que discriminan en este grupo:

| lectura | casos | |
|---|---|---|
| **CHIPS** | **375** | **93.8%** |
| TOTAL | 25 | 6.2% |
| ninguna de las dos | 33 | 8.3% |

### 3.2 Las manos SIN la ciega del BB grabada: 337

De las 61 calls que discriminan:

| lectura | casos | |
|---|---|---|
| CHIPS | **0** | **0%** |
| **TOTAL** | **61** | **100%** |

### 3.3 El cruce

| | manos | CHIPS | TOTAL | |
|---|---|---|---|---|
| ciega grabada | 921 | 375 | 25 | **93.8% CHIPS** |
| ciega **no** grabada | 337 | 0 | 61 | **0% CHIPS** |

**La mezcla no es una mezcla de convenciones.** Es una sola convención —CHIPS—
y 337 manos donde la ciega del BB **no está en la lista de acciones**, así que
quien las escribió cayó en la lectura natural («subió a X») porque no tenía la
ciega delante para leerla como fichas.

La diferencia entre los dos grupos es de **0% a 93.8%**, y la variable que la
explica es una sola: si el posting está grabado o no.

---

## 4. Qué se lleva por delante

### 4.1 `IMPORTE_SUBIDA` da 30 y son 5. Los otros 25 son falsos positivos.

El detector exige `amount > learn.BB` (1.0), un **suelo absoluto**, sobre datos
que son **CHIPS**. Con la aritmética correcta —el total del jugador tras la
subida tiene que superar la viva— la cuenta es:

| | manos con una subida que no supera la viva |
|---|---|
| `importe_subida` hoy | **30** |
| con la aritmética CHIPS | **5** |
| ...y de esas 5, con la ciega grabada | **0** |

**Ninguna** mano con la ciega grabada tiene una subida inválida. Las 30 del
lote `IMPORTE_SUBIDA` de `DOCS/SANEAMIENTO.md` §3.3 son trabajo que no existe.

### 4.2 El motor ya asume CHIPS, en el sitio que importa

`motor/observations.py:164`:

```python
sizing = amt / pot_before      # b/r: fracción del bote
```

Con CHIPS eso es correcto: `amt` es lo que se pone ahora, sobre el bote de
antes. Con TOTAL estaría contando dos veces lo que el jugador ya había
puesto. **El motor está escrito para la lectura correcta.** Lo que está mal
es el docstring y el detector, no el entrenamiento.

### 4.3 Un riesgo latente en `learn.classify_first_action`

```python
if raises_before == 0 and amount <= bb + 1e-9:
    return 'limp', 'no_raise'
```

`amount <= 1.0` se lee como «limpeo». Bajo CHIPS, si el jugador **ya tenía**
fichas en esa calle, 1.0 de importe es una subida real (total ≥ 2.0), no un
limpeo.

**Medido hoy: 0 casos.** No hay ninguna mano de la base donde la regla se
dispare mal. Es un riesgo latente, no un error activo, y por eso se anota y no
se toca: cambiar la regla sin un caso que la dispare es cambiarla a ciegas.

---

## 5. Plan de corrección

### Fase 0 — declarar la semántica (sin tocar la base)

El repo afirma lo contrario de lo que hace. Eso solo ya produce decisiones
equivocadas: cualquiera que lea `auditar_rango.py` para decidir algo trabajo
con la lectura equivocada.

- Reescribir la cabecera de `tools/auditar_rango.py` y el comentario de
  `importe_subida`: `amount` son **CHIPS**.
- Ponerlo en `DOCS/` con esta tabla, para que no dependa de leer código.
- Un test que fije la proporción, con la mirada en los dos grupos: si la
  proporción del grupo con ciega grabada se mueve, alguien ha cambiado de
  convención y hay que enterarse.

### Fase 1 — arreglar `importe_subida` (el más barato)

Recalcular la aritmética en CHIPS. **30 → 5**, y las 5 quedan en un lote
distinto y pequeño, todas sin ciega grabada.

Es la fase con mejor ratio del plan: una función, un test, y desaparece el 90%
de un lote de trabajo.

### Fase 2 — decidir las 337 ciegas ausentes (la de verdad)

Este es el problema de fondo. Antes de tocar la base hay que **decidir qué se
hace con ellas**, porque las dos opciones son defendibles y tienen consecuencias
distintas:

| | opción A | opción B |
|---|---|---|
| qué se hace | **insertar** el posting que falta | **declararlas** y hacer que los lectores lo tolerate |
|cuándo se puede | cuando la ciega se deduce de la mano (p. ej. `H_1063`, cuyo bote solo cuadra con el BB posteando) | siempre, sin mirar nada |
| qué gana | la base queda homogénea y `CHIPS` es verdad en las 1258 | no se inventa nada |
| qué cuesta | revisar 337 manos una a una | propagar «puede faltar la ciega» por todo el motor, y `learn.BB` deja de ser un suelo fiable |
| riesgo | escribir una ciega que no estaba | que el motor produzca categorías distintas según la mano |

**Mi lectura: A para las manos donde la ciega es deducible, B para el resto.**
Mezclarlas es peor que las dos puras: es lo que hizo que hoy 337 manos se
lean distinto de las otras 921.

### Fase 3 — las 52 manos que aún discrepan

En el grupo con ciega grabada quedan 52 manos con al menos una call que no es
CHIPS (25 `TOTAL`, 33 que no cuadran con ninguna lectura). Son el residuo real,
y se van a la grabación original como el resto del saneamiento.

### Fase 4 — cuadrar el bote (separada, y es la grande)

La suma de lo puesto en las cuatro calles **no cuadra** con `final_pot` en
1169 de 1258 manos, en CHIPS. Reparto: 89 exactas, 792 sobran, 377 faltan.

La diferencia más común es **exactamente −0.5, en 188 manos**, que es una
ciega pequeña. Eso es una pista, no una conclusión: puede ser la ciega del SB
sin grabar, o un bote robado, o un all-in sin llamar.

Esta fase **no depende** de las anteriores y no se empieza hasta cerrar la
Fase 2, porque hasta no saber si la ciega se graba o no, cualquier
conciliación de bote va a comparar contra una base que no es la real.

---

## 6. Lo que este plan NO hace

- **No convierte absolutos en delta.** La base ya es delta en el 93.8% de las
  manos donde se puede comprobar. Convertir sería inventar.
- **No rellena las 337 ciegas a ciegas.** La Fase 2 pide una decisión, y la
  decisión es del mantenedor.
- **No toca `classify_first_action`.** El riesgo es latente y son 0 casos;
  cambiarla sin un caso que la dispare es cambiarla a ciegas.
