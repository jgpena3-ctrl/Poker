# SANEAMIENTO DE `hands_db.jsonl` — lo corregido y lo que queda

**Estado:** vigente.
**Fecha:** 2026-10-15
**Base de partida:** `dfef471`, sha `31eba6e1c4824015`
**Alcance:** las 1258 manos, no solo `H_0001..H_1014`. Ver §4.

Instrumento: `tools/lista_saneamiento.py` reparte el trabajo por **coste de
decisión**, no por clase. Corrector: `tools/sanear_base.py`, que solo aplica
las correcciones cuya acción se deduce del propio dato, y las tiene escritas
una a una.

---

## 1. Qué significa «evidente» aquí

Una corrección es **evidente** cuando el dato determina el valor y no hace
falta mirar la grabación original para saberlo. En este repo eso se demuestra
con aritmética o con secuencia, no con criterio:

| prueba | ejemplo |
|---|---|
| el bote cuadra exactamente | el bote es la suma de lo que puso cada uno, y solo cuadra de una manera |
| la secuencia no deja otra lectura | el actor se sentó,_actuó_ y por tanto estuvo |
| es un caso único en la base | si el patrón se repite, el patrón es la regla, y quien tiene la grabación es quien la pone |

Y **no es evidente** cuando el dato admite dos correcciones distintas. En ese
caso este documento da el `hand_id`, la calle, el índice y la acción exacta,
y la corrección se hace mirando la grabación original. Preferimos dejar una
mano sin corregir a corregirla con una suposición: una corrección razonada mal
es indistinguible de un error, y nadie la va a volver a mirar.

---

## 2. Corregido — 3 correcciones

Las aplicó `tools/sanear_base.py --apply`. Backup verificado en
`data/_backup_aplicar_correcciones/antes_sanear_31eba6e1c4824015.jsonl`.

### 2.1 `H_1063` — al BB le faltaba la respuesta

Se inserta `{"pos": "BB", "action": "f", "amount": 0.0}` al final del preflop.

```
antes:   BB b 1.0 · UTG r 2.0 · MP f · CO f · BTN f · SB f
despues: BB b 1.0 · UTG r 2.0 · MP f · CO f · BTN f · SB f · BB f
```

**Lo que lo hace evidente es el bote.** `final_pot = 3.5`, y
`3.5 = 0.5 (SB) + 1.0 (BB) + 2.0 (UTG)`. Si el BB hubiera igualado, el bote
serían 5.5. No hay flop, ni turn, ni river, ni board. Y `winner = p2` con
`showdown = {winner1: UTG (Oscar.RG)}`: el UTG es el único que puso dinero más
allá de su ciega y gana sinimps contestada. El BB se fue.

### 2.2 `H_1203` — un BB marcado como ausente que jugó cuatro calles

`players[0].active`: `false` → `true`.

Jarduan tiene `pos: BB` y `active: false`, y actúa en las cuatro calles:
postea 1.0, iguala 1.0 en el flop, iguala 1.0 en el turn e iguala 5.6 en el
river. No hay forma de que alguien que no está en la mano juegue eso.

Y no es una convención: en las 1258 manos hay **21** jugadores con `pos`
puesta y `active: false`, y de esos 21, **solo este** tiene acciones. Los
otros 20 son gente que se sentó y no jugó, que es justo lo que la bandera
significa.

### 2.4 `H_1196` — la subida del BB grabada como `b`

La **última** violacion del invariante de CM-004 que quedaba en la base.
La aplicó el mantenedor a mano, en el commit `12c7bed`.

```
antes:   6  BB  b  2.0
despues: 6  BB  r  2.0
```

**Lo que lo hace evidente es la secuencia, no una suposicion.** La accion
del indice 6 va **despues de dos limpeos** (`CO c 1.0` en el 3 y `SB c 1.0`
en el 5), de modo que no puede ser la ciega: `_es_ciega_bb` exige
`not voluntary_before`. Y la regla exige `act == 'b'` para reconocer una
ciega, de modo que una subida bien grabada *nunca* se lee como ciega. Grabar
la subida del BB como `r` es la unica forma de que las dos cosas sean
verdad a la vez.

