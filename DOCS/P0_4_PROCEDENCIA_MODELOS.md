# P0-4 · Procedencia y compatibilidad de modelos (sombra)

**Estado:** auditoría y contrato implementados en modo sombra. No se bloquean
consultas live ni se cambian modelos, recomendaciones o artefactos.
**Base aceptada:** P0-4 original en `b59d369`, complemento de herramientas
auxiliares en `fa6539c`; este documento incorpora el cierre de los defectos
detectados al revisar esa entrega.
**Auditor:** `tools/auditar_procedencia.py` (`--json`).

## 0. Correcciones de este cierre

La revisión de `b59d369`/`fa6539c` encontró defectos concretos que se corrigen
aquí, sin tocar datos ni modelos:

1. El documento tenía un marcador `*** End Patch` commiteado al final.
2. El inventario de la sección 2 y los casos de la sección 6 seguían diciendo
   `unknown` para las dos herramientas auxiliares, contradiciendo su sección 9.
3. La matriz de compatibilidad estaba escrita a mano; ahora se calcula desde
   los envelopes.
4. Faltaban tres de los siete derivados históricos
   (`preflop_stats.json`, `profiles.json`, `observations.json`), las etiquetas,
   los priors, los rangos y los lectores de artefactos.
5. El campo `window_hash` existía pero nunca se rellenaba.
6. `build_models` estaba marcado `verified`, contradiciendo que B1 declara la
   reproducción de la base como no demostrada y el snapshot como provisional.
7. Los envelopes históricos heredaban el hash de la base actual, que es una
   inferencia: un artefacto histórico no registra con qué base se construyó.
8. La prueba de no-cambio solo comparaba un campo de `meta`; ahora compara
   tablas, evidencia, etiquetas y un vector de probabilidad completo.

## 1. Contrato de procedencia

`motor/provenance_contract.py` define `ProvenanceEnvelope` con estos campos:
componente, tipo, ruta de origen, base de datos y hash de base, manos recibidas,
manos usadas, observaciones, ventana, identificador y hash de ventana, commit y
estado sucio del código, versión del contrato de clasificación, versión de la
política de elegibilidad, procedencia de priors y rangos, fecha de construcción,
origen, estado, clasificación, hash del artefacto, hash canónico esperado y
coincidencia, campos requeridos/presentes/ausentes y notas.

Estados: `verified`, `partial`, `unknown`, `incompatible`, `historical`,
`rebuilt`. Orígenes: `rebuilt_from_current_base`, `historical_derivative`,
`static_table`, `unknown`.

Reglas:

- Un campo ausente queda en `None`; nunca se rellena por inferencia.
- La falta de un campo obligatorio no se convierte en compatibilidad implícita.
- Un artefacto histórico identificado por hash sigue siendo histórico: no pasa a
  ser compatible con la base actual.
- El hash de ventana solo se rellena si el hash de la base actual y el corte
  seleccionado coinciden con `data/calibration_window.json`.

Clasificación exigida a herramientas auxiliares: `historical_only`,
`current_only`, `explicit_modes`, `not_suitable`, `unknown`.

## 2. Fuente de la ventana y de la base

Hechos declarados, no inferidos:

| Dato | Valor |
|---|---|
| Base | `data/hands_db.jsonl` |
| SHA-256 de la base | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| Líneas totales | 1.344 |
| Regla de ventana | primeras 900 líneas físicas; JSON válido con `players` y `streets`; se excluyen las 23 CM-004 |
| Manos válidas en el corte | 900 |
| Exclusiones | 23 |
| Ventana seleccionada | 877 |
| SHA-256 de las líneas seleccionadas | `ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed` |
| `calibration_window.status` | `provisional` |
| `calibration_window.provenance_status` | `unverified: B1 reproduction from c1c1370 with the 11 versioned scripts failed` |

Consecuencia: la selección de 877 es verificable por hash, pero la reproducción
exacta de la base desde el manifiesto declarado no está demostrada. Por eso
`build_models` es `partial`, no `verified`.

## 3. Inventario componente × fuente × procedencia

### 3.1 Reconstruido en el build actual

