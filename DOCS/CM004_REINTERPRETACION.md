# CM-004 — reinterpretación a mano de `hands_db.jsonl`

**Estado:** aplicado y verificado. Una corrección pendiente.
**Fecha:** 2026-10-14
**Qué toca:** 26 manos de `data/hands_db.jsonl` de 1280.
**Cómo se comprueba:** `python tools/verificar_cm004.py` (no escribe nada).
**Guard:** `motor/test_cm004.py`.

---

## 0. Lo primero: qué es y qué no es esto

Las 26 manos se corrigieron **a mano**, no con un script. Eso no invalida
nada, pero tiene una consecuencia que hay que decir antes que nada:

> **No hay ni un original.** `DOCS/CORRELACION_CAPTURAS_CM004.md` cerró el
> asunto con **0 de 23** correlacionables por los dos métodos baratos que
> existían. Lo que sigue son **reinterpretaciones**: lecturas del dato que son
> coherentes con el resto de la mano, no lecturas de lo que ocurrió.

La diferencia importa y no es retórica. CM-001 se corrigió con un **OCR**: hay
un 27,0 y un 2,7, y se lee el 2,7. Eso es dato observado. Aquí no hay nada
observado: hay un registro que se contradice a sí mismo y una decisión sobre
cuál de las dos lecturas es la buena.

Por eso **este documento no se titula "correcciones"**. Se titula
"reinterpretación", y por eso la tabla de la §3 declara una por una las que
cambian algo más que una etiqueta.

---

## 1. El defecto que se cierra

`learn._es_ciega_bb` reconoce la ciega del BB solo si **no hay ninguna acción
voluntaria antes** (`motor/learn.py:255`). Si la hay, la entrada no se
reconoce como ciega y el motor la lee como **una subida que puede no haber
ocurrido**.

En 23 manos la entrada `BB b` estaba en esa situación. Dos firmas distintas, y
las dos son la misma regla leída de dos maneras:

| | condición | manos |
|---|---|---|
| **A1** | el BB tiene una sola entrada preflop, **no** hay ciega en el índice 0, y esa entrada va **después** de una acción voluntaria | 22 |
| **A2** | el BB **sí** posteó su ciega en el índice 0, y aun así tiene un `b` **posterior** a una acción voluntaria | 1 (`H_0722`) |

`A2` es la única mano de las 1280 con ese patrón. Su preflop es
inequívoco: `BB b 1.0` (ciega), `MP f`, `CO f`, `BTN c`, `SB c`, **`BB b 2.0`**,
`BTN c`, `SB c`. Un `b` del BB después de su propia ciega no es una ciega.

**La regla es exacta.** Aplicada a la versión comprometida de la base
selecciona 23 manos, ni una más ni una menos, y son exactamente las
corregidas. Se comprueba en `test_la_regla_sigue_siendo_exacta_contra_la_version_comprometida`.

---

## 2. La regla vive en el motor

El detector es `learn.entradas_bb_rechazadas` / `learn.defecto_orden_ciega_bb`
(`motor/learn.py`), y `tools/auditar_bb_check.py` **lo importa** en vez de
tener su copia.

No es cosmético. El defecto **es** la discrepancia con el motor: si el script
recalcula el criterio por su cuenta, puede discrepar de `_es_ciega_bb` y
publicar un número que el motor no sostiene. Es el mismo motivo por el que
`no_puede_actuar` se movió a `motor/multiway.py`, y
`test_auditar_bb_check_reexporta_y_no_reimplementa` lo fija por AST.

---

## 3. El manifiesto: 26 = 17 + 6 + 3

### 3.1 Reetiquetado — 17 manos

Solo cambia la etiqueta de la entrada del BB: `b` → `r`. Una regla, derivada
del motor, exacta sobre las 1280.

```
H_0031 H_0037 H_0078 H_0104 H_0107 H_0127 H_0147 H_0161 H_0170
H_0183 H_0210 H_0215 H_0248 H_0262 H_0279 H_0294 H_0722
```

### 3.2 Reconstrucción — 6 manos

Aquí **no** basta con cambiar una etiqueta. Se añade, se borra o se reordena
alguna acción, o se cambia lo que hizo otro jugador. Eso es reconstruir el
orden, que es justo lo que CM-004 declaraba no inventable.

