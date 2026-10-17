# REVISIÓN TÉCNICA DE LA AUDITORÍA DEL ORIGEN

**Estado:** revisión de la auditoría, no una auditoría nueva.
**Base:** `c8c5c9f`, sin modificar. SHA `35727961646dfaba`, 1258 líneas.
**Alcance:** verificar el informe anterior, no repetirlo.

Toda afirmación de este documento lleva una marca de grado:

| marca | qué significa |
|---|---|
| **[C]** | **comprobado en el código**: se lee en un fichero, en una línea |
| **[M]** | **medido en la base**: sale de una función que se puede volver a ejecutar |
| **[I]** | **inferencia compatible** con los datos, pero que podría ser otra cosa |
| **[H]** | **hipótesis** que necesita evidencia externa |

---

## 1. Estado inicial y protección de la base

**[C]** `git status` limpio. `HEAD = c8c5c9f`.

**[M]** SHA de `data/hands_db.jsonl` = `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`, que coincide con `learn.HANDS_DB_SHA256`. 1258 líneas. `HANDS_DB_COMMIT = 33ab8ee`.

**[M]** Estado de los backups:

| fichero | sha | ¿protege algo? |
|---|---|---|
| `antes_ciegas_35727961646dfaba.jsonl` | `35727961646dfaba` | **no** — es idéntico a la base actual |
| `antes_sanear_31eba6e1c4824015.jsonl` | `31eba6e1c4824015` | sí — el estado previo al saneamiento |
| `33ab8ee` en git | — | sí — mismo estado |

**El backup del intento revertido quedó redundante**: se hizo antes de migrar las
ciegas y, al revertir, la base volvió a ser byte a byte igual. **No hay un
respaldo independiente del estado actual fuera de git.** No es grave —el
estado está en `33ab8ee`— pero el nombre del fichero sugiere una protección
que ya no existe.

### 1.1 Protección del instrumento

**[M]** `motor/test_auditar_origen.py::test_la_auditoria_no_escribe_la_base`
mide el SHA antes y después de las **tres** secciones. **[C]** El fichero
importa `motor.learn` y `auditar_rango`; `motor/learn.py` tiene **una**
escritura (`open(path, 'w')`, línea 669) y está dentro de `def main()`, es decir
no se ejecuta al importar. **[M]** La comprobación es empírica, no textual, que
es más fuerte.

**Pero el guard tiene un hueco real, y hay que decirlo:**

- mide **solo** `data/hands_db.jsonl`. No mide los derivados `data/*.json`,
  que es donde escribe `tools/reconstruir_derivados.py`;
- no mide ficheros escritos por **otros procesos**;
- no protege contra un subproceso que este instrumento lanzara.

---

## 2. Hallazgos confirmados

**[M]** Recalculé las 25 cifras del informe anterior desde las funciones
reales. **Las 25 cuadran exactamente**, incluidas las que el informe daba sin
procedencia (`224` diferencias de 0.5, `71` de 1.0, `24` aportes cero, `190`
con ciegas declaradas, `29` con rake).

**[C]** `amount` es la caja de apuesta del jugador en esa calle:
`tools/lector_estado.py:798-814` hace OCR de `BET_ROIS[player]` y lo guarda en
`state[p_bet]`; `record_hand.py:200/209/248/251/273/278/284` lo copia tal cual
a `amount`. **No hay ninguna resta**: `new_bet - old_bet` no aparece en el
fichero. **Es la contribución acumulada en la calle**, no el delta ni el tamaño
objetivo.

**[M]** La serie es monótona en 6354 de 6380, y **ninguna `b` ni `r` la rompe**
en ninguna calle. Es lo esperable de un campo acumulado.

**[M]** 1258 manos de 6 jugadores. Ninguna mesa corta. Ningún ante ni straddle:
como máximo **una** posición cieguea por mano, y cuando ciega el importe es 0.5
o 1.0.

