# Hallazgos en el rango H_0001..H_1014

**Rango auditado:** `H_0001`..`H_1014` — **991 manos** de las 1258 que quedan
en `data/hands_db.jsonl`.
**Instrumento:** `tools/auditar_rango.py`. **No escribe nada.**
**Fecha:** 2026-10-14

```
python tools/auditar_rango.py --validar              # autocomprobación
python tools/auditar_rango.py --hasta H_1014         # el informe
python tools/auditar_rango.py --hasta H_1014 --json salida.json
```

---

## 0. Lo primero: el instrumento se autocomprueba

`auditar_rango.py --validar` corre los detectores contra `e314f74` (1280 manos)
y comprueba que dan las cifras que este proyecto ya publicó:

| clase | detecta | publicado | veredicto |
|---|---:|---:|---|
| `SIN_RESPUESTA_BB` | 652 | 652 | **reproduce** |
| `WINNER_FOLDEO` | 214 | 214 | **reproduce** |
| `IMPORTE_SUBIDA` | 39 | 45 | **NO SE REPRODUCE** |
| `ACCION_DESPUES_FOLD` | 6 | 8 | **NO SE REPRODUCE** |

Las dos que no reproducen se publicaron desde scripts de un solo uso que no
se versionaron. **No significa que el detector esté mal: significa que la
cifra no tiene a quién preguntarle.** Las cifras de este informe salen del
script, no de documentos anteriores.

> Esto ya pasó una vez en este proyecto y salió caro: tres scripts
> distintos dieron tres cifras para la misma pregunta. El número no era el
> problema. El problema era que no había ningún código del que decir «esto es
> lo quecuento».

---

## 1. Resumen

| clase | casos | naturaleza |
|---|---:|---|
| `CM-004` — `BB b` que el motor no reconoce como ciega | **0** | formato |
| `CM-002` — centinela de carta inválido | **0** | formato |
| `CARTAS_ILEGALES` | 2 | formato |
| `BOARD_ILLEGAL` | 5 | formato |
| `IMPORTE_SUBIDA` | 36 | formato |
| `ACCION_DESPUES_FOLD` | 5 | contradicción |
| `FOLD_TRAS_APUESTA` | 0 | contradicción |
| `ACCION_FANTASMA` | 16 | contradicción |
| `POSICION_DUPLICADA` | 2 | contradicción |
| `WINNER_FOLDEO` | 11 | contradicción |
| `SHOWDOWN_SIN_WINNER` | 15 | contradicción |
| `WINNER_VACIO` | 1 | contradicción |
| `SIN_ALLIN` | 73 | ausencia |
| `SIN_RESPUESTA_BB` (regla estructural) | 486 | ausencia |
| └ **→ de las cuales, candidatas reales** | **5** | |
| └ → falsos positivos | 481 | |

**Lo bueno primero:** CM-004 y CM-002 están a **0**. La ventana que se declara
fiable no tiene ni una entrada `BB b` mal ordenada ni un centinela de carta.
Eso es lo que se buscaba al fijar el rango.

**Lo que hay que mirar:** 36 subidas imposibles, 16 acciones de posiciones que
no estaban en la mesa, y un `winner` que no es fiable.

---

## 2. La corrección grande: el «defecto de 652»

La cifra de 652 se publicó como *«el BB tiene entrada y no vuelve a actuar»*.
**Eso no es lo que mide la regla que la produce.** La regla es:

> el preflop se cierra con una subida (`r`) de alguien que no es el BB

Y eso ocurre en la mitad de la base **porque es una situación normal**. Lo que
falta es mirar si el BB respondió después.

| | e314f74 (1280) | H_0001..H_1014 (991) |
|---|---:|---:|
| la regla estructural se cumple | 652 | 486 |
| ├ el BB **responde** (call, fold o check) | 613 | 471 |
| ├ el BB **ya estaba foldeado** antes de la subida | 16 | 10 |
| ├ **el BB no actúa tras la subida** | **22** | **4** |
| └ **el BB no tiene ninguna entrada preflop** | **1** | **1** |
| **SUBTOTAL REAL** | **23** | **5** |
| **falsos positivos** | **629** | **481** |

