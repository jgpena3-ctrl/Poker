# Resumen del trabajo de remediación

Sección desde `5905fe0` hasta `311f226`. **19 commits**, 44 ficheros
modificados, +6473 / −1121 líneas, 16 ficheros nuevos. Suite: **513 → 591**
tests (1 skip).

Todas las cifras de este documento están medidas y son reproducibles con los
scripts que se citan. Cuando algo no se pudo medir, se dice.

---

## 1. Procedencia de los ficheros derivados

| antes | después |
|---|---|
| `hands_used` copiaba la constante nominal `RELIABLE_HANDS` | n.º **real** de manos, en `motor/_procedencia.py` |
| una sola métrica, ambigua | `hands_input` (recibidas) vs `hands_used` (aportaron observación) |
| `hands_window` = f(número) | derivado de `hands_input`, que es lo que define la ventana |
| `arbol_sucio` con falsos positivos | acotado a las rutas fuente |
| git fallaba ⇒ "árbol limpio" | tri-estado `True` / `False` / `None` |

Ejemplo del bug, construido con 50 manos:

```
postflop 50 manos   -> hands_used: 50     (antes decía 900)
ventana completa   -> input=900  used=874  ventana=reliable_only
```

`_procedencia` también-duplicado en dos módulos pasó a ser común, y se añadió
`data/preflop_matrices.json` a las rutas relevantes: es **fuente** (el prior de
`player_ranges._prior_grid`), aunque tenga toda la pinta de derivado.

---

## 2. Correcciones de datos sobre `hands_db.jsonl`

`tools/aplicar_correcciones.py`, con nueve garantías: precondiciones estrictas,
idempotencia, backup verificado por SHA-256, procedencia diferenciada, inserción
en el lugar lógico, `--dry-run` por defecto, diff explícito, verificación
post-escritura y rollback automático.

| | qué | resultado |
|---|---|---|
| **CM-001** | `H_0141`: importe de la subida UTG, `27.0` → `2.7` (OCR) | 1 mano |
| **CM-003** | check del BB **inferido**, marcado `inferred: true` | 26 manos |

```
bb_check   310 -> 336   (+26)   sobre 1280 manos
ninguna otra categoría cambia
nº de manos: 1280 -> 1280
```

Los 26 checks **no** reutilizan `amount_type`: marcarlos `observed` sería
mentir. Reejecutar el script detecta la migración aplicada y no escribe nada;
un estado a medias aborta. Reversión documentada con hashes en
`DOCS/MIGRACION_CM001_CM003.md`.

### El inventario estaba mal: 41 → 26

`auditar_bb_check.py` clasificaba con `x[1] != 'b' or x[3]`, que trata
**cualquier** `'b'` del BB como su ciega. En 15 de las 41 la entrada `BB b`
está **después** de acciones voluntarias — y la ciega no puede ir ahí. El motor
lee eso como una subida del BB.

Preguntar al motor en vez de a una reimplementación de su criterio fue lo que
destapó la diferencia. La auditoría ahora usa `preflop_events`, con lo que
inventario y motor no pueden divergir.

### Bug del motor: la ciega se decidía por importe

`_es_ciega_bb` exigía `amount <= bb` con `bb = 1.0` nominal. Rechazaba **4**
manos con ciega real de 2.5–92.0 y `BB b` en el índice 0, y les atribuía
subidas que probablemente no ocurrieron. La condición era además redundante:
sin acción voluntaria previa, un `BB b` no puede ser una subida.

Efecto: los 4 `open` espurios del BB son 0. Los tres modos de fallo de
`_equity_vs_rival` tienen ahora test — el tercero no lo tenía, y el test que
creía cubrirlo recorría otra rama.

---

## 3. Contrato canónico de `pending`

`pending` se calculaba **cinco veces**, con dos semánticas incompatibles. Y la
función no era autosuficiente: con el default `()` devolvía `[]`, que se lee
como "nadie pendiente" cuando es "nadie me dijo quiénes son".

```python
def pending_positions(acts, hero_pos, activos) -> List[str]:
    """sigue en la mano Y no ha actuado en esta calle Y no es el hero"""
```

