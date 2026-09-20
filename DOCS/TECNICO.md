# TECNICO.md — todo lo implementado del asistente de póker

Documento técnico de estado: qué hay, cómo funciona, qué genera y cómo se
prueba. Complementa a `DOCS/ARQUITECTURA.md` (diseño) y
`DOCS/APRENDIZAJE.md` (spec del pipeline de aprendizaje).

Estado: **232 tests verdes + 2 fallos preexistentes** (`python -m pytest motor -q`,
~16 s). Los 2 fallos son de `test_decision.py` (MC runout / árbol MVP2) y existen
desde antes de los perfiles 2-clase (verificado con `git stash`).
Datos reales: 339 manos válidas en `data/hands_db.jsonl`.

---

## 1. Estructura del repo

```
C:\Users\Usuario\Documents\Repos\Poker\
├── motor\                # todo el código (Python 3.9, numpy, scipy)
│   ├── cards.py          # encoding 0..51 + bitmasks 52 bits
│   ├── ranges.py         # 1326 combos, RangeState, update bayesiano
│   ├── preflop.py        # tablas 13x13 de población (preflop_matrices.json)
│   ├── hand_evaluator.py # fuerza de manos 5/7 cartas (backend vectorizado)
│   ├── situation.py      # equity vs rango, pot odds, SPR, textura
│   ├── decision.py       # EV por acción (MVP 1) + OracleResponse
│   ├── panel.py          # salida inspeccionable (consola)
│   ├── recommend_loop.py # orquestador anytime (deadline 8 s)
│   ├── learn.py          # frecuencias preflop (DB real)
│   ├── stats.py          # estadísticas de transición por jugador (§5.2)
│   ├── profile.py        # perfiles: buckets, etiqueta, confianza, ω
│   ├── observations.py   # DecisionObservation por decisión/calle (§4)
│   ├── behavior.py       # behavior tables por perfil + Oracle P(A|C)
│   ├── player_ranges.py  # P(A|H, spot, perfil) preflop → RangeState (§3.7)
│   ├── postflop_ranges.py# P(A|H) postflop por buckets + Oracle (§3.8)
│   ├── asistente_live.py # bucle en vivo: captura + recomendación + registro (§3.9)
│   ├── asistente_live_gui.py # interfaz gráfica: nombres, auto/manual, topmost (§3.10)
│   └── test_*.py         # 14 archivos de tests
├── recorder\            # LiveRecorder + record_hand (registro de manos reales)
├── tools\              # capture_live, lector_estado, lector_unificado, leer_captura
├── data\                 # entradas, salidas y artefactos (ver §4)
└── DOCS\                 # ARQUITECTURA.md, APRENDIZAJE.md, TECNICO.md
```

---

## 2. Motor en tiempo real (fase 2, utilizado por recommend_loop)

