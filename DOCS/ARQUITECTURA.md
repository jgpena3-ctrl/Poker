# Asistente de Poker — Arquitectura y Bases del Proyecto

Documento base de diseño. Consolida la visión del proyecto, el estado actual, las
decisiones de arquitectura y el plan de la fase de **toma de decisiones**.
Incluye las correcciones de pegar2.txt.

---

## 1. Visión general

Asistente de poker en tiempo real que:

1. Lee el estado de la mesa desde capturas de pantalla (ya implementado).
2. Mantiene **hipótesis de rango** sobre cada rival (distribución de probabilidad
   sobre las 1326 combinaciones de mano).
3. Actualiza esas hipótesis con cada acción observada (**inferencia bayesiana**).
4. Evalúa acciones candidatas por **valor esperado (EV)** contra la distribución
   de pesos individuales del rango rival.
5. Recomienda una acción y **explica el razonamiento** en 2-3 razones.

El núcleo **no es un solver GTO**, sino un sistema de inferencia de rangos
explotable: busca la acción que maximiza EV contra la hipótesis actual del rival,
no el equilibrio teórico. Esto lo hace:

- **Explicable**: cada recomendación se puede inspeccionar.
- **Adaptativo**: el mismo movimiento rival pesa distinto según su histórico.
- **Practicable**: cabe bajo un **deadline de respuesta de ~8 segundos**.

Lo que el sistema **NO es por ahora** (fase 2): ML, perfiles avanzados de
jugadores, tilt detector, CFR/solver, árboles enormes de turn/river, aprendizaje
online, NLP sofisticado, explicación compleja. Primero lo mínimo inspeccionable:

> Dame una situación → dame el rango estimado → dime qué acciones tienen EV →
> dime la mejor acción. Y que podamos verificar cada número.

## 2. Estado del proyecto (lo que ya existe)

### 2.1 Visión por computadora — `tools/`

| Módulo | Función |
|---|---|
| `lector_unificado.py` | Cartas Hero + community (mapas de gradiente, 100% en datos etiquetados) |
| `lector_estado.py` | Pot, stacks, bets sobre el tapete, botones de acción (subir/igualar/retirarse/pasar), dealer button. Entrenado con `data/golden.json` |
| `ocr_rapido.py`, `digit_ocr.py`, `lector_numeros.py` | OCR de números (~3ms por región) |
| `lector_cartas*.py`, `calib_1365.json` | Verdades de calibración y zonas de recorte |

Pendiente: **no existe ningún evaluador de manos ni ranker en el repo** — hay que
construirlo desde cero (sección 6).

### 2.2 Recorder — `recorder/record_hand.py`

Captura el entorno en vivo, detecta acciones por cambios de bets/stacks y guarda
manos completas en `data/hands_db.jsonl`.

Formato de una mano (extraído de H_0001 real):

```json
{
  "hand_id": "H_0001",
  "btn_player": "p4",
  "players": [
    {"active": true, "name": "Juanmabm", "pos": "BB", "stack": 92.7, "cards": ""}
  ],
  "comunitarias": {"flop": ["5h","6d","4d"], "turn": ["3h"], "river": ["Qc"]},
  "streets": {
    "preflop": {"actions": [{"pos": "UTG", "action": "b", "amount": 2.5}], "board": []},
    "flop": {"actions": [...], "board": ["5h","6d","4d"]},
    ...
  },
  "final_pot": 37.3,
  "winner": ["p2","p4"],
  "allin": []
}
```

**Codificación de acciones (canónica):**

| Código | Significado | Notas |
|---|---|---|
| `b` | apuesta inicial | primer dinero de la calle |
| `c` | call | igualar cantidad indicada |
| `x` | check | pasar (amount 0) |
| `r` | raise | amount = total combinado (bet+raise) |
| `f` | fold | amount 0 |

Posiciones: `BTN, SB, BB, UTG, MP, CO` (hasta 6 asientos por mesa).

## 3. Principios de diseño

1. **Los rangos son distribuciones, no conjuntos binarios.**
   `AA → 0.98, KK → 0.97, AQ → 0.76, AQo → 0.65...` Expresan incertidumbre y
   se actualizan suavemente: una acción **pesa** las manos, no las elimina.