| Componente | Fuente | Base/hash | Manos | Ventana/hash | Commit | Contrato | Prior/rango | Estado |
|---|---|---|---|---|---|---|---|---|
| `build_models()` | `motor/asistente_live.py::build_models` | `hands_db.jsonl` / `3f0e7e5e…` | 877 | `reliable_only` / `ea99bae…` | actual | P0-1 shadow + P0-2 shadow | Oracle y rangos desde las mismas manos | `partial` |
| `oracle_priors` | `motor/behavior.py::build` + `Oracle` | `hands_db.jsonl` / `3f0e7e5e…` | 877 | `reliable_only` / `ea99bae…` | actual | P0-1/P0-2 en sombra | tablas granular/por_facing/label/población | `partial` |
| `ranges` | `ProfileRangeModel.from_hands` + `PostflopRangeModel.from_hands` | `hands_db.jsonl` / `3f0e7e5e…` | 877 | `reliable_only` / `ea99bae…` | actual | P0-1/P0-2 en sombra | matrices preflop sin procedencia + Oracle inyectado | `partial` |

`build_models(verbose=False)` construye etiquetas con
`Profiles.from_hands(hands)`, `range_model`, `oracle` y `postflop_model` desde
la misma lista de manos. Después inyecta el Oracle compartido en
`postflop_model._oracle`.

### 3.2 Los siete derivados históricos

Los siete ficheros están intactos y sus hashes coinciden exactamente con los
`canonical_sha256` declarados en `data/calibration_window.json`. Coincidir con
el artefacto declarado no demuestra que su build sea reproducible ni que sean
compatibles con la base actual: el estado de derivados declarado es
`stale relative to current base; regenerated on a copy, not adopted`.

| Componente | Fichero | Manos declaradas | Hash canónico | Commit del meta | Estado |
|---|---|---|---|---|---|
| `profile_ranges` | `data/profile_ranges.json` | 877 (usadas 866, sello legacy) | `add0e899…` | `0fcceed`, árbol sucio | `partial` |
| `postflop_ranges` | `data/postflop_ranges.json` | 877 (usadas 866, sello legacy) | `1db355f9…` | `0fcceed`, árbol sucio | `partial` |
| `preflop_stats` | `data/preflop_stats.json` | 877 (campo `hands`) | `53fae60a…` | no declarado | `partial` |
| `player_stats` | `data/player_stats.json` | no declarado | `ae6babbc…` | no declarado | `partial` |
| `profiles` (etiquetas) | `data/profiles.json` | no declarado | `24037cc5…` | no declarado | `partial` |
| `behavior` | `data/behavior.json` | 877 (campo `hands`) | `efe7b9d6…` | no declarado | `partial` |
| `observations` | `data/observations.json` | no declarado; 8.742 observaciones | `86ab8c2d…` | no declarado | `partial` |

Ninguno de estos envelopes hereda el hash de la base actual: el artefacto no lo
registra. `hands_used=866` es el sello legacy del artefacto y no un conteo de
contribuyentes postflop. Las 8.742 observaciones históricas tampoco son las
1.388 observaciones postflop de P0-3.

`profiles.json` provee etiquetas PEZ/TIBURÓN y perfiles; en live, `build_models`
recalcula las etiquetas desde la base actual. El artefacto histórico no se usa
como etiqueta live.

### 3.3 Tabla estática

| Componente | Fichero | Contenido | Hash | Meta/commit/fecha | Estado |
|---|---|---|---|---|---|
| `preflop_matrices` | `data/preflop_matrices.json` | 117 tablas | `075bae3a…` | ninguno | `unknown` |

### 3.4 Lectores de artefactos

| Lector | Artefacto | Comprueba procedencia | Comprueba hash | Efecto |
|---|---|---|---|---|
| `PostflopRangeModel.load` | `postflop_ranges.json` | no | no | deja `_oracle=None`; fallback 0.2 con `n>0` |
| `ProfileRangeModel.load` | `profile_ranges.json` | no | no | acepta cualquier JSON con `meta/perfil/opp/cnt` |
| `PostflopRangeModel.save` | `postflop_ranges.json` | no | no | escribe meta de procedencia, no firma la base |
| `ProfileRangeModel.save` | `profile_ranges.json` | no | no | escribe meta de procedencia, no firma la base |

