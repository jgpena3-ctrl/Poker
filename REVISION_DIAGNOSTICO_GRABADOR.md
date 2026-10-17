# DIAGNÓSTICO DEL GRABADOR

**Estado:** diagnóstico. La base no se ha modificado.
**HEAD:** `4fcca01` · **SHA de la base:** `35727961646dfaba` (1258 líneas, sin cambios)

Marcas usadas en cada conclusión:

| marca | qué es |
|---|---|
| **[C]** | **hecho comprobado** en el código o con un experimento reproducible |
| **[O]** | **anomalía observada**: patrón medido, causa no determinada |
| **[I]** | **inferencia** compatible con los datos, que podría ser otra cosa |
| **[D]** | **decisión de diseño** propuesta, no una conclusión empírica |

---

## 1. Estado inicial y protección

**[C]** `git status` limpio. `HEAD = 4fcca01`. Últimos commits: `4fcca01`,
`c500c71`, `82eacfa`, `c164bde`, `48ea44a`.

**[M]** SHA-256 de `data/hands_db.jsonl` =
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`, idéntico al
declarado en `learn.HANDS_DB_SHA256`. 1258 líneas, 1 782 206 bytes.

**[C]** No modificados en esta fase: `data/hands_db.jsonl`,
`recorder/hands_db.jsonl`, `recorder/hands_db_old.jsonl`, los backups de
saneamiento y los derivados de aprendizaje.

**Modificables:** `tools/` (instrumentos de lectura), `motor/test_*` (pruebas
nuevas) y `DOCS/`.

**Pruebas al abrir:** `828 passed, 1 failed`. El rojo es
`motor/test_cm004.py::test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega`
por `H_1196`, **conservado a propósito** y sin tocar su expectativa.

**[C]** `recorder/hands_db_old.jsonl` tiene JSON corrupto (`Extra data`) y no es
legible en bloque. No se ha tocado.

---

## 2. Resultados reproducidos

**[M]** Las cifras del informe anterior se reproducen: 921 postings de BB,
337 sin posting, 1229 con `pos:SB`, 26 claves repetidas en 21 pares, 66
no-monotonas, 69 reconciliaciones exactas.

**[C]** Una cifra **no** se reproduce tal cual, y es importante:

> La revisión dio **503** calls por debajo de la viva. Con la regla escrita en
> `tools/diagnostico_grabador.py` son **498**.

La diferencia son 5 casos, y son precisamente los anómalos: el script anterior
calculaba la viva incluyendo también las calls, y aquí la viva sale **solo de
`b` y `r`**. **El número dependía de una regla no escrita.** Ahora la regla
está en el código y el número es 498.

**[D]** Las 498 son **anomalías observadas**, no 498 errores confirmados.

---

## 3. Validación de las 498 calls

### 3.1 Cómo se calcula la viva, y por qué `seccion_2` no servía

**[C]** `auditar_origen.seccion_2` **no calcula apuesta viva**. Lleva
`puesto[pos]` —la caja de cada jugador— y su «no monótona» compara esa caja
consigo misma. Es otra propiedad, y ahora están las dos con nombre.

**[C]** La regla de la viva, tal como la implementa
`tools/diagnostico_grabador.py::apuesta_viva`:

```
viva = 0 al empezar cada calle
b    amount >= viva   ->  viva = amount
r    amount >  viva   ->  viva = amount
c    amount == viva   ->  la viva no cambia
x    amount == 0      ->  la viva no cambia
f    amount == 0      ->  la viva no cambia
```

**[C]** La viva se reinicia por calle porque `record_hand.py:316-317` pone
`street_bet = {p: None}` y `street_has_bet = False`. **No se mezclan calles**:
cada una se recorre con su propia accumulator.

**[C]** La comprobación de que la regla es correcta y no circular está en
`--validar`, con una mano sintética cuya viva debe evolucionar
`[0.0, 1.0, 3.0, 3.0, 3.0]`.

### 3.2 El desglose

**[M]** De 2558 calls: **2060 llegan a la viva (80.5%)**, **498 no (19.5%)**.

| cuánto falta | manos |
|---|---|
| redondeo (≤0.15) | **5** |
| pequeña (0.15-0.5) | 27 |
| media (0.5-2.0) | 369 |
| grande (>2.0) | 97 |

**[M]** Solo **5 de 498** son de escala de redondeo. El resto no lo es.

### 3.3 El hallazgo que domina: la falta de 1.0

**[M]** **337 de 498 tienen una falta EXACTAMENTE de 1.0 (67.7%).** Y no es del
BB:

| posición | calls | cortas | % cortas | % de esas con falta 1.0 |
|---|---|---|---|---|
| **BB** | 446 | **251** | **56.3%** | **89.2%** |
| SB | 552 | 53 | 9.6% | 17.0% |
| UTG | 329 | 48 | 14.6% | 60.4% |
| MP | 431 | 61 | 14.2% | 63.9% |
| CO | 368 | 46 | 12.5% | 52.2% |
| BTN | 432 | 39 | 9.0% | 30.8% |

**[O]** Dos fenómenos distintos, no uno:

1. **El BB**: 56.3% de sus calls son cortas, y el 89.2% de esas están
   exactamente 1.0 por debajo. Un patrón **sistemático y ligado a la
   posición**.
2. **Los demás**: ~12% cortas, y solo la mitad con falta 1.0. Un fenómeno
   **repartido**.

**[M]** Cruce decisivo: entre los jugadores **que postearon**, el 90.0% de las
calls cortas tienen falta 1.0. Entre los que **no postearon**, también el
**52.5%**. Si fuera la ciega propia, el segundo grupo no la tendría.

**[I]** Una componente de la falta es el posting propio; otra no lo es y sigue
sin explicar.

**[M]** Ninguna lectura pura encaja: «siempre resta 1.0» no puede ser, porque
2060 calls llegan; «siempre es exacta» tampoco, porque 498 no llegan.

### 3.4 Lo que exige cada caso, sin atribuir causa

**[M]** De las **247** que **no** son del BB:

| | manos |
|---|---|
| sin explicación evidente | **189 (76.5%)** |
| sin acción previa en la calle | 47 (19.0%) |
| `c 0.0`, el grabador traduce un check | 8 (3.2%) |
| iguala su stack: all-in corto legítimo | 3 (1.2%) |

**[M]** Las 251 del BB: **todas** tienen una caja que cabe en su stack. Ninguna
es imposible.

**[M]** `c 0.0`: 13 en total. **[C]** El grabador traduce un check a call:
`record_hand.py:218`, `'pasar': 'c'`.

**[C]** Las 498 incluyen un caso que **no es un error de captura**: si un
jugador se va all-in corto, su caja legitimately no llega a la viva. Se han
identificado **4** por `amount == stack`. Los otros 494 no tienen esa
explicación.

---

## 4. Análisis de las acciones repetidas

**[M]** 26 claves `(pos, action, amount)` repetidas en 21 pares (mano, calle).
**Ninguna consecutiva.**

**[M]** Las 26 una a una están en el informe del instrumento
(`tools/diagnostico_grabador.py`). La firma dominante:

| mano | clave | entre |
|---|---|---|
| `H_0039` | `BTN c 6.0` (i=6,8) | `SB r 11.0` |
| `H_0481` | `BB c 1.0` (i=1,4) | `MP r 2.0`, `SB c 1.0` |
| `H_0573` | `UTG c 1.0` (i=1,7) | folds, `SB r 2.0`, `BB f` |

**[C]** La repetición **no se puede llamar duplicado** por tres razones:

1. **[C]** El grabador **no puede emitir una `c` repetida por la vía principal**
   si la caja no cambia: `record_hand.py:244` exige `new_bet != old_bet`. Y sí
   puede emitirla por el **fallback de estado** (`:256-285`), que no mira la
   caja. Las dos vías son indistinguibles en el JSON.
2. **[C]** No hay marca de tiempo ni de fotograma en el esquema.
3. **[M]** Que el importe sea compatible con una acción legítima posterior no se
   puede decidir sin la caja anterior, que no está en el JSON.

**[O]** 26 repeticiones son **casos marcados por la definición empleada**, no 26
duplicaciones confirmadas.

**[D]** Detector propuesto: `diagnostico_grabador.repeticiones()` **conserva la
secuencia completa** y marca, por caso, si es consecutiva, qué hay entre, si el
mismo jugador actúa entre medias, y cuál era la viva. **No elimina acciones y
no les asigna aportación cero.**

---

## 5. Política de contribuciones

**[D]** `diagnostico_grabador.clasificar_aportado()` devuelve tres resultados
y **conserva siempre el importe original**:

| resultado | manos | regla |
|---|---|---|
| **CALCULABLE** | **5433 (90.8%)** | ninguna condición de sospecha, **o** all-in corta con `caja == stack` |
| **SOSPECHOSA** | **445 (7.4%)** | el cálculo se puede hacer, pero depende de una lectura o secuencia anómala |
| **INDETERMINADA** | **96 (1.6%)** | faltan las referencias; **no se devuelve importe** |

**[M]** Dos correcciones que estas pruebas encontraron en el clasificador, y que
son suyas:

1. **Una all-in corta salía `INDETERMINADA`**, y es falso. El jugador se fue con
   lo que tenía; la caja no llega a la viva porque no pudo, y el importe **sí se
   sabe**: es su stack. La evidencia está en el dato (`caja == stack`).
2. **Una `c` que SUPERA la viva no se miraba.** Una call cubre, no pasa. Y es
   el mismo defecto de lectura por el otro lado: si el importe cuadra con la
   viva y no con la anterior, la caja se leyó antes de actualizarse.

**[M]** Por tipo de acción: `b` → 2392 calculable / 6 sospechosa / 0
indeterminada. `c` → 2035 / 434 / 96. `r` → 1009 / 9 / 0. **La sospecha está
prácticamente toda en las calls.**

**[M]** Motivos más frecuentes: «no alcanza la viva» (variado), «sin acción
previa y no llega a la viva» (89), «acción repetida» (49), «`c 0.0`» (15).

### 5.1 La regla que el encargo decía insuficiente, y la corrección

**[C]** «Aceptar si alcanza la viva **o** si no hay acción previa» es
insuficiente, y por dos motivos distintos:

- **Alcanzar la viva no basta.** Una lectura obsoleta puede por casualidad
  alcanzar la viva, y la coherencia de la caja no dice nada sobre *cuándo* se
  leyó.
- **No tener acción previa no basta.** Puede no haberla porque la captura la
  perdió.

**[D]** La regla propuesta **no depende de esas dos condiciones**. Mira la
coherencia del **evento**, y clasifica:

| resultado | condición |
|---|---|
| CALCULABLE | ninguna sospecha |
| SOSPECHOSA | el importe existe pero algún rasgo del evento es anómalo |
| INDETERMINADA | `c` sin acción previa **y** que no llega a la viva: falta una captura, y no hay forma de saber cuánto puso |

**[C]** Dos reglas negativas, que son las que evitan convertir hipótesis en
datos:

1. **No se sustituye un importe sospechoso por la viva.** Se devuelve el
   importe original con su motivo.
2. **Una diferencia de 0.0 no se lee como «no puso nada».** Es el caso de un
   duplicado, y ahí el aportado es indeterminado, no cero.

**[C]** Las 8 clases de prueba sintética están en
`--validar`: primera call válida, call tras subida, lectura obsoleta, `c 0.0`,
acción repetida, all-in corto, orden anómalo y redondeo.

---

## 6. Análisis de `detect_actions` — el resultado más importante

**[C]** Se ha reproducido el comportamiento con **estados sintéticos**, sin
tocar la interfaz, construyendo un `HandRecorder` sin capturador
(`HandRecorder.__new__`). Resultado:

### 6.1 La regla de la letra, que NO es la da priori

**[C]** `record_hand.py:244-253`:

| caso | letra emitida |
|---|---|
| caja `None → X`, **sin apuesta viva en la calle** | `b` |
| caja `None → X`, **con apuesta viva en la calle** | **`c`** |
| caja `A → X`, con `A > 0` y `X > A` | `r` |
| caja `A → X`, en cualquier otro caso | **nada** |

**[C]** Dos consecuencias que no seanyone evidentasy que cambian cómo se lee la
base:

> **`c` se emite para dos cosas distintas**: una igualada real, **y una subida
> de un jugador que aún no había apostando en esa calle**. Reproducido: la SB
> subiendo a 11.0 con la caja en `None` se emite como **`c 11.0`**.

> **Una caja en `0.0` no se detecta.** La rama de `b`/`c` exige `old_bet is
> None` y la de `r` exige `old_bet > 0`. Un cambio de `0.0` a cualquier importe
> **no emite nada**. Y el paso de `None` a `6.0` **sí** emite `c 6.0`.

### 6.2 La letra de la apertura DICE si se capturó la ciega

**[M]** Reparto de la primera acción voluntaria del preflop:

| | `b` | `c` | `r` |
|---|---|---|---|
| ciega capturada (921) | **13** | **393** | 446 |
| ciega **no** capturada (337) | **138** | 126 | 49 |

**[C]** `start_hand` pone `street_has_bet = False` y, al capturar las ciegas,
emite `b` para la primera y **`c`** para las demás, poniendo
`street_has_bet = True` (`:205-208`). Por tanto:

> Si se capturó la ciega, la primera apuesta voluntaria sale `c`. Si no, sale
> `b`.

**[O]** Es una tendencia fuerte con **excepciones** (13 con ciega capturada
salen `b`, y 126 sin ciega salen `c`), porque `street_has_bet` también puede
 siendo `True` por otra vía. No es una ley.

**[I]** Las dos poblaciones de la base —con y sin ciega grabada— no son dos
convenciones de importes: son **el mismo grabador con distinto punto de
partida**, y la letra de la apertura lo delata.

### 6.3 `H_0039` reproducido

**[C]** La forma exacta, reproducida con estados:

```
i=6  BTN c 6.0    vía principal, caja nueva        [legítimo]
i=7  SB  r 11.0   caja de la SB nueva             [legítimo]
i=8  BTN c 6.0    FALLBACK por estado, caja SIN actualizar   [eco]
```

**[C]** Secuencia del experimento:

1. BTN `None → 6.0`: emite `c 6.0`.
2. SB `None → 11.0`: emite **`c 11.0`**, no `r`.
3. BTN con caja **todavía en 6.0** y su `_state` pasa a `igualar`: emite
   **`c 6.0`**. **Esta es la vía que produce `H_0039[8]`, y se reproduce.**
4. BTN `6.0 → 11.0` un fotograma después: emite `r 11.0`.
5. Si la caja **nunca** sube: **no emite nada**.

**[C]** El grabador produce **dos acciones para una acción real**: el eco del
fallback y el cambio de caja. En el JSON solo queda una, según cuál llegara.

**[C]** Y el caso 5 es el inverso y más grave: **una acción real puede no
registrarse nunca**, y el JSON no deja marca de que pasó.

**[I]** Que `H_0039[8]` sea exactamente este caso es muy probable —el eco, la
subida en medio y la ausencia de la `r 11.0` encajan— pero **no está probado**,
porque el JSON no guarda fotogramas.

---

## 7. Identificación de jugadores — corrección de un error mío

**[C]** **Los ids SÍ se resuelven.** `get_position(pid, btn_player)` en
`record_hand.py` los traduce a posición, y `PLAYER_IDS` es
`['hero','p1'..'p5']`, los mismos ids que aparecen en `winner` y `allin`.

> **Me equivoqué.** Informes anteriores decían que `winner`, `allin` y
> `btn_player` eran irresolubles por falta de un campo `pid`. **Es falso.** Lo
> comprobé solo contra la hipótesis del índice, y de un solo negativo concluí
> que no había mapeo. Sí lo hay.

**[M]** Validación: los 202 ids de `allin` resuelven a una posición. De ellos,
**38 tienen compromiso exactamente igual al stack**, que es la definición de
all-in:

| mano | id | posición | stack | comprometido |
|---|---|---|---|---|
| `H_0074` | hero | UTG | 38.2 | **38.2** |
| `H_0078` | p5 | BTN | 18.4 | **18.4** |
| `H_0130` | p5 | BTN | 18.5 | **18.5** |
| `H_0180` | p1 | UTG | 21.5 | **21.5** |

**[M]** Los 148 restantes tienen `compromiso != stack`, lo que encaja con las
pérdidas de captura descritas en §6, y 16 no tienen stack para esa posición.

**[M]** `H_0546` como ejemplo del método: `allin:['p1']` resuelve a **BTN**, que
es quien subió sus 52.3. El campo `allin` **es correcto**. En cambio
`winner:['p3']` resuelve a **MP** mientras `showdown` dice `winner1: BB` —una
contradicción **dentro de la mano**, y no un problema de ids.

**[O]** El esquema **no tiene** campo `pid` en `players[]`, así que el vínculo
`id → name` no es directo. Pero `id → posición → name` sí, y basta.

---

## 8. Ciegas, postings y ROI del BB

### 8.1 Los hechos, separados

**[M]** Postings registrados: **921**, todos `BB b` en el índice 0, con importe
1.0 en 915 y 0.5 en 6.

**[O]** Aperturas confundidas con postings: `H_0032` tiene `SB b 5.0` en la
racha inicial. **[C]** No es una ciega: es una apertura, porque el grabador
escribe `b` a quien abre (§6.1).

**[M]** Manos sin posting visible: **337**.

**[O]** Casos compatibles con una ciega omitida: 337 en total, de los cuales
varias —`H_0035`, cuyo preflop empieza `UTG c 1.0`, imposible sin una ciega de
1.0 en el bote— son **compatibles** con ella.

**[H]** Los 337 que no se pueden resolver sin evidencia visual: **los 1258**,
en el sentido de que ninguna ciega se puede **declarar** sin una captura.

### 8.2 La investigación del ROI, y su refutación

**[C]** `BET_ROIS` (`lector_estado.py:519-526`) es **por id de jugador**, no
por posición, y cada ROI mide 64×18. `hero` y `p3` son **left-aligned**; los
otros cuatro, **center**. `p3` además tiene un tratamiento especial por un
artefacto del botón (`:802-807`).

**[C]** **El BB no es un asiento fijo.** Con botón `hero` el BB es `p4`; con
botón `p5` es `p3`; con botón `p1` es `p5`. Cambia en cada mano.

**[O]** Eso hacía testeable, sin captura, una hipótesis: si el problema del BB
fuera el ROI, la tasa de calls cortas **dependería del id que ocupa el BB** y de
su alineación.

**[M]** **Se refuta:**

| id en el BB | alineación | calls | cortas | % |
|---|---|---|---|---|
| hero | left | 79 | 46 | 58.2% |
| p1 | center | 90 | 50 | 55.6% |
| p2 | center | 67 | 34 | 50.7% |
| p3 | left | 46 | 26 | 56.5% |
| p4 | center | 83 | 49 | 59.0% |
| p5 | center | 81 | 46 | 56.8% |

left 57.6% · center 55.8%. **Indistinguible.**

**[I]** El efecto es **por posición**, no por asiento ni por ROI. Eso refuerza la
lectura de que hay algo en el significado de la posición BB, y **debilita** la
hipótesis del OCR mal alineado.

**[H]** Sigue sin decidirse qué es. Lo que se ha eliminado es una hipótesis.

---

## 9. Origen y fiabilidad de `final_pot`

**[C]** `record_hand.py:319-324`:

```python
pot = state.get('pot') or state.get('pot_wide')
self.hand['final_pot'] = max(self.hand.get('max_pot', 0), pot)
```

`max_pot` se actualiza en el bucle de captura (`:364-366`).

**[C]** **`final_pot` es el máximo del OCR del bote durante la mano**, no un
cálculo. `recorder_live.py:1005` hace lo mismo sin el `max`: hay **dos
versiones** del grabador.

**[C]** `_street_ended` (`:113-119`) detecta el fin de calle porque
**todas las cajas desaparecen a la vez**. Eso implica que la ventana de
captura de una calle empieza cuando la primera caja aparece y termina cuando
la última desaparece. **[I]** Un `pot` leído cerca de ese borde puede ser de
la calle anterior o de la siguiente.

**[O]** `final_pot` y las acciones son **fuentes independientes**. **No hay
ninguna que sea la verdad de referencia.**

**[M]** `pearson = 0.835`, `R² = 0.70`, pendiente 0.68. El pot **sí** sigue al
aporte —el OCR funciona— pero con un 30% de varianza sin explicar.

**[M]** El modelo de rake probado **no mejora nada**: R² 0.6965 sin rake frente
a 0.6920 con rake. **[O]** Y la distribución es **bimodal**: 34.0% con el bote
por debajo, 39.5% por encima, 18.0% iguales. Una comisión se descuenta
siempre en el mismo sentido.

**[D]** **No concluir que el rake está descartado universalmente.** Lo que se
descarta es **ese modelo, con esa métrica**. Las dos fuentes pueden tener
errores independientes, y hasta que haya una imagen del pot display no se sabe
cuál.

**[H]** Que `final_pot` incluya o no el rake **no está determinado**.

---

## 10. Las seis manos prioritarias

| mano | observado | incumple | compatible con | descartado |
|---|---|---|---|---|
| `H_0546` | BB 40.3, BTN 52.3 = todo su stack; `allin:['p1']`→BTN ✓; pot 0.5 | pot ≪ aporte | OCR del pot leyó 0.5 | que el aporte esté mal: 92.6 con rake ≈ 90.6 |
| `H_0601` | BTN `r 73.0`, BB `c 37.0`; stacks 102.8 y 99.0 | BB iguala 37 contra 73 sin ser all-in | una de las dos cajas mal leída | — |
| `H_0077` | MP `b 101.0` en river con **stack 21.5**; aporte 125.8, pot 37.1 | aporta 110.4 con 21.5 de stack | stack mal leído, o importe mal leído | — |
| `H_0034` | SB `r 88.6` con **stack 56.6**; aporte 89.6, pot 7.0 |idem |idem | — |
| `H_0022` | UTG `b 28.0` con stack 31.0, más 8.0 antes: 36.0 | aporta 36.0 con 31.0 | stack corto, o importe de otra calle | — |
| `H_0190` | CO aporta 12.8 con stack **12.7** | se pasa por **0.1** | redondeo o lectura OCR | — |

**[M]** `H_0190` es el más limpio: un error de 0.1, compatible con redondeo.
Los otros cinco van de 0.1 a 88.7.

**[M]** `H_0546` es el único con un invariante **confirmado**: el
`allin` apunta al jugador correcto y su compromiso iguala su stack. El problema
está **solo** en `final_pot`.

**No se corrige ninguno.**

---

## 11. Tests existentes y pruebas nuevas

### 11.1 Qué se añade

| prueba | qué comprueba, y por qué no es un texto |
|---|---|---|
| `test_las_calls_que_no_llegan_a_la_viva` | la cifra fuerte, y `H_0039[8]` byte a byte |
| `test_las_manos_con_una_accion_repetida` | 26 claves / 21 pares / **0 consecutivas** |
| `test_la_viva_se_reinicia_por_calle` | una mano con dos calles y importes cruzados |
| `test_la_regla_de_la_letra_del_grabador` | **funcional**: estados sintéticos a través de `detect_actions` |
| `test_una_caja_en_cero_no_se_detecta` | funcional, y el caso que no esperaba |
| `test_una_subida_sin_apuesta_previa_sale_call` | funcional: reproduce el `c 11.0` |
| `test_la_clasificacion_de_aportado` | las tres clases y las 8 situaciones sintéticas |
| `test_los_ids_se_resuelven_con_el_boton` | la corrección de §7 |
| `test_38_allin_confirmados_por_compromiso` | los 38, que validan el mapeo |

**[D]** Los tests de `detect_actions` son los que **no existían**: hasta ahora
la semántica del grabador se comprobaba buscando cadenas de texto, que pasan
aunque el comportamiento cambie. Ahora se comprueba **ejecutando el código**.

### 11.2 Lo que sigue sin cubrir

- El **ROI** y su alineación: refutado por datos, pero el OCR real solo se
  comprueba con una imagen.
- `pot` frente a `pot_wide`: nadie sabe si son la misma magnitud.
- El **cierre de mano**: si `finalize_hand` corre antes de que el último pot
  visible esté leído.

---

## 12. Evidencia externa pendiente

| | qué resuelve | qué lo resuelve |
|---|---|---|
| **1. Captura del BB** | el patrón `viva − 1.0` y por qué afecta a un 56.3% de sus calls | una imagen |
| **2. Captura del pot display** | si `final_pot` lleva el rake, y si 0.5 en `H_0546` es una lectura mala | una imagen |
| **3. `BET_ROIS` de los seis asientos** | si algún ROI cubre el elemento equivocado | una captura con los seis visibles |
| **4. `H_0601`, `H_0077`, `H_0034`, `H_0022`** | qué caja está mal | 4 capturas |
| **5. Grabación de una pareja SB/BB** | si la SB postea | un vídeo |
| **6. `pot` vs `pot_wide` en el código de origen** | si son la misma magnitud | acceso al código de la app |

**[D]** Ninguna de las seis se sustituye por una regla inferida de la base. Los
puntos 1 y 2 explican, entre los dos, **más de la mitad** de las anomalías.

---

## 13. Plan de correcciones recomendado

Cada punto con su fichero, su riesgo y su prueba de aceptación. **Ninguno se
aplica sin autorización.**

| # | cambio | fichero | riesgo | aceptación |
|---|---|---|---|---|
| 1 | **No tocar la base** | — | — | SHA sin cambios |
| 2 | Corregir `importe_subida` a aritmética acumulada | `tools/auditar_rango.py` | bajo: es el cálculo del auditor, no el dato | 30 hallazgos → 5 |
| 3 | Declarar `pos` vacía = «no jugó» | `DOCS/` | ninguno | 783 jugadores, 0 acciones |
| 4 | Añadir el resolvedor `id → posición` | `tools/diagnostico_grabador.py` | bajo, es solo lectura | 202 ids resueltos |
| 5 | Corregir docstrings de tests | `motor/test_*` | ninguno | suite igual |
| 6 | **Corregir el grabador**: `0.0` no se detecta, y la subida sale `c` | `recorder/record_hand.py` | **alto**: afecta a toda captura futura | estados sintéticos + manos nuevas |
| 7 | **Añadir marca de fotograma** al esquema | `recorder/record_hand.py` | medio: cambia el formato | distinguir eco de lectura |
| 8 | **Ninguna ciega** | — | — | espera la captura 1 |

**[D]** El 6 y el 7 son los que de verdad importan, y **solo afectan a
capturas futuras**: no se puede arreglar el histórico. Con ellos, la siguiente
sesión de grabación produce manos donde `c` y `r` significen una cosa sola, y
donde un eco es identificable.

---

## 14. Archivos modificados y no modificados

**Modificados en esta fase:**

- `tools/diagnostico_grabador.py` — **nuevo**, solo lectura, con `--validar`
- `motor/test_diagnostico_grabador.py` — **nuevo**
- `REVISION_DIAGNOSTICO_GRABADOR.md` — **este documento**

**NO modificados:** `data/hands_db.jsonl` · `recorder/hands_db.jsonl` ·
`recorder/hands_db_old.jsonl` · `recorder/record_hand.py` ·
`tools/lector_estado.py` · `tools/auditar_rango.py` ·
`tools/auditar_origen.py` · `motor/learn.py` · los backups de saneamiento · los
derivados de aprendizaje.

**[M]** `H_1196` sigue en rojo y sin tocar.

---

## 15. SHA final y resultado de las pruebas

**[M]** SHA-256 de `data/hands_db.jsonl`:
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`
— **idéntico al de apertura y al declarado**.

