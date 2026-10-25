# CANAL MANUAL CERRADO — `hands_db.jsonl`

**Estado:** vigente.
**Fecha:** 2026-10-24
**Commit del estado canónico:** `12c7bed`
**SHA-256:** `7d3c55db7eca0a3f09282eedaf67032da38f511fa1b975e74e2c7b2a9f4ddc64`
**Líneas:** 1253
**Revisión manual:** **terminada**. `H_0001`..`H_1282`, en tres tramos.
**Saneamiento:** empezado. 3 correcciones; el resto documentado en
`DOCS/SANEAMIENTO.md`.
**Vigila:** `motor/test_canal_manual.py` — 16 tests

---

## Adopción de la base normalizada — 2026-10-24

`trabajo/hands_db_edicion.jsonl` pasa a ser la fuente canónica mediante una
copia verificada, conservando el original local en `data/hands_db.jsonl.bak`.
La adopción se autorizó después del cierre de la cuarentena: **1253 -> 1253**
manos candidatas, **0 -> 0** registros en cuarentena y **0 -> 0** violaciones
del orden de la ciega.

El contrato de aceptación no reutiliza los números de la base anterior:
el motor reconoce **1253** ciegas y las categorías de primera decisión son
`3bet=86`, `bb_check=348`, `call_3bet=15`, `call_limp=322`,
`call_open=594`, `fold=2211`, `fold_vs_3bet=139`, `fold_vs_open=1471`,
`limp=564`, `open=587`, `rol=275`, `squeeze=25`.
`trabajo/control_categorias_adopcion.json` fija ese contrato.

El reemplazo retiró cinco manos que no formaban parte de la candidata
validada: `H_0028`, `H_0072`, `H_0146`, `H_1123` y `H_1188`.
Los derivados se reconstruyen después de esta adopción desde la nueva fuente.

---

## 1. Qué significa «cerrado»

> **Ningún SCRIPT escribe `data/hands_db.jsonl`. Nunca a mano, nunca con un
> editor, nunca copiando y pegado.**
>
> El mantenedor **sí** la edita a mano: eso es la revisión. Lo que está cerrado
> es el canal por el que se cuela una escritura sin que nadie la decida. Ver §4.1.

No es una intención. `motor/test_canal_manual.py` falla si:

| | |
|---|---|
| 1 | el fichero tiene cambios **sin commitear** |
| 2 | su `sha256` **no es** `learn.HANDS_DB_SHA256` |
| 3 | el número de manos **no es** `learn.HANDS_DB_LINEAS` |
| 4 | este documento **no menciona** el hash y el commit vigentes |
| 5 | el commit declarado **no existe** o **no tiene** ese hash |
| 6 | el blob de git y el fichero en disco **no coinciden** byte a byte |
| 7 | `aplicar_reinterpretacion.py` **no** comprueba la revisión en curso |
| 8 | el mensaje de revisión vuelve a decir «BASE CONGELADA» |

Las ocho se leen juntas porque cada una sola se puede esquivar. Un hash
declarado sin documento es una afirmación sin respaldo; un documento sin hash
es una descripción de otra base.

## 2. Por qué, y no es una norma de estilo

En este mismo bloque, `aplicar_reinterpretacion.py --apply` sobrescribió
**928 líneas** que el mantenedor había escrito a mano: 74 manos modificadas y
22 borradas. Se restauraron enteras y no se perdió nada, pero el agujero era
real: el script comparaba con **su propia salida** y no con la del fichero
que tenía delante.

Lo que faltaba no era que el script fuera cuidadoso. Era **que nadie pudiera
hacerlo por error**.

> El fallo no fue ejecutar `--apply`. Fue que el script no tenía la
> garantía de «no sobrescribo lo que no es mío». Ahora sí, y además hay un
> test que falla si el fichero se sale del estado declarado.

`--apply --descartar-cambios` sigue existiendo, y es una **salvaguarda, no
una recuperación**: si se autoriza, el fichero ajeno se reemplaza. Por eso el
backup se verifica por hash antes de escribir y el rollback es automático si
la verificación posterior falla.

## 3. Los estados que se reconocen

`aplicar_reinterpretacion.py::estado_del_fichero_actual()` clasifica el
fichero en tres:

| estado | sha256 | qué es |
|---|---|---|
| `referencia` | `bb46fec0…` | `e314f74`, el punto de partida: CM-001, CM-003 y la ventana de 877 |
| `salida_de_este_script` | `173a7274…` | lo que produce `aplicar_reinterpretacion.py` |
| **`ajeno`** | cualquier otra cosa | alguien lo editó |

Con `ajeno`, `--apply` se niega y dice cuántas líneas se perderían. En
`dry-run` lo informa pero no falla: **informar no es escribir**.

El estado vigente (`9b5905a`) es `ajeno`, y con razón: es la revisión manual.

## 4. El estado vigente: la revisión manual, terminada

`hands_db.jsonl` la revisó el mantenedor mano a mano, de `H_0001` a `H_1282`.
Fueron **tres tramos declarados**, y los tres se midieron contra el estado
anterior, no se supusieron.

| tramo | commit | manos | rango | qué corrigió |
|---|---|---|---|---|
| 1.º | `9b5905a` | 63 | `H_1014` → `H_1029` | orden de la ciega del BB, `winner`, `active`/`pos`, 3 cartas por OCR |
| 2.º | **`bf60aa8`** | **40** | `H_1029` → `H_1070` | casi todo `winner`: listas de 2 a 6 nombres reducidas a una |
| 3.º | **`dfef471`** | **211** | `H_0173` → **`H_1282`** | el resto de los ganadores múltiples, 8 preflops reetiquetados, `Sandm` y `Capitan spiff` |

Los tres tramos juntos pasaron las manos con 2+ ganadores de **179 a 14**, y
ninguna mano se quedó sin ganador. La revisión **está terminada**: la
comprobación manual se hizo sobre las 1258 líneas.

### 4.0-bis El tercer tramo, en detalle

El tercero es el grande, y cerró lo que quedaba: **211 manos de golpe**, de
`H_0173` a `H_1282`, sin manos nuevas ni borradas.

| | antes | después |
|---|---|---|
| líneas del fichero | 1258 | 1258 |
| manos añadidas o borradas | — | ninguna |
| manos modificadas | — | **211** (`H_0173`..`H_1282`) |
| manos que no cambian en ningún campo | — | **1047** de 1258 |
| `winner` con 2+ en la base entera | 179 | **14** |
| manos sin ganador declarado | 0 | **0** |
| **`BB b` mal ordenadas (invariante de CM-004)** | 0 | **1** (`H_1196`) |

Y lo que corrigió, por familia:

| manos | qué cambió |
|---|---|
| 39 | `winner` de 2 a 1 |
| 17 | `winner` de 3 a 1 |
| 10 | `winner` de 2 a 1, y además `flop` |
| 8 | `winner` de 5 a 1 |
| 8 | `river`, y el jugador `Sandm` |
| 6 | `winner` de 2 a 1, y además `turn` |
| 6 | `river` |
| 5 | `winner` de 4 a 1 |
| 5 | `winner` de 6 a 1 |
| 4 | `river`, y el jugador `Capitan spiff` |
| 3 | `river`, y dos jugadores (`Sandm`, `ComboHunter`) |
| 8 | preflop reetiquetado, con longitud distinta |

**Y sí mueve las cifras de `CONTRATO_F72A.md` §5**, a diferencia del tramo
anterior: `H_0173` está dentro de la ventana de 877. El tramo 3 se cierra
**antes** de recalibrar, y el plan de `DOCS/FASE_D_PLAN.md` se queda
pendiente de rehacer contra este estado, no contra `bf60aa8`.

### 4.0-b La última violation del invariante: `H_1196`, ya corregida

Este era el punto abierto de la revisión, y se declaraba en vez de esconderse.

```
  0  BB  b  0.5     la ciega
  1  UTG f  0.0
  2  MP  f  0.0
  3  CO  c  1.0     limpeo
  4  BTN f  0.0
  5  SB  c  1.0     limpeo
  6  BB  r  2.0     <-- la subida del BB, antes grabada como `b`
  7  CO  f  0.0
  8  SB  c  2.0     iguala la subida
```

El motor **no** confundía el `BB b 2.0` con la ciega: `_es_ciega_bb` exige que
no haya ninguna acción voluntaria antes, y aquí hay dos limpeos, así que la
rechazaba como ciega y la trataba como subida. Lo que hace
`entradas_bb_rechazadas` es más ancho: registra **toda** `BB b` que el motor
no reconoció como ciega, y le pone `CAUSA_ORDEN`.