| Módulo | Rol | Detalles técnicos |
|---|---|---|
| `cards.py` | Encodificación | `card_id('Ah') → 50`; `RANK_ORDER='23456789TJQKA'`; `SUIT_ORDER='cdhs'`; máscaras de 52 bits con `1 << idx`. |
| `ranges.py` | Rango rival | 1326 combos indexados; `RangeState` con `reach` (float32, única masa que se actualiza), `weight` (vista normalizada); `update(prob_action)` multiplica `reach *= P(A\|H)`; `update_with_action(action, context, action_prob_fn)` consume una función `P(A\|H)`; `set_known_cards` (blockers) y `legal_mask`. |
| `preflop.py` | Matrices base | 112 tablas 13x13 (`AKQJT98765432`); celda = frecuencia de acción por tipo de mano; pares en la diagonal, suited arriba/derecha. |
| `hand_evaluator.py` | Fuerza de manos | `evaluate5` / `evaluate_batch` / `evaluate_hand`; score int (mayor = mejor); batch vectorizado con pares rivales + board; backend por-fila numpy y **tabla C(52,5)** precacheada (`~/.poker_motor/five_table.npy`, idéntica en exactitud, ~5× más rápida en 7 cartas). |
| `situation.py` | Leer la mano | `equity_vs_range` (ponderada por reach con masas individuales por combo), `hero_percentile`, `pot_odds`, `spr`, `board_texture` (pairs/trips/flush_suits/rainbow/two_tone/monotone/straight_run; válida solo para boards de 3..5 cartas). |
| `decision.py` | EV de acciones | Fórmulas MVP 1: FOLD→0; CHECK→eq·pot; CALL→eq·(pot+2t)−t; BET→`Σ_v w_v·[pf·pot + pc·bote_rama − pr·amount]` (ALL_IN con otra rama). `(pf, pc, pr)` = `default_response` (heurística por equity, vectorizada) o `OracleResponse` (perfil del rival, §3.6). Bet sizes por defecto 25/50/75 % del bote + all-in. **MVP 2 parcial**: `runout_equity(hero, board, reach, n_runouts, n_combos)` — MC conjunto determinista (seed fija) que reparte turn+river del deck privado de cada rival muestreado; `compute_evs(runout=True)` la usa en check/call. |
| `panel.py` | Explicación | La distribución agregada (nuts/valor/draws/aire) es solo para el panel, nunca para el engine (regla ARQUITECTURA §8.2). |
| `recommend_loop.py` | Orquestador | Acepta hero/board/calles/stacks/rivales, construye rango rival con blockers y devuelve `Recommendation` antes del deadline (8 s por defecto); anytime: cada etapa se cronometra; con `range_model`+`villain_player` el rango rival es el **perfilado** (player_ranges, perfil·ω) en vez de la población. |

Pipeline de una mano ≈ **24 ms** (bench fase 2; ver `data/golden.json` y
`data/calib_1365.json`).

---

## 3. Fase de aprendizaje (fase 4)

El pipeline consume `hands_db.jsonl` y produce en cadena: frecuencias preflop →
stats de transición → perfiles → observaciones postflop → behavior tables →
Oracle (P(A|C) por perfil) → respuesta perfilada en el EV.

```text
hands_db.jsonl (339 manos)
      │  load_hands()  [valida players+streets, sin duplicados,
      │                 descarta manos sin preflop; conserva la raras marcadas]
      ▼
learn.py         categoría de la 1ª decisión preflop por jugador
   └─ data/preflop_stats.json
      ▼
stats.py         VPIP/PFR/3BET/4BET/CBET/F2CB/barrel/WTSD/W$SD (denominadores reales)
   └─ data/player_stats.json
      ▼
profile.py       posterior Beta por stat → buckets → etiqueta + confianza + ω
   │              ahora 2-clase: label PEZ/TIBURON (stack medio < 50 BB) + subtype fino
   └─ data/profiles.json
      ▼
observations.py  UNA obs por decisión y calle (street, pot, SPR, textura, facing, sizing)
   └─ data/observations.json      (3.373 obs)
      ▼
behavior.py      frecuencias por (perfil, street, textura, facing) [granular]
                 + (perfil, street, facing) [por_facing, más volumen]
└─ data/behavior.json + data/behavior_probs.json      [regenerado con PEZ/TIBURON]
       ▼
Oracle           P(A|C) con fallbacks: granular → por_facing → perfil → población
       ▼
OracleResponse   (pf, pc, pr) → compute_evs con rival perfilado
       ▼
postflop_ranges  P(A|H) postflop: buckets de fuerza (5) de cada combo sobre el
                 board + evidencia de mano conocida (street, facing, bucket),
                 shrinkage al prior del Oracle
   └─ data/postflop_ranges.json   [regenerado con PEZ/TIBURON]
       ▼
recommend_loop   villain.update(prob_vec(P(A|H))) con villain_postflop
```

### 3.1 learn.py — frecuencias preflop
- **Cada jugador entra UNA vez por mano** con su primera decisión preflop.
- Categorías: fold / limp / open (RFI) / call_limp / rol / fold_vs_open /
  call_open / 3bet / squeeze / fold_vs_3bet / call_3bet / 4bet / bb_check
  (el estado del pot preflop en el momento de actuar decide la categoría;
  tabla completa en APRENDIZAJE.md §6).
- **Dos tipos de evidencia que nunca se mezclan**: `hand_known=True`
  (cartas conocidas / hero) → `P(A|H, contexto)`; `False` → `P(A|contexto)`.
