# AUDITORÍA DEL ORIGEN — posiciones, semántica de importes y botes

**Estado:** informe. No modifica nada.
**Base auditada:** `33ab8ee`, sha `35727961646dfaba`, 1258 manos.
**Instrumento:** `tools/auditar_origen.py` (solo lectura, con `--validar`).
**Pruebas:** `motor/test_auditar_origen.py`.
**Código del grabador citado:** `recorder/record_hand.py`, `tools/lector_estado.py`.

> **La base no se ha tocado.** El intento de declarar las ciegas se revirtió y
> el estado se conserva mientras se investigan las inconsistencias. Backup del
> intento revertido, verificado por SHA-256, en
> `data/_backup_aplicar_correcciones/antes_ciegas_35727961646dfaba.jsonl`.

---

## 0. Resumen para decidir

| pregunta | respuesta | confianza |
|---|---|---|
| ¿qué significa `amount`? | **la caja de apuesta del jugador en esa calle**, es decir su contribución acumulada en la calle | **alta** — está en el código, no deducido |
| ¿hay mezcla de convenciones? | **no, según el grabador**. Hay una sola regla y 26 casos que la incumplen | alta |
| ¿por qué el BB graba distinto? | **el BB graba `viva − 1.0` en 47 de 53 pares**. Causa no determinable con los datos | media |
| ¿las ciegas se pueden declarar? | **la del BB sí** (921/921 en el índice 0, importe 1.0). **La del SB no**: no hay dato que la respalde | alta |
| ¿por qué? | el grabador solo captura una ciega si la caja **ya tiene importe en el primer fotograma** | alta — `record_hand.py:202` |
| ¿el bote cuadra? | **69 de 1258** (5.5%). Y en 592 el bote declarado es **mayor** que lo aportado | alta |
| ¿es por el rake del 5%? | **no**: sin rake cuadran 69, con rake 29. El rake **empeora** el cuadre | alta |
| ¿es por los all-in? | **no**: con all-in cuadran 4.0%, sin all-in 7.7% | alta |
| ¿mesas cortas, ante o straddle? | **no hay ninguno**: las 1258 manos son de 6 jugadores | alta |
| ¿ayudaría declarar las ciegas? | **sí, en el bote**: la reconciliación pasa de 69 a **190** | alta |
| ¿qué es lo que más pesa? | **592 botes imposibles**, y un **agujero de esquema** que hace `winner` y `allin` irresolubles | alta |

> **Corrección de una versión anterior de este mismo informe.** Las cifras de
> la sección 3 estaban calculadas sumando los importes de las acciones, que es
> la lectura **delta**. Con la lectura del grabador —acumulado— la suma no vale:
> el BB de `H_0546` pasa por 1.0, 11.0 y 40.3, que son tres lecturas de la
> **misma** caja, y sumarlas las cuenta tres veces. El error era exactamente el
> que este informe denuncia, y lo encontró el test que exige que `H_0006` dé
> 92.6 y no 107.6. Las cifras de abajo son las de la lectura correcta.

---

## 1. POSICIONES Y CIEGAS

### 1.1 Inventario de las 1258 manos

| | manos |
|---|---|
| total | **1258** |
| con `pos: BB` | **1258** |
| sin `pos: BB` | 0 |
| con `pos: SB` | 1229 |
| sin `pos: SB` | **29** |
| ciega del BB declarada (posting) | **921** |
| BB sin posting declarado | **337** |
| SB sin posting declarado | **1198** |
| con algún jugador sin `pos` | **567** |
| con `pos` duplicada | **0** |

Reparto de posiciones vacías: 691 manos con 0 · 390 con 1 · 143 con 2 · 29 con
3 · 5 con 4. **783 jugadores** sin posición en total.

### 1.2 Estructura de mesa

| | |
|---|---|
| jugadores por mano | **6 en las 1258** |
| stack mínimo / mediana / máximo | 0.0 / 95.9 / **7588.0** |
| primera acción de preflop | `BB b` 921 · `UTG f` 190 · `UTG b` 60 · `UTG c` 34 · `UTG r` 19 · resto 34 |