Había dos lecturas defendibles, y **la decisión es del mantenedor, no del
motor**:

1. **El dato está mal.** Una subida del BB debería grabarse como `'r'`, y
   `learn._es_ciega_bb` ya avisa de ello: la regla exige `act == 'b'`, así que
   una subida bien grabada *nunca* se lee como ciega. Si la GUI escribe la
   subida del BB como `b`, esa es la forma exacta de CM-004 y la corrección es
   `'BB r 2.0'`.
2. **El guard es más ancho que el defecto.** La regla de CM-004 era «una
   `BB b` tardía **sin posting previo**», no «una `BB b` tardía». Aquí el BB ya
   posteó en el índice 0.

**Se tomó la primera.** El mantenedor corrigió la mano en el fichero —commit
`12c7bed`— y la corrección es de un carácter: `b` → `r`, con el **importe
intacto** (2.0 antes y 2.0 después). De modo que la mano no cambia de pot y
ningún número de bote se mueve.

Lo que se comprobó al cerrar, y por qué importaba:

| | |
|---|---|
| la repasa que pedía el expediente | `manos_con_orden_ciega_malo()` sobre las 1258: **`[]`**. No había una segunda mano con el mismo defecto. |
| ¿la mano estaba en la ventana? | **No.** `H_1196` está en la línea 1172 de 1258, y la ventana fiable corta en la línea `RELIABLE_HANDS`. |
| ¿estaba en la lista de exclusiones? | **No.** `EXCLUSIONES_VENTANA_FABLE` no la contiene. |

De las dos últimas sale lo que importa: **ninguna cifra publicada se mueve**.
Ni el AUC, ni las frecuencias, ni el rango auditado. Se comprobó midiendo, que
es la diferencia entre «no he visto que se mueva» y «no se mueve».

Y lo que **sí** se mueve, y por una unidad, es el reparto por acción de la base
entera: una acción deja de ser `b` y pasa a ser `r`. Los totales de la matriz
no cambian.

**El invariante no se relajó.** El test
`test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega` sigue en la suite,
sin `xfail` y sin `skip`, y ahora **pasa**. Relajar el invariante para ponerlo
verde habría sido justo el error que este canal manual existe para evitar: lo
que se corrigió fue el dato, no la regla.

El expediente, con la decisión y las mediciones, está en
[`INC-004_H_1196.md`](INC-004_H_1196.md), y el `git show 12c7bed` está a un
comando de distancia.

### 4.0 El segundo tramo, en detalle

| | antes | después |
|---|---|---|
| líneas del fichero | 1258 | 1258 |
| manos añadidas o borradas | — | ninguna |
| manos modificadas | — | **40** (`H_1030`..`H_1070`) |
| de 2+ ganadores a 1 ganador | — | **32** |
| de 1 ganador a 2+ (**empeoran**) | — | **0** |
| `winner` con 2+ en la base entera | 179 | **147** |
| `BB b` mal ordenadas (invariante de CM-004) | 0 | **0** |
| violaciones del invariante **introducidas** | — | **0** |
| manos sin ganador declarado | 0 | 0 |
| `active:false` conservando `pos` | 20 | 20 |

**Es una mejora y no una regresión**, y se puede comprobar: las 32 manos que
cambian lo hacen en una sola dirección, y ninguna de las 40 introduce una
violación del invariante de CM-004.

> **Y no mueve las cifras de `CONTRATO_F72A.md` §5.** Las 40 manos son
> **posteriores a la ventana de 877**, así que no entran en la métrica. Se
> comprobó midiendo, no suponiendo: `tools/auditar_solapamiento_multiway.py`
> sigue dando 674 puntos · 521 de política · 239 MULTIWAY · 45,9 % · cota 268.
>
> El tramo anterior (63 manos) **sí** los movió, de 519 a 521. Que este no los
> mueva no es que la cifra sea insensible a la base: es que estas manos están
> fuera de la ventana. Un tramo que no cambia nada también se declara.

### 4.1 El primer tramo, en detalle

Lo que se comprobó, contra el fichero anterior y no contra una impresión:

| | `5c41b23` | `9b5905a` |
|---|---|---|
| manos con una `BB b` mal ordenada (**el invariante de CM-004**) | 2 · `H_0103`, `H_0236` | **0** |
| manos sin ganador declarado | 1 | **0** |
| `winner` con 2+ ganadores, dentro de las 63 tocadas | 14 | **1** |
| jugadores `active:false` que conservan `pos` | 29 | **20** |
| cartas del hero corregidas por OCR | — | 3 manos |
| líneas del fichero | 1258 | 1258 |