**El 652 era 629 falsos positivos.** En el rango que se declara fiable, la
candidata a dato faltante es **1 de cada 198 manos, no 1 de cada 2**.

### 2.1 Los cinco, para revisión manual

Están en `DOCS/DEFECTO_652.md` con el preflop entero. Resumen:

| id | preflop | veredicto |
|---|---|---|
| `H_0399` | `BB b1.0 · MP f · CO f · BTN r2.5 · SB f` | **falta la acción del BB** |
| `H_0404` | `BB b1.0 · MP f · CO f · BTN r3.0 · SB f` | **falta la acción del BB** |
| `H_0633` | `BB b1.0 · UTG r2.5 · MP f · CO f · BTN f · SB f` | **falta la acción del BB** |
| `H_0196` | `UTG r17.0 · MP f · CO f · BTN f · SB f0.5` | **el BB no aparece** |
| `H_0883` | `BB b1.0 · UTG c1.0 · MP f · CO f · BTN f · SB c1.0 · BB r7.0 · UTG f · SB r7.0` | **no falta**: el `SB r7.0` no supera el `BB r7.0`. Es `IMPORTE_SUBIDA` |

**Cuatro son un hueco de grabación y uno es otro defecto.** En ninguno de los
cinco hay problema de poker: el BB tenía que actuar y no hay entrada suya.

### 2.2 Contraejemplos, para contrastar

Estas **también** cumplen la regla estructural y **no les falta nada**:

| id | preflop | por qué está descartada |
|---|---|---|
| `H_0006` | `UTG b1.0 · MP r4.0 · CO f · BTN c4.0 · SB f · **BB f** · UTG c4.0` | el BB foldeó |
| `H_0014` | `UTG f · MP f · CO b1.0 · BTN r4.0 · **BB c3.0** · CO c4.0` | el BB llamó (con un importe imposible, que es otro defecto) |
| `H_0020` | `UTG c1.0 · MP f · CO c1.0 · BTN r4.0 · **BB c4.0** · UTG f · CO c4.0` | el BB llamó correctamente |

---

## 3. Las demás clases, con sus identificadores

### 3.1 `IMPORTE_SUBIDA` — 36

Una subida que no supera la apuesta viva. Casi todas son `r 1.0` siendo la
primera acción voluntaria, o `r 0.5` por debajo de la ciega.

```
H_0044, H_0049, H_0076, H_0097, H_0104, H_0105, H_0107, H_0108, H_0117, H_0131
H_0139, H_0147, H_0148, H_0151, H_0159, H_0161, H_0163, H_0164, H_0167, H_0168
H_0169, H_0170, H_0171, H_0173, H_0175, H_0177, H_0185, H_0197, H_0207, H_0214
H_0215, H_0249, H_0327, H_0335, H_0369, H_0736
```

> La cifra publicada para esta clase era **45** y no se reproduce: el
> detector permanente da **36**. El 45 salió de un script que no se ha
> versionado. Ver `DEFECTO_45.md`.

### 3.2 `ACCION_FANTASMA` — 16

Una posición actúa y no está en `players[]` entre los activos. Suele ser una
posición que el recorder dejó vacía (`pos: ""`) y luego sí emitió acción.

```
H_0016, H_0022, H_0061, H_0143, H_0198, H_0209, H_0240, H_0519, H_0564, H_0718
H_0748, H_0822, H_0827, H_0846, H_0968, H_0978
```

### 3.3 `SHOWDOWN_SIN_WINNER` — 15

`showdown` nombra a una posición que no está en `winner`.

```
H_0374, H_0376, H_0409, H_0447, H_0511, H_0744, H_0751, H_0759, H_0786, H_0833
H_0911, H_0915, H_0932, H_0957, H_0972
```

### 3.4 `WINNER_FOLDEO` — 11

