"""behavior.py — behavior tables por perfil (APRENDIZAJE.md §5.7/§7).

Cruce de los perfiles (motor/profile.py) con las DecisionObservation
(motor/observations.py): cada jugador contribuye a la tabla de su etiqueta
de perfil (TAG/LAG/Regular/...), agregando frecuencias de acción por

  - granular: (perfil, street, textura, facing)   [§7: contexto completo]
  - por_facing: (perfil, street, facing)          [más volumen, sin textura]

Cada celda tiene n mínimo (anti-ruido) y el sizing medio de las b/r.
El CLI genera `data/behavior.json`.
"""
import json
import os
from typing import Dict, Optional

from .learn import load_hands
from .observations import STREETS, extract_hands
from .profile import Profiles

DEFAULT_MIN_N = 3
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def behavior_table(obs, by_player: Dict[str, str],
                   min_n: int = DEFAULT_MIN_N,
                   with_texture: bool = True) -> dict:
    """Frecuencias de acción por label (+ street, ± textura, facing).

    `by_player`: {nombre -> etiqueta de perfil}. Devuelve
    {(perfil, street[, textura], facing): {'n': k, 'f': %, 'x': %, 'c': %,
    'b': %, 'r': %, 'sizing_mean': p}} con n>=min_n.
    """
    agg = {}
    for o in obs:
        label = by_player.get(o.player, '?')
        key = (label, o.street)
        if with_texture:
            key += (o.texture_class or '-',)
        key += (o.facing,)
        cell = agg.setdefault(key, {'n': 0, 'f': 0, 'x': 0, 'c': 0, 'b': 0,
                                    'r': 0, 'size': 0.0})
        cell['n'] += 1
        cell[o.action] += 1
        if o.action in ('b', 'r') and o.sizing is not None:
            cell['size'] += o.sizing
    result = {}
    for key, cell in agg.items():
        if cell['n'] < min_n:
            continue
        out = {a: round(cell[a] / cell['n'], 3)
               for a in ('f', 'x', 'c', 'b', 'r')}
        if cell['b'] + cell['r']:
            out['sizing_mean'] = round(cell['size'] / (cell['b'] + cell['r']),
                                       3)
        out['n'] = cell['n']
        result[key] = out
    return result


def labels_from_hands(hands) -> Dict[str, str]:
    """Etiqueta del perfil por jugador (Profiles.from_hands)."""
    profs = Profiles.from_hands(hands)
    return {name: p.label for name, p in profs.profiles.items()}


ACTIONS = ('x', 'b', 'c', 'f', 'r')


class Oracle:
    """P(A|C) postflop por perfil con fallbacks escalonados (§7).

    Consulta `p_action(label, street, facing, texture=None)` y devuelve la
    distribución de acciones normalizada. Niveles de evidencia:

      1. granular   : (label, street, texture, facing) — contexto completo
      2. por_facing : (label, street, facing)          — sin textura
      3. label      : agregado de la etiqueta por street (cualquier facing)
      4. poblacion  : agregado de todas las etiquetas (perfil nuevo/descon.)

    `sizing` = sizing medio de las b/r de la celda ganadora (None si no
    hay). Pensado para alimentar `P(A|C)` del rival en la capa postflop de
    decisión (con los ω preflop ya escalados).
    """

    def __init__(self, data: dict):
        self.granular = dict(data.get('granular', {}))
        self.facing = dict(data.get('por_facing', {}))
        self.labels = list(dict(data.get('profiles', {})).values())
        self._label_level = None
        self._poblacion = None

    # --------------------------------------------------------------

    def _by_label(self, label, street):
        """Agregado (label, street) desde por_facing: {action: count}."""
        agg = {a: 0.0 for a in ACTIONS}
        for (lbl, st, fac), cell in self.facing.items():
            if lbl != label or st != street:
                continue
            for a in ACTIONS:
                agg[a] += cell.get(a, 0.0) * cell['n']
        return agg

    def _population(self, street):
        if self._poblacion is None:
            self._poblacion = {}
        if street not in self._poblacion:
            agg = {a: 0.0 for a in ACTIONS}
            for (lbl, st, fac), cell in self.facing.items():
                if st != street:
                    continue
                for a in ACTIONS:
                    agg[a] += cell.get(a, 0.0) * cell['n']
            self._poblacion[street] = agg
        return self._poblacion[street]

    @staticmethod
    def _norm(agg, source, sizing=None, n=0):
        total = sum(agg[a] for a in ACTIONS)
        if total <= 0:
            return None
        return {'actions': {a: round(agg[a] / total, 4) for a in ACTIONS},
                'source': source, 'sizing': sizing, 'n': n}

    def p_action(self, label, street, facing, texture=None):
        key1 = (label, street, texture or '-', facing)
        cell = self.granular.get(key1) if texture else None
        if cell:
            return self._norm({a: cell.get(a, 0.0) for a in ACTIONS},
                              'granular', cell.get('sizing_mean'), cell['n'])
        key2 = (label, street, facing)
        cell = self.facing.get(key2)
        if cell:
            return self._norm({a: cell.get(a, 0.0) for a in ACTIONS},
                              'por_facing', cell.get('sizing_mean'), cell['n'])
        agg = self._by_label(label, street)
        if any(agg.values()):
            return self._norm(agg, 'label')
        agg = self._population(street)
        if any(agg.values()):
            return self._norm(agg, 'poblacion')
        return None

    def to_dict(self):
        """Distribuciones por perfil (con textura cuando existe)."""
        out = {}
        for label in sorted(self.labels):
            per_street = {}
            for street in STREETS:
                fs = {}
                for (lbl, st, fac), cell in self.facing.items():
                    if lbl != label or st != street:
                        continue
                    entry = {'actions': {a: cell.get(a, 0.0)
                                         for a in ACTIONS},
                             'sizing': cell.get('sizing_mean')}
                    texts = {}
                    for (lbl2, st2, tex, fac2), cell2 in self.granular.items():
                        if (lbl2, st2, fac2) == (label, street, fac) \
                                and tex != '-':
                            texts[tex] = {a: cell2.get(a, 0.0)
                                          for a in ACTIONS}
                    if texts:
                        entry['texturas'] = texts
                    fs[fac] = entry
                if fs:
                    per_street[street] = fs
            if per_street:
                out[label] = per_street
        return out

    @staticmethod
    def for_dataset(hands, min_n=DEFAULT_MIN_N):
        """Oracle listo desde las manos crudas (carga + build + Oracle)."""
        data = build(hands, min_n=min_n)
        return Oracle(data)