| familia | cuántas | qué es |
|---|---|---|
| orden de la ciega del BB | 20 con preflop tocado | `BB x inferred` colocado donde el motor lo reconoce como ciega, acciones fantasma retiradas |
| `winner` | 17 | listas de 2 a 6 ganadores reducidas a uno; la mano sin ganador recuperada |
| `active` / `pos` | ~20 | jugadores que ya habían folderado con `active:false` y `pos` todavía puesta, o al revés |
| OCR | 3 | cartas del hero corregidas |

**La decisión es aceptar el estado y declararlo**, que es lo contrario de
revertirlo: revertir devolvería dos violaciones del invariante de CM-004 y
perdería trabajo real. Se llama Opción A en `revision_1`.

### 4.1 La revisión manual NO congela la base

> **Mientras haya revisión manual en curso, ningún SCRIPT escribe
> `hands_db.jsonl`.**

`learn.REVISION_EN_CURSO = False` desde el 2026-10-15: la revisión del
mantenedor está **terminada**, tras tres tramos que llegaron desde
`H_0001` hasta `H_1282`. Mientras estuvo en `True`, el mantenedor iba revisando
las manos una a una y eso, por definición, es editar el fichero.

**Y `False` no significa que la base sea correcta.** Significa que nadie la
está mirando en este momento. Quedan 30 `IMPORTE_SUBIDA`, 15
`SHOWDOWN_SIN_WINNER`, 3 `WINNER_FOLDEO` y 2 `ACCION_FANTASMA`, todos
declarados en `DOCS/HALLZGOS_H0001_H1014.md`.
Terminar la revisión cierra un estado; no cierra los defectos que quedan, y
confundir las dos cosas sería el error de este bloque.

**Lo que esta frase ya NO dice**, y antes sí:

> ~~`hands_db.jsonl` no se modifica: ni a mano, ni con script.~~

Las dos mitades eran verdad y juntas eran una contradicción: *revisar las
manos una a una es cambiarlas*. El congelamiento prohibía exactamente la
actividad de la revisión. Medido: `9b5905a` cambió 63 manos —legítimas, y con
mejora medida— y el guard falló, que es lo único que el guard podía hacer.
Volvería a fallar en el siguiente commit de la revisión. Eso no es un guard: es
una bomba de relojería, y obligaba a apagar el mecanismo entero para poder
seguir revisando.

| | antes | ahora |
|---|---|---|
| el mantenedor edita a mano | **prohibido** | **es la revisión** |
| un script escribe | prohibido | prohibido |
| el manifiesto se redeclara | imposible mientras dure la revisión | en cada avance, con su motivo |

Lo que protege las ediciones del mantenedor no es un congelamiento: es
`test_el_hash_de_la_base_es_el_declarado`. Obliga a que cada cambio de la
base lleve su hash, su commit y su motivo escrito. Dos guards del mismo
invariante no son más seguridad, son dos sitios donde el invariante puede
estar mal.

`--descartar-cambios` **no salta** el bloqueo de scripts. Saltarlo significa
terminar la revisión, no escribir más rápido.

### 4.2 Decisión vigente

**Declarar y continuar.** Las 22 borradas, las 70 de `5c41b23` y las 63 de
`9b5905a` **se aceptan** y quedan escritas, con el hash y el motivo aquí. Ya no
hay un «pendiente» que resolver: un pendiente que nadie puede resolver no es un
estado defendible en un repositorio.

Lo que **sigue abierto** no es el estado de la base, sino estas decisiones, que
son de calibración y no de datos:

| | |
|---|---|
| [APARCADO_DB.md](APARCADO_DB.md) | lo que queda aparcado, con su estado medido |
| [RANGO_VIGENTE.md](RANGO_VIGENTE.md) | si las manos excluidas vuelven a la ventana de calibración |

## 5. Cómo se cambia la base a partir de ahora

