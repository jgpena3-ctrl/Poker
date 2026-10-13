# Documento de proyecto — Motor de póker

> Estado: `82b4fab` (HEAD = `origin/main`) · 17 commits · suite: **445 passed, 1 skipped**
> Actualizado: 2026-10-13
>
> ⚠️ **Todas las cifras de este documento están medidas sobre las primeras 900 manos**, la única ventana
> con buena prosecución de acciones. El código, en cambio, usa las 1280. Ver §1 "Ventana de datos fiable".

---

## 1. Qué es el proyecto

Un asistente de póker que **lee la mesa por captura de pantalla** y devuelve una recomendación de acción
(`fold / check / call / bet / raise / all-in`) **antes de que caduque el turno**. El sistema **no ejecuta
nunca**: sólo observa, calcula y muestra.

Tres ideas gobiernan todo el diseño:

1. **No hay números inventados.** Si un modelo no tiene respaldo empírico, la función devuelve `None` o
   lanza. No se rellenan huecos con heurísticas silenciosas.
2. **Un cambio de modelo se observa antes de actuar.** Todo lo dudoso va primero a *modo sombra*: se
   registra, se compara, y no toca la decisión. Verificado por test.
3. **La base estadística se audita antes de calibrar.** Un peso bonito sobre datos mal clasificados es
   peor que no tener peso.

### Ventana de datos fiable — leer antes que nada

> ⚠️ **La base de datos está en mantenimiento y corrección.** Sólo las **primeras 900 entradas** de
> `data/hands_db.jsonl` (lineas 1–900, `H_0001`…`H_0902`) tienen **buena prosecución de acciones**.
> Las **380 restantes** pueden tener errores en las acciones y **no deben usarse para medir nada**.

El corte no es arbitrario: **el propio fichero muestra la discontinuidad exactamente en H_0903.**

| Porcentaje de manos con ciega del BB insertada | Manos |
|---|---|
| primeras 900 | 586 (65.1%) |
| líneas 901–950 | **50 de 50 (100%)** |
| últimas 380 | 376 de 380 (98.9%) |

Del mismo modo, los ganadores múltiples saltan de **2.7%** en la ventana fiable a **18.0%** en el
total. Es la firma de dos convenciones de grabación distintas, no de una distribución real.

**Y nada en el código respeta este corte.** `learn.load_hands()` no tiene parámetro de límite, y sus
**15 consumidores** cargan las 1280 manos:

| Consumidor | Ventana que usa |
|---|---|
| `asistente_live.build_models()` | **1280** ← los modelos que recomienda en vivo |
| `behavior`, `observations`, `profile`, `stats`, `learn`, `db_health` | **1280** |
| `player_ranges`, `postflop_ranges`, `range_lab_gui` | **1280** |
| `tools/auditar_anchor.py` | **1280** |
| `tools/medir_multiway.py` | **1280** (lee el fichero directamente) |
| `tools/auditar_sombra.py` | `load_hands()[:400]` ✅ dentro de la ventana |

Consecuencia: **todos los derivados en `data/*.json` y todos los modelos en vivo están contaminados**
con las 380 manos no fiables. Cualquier cifra de este documento que no diga explícitamente "primeras 900"
debe leerse como *provisional*.

### Flujo de datos

```
captura de pantalla
   └─ tools/capture_live.py + lector_estado.py        →  State (pantallazos)
        └─ recorder/recorder_live.py                  →  data/hands_db.jsonl   (1280 manos)
             └─ motor/learn.py                        →  categorías preflop + denominadores
                  └─ motor/stats.py                   →  VPIP/PFR/3BET/C-BET/barrel/WTSD
                       └─ motor/profile.py            →  etiqueta PEZ/TIBURON + confianza Beta
                            └─ motor/behavior.py      →  Oracle P(A|C)
                            └─ motor/player_ranges.py  →  P(A|H, spot, perfil) preflop  ← SIN AUDITAR
                            └─ motor/postflop_ranges.py→  P(A|H, calle, textura) postflop
                                 └─ motor/recommend_loop.recommend()
                                      ├─ motor/ranges.py       →  RangeState (1326 combos)
                                      ├─ motor/preflop.py      →  matrices 13×13
                                      ├─ motor/situation.py    →  equity, pot odds, SPR, textura
                                      ├─ motor/rules.py        →  10 acciones → 3 candidatas ← SIN AUDITAR
                                      ├─ motor/decision.py     →  EV por acción
                                      ├─ motor/hand_state.py   →  fuerza / draws / hand_role
                                      ├─ motor/hierarchy.py    →  modo sombra multiway (NO altera EV)
                                      └─ motor/panel.py        →  salida por consola
                                           └─ motor/asistente_live.py →  recomendación por hero
```

### Dataset

| Artefacto | Tamaño | Contenido |
|---|---|---|
| `data/hands_db.jsonl` | 1280 manos | fuente de verdad; primeras 900 declaradas como corregidas |
| `data/preflop_matrices.json` | 328 KB | matrices 13×13 por acción/posición |
| `data/behavior.json` | 20 KB | tablas P(A\|contexto) del Oracle |
| `data/observations.json` | 1.7 MB | una observación por decisión |
| `data/profile_ranges.json` | 80 KB | P(A\|H, spot, perfil) |
| `data/golden.json` | 37 KB | respuestas esperadas del OCR |
| `data/shadow_hierarchy.jsonl` | — | salida del modo sombra (append) |

Perfiles detectados: **181 jugadores → 106 TIBURON / 75 PEZ**. `Jarduan` (hero) cae en TIBURON (n≈1260).

---

## 2. Módulos del motor (`motor/`, 24 módulos + 22 de test)

### 2.1 Nucleo de cartas y rangos

#### `cards.py` (119 líneas)
Encoding canónico: `'Ah'` ↔ entero `0..51`, y bitmasks de 52 bits.
- `is_card_code(code)` — filtra marcadores `'-'` / `''` que deja el recorder
- `card_id`, `card_label`, `rank_of`, `suit_of`, `cards_to_bits`, `parse_hand`, `hand_mask`, `mask_to_cards`
- `is_pair`, `is_suited`, `all_card_ids`
- **Datos:** ninguno. **Depende de:** nada (es la raíz del grafo de dependencias).

#### `ranges.py` (771 líneas)
Los 1326 combos preflop, la jerarquía de clases y el `RangeState` con update bayesiano.
- `combos_with_card(idx)`, `hand_class(idx)`, `hand_class_name`, `hand_sub_class`, `base_weight`
- `hand_class_of_label(label)`, `class_weights_vector()`, `combos_by_sub_class`, `combos_by_class`
- `validate_reach(reach, allow_empty=)`, `villain_weights(reach, ids)` — **fuente única de verdad** de pesos; lanza `RangeError`
- `class RangeState`: `.legal_mask`, `.reach_blocked`, `.weights`, `.set_known_cards`, `.nullify_blocked`,
  `.copy()`, `.union()`, `.restrict_to_combo()`, `.validate()`, `.is_empty`, `.top_hands(k)`,
  `.update(prob_action)`, `.update_with_action()`, `.norm_to()`
- `uniform_range(cards)`, `default_action_prob(hand_code, action, context)`
- `class_weights_for_reach()` — **DEPRECADO explícitamente**, devuelve ceros en rango vacío y **no tiene llamadores en producción**
- Constantes: `N_COMBOS=1326`, `BASE_WEIGHT_MAP`, `_ACTION_PROBS`, `_HAND_CLASS_NAME`, `_HAND_SUB_CLASS`,
  `_NONPAIR_SUBS`, `_PAIR_SUBS`, `other`, `_HILO_IDX`
