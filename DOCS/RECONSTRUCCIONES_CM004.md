# RECONSTRUCCIONES DE CM-004 — las seis, decididas una a una

**Estado:** cerrado. Las seis han sido **revertidas parcialmente**.
**Fecha:** 2026-10-14
**Cómo se comprueba:** `python tools/aplicar_reinterpretacion.py` (dry-run) y
`python tools/verificar_cm004.py`.
**Disco:** 24 manos distintas de `e314f74` — 23 reetiquetados de CM-004 y
`H_0350`. Nada más.

---

## 0. La decisión y el criterio que la gobierna

`revision_1` fija el criterio, y es medible:

> «`H_0039`, `H_0051`, `H_0109`, `H_0143`: mantener si el patrón es
> demostrable con otros casos **no editados**; revertir si no lo es.»

Se ha medido. **Y la respuesta es que el problema no es que el patrón sea
indemostrable: es que se repite cientos de veces y se corrigió una.**

| patrón | instancias en las 1280 | corregidas a mano |
|---|---:|---:|
| el BB tiene entrada, no vuelve a actuar, y el preflop se cierra con una subida viva | **652** | 1 (`H_0039`) |
| subida a un importe ≤ la ciega nominal siendo la primera acción voluntaria | **45** | 3 (`H_0051`, `H_0109`, `H_0143`) |
| acción de una posición después de que esa misma posición haya foldeado | **8** | 1 (`H_0263`) |
| `winner` incluye a alguien que foldeó en algún momento de la mano | **214** | 1 (`H_0970`) |
| `cards="-"`, centinela que no es un código de carta | **2** | **2** (`H_0350`) |

La última fila es la que explica las decisiones: **es el único patrón que se
aplicó a todas sus apariciones.**

### Por qué eso decide

Corregir 1 de 652 no arregla un defecto: crea una base en la que el mismo
patrón está bien en una mano y mal en 651, sin que nada diga por qué. Eso es
peor que un defecto uniforme, porque un defecto uniforme se puede medir,
declarar y corregir después con un script — que es exactamente lo que se hizo
con CM-003 (26 checks, `inferred: true`, todos los casos).

Un defecto **parcheado sin script no es recuperable**: nadie puede saber qué
se va a corregir, porque la respuesta depende de qué mano se miró.

---

## 1. Las seis, una a una

En todas: **se conserva el `b` → `r` del BB**, que es la parte de CM-004 y
tiene una regla exacta y derivada del motor. Se revierte todo lo demás.

### `H_0039` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 6.0` → `BB r 6.0` |
| **qué se revierte** | el `BB f 0.0` añadido al final |
| **motivo** | el fold no lo grabó nadie. Es defendible como inferencia (el BB no responde a la resubida del SB), y es **la misma inferencia que aplicó CM-003**. Pero CM-003 la aplicó a las 26 manos que cumplían el patrón y las marcó `inferred`. Aquí se aplicó a **una** de 652 y sin marca. |

### `H_0051` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 5.0` → `BB r 5.0` |
| **qué se revierte** | `SB r 0.5` → `c 1.0`, y el `SB f 0.0` añadido |
| **motivo** | el `SB r 0.5` era una subida por debajo de la ciega, imposible, y del mismo género que CM-001. Pero hay **45** tales casos y se corrigieron **3**. `revision_1` pedía mantener si el patrón fuese demostrable con casos no editados: el patrón es **demasiado común** para ser un criterio de corrección manual. Es un defecto de recorder, y un defecto de recorder se arregla con script sobre los 45 o no se arregla. |

### `H_0067` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 2.5` → `BB r 2.5` |
| **qué se revierte** | partir una única llamada `SB c 1.5` en dos: `SB c 1.0` y `SB c 1.5` |
| **motivo** | **el peor de los ocho.** Inventa una acción a un importe que no constaba y duplica un importe. El único defecto real era el `b` del BB; el resto es relleno. `revision_1` recomienda revertir, y la razón no es el parecido con los otros: es que no hay ningún otro caso en la base donde una llamada grabada se parta en dos, ni patrón que lo sugiera. Es una invención sin regla. |

### `H_0109` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 3.0` → `BB r 3.0` |
| **qué se revierte** | `SB r 0.5` → `c 0.5` |
| **motivo** | idéntico al de `H_0051`: uno de los 45. Es el más limpio de la familia, porque no añade ninguna acción, pero eso no lo diferencia: la arbitrariedad está en elegir 3 de 45. |