**No hay mesa corta, ni ante, ni straddle.** La prueba de ante y straddle sería
una betting box de una posición distinta de SB/BB antes de que nadie actúe, y
la primera acción de preflop es `BB b` en 921 manos y una acción de UTG/MP/CO/BTN
en las otras 337 — es decir, el BB no posteó en el índice 0, no que haya un ante.

El stack de 7588.0 sí es un outlier que merece mirada aparte: 4 órdenes de
magnitud por encima de la mediana. No se ha diagnosticado aquí.

### 1.3 Qué campo y qué secuencia verifican un posting

Es la pregunta del encargo, y la respuesta es corta:

> **Campo:** la acción `b` de esa posición.
> **Secuencia:** en el PREFLOP **y antes de que haya dinero de nadie en el bote**.

`tools/auditar_origen.py::es_posting` implementa exactamente eso, y se apoya en
la secuencia, no en el importe: si antes de la `b` ya hay una `b` o una `r` de
otro, entonces hay algo que wager y la `BB b` es una salida, no un posting.

**Y tiene un límite, que se encontró al escribir el test que lo contrasta:**
`es_posting` no puede distinguir una ciega de una **apertura grabada como `b`**.
El grabador escribe `b` a quien abre —`record_hand.py:246`, `'b' if not
street_has_bet else 'c'`—, así que `H_0032` tiene `SB b 5.0` en la racha inicial
y eso es una apertura a 5.0, no una ciega. Por eso el filtro de importe se
aplica **solo al BB**, cuya `b` en el índice 0 sí es inequívocamente ciega.

Dos cosas que **no** verifican un posting, y que conviene no confundir:

- **La posición.** El BB sale `b` muchas veces, y solo 921 de esas son
  ciegas. La posición no dice nada.
- **El importe.** `auditar_rango._es_ciega_bb` ya avisa de una cosa: usa `voluntary_before`
  y no el importe. Correcto, y el motivo está escrito en `motor/learn.py`.

Y un dato de esquema que cambia lo que se puede exigir: **no hay `blind: true` en
ninguna de las 13826 acciones**. `learn._preflop_sequence` lo lee
(`a.get('blind') or a.get('is_blind')`), pero el grabador nunca lo escribe. El
marcador existe en el motor y no en los datos.

### 1.4 Las 29 manos sin `pos: SB`

La causa es una, y es coherente:

> **En las 29, todos los jugadores sin posición están marcados `active: false`.**

Ejemplos: son `NESANVAR`, `mur420`, `Freddy9212`, `P4`, `P5`, `Capitan spiff`,
`SunGodNika` — nombres que aparecen una y otra vez, y que en otras manos sí
tienen posición.

Y el dato que cierra el círculo:

> **Los 783 jugadores sin `pos` no tienen NINGUNA acción.** Medido: 0 con
> acciones, 783 sin.

Es decir: `pos` vacía significa «este jugador nourge$ó$ó$ está en la mano». No es
corrupción de la etiqueta, es que el grabador no asigna posición a quien ya no
juega. **Por lo tanto `pos` vacía no produce acciones fantasma**, y las dos manos
que `accion_fantasma` marca (`H_0519`, `H_0846`) son **otra cosa**, más pequeñas
y más graves.

| mano | posiciones | sin posición | inactivos |
|---|---|---|---|
| `H_0035` | UTG, CO, **—**, BTN, **—**, BB | NESANVAR, mur420 | NESANVAR |
| `H_0057` | **—**, UTG, CO, BTN, **—**, BB | Juanmabm, mur420 | mur420 |
| `H_0282` | BTN, **—**, BB, UTG, **—**, CO | P1, triki12 | P1 |
| `H_0511` | BB, CO, **—**, BTN, **—**, **—** | Franco1603, p4, p5 | los tres |
| `H_0590` | BB, **—**, **—**, BTN, **—**, **—** | 4 jugadores | los cuatro |

`H_0035` es el caso interesante: el preflop empieza con `UTG c 1.0`. Esa call solo
tiene sentido si había una ciega grande de 1.0 en el bote. **La ciega estaba y no
se grabó.** Eso no es «el SB no posteó», es «el grabador no vio la caja del BB a
tiempo».

### 1.5 Las dos lecturas del patrón SB/BB

La diferencia exacta entre la call del SB y la del BB, en las 53 manos donde
ambos igualan:

