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
| **CM-004** | 23 manos con la ciega del BB después de acciones voluntarias. El motor les asigna una subida que puede no haber ocurrido. **No migrable**: corregirlo exigiría inventar un orden. Alternativa: regrabar. |
| **CM-002** | `H_0350`, cartas ausentes. No verificable sin el pantallazo; no reconstruir. |
| **F7.2** | Decidir la política multiway sobre los datos de F7.1 (169 spots realmente multiway, no 297). |
| **Fase D** | Calibración. **Bloqueada en parte por CM-004**: CM-003 hace al BB más pasivo y CM-004 más agresivo; se anulan en dirección pero no en magnitud, así que el perfil del BB tiene un error de magnitud desconocida. |
| `select_best` con `evs` vacío | contrato C4 sin especificar. |
| `RangeState.position` | sigue naciendo vacía; 40 construcciones, 4 la pasan. Deuda documentada. |

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