- **Datos:** ninguno. **Depende de:** `cards`.

#### `preflop.py` (143 líneas)
Traduce las matrices 13×13 a vectores `(1326,)` listos para `RangeState.update`.
- `matrix_to_probs`, `load_tables()` (cachea en `_TABLES`), `table_key`, `has_table`
- `prob(action, pos, vs)` — **devuelve `None` si no hay tabla** (no ceros)
- `prob_or_fallback(...)` → `(vec, fuente ∈ {'table','uniform'})`
- `opening_range(pos)`, `opening_range_or_fallback(pos)`, `preload()`
- Exporta `CELL_ROW` / `CELL_COL`, usados por `player_ranges`
- **Lee:** `data/preflop_matrices.json`. **Depende de:** `cards`, `ranges`.

#### `hand_evaluator.py` (325 líneas)
Fuerza de manos de 5/6/7 cartas con score entero en base 13, vectorizado en numpy.
- `evaluate_five_batch`, `evaluate5`, `evaluate7`, `evaluate_n_batch`, `evaluate_batch`, `evaluate_hand`
- `compare_ranks`, `legal_hands(known_mask)`, `category_name(score)`, `hero_vs_range`
- Caché de la tabla C(52,5) en `~/.poker_motor/five_table.npy` (10.4 MB, ~4-6 s la primera vez;
  si no hay permiso queda sólo en memoria)
- **Depende de:** `cards`, `ranges`.

#### `hand_state.py` (183 líneas)
Clasifica la mano conocida del hero: categoría, draw y `hand_role` para filtrar acciones.
- `classify(hero_codes, board_codes) -> HandState`
- `HandState.nut_advantage()`, `range_advantage(hero_equity)` → `'HERO' | 'NEUTRAL' | 'VILLAIN'` (cortes 0.45 / 0.55)
- **Depende de:** `cards`, `hand_evaluator`.

### 2.2 Cálculo

#### `situation.py` (223 líneas)
"¿Qué significa nuestra mano?" — equity ponderada por reach, pot odds, SPR y textura.
- `equity_vs_range(hero, board, reach, ids)`, `hero_percentile`, `pot_odds(to_call, pot_before)`, `spr`
- `board_texture(board)` → `pairs / trips / flush_suits / rainbow / two_tone / monotone / straight_run`
- `class Situation`, `situation(...)`
- `_legal_ids` valida que los `villain_ids` no choquen con hero + board
- **Depende de:** `cards`, `hand_evaluator`, `ranges` (incluye `RangeError`, `villain_weights`).

#### `decision.py` (594 líneas)
EV de cada acción con respuesta modelada del rival y sorteo de runout. **Función central: `compute_evs()`**.
- `default_response(villain_eq, amount, pot) -> (fold, call, raise)`
- `class OracleResponse(oracle, label, context, fade_n=20)` — funde perfil con heurística, `alpha = min(1, n/fade_n)`
- `runout_equity(...)` — Monte Carlo conjunto determinista (seed 7)
- `EvTable.best(candidates)`
- Constantes: `BET_LABELS`, `ACTIONS`, `DEFAULT_RUNOUTS=100`, `DEFAULT_RUNOUT_COMBOS=200`,
  `TREE_STREET=60`, `TREE_FINALS=6`, `TREE_FRAC=0.5`
- **Depende de:** `cards`, `hand_evaluator`, `ranges`.

#### `rules.py` (518 líneas) — **SIN AUDITAR**
Reduce ~10 acciones de EV a 3 candidatas antes de calcular el EV (*10 → 3 → EV → 1*).
- `board_class(board)` → `'DRY' | 'SEMI_DRY' | 'WET'`
- Tabla de sizings: `CBET_SIZES`, `BARREL_SIZES`, `DONK_SIZES`, `PROBE_SIZES`, `VALUE_SIZES`
- `_multi_sizes(...)`, `_pot_before_bet`, `_raise_plan`, `_board_structure`, `_paired`
- `class RulePlan` (`spot, texture, candidates, bet_sizes, raise_to, raise_all_in, paired, structure, note, n_players`)
- `class Ctx`, `class Row`, `RULES` (9 filas por orden de prioridad), `_facing_plan`, `_apply`, `_decide`
- **`plan(...)`** — API principal, 14 parámetros
- `select_best(evs, rp=None)` — mejor acción por EV entre `rp.candidates`
- Módulo puro: no lee ni escribe ficheros. Importa `cards` **dentro de funciones** (hot path).

#### `implied_odds.py` (87 líneas)
Matemática pura de outs, pot odds e implied odds. Sin numpy, sin datos.
- `class AnalisisCall` (frozen, 10 campos), `equity_desde_outs`, `equity_regla` (regla 4-y-2),
  `pot_odds_necesarias`, `analizar_call`
- ⚠️ **No lo importa ningún módulo de `motor/` — es una isla.**

### 2.3 Orquestación

#### `recommend_loop.py` (487 líneas)
Orquestador *anytime*: construye el rango rival, calcula Situation + EV y devuelve `Recommendation` antes del deadline (8 s).
- `class Recommendation` — `.action`, `.value`, `.situation`, `.evs`, `.villain_label`, `.elapsed_ms`,
  `.stages`, `.runout`, `.rule_plan`, `.shadow`, `.hierarchy`
- `build_villain_range(...)` — HU o multiway
- **`recommend(hero_codes, board_codes, *, pot, to_call, stack, street, ...)`** — función principal, 25 parámetros
- `_hero_oop`, `_build_villain_range`, `_build_multiway_range`, `_equity_vs_rival`, `_POSTFLOP_ORDER`
- **Depende de:** `decision`, `hierarchy`, `panel`, `preflop`, `ranges`, `situation`, `rules`, `hand_state`.

#### `hierarchy.py` (514 líneas)
Instrumenta, **sin alterar la decisión**, el problema de que `RangeState.union()` mezcla rivales en vez de
distribuirlos conjuntamente.
- `texture_key(board)` → `'monotone' | 'two_tone' | 'rainbow'`
- `passive_penalty(board, street, n_checker)` — **marcado NO CALIBRADO**
- `OBSERVED_ANCHOR` — dict con `is_equity: False`, `signs_agree: False`, `records_matching_anchor: 3`,
  `records_previously_labelled_measured: 199`, `population_mismatch`
- `penalty_source(...)` → `'anchor_match' | 'partial_support' | 'none'`
- `classify_villains(acts, hero_pos, pending_positions)` → `main / aggressors / checkers_all / checkers /
  callers / pending / hero_bet / hero_pos`
- `shadow_equity(...)` — **sólo emite `equity_shadow` si `penalty_source == 'anchor_match'`**; si no, `None`
- `shadow_record(...)`, `class ShadowLog(path, enabled)` (silencioso ante `OSError`)
- **Escribe:** `data/shadow_hierarchy.jsonl` (append). **Depende de:** `situation`.

#### `panel.py` (90 líneas)
Salida por consola, inspeccionable. **Nunca alimenta** al motor de decisión.
- `format_cards`, `format_evs(evs, best_label)`, `format_situation`, `format_insight`
- **Depende de:** `decision`, `situation`.

#### `asistente_live.py` (1158 líneas)
Pipeline captura → recomendación por pantallazo (~0.5 s). **Nunca ejecuta por sí solo.**
- `build_models(verbose=True)` — construye los 4 modelos desde la DB
- `class Asistente`:
  - `.recomendacion(state, ...)` — un hero (retrocompatible)
  - `.recomendaciones(...)` — **una rec por cada hero activo**
  - `.step(state, img_arr, pil, log, on_reco, require_turn, force_reco, runout, all_heroes)` — un ciclo
  - `.run(stop_event, log)`
