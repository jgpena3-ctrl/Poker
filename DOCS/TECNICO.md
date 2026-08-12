# TECNICO.md — todo lo implementado del asistente de póker

Documento técnico de estado: qué hay, cómo funciona, qué genera y cómo se
prueba. Complementa a `DOCS/ARQUITECTURA.md` (diseño) y
`DOCS/APRENDIZAJE.md` (spec del pipeline de aprendizaje).

Estado: **172 tests verdes** (`python -m pytest motor -q`, ~5 s).
Datos reales: 327 manos válidas en `data/hands_db.jsonl`.

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
│   └── test_*.py         # 13 archivos de tests
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
hands_db.jsonl (327 manos)
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
   └─ data/profiles.json
      ▼
observations.py  UNA obs por decisión y calle (street, pot, SPR, textura, facing, sizing)
   └─ data/observations.json      (3.373 obs)
      ▼
behavior.py      frecuencias por (perfil, street, textura, facing) [granular]
                 + (perfil, street, facing) [por_facing, más volumen]
└─ data/behavior.json + data/behavior_probs.json
       ▼
Oracle           P(A|C) con fallbacks: granular → por_facing → perfil → población
       ▼
OracleResponse   (pf, pc, pr) → compute_evs con rival perfilado
       ▼
postflop_ranges  P(A|H) postflop: buckets de fuerza (5) de cada combo sobre el
                 board + evidencia de mano conocida (street, facing, bucket),
                 shrinkage al prior del Oracle
   └─ data/postflop_ranges.json
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
- **Rango por PERFIL (no por jugador)**: con 327 manos la muestra por
  jugador es mínima; el grid se agrega por perfil (etiqueta de profile.py).
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
- **P(A|H, street, facing, perfil)** con la mano conocida: la muestra por
  (perfil, street, facing) es chica en postflop (327 manos → 1.043
  decisiones con cartas, repartidas), así que la fuerza se **cuantiza en
  5 buckets** por board (percentiles del score de `hand_evaluator` sobre
  los 1128 combos legales; incompatibles con el board → bucket 0, los
  descarta el `RangeState`).
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

---

## 4. Datos de `data\`

| Archivo | Tamaño | Qué es / cómo se genera |
|---|---|---|
| `hands_db.jsonl` | ~450 KB | 327 manos válidas (cargadas por `load_hands`) |
| `preflop_matrices.json` | ~285 KB | 112 tablas 13×13 `{action, pos, vs, matrix}` (5 viajes) |
| `preflop_stats.json` | 13 KB | `learn --json` |
| `player_stats.json` | 29 KB | `stats --json` |
| `profiles.json` | 23 KB | `profile --json` |
| `observations.json` | 1,7 MB | `observations --json` (3.373 obs) |
| `behavior.json` | 22 KB | `behavior --json` |
| `behavior_probs.json` | 17 KB | `behavior --probs` |
| `profile_ranges.json` | ~1 MB | `player_ranges --json` (grids opp/cnt por perfil y spot) |
| `golden.json`, `calib_1365.json` | — | Bench fase 2 |
| `test_*.jsonl` | — | Registros de las pruebas |

---

## 5. Comandos de prueba y generación

```powershell
python -m pytest motor -q                    # 172 tests
python -m motor.learn --json               # data/preflop_stats.json
python -m motor.stats --json               # data/player_stats.json
python -m motor.profile --json             # data/profiles.json
python -m motor.observations --json        # data/observations.json
python -m motor.behavior --json --min-n 3  # data/behavior.json
python -m motor.behavior --probs           # data/behavior_probs.json
python -m motor.player_ranges --json     # data/profile_ranges.json
python -m motor.postflop_ranges --json   # data/postflop_ranges.json
python -m motor.recommend_loop             # demo anytime
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

**Hecho (172 tests):**
- Fase 2 MVP: cards · ranges · preflop · hand_evaluator · situation ·
  decision · panel · recommend_loop (anytime).
- Fase 4 aprendizaje: learn · stats · profile · observations · behavior +
  Oracle (files: `data/*.json`).
- player_ranges: **P(A|H, spot, perfil)** preflop con shrinkage a la
  base (§3.7) + **ajuste individual** (`player_omega`/`p_player`) — el
  rango rival perfilado alimenta `RangeState.update`.
- postflop_ranges: **P(A|H, street, facing, perfil)** postflop con
  buckets de fuerza (5) del board + shrinkage al prior del Oracle
  (§3.7); `recommend_loop` aplica el update en `villain_postflop`
  (`data/postflop_ranges.json`).
- Integración a EV: `OracleResponse` como función de respuesta del rival.

**Pendiente (decidido con el usuario):**
1. **`facing_3bet` con `b4`**: refinar `player_omega` para el spot 4bet
   (+ evaluación formal de `profile_ranges.json`).
2. Evaluación/mapas de desviación del hero (§8 capa 2): **postpuesto
   explícitamente** por el usuario.
3. Más adelante: árbol de calles completo con pagos intermedios (el sorteo
   del runout del MVP 2 parcial ya está en `runout_equity`) y refinar
   `P(A|H)` con `base`·ω por spot y cellas postflop por textura (más
   volumen).