`activos` es **obligatorio y sin default**: omitirlo es un `TypeError`, falla
ruido en vez de mentir en silencio. Los tres estados son explícitos:

| entrada | `pending` | `pending_known` |
|---|---|---|
| omitido | — | `TypeError` |
| `None` | `[]` | `False` |
| `[]` | `[]` | `True` |

| | antes | después |
|---|---|---|
| sitios que calculan el conjunto | 5 | **1** |
| vocabulario de roles | 4 constantes, 0 usos en producción | **eliminadas** |
| alias `checkers` (= `checkers_secondary`) | trampa para futuros consumidores | **eliminado** |

`pending_known` se produjo primero y **no lo leía nadie**: se perdía igual. Se
llevó al registro sombra, con la nota de que ningún consumidor lo exploitaba
todavía.

---

## 4. `equity_main` en la ruta viva

`equity_main` estaba cableado dentro de `recommend()`… y **`asistente_live` no
llama a `recommend()`**: tiene su propia ruta con `rules.plan` +
`select_best`. El único llamador de producción de `recommend()` es
`run_demo()`. La conclusión del inventario inicial era incorrecta y se
corrigió.

El productor (`_rango_main` + `_equity_main_sombra`) escribe **solo** sobre el
dict del registro sombra. No toca `evs`, ni `rp`, ni `select_best`.

### Dos campos que mentían

**`equity_main_source` valía siempre `'main'`.** `_equity_vs_rival` devolvía
`getattr(rs, 'position', '') or 'main'`, y `RangeState` nace sin `position`:
el campo documentado como "identidad del rival" no llevaba identidad. Ahora el
productor la fija, y la ausencia se declara con el centinela `SIN_POSITION`
— que vive en `ranges.py`, donde vive la clase — en vez de inventarse un
nombre.

**`equity_main_note` mezclaba código y texto libre.** Ahora el código va en
`note` y el detalle en `note_detail`, y el código se valida contra
`CODIGOS_EQUITY_MAIN`. Un motivo fuera de vocabulario se marca `unknown`
**conservando el texto**: ni se pierde información ni se finge que sea un
código.

Seis casos de fallo, todos dejan la decisión intacta y anotan motivo. Ninguno
devuelve `0.0` como sustituto.

---

## 5. Alcance multiway (F7.1)

`tools/inventario_multiway.py`, con la regla de clasificación fijada y
reproducible.

| | puntos |
|---|---|
| HU | 702 |
| MULTIWAY | 304 |
| no clasificables | 1694 |

Los no clasificables, desglosados: **1368** calles sin acciones (check-check,
no hay decisión que tomar), **305** hero solo en el bote, **21** sin hero.

**El multiway entra al motor en silencio**: no hay ninguna guarda de la forma
`n_players > N`. `n_players` solo cambia los *sizings* vía `rules._multi_sizes`;
no toca rango ni equity, que siguen siendo de **un** rival.

`RangeState.union()` suma masas sin normalizar (medido: dos rangos uniformes
dan `2.000` por combo, masa total 2652). Su único uso en producción es
`_build_multiway_range`, que `asistente_live` nunca activa.

### El hallazgo que cambia la decisión de F7.2

| | MW en el bote | MW **pueden actuar** |
|---|---|---|
| total | 297 | **169** |

Un rival all-in está en el bote pero no responde a una decisión. El all-in
**reclasifica 128 spots** de multiway a HU: el multiway baja del 29,7% al
**16,8%**. Los dos conceptos no son intercambiables.

También: usar `players[].active` (estado final de la mano) habría dicho **1308**
multiway donde hay 304 — un factor de **4,3×** de inflación.

---

## 6. Calidad de datos versionados

`tools/clasifica_data.py` clasifica `data/` por evidencia: fuente, derivado o
runtime. Se sacaron del control de versiones **5 ficheros** que no lo eran
(telemetría del modo sombra y 4 salidas de herramientas). El criterio: ¿se lee
como entrada? → fuente; ¿solo se escribe al usar el sistema? → runtime.

---

## 7. Bugs encontrados midiendo

Ninguno se habría visto leyendo el código. Todos salieron al verificar un
instrumento contra el dato real:

| bug | cómo apareció |
|---|---|
| `checkers_secondary` siempre `()` en `anchor_match` | agrupaba 5 muestras en 1 cubo donde había 2 escenarios |
| `equity_main_source` siempre `'main'` | el campo no llevaba identidad |
| `pending_known` sin lectores | se producía y se descartaba |
| `HU = 0` en el inventario | rama inalcanzable (`rivales <= 0` con mínimo 1) |
| test de invariancia vacío | `_asis_postflop` pisa `rec.hand`: el productor no se ejecutaba |
| `'importe_sobre_nominal'` muerto | detector de regresión, documentado como tal |
| `1308` vs `304` multiway | el docstring declaraba una regla que el código no cumplía |

---

## 8. Los instrumentos, verificados

Cinco instrumentos de medida fallaron en esta sección. Se corrigieron
verificándolos contra el dato real:

- **El filtro de docstring** reportó **0** usos de `union()` en producción
  cuando había 1: un `"""` suelto no cerraba el bloque.
- **El test de vocabulario con AST** tenía su propio falso positivo
  (`getattr(rs, 'position', '')` tomado por un código de motivo) y luego no
  encontraba ninguno, porque los retornos son tuplas.
- **La sonda de regresión** apuntaba a otra forma de la llamada.
- **El guard anti-vacuidad** no era la primera comprobación: un fallo previo
  lo saltaba.
- **`clasifica_data.py`** daba falsos positivos en la dirección peligrosa
  ("nadie lo escribe" invita a borrar algo vivo): 4 de 15 sin autor.

Los guards se verifican simulando la regresión que deben detectar. El
extractor de códigos del AST se autoverifica. Un instrumento que no se
demuestra capaz de fallar no puede usarse para decir que algo está bien.

---

## 9. Método

- **Medir antes de concluir.** Cada bloque empieza por inventario, no por
  código. Dos inventarios corrigieron su propia conclusión.
- **Verificar el instrumento.** La observación se repite: el error más caro
  no es medir mal, es *creer* que se mide bien.
- **Compilar antes de escribir.** Dos veces escribí un fichero y solo después
  compilé; `io.open(p, 'w')` trunca antes de validar, y un `newline`
  mal escapado dejó un fichero de test a 0 bytes.
- **Compromiso justo.** Cuando el arreglo era desproporcionado (`position`
  obligatoria: 40 construcciones para tapar un fallback de uno), se documentó
  la deuda en vez de gastar el churn.

---

## 10. Abierto

| | |
|---|---|
| **CM-004** | **RESUELTO, por reinterpretación** (`CM004_REINTERPRETACION.md`). El defecto de orden ya no existe en ninguna de las 1280 manos. Pero se corrigió **a mano y sin original**: 17 son un cambio de etiqueta con una regla exacta, y **6 reconstruyen el preflop** (`H_0039`, `H_0051`, `H_0067`, `H_0109`, `H_0143`, `H_0263`). La Opción A de `DECISION_CM004.md` quedó **refutada**: su condición 1 —las 23 intactas— dejó de cumplirse 33 minutos después de firmarse. |
| **CM-002** | `H_0350`, cartas ausentes. Se normalizó el centinela `'-'` a `''`, que **no** es reconstruir las cartas. Las cartas siguen sin saber. |
| **F7.2** | Contrato F7.2.a **firmado** (`CONTRATO_F72A.md`). La política multiway **no está implementada** y el motor sigue entrando en multiway en silencio. Cifra vigente: **44,6 %** (226 de 507). |
| **Fase D** | Calibración. CM-004 ya no la bloquea como *defecto conocido*, pero la ventana de 877 descansa en un motivo que **ya no es el que se escribió**: las 23 se reinterpretaron, así que el defecto de orden desapareció, y su sustituto tampoco tiene original. Decidir si vuelven a la ventana es una decisión **abierta**, y tiene coste de recálculo. siguen bloqueándola, además: CM-003 y CM-004 se anulan en dirección pero no en magnitud, y el motor sigue entrando en multiway en silencio (política F7.2 sin implementar). |
| `select_best` con `evs` vacío | **resuelto**: contrato C4 firmado (`CONTRATO_C4.md`). Un EV no finito se ignora como candidato; si no queda ninguno, lanza `EvInvalido` en vez de devolver una acción inventada. |
| `RangeState.position` | **cerrado** (2026-10-14). Nace en `SIN_POSITION` en vez de la cadena vacía. Cuesta **una línea**, no 49: el valor por defecto del constructor, y el único consumidor de producción ya tratarse el centinela. |
| `H_0970` | **pendiente**: el recorte de `winner` quita al BB de un bote que sí ganó. Valor recomendado `['hero', 'p1']`. Declarado en `tools/verificar_cm004.py`. Fuera de la ventana de 900, así que no mueve ninguna cifra. |