### 3.5 Herramientas auxiliares

| Herramienta | Clasificación | Estado | ¿Apta para análisis actual? |
|---|---|---|---|
| `tools/diagnosticar_56_154.py` | `historical_only` | `historical` | no |
| `tools/range_lab_gui.py` | `not_suitable` | `incompatible` | no |

## 4. Matriz de compatibilidad

Calculada desde los envelopes, no escrita a mano:

| Par | Resultado | Ámbito | Motivo |
|---|---|---|---|
| `build_models` vs `profile_ranges` | incompatible | actual vs histórico | no mezclar modelo reconstruido con artefacto histórico |
| `build_models` vs `postflop_ranges` | incompatible | actual vs histórico | mismo motivo |
| `build_models` vs `behavior` | incompatible | actual vs histórico | mismo motivo |
| `build_models` vs `profiles` | incompatible | actual vs histórico | etiquetas live vs artefacto histórico |
| `build_models` vs `preflop_matrices` | unknown | desconocido | tabla sin procedencia |
| `build_models` vs `oracle_priors` | compatible | actual | misma base, ventana y commit |
| `build_models` vs `ranges` | compatible | actual | misma base, ventana y commit |
| `profile_ranges` vs `postflop_ranges` | compatible | solo histórico | ambos coinciden con los hashes canónicos declarados |
| `postflop_ranges` vs `oracle_priors` | incompatible | actual vs histórico | artefacto histórico vs Oracle actual |
| `postflop_ranges` vs `ranges` | incompatible | actual vs histórico | artefacto histórico vs rangos actuales |
| `ranges` vs `preflop_matrices` | unknown | desconocido | el prior preflop depende de una tabla sin procedencia |
| `ranges` vs `oracle_priors` | compatible | actual | misma base, ventana y commit |

`compatible` en ámbito `historical_only` significa que dos artefactos son
consistentes entre sí como conjunto histórico declarado; no significa que sean
compatibles con la base actual.

## 5. Casos reproducibles de mezcla

`mixture_cases()` devuelve estos casos y `detect_mixture()` los recalcula:

| Caso | Componentes | Veredicto | ¿Se habría bloqueado? |
|---|---|---|---|
| `reconstruido_vs_perfil_historico` | `build_models`, `profile_ranges` | incompatible | sí |
| `reconstruido_vs_postflop_historico` | `build_models`, `postflop_ranges` | incompatible | sí |
| `reconstruido_vs_behavior_historico` | `build_models`, `behavior` | incompatible | sí |
| `reconstruido_vs_matrices_sin_procedencia` | `build_models`, `preflop_matrices` | unknown | no; se habría avisado |
| `rangos_vs_matrices_sin_procedencia` | `ranges`, `preflop_matrices` | unknown | no; se habría avisado |
| `postflop_historico_vs_oracle_actual` | `postflop_ranges`, `oracle_priors` | incompatible | sí |
| `historico_vs_historico_mismo_snapshot` | `profile_ranges`, `postflop_ranges` | compatible histórico | control |

En modo sombra no se bloquea ninguna consulta live. El registro de
`would_block`/`would_warn` es la evidencia de qué se bloquearía al activar el
contrato.

## 6. Cachés e invalidación

| Caché | Ámbito | Clave actual | Debería depender también de |
|---|---|---|---|
| `_TABLES` (`preflop.py`) | proceso | `None` (singleton) | ruta + hash/mtime de matrices + `code_commit` |
| `_tables_cache` (`player_ranges.py`) | proceso | `None` (singleton) | ruta + hash/mtime de matrices + `code_commit` |
| `_scores_cache` (`PostflopRangeModel`) | instancia | bytes del board | board + `n_buckets` + `code_commit` |
| `_board_buckets` (`PostflopRangeModel`) | instancia | board | board + `code_commit` |
| `_cell_hand_ids`/`_cell_hand_counts` | instancia | celda | evidencia P0-3 + `code_commit` |
| `_poblacion` (`Oracle`) | instancia | calle | tabla `por_facing` + `min_n` + etiquetas + manos |
| `_by_label`/`_norm` (`Oracle`) | instancia | sin caché persistente | tabla `por_facing` + `code_commit` |
| `_omega` (`ProfileRangeModel`) | instancia | jugador + spot | perfiles + `SPOT_STAT` + `code_commit` |
| `_prior_grid` (`ProfileRangeModel`) | instancia | acción + posición + vs | hash de matrices + `CAT_TABLE` + `code_commit` |
| `_base_rates` (`Profiles`) | instancia | `matrices_path` | ruta + hash/mtime + `code_commit` |

