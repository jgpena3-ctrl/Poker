# CM-004 — reinterpretación de `hands_db.jsonl`

> **SUPERADO en parte.** Este documento describe el estado intermedio —26
> manos editadas a mano— que después se corrigió. **El estado final son 24
> manos**, y está en [`RECONSTRUCCIONES_CM004.md`](RECONSTRUCCIONES_CM004.md).
> Se conserva aquí porque el hallazgo del que salió —la regla exacta del
> motor, y que las 6 reconstrucciones eran(pattern)-inventadas— sigue en pie.
>
> | | este documento | estado final |
> |---|---|---|
> | manos editadas | 26 | **24** |
> | de ellas reetiquetadas | 17 | **23** |
> | de ellas reconstrucciones | 6 | **0** (revertidas) |
> | ajenas a CM-004 | 3 | **1** (`H_0350`) |
> | `H_0970` | pendiente | **revertido** |
> | sha256 | `3b0574bd…` | **`173a7274…`** |

**Estado del documento:** histórico. No describe el disco.
**Fecha:** 2026-10-14

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

> **Lo que la §3 destapó, y que sigue siendo lo que importa:** las 6
> reconstrucciones no fallaron por falta de evidencia. Fallaron por otro
> motivo que aquí no se había medido, y que `RECONSTRUCCIONES_CM004.md`
> cuantifica: **sus patrones se repiten 8, 45 y 652 veces**. Se había
> corregido una de cada grupo.

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
corregidas. Se comprueba en `test_la_regla_sigue_siendo_exacta_contra_la_version_previa`.

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

> **La versión de este bloque de la regla cogía 962 manos de 1280.** Estaba
> escrita en el script y contaba la ciega del BB en el índice 0 como «acción
> voluntaria previa». El motor la reconoce por `voluntary_before`, que ya la
> excluye. Menos mal que se preguntó al motor.

---

## 3. El manifiesto del estado intermedio: 26 = 17 + 6 + 3

> **Histórico.** De las 6 reconstructions, **0 sobreviven**. Las 17 + 6 de
> CM-004 son ahora 23 reetiquetados, porque en las 6 se conservó la parte de
> CM-004 y se revirtió el resto. Ver `RECONSTRUCCIONES_CM004.md`.

### 3.1 Reetiquetado — 17 manos

Solo cambia la etiqueta de la entrada del BB: `b` → `r`. Una regla, derivada
del motor, exacta sobre las 1280.

```
H_0031 H_0037 H_0078 H_0104 H_0107 H_0127 H_0147 H_0161 H_0170
H_0183 H_0210 H_0215 H_0248 H_0262 H_0279 H_0294 H_0722
```

### 3.2 Reconstrucción — 6 manos → **0, todas revertidas**

Aquí **no** bastaba con cambiar una etiqueta. Se añadía, se borraba o se
reordenaba alguna acción, o se cambiaba lo que hizo otro jugador.

| mano | qué se hacía además de `b`→`r` | instances del patrón | estado final |
|---|---|---:|---|
| `H_0039` | **añadía** `BB f 0.0` al final | 652 | revertido |
| `H_0051` | `SB r 0.5` → `c 1.0`, y **añadía** `SB f 0.0` | 45 | revertido |
| `H_0109` | `SB r 0.5` → `c 0.5` | 45 | revertido |
| `H_0143` | `CO r 1.0` → `c 1.0` | 45 | revertido |
| `H_0263` | **borraba** `MP x 0.0` y reordenaba | 8 | revertido |
| `H_0067` | partía una única llamada `SB c 1.5` en **dos** | — | revertido |

La columna de instancias es lo que faltaba medir en este bloque, y es lo que decide:
**corregir una de 652 deja la base unas veces bien y 651 mal.**

### 3.3 Ajeno a CM-004 — 3 manos → **1**

| mano | qué | estado final |
|---|---|---|
| `H_0350` | dos `players` con `cards="-"` → `""` | **mantenido** |
| `H_0969` | borra un `BB f` del turn; recorta `winner` | revertido |
| `H_0970` | recorta `winner` | revertido |

