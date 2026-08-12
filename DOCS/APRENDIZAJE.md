# Aprendizaje desde hands_db (especificación — pegar4 + pegar5)

Este documento fija cómo el motor aprende de `data/hands_db.jsonl` y cómo
la información almacenada escala a **perfiles de jugador** (pegar5). Es el
punto de partida para que P(A|H) deje de ser heurística pura y se alimente
de decisiones reales. Objetivo inmediato: **frecuencias preflop** (limp,
open, 3-bet, ROL, squeeze); objetivo siguiente: **perfil de jugador** (vector
de estadísticas → modelo de rangos preflop + comportamiento postflop).

Convención de identidad: **`Jarduan` soy yo (Hero)** — sus manos se conocen
siempre. El resto de jugadores son rivales; su mano se conoce solo cuando el
historial la muestra (showdown / revelada), y según cómo quede registrada en
`hands_db.jsonl`.

---

## 1. Dos tipos de evidencia, nunca mezcladas

Frente a cada decisión de un jugador distinguimos por qué sabemos (o no) su
mano:

| Tipo | Mano | Aprende | Ejemplo |
|---|---|---|---|
| **Showdown / revelada** | `H` conocida | `P(A | H, contexto)` | "J9s check-call 50% en AT7ss" |
| **Sin showdown** | `H` desconocida | `P(A | contexto)` | "call 50% en AT7ss (sin ver cartas)" |

Regla del documento pegar4: **no mezclarlas como observaciones equivalentes**.
Cada registro lleva `hand_known=True/False` y el almacenamiento las separa.

Ambas son información: si Villain bet y su rival fold, sabemos *que* apostó
aunque no sepamos con qué carta. Además se registra **por qué cesó la
observación** de la mano del jugador:

```
fold · showdown · all-in sin showdown · mano interrumpida
```

(fold es información: esa acción ocurrió, aunque nunca veremos la mano).

## 2. Sesgo de supervivencia hasta showdown

Los showdowns NO son una muestra aleatoria. `AA`/`AK` llegan a showdown mucho
más a menudo que `72o`, porque `72o` suele fold antes de que se descubra su
mano. Conclusión: **nunca usar la frecuencia de showdown como frecuencia de
acción**.

Por eso se mantienen dos estadísticas separadas (para el mismo jugador y
contexto):

```
P(A | contexto)          <- TODAS las manos (denominador: oportunidades)
P(A | H, contexto)       <- solo manos reveladas (denominador: oportunidades)
```

Y deben ser compatibles: `Σ_H P(A|H)·P(H) = P(A|contexto)`. Si no se cumple,
hay un indicio de sesgo o de datos rotos.

## 3. Niveles del modelo

```
Nivel 1  P(A | contexto)                 ← todas las manos
Nivel 2  P(A | H, contexto)              ← manos reveladas
Nivel 3  P(H | A, contexto) ∝ P(A|H,C)·P(H|C)   ← inferencia en vivo (Range Engine)
```

El motor de rangos ya aplica el Nivel 3; este documento define cómo obtener
los Niveles 1 y 2 desde el historial real. El perfil de jugador (capítulo 5)
no crea un nivel nuevo: entra como **una condición más del contexto C**

```
P(A | H, C, perfil)     P(H | A, C, perfil) ∝ P(A | H, C, perfil) · P(H | C, perfil)
```

El perfil selecciona y ajusta la `P(A|H)` base (matrices) y el rango inicial
(§5.6), pero las reglas de evidencia del §1 aplican igual dentro del perfil.

## 4. Cómo guardamos cada decisión (`DecisionObservation`)

Una decisión de un jugador (una calle, no una mano completa):

```
DecisionObservation(
    player="Jarduan" | "VillainX",
    player_kind = "hero" | "villain",
    street="preflop" | "flop" | "turn" | "river",

    hand_known = True/False,
    hand       = ["Js", "9s"] | None,

    position   = "BB",
    players    = n (multiway / heads-up),
    pot        = 8.5,
    effective_stack = 97.5,
    spr        = 11.4,

    preflop_sequence = "BTN_open_BB_call",
    action_history   = [ {pos, action, amount}, ... ],

    board      = ["As", "Td", "7s"] | [],
    board_texture = {...},

    action     = "call",            # f/x/c/b/r
    sizing     = 0.50,              # fracción del bote (bet/raise)
    raised_before = {"hero": True, "other": False},

    end_reason = "fold" | "showdown" | "all_in" | "interrupted",
    outcome_bb = +2.4 | None        # botes ganados en BB (si se sabe)
)
```

