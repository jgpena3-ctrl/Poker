# Mapa de dependencias HU/MW (2026-11-13)

**Estado:** mapa read-only. No implementa cambios, no regenera artefactos y no
activa multiway.

**Objetivo:** saber qué dato, modelo y función alimentan cada decisión para
poder corregir HU sin romper MW, y para que el futuro motor MW no herede
dependencias ocultas.

**Snapshot:** commit `8197eee`; hashes completos en
`DISCREPANCIAS_AUDITORIA_2026-11-13.md`.

## 1. Capas

```
data/                         artefactos de entrada
  ↓
interpretación preflop        contrato, acciones, denominadores
  ↓
contexto y estado             stack, bote, board, rivales activos
  ↓
rangos y perfiles             ProfileRangeModel / PostflopRangeModel
  ↓
equity                        actual, showdown, EV por acción
  ↓
política                      rules.plan / select_best
  ↓
presentación y registro       insight, panel, decision_log
  ↓
herramientas y tests          auditoría, paridad, invariantes
```

## 2. Ruta live HU (la que decide)

```
recorder_live / estado de la mesa
  → AsistenteLive._villain_id          un solo rival
  → AsistenteLive._perfil_for          TIBURON / PEZ
  → _Models.range_model                ProfileRangeModel.load()
  → _rango_main / postflop_model       prob_vec / update
  → Situation / equity_vs_range        equity actual
  → rules.plan(n_players=...)          plan postflop
  → rules.select_best(evs, rp)         acción
  → _log_recommendation / insight      presentación
```

Puntos exactos:

| Etapa | Archivo:línea | Qué decide | Riesgo |
|---|---|---|---|
| Rival principal | `motor/asistente_live.py:706` | PID del agresor o del stack mayor | Un solo rival; no representa MW |
| Perfil | `motor/asistente_live.py:684` | PEZ/TIBURON por stack o media | No es estilo; default oculta falta de datos |
| Rango del rival | `motor/asistente_live.py:1131` | `_rango_main` con `prob_vec` | Un rango, no un conjunto |
| Rango postflop | `motor/asistente_live.py:1594` | `postflop.prob_vec` | Perfil y reach acoplados |
| Equity | `motor/situation.py:54` | equity actual contra un rango | No es showdown |
| Plan | `motor/rules.py:545` | reglas postflop con `n_players` | `n_players` no cambia el rango |
| Selección | `motor/rules.py:622` | mejor EV finito | Depende de los EV calculados |
| Registro | `motor/asistente_live.py:1690` | `decision_log` | Debe conservar fuente y versión |

La ruta live **no** usa `prob_vec_player` ni `player_omega`; usa
`range_model.prob_vec(...)` y elige un solo `villain`.

## 3. Ruta live preflop (matrices)

```
acciones preflop
  → _preflop_raises(actions, hero_pos)      solo cuenta 'r'
  → _pf_rival_pos(hand, hero_pos, spot)     agresor para la tabla
  → _pf_freq(base, pos, vs, hand_idx)
  → preflop.lookup_table / _pf_table_lookup
  → _pf_evs(f_raise, f_call)
  → _sample_preflop_action(ev, seed)
  → evs.chosen
```

Puntos exactos:

| Etapa | Archivo:línea | Qué hace | Riesgo |
|---|---|---|---|
| Conteo de subidas | `motor/asistente_live.py:379` | cuenta `r` | ignora `b` |
| Limp manual | `motor/asistente_live.py:1368` | mira `c` antes de subida | ignora limp corto `b` |
| Elegir rival | `motor/asistente_live.py:197` | primer/segundo agresor | no usa el contrato |
| Consulta tabla | `motor/asistente_live.py:347` | `preflop.lookup_table` | fallback puede ser silencioso |
| EV preflop | `motor/asistente_live.py:393` | reescala probabilidades | no es EV monetario completo |
| Sorteo | `motor/asistente_live.py:437` | muestrea según frecuencias | acción no determinista; semilla |
| Contrato | `motor/asistente_live.py:47` | importa `first_decision`/`table_plan` | **solo sombra**, no fuente |

La ruta live preflop **no** usa `first_decision` ni `table_plan` como fuente;
los importa para el log de sombra (`_preflop_shadow_*`, alrededor de
`motor/asistente_live.py:1911`).

## 4. Ruta demo/laboratorio

```
recommend_loop.recommend
  → build_villain_range
  → _build_multiway_range
  → RangeState.union(...)
  → equity_vs_range / runout_equity
  → rules.plan
  → select_best
  → Recommendation
```

Puntos exactos:

| Etapa | Archivo:línea | Qué hace | Riesgo |
|---|---|---|---|
| Entrada | `motor/recommend_loop.py:256` | `recommend()` | No es la ruta live |
| Rango rival | `motor/recommend_loop.py:191` | `build_villain_range` | HU o multiway aproximado |
| Multiway | `motor/recommend_loop.py:160` | `_build_multiway_range` | usa `union()` |
| Unión | `motor/recommend_loop.py:185` | suma masas | no es probabilidad conjunta |
| Etiqueta | `motor/recommend_loop.py:339` | “multiway aprox.” | la etiqueta no corrige la equity |
| Plan | `motor/recommend_loop.py:424` | `rules.plan` | depende de `n_players` |
| Sombra | `motor/recommend_loop.py:448` | `multiway` por `rp` o `n_players` | una sola sombra de MW |

`asistente_live` importa de `recommend_loop` únicamente `_equity_vs_rival`
(`motor/asistente_live.py:1246`), no `recommend`. `run_demo` es el consumidor
de `recommend` (`motor/recommend_loop.py:611`); los tests también lo usan, pero
no son producción.