| diferencia `SB c − BB c` | pares | qué se cumple, exactamente |
|---|---|---|
| **+1.0** | **44** | `BB c == viva − 1.0` (44/44) y `SB c == viva` (44/44) |
| +0.5 | 4 | 3 de 4: `BB c == viva − 1.0`; 3 de 4: `SB c == viva − 0.5` |
| 0.0 | 4 | `BB c == viva` (4/4) y `SB c == viva` (4/4) |
| −8.0 | 1 | `H_0104`: `BB c == viva`, `SB c == 1.0` |

El patrón mayoritario es `viva − 1.0` en **44 de 44**, sin una sola excepción. No
es un descuido de la caja.

**Y esto no se puede atribuir a una posición mal puesta.** Las cuatro hipótesis
que encajan, y ninguna se puede elegir con los datos:

| hipótesis | qué predice | por qué no se decide aquí |
|---|---|---|
| **H1 · el ROI del BB cubre otro elemento** | el grabador lee el «to call» del BB, no su caja | `tools/lector_estado.py:798-814` lee un ROI por jugador, sin documentar cuál es cuál. Habría que mirarlo en una captura. |
| **H2 · la SB no posteó de verdad** | la SB no tiene nada puesto, y su «to call» es la viva entera | exige mirar si el BB guía de esa mano tenía la SB en la mesa |
| **H3 · el BB sí posteó y la SB no** | la SB se fue y el BB no; es un heads-up | contradice que `players[]` tenga 6 jugadores activos |
| **H4 · la caja del BB está leída de otra región** | dos ROIs solapados | se decide con una imagen, no con un aggregate |

> **No se acepta ninguna por «mejorar la métrica».** La anterior hipótesis
> —«la mezcla es la ciega ausente»— mejoraba el agregado CHIPS/TOTAL y quedó
> **falsada** al declararlas: las 921 manos que ya estaban bien bajaron de
> **86.6% a 41.8%**. Se anota precisamente por eso.

---

## 2. SEMÁNTICA Y NORMALIZACIÓN DE LOS IMPORTES

### 2.1 Dónde se registra, se interpreta y se serializa

```
tools/lector_estado.py:798-814   OCR del ROI de cada jugador -> state[p_bet]
record_hand.py:200               bet = state.get(f'{pid}_bet')        # inicio
record_hand.py:209               'amount': bet                        # ciegas iniciales
record_hand.py:248               'amount': new_bet                    # b / c
record_hand.py:251               'amount': new_bet                    # r
record_hand.py:273/278/284       bet = state.get(f'{pid}_bet'); 'amount': bet
```

**`amount` es el valor de la caja de apuesta del jugador en esa calle.**

| lectura | ¿es la del grabador? |
|---|---|
| cantidad **añadida** (delta) | no |
| **contribución acumulada** en la calle | **sí** |
| tamaño **objetivo** de la apuesta | no |

La docstring de `tools/auditar_rango.py` decía bien esto desde el principio:
*«`amount` es el importe TOTAL puesto por esa accion, no un delta»*. Lo que
fallaba era la implementación de `importe_subida`, que exige
`amount > learn.BB` (un suelo **nominal absoluto**) sobre un campo que es
acumulado.

### 2.2 Por qué la contribución acumulada, y no la otra

Una caja de apuesta acumula. Y la serie que produce esa lectura tiene que ser
**monótona**: el acumulado de un jugador no puede bajar. Medido sobre las
13 826 acciones:

| acción | ok | **no monótona** |
|---|---|---|
| preflop `b` / `r` | 1124 / 856 | **0 / 0** |
| preflop `c` | 1718 | **12** |
| flop `c` · turn `c` · river `c` | 393 · 303 · 118 | **7 / 2 / 5** |
| todas las demás | — | 0 |

**6354 de 6380, 99.6%.** Ninguna `b` ni ninguna `r` rompe la monotonía, en
ninguna calle. Eso es exactamente lo que se espera de un campo acumulado, y
**no lo esperaría** de un campo delta.

### 2.3 Qué se representa en cada tipo de acción