- Auxiliares: `_preflop_spot`, `_villain_postflop_actions`, `_hero_oop`, `_hero_is_initiator`,
  `_hand_was_raised`, `_hero_bet_facing`, `_combo_index`, `_pf_table_probs`, `_pf_freq`, `_preflop_raises`,
  `_pf_evs`, `_format_preflop`, `_heroes_conocidos`, `_cartas_bloqueantes`, `_villain_id`
- Constantes: `POLL_DEFAULT=0.5`, `HERO_NAME_DEFAULT='Jarduan'`, `HERO_PID`, `PLAYER_IDS`
- **Depende de:** 14 módulos de `motor` + `tools/capture_live.py` + `recorder/recorder_live.py`

#### `asistente_live_gui.py` (633 líneas)
GUI Tkinter del asistente: nombres por asiento, modo automático (~0.5 s) y modo manual.
- `class AsistenteLiveGUI` — `_build_ui`, `_preload_names`, `_sync_to_recorder`, `_start`/`_stop`/`_run_auto`,
  `_manual_init`/`_manual_capture`/`_manual_end_hand`/`_manual_cancel_hand`, `_poll_queue`
- **Depende de:** `asistente_live`, `tkinter`, `recorder_live`, `capture_live`.

### 2.4 Aprendizaje y calibración

#### `learn.py` (275 líneas) — **SIN AUDITAR**
Extrae frecuencias preflop por jugador: primera decisión de cada jugador, 13 categorías, 3 denominadores.
- `load_hands(path=None)` — descarta líneas rotas o sin `players`/`streets`
- `player_of_pos`, `cards_of_pos`, `hand_known`
- `classify_first_action(action, amount, raises_before, limps_before, bb) -> (cat, denom)`
- `class PreflopEvent` (`hand_id, player, pos, category, denom, amount, hand_known, cards, prereq`)
- `preflop_events(hand, bb)`, `_preflop_sequence(hand)`
- `class PreflopStats` — `.from_hands`, `.opportunities`, `.freq`, `.report`, `.to_dict`
- **Lee:** `data/hands_db.jsonl`. **Escribe:** `data/preflop_stats.json` (con `--json`)
- **Sin dependencias internas** — es la base de todo el grafo de aprendizaje.

#### `stats.py` (247 líneas)
Estadísticas de transición por jugador.
- `class PlayerStats`, `class TransitionStats` (`.from_hands`, `.report`, `.to_dict`)
- `SHOWDOWN_RE`, `MONEY_CATS`, `RAISE_CATS`, `STAT_LABELS`
- **Lee:** `hands_db.jsonl`. **Escribe:** `data/player_stats.json`. **Depende de:** `learn`.

#### `profile.py` (330 líneas)
Vector de estadísticas → bins → etiqueta PEZ/TIBURON + confianza por posterior Beta.
- `mean_stack_by_player`, `simple_label(vpip, pfr, stack_mean)`,
  `beta_mass(opp, act, lo, hi)` (scipy), `load_base_rates`
- `class PlayerProfile` — `.reliability()` (bandas 40/500/5000), `.omega(...)`
- `class Profiles` — `.from_hands`, `.report`, `.to_dict`
- Constantes: `STAT_BINS`, `PROFILE_STATS`, `HANDS_BANDS`, `STACK_FISH_BB=50.0`
- **Lee:** `hands_db.jsonl`, `preflop_matrices.json`. **Escribe:** `data/profiles.json`.

#### `observations.py` (257 líneas)
Extrae una `Observation` por decisión (calle, bote, SPR, textura, `facing`, sizing, secuencia preflop).
- `class Observation`, `lead_label(...)`, `extract_hand`, `extract_hands`, `behavior_table`
- **Lee:** `hands_db.jsonl`. **Escribe:** `data/observations.json`. **Depende de:** `learn`, `situation`.

#### `behavior.py` (305 líneas)
Cruce perfiles × observaciones → tablas P(A|C) con 4 niveles de fallback
(`granular` → `por_facing` → `label` → `poblacion`).
- `class Oracle` — `.p_action(label, street, facing, texture)`, `.for_dataset`, `.to_dict`
- `labels_from_hands`, `behavior_table`, `oracle_from_hands`, `build`, `report`, `oracle_payload`
- **Lee:** `hands_db.jsonl`. **Escribe:** `data/behavior.json`, `data/behavior_probs.json`.

#### `player_ranges.py` (287 líneas) — **SIN AUDITAR**
Modelo P(A|H, spot, perfil) preflop: grid 13×13 por (perfil, spot) con shrinkage al prior, más ajuste ω individual.
- `class ProfileRangeModel` — `.from_hands`, `.p_matrix(perfil, spot, action, pos)` (núcleo:
  `(cnt + α·prior) / (opp + α)`), `.range_matrix`, `.prob_vec`, `.p_hand`,
  `.player_omega(player, spot, fade=20)`, `.p_player`, `.prob_vec_player`, `.to_json`, `.save`, `.load`, `.report`
- Constantes: `DEFAULT_ALPHA=2.0`, `FLAT_PRIOR=0.15`, `CAT_TABLE`, `SPOT_STAT`, `GRID_RANKS`
- **Lee:** `hands_db.jsonl`, `preflop_matrices.json`. **Escribe:** `data/profile_ranges.json`.

#### `postflop_ranges.py` (299 líneas)
P(A|H, calle, facing, perfil) postflop usando buckets de fuerza del board (5 percentiles) + shrinkage al Oracle.
- `class PostflopRangeModel` — `.from_hands`, `.p_action`, `.prob_vec`, `.report`, `.to_json`, `.save`, `.load`
- `_board_ids`, `_strength_buckets`; `DEFAULT_ALPHA=2.0`, `DEFAULT_BUCKETS=5`
- **Lee:** `hands_db.jsonl`. **Escribe:** `data/postflop_ranges.json`.

#### `db_health.py` (294 líneas)
Reporte de ingesta y cobertura de `hands_db.jsonl`. **Sólo reporta, nunca borra.**
- `validate_hands(hands)` — detecta `dup_board`, `flop_corto`, `hand_id_dup`, `amount_invalido`,
  `pos_desconocida`, `carta_repetida`
- `coverage(hands, min_n)`, `snapshot_delta(hands)`, `save_snapshot(hands)`
- **Lee:** `hands_db.jsonl`. **Lee+escribe:** `data/db_health.json`.

### 2.5 Paquete

#### `motor/__init__.py` (25 líneas)
Re-exporta 15 submódulos con `from . import (...)`.
- **No lee datos ni construye modelos en el import.** Todo es lazy.
- ⚠️ El docstring documenta 15 módulos; existen 24. Faltan `rules`, `hand_state`, `hierarchy`,
  `implied_odds`, `db_health`, `asistente_live`, `asistente_live_gui`.
- ⚠️ `rules` **no está en la lista**: hoy `motor.rules` es importable sólo porque `recommend_loop` lo
  arrastra de forma diferida. Quitar `recommend_loop` de la lista rompería `motor.rules`.
- Trabajo pesado en import: `ranges.py:295` itera los 1326 combos para construir las tablas de clase.

---

## 3. Scripts de soporte

### `tools/` — OCR y captura