- `HERO_NAMES = ('Jarduan',)` → siempre `hand_known`. ⚠️ El jugador `HERO`
  de la DB (antiguo p0) es un rival normal, **no el hero real**.
- Resultado real (327 manos): Jarduan VPIP 26 %, PFR 21 %, 3BET 8 %,
  4BET 10 %, CBET 38 %, BAR 64 % (Fold/Call/Raise-CBET con muestra mínima
  muestran 100 % — ojo con n pequeña).
- CLI: `python -m motor.learn --json` → `data/preflop_stats.json`.

### 3.2 stats.py — transiciones (§5.2)
- Contadores `(oportunidad, acción)` por jugador: VPIP, PFR, 3BET, 4BET,
  Fold/Call/Raise-CBET, turn barrel, fold-to-barrel, river bet, WTSD y W$SD.
- **Gates reales**: CBET/barrel/river con gate de iniciativa (el que lidera
  debe ser el iniciador preflop; si otro apostó primero, no cuenta como
  CBET). WTSD/W$SD solo si la mano pasó por showdown registrado.
- **Hero → WTSD y W$SD = None**: sus cartas están SIEMPRE en la DB, por lo
  que "llegar al showdown" no es inferible; documentado.
- Iniciativa por **posición** (`ev.pos`), nunca por nombre (bug corregido).
  Acepta acciones como dicts `{pos, action, amount}` o tuplas.
- CLI: `python -m motor.stats --json` → `data/player_stats.json`.

### 3.3 profile.py — perfiles
- `STAT_BINS`: vpip (tight/mid/loose), pfr (low/mid/high), b3 (low/mid/high),
  cbet (low/mid/high), wtsd — **fracciones 0..1, no %** (no `betainc` sin
  saturación silenciosa en x>1).
- Posterior `Beta(a+1, opp−a+1)`; bin por **media de la posterior** (bug de
  n=1 corregido); confianza = **masa modal media geométrica**.
- `_archetype(bins)` → TAG / LAG / Nit / Tight-passive / Loose-passive /
  Passive-reg / Regular / Loose-reg.
- `reliability()` por nº de manos (APRENDIZAJE §5.5): <40 "probable",
  40–500 "confiable", >5000 "individual".
- `omega(table, base_rates)` = frecuencia real / frecuencia base con clamp
  [0,25, 4]; `load_base_rates` ponderado por los pesos de combos (6/4/12)
  sobre las 112 tablas.
- Resultados reales: Jarduan → **Regular** (conf 76 %, confiable),
  NESANVAR → **LAG** (32 manos: probable), Elyessi27 → **Loose-passive**
  (77 %), mur420 → **Regular** 68 %.
- **Clasificación 2-clase (PEZ/TIBURON, decisión del usuario):** `Profiles`
  ahora etiqueta cada jugador con `label` = **PEZ** o **TIBURON** además del
  `subtype` fino histórico. Regla (`simple_label`): stack medio (`stack_mean` =
  media de `players[].stack` en hands_db) **< 50 BB → PEZ**; sin stack y a la
  vez `vpip > 0.32` y `pfr < 0.10` → PEZ; el resto → TIBURON. `STACK_FISH_BB
  = 50.0` en `profile.py`. Con 339 manos: **32 PEZ / 24 TIBURON** y los stacks
  separan naturalmente en ~50 BB — la regla del usuario coincide con los datos.
- `to_dict()` y `report()` incluyen `label`, `subtype` y `stack_mean`.
- CLI: `python -m motor.profile --json` → `data/profiles.json`.

### 3.4 observations.py — observaciones (§4)
- `Observation` por decisión+calle: street, pos, action, amount, `pot_before`
  (aportes acumulados), `stack_effective` = stack inicial − ya aportado,
  `spr`, `pot_type` (SRP/3BP/4BP según raises preflop), `players_active`,
  `board`, `texture_class` (monotone/two_tone/rainbow [+pair]), `facing`
  (none/bet/cbet/barrel/raise: etiqueta de la apuesta vigente),
  `sizing` (b/r = amount/pot, si pot>0), `raised_before`,
  `preflop_sequence`, `hand_known`, `cards`.