`H_0350` sobrevive por una razón que las otras dos no tienen: **el patrón se
aplica a todas sus apariciones**, 2 de 2. `'-'` no es un código de carta, son
las 2 únicas apariciones del centinela en las 1280 manos, y la cadena vacía se
usa 6085 veces. Normalizar un centinela no es reconstruir la carta, que es lo
que CM-002 prohíbe.

---

## 4. `H_0970`: estaba mal, y el arreglo era no tocarlo

> **Resuelto por reversión.** Vuelve a `winner: ["hero","p1","p4"]`.

Preflop: `BB b 1.0` (ciega), `BTN f`, `SB f`. Todos foldean hasta las ciegas.

- El defecto real es que **p4 (BTN) foldeó y figura como ganador**.
- El recorte aplicado dejaba `["hero"]`, que además **quitaba p1 (BB)**, que
  comparte el bote: **cambia un error por otro**.
- Lo que hace el campo `winner` no es Util: es **incoherente en 214 de las
  1280 manos**.

Corregir el campo en una de esas 214 no dice nada de las otras 213. Vuelve al
valor grabado y el defecto se documenta en `RECONSTRUCCIONES_CM004.md` §2.

Las dos manos están en las líneas **967 y 968**, fuera del corte de 900: nunca
entraron en ninguna cifra publicada.

---

## 5. Qué NO se ha hecho, y por qué

### 5.1 Las 23 siguen excluidas de la ventana de calibración

Que el defecto esté resuelto **no** las devuelve a la ventana. El motivo
escrito en `motor/learn.py` ya no se cumple en ninguna de las 23, y el motivo
vigente —que el sustituto tampoco tiene original— sigue sin estar escrito.
Mover la ventana de 877 a 900 invalidaría todas las cifras de
`CONTRATO_F72A.md` y `RESUMEN_SECCION.md`. Ver `DECISION_CM004.md` §0.

### 5.2 Los derivados

Estaban obsoletos. **Ya no:** ver [`REGENERACION_DERIVADOS.md`](REGENERACION_DERIVADOS.md).

### 5.3 Ninguna corrección es «observada»

No se ha añadido `"inferred": true` a ninguna entrada. Las 24 que quedan son
**relabels**: cambian una etiqueta `b` por `r` en una posición que el motor ya
sabía identificar por su importe y su orden. No inventan una acción ni un
resultado, solo nombran lo que el motor ya leía. El detalle está en
`RECONSTRUCCIONES_CM004.md`.

---

## 6. Cómo se verifica

```
python tools/aplicar_reinterpretacion.py   # dry-run: qué haría, y qué deja fuera
python tools/verificar_cm004.py            # manifiesto, no escribe
python -m pytest motor/test_cm004.py -q    # 19 guards
```

Cuatro preguntas, y las cuatro se responden contra el **motor**:

1. **Invariante.** ¿Alguna de las 1280 tiene una `BB b` que no pueda ser la
   ciega? **0.**
2. **Clasificación.** Para cada mano editada frente a `e314f74`: ¿reetiquetado
   o reconstrucción? **23 / 0 / 1.**
3. **Exactitud.** La regla aplicada a `e314f74` selecciona exactamente las 23
   corregidas.
4. **Colados.** Toda edición que no sea un reetiquetado tiene que estar
   **declarada**. Una cuarta sin declarar es un **fallo**.

El verificador se ancla a `e314f74`, **no a HEAD**: en cuanto la
reinterpretación está commiteada, HEAD contiene la base ya corregida, la
regla derivaría 0 y el script pasaría sin comprobar nada. Y hay cinco tests
que lo demuestran mutando el fichero y exigiendo que los vea, porque HEAD ya
tiene el estado correcto.

---

## 7. Reversión

| | SHA-256 de `hands_db.jsonl` |
|---|---|
| antes de este bloque (`e314f74`) | `bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee` |
| estado intermedio, las 26 a mano | `3b0574bda0d290b425d487d4a98b376991556a8a5324e5f77e637d9bd5b4859f` |
| **estado final** | `173a72743c7a54255452fb3fc4d8a9095adaddff29a54d84dda1d459bcc7fe8d` |

El estado final **se puede rehacer**: `python tools/aplicar_reinterpretacion.py --apply`.
Construye desde `e314f74`, no desde el fichero actual.