| Script | Función |
|---|---|
| `capture_live.py` | Captura la ventana del juego. `get_readers()`, `capture()`, `init_reader()`, `init_ms()` |
| `lector_estado.py` | **Lector principal.** `DigitReader`, `SlidingNumberReader`, `BinaryMatcher`, `StateMatcher`, `StateReader` |
| `lector_cartas.py` / `lector_cartas_v2.py` | Lectura de cartas. `CardReader`, `CardReaderV2` (v2 añade corrección de etiquetas) |
| `lector_unificado.py` | Fusión de los lectores de cartas. `CardReader` |
| `lector_numeros.py` | Lectura de números. `NumberReader` |
| `digit_ocr.py` | OCR de dígitos por template matching. `DigitOCR` |
| `ocr_rapido.py` | Variante rápida de OCR. `OcrRapido` |
| `leer_captura.py` | Volca una captura a disco. `main()` |
| `add_to_golden.py` | Añade predicciones al dataset golden. `predict_all()`, `main()` |

### `tools/` — análisis y laboratorio

| Script | Función |
|---|---|
| `medir_multiway.py` | Distribución por escenario multiway. `_gana(h)`, `_hero_pos(h)` — separa WIN% de EQUITY% |
| `auditar_sombra.py` | Auditoría de consistencia de los registros del modo sombra (script) |
| `auditar_anchor.py` | Auditoría del respaldo real del ancla de calibración (script) |
| `range_lab_gui.py` | Laboratorio interactivo de rangos. `load_models()`, `build_base_range()`, `run_pipeline()`, `top_combos()`, `bucket_dist()`, `class RangeLabGUI` |
| `calculadora_outs_gui.py` | Calculadora de outs en GUI. `CalculadoraOutsGUI` |
| `debug_juego.py` | Formatea un `State` para depuración. `fmt_state(state)` |
| `test_live.py`, `test_mano2.py`, `test_mano3.py`, `test_mano6.py`, `test_recorder_juego.py` | Playback de manos grabadas para validar el lector. `load_frame()`, `print_state()`, `print_hand()` |

### `recorder/`

| Script | Función |
|---|---|
| `recorder_live.py` | **Grabador principal.** `class LiveRecorder` — captura la partida en vivo y escribe `data/hands_db.jsonl` |
| `record_hand.py` | Grabación de una mano aislada. `get_position(player_id, btn_player)`, `class HandRecorder` |
| `poker_recorder_gui.py` | GUI del grabador. `class RecorderGUI` |

### Tests sueltos

- `tests/test_ausente.py` — suite independiente en `tests/`, fuera del paquete `motor/`.

---

## 4. Cobertura de tests

**445 passed, 1 skipped** de 446 tests recolectados.

| Fichero | Tests | Fichero | Tests |
|---|---|---|---|
| `test_asistente_live.py` | 78 | `test_hierarchy.py` | 72 |
| `test_rules.py` | 34 | `test_robustness.py` | 31 |
| `test_decision.py` | 25 | `test_ranges.py` | 23 |
| `test_learn.py` | 17 | `test_hand_evaluator.py` | 16 |
| `test_stats.py` | 15 | `test_recommend_loop.py` | 15 |
| `test_player_ranges.py` | 14 | `test_hand_state.py` / `test_situation.py` | 13 / 13 |
| `test_preflop.py` / `test_profile.py` | 12 / 12 | `test_behavior.py` | 11 |
| `test_postflop_ranges.py` | 10 | `test_observations.py` | 9 |
| `test_implied_odds.py` | 8 | `test_cards.py` / `test_db_health.py` | 7 / 7 |
| `test_decision_oracle.py` | 4 | | |

```bash
python -m pytest motor/ -q          # suite completa (~2m20s)
```

---

## 5. Correcciones realizadas

Ordenadas por commit, de la más antigua a la más reciente.

### Taxonomía de rangos — `9a08d00`, `4902a25`, `52c6bad`, `1cecf69`
- Grid 13×13 / 169 posiciones, **1326 combos**, con `_HAND_CLASS_NAME`, `_HAND_SUB_CLASS`,
  `_HILO_IDX` y `_preflop_category()` coherentes entre sí.
- `BASE_WEIGHT_MAP` y `_ACTION_PROBS` extendidos a **todas** las subclases (`_PAIR_SUBS`, `_NONPAIR_SUBS`).
- `taxonomy_169.csv` generado para revisión manual (91 pares únicos `hi >= lo`).
- `offsuit_ace` con sus 4 subclases, separando AKo/AQo de `offsuit_broadway`.
- `hand_evaluator`: turn y river con 7 columnas sin duplicar la carta del board (rama `restantes == 1`).

### Robustez de rangos — `1349d0b` (fases A-B-C)
- `RangeError` + `validate_reach()`: rechaza NaN, infinito, negativos y probabilidades fuera de `[0,1]`.
- `villain_weights()` como **fuente única de verdad** de pesos, compartido por `situation.py` y `decision.py`.
- `RangeState.copy()` — evita mutaciones compartidas entre llamadores.
- `preflop.prob()` devuelve `None` si no hay tabla (antes devolvía ceros silenciosos).
- `opening_range_or_fallback()` registra explícitamente cuando cae al prior uniforme.
- `extra_blockers` distingue *blockers* de *mano rival conocida*: las cartas de un segundo hero son
  blockers, no una mano a restringir.
- `cards.is_card_code()` evita que `'-'` rompa el procesamiento postflop.
- `compute_evs()` mantiene las etiquetas de bet aunque `pot == 0`; validación de `amount <= 0`, pot, stacks y entradas inválidas.
- `_en_probe` exige `hero_oop=True`, con test del caso in-position.
- **31 tests de regresión** en `motor/test_robustness.py`.

### Multi-hero — `a94484a`, `4bcc541`
- `_heroes_conocidos()`: sólo heroes elegibles **activos**.
- `_cartas_bloqueantes()`: cartas conocidas incluso de jugadores folded.
- `_villain_id(state, hero_pid=..., known_pids=...)`: villano resuelto **por hero**, con separación de blockers.
- `Asistente.recomendaciones()` → `[(pid, evs)]`; `recomendacion()` se mantiene retrocompatible.
- `step(all_heroes=True)`: consulta cualquier hero activo y conserva el registro continuo.
- Si no hay heroes activos: no se recomienda, pero el recorder **sigue capturando**.
- En showdown no hay recomendación; las manos se editan manualmente offline porque el recorder no las captura.
- Corregido shadowing de `board`/`street` al actualizar rangos postflop.

### Modo sombra de jerarquía — `79c55f2`
- `hierarchy.py` completo: `classify_villains`, `passive_penalty`, `shadow_equity`, `ShadowLog`.
- Registro en `data/shadow_hierarchy.jsonl`.
- Garantizado por test que **no altera EV ni acción** (`test_shadow_no_altera_la_accion`).

### Correcciones P0/P1 del modo sombra — `2b309a9`
- `checkers_all` (todos los que checkean) separado de `checkers_secondary` (los que no son el main).
- Reconocimiento de rondas que vuelven al hero.
- Separación de `call` (`c`) de `check` (`x`) mediante la categoría `callers`.
- Auditoría de 608 registros de 400 manos: **0 incoherencias**.

### Separación de las tres equity — `fef0e3f`
- `equity_production` (la que decide), `equity_main` y `equity_shadow` pasan a ser campos distintos.
- `equity_shadow` queda en `None` si no hay `anchor_match` — ya no se emite un número inventado.
- `OBSERVED_ANCHOR` documenta que **0.02 viene de win rate, no de equity**, y que los signos no coinciden;
  se invierte el signo al reconstruir equity.
- `penalty_source()` → `'anchor_match' | 'partial_support' | 'none'`.

### El ancla no era una calibración de equity — `f817d93`
- **Corrección de una conclusión propia previa.** Se había reportado que el escenario del ancla no aparecía
  en los datos; en parte era un error de construcción: `penalty_source()` exigía `len(checkers)==1` sobre una
  lista de la que ya se había quitado `main`, y sin agresor `main` sale justamente de checkers.
  La condición era insatisfacible.