| | cómo se graba | qué es |
|---|---|---|
| **ciega inicial** | `b` (la primera) o `c` (las siguientes), `record_hand.py:206-209` | la caja en el primer fotograma |
| **`b`** | `:246` si `old_bet is None` y no había apuesta; `:273` por estado | acumulado en la calle |
| **`c`** | `:246` o `:284` | acumulado en la calle |
| **`r`** | `:251` | acumulado en la calle |
| **all-in** | no tiene código propio | es una `r` que iguala el stack: se detecta por `allin`, no por la acción |
| **call de check** | **`'pasar': 'c'`**, `:218` | **un check se graba como call** |
| **postflop** | igual que preflop, pero `puesto` se reinicia por calle | acumulado **en esa calle**, no en la mano |

El caso del check es un defecto del grabador, no una convención: un check
registrado como `c 0.0` hace que el acumulado del jugador **baje a cero**, y de
ahí salen 9 de las 26 no-monotonías:

```
H_0008 turn[2]  BB c 0.0   (antes tenía 38.8)   [BB b 38.8, CO f, BB c 0]
H_0056 river[2] BB c 0.0   (antes tenía 2.3)    [BB b 2.3, BTN c 2.3, BB c 0]
H_0091 river[2] MP c 0.0   (antes tenía 22.6)   [MP b 22.6, CO f, MP c 0]
```

Y un caso de **orden** corrupto, que no es lo mismo que un importe:

```
H_0026 preflop  [MP r 6.0, CO b 1.0, BTN f, SB c 1.0, SB c 5.0, BB x 0]
```

El SB iguala 1.0 y después 5.0, cuando la viva era 6.0. Dos llamadas del mismo
jugador, en orden invertido.

### 2.4 Propuesta de transformación reversible

**No se implementa. Se demuestra y se propone**, como pide el encargo.

El objetivo: poder reconstruir, desde `amount`, las tres cosas que hoy están
mezcladas —aportado, acumulado y objetivo— sin perder el dato original.

**Regla 0 — no tocar `amount`.** Es el campo que el grabador escribió y el único
que tiene un significado documentado. Cualquier normalización va en campos
nuevos, y se puede tirar sin perder nada.

**Regla 1 — `aportado` (lo que sale del bolsillo en esa acción).** Requiere saber
el acumulado anterior del mismo jugador en esa calle:

```
aportado(i) = amount(i) − acumulado_anterior(pos, calle)
acumulado_anterior = 0 si es su primera acción con importe en la calle
```

Es invertible: `acumulado(i) = acumulado_anterior + aportado(i)`.

**Regla 2 — `objetivo` (el tamaño al que se sube la apuesta viva).** Para `b` y
`r` es `acumulado(i)`. Para `c` es la viva antes de la acción.

**Regla 3 — `es_posting`.** `pos ∈ {SB, BB}` ∧ `action == 'b'` ∧ no hay importe
de nadie antes en el preflop. **Nunca se decide por el importe**: hay `BB b` de
0.5 (6 manos) y de 1.0 (915), y ninguna de las dos es posting por su cifra.

**Regla 4 — la normalización del BB se aplica SOLO si se confirma H1.** Si el
ROI del BB cubre el «to call», entonces `amount` del BB es
`objetivo − su posting`, y el `objetivo` se reconstruye sumando el posting. Si
no se confirma, **no se toca**, porque aplicarla sin saberlo sería inventar.

#### Demostración sobre manos reales

`H_0001` — preflop `UTG b 2.5 · MP c 2.5 · CO f · BTN c 2.5 · SB c 2.5 · BB c 1.5`

| i | acción | amount | acumulado antes | **aportado** | **objetivo** |
|---|---|---|---|---|---|
| 0 | `UTG b` | 2.5 | 0.0 | **2.5** | 2.5 |
| 1 | `MP c` | 2.5 | 0.0 | **2.5** | 2.5 |
| 3 | `BTN c` | 2.5 | 0.0 | **2.5** | 2.5 |
| 4 | `SB c` | 2.5 | 0.0 | **2.5** | 2.5 |
| 5 | `BB c` | 1.5 | **0.0** ← *no* 1.0 | **1.5** | 1.5 |

La última fila es **el caso que decide la normalización**: el acumulado anterior
del BB **no aparece en el dato**, porque su posting no se grabó (ver §2.5). Con
`acumulado_anterior = 0` el `BB c` aporta 1.5, que es menos que la viva de 2.5: la
mano no cuadra. Si se sabe que el BB posteó 1.0, el aportado pasa a **0.5** y la
viva sigue sin cuadrar, porque haría falta 1.5. **Ninguna de las dos
normalizaciones cierra esta mano**, y por eso hace falta la grabación.