**[M]** Suite: `828 passed, 1 failed, 1 skipped, 5 xfailed`. El rojo es `H_1196`.

---

## Conclusión

**Lo que se sostiene.** La semántica acumulada de `amount` **[C]**, con un
matiz duro y reproducido: la caja que se emite es **la del fotograma en que se
detectó la acción**, que puede ser la anterior **[C]**. La letra de la acción
depende de si la ciega se capturó **[O]**, y una caja en `0.0` no se detecta
nunca **[C]**. El BB tiene un patrón propio de 1.0 por debajo **[O]**, que **no
es del ROI** **[M]**. Los ids se resuelven con el botón **[M]**, corrigiendo un
error mío. 498 calls no llegan a la viva **[M]**, de las que 4 son all-ins
cortos legítimos **[M]** y 189 no tienen explicación evidente **[M]**.

**Lo que no.** Ninguna ciega. Ningún importe. Ningún `final_pot`. Ningún
`winner`, `allin` ni posición.

**El error conceptual que hereda todo el trabajo previo** es tratar
`final_pot` como referencia. No lo es: es **otra lectura de OCR**, y por eso
las 592 manos «imposibles» no son necesariamente errores de las acciones.

**Y el hallazgo que más dato pide con menos evidencia:** una captura del BB y
otra del pot display. Entre las dos explican la mitad de las anomalías, y las
seis hipótesis que siguen abiertas dependen solo de ellas.