**[M]** 783 jugadores sin `pos`, **0 con acciones**. En las 29 manos sin
`pos:SB` los jugadores sin posición están todos `active:false`. `pos` vacía
significa «no llegó a jugar».

**[M]** `es_posting` no puede distinguir una ciega de una apertura grabada como
`b`, porque el grabador escribe `b` a quien abre (`record_hand.py:246`). El
informe anterior lo decía; aquí lo confirmo con `H_0032`, que tiene `SB b 5.0`
en la racha inicial y es una apertura.

---

## 3. Conclusiones del informe anterior que REQUIEREN CORRECCIÓN

### 3.1 El «99.6% monótono» mide una propiedad débil

**[M]** El informe destaca que 6354 de 6380 son monótonas. Es cierto, pero
monotonía **solo comprueba que la caja de un jugador no baje**. No comprueba
que una call llegue a la apuesta viva.

Medida esa propiedad fuerte:

> **503 de 13826 acciones son `c` que no llegan a la apuesta viva.**
> Preflop 412 · flop 37 · turn 26 · river 28.

| mano | calle | acción | amount | viva |
|---|---|---|---|---|
| `H_0001` | preflop | `BB c` | 1.5 | 2.5 |
| `H_0021` | preflop | `BTN c` | 6.7 | 6.8 |
| `H_0032` | flop | `SB c` | 5.9 | 6.0 |
| `H_0088` | turn | `BB c` | 0.0 | 38.8 |

**El 99.6% invita a leer «el dato es consistente en general». No lo es.** El
número fuerte es 503, no 26.

### 3.2 `amount` puede ser una lectura **obsoleta** de la caja

**[C]** El detector es `if new_bet != old_bet` (`record_hand.py:244`), y el
fallback por estado (`:256-285`) emite para un jugador **no detectado** en el
primer bucle, leyendo `state[f'{pid}_bet']` **en ese momento**.

**[M]** Si la caja del jugador todavía no se ha actualizado cuando su estado
aparece, se emite el valor viejo. Caso limpio, `H_0039`:

```
i=6  BTN c 6.0      (viva 6.0, correcto)
i=7  SB  r 11.0     (viva 11.0)
i=8  BTN c 6.0      contra una viva de 11.0  <-- lectura ANTIGUA
```

**Consecuencia para la hipótesis semántica:** no es «la caja en el momento de
la acción», es «la caja **tal como se leyó** en el fotograma en que se detectó
la acción». En la mayoría de las manos coinciden; en estas no, y no hay forma de
saberlo sin la marca de tiempo, que el esquema no guarda.

### 3.3 Mi propia «corrección» del rake en esta sesión fue un error

**[M]** Escribí que el rake mejoraba el ajuste (`rmse 0.44` frente a `13.92`)
por «32 veces». **Era falso**, por un fallo de mi propio script: regresé `X`
contra `X` —el modelo del rake contra sí mismo— en vez de contra los botes
reales.

El ajuste correcto:

| modelo | R² | rmse | dentro ±2.0 |
|---|---|---|---|
| sin rake | **0.6965** | 13.92 | **33.5%** |
| rake 5% hasta 2.5BB | 0.6920 | 14.03 | 31.2% |

**El rake no explica el bote, y la conclusión del informe anterior era
correcta.** Se mantiene, y ahora con un argumento mejor (§6.2).

### 3.4 Las cifras de los docstrings de los tests están viejas

**[C]** Dos defectos de documentación, que no cambian ningún resultado:

| sitio | dice | debería decir |
|---|---|---|
| `test_el_bote_solo_cuadra_en_89_manos` | nombre: 89 | 69 |
| su docstring | «7.1%» | **5.5%** (69/1258) |
| `test_el_rake_no_explica_el_bote` docstring | «16 de 1258; sin rake, 189» | **29 y 69** |

Las **aserciones** de los tres son correctas y los tests pasan. Lo que está
mal es el texto, que es lo que se lee.

### 3.5 Los dos datasets reconcilian igual

