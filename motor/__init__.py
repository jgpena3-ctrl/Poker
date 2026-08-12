"""motor — núcleo del asistente de decisiones (fase 2).

Módulos:
    cards          : encoding de cartas y bitmasks 0..51
    ranges         : 1326 combinaciones, RangeState (reach/weight), update bayesiano
    preflop        : tablas de decisión preflop (data/preflop_matrices.json)
    hand_evaluator : fuerza de manos (backend vectorizado, benchmark first)
    situation      : equity vs rango, pot odds, SPR, textura (Situation)
    decision       : EV por acción (MVP 1: EV inmediato + respuesta modelada)
    panel          : salida inspeccionable (consola; solo para explicar)
    recommend_loop : orquestador anytime → Recommendation antes del deadline
    learn          : frecuencias preflop desde hands_db.jsonl (PreflopStats)
    stats          : estadísticas de transición por jugador (§5.2)
    profile        : perfiles (buckets, etiqueta, confianza, ω matrices)
    observations   : DecisionObservation por decisión/calle (§4) → behavior tables
    behavior       : behavior tables por perfil (perfil×street×textura×facing)
    player_ranges  : P(A|H, spot, perfil) preflop → grids 13×13 → RangeState
    postflop_ranges: P(A|H, street, facing, perfil) postflop, buckets de fuerza
                     + shrinkage al Oracle (pega6, paso 3)
"""
from . import (  # noqa: F401
    cards, ranges, preflop, hand_evaluator, situation, decision, panel,
    recommend_loop, learn, stats, profile, observations, behavior,
    player_ranges, postflop_ranges,
)