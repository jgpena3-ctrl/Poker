# P0-4 · Procedencia y compatibilidad de modelos (sombra)

**Estado:** auditoría y contrato implementados en modo sombra. No se bloquean
consultas live ni se cambian modelos, recomendaciones o artefactos.
**Commit de referencia:** `a4d8d8d` (P0-3).
**Auditor:** `tools/auditar_procedencia.py` (`--json`).

## 1. Contrato de procedencia

`motor/provenance_contract.py` define `ProvenanceEnvelope`, con campos obligatorios
de procedencia: base de datos, hash de base, manos recibidas, ventana, hash de
ventana cuando existe, commit de código, estado sucio, versión de contrato de
clasificación, versión de política de elegibilidad, procedencia de priors y
rangos, fecha de construcción, origen y estado.

Estados posibles: `verified`, `partial`, `unknown`, `incompatible`,
`historical`, `rebuilt`. La ausencia de un campo obligatorio no se convierte en
compatibilidad implícita: pasa a `partial` o `unknown`.

Orígenes: `rebuilt_from_current_base`, `historical_derivative`,
`static_table`, `unknown`.

## 2. Inventario componente × fuente × procedencia

| Componente | Origen | Estado | Motivo principal |
|---|---|---|---|
| `build_models()` | Reconstruido desde base actual | verified | 877 manos fiables, commit actual, contrato y política declarados |
| `profile_ranges.json` | Derivado histórico | incompatible/partial | `hands_input=877`, commit `0fcceed`, árbol sucio; no se puede verificar compatibilidad con la base actual |
| `postflop_ranges.json` | Derivado histórico | incompatible/partial | Mismo commit histórico y ventana; no hay verificación de base |
| `behavior.json` | Derivado histórico | partial/unknown | Sin sello de procedencia |
| `player_stats.json` | Derivado histórico | partial/unknown | Sin sello de procedencia |
| `preflop_matrices.json` | Tabla estática | unknown | Sin meta, hash, commit ni fecha; no se sabe si es de 877, 1344 u otra ventana |
| `diagnosticar_56_154.py` | Herramienta auxiliar | unknown | Auditar separación modo histórico/actual |
| `range_lab_gui.py` | Herramienta auxiliar | unknown | Auditar consumo de artefactos históricos vs actuales |

Los siete derivados históricos permanecen intactos. No se reanclan, regeneran ni
se declaran compatibles con la base de 1.344 manos.

## 3. Matriz de compatibilidad

| Par | Resultado | Motivo |
|---|---|---|
| `build_models` vs `profile_ranges` | incompatible | No mezclar artefacto histórico con modelo reconstruido |
| `build_models` vs `postflop_ranges` | incompatible | No mezclar artefacto histórico con modelo reconstruido |
| `profile_ranges` vs `postflop_ranges` | unknown | Ambos históricos (`0fcceed`), sin verificación de base |
| `preflop_matrices` vs `build_models` | unknown | Matrices sin meta; no se sabe si son de 877/1344 |
| `behavior` vs `build_models` | unknown | `behavior.json` sin sello de procedencia |

Cuando dos componentes tienen procedencias incompatibles o desconocidas, el
contrato las identifica y evita presentarlas como un modelo coherente. En modo
sombra no se bloquean consultas live; se registra qué habría sido bloqueado.

## 4. Cachés e invalidación

| Caché | Ámbito | Clave actual | Dependencias que deberían formar parte de la clave |
|---|---|---|---|
| `_TABLES` (`preflop.py`) | Proceso | `None` (singleton) | ruta de matrices, mtime/hash, `code_commit` |
| `_tables_cache` (`player_ranges.py`) | Proceso | `None` (singleton) | ruta de matrices, mtime/hash, `code_commit` |
| `_scores_cache` (`PostflopRangeModel`) | Instancia | bytes del board | board, `n_buckets`, `code_commit` |
| `_poblacion`/`_label_level` (`Oracle`) | Instancia | calle | tabla facing, `min_n`, etiquetas |
| `_omega` (`ProfileRangeModel`) | Instancia | jugador+spot | perfiles, `SPOT_STAT` |
| `_base_rates` (`Profiles`) | Instancia | ruta de matrices | ruta, mtime/hash, `code_commit` |

Estas cachés pueden sobrevivir a cambios de base, ventana, etiquetas o contratos.
La auditoría documenta las invalidaciones necesarias; no se introducen todavía
cambios que alteren probabilidades, modelos o recomendaciones.

## 5. `preflop_matrices.json`