`H_0085` — subidas sucesivas: `UTG b 2.5 · MP f · CO r 9.0 · BTN f · SB f · BB f ·
UTG r 22.0 · CO c 22.0`

| i | acción | amount | acumulado antes | aportado | objetivo |
|---|---|---|---|---|---|
| 0 | `UTG b` | 2.5 | 0.0 | 2.5 | 2.5 |
| 2 | `CO r` | 9.0 | 0.0 | 9.0 | 9.0 |
| 6 | `UTG r` | 22.0 | **2.5** | **19.5** | 22.0 |
| 7 | `CO c` | 22.0 | **9.0** | **13.0** | 22.0 |

El juego: UTG pone 2.5, CO sube a 9.0, UTG sube a 22.0 (pone **19.5** más), CO
iguala (pone **13.0** más). Con lectura delta sería 22.0 + 22.0. **La lectura
acumulada es la que hace que estas cuatro acciones sumen 44.0, que es el bote
bruto correcto.**

### 2.5 Por qué la ciega del SB no se puede declarar

El grabador captura las ciegas iniciales así:

```python
for pid in PLAYER_IDS:
    bet = state.get(f'{pid}_bet')
    if bet is not None and bet > 0 and pos:      # ← el filtro
        initial_bets.append(...)
```

Y luego emite `b` para la primera y `c` para las demás (`:206-209`).

Consecuencias, y las tres se ven en los datos:

1. **Si la caja del BB está vacía en el primer fotograma, su ciega no se
   registra nunca.** De ahí las 337 manos sin `BB b`.
2. **La primera ciega que se ve se graba como `b` y las demás como `c`.** En las
   921 manos con posting, la `b` del índice 0 es la primera que el grabador vio —
   y siempre es del BB, lo que encaja con que el SB suele llegar más tarde.
3. **De la SB no hay ni un solo dato.** En las 1258.

Las 921 `BB b` del índice 0 valen 1.0 en 915 y 0.5 en 6. El 0.5 del BB es
anómalo y no se toca: se declara, no se normaliza.

**Y las 31 manos donde `es_posting(SB)` da True son las que hay que mirar
primero**, porque son las únicas donde una `SB b` está en posición de posting y
por tanto podría ser una SB perdida y recuperable.

---

## 3. INTEGRIDAD DE CONTRIBUCIONES Y BOTES

### 3.1 Qué significa «92.6 en H_0546» y cómo se calcula

**H_0546**, tal cual está en la base:

```
preflop: BB b 1.0 · UTG f · MP f · CO f · BTN r 3.0 · SB f · BB r 11.0 · BTN r 52.3 · BB c 40.3
stacks :  BB 100.0 · UTG 109.2 · MP 45.5 · CO 162.0 · BTN 52.3 · SB 69.5
allin  :  ['p1']        winner: ['p3']        final_pot: 0.5
```

**Lo que significa 92.6, exactamente:** es lo que aporta cada caja al cierre de
la calle, es decir el **último** valor de cada una:

```
BB  40.3   (su caja pasó por 1.0, 11.0 y 40.3; el ultimo es 40.3)
BTN 52.3   (su caja pasó por 3.0 y 52.3; el ultimo es 52.3, que es su stack)
                                     --------
                                     92.6
```

Los `BB b 1.0` y el `BB r 11.0` **no se suman**: son lecturas anteriores de la
**misma** caja. Sumarlos daría 107.6, y sería contabilidad delta.

**Lo que debería ser el bote:** el BTN tiene stack **52.3** y su `r` es de
**52.3**: se ha ido **todas** las fichas. El BB iguala con 40.3. Bote real
≈ **92.6**, más lo que se devuelve al perdedor, menos la rake.

**Lo que dice la base:** `final_pot = 0.5`. Esa cifra **no aparece en ninguna
parte de la mano**. No es la rake, no es el bote lateral, no es una devolución:
es un valor que no se puede reconstruir desde los datos.

### 3.2 Reconciliación de las 1258

Suma de las contribuciones **acumuladas** (último valor de cada caja, por
jugador y calle):