`hero` es la entrada más limpia: en `Jarduan` `hand_known` es **siempre
True** y `outcome_bb` se puede calcular (sabemos bote final y quién lo ganó).

## 5. Perfil de jugador — la capa intermedia (pegar5)

La cadena es: **jugador → estadísticas → perfil → modelo de rangos → modelo
postflop del rango → explotación**. No hace falta conocer 10.000 manos de un
rival concreto: unas pocas sirven para aproximar su perfil y el modelo
poblacional aporta el resto (§5.5).

```
Jugador                    Perfil                Modelo del rango
   │                            │                       │
   ├── VPIP   ─┐                │                       │
   ├── PFR    ─┤                ▼                       ▼
   ├── 3BET   ─┼→  vector de  → Perfil de jugador →  rango preflop
   ├── C-BET  ─┤   estadísticas  (buckets+label)        │
   ├── WTSD   ─┤                                        ▼
   ├── W$SD   ─┘                               modelo postflop del rango
   └── ...                                    (freq·contexto → P(A|C,perfil))
```

### 5.1 Vector de estadísticas — el perfil es el vector, no la etiqueta

Una sola etiqueta (`TAG`, `LAG`, `Nit`, `Calling Station`) es demasiado
grueso: dos TAGs pueden tener C-BET 82% y 48%. Se usa el **vector numérico**
directamente y, opcionalmente, una etiqueta derivada de sus bins:

```
Profile
──────────────
VPIP    31.4
PFR     12.1
3BET     3.2
C-BET   67.5
WTSD    34.1
W$SD    47.8
```

### 5.2 Estadísticas de transición y sus denominadores

Para que el modelo postflop sea útil no basta el núcleo VPIP/PFR/3BET/C-BET/
WTSD/W$SD: hay que describir las **transiciones** (qué hace ante las acciones
de los demás). Cada una se define como un par **acción/oportunidad** con el
mismo rigor que la tabla preflop (§6), para no volver a caer en el sesgo de
supervivencia (un "frecuencia sobre showdowns" NO vale):

| Stat | Denominador (oportunidad) | Numerador |
|---|---|---|
| VPIP | todas las primeras decisiones preflop con entrada (`bb` included) | cualquier acción que mete dinero (call, bet, raise; `x` y `f` no) |
| PFR | idem VPIP | raise/preflop (open, rol, 3bet, squeeze, 4bet) |
| 3BET | `facing_open` | `3bet` + `squeeze` |
| 4BET | `facing_3bet` | `4bet` |
| C-BET | flops donde el jugador es el **último agresor preflop** y no ha habido bet en el flop | `b` en ese flop |
| Fold-to-C-BET | flop defendiendo un bet ajeno (`facing_cbet`) | `f` |
| Call-C-BET | idem | `c` |
| Raise-C-BET (XR) | idem | `r`/`b` sobre el bet ajeno |
| Turn barrel | turn con iniciativa (apostó en flop) | `b` en turn |
| Fold-to-barrel | turn defendiendo bet ajeno | `f` |
| River bet | river con iniciativa | `b` en river |
| River raise / fold | river defendiendo | `r` / `f` |
| WTSD | manos en las que vi flop activo | ¿llegó a showdown? |
| W$SD | llegó a showdown | ¿ganó el bote? |

W$SD/WTSD son **features del perfil** y no se usan para ajustar un combo
concreto: un WTSD alto + W$SD bajo señala "llega demasiado y pierde"; eso
modifica el perfil, nunca directamente `P(A|H)` de una mano (§5.8).

### 5.3 De los datos al vector

- Cada `DecisionObservation` aporta a los contadores de la tabla (acciones +
oportunidades), con `hand_known=True/False` intacto: las frecuencias
agregadas por perfil siguen sin mezclar evidencia (§1/§2).
- `player_kind` separa la contribución de Hero de la de los rivales; ambas
se agregan igual a la población (§5.9).
- Estadísticas con denominador 0 quedan `None` (nunca 0 % inventado); el
  consumidor las trata como "sin muestra".