- Separando `checkers_all` de `checkers_secondary` aparecen **3 registros** donde antes se reportaban 0.
- `tools/auditar_anchor.py`: 654 observaciones → 441 `none`, 210 `partial_support`, **3 `anchor_match`**.
- Se declara el **desajuste de población**: el ancla se midió con otra definición de `pending` que la que
  produce el clasificador. Los 3 registros son alineación accidental, no correspondencia limpia.
  Documentado en `OBSERVED_ANCHOR['population_mismatch']` con su propio test.

### `checkers_all` vs secondary y `equity_main` — `82b4fab` (HEAD)
- `equity_main` implementada vía `_equity_vs_rival()` y `main_range_builder()`, con motivos de fallo
  explícitos y **sin tocar la decisión**.

> ⚠️ **Las cifras de las cuatro entradas anteriores (`2b309a9`, `fef0e3f`, `f817d93`, `82b4fab`) se
> midieron sobre las 1280 manos.** Repitiéndolas sobre las 900 fiables, el `anchor_match` pasa de **3 a 1** y
> las observaciones de 654 a 425. Las correcciones de código siguen siendo válidas —el error de construcción
> de `penalty_source` era real— pero **su magnitud está sobrestimada**. Ver §6.4.

---

## 6. Qué falta

### 6.1 Bloqueantes de la Fase D (calibración)

Los tres módulos siguientes son la base estadística del motor y **no han sido auditados**. Sin ellos no se
puede empezar a calibrar con garantías.

#### El campo `amount` mezcla dos semánticas — 🔴 invalida el arreglo por importe

El recorder graba el dinero comprometido de **dos maneras distintas en el mismo campo**:

- **Observado**: cuando el lector ve la apuesta en pantalla, graba el **nivel absoluto** ("subió a 3").
- **Calculado**: cuando no lo ve, lo deduce de la caída del stake (`recorder_live.py:601`):
  `delta = round((prev_stake or 0) - cur_stake, 2)` y graba el **incremento** ("puso 1 más").

Y se mezclan sin marcar. La acción guardada sólo tiene tres claves — `pos`, `action`, `amount` — **sin
ningún indicador del origen**, así que a posteriori es imposible distinguirlas.

**Evidencia medida** (primeras 900): hay **271 calls con importe menor que el nivel actual de la ronda**, lo
que es imposible si el importe fuera absoluto:

```
H_0021  ['UTG:b:6.8', 'MP:f', 'CO:f', 'BTN:c:6.7', 'SB:f']        call 6.7 tras bet 6.8  → delta
H_0022  ['UTG:b:2.0', 'MP:f', 'CO:r:8.0', 'BTN:c:7.5', ...]      call 7.5 tras raise 8  → delta
H_0026  ['MP:r:6.0', 'CO:b:1.0', 'BTN:f', 'SB:c:1.0', 'SB:c:5.0']  importes que no cuadran
```

**Consecuencia grave.** El recorder decide `b` / `c` / `r` comparando un **delta** contra `run_max`, que es
un **nivel** (`recorder_live.py:606-611`):

```python
if not has_bet:            atype = 'b'
elif amt <= run_max + 0.15: atype = 'c'
else:                      atype = 'r'
```

Una subida real a 3 cuyo delta observado sea 1 se clasifica como `'c'`, porque 1 ≤ run_max. **La propia
etiqueta `b`/`c`/`r` es poco fiable cuando el monto vino por delta**, no sólo el número.

**Esto invalida el arreglo por importe que se proponía antes.** No se puede usar `amount <= 1.0` para
identificar ciegas o limpes mientras `amount` sea unas veces un nivel y otras un incremento. El arreglo
seguro para la ciega del BB es **estructural** (posición BB + ser la primera acción), no basado en importe.

#### `motor/learn.py` — 🔴 defecto grave y medible

**No es un error del recorder.** Grabar la ciega del BB como `{'pos':'BB','action':'b'}` es una decisión
de diseño **correcta**: la ciega es un compromiso de fichas y tiene que aparecer en la secuencia, o el
recuento de committed chips no cuadra. El defecto está aguas abajo: `learn.py:175` infiere *"hubo una
subida"* **a partir del código de acción** en vez de a partir del importe.

```python
raises = sum(1 for p, a, m in seq[:i] if a in ('b', 'r'))   # learn.py:175
```

**Hay dos causas distintas, no una.** Descomposición de las 3252 decisiones con conteo divergente:

| Causa | Decisiones mal clasificadas | Ciegas que las originan |
|---|---|---|
| **Ciega del BB** (importe ≤ 1.0, posición BB) | **3085** (94.7%) | **560** |
| **Limpe corto grabado como `'b'`** (importe ≤ 1.0, otra posición) | **165** (5.1%) | 20 |
| Ambas a la vez | 2 (0.1%) | — |

⚠️ **Ojo con las magnitudes:** 3085 **no** es el número de ciegas registradas, sino el número de
*decisiones posteriores* cuyo conteo de subidas quedó inflado. Hay **560 ciegas reales** (586 manos), y cada
una corrompe ~5.3 decisiones de su mano (3085 ≈ 560 × 5.3). No puede haber más ciegas que manos: lo que se
multiplica son las decisiones afectadas, no las ciegas.

La segunda causa es independiente y no la había detectado: un limpe de 1BB se graba como `'b'`, no como `'c'`.
Ejemplos reales: `H_0004` → `MP:b:1.0` · `H_0006` → `UTG:b:1.0` · `H_0008` → `CO:b:1.0`.
El doble daño es que un limpe contabiliza como **subida** y además **no** como limpe, así que la categoría
`rol` (raise over limp) nunca se dispara para esos casos.

**La evidencia de que la intención era correcta está en la propia firma:**

```python
def classify_first_action(action, amount, raises_before, limps_before, bb=BB):   # learn.py:113
```

Recibe `amount` y `bb` — y **no usa ninguno de los dos** en el cuerpo (líneas 118-138). La función fue
diseñada para distinguir la ciega por importe, el caller se lo pasa (línea 177), y la implementación nunca
se terminó. Es una función a medio acabar, no un error de diseño.

**Medido sobre las 900 manos fiables** (entre paréntesis, el total de 1280 que usa el código hoy):

| Medición | Primeras 900 | Todas 1280 |
|---|---|---|
| Manos que contienen `{"pos":"BB","action":"b"}` | **586 (65.1%)** | 962 (75.2%) |
| De ellas, con la ciega del BB en el índice 0 | **562** | 938 |
| Manos donde la ciega precede a al menos otra acción preflop | **582** | 957 |
| Acciones donde `learn.py` ve una subida y **no hay ninguna real** | **1830** | 3198 |
| Total de `PreflopEvent` | **4695** | 6755 |
| Eventos en un denominador `facing_*` | **3060 (65.2%)** | 4723 (69.9%) |

Denominadores en la ventana fiable: `facing_open` 2326 · `no_raise` 1635 · `facing_3bet` 734.

**Simulación del arreglo.** Contando una subida sólo cuando el importe supera la ciega:

| Regla | Acciones con conteo divergente |
|---|---|
| Actual (`a in ('b','r')`) | **3252** |
| Ignorando sólo la ciega del BB | 184 |
| Sólo importes > 1.0 | **0** |

Efecto sobre la clasificación de `fold`, que es donde más se nota:

| Regla | `no_raise` | `vs_open` | `vs_3bet` |
|---|---|---|---|
| Actual | 527 | 1437 | 524 |
| Corregida | **1599** | 825 | **64** |

Es decir: los folds sin subida están **subcontados 3 veces** (527 → 1599) y los folds contra 3-bet
**sobrecontados 8 veces** (524 → 64). Cualquier apertura o VPIP derivado de esas cifras está mal.