2. **Rango y decisión están separados.** El motor de inferencia emite un
   `RangeState` con confianza; el motor de decisión lo consume. Se pueden
   cambiar de forma independiente.
3. **Se trabaja con las 1326 combinaciones reales**, no con los 169 tipos
   abstractos: los blockers (cartas propias + board) importan.
4. **`P(A|H)` es una función contextual desde el diseño original**, aunque
   internamente arranque con tablas heurísticas (ver §5.3).
5. **Deadline de 8 s, no pipeline rígido.** Cada módulo consume lo que necesita
   hasta un límite máximo; decisión anytime (§7).
6. **DecisionEngine consume pesos individuales (§8.2)**, no solo buckets
   agregados.
7. `P(A|H)` inicial desde **heurísticas de estrategia base** editables; el
   refinamiento con datos de `hands_db.jsonl` es fase posterior.

## 4. Flujo de decisión y estado

```
       ┌─────────────────────┐
       │     HandState       │
       └──────────┬──────────┘
                  │
                  ▼
       ┌───────────────────────┐
       │     Range Engine      │
       │                       │
       │  1326 combo weights   │
       │  + reach (hist.)      │
       │  + action history     │
       └──────────┬────────────┘
                  │
                  ▼
       ┌───────────────────────┐
       │   Situation Engine    │
       │                       │
       │ equity                │
       │ board texture         │
       │ relative strength     │
       │ SPR / pot odds        │
       └──────────┬────────────┘
                  │
                  ▼
       ┌───────────────────────┐
       │   Decision Engine     │
       │                       │
       │ candidate actions     │
       │ EV (1326 pesos)       │
       └──────────┬────────────┘
              ┌────┴────┐
              ▼         ▼
         ACTION    EXPLANATION
```

Y simultáneamente (loop de acción observada), el rango es la **memoria
estratégica de la mano**:

```
        Observed Action
               │
               ▼
         Range Engine
               │
               ▼
        New RangeState
               │
               ▼
      nueva decisión
```

Estado persistente por rival (modelo inicial):

```
OpponentModel
 ├─ range          (RangeState sobre 1326 combos)
 ├─ position / stack
 ├─ action / sizing history
 ├─ tendencies     (agresión, frecuencia… — fase 3)
 └─ confidence     (crece con manos observadas)
```

Multiway: un `RangeState` por rival activo; la decisión evalúa
`EV(acción | R_A, R_B, …)` y hasta el conjunto de rivales.

## 5. Motor de rangos (Range Engine)

### 5.1 Representación

- Cada carta: índice `0..51` y bit `1 << idx` (bitmask de 52 bits).
- `ALL_HANDS`: tabla de las 1326 combinaciones con `code`, `mask`,
  suitedness y clasificación preflop — construida una vez al iniciar.
- **Filtro de blockers:** `legal = (hand_mask & known_cards_mask) == 0` — barato.

### 5.2 Estructura del rango — reach vs weight

Convención de nombres: **`mask` se reserva para cosas binarias**
(`known_cards_mask`, `hand_mask`, `legal_mask`). Las masas de probabilidad
se llaman `reach` y `weights` (`np.ndarray[float32]`), nunca `*_mask`.

```
RangeState
  combos            : ids de las 1326 combinaciones
  reach             : np.ndarray[float32] (1326,) — masa absoluta de haber llegado aquí
  blockers          : cartas conocidas (hero + board)
  confidence        : 0..1
```

**Definición matemática cerrada (antes de programar `ranges.py`):**

```
weight_h = reach_h / Σ_j reach_j        (tras blockers y normalización)
```

- `reach` es la **única masa que se actualiza**: cada `update_range` multiplica
  por `P(A|H, context)` y pone a 0 los combos que chocan con blockers. Es la
  fuente de verdad del estado.
- `weight` es una **vista normalizada** de `reach` (derivada, nunca se modifica
  de forma independiente). Se calcula al consumir el rango (DecisionEngine,
  panel).
- Así no pueden divergir dos verdades. El ejemplo "AA preflop 100% → flop 92% →
  turn 75%" se lee siempre en `reach`.