- Defensivo: boards incompletos del recorder (1-2 cartas) → textura `None`,
  no rompe.
- Resultado: 3.373 observaciones de 327 manos (preflop 1.878, flop 735,
  turn 471, river 289; facing: none 2.002, apuesta 948, raise 271, cbet 100,
  barrel 52; 1.043 con cartas conocidas).
- CLI: `python -m motor.observations --json` → `data/observations.json`.

### 3.5 behavior.py — behavior tables + Oracle (§5.7 / §7)
- `build(hands)` cruza las **etiquetas de perfil** con las observaciones:
  - `granular`: (perfil, street, textura, facing);
  - `por_facing`: (perfil, street, facing) — sin textura, más volumen;
  - toda celda exige `n >= min_n` (3 por defecto, `--min-n`);
  - `sizing_mean` = media del sizing de las b/r de la celda.
- `Oracle.p_action(label, street, facing, texture=None)` → frecuencias
  normalizadas con **fallbacks escalonados**: granular → por_facing →
  agregado de la etiqueta → población; devuelve también `source`, `n` y
  `sizing`.
- Resultado real (min_n=3): 74 casillas granular + 50 por-facing.
  Regular: flop sin enfrentar = x 70 % / apuesta 30 % (size 77 %p); vs cbet:
  call 51 %, fold 43 %, raise 6 % (size 155 %p). Loose-passive: fold vs bet
  61 %, raise <10 %.
- CLI: `python -m motor.behavior --json` → `data/behavior.json`;
  `--probs` → `data/behavior_probs.json`.

### 3.6 Oracle → capa de EV
- `OracleResponse(oracle, label, (street, facing, texture))` → función
  `(equity_rival, amount, pot) → (pf, pc, pr)` vectorizada, misma firma
  que `default_response`.
  - `P(fold/call/raise)` del perfil **normalizada sobre esas tres**;
  - **fade-in**: `alpha = min(1, n_celda / 20)`; mezcla
    `probs = alpha·perfil + (1−alpha)·heurística`; sin celda → alpha 0 →
    heurística pura;
  - `compute_evs(..., response_fn=OracleResponse(...))` la usa en todas las
    ramas sin tocar el resto del motor.
- Ejemplo real (AK en 5♦6♦9♠, pot 100): bet_50 EV 40,1 (heurística) →
  80,0 vs Regular (fold 57 %) → 44,6 vs LAG (fold 75 %, raise 25 %,
  alpha 0,2).

### 3.7 player_ranges.py — P(A|H, spot, perfil) + ajuste individual (pegar6)
- **Rango por PERFIL (no por jugador)**: con 339 manos la muestra por
  jugador es mínima; el grid se agrega por perfil. Desde esta iteración el
  perfil es la **etiqueta 2-clase `label` (PEZ/TIBURON**, §3.3), no el
  `subtype` fino — `data/profile_ranges.json` quedó regenerado con 2 claves.
- Solo usa **manos conocidas** (`hand_known` y cartas): ~1.043 decisiones
  preflop de la DB (los eventos sin cartas quedan fuera; regla §3.1).
- Por (perfil, spot) se acumula `opp` (todas las primeras decisiones con
  mano conocida) y `cnt` por (perfil, spot, acción) sobre el **grid 13×13**
  (misma convención que preflop.py).
- **Shrinkage a la base poblacional** por celda:

      P(A|H, spot, P) = (cnt + alpha·prior) / (opp + alpha)

  con `alpha = 2` (pseudo-conteos) y `prior` = tabla base de la misma
  acción (preflop_matrices.json), o prior plano 0.15 si la acción no tiene
  tabla (limp/fold/bb_check/call_limp...). Perfil sin datos en el spot →
  grid = base pura.
- **Ajuste individual (paso 2 de pegar6)**: `player_omega(player, spot)`
  = freq real del jugador / media del stat del spot (no_raise→pfr,
  facing_open→b3, facing_3bet→b4) entre los jugadores de su perfil, con
  clamp [0.25, 4] y **fade-in** (alpha_mix = min(1, n/20): poca muestra
  del jugador → ω → 1). `p_player` escala el grid del perfil por esa ω.
