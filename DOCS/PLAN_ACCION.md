# Plan de acción — Motor de póker

Consolidación de las hojas de ruta `pegar_2.txt` y `pegar_3.txt` sobre `DOCS/PROYECTO.md`.
Orden por dependencias reales; ninguna medición sobre datos contaminados ni sobre código sin auditar.

## Fase 0 — Congelar base
- Tag `pre-audit-82b4fab`.
- Snapshot de `data/*.json` en `data/_snapshot_pre_audit/`.
- Decisión regrabar vs migrar DB en `DOCS/DECISIONES.md`.

## Fase 1 — Ventana de datos fiable (implementada parcialmente)
- `learn.load_hands(path=None, *, max_hands=None, reliable_only=False)` con `RELIABLE_HANDS=900`.
- Consumidores productivos usan `load_hands(reliable_only=True)` (asistente, behavior, stats, profile, observations, player_ranges, postflop_ranges, db_health, range_lab_gui, auditorías).
- Arreglar `medir_multiway.py` para usar la ventana fiable.

## Fase 2 — Auditar learn.py (implementada parcialmente)
- Ciega del BB identificada estructuralmente (primera acción + pos `BB`) y no contada como subida.
- `'b'`/`'r'` de ≤1BB sin subida previa se clasifica como `limp`, no `open`.
- `classify_first_action` ahora usa `amount` y `bb`.
- Pendientes: `opportunities()` denominadores, agregación por posición, `hand_known`.

## Fase 3 — Recorder (`amount` mixto)
- Separar `amount_type: observed | delta`.
- No decidir `b`/`c`/`r` comparando delta vs nivel.
- Procedimiento reproducible de migración/regrabado.

## Fase 4 — player_ranges.py
- `_prior_grid` por par de posiciones; avisar fallback.
- `load()` restaura `profiles` y `omega`.
- ω excluye al propio jugador de peers y renormaliza por celda.
- Documentar resolución individual de ω.

## Fase 5 — rules.py
- Contrato `candidates` vacío.
- Manejo explícito de EV `NaN`/inf.
- Usar o eliminar `nut_advantage`, `villain_bet_flop`.
- `_en_flop_ip` = IP real (no `not initiator`).
- Contrato `plan()` en preflop.

## Fase 6 — Pending + modo sombra
- Unificar definición de `pending`.
- Repetir `auditar_anchor.py` sobre 900 (anchor_match = 1).
- Cablear `equity_main` en `Asistente`.
- `passive_penalty` sigue NO CALIBRADO.

## Fase 7 — Alcance multiway
- Decisión: rediseño conjunto o limitación explícita a HU.
- Si HU: `recommend_loop` avisa/lanza con `n_players > 2`.

## Fase 8 — Deuda técnica menor
- `motor/__init__.py` docstring + `rules` re-export.
- `implied_odds.py` integrar o marcar experimental.
- Imports muertos / caché fuera del repo / `H_0350` / `OR_BB`.

## Fase D — Calibración (solo tras cerrar lo anterior)
- Cobertura por celda; identificar celdas no calibrables.
- Calibrar `BASE_WEIGHT_MAP` y `_ACTION_PROBS` con evidencia.
- Validar en modo sombra antes de activar.

Decisiones pendientes: regrabar vs migrar; HU vs multiway; `reliable_only` por defecto; renombrar ω.