```
AA :  preflop 100%  → flop 92% → turn 75%
76s:  preflop  65%  → flop 48% → turn 21%
```

No esencial para el MVP, pero el diseño lo permite desde ya: `RangeState`
guarda `reach` y expone `weight` como vista derivada.

### 5.3 Inicialización — no solo RFI

No partimos únicamente de "¿qué abre este jugador?", sino de estados preflop
situacionales. El punto de partida depende del estado:

```
InitialRange               (distribución base por posición: UTG ≈12%, BTN ≈40%…)
     │
     ▼
PreflopActionUpdate        (UTG open · UTG call · UTG 3bet · cold call ·
                            BB defend · BB squeeze · BTN vs open · ...)
     │
     ▼
FlopRange                  (rango resultante "UTG open + BB call")
```

Range Engine debe entender qué secuencia preflop pasó para arrancar el flop con
el rango correcto, no solo con la interpretación inicial de apertura.

### 5.4 Actualización bayesiana contextual

```
P(H | A) ∝ P(A | H) · P(H)
```

- `H` = mano concreta, `A` = acción observada.
- `P(A|H)` **no es una tabla plana**: es una función con contexto:

```
action_probability(
    hand,
    board,          S: street y textura
    street,
    position,
    action,
    sizing,
    pot,
    players,        número de jugadores activos (HU vs multiway)
    history
)
```

Lo que la función captura:

- `AA → bet` no significa lo mismo en `A72r` que en `JT9ss`.
- `BB check-raise` pesa distinto en HU que en bote multiway.
- Un raise de 2.5 BB no pesa como uno de 15 BB.

Internamente arrancará como **tablas heurísticas de estrategia base**
(por categoría: premiums 3-betean, draws manejan flush boards, etc.),
editables sin datos; pero la **interfaz de la función ya queda contextual**
para poder crecer en precisión (o aprender) sin cambiar firmas.

## 6. Evaluador batch de manos — pragmático, no asumir tabla completa

Para `P(A|H)` y, en EV, lo que necesitamos es evaluar los alrededor de
1326−blockers combos legales **del rango actual**, no millones. Así:

1. **Primero** implementamos un evaluador simple y **medimos**
   (`1326 → filter blockers → evaluate_batch`) con benchmark real.
2. **Solo si** resulta lento para el deadline de 8 s, precomputamos
   `C(52,5) = 2.598.960` valores (5 cartas exacto) o alternativas
   (Numba/C++/bitmask-nip). El documento de pegar.txt ya describe esa tabla:
   rankear 7 cartas = máximo de los 21 subconjuntos de 5.

La **arquitectura aísla** el backend del evaluador (`BatchHandRanker`
detrás de una interfaz), para cambiarlo sin tocar el resto.

```
known       = hero_mask | board_mask
legal       = (ALL_CARD_MASKS & known) == 0
ranks       = evaluate_batch(ALL_CARD_SETS[legal], board)   # vector
hero_rank   = evaluate(hero + board)
wins        = ranks > hero_rank
ties        = ranks == hero_rank
```

- Flop/turn: fuerza actual con las cartas disponibles; equity futura de turn/
  river es fase posterior.
- De un rankeo sale la `RangeDistribution` (nuts / valor fuerte / valor medio /
  par / draws / aire) **para explicación**, nunca como entrada del Decision.

## 7. Presupuesto de tiempo *anytime* (~8 s)

No pensamos en bloques fijos (`0-100 parsing, 100-500 equity…`). Es un
**deadline máximo** con *anytime decision*: cada módulo consume lo necesario;
cuanto más tiempo quede, más profundo se analiza, pero nunca se bloquea la
recomendación.

```
deadline = 8 s
parse 30 ms   + range 15 ms   + equity  5 ms  + EV 20 ms  → 70 ms     (mano sencilla)
parse 30 ms   + range 80 ms   + equity 600 ms + actions 900 ms
            + future branches 3500 ms      → ~5.1 s (situación compleja)
```

## 8. Motor de situación y decisión

### 8.1 Situation Engine — "¿Qué significa nuestra mano?"