Riesgo demostrado: `_TABLES`, `_tables_cache`, `_prior_grid` y `_base_rates`
sobreviven a cambios de base, etiquetas o contratos. `_poblacion` y `_omega`
sobreviven a cambios de contrato. Ninguna clave incluye hoy hash de base,
ventana, etiquetas ni versión de contrato.

## 7. `preflop_matrices.json`

El archivo se conserva intacto. Tiene solo la clave `tables`, con 117 tablas:

| Familia | Tablas |
|---|---|
| `OR` | 5 |
| `3B` | 15 |
| `4B` | 15 |
| `5B` | 15 |
| `Call` | 53 |
| `ROL` | 5 |
| `SQUEEZE` | 6 |
| `Over` | 3 |

No tiene meta, hash de base, commit ni fecha. No se puede determinar si
pertenece a la ventana de 877, a la base de 1.344 o a otra fuente. Su hash
actual es `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1`.

Es fuente de `preflop.py`, `profile.py` y `player_ranges._prior_grid`. Por
tanto, el build actual usa una tabla sin procedencia verificable: los rangos
preflop y los priors no pueden declararse `verified`.

## 8. Pérdida de inyección de Oracle en `load()`

P0-3 documentó que `PostflopRangeModel.load()` deja `_oracle=None` y usa el
fallback plano 0.2 cuando `n>0`. P0-4 no corrige ese comportamiento. El
envelope lo registra como limitación de procedencia: un artefacto cargado desde
disco no conserva el Oracle que lo construyó, de modo que la procedencia del
prior se pierde. `range_lab_gui.py` intenta paliarlo reinyectando un Oracle
reconstruido desde la base actual, lo que introduce una mezcla explícita
(artefacto histórico + Oracle actual) y es una de las razones de su
clasificación `not_suitable`.

## 9. Complemento: herramientas auxiliares

### 9.1 `tools/diagnosticar_56_154.py`

Flujo real:

- `SNAP = data/_snapshot_pre_rebuild_1b14c18` (línea 16).
- `_load(name)` abre `SNAP/<name>` y `data/<name>` (líneas 20-24).
- Compara jugadores, claves y totales de `opp`/`cnt` de `profile_ranges.json` y
  `postflop_ranges.json`.
- No importa `motor`, no construye modelos, no usa P0-1/P0-2/P0-3, no
  recomienda.

Matriz de fuentes:

| Fuente | Tipo | Uso |
|---|---|---|
| `data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json` | histórica | lado antiguo |
| `data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json` | histórica | lado antiguo |
| `data/profile_ranges.json` | histórica en disco | lado nuevo |
| `data/postflop_ranges.json` | histórica en disco | lado nuevo |

Clasificación: **`historical_only`**. Depende exclusivamente de un snapshot
histórico y de artefactos históricos. No existe separación de modos ni modo
actual; por eso su salida no puede presentarse como diagnóstico de los modelos
live actuales. Evidencia: no hay ninguna llamada a `build_models`, `Oracle` o
`load_hands` en el fichero.

### 9.2 `tools/range_lab_gui.py`

Flujo real:

- **Al auditar P0-4**, `load_models()` intentaba `ProfileRangeModel.load()` y
  `PostflopRangeModel.load()` primero, y luego reinyectaba un Oracle de la base
  actual sin verificar procedencia. Esa mezcla motivó `not_suitable`.
- **Desde P0-6**, `load_models()` falla cerrado si cualquiera de los dos JSON
  persistidos existe. No los carga ni construye un Oracle actual que se combine
  con ellos. El error declara explícitamente la mezcla rechazada. Si ambos
  ficheros faltaran, el fallback reconstruye los componentes desde las mismas
  manos de entrada; esa ruta sigue sin elevar la procedencia `partial` a
  `verified`.