| | manos |
|---|---|
| el bote **exacto** | **69** (5.5%) |
| sobra lo aportado (el bote es menor) | 597 |
| **falta lo aportado** (el bote es **mayor**) | **592** |
| ratio (aportado − bote)/aportado | mín **−1.500** · mediana **0.000** · máx **+0.995** |

Ningún modelo de rake lo explica:

| modelo | cuadran |
|---|---|
| sin rake | **69** |
| rake 5% hasta 2.5BB | **29** |
| rake 5% hasta 2.5BB **+ ciegas declaradas** | 29 |

Y hay un dato que va en la dirección contraria y por eso importa: **declarar
las ciegas sube la reconciliación de 69 a 190**. No la arregla —121 de 1258— pero
es la única palanca que hasta ahora mueve el número, y apunta a que las 592
imposibles tienen que ver con posting perdido más que con el rake.

Dos cifras que se repiten y que son pistas, no conclusiones:

- **224** manos tienen una diferencia de **exactamente 0.5** entre lo aportado y
  el bote. 0.5 es la ciega pequeña, y la ciega pequeña no aparece en ninguna
  acción (§2.5).
- **24** manos aportan **0.0** y aun así tienen bote positivo. Ahí se perdió la
  totalidad de la captura.

### 3.3 Las tres muestras

**Válidas** (dif 0, 69 casos) — casi todas manos cortas, preflop, sin all-in:

| mano | aportado | bote |
|---|---|---|
| `H_0065` | 2.5 | 2.5 |
| `H_0083` | 10.0 | 10.0 |
| `H_0115` | 2.5 | 2.5 |

**Imposibles** — el bote declarado supera lo aportado, y estas son las mayores:

| mano | aportado | bote | **sobran** |
|---|---|---|---|
| `H_0601` | 141.6 | 176.6 | **35.0** |
| `H_0074` | 47.2 | 75.4 | **28.2** |
| `H_0321` | 81.3 | 109.0 | **27.7** |
| `H_0974` | 123.0 | 150.6 | **27.6** |
| `H_0885` | 100.4 | 123.7 | **23.3** |

Un bote 35 fichas mayor que lo aportado es imposible bajo cualquier lectura: o
faltan acciones, o `final_pot` es de otra mano.

**Extremas** — aportes cero:

| mano | aportado | bote |
|---|---|---|
| `H_0017` | **0.0** | 1.0 |
| `H_0048` | **0.0** | 1.0 |
| `H_0059` | **0.0** | 2.5 |
| `H_0060` | **0.0** | 1.0 |

24 manos en total. No es aritmética: **se perdió la captura entera**.

### 3.4 Qué invariantes se pueden comprobar DE VERDAD aquí

| invariante | resultado | ¿útil? |
|---|---|---|
| **I1** el bote declarado nunca es negativo | **se cumple en las 1258** | sí |
| **I2** el bote declarado no supera lo aportado | **falla en 592** | sí, y es la que encuentra las pérdidas de captura |
| **I3** el bote declarado ≥ las ciegas, si hay dos postings | **falla en 2** (`H_0357`, `H_0421`) | sí |
| **I4** ningún jugador aporta más que su stack | **falla en 22** | sí |

**I4 es la más dura, porque no depende del rake ni de las ciegas.** 22 manos en
las que alguien aporta más fichas de las que tenía:

| mano | jugador | aporta | stack | por calle |
|---|---|---|---|---|
| `H_0077` | MP | 110.4 | **21.5** | 3.0 pf + 6.4 turn + 101.0 river |
| `H_0034` | SB | 88.6 | 56.6 | 88.6 pf |
| `H_0022` | UTG | 36.0 | 31.0 | 8.0 pf + 28.0 flop |
| `H_0190` | CO | 12.8 | 12.7 | 1.0 pf + 6.8 flop + 5.0 turn |

O el stack está mal, o la acción es de otra calle, o la lectura acumulada se
atribuye a quien no es. **Ninguna de las tres se puede decidir sin la grabación.**

Y un invariante que **no** se puede comprobar, y hay que decirlo:

> **No hay forma de resolver `winner`, `allin` ni `btn_player`.** Usan ids
> `p1`..`p5` / `hero`. `players[]` tiene `['active', 'cards', 'name', 'pos',
> 'stack']` — **no hay campo de id**. Se comprobó si el id fuera el índice en
> `players[]`: de 179 ids de all-in, **0** corresponden a un jugador con stack 0.