Calcula: equity vs rango, nut/range advantage, strength relativa, draws,
vulnerability, SPR, pot odds, posición, textura de board.

### 8.2 Decision Engine — "¿Qué hacemos?" (con pesos, no buckets)

El DecisionEngine **no recibe la `RangeDistribution` como entrada**.
```
RangeState ────────────────→ DecisionEngine
     │
     └─── RangeDistribution → EXPLAINING (panel)
```

La distribución agregada (sets/two pair/draws/air) sirve para explicar, pero
para EV se operan los **1326 pesos individuales** (p. ej. `AsKs`, `AhKs`,
`KdQd`, `JdTd` – cada combo con su masa).

Acciones discretas:

```
fold · check · call · bet_small (25%) · bet_medium (50%) ·
bet_large (75%) · raise · all-in
```

Para cada una se estima `EV(acción | pesos del rango)`:

```
CHECK     +0.41 BB
BET 25%   +0.57 BB
BET 50%   +0.71 BB   ← recomendada
BET 75%   +0.52 BB

razón: captura valor de top pair, cobra draws, mantiene manos peores.
```

El `anytime` permite además profundizar (futuros turn/river, `future response`)
según tiempo restante (§7).

### 8.3 Profundidad temporal del EV

El EV no es solo "mi equity × bote". El Decision Engine debe modelar al menos
una respuesta:

```
acción Hero → respuesta probable Villain → nuevo rango → resultado / siguiente decisión
```

por etapas explícitas:

| Etapa | Alcance |
|---|---|
| **MVP 1** | **EV inmediato**: "apuesto X, el rival responde (fold/call/raise según modelo), resultado". |
| **MVP 2** | **EV con una calle futura**: bet flop → turn → respuestas probables allí. **Parcial ✔**: el sorteo del runout ya entra en las ramas pasivas (check/call) vía `runout_equity`; los pagos intermedios de la calle futura quedan pendientes. |
| Más adelante | Árbol turn/river completo (con el presupuesto anytime). |

No se intenta el árbol completo al inicio.

## 9. Estructura del código (fase 2)

Nuevo paquete `motor/`:

```
motor/
  cards.py             # encoding de cartas, bitmasks 0..51
  hand_evaluator.py    # evaluador de fuerza (backend aislado, benchmark first)
  ranges.py            # ALL_HANDS, HandRange, update bayesiano contextual
  preflop.py           # tablas preflop 13x13 -> P(A|H) (1326,) por acción/pos/vs
  situation.py         # equity vs rango, pot odds, SPR, texture
  decision.py          # asign EV de acciones, elección de tamaño, recomendación
  recommend_loop.py    # orquestador anytime: HandState → panel (deadline 8 s)
  panel.py             # salida inspeccionable (consola · JSON opcional)
  learn.py             # frecuencias preflop desde hands_db.jsonl (PreflopStats)
  stats.py             # estadísticas de transición por jugador (§5.2 spec)
  profile.py           # perfiles: bins, etiqueta, confianza, ω matrices
  observations.py      # DecisionObservation por decisión/calle (§4 APRENDIZAJE)
  behavior.py          # behavior tables por perfil (perfil×street×textura×facing)
```

Datos preflop: `data/preflop_matrices.json` — 112 matrices 13x13 (OR, 3B,
Call_OR, 4B/5B, Call_3B/4B/5B, SQUEEZE, Over_Call) para todas las
posiciones/emparejamientos. Cada celda es la frecuencia con la que la mano
ejecuta la acción. `motor/preflop.py` las mapea a vectores de 1326 combos
(P(A|H) preflop). Los perfiles de jugador (fase 4) escalarán estos vectores
según la frecuencia esperada vs real de `hands_db.jsonl`.