El archivo se conserva intacto. Tiene solo la clave `tables` con 117 tablas y
**no tiene meta, hash de base, commit ni fecha**. No se puede determinar si
pertenece a la ventana de 877, a la base de 1.344 o a otra fuente. Su hash
actual es `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1`.

No se asume compatibilidad con el modelo actual. La falta de procedencia
verificable queda explícita en el envelope y en la auditoría.

## 6. Casos reproducibles

- Mezclar `build_models()` (reconstruido) con `profile_ranges.json` histórico
  (`0fcceed`, árbol sucio) debe marcarse incompatible.
- Mezclar `build_models()` con `postflop_ranges.json` histórico debe marcarse
  incompatible.
- `preflop_matrices.json` sin meta no puede declararse compatible con 877 ni
  con 1344.
- `behavior.json` y `player_stats.json` sin sello no pueden verificarse.
- Herramientas auxiliares (`diagnosticar_56_154.py`, `range_lab_gui.py`) quedan
  en estado unknown hasta auditar su separación de modos.

## 7. Relación con la pérdida de inyección de Oracle en `load()`

P0-3 documentó que `PostflopRangeModel.load()` deja `_oracle=None` y vuelve al
fallback plano 0.2. P0-4 no corrige ese comportamiento; lo registra como
limitación de procedencia: un artefacto cargado desde disco no conserva la
procedencia del Oracle que lo construyó. El envelope marca esta pérdida y el
contrato deja explícito que no se infiere compatibilidad.

## 8. Pruebas y no interferencia

`motor/test_provenance_contract.py` verifica el envelope, los estados de
artefactos históricos, la procedencia desconocida de `preflop_matrices`, la
matriz de compatibilidad, el inventario de cachés, la auditoría de solo lectura
y que el envelope no modifica modelos ni recomendaciones.

La auditoría P0-4 es de solo lectura y no bloquea consultas live. No se
activaron P0-1, P0-2 ni P0-3. No se regeneraron derivados, calibraron modelos
ni realizaron sesiones reales.

## 9. Complemento: auditoría de herramientas auxiliares

### 9.1 `tools/diagnosticar_56_154.py`

Flujo real:
- Lee `data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json` y
  `data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json`.
- Lee `data/profile_ranges.json` y `data/postflop_ranges.json` actuales.
- Compara jugadores, claves y totales de `opp`/`cnt`.
- No lee la base canónica, no construye modelos, no usa P0-1/P0-2/P0-3, no
  recomienda.

Clasificación: `historical_only`. Depende exclusivamente del snapshot histórico
`_snapshot_pre_rebuild_1b14c18` y de los artefactos actuales como comparador
histórico. No existe separación de modos ni modo actual; por eso no puede
presentarse como diagnóstico de los modelos live actuales. Su salida sirve para
explicar el salto 56 → 154 jugadores, no para auditar el modelo reconstruido.

### 9.2 `tools/range_lab_gui.py`

Flujo real:
- `load_models()` intenta `ProfileRangeModel.load()` y
  `PostflopRangeModel.load()` primero; si existen artefactos históricos, los
  usa sin verificar procedencia.
- Si falta un artefacto, reconstruye el modelo correspondiente desde la base
  actual (`load_hands(reliable_only=True)`).
- Si `PostflopRangeModel.load()` perdió `_oracle`, lo reconstruye con
  `Oracle(build(hands, labels=dict(post.labels)))` desde la base actual.
- `build_base_range()` usa `ProfileRangeModel.prob_vec` o `opening_range()`.
- `run_pipeline()` usa `PostflopRangeModel.prob_vec`, `RangeState.update`,
  `equity_vs_range`.
- La interfaz no comunica qué fuente se está usando ni si hay mezcla.

Clasificación: `not_suitable`. Existe una mezcla previamente identificada entre
`profile_ranges.json` histórico, `postflop_ranges.json` histórico y Oracle
reconstruido desde la ventana actual. No hay separación real de fuentes ni
comprobación de compatibilidad, y la GUI no comunica claramente qué modelo está
utilizando. No se declara compatible por tener datos disponibles o estructuras
técnicamente legibles.

### 9.3 Limitaciones abiertas

- `range_lab_gui.py` sigue pudiendo mezclar artefactos históricos y Oracle
  actual; no se corrige en este bloque.
- `diagnosticar_56_154.py` sigue dependiendo del snapshot histórico, que debe
  conservarse como evidencia.
- Ninguna de las dos herramientas reconstruye modelos con el envelope P0-4;
  su clasificación queda documentada y probada, no activada.

**Me detengo aquí para revisión.** No activar contratos ni continuar con otro
bloque automáticamente.
*** End Patch