| mano | qué se hace además de `b`→`r` | en qué se apoya | cuán frágil |
|---|---|---|---|
| `H_0039` | **añade** `BB f 0.0` al final | la misma inferencia de CM-003 (preflop cerrado y el BB sin acción propia → folteó), que CM-003 no cubría porque aquí el BB sí tenía entrada. **Aditiva y con regla previa.** | baja |
| `H_0051` | `SB r 0.5` → `c 1.0`, y **añade** `SB f 0.0` | el `SB r 0.5` era una **subida por debajo de la ciega**: imposible, y del mismo género que CM-001 (un importe leído mal) | media |
| `H_0109` | `SB r 0.5` → `c 0.5` | la misma regla que `H_0051`, y aquí **no añade nada**, que es lo que lo hace más defendible | baja |
| `H_0143` | `CO r 1.0` → `c 1.0` | la misma regla con el límite más fino: subir a **exactamente** la ciega nominal sin que nadie haya subido antes no es imposible por regla, pero tampoco es una apertura | media |
| `H_0263` | **borra** `MP x 0.0` y reordena el preflop | el `MP x` estaba grabado **después** de que el MP ya hubiera foldeado en el índice 1: un check de un jugador que ya no está en la mano es una contradicción real, y borrarlo está justificado. **Reordenar el resto no lo está** | alta |
| `H_0067` | parte una única llamada `SB c 1.5` en **dos**: `SB c 1.0` y `SB c 1.5` | — | **la más frágil** |

> **`H_0067` deserve atención aparte.** El único defecto real era el `b` del
> BB. Todo lo demás es relleno: convierte una llamada grabada en dos
> llamadas, una de ellas a un importe que **no estaba grabado**. Inventa una
> acción y duplica un importe. Si algo de este bloque hay que revisar contra
> la grabación, es esta mano la primera.

La regla de las tres primeras se puede enunciar y merece enunciarse:

> **Una subida a un importe menor o igual que la ciega nominal, sin que nadie
> haya subido antes, no es una apertura: se relee como llamada.**

### 3.3 Ajeno a CM-004 — 3 manos

| mano | qué | en qué se apoya | estado |
|---|---|---|---|
| `H_0350` | dos `players` con `cards="-"` → `cards=""` | **CM-002.** El guion no es un código de carta: son las **2 únicas** apariciones de ese centinela en las 1280 manos, frente a **6085** usos de la cadena vacía. Normalizar el centinela **no es** reconstruir las cartas, que es lo que CM-002 prohíbe. | aplicado |
| `H_0969` | borra el `BB f` final del turn; `winner ["hero","p4"]` → `["hero"]` | el `BB f` va detrás de su propia apuesta sin respuesta: imposible. Con la apuesta del turn sin llamada el BB se lleva el bote, y el SB (p4) no puede figurar como ganador | aplicado |
| `H_0970` | `winner ["hero","p1","p4"]` → `["hero"]` | ver §4 | **pendiente** |

---

## 4. Lo que queda pendiente: `H_0970`

Es la única corrección **no** aplicada, y la única que el manifiesto marca
comotal.

**Lo que ocurre.** Preflop: `BB b 1.0` (ciega), `BTN f`, `SB f`. Todos foldean
hasta las ciegas. El `winner` grabado es `[hero(SB), p1(BB), p4(BTN)]`.

- El defecto real es que **p4 (BTN) foldeó y figura como ganador**.
- El recorte aplicado deja `["hero"]`, que además **quita p1 (BB)**, que
  comparte el bote. **Cambia un error por otro.**
- El valor correcto es **`["hero", "p1"]`**: las dos ciegas se reparten.

**Por qué no es opinión.** De las 77 manos con el mismo patrón en la base:

| mano | `winner` grabado |
|---|---|
| `H_0345` | `hero(SB)` + `p1(BB)` — las dos ciegas |
| `H_1050` | `hero(BB)` + `p5(SB)` — las dos ciegas |
| `H_0360`, `H_0365`, `H_0400`, `H_0473`… | solo el BB |
| `H_0881`, `H_1006`, `H_1087` | **las seis** |

El campo `winner` de esta base **no es fiable**: el recorder lo escribe en un
punto que no siempre es el final de la mano. Recortarlo a un elemento sin
regla lo deja **más** incoherente con sus vecinas, no menos.

**Por qué no se aplica ya.** Las dos manos están en las líneas **967 y 968**,
**fuera** del corte de 900: nunca entraron en ninguna cifra publicada. No hay
urgencia numérica, y la corrección de verdad exige mirar la grabación.
`test_h0970_no_coincide_con_lo_recomendado_y_eso_es_lo_que_se_declara` deja
constancia de que la diferencia es conocida y no un descuido. Cuando se
aplique, ese test hay que **borrarlo**, no relajar.

---

## 5. Qué NO se ha hecho, y por qué

### 5.1 Las 23 siguen excluidas de la ventana de calibración