Estado del motor (agosto 2026): está completo el MVP de la fase 2 — `cards.py`,
`ranges.py`, `preflop.py`, `hand_evaluator.py`, `situation.py`, `decision.py`,
`panel.py`, `recommend_loop.py` y `learn.py` implementados y verificados (186
tests). El
evaluador usa un backend numpy vectorizado con **tabla C(52,5) precacheada**
(fase 3 ya implementada: `hand_evaluator._five_table`, build ~10 s una sola vez
guardado en `POKER_MOTOR_CACHE`/`~/.poker_motor/five_table.npy`, 10.4 MB;
mismo resultado exacto que el evaluador por-fila, ~5× más rápido en 7 cartas).
Benchmark actual (`python -m motor.hand_evaluator`): ~4 ms flop, ~74 ms river
en 990 combos legales. `python -m motor.recommend_loop` muestra el panel
completo (JJ vs OR UTG: call +11.05 BB) en ~24 ms totales — el presupuesto
anytime de 8 s queda con holgura enorme. `situation.py` monta el `Situation`
(equity vs rango ponderada por reach, pot odds, SPR, textura determinista).
`decision.py` implementa la etapa **MVP 1** (§8.3): EV inmediato con una
respuesta rival modelada (`default_response` vectorizado: fold según las odds
rivales, raise con figuras), operando los 1326 pesos individuales, y ya suma
**MVP 2 parcial** (§14.7, #11): `compute_evs(runout=True)` — `runout_equity`
reemplaza la equity determinista por equity a showdown con sorteo MC conjunto
de turn+river (200×~300 muestras, determinista por seed fija, ~1-2 s; los
régs. de blocker por combo se respetan muestreando el runout del deck privado
de cada rival). Las ramas pasivas (check/call) usan esa equity; las agresivas
y el all-in conservan la determinista; los pagos intermedios de la siguiente
calle siguen pendientes (#11). El `recommend_loop` orquesta con presupuesto
anytime (deadline por defecto 8 s, mide cada etapa y reporta el margen
restante). La distribución agregada
(nuts/valor/draws/aire) sigue reservada al panel (§8.2), que hoy es consola
ASCII pura (Windows-safe); `panel.py` solo explica, nunca alimenta al
Decision Engine. `learn.py` (fase 4 iniciada) extrae frecuencias preflop de
`data/hands_db.jsonl` según la spec `DOCS/APRENDIZAJE.md`: primera decisión de
cada jugador con su estado correcto (frecuencia sobre denominadores no_raise /
facing_open / facing_3bet), categorías open·limp·R·call_limp·call_open·3bet·
squeeze·4bet·call_3bet·folds·bb_check, y la marca `hand_known` para separar
siempre `P(A|contexto)` de `P(A|mano, contexto)` (sin mezclar evidencia con y
sin showdown). Sobre 327 manos reales ya genera la tabla de frecuencias por
jugador (`python -m motor.learn --json` → `data/preflop_stats.json`).

Consumidor inicial: `HandState` del recorder, corroborado contra
`data/hands_db.jsonl` y fixtures sintéticas.

## 10. Roadmap

| Fase | Contenido |
|---|---|
| **1. Bases** (este doc) | Decisión de arquitectura + decisiones acordadas |
| **2. En práctica (MVP)** | **✔ Hecho (julio 2026):** `cards.py` + `ranges.py` (1326 combos, blockers, reach/weight, update bayesiano) → evaluador simple + benchmark → Situation + Decision (EV inmediato, etapa MVP 1) → panel + `recommend_loop` anytime. 82 tests, pipeline ~24 ms. Pendiente: tests con `HandState` real de `hands_db.jsonl` y fixtures |
| **3. Backend si falta** | **✔ Hecho (agosto 2026):** tabla `C(52,5)` precacheada (`five_table.npy`, build ~10 s una vez, ~5× en 7 cartas). Requirió corregir overflow int16 del evaluador por-fila (los kickers se multiplican por 13^k) y scatter por índice combinatorio en el build |
| **4. Aprendizaje** | **✔ Iniciado (julio 2026):** `motor/learn.py`: frecuencias preflop (327 manos; `data/preflop_stats.json`). **✔ `motor/stats.py`**: estadísticas de transición VPIP/PFR/3BET/4BET/C-BET/F2CB/barrel/WTSD/W$SD con denominadores reales (`data/player_stats.json`). **✔ `motor/profile.py`**: buckets con posterior Beta, etiqueta derivada, confianza por muestra y `ω(perfil, spot)` contra las matrices (`data/profiles.json`). **✔ `motor/observations.py` (agosto 2026):** extractor postflop de `DecisionObservation` (street·pot·SPR·textura·facing·sizing; `data/observations.json`) + `behavior_table()`. **✔ `motor/behavior.py` (agosto 2026):** behavior tables materializadas por perfil (granular + por_facing; `data/behavior.json`) y `Oracle` → P(A|C) postflop con fallbacks (granular→facing→perfil→población; `data/behavior_probs.json`). **✔ Conexión al EV (agosto 2026):** `OracleResponse` como `response_fn` de `compute_evs` (fade-in por n de celda). **✔ `motor/player_ranges.py` (agosto 2026):** P(A\|H) preflop con grids 13×13 por perfil × spot + shrinkage a la base y ajuste individual por ω (`data/profile_ranges.json`). **✔ `motor/postflop_ranges.py` (agosto 2026):** P(A\|H) postflop con buckets de fuerza (5) + shrinkage al Oracle (`data/postflop_ranges.json`); `recommend_loop` aplica `villain.update(prob_vec)` vía `villain_postflop`. Spec: `DOCS/APRENDIZAJE.md`. Pendiente: capa 2 del Hero (mapa de desvíos), perfiles individuales, refinar `P(A|H)` con más volumen y cellas por textura |
| **5. Tiempo real** | Integración al recorder en vivo con deadline 8s |

## 11. Decisiones registradas

| # | Pregunta | Decisión |
|---|---|---|
| 1 | Evaluador de manos | Empezar por evaluador simple + benchmark; tabla `C(52,5)` solo puntual (fase 3) |
| 2 | Rivales del MVP | Todos los activos, un `RangeState` por rival |
| 3 | `P(A|H)` | Función **contextual** desde el inicio; internamente tablas heurísticas editables |
| 4 | Inicialización de rango | No solo RFI: según estados preflop (open/call/3bet/defend…) |
| 5 | `RangeState` | `reach: float32` es la **única masa que se actualiza**; `weight` = `reach/Σreach` es vista normalizada derivada (§5.2) |
| 6 | DecisionEngine | Entrada = pesos individuales; `RangeDistribution` solo vale para explicar |
| 7 | Presupuesto 8s | Deadline *anytime* (no bloques fijos): cada módulo consume, nunca bloquea |
| 8 | Recomendación | Consola + panel de inspección (acción, EV, rango, razones) |
| 9 | Perfiles de jugador | Fase 4; el MVP infiere solo por posición + acción + sizing |
| 10 | Nombres de masas | `mask` reservado a binario (`legal_mask`, `hand_mask`…); `reach`/`weights` son `float32` |
| 11 | Profundidad EV | **MVP 1**: EV inmediato con una respuesta modelada; **MVP 2 (parcial, ✔ agosto 2026)**: equity a showdown con sorteo del runout (MC conjunto determinista, ramas pasivas) — sin pagos intermedios de la siguiente calle; árbol turn/river más adelante |
| 12 | Orden de implementación | `cards.py` + `ranges.py` con test primero; el evaluador se conecta después |
| 13 | Buckets postflop (pegar7) | `P(A|bucket,C,P)` es **mecanismo de aprendizaje con poca muestra**, nunca representación final: el engine sigue operando sobre los 1326 pesos; migrar a `P(A|combo)` gradualmente **solo** cuando el dataset lo soporte |
| 14 | Granularidad de contexto (pegar7) | **No** añadir posicion/pot_type/nº jugadores/sizing de golpe: con 327 manos el grid se atomiza; el fallback jerárquico (granular → por_facing → perfil → población) cubre los huecos |
| 15 | Prioridad actual (pegar7) | **Volumen > algoritmo**: validar player_ranges y postflop_ranges, validar los updates de 1326 combos, y extraer más manos; nada de ML/CFR/árboles completos/tilt detector hasta que la evidencia lo justifique |
| 16 | Ajuste individual (pegar7) | El ω individual no puede dominar sin evidencia: mantener fade-in (`alpha_mix = min(1, n/20)`, clamp [0.25, 4]); el orden de confianza sigue siendo Población → Perfil → Jugador |