### `H_0143` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 3.0` → `BB r 3.0` |
| **qué se revierte** | `CO r 1.0` → `c 1.0` |
| **motivo** | el mismo patrón con el límite más fino: subir a **exactamente** la ciega nominal sin que nadie haya subido antes. No es imposible por regla, así que la regla es aún más discutible, y hay 44 casos más sin tocar, entre ellos `H_0139` (`BB r 1.0`). |

### `H_0263` — REVERTIDO PARCIAL

| | |
|---|---|
| **qué se mantiene** | `BB b 2.5` → `BB r 2.5` |
| **qué se revierte** | el borrado de `MP x 0.0` y todo el reordenamiento del preflop |
| **motivo** | el `MP x` estaba grabado **después** de que el MP ya hubiera foldeado en el índice 1: un check de alguien que ya no está en la mano es una contradicción real, y el borrado **está justificado**. `revision_1` recomienda mantener el borrado y revertir el reordenamiento. No se hizo, por una razón que va más allá: el patrón aparece **8 veces** y se corrigió **una**. `H_0054`, `H_0103` (tres veces), `H_0180`, `H_0236` y `H_0330` siguen igual. |

> **Por qué aquí no se sigue la recomendación al pie de la letra.** Borrar
> un check de un jugador que ya foldeó es correcto poker, y aun así queda
> sin hacer. Un defecto sistémico de 8 casos no se resuelve de a una: o se
> hace con script y se declara, o no se hace. La recomendación era
> «revertir el reordenamiento, mantener el borrado» y el borrado se ha
> revertido **por la misma razón que el reordenamiento**, no porque sea
> incorrecto.

---

## 2. Las dos revertidas enteras

### `H_0969` y `H_0970` — REVERTIDAS EN TERAS

No son de CM-004 y no tienen ninguna parte que conservar.

**`winner` no es un campo fiable en esta base.** De las 1280 manos, **214**
tienen un ganador que foldeó en algún momento. No son 214 errores aislados: es
el comportamiento normal del campo, porque el recorder lo escribe en un punto
que no siempre es el final de la mano.

Corregir el campo en **una** de esas 214 no dice nada de las otras 213, y en
el caso de `H_0970` empeora las cosas: el recorte quita al BB de un bote que
sí ganó (`H_0345` y `H_1050` graban las dos ciegas en el mismo patrón, y el
grabado tiene tres incluyendo al BTN que foldeó).

**Vuelven al valor grabado.** El defecto se documenta aquí en vez de
inventarse una corrección que no hay con qué sostener.

**Sobre el `BB f` de `H_0969`:** es imposible —un fold tras su propia
apuesta sin respuesta— y borrarlo es correcto. Pero venía en el mismo paquete
que el recorte de `winner`, y ese sí se sostiene solo en el campo no fiable.
Se ha revertido el paquete entero y el motivo queda escrito aquí.

---

## 3. Lo que este documento deja abierto, y como se cierra

Los cuatro defectos sistémicos que la evidencia ha destapado **no se corrigen
aquí**. Se registran con su recuento, que es lo que permite decidir.

| | recuento | qué haría falta |
|---|---:|---|
| subida a importe ≤ la ciega nominal | 45 | un script como el de CM-003, con `inferred: true`, sobre los 45 |
| acción de alguien que ya foldeó | 8 | borrar el check contradictorio; regla trivial, 8 casos |
| el BB no actúa tras la última subida | 652 | **no está claro que sea un defecto.** 652 de 1280 sugiere que el recorder no registra la respuesta del BB, no que haya un error. Instrumento primero |
| `winner` incoherente | 214 | probablemente el campo no sea utilizable. Decidir si se deja de consumirlo |

El tercero es el que cambia el tamaño del problema, y por eso se mide antes
de tocar nada.

---

## 4. Reversión

`hands_db.jsonl` está versionado y el estado final es **reproducible**:

```
python tools/aplicar_reinterpretacion.py            # dry-run
python tools/aplicar_reinterpretacion.py --apply
```

El script construye desde `e314f74` (verificado por sha256), aplica las dos
reglas y compara con el fichero actual antes de escribir. **No parte del
fichero actual**, que es justamente lo que hay que poder rehacer. Es
idempotente por construcción: aplicarlo dos veces da el mismo fichero.

| | SHA-256 de `hands_db.jsonl` |
|---|---|
| antes de la reinterpretación (`e314f74`) | `bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee` |
| estado intermedio, con las 26 a mano | `3b0574bda0d290b425d487d4a98b376991556a8a5324e5f77e637d9bd5b4859f` |
| **estado final, este documento** | `173a72743c7a54255452fb3fc4d8a9095adaddff29a54d84dda1d459bcc7fe8d` |