Que el defecto esté resuelto **no** las devuelve a la ventana. Eso es otra
decisión, y es de quien mantiene la base.

El fundamento actual de la exclusión era textual: *«la entrada `BB: b`
aparece después de acciones voluntarias, luego el motor la lee como una
subida que puede no haber ocurrido»*. Ese motivo **ya no se cumple en ninguna
de las 23**. La exclusión se apoya ahora en un motivo distinto — que el
sustituto tampoco tiene original verificable — y ese motivo no está escrito.
Ver `DECISION_CM004.md` §0, que se ha actualizado en consecuencia.

Mover la ventana de 877 a 900 invalidaría **todas** las cifras de
`CONTRATO_F72A.md` y `RESUMEN_SECCION.md`, que se acaban de corregir. Por eso
aquí no se toca: es una decisión con coste de recálculo, no una consecuencia
de este bloque.

### 5.2 Los derivados no se han regenerado

`data/*.json` se reconstruyeron el 13/10 a las 19:57, en el commit `e314f74`.
La base cambió después. Se está obsoleto respecto del fichero actual.

Medido, el efecto es nulo sobre las cifras publicadas:

| | |
|---|---|
| las 23 de CM-004 | fuera de la ventana de calibración |
| `H_0969`, `H_0970` | líneas 967 y 968, fuera del corte de 900 |
| `H_0350` | dentro de la ventana, pero el cambio es de un centinela de carta |

`metrica_politica()` da **exactamente lo mismo** con la base actual:
656 puntos, denominador 507, MULTIWAY 226, 44,6 %, cota 255.

Regenerar los derivados toca miles de líneas por un cambio que no mueve
ninguna cifra. Es el mismo paso que las correcciones pendientes, y conviene
hacerlo **después**, no antes.

### 5.3 Ninguna corrección es «observada»

No se ha añadido `"inferred": true` a ninguna de las 26 entradas, y esa es una
decisión que queda abierta. Lo que sí se ha hecho es lo que se puede hacer sin
tocar la base: **declararlas una a una** en `tools/verificar_cm004.py`, con
motivo, fragility y estado. A favor de marcarlas está la garantía 4 de
`tools/aplicar_correcciones.py`: *«marcarlas como `observed` sería mentir»*,
y los 26 checks de CM-003 llevan su `inferred`. En contra: la base ya está
editada a mano, y añadir una cuarta edición por encima también es tocar lo que
no se ha pedido.

---

## 6. Cómo se verifica

```
python tools/verificar_cm004.py      # manifiesto, no escribe
python -m pytest motor/test_cm004.py -q
```

Cuatro preguntas, y las cuatro se responden contra el **motor**:

1. **Invariante.** ¿Alguna de las 1280 tiene una `BB b` que no pueda ser la
   ciega? **0.** Si vuelve a haber, alguien deshizo esto sin darse cuenta.
2. **Clasificación.** Para cada mano editada frente a la versión
   *comprometida*: ¿reetiquetado o reconstrucción? 17 / 6 / 3.
3. **Exactitud.** La regla aplicada a la versión comprometida selecciona
   exactamente las 23 corregidas.
4. **Colados.** Toda edición que no sea un reetiquetado trivial tiene que
   estar **declarada** en el script. Una cuarta sin declarar es un **fallo**,
   no una sorpresa.

Ese último punto es el que justifica el fichero. Una base editada a mano no
tiene quién la vuelva a hacer ni quién detecte que alguien la estropea. Un
instrumento que dice *«todo correcto»* delante de un cambio sin explicar es
peor que uno que dice *«no lo sé»*.

### Los guards se comprobaron mutándolos

Reintroducir la etiqueta `b` en `H_0031` → el invariante la detecta. Inyectar
un `BB b` nuevo en `H_0800` → también. Quitar un `hand_id` de
`EXCLUSIONES_VENTANA_FABLE` o añadir uno de más → el guard de exactitud falla
en los dos sentidos.

Es el mismo principio del commit que arregló el guard de `metrica_politica`,
donde la primera versión recalculaba en el test lo que vigilaba: mutada la
función para volver a incluir los folds, el test pasaba igual.

---

## 7. Reversión

`hands_db.jsonl` está versionado, así que la reversión es un `git checkout` de
la versión anterior. Los hashes para verificar cuál es cuál:

| | SHA-256 |
|---|---|
| antes de este bloque (`e314f74`) | `bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee` |
| después | `3b0574bda0d290b425d487d4a98b376991556a8a5324e5f77e637d9bd5b4859f` |

Los derivados se reconstruyen con `python tools/reconstruir_derivados.py regen`
y la suite con `python -m pytest motor recorder tests -q`.