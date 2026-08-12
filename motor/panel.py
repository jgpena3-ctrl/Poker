"""panel.py — salida inspeccionable del motor (consola). El panel explica lo
que el Decision recomienda usando EV y rangos; nunca alimenta al Decision.

ARQUITECTURA §8.2: la distribución agregada (nuts/valor/draws/aire) es para
este panel, no para el Decision Engine.
"""
from typing import Optional

from .decision import EvTable
from .situation import Situation


def format_cards(cards) -> str:
    """['Ah', 'Kd'] -> 'AhKd'."""
    return ' '.join(str(c) for c in cards)


def format_evs(evs: EvTable, best_label: Optional[str] = None) -> str:
    """Tabla de EV ordenada desc; la recomendada marcada con flecha."""
    if best_label is None:
        best_label = evs.best()[0]
    items = sorted(evs.ev.items(), key=lambda kv: kv[1], reverse=True)
    lines = []
    for label, value in items:
        marker = ' <==' if label == best_label else ''
        lines.append(f'    {label:8s} {value:+7.2f} BB{marker}')
    return '\n'.join(lines)


def format_situation(sit: Situation) -> str:
    """Líneas destacadas del Situation Engine (que consume el panel)."""
    tex = sit.texture
    flags = []
    if tex.get('rainbow'):
        flags.append('rainbow')
    elif tex.get('two_tone'):
        flags.append('two-tone')
    elif tex.get('monotone'):
        flags.append('monotone')
    if tex.get('trips'):
        flags.append('paired-trips')
    elif tex.get('pairs'):
        flags.append(f"pair {tex['pairs']}")
    flags.append(f'run {tex.get("straight_run")}')

    lines = [
        f'  Hero : {format_cards(sit.hero_codes)}',
        f'  Board: {format_cards(sit.board_codes)}',
        f'  Textura: {", ".join(flags)}',
        f'  Equity vs rango: {sit.equity * 100:5.1f}% '
        f'(w {sit.wins * 100:5.1f} | t {sit.ties * 100:4.1f} | '
        f'l {sit.losses * 100:5.1f}) | {sit.combos_evaluados} combos',
    ]
    if sit.pot_odds is not None:
        lines.append(f'  Pot odds: {sit.pot_odds:.1%} (pagando {sit.pot_odds:.1%} min)')
    if sit.spr is not None:
        lines.append(f'  SPR: {sit.spr:.1f}')
    return '\n'.join(lines)


def format_insight(sit: Situation, evs: EvTable,
                   villain_label: str = 'rango',
                   runout: bool = False) -> str:
    """Panel completo: situación + tabla de EV + recomendación."""
    best_label, best_value = evs.best()
    head = f'== {format_cards(sit.hero_codes)} | {sit.street} | {sit.position or "-"}'
    rule = '=' * max(len(head), 30)
    lines = [
        rule,
        head,
        format_situation(sit),
        f'  Rival: {villain_label or "unformatted"}',
    ]
    if runout and len(sit.board_codes) < 5:
        lines.append('  Ramas pasivas: equity a showdown con sorteo de '
                     'turn+river (MVP 2 parcial)')
    lines += [
        f'-> Mejor accion: {best_label}  (+{best_value:.2f} BB)',
        format_evs(evs, best_label),
        rule,
    ]
    return '\n'.join(lines)