- La corrección es una protección de la herramienta auxiliar, no una
  habilitación: la clasificación P0-4 continúa `not_suitable` para el modo de
  artefactos históricos y no se presentan esos modelos como actuales.
- `build_base_range()` usa `ProfileRangeModel.prob_vec` u `opening_range()`.
- `run_pipeline()` usa `PostflopRangeModel.prob_vec`, `RangeState.update` y
  `equity_vs_range`.
- El modo con JSON persistidos ahora se detiene con error claro; en fallback
  sin esos archivos, la cabecera todavía no sella hash/commit de cada modelo.

Matriz de fuentes:

| Fuente | Tipo | Uso |
|---|---|---|
| `data/profile_ranges.json` | histórica | detectada y rechazada por el guard |
| `data/postflop_ranges.json` | histórica | detectada y rechazada por el guard |
| `data/hands_db.jsonl` | actual | fallback únicamente si ambos JSON faltan |
| `data/preflop_matrices.json` | desconocida | prior preflop vía `player_ranges` |
| `Oracle` reconstruido | actual | fallback fresco desde el mismo input |
| fallback 0.2 | estático | cuando no hay Oracle y `n>0` |

En el código auditado por P0-4 eran posibles perfil/postflop históricos con
Oracle actual y perfil histórico con matrices desconocidas. Desde P0-6, la
presencia de cualquiera de los dos JSON hace que `load_models()` falle antes
de cargar modelos; esas combinaciones quedan documentadas como riesgo
histórico, no como flujo habilitado. Si ambos JSON faltan, la ruta fallback
reconstruye los tres modelos desde la misma entrada, pero sigue con procedencia
`partial`.

Cachés implicadas: `_TABLES`, `_tables_cache`, `_scores_cache`, `_poblacion`,
`_omega`, `_prior_grid`, `_board_buckets`.

Clasificación: **`not_suitable`**. En la revisión P0-4 se reprodujo una mezcla
real entre artefactos históricos y Oracle reconstruido desde la ventana actual.
P0-6 añade un guard fail-closed para JSON persistidos; el guard no eleva la
procedencia ni cambia la clasificación auxiliar a apta.

## 10. Pruebas y no interferencia

`motor/test_provenance_contract.py` verifica:

- `build_models` es `partial`, no `verified`;
- el hash de ventana coincide con `calibration_window.json`;
- los siete derivados están inventariados, coinciden con los hashes canónicos y
  no heredan el hash de la base actual;
- `preflop_matrices` queda `unknown`;
- la matriz de compatibilidad se calcula desde los envelopes;
- los casos de mezcla registran `would_block`/`would_warn`;
- las dos herramientas auxiliares tienen la clasificación exigida y su flujo;
- los lectores no comprueban procedencia;
- las cachés declaran sus dependencias de invalidación;
- la auditoría es de solo lectura: hashes de datos antes/después idénticos;
- la auditoría no muta el modelo: digest de tablas/evidencia/etiquetas y vector
  `prob_vec` idénticos antes/después.

La auditoría P0-4 es de solo lectura y no bloquea consultas live. No se
activaron P0-1, P0-2 ni P0-3. No se regeneraron derivados, calibraron modelos
ni realizaron sesiones reales.

## 11. Limitaciones abiertas

- `range_lab_gui.py` permanece `not_suitable` para los artefactos persistidos;
  P0-6 impide la mezcla con un error explícito. No se regeneraron artefactos.
- `diagnosticar_56_154.py` sigue dependiendo del snapshot histórico, que debe
  conservarse como evidencia.
- `preflop_matrices.json` sigue sin procedencia verificable y sigue alimentando
  el prior preflop actual.
- `PostflopRangeModel.load()` sigue perdiendo el Oracle y cayendo al fallback
  0.2.
- Las cachés siguen sin incluir en su clave el hash de base, la ventana, las
  etiquetas y las versiones de contrato.
- El contrato no bloquea consultas live: solo registra qué se habría bloqueado.

**Me detengo aquí para revisión.** No activar contratos ni continuar con otro
bloque automáticamente.