Y el reparto de la mano cuadra: el BB postea 0.5, sube a 2.0 encima de los
limpeos a 1.0, el CO se va y el SB iguala a 2.0. El **importe no se toca**:
2.0 antes y 2.0 despues, de modo que la mano no cambia de pot.

**Lo que se comprobo al cerrar, y por que importaba:**

- la repasa que pedia el expediente: `manos_con_orden_ciega_malo()` sobre
  las 1258 manos da `[]`. No habia una segunda mano con el mismo defecto.
- `H_1196` esta en la linea 1172 de 1258, y la ventana fiable corta en la
  linea `RELIABLE_HANDS`: o sea que es **posterior** a la ventana.
- `H_1196` **no** esta en `EXCLUSIONES_VENTANA_FABLE`.

De las dos ultimas sale lo que importa: **ninguna cifra publicada se
mueve**. Y lo que si se mueve, y por una unidad, es el reparto por accion
de la base entera: una accion deja de ser `b` y pasa a ser `r`.

Ver `DOCS/INC-004_H_1196.md`.

### 2.3 Un detector que estaba mal, y se corrigió de paso

`auditar_rango.accion_fantasma` usaba `active` como sinónimo de «está en la
mesa». **No lo es.** Medido sobre las 1258: hay **4991** jugadores con
`active: true` que foldean. La bandera dice «se sentó a jugar», no «está en el
bote».

Eso producía **un falso positivo**: `H_1203` salía como «el BB actúa y no está
en la mesa», siendo al revés. El detector ahora mira si algún jugador —activo
o no— tiene esa posición.

| | antes | después |
|---|---|---|
| `ACCION_FANTASMA` | 3 | **2** |

---

## 3. Pendiente — con id y acción

> `H_1196` salía de aquí: la sección 3.7 de este documento estaba
> pendiente y ya no lo está. Está en §2.4, con la corrección y su motivo.

### 3.1 `ACCION_FANTASMA` — 2 manos

Una acción de una posición que **ningún** jugador tiene puesta.

| id | calle | índice | acción | posiciones reales en la mesa | jugadores con `pos` vacía |
|---|---|---|---|---|---|
| `H_0519` | `turn` | 1 | `{"pos": "CO", "action": "f", "amount": 0.0}` | MP, BTN, SB, BB | 2, ambos `active:false` |
| `H_0846` | `preflop` | 1 | `{"pos": "MP", "action": "f", "amount": 0.0}` | SB, BB, UTG, CO, BTN | 1, `active:false` |

**Qué mirar en la grabación.** Las dos tienen el mismo patrón y no se puede
saber solo con el dato:

- `H_0519`: hay **dos** jugadores con `pos` vacía, y además **BTN y SB están
  `active: true` y no actúan en ninguna calle posterior al preflop**. O sea que
  o falta la `pos` de alguien que sí actuó, o sobra una acción. ¿Cuál?
- `H_0846`: hay **un** jugador con `pos` vacía, y el **UTG está `active: true`
  pero no actúa nunca**. La lectura A es que el `MP` de la acción es en realidad
  el UTG. La lectura B es que el `MP` es el de `pos` vacía y lo que falta es una
  acción del UTG. Son correcciones distintas.

La aritmética no las separa: en `H_0846` el bote es 1.5
(`0.5 SB + 1.0 BB`), que cuadra con «todos foldean a la ciega del BB», y las
dos lecturas dan el mismo bote.

### 3.2 `AUSENCIA_RESPUESTA_BB` — 1 mano

| id | qué falta | contexto |
|---|---|---|
| `H_1241` | la respuesta del BB a `BTN r 20.0` | `BB b 1.0 · UTG f · MP f · CO f · BTN r 2.0 · SB c 2.0 · BB r 12.0 · BTN r 20.0 · SB f` |