**Qué habría que tocar. Todo en `learn.py`, nada en el recorder (grabar la ciega como `'b'` es correcto):**
1. `preflop_events()` línea 175: no contar como subida la ciega del BB, identificándola **estructuralmente**
   (posición `BB` + primera acción de la mano), **no** por importe — ver arriba, `amount` no es fiable.
2. La etiqueta `b`/`c`/`r` en sí misma es poco fiable cuando el monto vino por delta; a medio plazo hay que
   arreglar el recorder (§ siguiente) antes de afinar la taxonomía.
3. Opcionalmente, hacer que `classify_first_action` use por fin los parámetros `amount` y `bb` que ya recibe
   — pero sólo cuando `amount` vuelva a ser fiable.

Medido: de los 625 `'b'` con importe ≤ 1.0, **561 son separables sin ambigüedad** (ciega del BB al inicio,
o cortina corta tras una subida real) y sólo **64 son ambiguos** — un `'b'` a 1.0 sin subida previa, donde
importe no distingue limpe de open. En póker, subir exactamente a 1BB *es* un limpe, así que clasificarlos
como `limp` es defendible y cierra los 625 sin tocar el recorder.

Ejemplo real (`H_0340`, dentro de la ventana fiable):
```
seq: [('BB','b',1.0), ('UTG','f',0), ('MP','f',0), ('CO','f',0), ('BTN','f',0), ('SB','f',0)]
   BB  b  raises=0 -> open / no_raise     ← la ciega contada como "open"
   UTG f  raises=1 -> fold_vs_open        ← nadie abrió: es un fold a la ciega
   ... (5 jugadores idénticos)
```
La categoría correcta sería `fold/no_raise`. Consecuencia: `facing_open` y `fold_vs_open` están
**sobreestimados**, `no_raise/fold` **subestimados**. Se propaga en cascada a `stats.py` (b3/b4/vpip/pfr),
`profile.py`, `behavior.py`, `player_ranges.py` y `postflop_ranges.py`.

Otros problemas de `learn.py`:
- **`opportunities()` mezcla denominadores**: con `category=None` devuelve la suma de los 3 denominadores,
  pero cada columna de frecuencia usa `CATEGORY_DENOM[category]`. La columna `opp` **no es el denominador de
  ninguna columna de su propia fila**.
- **Posición perdida al agregar**: `PreflopEvent.pos` existe, pero `PreflopStats.from_hands` agrega sólo por
  `ev.player`. No hay forma de validar `preflop_matrices.json` (que sí es por posición) contra la DB.
- `classify_first_action` recibe `amount` y `bb` y **no los usa** — parámetros muertos.
- `hand_known` mezcla dos cosas: devuelve `True` si hay cartas **o** si el jugador es `Jarduan`, así que un
  hero sin cartas cuenta como "mano conocida".

#### `motor/player_ranges.py` — 🔴 seis problemas confirmados

1. **`_prior_grid` construye una clave que casi nunca existe.** Hace `tables.get(f'{prefix}_{pos}')`
   (`player_ranges.py:164`), pero las tablas de `3B` y `Call_OR` están indexadas **por par de posiciones**
   (`3B_BB_vs_SB`, `3B_BTN_vs_CO`, …), no por posición simple. La clave `3B_CO` no existe jamás, así que
   **toda** petición de `3bet` y de `call_open` cae al fallback de las líneas 165-169: la primera tabla de
   esa acción en el orden de inserción del JSON, que es siempre `3B_BB_vs_SB` / `Call_OR_BB_vs_SB`
   — el spot BB contra SB, **independientemente de las posiciones reales**. Sin aviso.

   | Prefijo | Tablas disponibles | Posiciones sin tabla → fallback |
   |---|---|---|
   | `OR` | `OR_UTG, OR_MP, OR_CO, OR_BTN, OR_SB` | `BB` → `OR_UTG` |
   | `3B` | 15 tablas `X_vs_Y` | **todas** → `3B_BB_vs_SB` |
   | `Call_OR` | 8 tablas `X_vs_Y` | **todas** → `Call_OR_BB_vs_SB` |
   | `LIMP` | **ninguna** | todas → prior plano `0.15` |

   Impacto real, medido sobre las **900 fiables** (peso del prior = `alpha/(opp+alpha)`, `alpha=2.0`):

   | Perfil | Spot | `opp` (900) | Peso del prior (900) | Peso con 1280 |
   |---|---|---|---|---|
   | TIBURON | no_raise | 393 | 0.5% | 0.4% |
   | TIBURON | facing_open | 513 | 0.4% | 0.3% |
   | TIBURON | facing_3bet | 146 | 1.4% | 0.9% |
   | PEZ | no_raise | 55 | 3.5% | 3.0% |
   | PEZ | facing_open | 50 | 3.8% | 3.3% |
   | **PEZ** | **facing_3bet** | **15** | **11.8%** | 11.1% |

   El daño está acotado donde hay datos (0.4–1.4% en TIBURON) pero **concentrado justo donde los datos
   escasean**: para PEZ en `facing_3bet`, con `opp=15`, casi uno de cada nueve pesos del modelo viene de
   un prior que describe otro spot.

2. **`load()` no restaura `self.profiles` ni lee la clave `'omega'`.** Verificado:
   `m.profiles → None`, `m.player_omega('Jarduan','no_raise') → 1.0` (siempre). `to_json()` **sí escribe**
   `'omega'`, pero `load()` nunca lo lee → **el ajuste individual desaparece silenciosamente** al cargar
   de disco, y `p_player()` queda idéntico a `p_matrix()`.
3. **ω se multiplica y se recorta sin renormalizar.** Medido sobre las 900 fiables, grid `CO`/`pfr`
   (suma base 13.27):

   | Jugador | ω | Suma base | Suma ajustada |
   |---|---|---|---|
   | Jarduan | 0.9946 | 13.27 | 13.20 |
   | NESANVAR | 1.0154 | 13.27 | 13.48 |
   | **Pipaaf182** | **0.5371** | **13.27** | **7.13** |

   ω=0.537 deja al jugador con la mitad de masa de rango sin renormalizar. La renormalización posterior
   recupera el déficit *globalmente pero no por celda*.
4. **El jugador está incluido en sus propios `peers`** — verificado: `Jarduan` está en sus propios peers,
   con **88** peers en la ventana de 900 (los 88 TIBURON, incluyéndolo a él). Sesga el denominador de ω
   hacia el propio jugador.
5. **ω tiene poca resolución individual.** Jarduan (0.9946) y NESANVAR (1.0154) coinciden en ~1.0 con
   dos decimales de diferencia, mientras Pipaaf182 (0.5371) se aparta mucho. La mayor parte de la señal es
   **por perfil**, no por jugador — que es lo contrario de lo que promete el nombre `player_omega`.
   Nótese además que ω **cambia de signo según la ventana** (Jarduan 1.0119 con 1280 → 0.9946 con 900),
   señal de que está estimado sobre muy pocos datos.
6. **`LIMP` no tiene ninguna tabla** en `preflop_matrices.json`: el spot del BB que hace `limp` usa prior
   plano 0.15 en todas las posiciones.

> Contradicción docstring vs. realidad: `player_ranges.py:45-46` afirma que *"el modelo NUNCA mezcla manos
> conocidas del HERO con las de rivales por diseño"*, pero `Jarduan` cae en TIBURON (en la ventana de 900:
> 154 jugadores, 88 TIBURON / 66 PEZ) y se mezcla con los otros 87 rivales en el mismo `p_matrix`.