- API: `p_matrix(perfil, spot, acción, pos)` → 13×13;
  `prob_vec(...)` → (1326,) listo para `RangeState.update`; `p_player`
  y `player_omega` para el rango individual; `p_hand(...)` → P(A|H) de
  una mano concreta ('AsKd').
- El grid empírico NO se desglosa por posición (n chica): la posición solo
  modula el prior cuando se pasa `pos` (busca la tabla `OR_BTN`-style,
  sino la mejor de la misma acción).
- Resultados reales (perfil con más muestra): Regular/no_raise 236 manos
  (open 51, fold 123, bb_check 27, rol 28), Regular/facing_open 121
  (call_open 22, fold_vs_open 86, 3bet 10); Loose-passive/no_raise 34.
  Ejemplo: AA en BTN no_raise → P(open) ≈ 0.8 (1 obs + prior).
- CLI: `python -m motor.player_ranges --json` →
  `data/profile_ranges.json` (incluye ω por jugador/spot en la clave
  `omega`).
- **Integración al motor**: `recommend(..., range_model=..., villain_player=...)`
  inicializa el rango rival con `prob_vec_player` (perfil·ω) en lugar de la
  población (`opening_range`). Ejemplo real (JdJh, Qh7s2c, pot 12.5):
  call +11.05 vs OR UTG → +11.86 vs NESANVAR (Loose-passive, ω>1 en
  no_raise) → +11.08 vs Mauroparley (ω<1 en no_raise).

### 3.8 postflop_ranges.py — P(A|H) postflop, buckets de fuerza + Oracle (pegar6, paso 3)
- **P(A|H, street, facing, perfil)** con la mano conocida (perfil = `label`
  PEZ/TIBURON, §3.3): la muestra por (perfil, street, facing) es chica en
  postflop (339 manos → ~1.043 decisiones con cartas, repartidas), así que la
  fuerza se **cuantiza en 5 buckets** por board (percentiles del score de
  `hand_evaluator` sobre los 1128 combos legales; incompatibles con el board →
  bucket 0, los descarta el `RangeState`).
- El bucket de una mano se busca por máscara de AMBAS cartas
  (`(HAND_MASKS & bit0) & (HAND_MASKS & bit1)`; un solo bit matchea 101
  combos — lección §6).
- ⚠️ **Hallazgo de la evaluación (pegar7)**: la DB real guarda en
  `turn`/`river` solo la **carta nueva** (ej. `'3h'`), no el board
  acumulado; sin reconstrucción el modelo solo veía flop. `observations.py`
  ahora acumula flop+turn+river (formato 1-carta respetado; boards
  completos de tests intactos) y `_board_ids` descarta boards con cartas
  duplicadas (4 casos en la DB). Resultado: cobertura real de flop (228
  obs conocidas), turn (191) y river (153).
- Por (perfil, street, facing, bucket) se acumula `opp` (manos que llegan
  al spot) y `cnt` por acción; **shrinkage al prior del Oracle P(A|C)**:

      P(A|H, bucket) = (cnt_bucket + alpha·prior) / (opp_bucket + alpha)

  con `alpha = 2`; bucket sin observaciones → prior plano del Oracle;
  sin Oracle → prior plano 0.2. El grid es grueso (5) a propósito: con n
  chica, leer siempre la n de la casilla.
- API: `p_action(perfil, street, facing, bucket, acción)` → float;
  `prob_vec(perfil, street, facing, board_codes, acción)` → (1326,) listo
  para `RangeState.update`; `from_hands / save / load`
  (`data/postflop_ranges.json`).
- **Integración al motor**: `recommend(..., postflop_model=...,
  villain_postflop=[(street, facing, acción), ...])` aplica los updates
  bayesianos sobre el `RangeState` del rival en cada calle
  (`villain.update(prob_vec)`), en la etapa `postflop` del orquestador.