**Qué mirar en la grabación.** Si el BB igualó a 20.0, llamó o se fue. El bote
**no lo dice**: `final_pot = 24.7`, y ni una igualada ni un fold cuadran con
ese número, así que el bote de esta mano está mal por separado. Además esta
mano tiene dos ganadores (`winner = [p1, p3]`) y un board `Ks 4c 4s 4d Kh`, que
es un reparto. Conviene mirar las tres cosas a la vez.

### 3.3 `IMPORTE_SUBIDA` — 30 manos, 37 ocurrencias

Una acción `r` por un importe que no supera la apuesta viva.

**Lo que ya está medido y NO hay que volver a medir:**

- El suelo de 1.0 del detector es **correcto**. La ciega grabada en la base es
  1.0 en 915 manos, 0.5 en 6 y 2.0 en 1.
- **Ninguna** de estas 30 manos tiene la ciega del BB grabada. Por eso el
  detector usa la constante nominal en vez de la ciega observada.
- 28 de las 37 ocurrencias son `r 1.0` y 9 son `r 0.5`. O sea que **ninguna es
  una subida real**: no hay nada que subir.

**Por qué no se corrigen aquí.** Hay dos lecturas y cambian frequencies:

1. `r 1.0` de salida, sin ciega grabada, es un **limpeo** → `c 1.0`.
2. O es una **apertura** y lo que falta es la entrada de la ciega, en cuyo caso
   lo que hay que escribir no es `c` sino otra cosa.

Y la consecuencia es grande: cambiar `r` por `c` cambia lo que el preflop lee
como `open`, `3bet` y `squeeze`, que es de donde salen las frecuencias de
apertura. **Eso se decide con la grabación delante, no con la aritmética.**

| id | calle | índice | posición | importe | qué hay antes |
|---|---|---|---|---|---|
| `H_0049` | preflop | 0 | MP | 1.0 | (es la primera) |
| `H_0076` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0104` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0105` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0107` | preflop | 2 | CO | 1.0 | `UTG f · MP f` |
| `H_0108` | preflop | 3 | BTN | 1.0 | `UTG f · MP f · CO f` |
| `H_0117` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0131` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0139` | preflop | 2 | BB | 1.0 | `UTG f · BTN f` |
| `H_0147` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0148` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0151` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0151` | preflop | 2 | BTN | 1.0 | `UTG r 1.0 · MP f` |
| `H_0151` | preflop | 3 | SB | 0.5 | `UTG r 1.0 · MP f · BTN r 1.0` |
| `H_0159` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0159` | preflop | 3 | SB | 0.5 | `UTG f · MP r 1.0 · CO f` |
| `H_0161` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0163` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0164` | preflop | 3 | SB | 0.5 | `UTG f · MP f · BTN f` |
| `H_0167` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0167` | preflop | 2 | SB | 0.5 | `UTG r 1.0 · BTN f` |
| `H_0168` | preflop | 2 | SB | 0.5 | `UTG f · BTN f` |
| `H_0169` | preflop | 1 | SB | 1.0 | `BTN f` |
| `H_0170` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0171` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0171` | preflop | 1 | MP | 1.0 | `UTG r 1.0` |
| `H_0175` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0177` | preflop | 2 | SB | 0.5 | `UTG f · BTN f` |
| `H_0185` | preflop | 0 | MP | 1.0 | (es la primera) |
| `H_0197` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0197` | preflop | 2 | CO | 1.0 | `UTG f · MP r 1.0` |
| `H_0197` | preflop | 4 | SB | 0.5 | `UTG f · MP r 1.0 · CO r 1.0 · BTN f` |
| `H_0207` | preflop | 1 | MP | 1.0 | `UTG f` |
| `H_0214` | preflop | 4 | SB | 0.5 | `UTG f · MP f · CO c 1.0 · BTN f` |
| `H_0215` | preflop | 0 | UTG | 1.0 | (es la primera) |
| `H_0249` | preflop | 3 | BTN | 1.0 | `UTG f · MP f · CO f` |
| `H_0335` | preflop | 1 | SB | 0.5 | `BTN f` |