`winner` incluye a alguien que foldeó en algún momento.

```
H_0028, H_0505, H_0602, H_0748, H_0864, H_0879, H_0881, H_0882, H_0893, H_0895, H_0983
```

### 3.5 `ACCION_DESPUES_FOLD` — 5

Una posición actúa después de haber foldeado. **Todas preflop.**

```
H_0054, H_0103, H_0180, H_0236, H_0330
```

> La cifra publicada era **8**; el detector da **5**. Mismo motivo que en
> `IMPORTE_SUBIDA`.

### 3.6 `BOARD_ILLEGAL` — 5

Board con carta repetida, no válida, o compartida con un jugador.

```
H_0093, H_0297, H_0582, H_0835, H_0915
```

### 3.7 `CARTAS_ILEGALES` — 2

Una misma carta en dos jugadores.

```
H_0581, H_0711
```

### 3.8 `POSICION_DUPLICADA` — 2

Dos jugadores activos con la misma posición.

```
H_0029, H_0748
```

### 3.9 `WINNER_VACIO` — 1

```
H_0086
```

### 3.10 `SIN_ALLIN` — 73

El campo `allin` falta. Son **exactamente `H_0001`..`H_0073`**, las primeras
73 manos de la base: el recorder antiguo no lo escribía. No es un defecto
disperso, es un bloque, y ya se conoce. Ver `CONTRATO_F72A.md` §2.

```
H_0001 .. H_0073   (73 consecutivas)
```

---

## 5. El estado del fichero de datos, y por qué hay 5 tests en rojo lógico

`hands_db.jsonl` se ha editado **a mano** por encima del commit `02fc641`, y
`tools/verificar_cm004.py` lo dice:

| | |
|---|---|
| las 8 correcciones revertidas en `02fc641` | **vuelven a estar aplicadas** — `H_0039`, `H_0051`, `H_0067`, `H_0109`, `H_0143`, `H_0263`, `H_0969`, `H_0970` |
| manos cambiadas sin declarar | **68** |
| manos **borradas** de la base | **22** |
| manos totales | 1258 (antes 1280) |

`revision_1` dice, literalmente:

> «No toques `hands_db.jsonl` a mano otra vez. Si hay que cambiarlo, se cambia
> con `aplicar_reinterpretacion.py` o con un script versionado. **El canal
> manual está cerrado.**»

Los cinco tests marcados en `motor/test_cm004.py` fallan por eso, y llevan
`xfail(strict=True)` con el motivo escrito:

- **No están para taparlos.** Están diciendo la verdad sobre el fichero.
- `strict=True` significa que, si alguien deja la base en su estado
  reproducible, **pasarán** y el xfail se convierte en fallo. Eso obliga a
  quitar la marca, que es lo que hay que hacer cuando se cierre la decisión.

Suite: **686 verdes, 5 xfail, 1 skipped.**

### Qué haría falta para cerrarlo

Ninguna de las tres vías es «volver a editar a mano»:

1. **Un script versionado** que aplique el cambio con motivo, y sus hashes.
2. **Declarar el rango** en el código (`RELIABLE_HANDS`), con las cifras
   recalculadas. Ahora mismo `learn.RELIABLE_HANDS` sigue en **900** y
   `EXCLUSIONES_VENTANA_FABLE` sigue con las 23 de CM-004: el rango que se
   ha declarado fiable **no está en el motor**, y las cifras publicadas
   siguen calculándose sobre la ventana de 877.
3. **Decidir las 68** una a una, o revertirlas.

Lo segundo es lo urgente, y es una decisión de quien mantiene la base.

---

## 6. Lo que este informe NO dice

- **No dice que el rango sea fiable.** Dice qué se incumple en 991 manos.
- **No corrige nada.** Ningún fichero de datos se ha tocado.
- **No cierra nada.** Las cifras de F7.2 y la ventana de 877 siguen como
  estaban, y siguen sin visar porque el rango declarado ha cambiado y nadie
  ha recalculado.