- Evaluación real (327 manos): Regular flop/none b4 n=32 (x:19 b:13 →
  P(bet) 0.41) vs b1 n=18 (0.22) vs b0 n=5 (0.00): dirección por fuerza
  coherente; Loose-passive flop/none b3 n=7 (0.86) vs b2 n=3 (0.00):
  colas de muestra que respetar. Celdas nuevas tras el fix: Regular
  turn/none b4 n=31 (x:20 b:11), turn bet b4 n=11 (c:6 r:5), river none
  b4 n=26. 39 % de celdas con n≤2 → shrink 100 % al prior del Oracle.
- CLI: `python -m motor.postflop_ranges --json` →
  `data/postflop_ranges.json`; `--json` persiste.

### 3.9 asistente_live.py — asistente en vivo (2 perfiles PEZ/TIBURON)
- Bucle continuo (~0.5 s, `--poll`) sobre `capture()` (`tools/capture_live.py`):
  `state` con `pot`, `{pid}_stake`, `{pid}_bet`, `{pid}_state`
  (`activo/inactivo`), `{pid}_cards`, `community`, `btn`.
- **Clasificación rival en vivo (por STACK, nunca por coincidencia de
  nombres)**: PEZ si el jugador juega **mayoritariamente** por debajo de 50 BB
  — la media de los stacks observados en la sesión manda (`_observe_stacks`
  acumula en `live_stacks`); sin historial de sesión se usa el stack actual;
  sin información → TIBURON conservador. El rival elegido es el jugador activo
  no-hero de mayor stack; su nombre configurado en la GUI solo va a la
  etiqueta del panel (`_villain_name`) y al registro (para el reentrenamiento).
- Modelos en memoria (`build_models`): `load_hands()` → `Profiles.from_hands`
  → `label` PEZ/TIBURON; `ProfileRangeModel.from_hands`; `Oracle(build(...))`
  y `PostflopRangeModel` con ese mismo `Oracle` (⚠️ no usar `load()`: el JSON
  serializa las claves como strings y el `Oracle` pierde las tuplas →
  `p_action` lanza `ValueError: too many values to unpack`).
- Rango rival: `range_model.prob_vec(perfil, spot, action, pos)` según lo que
  el rival hizo preflop (`b→open`, `r→3bet`, `c→call_open`, `x→limp`, nada→
  `open`), + blockers (hero+board) + updates postflop con
  `prob_vec(perfil, street, facing, board, acción)` por cada acción ya
  observada del rival (facing: ``/cbet/barrel/bet/raise, escalado como en
  observations).
- Recomendación: `situation()` + `compute_evs()` y panel `format_insight` con
  `villain_label = "PEZ|TIBURON <nombre>"`; en manual se recomienda en cada
  captura (`require_turn=False, force_reco=True`); en auto cuando toca a hero:
  primera detección por botón de acción (`StateMatcher.read(pil, 'hero')` en
  `igualar/subir/pasar/apostar/apostar todo/mostrar cartas`) y, si el botón no
  se reconoce, **fallback lógico** (`_hero_maybe_to_act`: hero activo + rival
  activo + bote > 0). Dedupe por firma (hand_id + n_com + pot + hero_bet +
  max_bet) — el `hand_id` hace que una MANO NUEVA siempre reinforme. Cartas
  del hero/board con fallback a las registradas en la mano si el OCR las
  pierde (`_hero_cards_fallback`/`_board_fallback`).
- **Recomendación PREFLOP desde las matrices** (`_recom_preflop`, nunca EV):
  `street == 'preflop'` sale de `data/preflop_matrices.json` (no de
  `situation()/compute_evs()`, que exigirían >2 cartas). Spot del hero por las
  acciones del recorder (el blind BB es `b`, **cada raise es `r`**):
  - 0 raises → apertura con `OR_{pos}` (f ≥ 0.5 → `subir`, si no `retirar`;
    BB sin raise → `pasar`); 1 → `3B_{pos}_vs_{raiser}` vs
    `Call_OR_{pos}_vs_{raiser}`; 2 → `4B` vs `Call_3B`; 3 → `5B` vs
    `Call_4B`; más → retirar.
  - Decisión = argmax(f_rec, f_row, residuo-f = 1−min(1,Σ)) y el EvTable
    devuelto lleva `preflop=True` (frecuencias de la matriz, no EV; la GUI lo
    muestra como `· {f:.0%} (matriz preflop)`).
  - Frecuencia de la mano: `probs[combo]` con el índice del combo del hero
    (`_combo_index`); fallback por proximidad de tabla (`BASE_{pos}_vs_{vs}` →
    `BASE_{pos}` → cualquier `BASE`).