**[M]** `data/hands_db.jsonl` (1258) cuadra en el 5.5%. `recorder/hands_db.jsonl`
(84) cuadra en el **4.8%**. La impresión previa de que el segundo «cuadraba
mejor» venía de mirar **una** mano. **No es una diferencia de ruta de código**,
así que esa hipótesis queda descartada.

`recorder/hands_db_old.jsonl` tiene **JSON corrupto** (`Extra data`), no se
puede leer en bloque.

---

## 4. Defectos en las pruebas

### 4.1 Falsos positivos que pasan por pruebas válidas

| test | qué hace realmente | por qué es insuffciente |
|---|---|---|
| `test_un_jugador_sin_pos_es_uno_que_no_jugo` | cuenta acciones con `pos` vacía y espera 0 | **No demuestra lo que su nombre dice.** Cuenta acciones sin `pos`, que es un conjunto distinto de «acciones de los jugadores sin `pos`». Y como el esquema no tiene `pid`, **es imposible** atribuir una acción a un jugador: la posición es la única clave. La conclusión correcta es «no se puede atribuir», no «no tienen acciones». |
| `test_h0546_tiene_un_bote_que_no_aparece_en_la_mano` | fija 92.6, 0.5, 52.3, 40.3 | **Correcto y valioso**: fue el que cazó el error de la suma. |
| `test_la_semantica_viene_del_codigo_del_grabador` | comprueba tres cadenas de texto | **Frágil**: pasa aunque el código cambie de comportamiento sin cambiar esas tres líneas. La versión fuerte sería un test funcional sobre `detect_actions` con estados sintéticos. |
| `test_el_esquema_no_tiene_campo_de_id` | comprueba que `players[]` no tiene id, y que el id no es el índice | **Solo descarta UNA vía** (el índice). No descarta un orden distinto, un mapeo por `btn_idx`, ni un id externo. |

### 4.2 Lo que las pruebas SÍ hacen bien

- **Fijan cifras contra las funciones reales**, no contra constantes escritas a
  mano. Cuando las funciones cambiaron, los tests saltaron.
- **`test_h0546_...` detectó un error conceptual mío** que la lectura del
  informe no detectó.
- **La batería de `--validar` planta violaciones**, y eso se comprobó: cuando
  escribí mal un caso sintético, el propio `--validar` lo cazó.

### 4.3 Qué NO cubren

- Que `es_posting` no confunda una ciega con una apertura: el test sintético usa
  `BB b` al principio y `BB b` después de que otro apueste, pero **no** cubre
  `SB b 5.0` de `H_0032`, que es el falso positivo real.
- Que la reconciliación del bote sea sensible a la lectura: no hay test que
  falle si alguien vuelve a sumar en vez de tomar el último valor, salvo el de
  `H_0546`.
- Acciones duplicadas: no hay ningún test sobre ellas, y hay 21 manos con una
  acción repetida.

---

## 5. Análisis de `amount`, postings y contribuciones

### 5.1 ¿Consistente por calle y por tipo de acción?

**[C]** Sí en el grabador: las cuatro calles pasan por la misma función
`detect_actions`, sin ramas por calle.

**[M]** Pero hay una asimetría entre el **preflop** y el **postflop** en los
datos: de las 503 calls que no llegan a la viva, **412 son de preflop**
(82%). Y el patrón `viva − 1.0` del BB (§5.3) aparece **solo en preflop**.

**[I]** En preflop todas las cajas están presentes en pantalla a la vez desde el
primer fotograma, y el BB es el último en actuar; en postflop las cajas se
reinician por calle (`record_hand.py:316`). Eso explicaría la asimetría, pero
**no está verificado**.

### 5.2 ¿Se puede reconstruir `aportado` con la fórmula propuesta?

La fórmula es `aportado(i) = amount(i) − acumulado_anterior(pos, calle)`. **Es
válida bajo condiciones, y enumero cuáles:**