> Nota sobre `CAT_TABLE`: sólo existen `open`, `3bet`, `call_open` y `limp` de entre las acciones que
> `_preflop_spot` puede devolver, así que el camino de producción sí usa prior por posición para `open`.
> El fallo es específicamente de las tablas indexadas por par.

#### `motor/rules.py` — 🟡 degradado, no vacío

- **`rp.candidates` puede degenerar en `('check',)` y enmascarar un error de datos.** Cuando
  `_multi_sizes` vacía el set natural y `strong_hand=False`, el plan queda *check-only*; `select_best` inyecta
  `'fold'` automáticamente → resultado silencioso *check o fold*, nunca una bet, sin señal de por qué.
- **`nut_advantage` se pasa y nunca se consulta** (0 apariciones como condición).
- **`villain_bet_flop` se pasa y nunca se consulta** (0 apariciones como condición).
- **`_en_flop_ip` no representa IP real**: significa "no fui el agresor preflop". Contraejemplo:
  `UTG open, BB call` → hero BB es OOP pero `hero_initiator=False` → se clasifica como IP.
- **`plan()` lanza `ValueError` en `street='preflop'`**; `recommend_loop.py` lo captura con un `print` a
  stderr y pone `rp=None` → se pierde todo el filtrado de reglas. `asistente_live.py:949` bifurca y no lo
  dispara, pero el riesgo sigue vivo en la llamada directa.

### 6.2 Bloqueantes de diseño

- **Multiway: `RangeState.union()` es matemáticamente inválido.** Mezcla distribuciones en lugar de
  distribuir conjuntamente. Caso medido: da **0.500** donde la equity contra dos rivales simultáneos da
  **0.000**. Hace falta rediseño conjunto o acotar explícitamente el alcance del motor a HU.
  El modo sombra **documenta** el problema pero no lo corrige: producción sigue usando `union()`.
- **`BASE_WEIGHT` no se aplica al reach inicial.** `RangeState.__init__` usa `np.zeros(1326)`, así que el
  rango inicial trata P(AA) = P(72o). `class_weights_for_reach()` existe pero está **DEPRECADO y sin
  llamadores en producción**. Nota: `BASE_WEIGHT_MAP` y `_ACTION_PROBS` **no están conectados a la ruta
  productiva**; `DEFAULT_ALPHA` sigue en 2.0 sin tocar.
- **Política ante EVs `NaN`.** `EvTable.best()` y `rules.select_best()` requieren un contrato explícito.
- **Contrato para `candidates` vacío** en `rules.py`, sin el efecto colateral de convertirse en fold.

### 6.3 Datos y calibración

- **Muestra insuficiente**: sólo **3 de 137** celdas de escenario tienen `n>=30`; **ninguna** tiene `n>=100`.
  (Cifra medida sobre 1280; debe repetirse sobre las 900.)
- **`other` representa 404/1172 eventos** (34.5%) de la primera ventana de 900.
- **Ganadores múltiples: 2.7% en la ventana fiable, no 18%.** Medido: 24 de 900 (2.7%) en las primeras 900,
  frente a 231 de 1280 (18.0%) en el total. Las 207 manos multi-ganadoras adicionales están **todas fuera de
  la ventana fiable**, lo que confirma que ese 18% es un artefacto de la convención de grabación de las 380
  últimas, no un hecho del juego.
- **3 manos sin ganador registrado**, todas dentro de la ventana fiable: `H_0086`, `H_0342`, `H_0344`.
- **Win rate ≠ equity**: `winner` es una lista de todos los ganadores; la equity exige reparto del bote.
- `data/hands_db.jsonl` tiene `cards: "-"` en `H_0350` (línea 347). El código lo tolera vía `is_card_code`,
  pero la fuente debería corregirse manualmente.
- `preflop_matrices.json` **no contiene `OR_BB`**; hay fallback uniforme y no se ha generado la tabla.
- Artefactos derivados obsoletos: `observations.json` con 3373 registros frente a 13715 potenciales;
  `behavior.json` con 339. Todos, además, construidos sobre las 1280.
- Nota operativa de `pegar_9.txt`: eliminar 20 manos concretas (`H_0339`–`H_0346`, `H_0368`, `H_0379`,
  `H_0386`, `H_0410`, `H_0422`, `H_0446`, `H_0449`, `H_0516`, `H_0583`, `H_0586`, `H_0603`, `H_0690`,
  `H_0705`). ⚠️ `H_0340` está en ese rango y es el ejemplo de la inferencia errónea de subida.

### 6.4 Ventana de datos: nadie la respeta

Este es el bloqueante transversal y el más fácil de arreglar:

- **`learn.load_hands()` no tiene límite de ventana.** Lee el fichero entero y devuelve todo lo que parsea.
  No existe ningún flag, constante ni parámetro que restrinja a las primeras 900.
- **Sus 15 consumidores** (ver tabla en §1) cargan las 1280 manos, incluidos
  `asistente_live.build_models()` — es decir, **las recomendaciones en vivo se calculan hoy con 380 manos
  de acción dudosa**.
- **Todos los derivados** (`preflop_stats.json`, `player_stats.json`, `profiles.json`, `behavior.json`,
  `observations.json`, `profile_ranges.json`, `postflop_ranges.json`) están calculados sobre las 1280.
- **`tools/auditar_anchor.py` y `tools/medir_multiway.py`** recorren el fichero entero, así que sus
  conclusiones también están contaminadas.

**Consecuencia sobre el ancla.** Repetida la auditoría restringida a las 900 fiables:

| | Primeras 900 | Todas 1280 |
|---|---|---|
| `none` | 292 | 441 |
| `partial_support` | 132 | 210 |
| **`anchor_match`** | **1** | 3 |
| Total observaciones | 425 | 654 |

El único `anchor_match` de la ventana fiable es `('turn', ())`. Es decir: **sobre la ventana en la que se
debería calibrar, el ancla tiene exactamente un registro de apoyo.** La conclusión de `f817d93` y
`82b4fab` ("3 registros en vez de 0") es correcta sobre 1280 pero **queda en 1 sobre los datos fiables**.
Esto refuerza, no debilita, la decisión de no activar la penalización.

**Arreglo propuesto:** añadir un parámetro explícito a `load_hands()` (p. ej. `max_hands=900` o
`reliable_only=True`) y propagarlo a todos los consumidores, de modo que la ventana sea una decisión
explícita y no una convención implícita.

### 6.4a ¿Hay que corregir la DB a mano?

**Recomendación: no, y no todavía.** Es una pregunta legítima y la respuesta corta es que corregir la DB
*antes* de arreglar el código y el recorder sería tratar el síntoma y además caro. El razonamiento:

**Los `b:1` de preflop no están "mal".** Son 560 entradas que registran algo que ocurrió de verdad: el BB
posted 1.0 antes de que nadie actuara. Borrarlas elimina un hecho real (que hubo ciega) y rompe el cálculo
del bote. Lo que está mal es que `learn.py` los lea como "alguien subió". Se arregla interpretando, no
borrando.

**El problema real no son esos 560 registros, sino la semántica mixta de `amount`**, que afecta a llamadas y
subidas por delta — 271 casos ya demostrados, y probablemente muchos más que no se manifiestan como
"imposibles" pero siguen siendo incorrectos. Eso **no se arregla con una edición dirigida**: para
reconstruir tendrías que adivinar qué entradas eran observadas y cuáles calculadas, y el fichero **no guarda
ningún indicador** que lo permita.

**Orden recomendado:**

1. **Arreglar `learn.py`** con detección estructural de la ciega (posición + índice), que es correcta
   aunque `amount` siga siendo dudoso. Inmediato y sin riesgo.