- **Registro continuo**: el `LiveRecorder` (`recorder/recorder_live.py`)
  procesa cada frame en paralelo y escribe manos completas en
  `data/hands_db.jsonl` → la base para reentrenar perfiles crece sola.
- Comportamiento real (339 manos, smoke): As Ks en `7h 2d Jc`, pot 3, to_call
  0.5, rival TIBURON 90 BB → `call (+1.88 BB)`; bet ≤ call.
- CLI: `python -m motor.asistente_live [--poll 0.5] [--hero-nombre Jarduan]
  [--quiet]`. El asistente **solo recomienda**, nunca ejecuta.

### 3.10 asistente_live_gui.py — interfaz del asistente (nombres + auto/manual)
- GUI tkinter inspirada en `poker_recorder_gui.py`:
  - Fila por asiento (hero..p1) con **nombre** (para el registro y la etiqueta
    del rival), `Inact` (inactivo manual), posición y cartas manuales; precarga
    de nombres desde la última mano de `data/hands_db.jsonl`.
  - **Modo Automático**: Iniciar/Detener; hilo con `init_reader()` + modelos
    + `Asistente.step` por frame (registra cada mano y recomienda cuando toca a
    hero, dedupe por firma de la situación).
  - **Modo Manual**: `Inicializar lector + modelos` → `Capturar` (un fotograma
    a tu ritmo: estado + mano + recomendación) → `Guardar mano` / `Cancelar
    mano` con override de ganador, como el recorder.
  - **Check `Ventana siempre al frente`** (`root.attributes('-topmost', ...)`).
  - Área de **Recomendación** destacada (mejor acción grande + panel completo)
    y log del estado de la mano.
- Revisa en cada fotograma los nombres/cartas/posiciones del GUI
  (`_sync_to_recorder` → `recorder_live.PLAYER_NAMES/MANUAL_*`).
- `Asistente` solo pisa `recorder_live.PLAYER_NAMES` si siguen siendo los por
  defecto (`_is_default_names`) — no machaca los nombres del usuario.
- MUY IMPORTANTE: al recargar el dataset, `Asistente` reconstruye los modelos;
  para re-arquitectura con capturas en vivo conviene reiniciar el hilo
  (cada `Iniciar` rebuild de ~2,5 s).
- CLI: `python -m motor.asistente_live_gui`.

---

## 4. Datos de `data\`

| Archivo | Tamaño | Qué es / cómo se genera |
|---|---|---|
| `hands_db.jsonl` | ~460 KB | 339 manos válidas (cargadas por `load_hands`) |
| `preflop_matrices.json` | ~285 KB | 112 tablas 13×13 `{action, pos, vs, matrix}` (5 viajes) |
| `preflop_stats.json` | 13 KB | `learn --json` |
| `player_stats.json` | 29 KB | `stats --json` |
| `profiles.json` | 23 KB | `profile --json` (label PEZ/TIBURON + subtype + stack_mean) |
| `observations.json` | 1,7 MB | `observations --json` (3.373 obs) |
| `behavior.json` | 22 KB | `behavior --json` (2 perfiles) |
| `behavior_probs.json` | 17 KB | `behavior --probs` (2 perfiles) |
| `profile_ranges.json` | ~1 MB | `player_ranges --json` (grids opp/cnt por PEZ/TIBURON) |
| `postflop_ranges.json` | — | `postflop_ranges --json` (2 perfiles) |
| `golden.json`, `calib_1365.json` | — | Bench fase 2 |
| `test_*.jsonl` | — | Registros de las pruebas |

---

## 5. Comandos de prueba y generación