### 5.4 Buckets y etiquetas derivadas

Para que un perfil tenga masa estadística se discretiza el vector manteniendo
el dato original:

```
Profile #17   buckets:  VPIP 29-33 · PFR 10-14 · 3BET 2-4 · WTSD 31-36
  vector:      VPIP 31.4 · PFR 12.1 · 3BET 3.2 · ...
  etiqueta:   loose-passive (derivada de los bins, no es la identidad)
```

Bin = identidad agrupada; vector = lo que se usa para buscar "jugadores
similares" y para la mezcla con las matrices.

### 5.5 Confianza por tamaño de muestra

```
40 manos   → perfil probable   (distribución P(perfil | observaciones))
500 manos  → perfil confiable
5000 manos → el modelo individual puede separarse del perfil
```

- Con poca muestra se mantiene la **distribución posterior** `P(perfil |
obs)`, no una única etiqueta. El motor evalúa la mezcla (o el bin dominante
cuando esté muy por encima).
- El modelo individual **solo se activa cuando supera al poblacional**; nunca
  se descarta el perfil por tener más manos del jugador.

### 5.6 Rango preflop del perfil (integración con el Range Engine)

El Range Engine puede partir del rango del perfil en lugar de GTO:

```
Villain → perfil = loose-passive → situación preflop → rango inicial del perfil
```

Con las matrices actuales (`preflop_matrices.json`, 112 tablas 13×13), el
rango del perfil se obtiene así:

```
initial_range(perfil, pos, spot) = base_matrix(pos, spot) · ω(perfil, spot)
ω = frecuencia real del perfil en el spot / frecuencia base del spot   (clamp 0..1)
```

`ω` escala cada celda de la matriz según lo que el perfil realmente hace
(open de 31 % vs los ~12 % base del UTG ⇒ ω ≈ 2.5 en el spot open-UTG...). Las
frecuencias vienen del §5.2, así que el ajuste es constructivo y transparente.

### 5.7 Modelo postflop del rango (behavior tables)

Para cada perfil se agrega la tabla de acciones condicionada por contexto:

```
Profile #17 · BTN vs BB · SRP · board A-high seco
    c-bet      71 %
    check      29 %

Profile #17 · BTN vs BB · SRP · board A-high húmedo
    c-bet      49 %
    check       51 %
```

Dimensiones del contexto (mismas que la §7):

```
street · position · pot_type (SRP/3BP/4BP) · nº jugadores ·
board_texture · preflop_sequence · sizing recibido
```

Resultado por tamaño además:

```
Flop (Profile #17)
  check 52 % · bet 25 % 11 % · bet 33 % 17 % · bet 50 % 14 % · bet 75 % 6 % ·
  raise 1 %
```

Estas tablas son el `P(A|C, perfil)` del Nivel 1; con manos reveladas
(hand_known) del mismo bucket se aproxima `P(A|H, C, perfil)` (Nivel 2) — el
sesgo de §2 aplica igual (los showdowns no son muestra aleatoria).

**Implementado (agosto 2026):** `motor/postflop_ranges.py` materializa el
Nivel 2: buckets de fuerza (5) de cada combo sobre el board + evidencia de
mano conocida (street, facing, bucket) con shrinkage al prior del Oracle
(`data/postflop_ranges.json`); `recommend_loop` lo consume con
`villain_postflop` (detalles en TECNICO §3.8).

### 5.8 WTSD/W$SD: features, no inputs de combo

Coinciden con §2: no usar WTSD/W$SD **para tocar la `P(A|H)` de un combo
concreto**. Son características del perfil (estilo de llegada al showdown) y
se usan para reconocer tipo de jugador y para detección de desvíos, pero la
actualización bayesiana sigue operando sobre `P(A|H, C, perfil)`.

### 5.9 Hero dentro de la población

Las manos de Jarduan (hand_known=True siempre) alimentan la **misma** base de
datos de perfiles: contestan "¿cómo juega un jugador con este perfil?" al
acumular sus decisiones como cualquier `player_kind`.

Su perfil personal (Capa 1/2, apartado 8) es **otra cosa**: sirve para
detectar desvios respecto a la estrategia de referencia, no para que el motor
juege "como él". Durante una sesión el motor solo ve:

```
Hero    → juega normalmente (su perfil no interviene en el consejo)
Villain → perfil estimado de la población
```

## 6. Frecuencias preflop — definiciones concretas

Para cada jugador y mano, se toma su **primera decisión preflop** de la
mano (fold incluido). Se clasifica según el estado del pot preflop al momento
de actuar:

| Estado (cuando actúa) | action | Categoría |
|---|---|---|
| sin raise previo, sin limpers | `f` | `fold` |
| sin raise previo, sin limpers | `c` (≤ BB) | `limp` |
| sin raise previo, sin limpers | `b/r` | `open` (RFI) |
| sin raise previo, con ≥1 limp | `f/c` | `fold` / `call_limp` |
| sin raise previo, con ≥1 limp | `b/r` | `rol` (raise over limpers) |
| con 1 raise previo (n ls callers) | `f` | `fold_vs_open` |
| con 1 raise previo | `c` | `call_open` |
| con 1 raise previo, sin callers antes | `r` | `3bet` |
| con 1 raise previo + ≥1 caller | `r` | `squeeze` |
| con ≥2 raises previos | `c/f/r` | `fold_vs_3bet` / `call_3bet` / `4bet` |
| BB sin raisers | `x` | `bb_check` |

**Denominadores (oportunidades)**: caen en el mismo estado del momento de
su decisión:

```
list_opp(cat):
    open/limp/call_limp/rol   ← opciones cuando llega sin raise previo
    call_open/3bet/squeeze/fold_vs_open ← cuando llega contra 1 raise
    call_3bet/4bet/fold_vs_3bet ← cuando llega contra 2+ raises
```

- `freq(cat) = #categorías / #oportunidades del estado`.
- Cada jugador entra una vez por mano (su primera decisión preflop).
- El `bb_check` del BB se cuenta como decisión (oportunidad de rol perdida/check).
- Los players que no pudieron actuar (fold de otro antes, etc.) no aportan.

### 6.1 Los datos tienen ruido
El recorder captura frames y las acciones tienen artefactos (amounts no
sanos, dobles registros, `x` con amount). El loader:
- **valida** cada mano: debe tener `players` y `streets`, sin duplicados de
  una misma decisión por jugador/calle;
- **descarta** manos sin preflop parecido (sin actions);
- mantiene las manos con acciones raras (se marcan, no se borran).

## 7. Postflop — contexto rico

Para postflop **no basta "call flop"**: el contexto es exigente (pegar4 §10):

```
street · position · number_of_players · pot_size · SPR · pot_type (SRP/3BP/4BP)
board_texture · previous_action(bet size / check / raise) · action_history
```

`call flop vs 33%` ≠ `call flop vs 150%`; `check-raise` en `A72r` ≠ en `987ss`.
El estrés está en guardar el `sizing` (fracción del bote) y el
`board_texture` como claves del contexto. **Implementado**: `observations.py`
extrae la observación postflop (street · pot · SPR · textura · facing ·
sizing; `data/observations.json`), que alimenta las behavior tables por
perfil (§5.7) y el modelo `P(A|H)` postflop (`postflop_ranges.py`,
TECNICO §3.8). Pendiente (decisión pegar7, §10): **no** añadir más
dimensiones de contexto de golpe — con 327 manos el grid se atomiza; el
fallback jerárquico (granular → por_facing → perfil → población) ya cubre
los huecos.

## 8. Perfil de Hero (Jarduan) — dos capas

- **Capa 1 — comportamiento real:** `P(A | H, C)` para ti (dataset completo
  etiquetado: mano conocida siempre). Sirve para describir qué haces.
- **Capa 2 — calidad:** PDF `resultado vs modelo`: en cada decisión
  guardamos `Decision: model_action + EV` del motor y `hero_action` real; la
  diferencia de EV construye el mapa de errores (`over_aggression`,
  `over_calling`, `over_folding`, `overvaluing`...).

El asistente **no aprende a "copiarte"**: tu perfil es para detectar
desvíos respecto a la estrategia de referencia (board seco, conectado,
multiway), no para imitarte. Las mismas manos de Jarduan sí entran en la
base poblacional de perfiles (§5.9), pero su estilo solo contribuye a
describir cómo juega la población con ese perfil: el motor no copia tu juego.