> **Aviso de vigencia — la sección 5 de este documento NO es vigente.**
>
> Describe el multiway «que puede responder» con una regla que luego se auditó y se encontró mayoritariamente falsa. Sus cifras — 297, 169,
> 16,8 % y «el all-in reclasifica 128 spots» — se conservan como **registro de lo que se midió en aquel
> momento**
>, no como base para decidir.
>
> Han cambiado dos cosas desde entonces, y por eso ninguna cifra de la
> sección 5 es comparable con las actuales:
>
> 1. **Qué se cuenta.** F7.1 contaba *calles con acciones*. Ahora se cuentan
>    **acciones del hero**: si apuesta y luego decide otra vez ante una
>    resubida, son dos puntos. Y una calle donde el hero ya foldeó no
>    es ninguna decisión.
> 2. **Cómo se cuenta.** F7.1 contaba por calle. Ahora es por **instante**,
>    respetando el orden real de las acciones.
>
> ### La cifra vigente: **45,9 %**
>
> | | |
> |---|---|
> | HU (no fold) | 281 |
> | **MULTIWAY (no fold)** | **238** |
> | denominador de política | **519** |
> | folds excluidos (deciden, pero no consultan equity) | 93 |
> | cota superior | 267 |
>
> Ventana de **877** manos. Puntos de decisión: **672**.
>
> **Recalculada el 2026-10-14.** Antes publicaba 226/507 = 44,6 %. El
> fichero pasó de 1280 a 1258 líneas y la ventana de 877 contiene ahora
> otras 70 manos: el denominador subió a 519 y el **porcentaje pasó de 44,6 %
> a 45,9 %**. No es un redondeo, es otra muestra. Ver `RANGO_VIGENTE.md`.
>
> **16,8 % y 45,9 % llevan a políticas opuestas.** Con el primero el multiway
> es un caso marginal que se puede ignorar; con el segundo es casi la mitad de
> las decisiones y no se puede seguir entrando en él en silencio.
>
> Fundamento y contrato: [`CONTRATO_F72A.md`](CONTRATO_F72A.md) §5.5.
> Auditoría reproducible: [`AUDIT_NOPUEDE_ACTUAR.md`](AUDIT_NOPUEDE_ACTUAR.md).

---

## Documentos de referencia

| | |
|---|---|
| `MIGRACION_CM001_CM003.md` | qué se corrigió, con hashes y reversión |
| `CORRECCIONES_MANUALES.md` | CM-001 a CM-004, con el impacto combinado |
| `INVENTARIO_PENDING.md` | las 5 fuentes de `pending` y el contrato canónico |
| `F62B_INSERCION.md` | las 4 preguntas del punto de inserción y el resultado |
| `AUDIT_CONSUMIDORES.md` | por qué `inferred: true` sobrevive al pipeline |
| `DATA_FUENTE_VS_RUNTIME.md` | qué es fuente y qué es runtime en `data/` |
| `AUDIT_NOPUEDE_ACTUAR.md` | **INC-001**: representación real del all-in, el 14,6 % de precisión de la regla vieja, y el intervalo 225–276 que sustituye al 169 |

Y los instrumentos, que son ejecutables:

```
python tools/aplicar_correcciones.py          # dry-run (por defecto)
python tools/auditar_bb_check.py
python tools/auditar_consumidores.py
python tools/inventario_pending.py
python tools/inventario_equity_main.py
python tools/inventario_multiway.py
python tools/clasifica_data.py
```