| condición | ¿se cumple? | cómo se detecta |
|---|---|---|
| el jugador tiene una acción previa en la calle | a veces | con `i > primera_del_jugador` |
| la lectura de la caja no es obsoleta | **no siempre** | 503 calls no llegan a la viva |
| no hay acciones duplicadas | **no siempre** | 21 manos con acción repetida |
| el jugador tiene `pos` | **casi siempre** | 783 jugadores sin `pos`; 0 acciones suyas |
| la posición es única en la mano | sí | 0 `pos` duplicadas |
| la calle está bien delimitada | sí | el recorder reinicia `street_bet` (`:316`) |

**Las tres primeras la invalidan.** Concretamente:

- **Con una lectura obsoleta** (`H_0039[8]`) la fórmula da
  `6.0 − 6.0 = 0`, cuando el BTN puso 5.0 más. Es un importe inventado.
- **Con un check grabado como call** (`'pasar': 'c'`, `:218`), `c 0.0` pone el
  acumulado a 0 y el siguiente `aportado` sale restado de cero.
- **Con un duplicado**, la segunda aparición da `aportado = 0`.

**Regla propuesta:** `aportado` solo es calculable si la acción llega a la viva
**o** si la acción anterior del mismo jugador en la calle no existe. Y esas dos
cosas se pueden comprobar antes de calcular, con lo que las 503 se marcan en
vez de producir cifras falsas.

### 5.3 El patrón del BB, revisado

**[M]** 53 parejas SB/BB. 44 con `BB c == viva − 1.0` y `SB c == viva`, ambas
al 100%. Además 3 de las 4 del grupo 0.5, y 4 del grupo 0.0 con `BB c == viva`.

**[I]** Compatible con que el ROI del BB lea un elemento distinto.

**[C]** El ROI existe y es por jugador: `BET_ROIS` en
`tools/lector_estado.py:799`, y `p3` ya tiene un tratamiento especial
(`:802-807`, «unique ROI with button artifact»). **Que el BB tenga otro ROI es
plausible y no está descartado.**

**[H]** Falta una captura. Sin ella no se elige entre las cuatro hipótesis del
informe anterior, y sigue sin elegirse.

### 5.4 Postings: qué se puede reconstruir con evidencia suficiente

**[M]** Las 921 `BB b` del índice 0, todas con importe 1.0 (915) o 0.5 (6).

**[M]** Las 337 sin posting: en varias (`H_0035`) el preflop empieza con
`UTG c 1.0`, que solo cuadra si había 1.0 en el bote.

**[I]** Que la ciega del BB se puede reconstruir como `1.0` en esas 337.

**[C]** **Contra esa inferencia:** el grabador solo captura una ciega si la caja
**ya tiene importe en el primer fotograma** (`record_hand.py:202`). Si la caja
estaba vacía, no se registró — pero eso **no demuestra que no se posteara**,
solo que no se vio. Reconstruirla es una hipótesis, no una medición.

**Las 6 con importe 0.5** sí son un posting registrado con el importe de una SB.
Eso es un hecho del dato; cuál de las dos ciegas es, no.

**Ninguna SB es reconstruible.** **[M]** El dato no contiene ninguna
información de la SB: ni posting, ni importe, ni caja. Declararla sería
inventar el importe, y el intento de 0.5 ya se probó y empeoró la métrica.

---

## 6. Análisis de `final_pot` y reconciliación

### 6.1 Origen localizado

**[C]** `record_hand.py:319-324`:

```python
pot = state.get('pot') or state.get('pot_wide')
if pot is not None:
    self.hand['final_pot'] = max(self.hand.get('max_pot', 0), pot)
else:
    self.hand['final_pot'] = self.hand.get('max_pot', 0)
```

Y `max_pot` se actualiza en el bucle de captura, `record_hand.py:364-366`.

**`final_pot` es una lectura por OCR del bote en pantalla — el máximo visto
durante la mano —, no un cálculo a partir de las acciones.** Por eso no
reconcilia: son dos fuentes independientes.