### 3.4 `SIN_ALLIN` — 73 manos, y son **una** decisión

Las 73 son `H_0001`..`H_0073`, **contiguas**, y ninguna más. No son 73
problemas: es un tramo en el que el recorder no escribió la clave.

El campo `allin` es una lista de ids (`p1`..`p5`, `hero`). En las 1185 manos
que sí lo tienen, **984 valen `[]`**.

**Qué hay que mirar.** Si alguien se fue all-in en alguna de esas 73, el valor
no es `[]`. Y del dato no sale: hay que buscar un `stack` a 0 o una subida al
máximo en la mano. Una decisión, y una pasada.

### 3.5 `WINNER_FOLDEO` — 3 manos

`winner` incluye a alguien que foldeó.

| id | quién figura como ganador | posición |
|---|---|---|
| `H_0602` | `p3` | BTN |
| `H_0748` | `p2` | UTG |
| `H_0893` | `p2` | SB |

Dos lecturas: el `winner` está mal y el fold está bien (el nombre se pisó), o
el fold está mal y el `winner` está bien (quien figura no se fue). No es
académico: la primera cambia el resultado de la mano y la segunda cambia el
`PreflopStats`.

### 3.6 `SHOWDOWN_SIN_WINNER` — 15 manos

El campo `showdown` nombra a alguien que no está en `winner`:
`H_0374`, `H_0376`, `H_0409`, `H_0447`, `H_0511`, `H_0744`, `H_0751`,
`H_0759`, `H_0786`, `H_0833`, `H_0911`, `H_0915`, `H_0932`, `H_0957`, `H_0972`.

Lectura A: el showdown cita a más gente de la que ganó, porque es un
desglose de lo que se vio y no una declaración del ganador — legítimo.
Lectura B: falta un ganador en `winner`.

### 3.8 Ganador múltiple — 14 manos

`H_0105`, `H_0173`, `H_0188`, `H_0307`, `H_0372`, `H_0793`, `H_0798`,
`H_0974`, `H_0977`, `H_0978`, `H_1121`, `H_1220`, `H_1241`, `H_1267`.

No son una clase de defecto: la revisión las bajó de 179 a 14. Se listan para
que el número sea revisable, no porque se sepa que estén mal.

---

## 4. El alcance: por qué 1258 y no 991

`tools/auditar_rango.py` audita por defecto hasta `H_1014`. La revisión manual
llegó a `H_1282`. Es decir, **267 manos se corrigieron sin que ningún detector
las mirase**, y por ahí entraron cuatro defectos que el rango viejo no podía
encontrar: `H_1203`, `H_1063`, `H_1241` y `H_1196`.

`tools/lista_saneamiento.py` usa toda la base por eso, y
`motor/test_lista_saneamiento.py` fija las cuatro para que el alcance no vuelva
a recortarse en silencio.

---

## 5. Cómo se aplica una corrección pendiente

**Mirando la grabación original**, no desde aquí. Cuando una de las secciones
de §3 se decide, la corrección entra en `CORRECCIONES` de
`tools/sanear_base.py` con su `porque` escrito —la aritmética o la secuencia
que la justifica—, y:

```
python tools/sanear_base.py            # dry-run, no escribe
python tools/sanear_base.py --apply    # backup verificado, escritura atómica
```

El script **no deduce nada en tiempo de ejecución**. Si aparece un defecto
nuevo, no lo toca: o se añade a mano con su justificación, o se queda aquí.
Un saneador que se extiende solo sobre la base es un saneador que nadie ha
revisado.

Y después de cada aplicación hay que **redeclarar el manifiesto**
(`HANDS_DB_COMMIT` y `HANDS_DB_SHA256`), que es un commit aparte y posterior:
el fichero se commitea primero, y el manifiesto apunta a ese commit después.