def oracle_from_hands(hands, min_n=DEFAULT_MIN_N):
    """Convenience: Oracle desde las manos (sin persistir tablas)."""
    return Oracle.for_dataset(hands, min_n)


def _key(k):
    """Serializable: tuple -> 'a|b|c'."""
    return '|'.join(str(x) for x in k)


def build(hands, labels: Optional[Dict[str, str]] = None,
          min_n: int = DEFAULT_MIN_N) -> dict:
    """Materializa las behavior tables para un dataset de manos.

    Devuelve {'hands': N, 'observaciones': K, 'profiles': {jugador: etiqueta},
    'granular': {...}, 'por_facing': {...}}.
    """
    labels = labels_from_hands(hands) if labels is None else dict(labels)
    obs = extract_hands(hands)
    return {
        'hands': len(hands),
        'observaciones': len(obs),
        'profiles': labels,
        'granular': behavior_table(obs, labels, min_n, with_texture=True),
        'por_facing': behavior_table(obs, labels, min_n, with_texture=False),
    }


def report(data: dict, min_n: int = DEFAULT_MIN_N) -> str:
    lines = []
    cnt_g = sum(r['n'] for r in data['granular'].values())
    cnt_f = sum(r['n'] for r in data['por_facing'].values())
    lines.append(f"Manos: {data['hands']}  Observaciones: {data['observaciones']}")
    lines.append('Casillas granular: {:<4} (n>={}, obs {})'.format(
        len(data['granular']), min_n, cnt_g))
    lines.append('Casillas por-facing: {:<4} (n>={}, obs {})'.format(
        len(data['por_facing']), min_n, cnt_f))
    order = {s: i for i, s in enumerate(STREETS)}
    if data['por_facing']:
        lines.append('')
        lines.append('== POR FACING (perfil, street, facing) ==')
        last = object()
        for (label, st, facing) in sorted(
                data['por_facing'],
                key=lambda k: (k[0], order.get(k[1], 9), k[2])):
            if label != last:
                lines.append('-- ' + label)
                last = label
            c = data['por_facing'][(label, st, facing)]
            acts = ''.join(f'{a} {c[a] * 100:.0f}%'
                           for a in ('x', 'b', 'c', 'f', 'r') if c[a])
            size = (f'  size {c["sizing_mean"] * 100:.0f}%p'
                    if 'sizing_mean' in c else '')
            lines.append(f'   {st:<7} {facing:<7} n={c["n"]:<3} {acts}{size}')
    if data['granular']:
        lines.append('')
        lines.append('== GRANULAR (perfil, street, textura, facing) ==')
        last = object()
        for (label, st, tex, facing) in sorted(
                data['granular'],
                key=lambda k: (k[0], order.get(k[1], 9), k[2], k[3])):
            if label != last:
                lines.append('-- ' + label)
                last = label
            c = data['granular'][(label, st, tex, facing)]
            acts = ''.join(f'{a} {c[a] * 100:.0f}%'
                           for a in ('x', 'b', 'c', 'f', 'r') if c[a])
            size = (f'  size {c["sizing_mean"] * 100:.0f}%p'
                    if 'sizing_mean' in c else '')
            lines.append(f'   {st:<7} {tex:<14} {facing:<7} '
                         f'n={c["n"]:<3} {acts}{size}')
    if not data['granular'] and not data['por_facing']:
        lines.append('Sin casillas con n >= {} (muestra corta).'.format(min_n))
    return '\n'.join(lines)


def oracle_payload(oracle):
    """Serializable del Oracle: perfil × street × facing (+texturas)."""
    return oracle.to_dict()


def main(argv=None):
    """CLI: python -m motor.behavior [--json] [--min-n N] [--probs] [--out PATH]"""
    import sys
    args = list(argv if argv is not None else sys.argv[1:])
    write_json = '--json' in args
    write_probs = '--probs' in args
    out_path = ''
    min_n = DEFAULT_MIN_N
    if '--min-n' in args:
        try:
            min_n = int(args[args.index('--min-n') + 1])
        except (IndexError, ValueError):
            pass
    if '--out' in args:
        i = args.index('--out')
        out_path = args[i + 1] if len(args) > i + 1 else ''
    hands = load_hands()
    data = build(hands, min_n=min_n)
    print(report(data, min_n))
    if write_json:
        out = {
            'hands': data['hands'],
            'observaciones': data['observaciones'],
            'profiles': data['profiles'],
            'granular': {_key(k): v
                         for k, v in data['granular'].items()},
            'por_facing': {_key(k): v
                           for k, v in data['por_facing'].items()},
        }
        path = out_path or os.path.join(DATA_DIR, 'behavior.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f'\n-> {path}')
    if write_probs:
        oracle = Oracle(data)
        path = out_path or os.path.join(DATA_DIR, 'behavior_probs.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(oracle_payload(oracle), f, indent=2,
                      ensure_ascii=False)
        print(f'-> {path}')


if __name__ == '__main__':
    main()