```powershell
python -m pytest motor -q                    # 232 passed (2 preexistentes: test_decision)
python -m motor.learn --json               # data/preflop_stats.json
python -m motor.stats --json               # data/player_stats.json
python -m motor.profile --json             # data/profiles.json
python -m motor.observations --json        # data/observations.json
python -m motor.behavior --json --min-n 3  # data/behavior.json
python -m motor.behavior --probs           # data/behavior_probs.json
python -m motor.player_ranges --json     # data/profile_ranges.json
python -m motor.postflop_ranges --json   # data/postflop_ranges.json
python -m motor.recommend_loop             # demo anytime
python -m motor.asistente_live             # asistente en vivo CLI (PEZ/TIBURON)
python -m motor.asistente_live_gui         # interfaz gráfica (nombres + auto/manual)
```

---

## 6. Decisiones y lecciones aprendidas (no redescubrir)

- **Beta con `betainc` en fracciones**, nunca en porcentaje (saturación).
- **n pequeña**: los `100 %` con 2 oportunidades son artefacto: siempre leer
  la `n` de la celda.
- Hero (Jarduan): WTSD/W$SD no inferibles; su perfil entra en la base
  poblacional por etiqueta, pero el motor **no imita su estilo** (§8).
- Sin muestra → **fallback al nivel superior** (granular → por_facing →
  etiqueta → población) + fade-in para no dejar que 3 muestras dominen.
- Test conocido flakey: `test_deadline_param_accepted` (deadline 50 ms bajo
  carga; pasa a la segunda).
- `board_texture` exige 3..5 cartas; el observador tolera boards parciales.

---

## 7. Estado: hecho / pendiente

**Hecho (232 tests verdes; 2 fallos preexistentes de MC/árbol):**
- Fase 2 MVP: cards · ranges · preflop · hand_evaluator · situation ·
  decision · panel · recommend_loop (anytime).
- Fase 4 aprendizaje: learn · stats · profile · observations · behavior +
  Oracle (files: `data/*.json`).
- **Perfiles 2-clase PEZ/TIBURON**: `profile.py` con `simple_label`
  (stack medio < 50 BB; fallback vpip>0.32 y pfr<0.10) + `stack_mean`;
  `player_ranges`, `behavior` y `postflop_ranges` regenerados con las
  2 etiquetas (fluyen sin cambios de código vía `Profiles.from_hands`).
- **Asistente en vivo** (`motor/asistente_live.py`, §3.9): captura →
  rango rival PEZ/TIBURON en vivo → situation + EV por acción → panel; nunca
  juega solo; registra cada mano en `hands_db.jsonl` con el `LiveRecorder`
  para el reentrenamiento.
- **GUI del asistente** (`motor/asistente_live_gui.py`, §3.10): nombres por
  asiento, modos automático/manual (capturar a tu ritmo + guardar/cancelar
  mano) y check de ventana siempre al frente.
- player_ranges: **P(A|H, spot, perfil)** preflop con shrinkage a la
  base (§3.7) + **ajuste individual** (`player_omega`/`p_player`) — el
  rango rival perfilado alimenta `RangeState.update`.
- postflop_ranges: **P(A|H, street, facing, perfil)** postflop con
  buckets de fuerza (5) del board + shrinkage al prior del Oracle
  (§3.7); `recommend_loop` aplica el update en `villain_postflop`
  (`data/postflop_ranges.json`).
- Integración a EV: `OracleResponse` como función de respuesta del rival.

**Pendiente (decidido con el usuario):**
1. **Prueba en vivo con 20–50 manos reales** (siguiente paso): correr
   `python -m motor.asistente_live` y comparar recomendación vs decisión
   humana; verificar que la clasificación PEZ/TIBURON por stack coincide.
2. **`facing_3bet` con `b4`**: refinar `player_omega` para el spot 4bet
   (+ evaluación formal de `profile_ranges.json`).
3. Evaluación/mapas de desviación del hero (§8 capa 2): **postpuesto
   explícitamente** por el usuario.
4. Más adelante: árbol de calles completo con pagos intermedios (el sorteo
   del runout del MVP 2 parcial ya está en `runout_equity`) y refinar
   `P(A|H)` con `base`·ω por spot y cellas postflop por textura (más
   volumen).