## 9. Estado y módulos

- `motor/learn.py` — hecho (julio 2026): carga `hands_db.jsonl`, clasifica la
  **primera decisión preflop** de cada jugador y agrega frecuencias por estado.
  - `preflop_events(hand)` → `[PreflopEvent]` (con `hand_known`);
  - `classify_first_action(...)`, `PreflopStats` (cats/denoms/known/freq),
    `report()`, `to_dict()`, CLI `--json`;
  - output generado: `data/preflop_stats.json` (327 manos reales).
- `data/preflop_stats.json` — frecuencias de la DB (generado).
- `motor/stats.py` — **hecho (julio 2026)**: `TransitionStats.from_hands()`
  agrega las estadísticas de transición del §5.2 con denominadores reales;
  C-BET/barrel/River con gate de iniciativa; WTSD/W$SD con gate de showdown
  y `None` para hero (sus cartas siempre en el DB: no inferibles). Genera
  `data/player_stats.json` (`python -m motor.stats --json`).
- `motor/profile.py` — **hecho (julio 2026)**: buckets por estadística con
  posterior Beta (bin = media posterior, confianza = masa modal), etiqueta
  derivada (TAG/Nit/LAG/Loose-passive/...), `reliability()` por nº de manos
  (§5.5) y `omega(table, base_rates)` con clamp [0.25, 4] para escalar las
  matrices preflop (§5.6). Generador: `python -m motor.profile --json` →
  `data/profiles.json`.
- `motor/observations.py` — **hecho (agosto 2026)**: extrae `DecisionObservation`
  por decisión y calle (§4): street, pot_type (SRP/3BP/4BP), pot_before,
  stack efectivo/SPR, jugadores activos vs folds, textura del board
  (monotone/two_tone/rainbow [+pair]; boards incompletos del recorder → sin
  clase), `facing` (none/cbet/bet/barrel/raise según quién puso la apuesta
  vigente), sizing (fracción del bote, solo b/r) y secuencia preflop.
  `behavior_table()` agrega las frecuencias de acción por
  (perfil, street, textura, facing) con `min_n` (anti-ruido) y el sizing
  medio. Generador: `python -m motor.observations --json` →
  `data/observations.json` (3373 observaciones sobre 327 manos).
- `motor/behavior.py` — **hecho (agosto 2026)**: materializa las behavior
  tables por perfil: `build(hands)` cruza `Profiles.from_hands` (etiqueta por
  jugador) con las observations → `granular` (perfil, street, textura,
  facing) y `por_facing` (sin textura, más volumen), cada casilla con
  `n >= min_n` (3 por defecto) y el sizing medio de las b/r. Generador:
  `python -m motor.behavior --json --min-n 3` →
  `data/behavior.json` (74 casillas granular + 50 por-facing sobre 327
  manos). Los perfiles sin volumen (Loose-reg, Passive-reg) apenas aportan
  casillas: señal de que el primer uso real vendrá al crecer el dataset.
- `motor/behavior.py` → `Oracle` — **hecho (agosto 2026)**: `Oracle.p_action(
  label, street, facing, texture)` devuelve P(A|C) en el contexto postflop
  con fallbacks escalonados: granular → por_facing → agregado del perfil →
  población; siempre normalizada y con `sizing` de referencia. CLI:
  `python -m motor.behavior --probs` → `data/behavior_probs.json`.
- `motor/decision.py` → `OracleResponse` — **hecho (agosto 2026)**: respuesta
  del rival en el EV derivada del perfil: `OracleResponse(oracle, label,
  (street, facing, texture))` se pasa como `response_fn` a `compute_evs` y
  funde P(A|C) con la heurística por equity (alpha = n/fade_n, n de la celda
  del Oracle; sin celda → heurística pura). `pf/pc/pr` = P(fold/call/raise)
  normalizados sobre las tres.
- **Siguiente hito:** capa 2 del Hero (§8): mapa de desvíos
  (`hero_action` vs `model_action` en cada decisión → over_aggression /
  over_calling / over_folding / overvaluing) con las observaciones ya
  extraídas.
- La fusión final con `preflop_matrices.json` (la `action_probability` real =
  mezcla base · ω del perfil) se cierra cuando haya volumen suficiente.