Es un agujero del **esquema**, no de una mano, y por eso no se puede corregir
mano a mano: habría que añadir el id al esquema y reasignar las 1258.

### 3.5 Inconsistencias de origen frente a errores del código

| | de ORIGEN (el grabador no lo vio) | del CÓDIGO QUE INTERPRETA |
|---|---|---|
| ciegas | 337 BB sin posting, 0 SB | `learn.BB` como suelo absoluto en `importe_subida` — 30 hallazgos de los que 29 son falsos |
| importes | 26 no-monótonas, 5 con orden invertido | la lectura delta que se propuso y se darse por buena antes de esta auditoría |
| botes | `final_pot` roto en 592, captura perdida entera en 24 | el modelo de rake del 5%, que **empeora** el cuadre (29 vs 69) |
| posiciones | 567 manos con jugadores sin `pos` | `accion_fantasma` usando `active` como «está en la mesa» — ya corregido |
| esquema | `players[]` sin id | `winner`/`allin`/`btn_player` irresolubles por construcción |

---

## 4. Tabla de anomalías

| # | id | evidencia | hipótesis | confianza |
|---|---|---|---|---|
| 1 | **337** | sin `BB b` en el índice 0; en `H_0035` el preflop empieza con `UTG c 1.0`, que solo cuadra con una ciega de 1.0 en el bote | la caja del BB estaba vacía en el primer fotograma y el posting no se capturó (`record_hand.py:202`) | **alta** |
| 2 | **1258** | ninguna SB tiene posting; las `SB b` están en índices 1-4 tras folds | la SB nunca llegó a tener importe en el primer fotograma | **alta** |
| 3 | **567** / 783 jugadores | `pos` vacía y `active:false`, con **0 acciones** | jugador que no llegó a jugar; no es corrupción | **alta** |
| 4 | **44** | `BB c == viva − 1.0`, exacto, sin excepciones | el ROI del BB lee otro elemento de la UI, o la SB no posteó | **media** — falta una imagen |
| 5 | **26** | el acumulado de un jugador baja; 9 son `c 0.0` | `'pasar': 'c'` en `record_hand.py:218`: un check se graba como call | **alta** |
| 6 | `H_0026` | `SB c 1.0` y después `SB c 5.0` con viva 6.0 | orden de captura invertido | **media** |
| 7 | **592** | el bote declarado supera lo aportado; `H_0601` necesita 35.0 más de los que aporta; **24** aportan 0.0 y aun así tienen bote | `final_pot` mal escrito, o captura perdida | **alta** en el síntoma, **baja** en la causa |
| 8 | `H_0546` | **92.6** aportados, bote declarado **0.5**, una cifra que no aparece en la mano | `final_pot` con un valor que no se puede reconstruir | **alta** en el síntoma |
| 9 | **22** | un jugador aporta más que su stack (`H_0077`: 110.4 con 21.5) | stack mal leído, o acción de otra calle | **baja** |
| 10 | **1258** | `winner`/`allin`/`btn_player` usan ids sin campo que los enlace | agujero de esquema | **alta** |
| 11 | 6 | `BB b` de 0.5 | posting de BB con importe de SB | **media** |
| 12 | 1 | stack 7588.0 frente a una mediana de 95.9 | outlier de OCR | **baja** |

---

## 5. Pruebas

`motor/test_auditar_origen.py`, **22 tests, ninguno escribe en la base**:

- **`test_esta_herramienta_no_escribe_la_base`** — mide el sha antes y después de
  correr las tres secciones.
- **`test_el_chequeo_de_escritura_detecta_lo_que_tiene_que_detectar`** — planta
  siete violaciones (`open(DB_PATH)`, `os.replace`, la ruta literal…) y exige
  que las siete salten. Sin esto el guard solo se vería pasar.
- **`test_una_mano_sin_pos_es_un_jugador_que_no_jugo`** — comprueba contra
  `dfef471` que los jugadores sin `pos` no tienen acciones, que es lo que
  sostiene §1.4.
- **`test_el_chequeo_de_posting_acepta_y_rechaza`** — dos manos stingidas: una
  `BB b` al principio **sí** es posting, y una `BB b` con el UTG ya ha apostado
  **no**. Las dos, porque una prueba que solo comprueba el rechazo no dice si la
  función distingue.