## 5. Entrenamiento y artefactos

```
hands_db.jsonl
  ├─ learn.load_hands
  │    ├─ learn.preflop_events (legacy)
  │    ├─ PreflopStats
  │    └─ multiway.metrica_politica
  ├─ observations.extract_hands
  │    └─ behavior.behavior_table
  │         └─ behavior.build → data/behavior.json
  └─ postflop_ranges.build → data/postflop_ranges.json

preflop_matrices.json
  ├─ preflop.load_tables
  │    ├─ lookup_table / audit_engine_coverage
  │    └─ _pf_table_lookup (live)
  └─ player_ranges._load_tables
       └─ ProfileRangeModel._prior_grid

profile_ranges.json
  └─ ProfileRangeModel.load → prob_vec (live)

behavior.json
  └─ behavior.Oracle → PostflopRangeModel
```

Dependencias críticas:

| Artefacto | Consumidor | Uso | No usar para |
|---|---|---|---|
| `hands_db.jsonl` | `learn`, `observations`, `multiway` | etiquetas, stats, métrica | asumir inmutable o certificado |
| `preflop_matrices.json` | `preflop`, `player_ranges` | frecuencias y priors | inventar tabla ausente |
| `profile_ranges.json` | `ProfileRangeModel` | prior por perfil/spot | presentar flat prior como observado |
| `behavior.json` | `behavior.Oracle` | P(A|C) postflop | equity |
| `postflop_ranges.json` | `PostflopRangeModel` | P(A|H) postflop | rango multiway conjunto |
| `decisions.jsonl` | logger / F0 | trazas de decisión | decidir en vivo |
| `observations.json` | offline / F0 | observaciones | sustituir `hands_db` sin contrato |

## 6. Acoplamientos que no se ven en una firma

1. **`preflop_matrices` y `profile_ranges`:** el prior no es independiente de
   las tablas; un cambio de matrices puede cambiar el prior sin cambiar la
   firma de `ProfileRangeModel`.
2. **`ProfileRangeModel._prior_grid`:** tres caminos (tabla simple, tabla de
   par, `FLAT_PRIOR`). El tercero es el 78,5 % de los jugadores.
3. **`_perfil_for` y `postflop.prob_vec`:** el perfil se usa como clave de
   tabla; un cambio de clasificación cambia el rango y la equity.
4. **`n_players`:** llega a `rules.plan` y a los tamaños, pero no al rango.
   Un mismo `n_players>2` puede seguir produciendo una equity de un rival.
5. **`MULTIWAY_SOPORTADO`:** es un flag de presentación/contrato, no una
   barrera de ejecución. `rules.plan` puede construir un plan MW con
   `multiway_soportado=False`; la decisión debe declarar que no está soportada.
6. **`recommend_loop`:** `union()` y la etiqueta “aproximado” conviven; la
   etiqueta no evita que un consumidor use el número como equity.
7. **Sombra preflop:** `asistente_live` calcula contrato para medir, no para
   decidir. Es la prueba de que la migración es posible, pero no la migración.
8. **Tests:** `test_multiway_soportado.py` fija consumidores esperados y
   prohíbe `union()` en producción; no valida la calidad estadística.

## 7. Matriz de dependencias por cambio

| Si se cambia… | Hay que revisar… | Validación mínima |
|---|---|---|
| `preflop_contract` | `asistente_live` preflop, `learn.preflop_events`, sombra, tests | paridad de etiquetas y acciones |
| `_preflop_spot` | `_rango_main`, `_preflop_shadow_spot`, prior live | comparar tabla elegida, no solo spot |
| `_preflop_raises` | `_recom_preflop`, `_pf_rival_pos` | matriz `b/r`, limp y short limp |
| `profile_ranges` | `ProfileRangeModel`, `_rango_main`, postflop | calibración por perfil y cobertura |
| `preflop_matrices` | `preflop.lookup_table`, `_pf_table_lookup`, priors | cobertura exacta/alias/missing |
| `postflop_ranges` | `postflop.prob_vec`, `_rango_main` | reach, blockers y calibración |
| `rules.plan` | live, `recommend_loop`, tests de contratos | decisión y EV; no solo firma |
| `MULTIWAY_SOPORTADO` | live, demo, tests, panel | ningún MW sin ruta y rango explícitos |

## 8. Trazabilidad y datos dinámicos

- El script de auditoría imprime commit y SHA-256 de los artefactos en cada
  ejecución (`tools/auditar_estrategia_reproducible.py`).
- No hay un campo de versión dentro de los JSON; el hash es la identidad
  mínima actual.
- `hands_db.jsonl` puede corregirse en el futuro. Cualquier cifra de este
  mapa queda ligada al hash, no a la fecha.
- No se regeneran derivados sin justificación y sin registrar:
  `hands_db → observations/behavior/postflop_ranges/profile_ranges`.
- Una corrección histórica debe declarar si invalida etiquetas, priors,
  matrices o métricas. No se propaga sola.

## 9. Frontera de activación

| Elemento | Estado actual | Condición para cambiar |
|---|---|---|
| `MULTIWAY_SOPORTADO` | `False` | diseño + ruta + validación + revisión |
| Ruta live | un villano | conjunto de rivales y equity declarada |
| `recommend_loop` MW | `union()` aproximado | rango conjunto y etiqueta verificable |
| `FLAT_PRIOR` | 78,5 % de los casos | cobertura y calibración por fuente |
| Equity | actual vs showdown mezcladas | campos separados y muestreo declarado |
| Datos | snapshot por hash | versionado y dependencia registrada |