```bash
# 1. el script, con su dry-run primero
python tools/aplicar_reinterpretacion.py
python tools/aplicar_reinterpretacion.py --apply

# 2. si el fichero actual NO es suyo, hay que decirlo a sabiendas
python tools/aplicar_reinterpretacion.py --apply --descartar-cambios

# 3. actualizar el estado canonico: las TRES constantes, con motivo
#      learn.HANDS_DB_SHA256
#      learn.HANDS_DB_LINEAS
#      learn.HANDS_DB_COMMIT
#    y este documento

# 4. si el cambio afecta a la ventana, recalcular las cifras publicadas
python tools/auditar_solapamiento_multiway.py     # §5 de CONTRATO_F72A.md

# 5. suite
python -m pytest motor recorder tests -q
```

**Actualizar el hash sin escribir el motivo en este documento es editar a
mano con más pasos.** Es la misma falta de trazabilidad, con más pasos.

## 6. Quién escribe la base, medido

> Esta sección **no** decía la verdad hasta ahora. Afirmaba que el canal
> manual estaba cerrado sin haber comprobado quién escribe. Se ha medido:
> `python tools/quien_escribe.py`, y `motor/test_quien_escribe.py` verifica
> que la lista de aquí y la del instrumento coinciden.

Hay **cinco** módulos que escriben `data/hands_db.jsonl`:

| módulo | cómo | ¿guard? |
|---|---|---|
| `recorder/recorder_live.py` | `open(self.output_path, 'a')` | **no hace falta**: solo AÑADE manos, no puede destruirlas |
| `recorder/record_hand.py` | `open(self.output_path, 'a')` | **no hace falta**, por lo mismo |
| `hand_editor.py` | `_guardar_base()` → backup, temporal, `os.replace` | **sí**, añadido en este bloque (§6.1) |
| `tools/aplicar_reinterpretacion.py` | `shutil.copy2` / `os.replace` | **sí**: `estado_del_fichero_actual()` → 3, revisión en curso → 4, SHA de salida declarado |
| `tools/aplicar_correcciones.py` | `shutil.copy2` / `os.replace` | **sí**: backup verificado por SHA y rollback automático |

Los otros cuatro módulos que tocan el fichero **solo leen**, y no les pasa
nada: `motor/learn.py` escribe `preflop_stats.json`, no la base.

> **Dos correcciones a lo que este mismo documento decía antes.**
>
> 1. Afirmaba que `aplicar_correcciones.py` «no declara el sha256 de lo que
>    produce». **Es falso**: lo declara, y hay un test que lo comprueba.
>    La afirmación era verdad en su día y nadie la actualizó.
> 2. `hand_editor.py` **no aparecía en ninguna lista**. Es una GUI que
>    reescribe las 1258 manos enteras. Eso sí era un agujero real.

### 6.1 El guard de `hand_editor.py`

Antes, `_write()` hacía `open(DATA_PATH, 'w')` a pelo: podía perder la base
entera con un fallo de disco a mitad, y no había backup ni aviso.

No se le **prohíbe** escribir —la revisión manual es editar el fichero, y sin
eso el mantenedor no puede trabajar—, se le pone **red**:

| | |
|---|---|
| backup `hands_db.jsonl.bak` | verificado por SHA antes de escribir nada |
| escritura a `.tmp` + `os.replace` | atómica: un fallo deja la original intacta |
| aviso de manifiesto obsoleto | si el hash nuevo no es el declarado, dice qué tres constantes actualizar |

Si el backup no se verifica o la escritura falla, **no se escribe nada** y se
dice. Hay dos tests que lo comprueban simulando justo esos dos fallos.

---

## 7. Lo que este documento NO dice

- No dice que la base actual sea **correcta**. Dice que es **conocida**: tiene
  un hash, un commit y una lista de lo que se hizo y por qué.
- No dice que las 22 manos borradas de `5c41b23` estuvieran mal. Dice que **se
  borraron**, y que la evidencia que lo autoriza está sin escribir. Ver
  `DOCS/HALLZGOS_H0001_H1014.md` §5.
- No dice que `9b5905a` esté completo. Dice que las 63 manos que tocó están
  medidas y declaradas, y que la revisión siguió en `H_1029` con dos tramos
  más por delante: `bf60aa8` (40 manos) y `dfef471` (211 manos), hasta
  `H_1282`.
- No dice que la revisión haya encontrado todos los errores. Dice que se ha
  mirado las 1258 líneas y que lo que queda está en la lista: el saneamiento
  ya corrigió 2 y **`DOCS/SANEAMIENTO.md`** deja el resto con id, calle,
  índice y acción exacta. Lo no declarado sigue sin mirar.