`recorder/recorder_live.py:1005` hace lo mismo sin el `max`, lo que sugiere dos
versiones del grabador.

### 6.2 Por qué el rake no explica nada

**[M]** El ratio `(declarado − aportado)/aportado` es **bimodal**:

| banda | manos |
|---|---|
| declarado mucho menor (< −50%) | 90 (7.3%) |
| declarado algo menor | 420 (34.0%) |
| igual (±2%) | 222 (18.0%) |
| declarado algo mayor | 488 (39.5%) |
| declarado mucho mayor (> +50%) | 14 (1.1%) |

**Una comisión se descuenta siempre y en el mismo sentido.** Aquí es
aproximadamente la mitad y la mitad. **[I]** La firma es de acciones que faltan
o sobran, no de un descuento.

**[M]** `pearson(final_pot, aportado) = 0.835`, `R² = 0.70`, pendiente 0.68.
El pot **sí** sigue al aporte —el OCR funciona— pero con un 30% de varianza sin
explicar, y una pendiente de 0.68 que no es 1.0 ni 0.95.

**[I]** Una pendiente de 0.68 con `final_pot` por debajo en 41% de las manos y
por encima en 40% sugiere que las cajas se **sobreleen** más de lo que se
subleen, y que el potDisplay se queda corto en las manos grandes.

### 6.3 Los seis casos del encargo

| mano | registrado | deducible | solo con grabación |
|---|---|---|---|
| `H_0546` | BB 40.3 (caja), BTN 52.3 = todo su stack; `allin:['p1']`; pot 0.5 | bote real ≈ 90.6 tras rake | por qué el pot es 0.5 y qué jugador es `p1` |
| `H_0601` | BTN `r 73.0` en river, BB `c 37.0`; stacks 102.8 y 99.0 | imposible: BB iguala 37 contra 73 sin ser all-in | cuál de las dos cajas está mal |
| `H_0077` | MP `b 101.0` en river con **stack 21.5**; aporte 125.8, pot 37.1 | o el importe o el stack está mal | cuál |
| `H_0034` | SB `r 88.6` con **stack 56.6**; aporte 89.6, pot 7.0 | ídem | ídem |
| `H_0022` | UTG `b 28.0` en flop con stack 31.0, y 8.0 antes: 36.0 total |el stack se queda corto | si el stack estaba mal leído o el importe |
| `H_0190` | CO aporta 12.8 con stack **12.7**: se pasa por **0.1** | redondeo o lectura OCR | poco: la diferencia es de una cifra |

**[M]** `H_0190` es el caso más limpio: un error de 0.1, compatible con
redondeo. Los otros cinco son de 0.1 a 88.7.

**[C]** Sobre las 22 manos de I4 (aportar más que el stack), **cuatro de las
seis del encargo están ahí**. Es el invariante más duro porque no depende ni del
rake ni de las ciegas ni del pot.

---

## 7. Qué se puede corregir con seguridad

| | por qué es seguro | confianza |
|---|---|---|
| **`importe_subida` a aritmética acumulada** | la lectura la fija el código, y la aritmética es la del grabador | **[C]** |
| **Docstring de `auditar_rango.py`** | afirma lo contrario de lo que hace el código | **[C]** |
| **Nombres y docstrings de los tests** | no cambian ningún resultado | **[C]** |
| **Declarar que `pos` vacía = no jugó** | **[M]** 783 jugadores, 0 acciones | **[M]** |
| **Añadir el detector de las 503 calls** | es la propiedad fuerte que faltaba | **[M]** |
| **Marcar las 21 manos con acción repetida** | son identificables y ninguna es reinterpretable | **[M]** |

**Ninguna de estas toca `data/hands_db.jsonl`.**

## 8. Qué requiere grabación o evidencia adicional