2. **Arreglar el recorder** para que deje de mezclar semánticas: guardar el importe observado y el
   calculado por separado, o añadir un campo `amount_type: 'observed' | 'delta'`, y no usar deltas para
   decidir `b`/`c`/`r` (comparar siempre contra el nivel, no contra el incremento).
3. **Regrabar** o **migrar** la DB sólo después, con un script versionado y auditable — nunca a mano. La
   migración podría normalizar los montos a absolutos usando el máximo acumulado, pero necesita el paso 2
   para saber qué trustworthy cada valor.
4. Mientras tanto, **excluir las 380 manos no fiables** (el límite de ventana, §6.4) y aceptar que el resto
   arrastra las estadísticas heredadas de los dos defectos anteriores.

Lo que sí conviene decidir pronto: **si la DB se va a re-grabar desde cero** cuando se arregle el recorder,
o si hay que migrar. Si se regraba, el orden 1-3 se simplifica mucho; si hay que migrar, hace falta el
script. Depende de cuánto más lejos vaya la corrección manual de la DB, y eso sólo lo sabe quien la está
manteniendo.

### 6.5 Definiciones por unificar

`pending` significa dos cosas distintas:
- `tools/medir_multiway.py`: *acted después del hero en la calle*.
- `hierarchy._jerarquia()`: *jugadores activos que aún no han acted*.

Esto es exactamente lo que hace que los `anchor_match` no sean una correspondencia limpia.
Repetido sobre la ventana fiable de 900, sólo queda **1** `anchor_match` (ver §6.4).

### 6.6 Deuda técnica menor

- `motor/__init__.py`: docstring desactualizado (15 vs 24 módulos) y `rules` no está en la lista de re-export.
- `implied_odds.py` es una isla: ningún módulo lo importa.
- `player_ranges.py` importa `matrix_to_probs` sin usarlo (import muerto).
- `rules.py` importa `cards` dentro de funciones, en el hot path de `plan()`.
- `hand_evaluator.py` escribe una caché de 10.4 MB fuera del repo (`~/.poker_motor/`).

### 6.7 Pendiente en modo sombra

- **`equity_main` no está cableado** desde el flujo real de `Asistente`. La función
  (`_equity_vs_rival` + `main_range_builder`) existe y está testeada, pero
  `asistente_live` no le pasa un constructor de rango, así que en producción se registra como no disponible.
- Falta verificar `equity_main` online y confirmar que no altera `action` ni `value`.
- `passive_penalty` sigue marcado **NO CALIBRADO** y sus constantes (incluido 0.02) no se han validado.

---

## 7. Cómo ejecutarlo

```bash
# Suite completa
python -m pytest motor/ -q

# Asistente en vivo (CLI)
python -m motor.asistente_live --poll 0.5 --hero-nombre Jarduan

# GUI del asistente
python -m motor.asistente_live_gui

# Recalcular derivados
python -m motor.learn --json
python -m motor.stats --json
python -m motor.profile --json
python -m motor.observations --json
python -m motor.behavior --json
python -m motor.player_ranges --json
python -m motor.postflop_ranges --json

# Auditorías
python -m motor.db_health --json
python tools/medir_multiway.py
python tools/auditar_sombra.py
python tools/auditar_anchor.py

# Laboratorio de rangos / calculadora de outs
python tools/range_lab_gui.py
python tools/calculadora_outs_gui.py
```

---

## 8. Orden sugerido de trabajo

1. **Restringir la ventana de datos a las 900 fiables.** Añadir el límite a `load_hands()` y propagarlo a
   los 15 consumidores. Es el paso más barato y el que más limpia todo lo demás: sin él, cualquier
   medición posterior vuelve a estar contaminada.
   *Acción concreta*: `load_hands(max_hands=900)` + `asistente_live.build_models()`, `behavior`,
   `observations`, `profile`, `stats`, `db_health`, `player_ranges`, `postflop_ranges`, `range_lab_gui`,
   `auditar_anchor`, `medir_multiway`. Luego reconstruir los derivados.
2. **Auditar `learn.py`** y corregir la inferencia de subida. Es el defecto más grave y contamina toda la
   cadena estadística aguas abajo. Ninguna calibración es válida antes de arreglarlo.
   *Acción concreta* (todo dentro de `learn.py`, **el recorder no se toca** — grabar la ciega como `'b'`
   es correcto): identificar la ciega del BB **estructuralmente** (posición `BB` + primera acción) y no
   contarla como subida. **No usar `amount`**, porque mezcla niveles e incrementos.
   Simulado: divergencias 3252 → 184, folds `no_raise` 527 → 1537. Las 184 restantes dependen de arreglar
   el recorder.
3. **Arreglar el recorder** (`recorder_live.py:599-616`): no decidir `b`/`c`/`r` comparando un delta contra
   un nivel, y registrar por separado el importe observado del calculado. Sin esto la taxonomía preflop
   queda coja aunque se arregle `learn.py`.
4. **Auditar `player_ranges.py`**, en este orden:
   - `_prior_grid`: indexar las tablas por par de posiciones (o dejar de usarlas como prior) y **avisar**
     cuando hay fallback, en vez de devolver la tabla de otro spot sin marcarlo.
   - `load()`: restaurar `profiles` y `omega`.
   - ω: excluir al propio jugador de `peers` y renormalizar por celda.
5. **Auditar `rules.py`**: contrato de `candidates`, `nut_advantage`, `villain_bet_flop`, `_en_flop_ip`.
6. **Unificar la definición de `pending`** y repetir `tools/auditar_anchor.py` ya sobre la ventana fiable.
7. **Cablear `equity_main`** en el flujo real y verificar que no altera la decisión.
8. **Decidir el alcance de multiway**: rediseño conjunto o limitación explícita a HU.
9. Sólo entonces, **Fase D**: recalcular derivados y empezar a calibrar `BASE_WEIGHT_MAP` y `_ACTION_PROBS`.

> Nota: los pasos 1–4 invalidan los derivados actuales (`preflop_stats.json`, `player_stats.json`,
> `profiles.json`, `behavior.json`, `profile_ranges.json`, `observations.json`). Hay que reconstruirlos
> antes de volver a medir nada. Por eso el orden importa: medir ahora daría cifras que luego habría que tirar.
>
> **Decisión pendiente para quien mantiene la DB:** ¿se regraba desde cero cuando se arregle el recorder, o
> hay que migrar las 900? Si se regraba, los pasos 2–3 se simplifican mucho; si hay que migrar, hace falta
> un script versionado. Ver §6.4a.
>
> Y una advertencia sobre el paso 1: al recortar a 900 la muestra baja de 1280 a 900 y varios `opp` caen
> por debajo de 50 (PEZ `facing_3bet` queda en **15**). Restringir la ventana **hace el problema de
> escasez más visible**, no menos. Es lo correcto: prefiero 15 observaciones limpias a 21 mezcladas con
> datos dudosos.

---

## 9. Ficheros relacionados

| Fichero | Contenido |
|---|---|
| `DOCS/ARQUITECTURA.md` | arquitectura detallada del sistema |
| `DOCS/TECNICO.md` | detalle técnico de los módulos |
| `DOCS/APRENDIZAJE.md` | cadena de aprendizaje y calibración |
| `DOCS/DIAGNOSTICO_CALIBRACION.md` | diagnóstico de mecanismos, cableado y estado de robustez |

Notas de trabajo (`pegar.txt`, `pegar_2.txt`, `pegar_3.txt`, `pegar_9.txt`, `pendientes_pegar.txt`,
`driff.txt`) están en la raíz y **están ignoradas por `.gitignore`** (`*.txt`). Son borradores locales, no
versionados.