- **`test_el_repositorio_no_ha_cambiado_durante_la_auditoria`** — comprueba el
  sha declarado contra el disco y contra el blob de git.
- Los detectores contra cifras fijadas, con el mensaje explicando qué cambió si
  fallan.

---

## 6. Recomendación

### 6.1 Seguro, se puede hacer ya

| | por qué es seguro |
|---|---|
| **Corregir `importe_subida` a aritmética acumulada** | la lectura la fija el código, no los datos. Pasa de 30 a 5 hallazgos reales, y los 25 que desaparecen son falsos positivos demostrados. |
| **Corregir `accion_fantasma` a «cualquier `pos`, activa o no»** | ya está hecho. 3 → 2. |
| **Añadir `INACTIVO_QUE_ACTUA`** | ya está hecho. El defecto de `H_1203` no lo cubría nadie. |
| **Declarar que `pos` vacía = no jugó**, y sacar las 567 manos de la lista de «manos sospechosas» | los 783 jugadores sin `pos` no tienen **ninguna** acción. Declararlo evita que se investigue 45% de la base sin motivo. |
| **Corregir la docstring de `auditar_rango.py`** | afirma lo contrario de lo que hace el código. |

### 6.2 Requiere información que no está en el repo

| | qué hace falta |
|---|---|
| **La ciega del BB en las 337** | no hace falta nada: es mechanically derivable y elSB** no. Ver 6.3. |
| **H1: qué lee el ROI del BB** | **una captura de la pantalla del BB.** Es la pregunta que decide la normalización de §2.4 Regla 4. Una imagen la responde; 1258 manos no. |
| **Si la SB postea de verdad** | la grabación original de una de las 53 parejas SB/BB. |
| **`final_pot`** | el valor viene de una lectura distinta que no está en el código del repo. Hay que localizarlo antes de intentar cuadrar botes. |
| **Los 22 de I4** | la grabación de una de esas manos. |
| **El stack de 7588** | una captura. |

### 6.3 NO automatizable con la evidencia disponible

| | por qué no |
|---|---|
| **Declarar la ciega del SB** | se probó y se revirtió. Declararla a 0.5 bajó las 921 manos buenas de **86.6% a 41.8%**: la cifra contradice al dato en 44 de 53 casos. **No hay ningún valor de SB que sirva**, porque el problema no es el valor. |
| **Cuadrar el bote** | el modelo de rake del 5% hasta 2.5BB cuadra **29** de 1258, y **sin rake** cuadran 69. Ninguno de los dos modelos es el del dato, y `H_0546` (bote 0.5 con 92.6 aportados) no lo arregla ninguno. **No se puede normalizar contra una referencia que no se sabe qué es.** |
| **Reasignar posiciones** | con 0 acciones de los jugadores sin `pos`, no hay evidencia en el dato de qué posición tenían. Anyiarlo sería inventar. |
| **Resolver `winner` / `allin`** | requiere un campo que no existe en el esquema. No es una corrección: es una migración de las 1258. |
| **Reconstruir la caja del BB** | depende de H1. Si el ROI lee el «to call», la corrección es un `+` por el posting del BB; si no, es otra cosa. Aplicarlo sin saber sería inventar. |

### 6.4 Lo que yo haría, en orden

1. **Localizar de dónde sale `final_pot`.** Está en un sitio del que este repo no
   tiene el código, y es el 40% de los hallazgos. Sin él, las manos del §3 no se
   pueden ni evaluar.
2. **Una captura del BB** para cerrar H1. Decide §2.4.
3. **Corregir `importe_subida`** y las docstrings. Es lo único que se sabe
   seguro, y quita 25 falsos positivos.
4. **Declarar las 337 ciegas del BB**, y solo esas. El BB es el caso sólido: 921
   de 921 en el índice 0 con importe 1.0. Y hay un dato a favor que no estaba
   en la versión anterior de este informe: **declarar las ciegas sube la
   reconciliación del bote de 69 a 190.** No la arregla, pero es la única palanca
   que mueve el número, y no lo mueve para peor.
5. **Nada de la SB** hasta que haya una respuesta a por qué 44 de 53 digan
   `viva − 1.0`.