| | qué lo resuelve | coste |
|---|---|---|
| **Qué lee el ROI del BB** | **una captura de la pantalla con el BB** | una imagen |
| **Si la SB postea** | la grabación original de una pareja SB/BB | un vídeo |
| **`H_0546`, `H_0601`, `H_0077`, `H_0034`, `H_0022`** | la captura del bote y de las cajas de esos momentos | 5 capturas |
| **Los 592 botes imposibles** | saber si `final_pot` es del OCR o de otro sitio | 1 imagen del pot display |
| **El stack de 7588** | una captura | una imagen |
| **`winner` / `allin` / `btn_player`** | un campo `pid` en el esquema | migración de las 1258 |

---

## 9. Plan de acción priorizado

1. **Captura del BB con su ROI.** Es lo que más desatasca: decide §5.3, decide
   la Regla 4 de la normalización, y probablemente parte de §6. **Coste: una
   imagen.**
2. **Captura del pot display.** Confirma si `final_pot` es el pot visible y si
   lleva el rake dentro. Sin eso, §6 es hipótesis.
3. **Añadir el detector de las 503 calls** y el de las 21 duplicadas, sin tocar
   la base. Convierte dos intuiciones en invariantes.
4. **Corregir `importe_subida`** a acumulada. Quita 25 falsos positivos.
5. **Ninguna ciega.** Ni BB ni SB, hasta tener la captura del punto 1. La
   prueba previa —declararlas empeoró la métrica— sigue siendo el dato más
   sólido contra hacerlo a ciegas.
6. **No tocar `final_pot`.** Es una lectura independiente; cualquier
   «corrección» sería inventar la referencia contra la que medir.

---

## 10. Archivos examinados y comandos

**Ficheros:** `tools/auditar_origen.py`, `motor/test_auditar_origen.py`,
`DOCS/AUDITORIA_ORIGEN.md`, `recorder/record_hand.py` (líneas 113-153, 186-211,
213-287, 289-324, 358-373), `tools/lector_estado.py` (790-825),
`motor/learn.py` (líneas 26-39, 303-341, 433-482, 570-597, 669),
`data/hands_db.jsonl`, `recorder/hands_db.jsonl`, `recorder/hands_db_old.jsonl`,
`tools/sanear_base.py`, `tools/lista_saneamiento.py`.

**Comandos de verificación:**

```bash
git log --oneline -1; git status --short
python -c "import hashlib;print(hashlib.sha256(open('data/hands_db.jsonl','rb').read()).hexdigest())"
python tools/auditar_origen.py --validar
python tools/auditar_origen.py --seccion 1
python tools/auditar_origen.py --seccion 2
python tools/auditar_origen.py --seccion 3
python -m pytest motor/test_auditar_origen.py -q
python -m pytest motor -q
```

**Estado de la suite al cerrar esta revisión:** 826 pasan, 1 rojo
(`test_cm004.py::test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega`,
por `H_1196`, que sigue abierta y a propósito).

---

## Conclusión

**Lo que se sostiene:** la semántica acumulada de `amount` **[C]**, con el
matiz de que puede ser una lectura obsoleta **[M]**; que `pos` vacía significa
«no jugó» **[M]**; que el patrón del BB es exacto en 44 de 44 **[M]**; que
`final_pot` es un OCR del pot display **[C]**; que el rake no lo explica **[M]**;
que el campo `pid` falta **[C]**.

**Lo que NO se sostiene y estaba en el informe anterior:** el «99.6% monótono»
como medida de consistencia —la cifra fuerte es 503 **[M]**—.

**Lo que no se puede decidir con lo que hay:** qué lee el ROI del BB **[H]**, si
la SB postea **[H]**, y por qué `H_0546` tiene un bote de 0.5 **[H]**. Las tres
esperan lo mismo: una captura.

**El error conceptual más grave que hereda esta auditoría** es tratar
`final_pot` como si fuera una referencia contra la que medir. No lo es: es otra
lectura de OCR, y por eso las 592 manos «imposibles» no son necesariamente
errores de las acciones. Hasta que haya una imagen del pot display, esa cifra
está mal interpretada.