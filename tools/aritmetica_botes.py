# -*- coding: utf-8 -*-
"""ARITMETICA EXHAUSTIVA DE BOTES + NORMALIZACION.

Para cada mano enumera TODAS las lecturas posibles de los importes:

  * una apuesta/subida `b`/`r` puede ser ABSOLUTA (el importe es el total
    comprometido en la calle) o PARCIAL (el importe se suma a lo que ese
    jugador ya tenia comprometido en la calle).
  * una llamada `c` se resuelve contra la apuesta viva; si el stack no
    alcanza, es un all-in corto.

Cada combinacion produce un bote de dos formas:

  * NETO   : solo fichas igualadas (las no completadas se devuelven)
  * BRUTO  : todas las fichas comprometidas (incluye lo no completado)

Comision (confirmada por el usuario):
  * 5% de las apuestas IGUALADAS
  * tope 2.5bb
  * solo cuentan las calles que se completan a la siguiente calle o a showdown
  * los aportes devueltos no cuentan

Se compara con el `final_pot` declarado con tolerancia +/-0.2bb, dando
prioridad a las coincidencias exactas. Si el grabador viejo omitio la ciega
del SB, se prueba tambien la variante descontando 0.5.

SEMANTICA OBJETIVO (normalizacion, solo manos de lectura unica):
  * todos los `amount` de `b`/`c`/`r` quedan ABSOLUTOS (total de la calle);
    el all-in corto conserva su total real, que es lo que aporta.
  * `final_pot` = bote BRUTO (incluye la ultima apuesta no completada) si la
    mano se gana por fold; NETO si hay showdown. Asi el motor calcula la
    ganancia restando solo las apuestas del ganador.

Las ambiguas por `DEVUELTA` (la diferencia esta en una subida no pagada y el
neto no cambia) se resuelven solas: se elige la lectura absoluta cuyos
importes coinciden con los grabados. `H_0024` queda excluida.

Clasificacion por mano:
  UNICA_EXACTA | UNICA_TOL | ACCION_AMBIGUA | NADA

USO
---
  python tools/aritmetica_botes.py [ruta] [--aplicar] [--doc RUTA]
  python tools/aritmetica_botes.py --aplicar-resueltas
"""
import argparse
import io
import json
import os
import shutil
import sys

STREETS = ('preflop', 'flop', 'turn', 'river')
TOL = 0.2                 # +/- 0.2 bb
EXACTO = 0.005            # a partir de aqui consideramos coincidencia exacta
COMISION_PORC = 0.05
COMISION_TOPE = 2.5
MAX_ESTADOS_CALLE = 40000
MAX_COMBOS = 120000
EPS = 1e-9

# H_0024: el usuario detecto que la accion grabada como `r` era una llamada
# (`BB c 3.4`). No se resuelve por importe: se queda para revision manual.
NO_RESOLVER_DEVUELTA = {'H_0024'}


def _clave(c, folded, res):
    return (tuple(sorted((p, round(v, 4)) for p, v in c.items())),
            frozenset(folded), tuple(res))


def _poner(c, pos, val):
    nc = dict(c)
    nc[pos] = round(val, 4)
    return nc


def _expandir(estado, a, restante):
    """[(nuevo_estado)] para una accion, con el importe resuelto."""
    pos = a.get('pos')
    acc = a.get('action')
    v = float(a.get('amount') or 0.0)
    c = estado['c']
    folded = estado['folded']
    last = estado['last']

    if pos is None:
        return []

    actual = c.get(pos, 0.0)
    disponible = restante.get(pos, 1e18) - actual

    def nuevo(nc, nfolded, nlast, etiq, res):
        return {'c': nc, 'folded': nfolded, 'last': nlast,
                'path': estado['path'] + [etiq],
                'res': estado['res'] + [res]}

    if acc == 'f':
        nf = set(folded)
        nf.add(pos)
        return [nuevo(dict(c), nf, last, '%s f' % pos, None)]

    if acc == 'x':
        return [nuevo(dict(c), set(folded), last, '%s x' % pos, None)]

    if acc == 'p':
        return [nuevo(_poner(c, pos, v), set(folded), last,
                      '%s p %.2f' % (pos, v), round(v, 4))]

    if acc == 'c':
        if pos in folded:
            return []
        live = max(c.values()) if c else 0.0
        falta = live - actual
        if falta <= EPS:
            return [nuevo(dict(c), set(folded), last,
                          '%s c (check)' % pos, None)]
        if disponible + EPS < falta:
            val = actual + max(0.0, disponible)
            return [nuevo(_poner(c, pos, val), set(folded), last,
                          '%s c all-in %.2f' % (pos, val), round(val, 4))]
        return [nuevo(_poner(c, pos, live), set(folded), last,
                      '%s c %.2f' % (pos, live), round(live, 4))]

    if acc in ('b', 'r'):
        if pos in folded:
            return []
        if v <= EPS:
            return [nuevo(dict(c), set(folded), last,
                          '%s %s 0 (no-op)' % (pos, acc), None)]
        candidatos = []
        if actual > EPS:
            candidatos.append(('parcial', round(actual + v, 4)))
        candidatos.append(('absoluta', round(v, 4)))
        out = []
        vistos = set()
        for tipo, val in candidatos:
            if (tipo, val) in vistos:
                continue
            vistos.add((tipo, val))
            if val <= actual + EPS:
                continue
            marca = ''
            if val > disponible + EPS:
                marca = ' [EXCEDE_STACK %.2f]' % (val - disponible)
            etiq = '%s %s %s %.2f%s' % (pos, acc, tipo, val, marca)
            out.append(nuevo(_poner(c, pos, val), set(folded), pos, etiq,
                             round(val, 4)))
        return out

    return []


def _igualado_calle(c, last):
    if not c:
        return 0.0, 0.0
    if last is None or last not in c:
        nivel = max(c.values())
    else:
        otros = [v for p, v in c.items() if p != last]
        nivel = max(otros) if otros else 0.0
    return sum(min(v, nivel) for v in c.values()), nivel


def enumerar_calle(acciones, restante, folded, tope=MAX_ESTADOS_CALLE):
    """[(igualado, bruto, c, folded, path, nivel, res)] o None."""
    estados = [{'c': {}, 'folded': set(folded), 'last': None, 'path': [],
                'res': []}]
    for a in acciones:
        nuevos = {}
        for est in estados:
            for ns in _expandir(est, a, restante):
                k = _clave(ns['c'], ns['folded'], ns['res'])
                if k not in nuevos:
                    nuevos[k] = ns
        estados = list(nuevos.values())
        if not estados or len(estados) > tope:
            return None
    res = []
    for est in estados:
        igualado, nivel = _igualado_calle(est['c'], est['last'])
        res.append((round(igualado, 4), round(sum(est['c'].values()), 4),
                    est['c'], est['folded'], est['path'], nivel, est['res']))
        if len(res) > tope:
            return None
    return res


def enumerar_mano(mano, tope=MAX_COMBOS):
    players = mano.get('players') or []
    stacks = {}
    for p in players:
        if not p.get('pos'):
            continue
        s = p.get('stack')
        stacks[p['pos']] = 1e9 if s is None else float(s)
    actuaron = set()
    calles = []
    for st in STREETS:
        acciones = (((mano.get('streets') or {}).get(st) or {})
                    .get('actions') or [])
        if acciones:
            calles.append(st)
            for a in acciones:
                if a.get('pos'):
                    actuaron.add(a['pos'])

    # combo = (ig_t, br_t, ig_u, restante, folded, ult_c, res_s, path_s)
    combos = [(0.0, 0.0, 0.0, dict(stacks), set(), {}, [], [])]
    for st in calles:
        acciones = (((mano.get('streets') or {}).get(st) or {})
                    .get('actions') or [])
        nuevos = {}
        for (ig_t, br_t, ig_u, rest_s, fold_s, _ult, res_s,
             path_s) in combos:
            res = enumerar_calle(acciones, rest_s, fold_s)
            if res is None:
                return None
            for ig, br, c, fold, path, _nivel, racc in res:
                nr = dict(rest_s)
                for p, val in c.items():
                    nr[p] = round(nr.get(p, 0.0) - val, 4)
                n_ig_t = round(ig_t + ig, 4)
                n_br_t = round(br_t + br, 4)
                n_res_s = res_s + [racc]
                k = (n_ig_t, n_br_t, round(ig, 4),
                     tuple(sorted((p, round(v, 2))
                                  for p, v in nr.items())),
                     frozenset(fold),
                     tuple(sorted((p, round(v, 2))
                                  for p, v in c.items())),
                     tuple(tuple(x) for x in n_res_s))
                if k in nuevos:
                    continue
                nuevos[k] = (n_ig_t, n_br_t, round(ig, 4), nr, set(fold),
                             dict(c), n_res_s,
                             path_s + ['[%s]' % st] + path)
                if len(nuevos) > tope:
                    return None
        combos = list(nuevos.values())

    if not combos:
        return []

    resultados = []
    for (ig_t, br_t, ig_u, rest_s, fold_s, ult_c, res_s, path_s) in combos:
        live = max(ult_c.values()) if ult_c else 0.0
        en_showdown = 0
        for p in actuaron:
            if p in fold_s:
                continue
            aportado_calle = ult_c.get(p, 0.0)
            stack_p = stacks.get(p, 1e9)
            total = round(stack_p - rest_s.get(p, stack_p), 4)
            all_in = stack_p < 1e8 and total >= stack_p - 0.01
            if aportado_calle >= live - 0.01 or all_in:
                en_showdown += 1
        showdown = en_showdown >= 2
        base = ig_t if showdown else round(ig_t - ig_u, 4)
        rake = min(COMISION_PORC * base, COMISION_TOPE) if base > 0 else 0.0
        resultados.append({
            'neto': round(ig_t - rake, 4),
            'bruto': round(br_t - rake, 4),
            'rake': round(rake, 4),
            'igualado': ig_t,
            'bruto_sin_rake': br_t,
            'showdown': showdown,
            'calles': calles,
            'res': res_s,
            'path': path_s,
        })
    return resultados


def _valor_variante(r, campo):
    if campo == 'neto':
        return r['neto']
    if campo == 'bruto':
        return r['bruto']
    if campo == 'neto_sin_sb':
        return round(r['neto'] - 0.5, 4)
    if campo == 'bruto_sin_sb':
        return round(r['bruto'] - 0.5, 4)
    return None


def _muestra(res, campo, valor, pot):
    for r in res:
        v = _valor_variante(r, campo)
        if v is not None and round(v, 2) == valor:
            return {'campo': campo, 'neto': r['neto'], 'bruto': r['bruto'],
                    'valor': v, 'rake': r['rake'],
                    'diff': round(v - pot, 4), 'path': r['path']}
    return None


def violaciones_stack(mano):
    """Jugadores cuyo total comprometido supera su stack (lectura absoluta).

    Si el registro ya supera el stack, el importe no es fiable y no se debe
    normalizar: inflar el bote por una apuesta imposible lo dispara.
    """
    stacks = {}
    for p in (mano.get('players') or []):
        if not p.get('pos'):
            continue
        s = p.get('stack')
        if s is not None:
            stacks[p['pos']] = float(s)
    por = {}
    for st in STREETS:
        ult = {}
        for a in (((mano.get('streets') or {}).get(st) or {})
                  .get('actions') or []):
            if a.get('action') in ('p', 'b', 'c', 'r'):
                ult[a['pos']] = float(a.get('amount') or 0.0)
        for p, v in ult.items():
            por[p] = round(por.get(p, 0.0) + v, 4)
    out = []
    for p, total in por.items():
        s = stacks.get(p)
        if s is not None and total > s + 0.05:
            out.append({'pos': p, 'total': round(total, 2), 'stack': s,
                        'exceso': round(total - s, 2)})
    return out


def _trazas_unicas(match):
    out = []
    vistos = set()
    for r in match:
        k = tuple(tuple(x) for x in r['res'])
        if k not in vistos:
            vistos.add(k)
            out.append(r)
    return out


def _diagnostico(mano, trazas, campo):
    """Por que hay varias trazas que producen el mismo bote.

    DEVUELTA   : la diferencia esta en una subida no pagada; el neto no cambia
    REPARTO    : neto y bruto iguales; cambia quien aporto cada ficha
    NETO_IGUAL : neto igual, pero cambian importes igualados (y el bruto)
    REAL       : el neto cambia; aqui si hay que decidir
    """
    flats = []
    for r in trazas:
        f = {}
        for st, amounts in zip(r['calles'], r['res']):
            acts = (((mano.get('streets') or {}).get(st) or {})
                    .get('actions') or [])
            for i, amt in enumerate(amounts):
                if i < len(acts):
                    f[(st, i)] = amt
        flats.append(f)
    claves = set().union(*[set(f) for f in flats])
    diferencias = []
    for k in sorted(claves, key=lambda x: (STREETS.index(x[0]), x[1])):
        vals = [f.get(k) for f in flats]
        norm = {None if v is None else round(v, 2) for v in vals}
        if len(norm) > 1:
            st, i = k
            a = (((mano.get('streets') or {}).get(st) or {})
                 .get('actions') or [])[i]
            diferencias.append({
                'street': st,
                'i': i,
                'pos': a.get('pos'),
                'action': a.get('action'),
                'valores': [None if v is None else round(v, 2)
                            for v in vals],
            })
    netos = {round(r['neto'], 2) for r in trazas}
    brutos = {round(r['bruto'], 2) for r in trazas}
    if len(netos) > 1:
        causa = 'REAL'
    elif len(brutos) == 1:
        causa = 'REPARTO'
    elif diferencias and all(d['action'] in ('b', 'r')
                             for d in diferencias):
        causa = 'DEVUELTA'
    else:
        causa = 'NETO_IGUAL'
    if campo and campo.endswith('_sin_sb'):
        causa += '+SB'
    return causa, diferencias[:10]


def _elegir_absoluta(mano, trazas, diferencias):
    """Traza en la que cada accion dudosa vale lo grabado (lectura absoluta)."""
    por_calle = {}
    for st in STREETS:
        por_calle[st] = (((mano.get('streets') or {}).get(st) or {})
                         .get('actions') or [])
    elegidos = []
    for r in trazas:
        plano = {}
        for st, amounts in zip(r['calles'], r['res']):
            for i, amt in enumerate(amounts):
                plano[(st, i)] = amt
        ok = True
        for d in diferencias:
            acts = por_calle.get(d['street']) or []
            if d['i'] >= len(acts):
                ok = False
                break
            raw = float(acts[d['i']].get('amount') or 0.0)
            val = plano.get((d['street'], d['i']))
            if val is None or abs(float(val) - raw) > 1e-9:
                ok = False
                break
        if ok:
            elegidos.append(r)
    return elegidos[0] if len(elegidos) == 1 else None


def clasificar(mano, resolver_devuelta=False):
    pot = round(float(mano.get('final_pot') or 0.0), 4)
    viol = violaciones_stack(mano)
    res = enumerar_mano(mano)
    if res is None:
        return {'hand_id': mano.get('hand_id'),
                'date': (mano.get('date') or '')[:10],
                'clase': 'EXPLOTA', 'pot': pot}

    tiene_ciega_sb = any(
        a.get('pos') == 'SB' and a.get('action') == 'p'
        for st in STREETS
        for a in (((mano.get('streets') or {}).get(st) or {})
                  .get('actions') or []))

    def valores(campo):
        if campo == 'neto':
            return {round(r['neto'], 2) for r in res}
        if campo == 'bruto':
            return {round(r['bruto'], 2) for r in res}
        if campo == 'neto_sin_sb' and tiene_ciega_sb:
            return {round(r['neto'] - 0.5, 2) for r in res}
        if campo == 'bruto_sin_sb' and tiene_ciega_sb:
            return {round(r['bruto'] - 0.5, 2) for r in res}
        return set()

    clase, campo, usados = 'NADA', None, []
    for c in ('neto', 'bruto', 'neto_sin_sb', 'bruto_sin_sb'):
        vals = valores(c)
        e = sorted(v for v in vals if abs(v - pot) <= EXACTO)
        if e:
            clase = 'UNICA_EXACTA' if len(e) == 1 else 'MULTI_EXACTA'
            campo, usados = c, e
            break
        t = sorted(v for v in vals if abs(v - pot) <= TOL)
        if t:
            clase = 'UNICA_TOL' if len(t) == 1 else 'MULTI_TOL'
            campo, usados = c, t
            break

    netos = sorted({round(r['neto'], 2) for r in res})
    brutos = sorted({round(r['bruto'], 2) for r in res})
    detalles = [_muestra(res, campo, v, pot) for v in usados] if campo else []

    # lecturas que producen el bote elegido
    match = []
    if campo:
        for r in res:
            if round(_valor_variante(r, campo), 2) in usados:
                match.append(r)
    firmas = {tuple(tuple(x) for x in r['res']) for r in match}
    n_trazas = len(firmas)

    causa = None
    diferencias = []
    if n_trazas > 1:
        causa, diferencias = _diagnostico(
            mano, _trazas_unicas(match), campo)

    r_ok = None
    resuelta_por = None
    if n_trazas == 1 and match and not viol:
        r_ok = match[0]
    elif (resolver_devuelta and not viol
          and causa and causa.startswith('DEVUELTA')
          and mano.get('hand_id') not in NO_RESOLVER_DEVUELTA):
        r_ok = _elegir_absoluta(mano, _trazas_unicas(match), diferencias)
        if r_ok is not None:
            resuelta_por = 'DEVUELTA'
            difs = [abs(c['diff']) for c in detalles if c]
            clase = ('UNICA_EXACTA'
                     if difs and min(difs) <= EXACTO else 'UNICA_TOL')

    resuelto = None
    if r_ok is not None:
        objetivo = r_ok['bruto'] if not r_ok['showdown'] else r_ok['neto']
        resuelto = {
            'showdown': r_ok['showdown'],
            'pot_objetivo': round(objetivo, 4),
            'por_calle': [
                {'street': st, 'amounts': [None if x is None else round(x, 4)
                                           for x in amounts]}
                for st, amounts in zip(r_ok['calles'], r_ok['res'])
            ],
        }

    if (clase in ('UNICA_EXACTA', 'UNICA_TOL') and n_trazas > 1
            and not resuelta_por):
        clase = 'ACCION_AMBIGUA'

    traza = match[0]['path'] if len(match) == 1 else None
    alternativas = []
    vistos = set()
    for r in match:
        k = tuple(tuple(x) for x in r['res'])
        if k not in vistos:
            vistos.add(k)
            alternativas.append(r['path'])
    alt_vals = []
    for r in match:
        v = _valor_variante(r, campo)
        if v not in alt_vals:
            alt_vals.append(v)

    return {
        'hand_id': mano.get('hand_id'),
        'date': (mano.get('date') or '')[:10],
        'clase': clase,
        'campo': campo,
        'pot': pot,
        'n_combinaciones': len(res),
        'netos_distintos': len(netos),
        'netos': netos[:12],
        'brutos': brutos[:12],
        'n_trazas': n_trazas,
        'coincidencias': detalles,
        'traza': traza,
        'alternativas': alternativas[:4],
        'stack_violations': viol,
        'causa': causa,
        'diferencias': diferencias,
        'resuelta_por': resuelta_por,
        'resuelto': resuelto,
    }


# --------------------------------------------------------------------------
# Normalizacion de la copia de trabajo
# --------------------------------------------------------------------------
def aplicar_normalizacion(manos, detalle, ruta, solo_resueltas=False):
    bak = ruta + ('.bak_antes_resolver_devuelta' if solo_resueltas
                  else '.bak_antes_normalizar')
    shutil.copy2(ruta, bak)
    cambios_acc = 0
    cambios_pot = 0
    manos_n = 0
    for h, d in zip(manos, detalle):
        if solo_resueltas and d.get('resuelta_por') != 'DEVUELTA':
            continue
        r = d.get('resuelto')
        if not r:
            continue
        manos_n += 1
        for calle in r['por_calle']:
            st = calle['street']
            acs = ((h.get('streets') or {}).get(st) or {}).get(
                'actions') or []
            for a, rv in zip(acs, calle['amounts']):
                if rv is None:
                    continue
                if a.get('action') not in ('b', 'c', 'r'):
                    continue
                if abs(float(a.get('amount') or 0.0) - rv) > 1e-9:
                    a['amount'] = rv
                    cambios_acc += 1
        if abs(float(h.get('final_pot') or 0.0) - r['pot_objetivo']) > 1e-9:
            h['final_pot'] = r['pot_objetivo']
            cambios_pot += 1
    with io.open(ruta, 'w', encoding='utf-8', newline='\n') as f:
        for h in manos:
            f.write(json.dumps(h, ensure_ascii=False) + '\n')
    return {'respaldo': bak, 'manos': manos_n, 'acciones': cambios_acc,
            'pots': cambios_pot}


# --------------------------------------------------------------------------
# Documento de revision manual
# --------------------------------------------------------------------------
def escribir_documento(manos, detalle, ruta):
    por_id = {h.get('hand_id'): h for h in manos}
    stack = [d for d in detalle if d.get('stack_violations')]
    nada = [d for d in detalle
            if d['clase'] == 'NADA' and not d.get('stack_violations')]
    amb = [d for d in detalle
           if d['clase'] == 'ACCION_AMBIGUA' and not d.get('stack_violations')]
    amb_dev = [d for d in amb
               if (d.get('causa') or '').startswith('DEVUELTA')]
    amb_rep = [d for d in amb
               if (d.get('causa') or '').startswith('REPARTO')]
    amb_net = [d for d in amb
               if (d.get('causa') or '').startswith('NETO_IGUAL')]
    amb_real = [d for d in amb
                if (d.get('causa') or '').startswith('REAL')]
    lineas = []
    lineas.append('# Botes no encontrados - revision manual')
    lineas.append('')
    lineas.append('Generado por `tools/aritmetica_botes.py`.')
    lineas.append('')
    lineas.append('| motivo | manos |')
    lineas.append('|---|---:|')
    lineas.append('| `STACK` (alguna accion supera el stack: no se normaliza) '
                  '| %d |' % len(stack))
    lineas.append('| `NADA` (el bote no coincide con ninguna lectura) | %d |'
                  % len(nada))
    lineas.append('| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | %d |'
                  % len(amb))
    lineas.append('')
    lineas.append('En las `STACK` el registro ya es imposible (un jugador '
                  'compromete mas que su stack), asi que normalizarlo '
                  'dispararia el bote: se dejan intactas. En las `NADA` el '
                  'bote declarado no sale con ninguna combinacion de apuestas '
                  'parciales/absolutas, con ni sin comision, ni con ni sin la '
                  'ciega del SB.')
    lineas.append('')
    lineas.append('De las `ACCION_AMBIGUA`: `REPARTO` %d (mismo neto y bruto; '
                  'cambia quien aporta), `NETO_IGUAL` %d (mismo neto; cambian '
                  'importes igualados), `REAL` %d (el neto cambia; hay que '
                  'decidir). Solo `REAL` afecta a la ganancia. Las `DEVUELTA` '
                  '(subida no pagada; el neto no cambia) se resuelven solas '
                  'eligiendo la lectura absoluta%s.'
                  % (len(amb_rep), len(amb_net), len(amb_real),
                     ('' if not amb_dev else
                      '; quedan %d sin resolver' % len(amb_dev))))
    lineas.append('')

    def acciones(h):
        out = []
        for st in STREETS:
            acs = ((h.get('streets') or {}).get(st) or {}).get(
                'actions') or []
            if not acs:
                continue
            out.append('- **%s**: %s' % (st, ' | '.join(
                '%s %s %s' % (a.get('pos'), a.get('action'),
                              a.get('amount'))
                for a in acs)))
        return out

    def ficha(d):
        h = por_id.get(d['hand_id'], {})
        lineas.append('### %s - %s' % (d['hand_id'], d['date']))
        lineas.append('')
        lineas.append('- **Pot declarado**: %s' % d['pot'])
        lineas.append('- **Combinaciones**: %s' % d.get(
            'n_combinaciones'))
        lineas.append('- **Netos posibles**: %s' % d.get('netos'))
        lineas.append('- **Brutos posibles**: %s' % d.get('brutos'))
        if d.get('coincidencias'):
            c = d['coincidencias'][0]
            lineas.append('- **Coincidencia**: %s = %s (dif %s)' % (
                c.get('campo'), c.get('valor'), c.get('diff')))
        if d.get('causa'):
            lineas.append('- **Causa**: `%s`' % d['causa'])
        if d.get('diferencias'):
            lineas.append('- **Diferencia**: %s' % '; '.join(
                '%s %s %s %s' % (x['street'], x['pos'], x['action'],
                                 x['valores'])
                for x in d['diferencias']))
        if d['clase'] == 'NADA' and d.get('netos'):
            cerca = min(d['netos'], key=lambda v: abs(v - d['pot']))
            lineas.append('- **Neto mas cercano**: %s (dif %s)' % (
                cerca, round(cerca - d['pot'], 2)))
        lineas.append('- **Stacks**: %s' % ', '.join(
            '%s=%s' % (p.get('pos'), p.get('stack'))
            for p in (h.get('players') or []) if p.get('pos')))
        if d.get('stack_violations'):
            lineas.append('- **Supera stack**: %s' % ', '.join(
                '%s total=%s stack=%s exceso=%+.2f'
                % (v['pos'], v['total'], v['stack'], v['exceso'])
                for v in d['stack_violations']))
            if any(v['exceso'] <= TOL + 1e-9
                   for v in d['stack_violations']):
                lineas.append('- **Nota**: el exceso <= %s esta dentro de la '
                              'tolerancia del bote; puede ser redondeo, no un '
                              'error de stack.' % TOL)
        lineas.append('- **Acciones**:')
        lineas.extend(acciones(h))
        if d.get('alternativas'):
            lineas.append('- **Lecturas alternativas** (%d):'
                          % len(d['alternativas']))
            for i, alt in enumerate(d['alternativas'], 1):
                lineas.append('  %d. %s' % (i, ' | '.join(
                    x for x in alt if '[' not in x)))
        lineas.append('')

    for titulo, grupo in (('STACK', stack), ('NADA', nada)):
        if not grupo:
            continue
        lineas.append('## %s (%d)' % (titulo, len(grupo)))
        lineas.append('')
        for d in grupo:
            ficha(d)

    if amb:
        lineas.append('## ACCION_AMBIGUA (%d)' % len(amb))
        lineas.append('')
        lineas.append('La `causa` describe por que hay mas de una traza. '
                      '`DEVUELTA` no es un error de bote: la subida no se '
                      'paga y las fichas extra se devuelven; el neto es el '
                      'mismo. `REPARTO` y `NETO_IGUAL` tampoco cambian el '
                      'bote neto, pero dejan el `amount` de alguna accion sin '
                      'determinar. `REAL` es el unico caso en que el bote '
                      'neto depende de la lectura. El sufijo `+SB` indica que '
                      'la coincidencia usa la variante que descuenta la '
                      'ciega del SB.')
        lineas.append('')
        for subtitulo, grupo in (
                ('DEVUELTA (subida no pagada; el neto no cambia)', amb_dev),
                ('REPARTO (mismo bote; cambia quien aporta)', amb_rep),
                ('NETO_IGUAL (mismo neto; cambian importes igualados)',
                 amb_net),
                ('REAL (el bote neto cambia)', amb_real)):
            if not grupo:
                continue
            lineas.append('### %s - %d' % (subtitulo, len(grupo)))
            lineas.append('')
            for d in grupo:
                ficha(d)
    with io.open(ruta, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lineas))
    return {'nada': len(nada), 'ambiguas': len(amb), 'stack': len(stack),
            'ruta': ruta}


def cargar(ruta):
    with io.open(ruta, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ruta', nargs='?', default=os.path.join(
        os.getcwd(), 'trabajo', 'hands_db_edicion.jsonl'))
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--salida', default=os.path.join(
        os.getcwd(), 'trabajo', 'botes_aritmetica.jsonl'))
    ap.add_argument('--aplicar', action='store_true')
    ap.add_argument('--no-resolver-devuelta', dest='resolver_devuelta',
                    action='store_false',
                    help='no resolver las ambiguas DEVUELTA (para inspeccion)')
    ap.add_argument('--aplicar-resueltas', action='store_true')
    ap.add_argument('--doc', default=os.path.join(
        os.getcwd(), 'trabajo', 'BOTES_NO_ENCONTRADOS.md'))
    args = ap.parse_args()
    if args.aplicar and args.aplicar_resueltas:
        ap.error('usa --aplicar o --aplicar-resueltas, no ambos')
    resolver = args.resolver_devuelta
    manos = cargar(args.ruta)
    if args.limite:
        manos = manos[:args.limite]
    cuentas = {}
    detalle = []
    for i, h in enumerate(manos, 1):
        c = clasificar(h, resolver_devuelta=resolver)
        cuentas[c['clase']] = cuentas.get(c['clase'], 0) + 1
        detalle.append(c)
        if i % 100 == 0:
            print('  ... %d/%d' % (i, len(manos)), file=sys.stderr)
    with io.open(args.salida, 'w', encoding='utf-8', newline='\n') as f:
        for d in detalle:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')
    print('=' * 70)
    print('CLASIFICACION DE BOTES (%d manos)' % len(manos))
    print('=' * 70)
    for k in ('UNICA_EXACTA', 'UNICA_TOL', 'ACCION_AMBIGUA', 'MULTI_EXACTA',
              'MULTI_TOL', 'NADA', 'EXPLOTA'):
        if k in cuentas:
            print('  %-14s %4d' % (k, cuentas[k]))
    resueltas = sum(1 for d in detalle if d.get('resuelta_por'))
    if resueltas:
        print('  %-14s %4d' % ('DEVUELTA->UNICA', resueltas))
    if args.aplicar_resueltas:
        r = aplicar_normalizacion(manos, detalle, args.ruta,
                                   solo_resueltas=True)
        print()
        print('RESUELTAS DEVUELTA aplicadas a %d manos' % r['manos'])
        print('  acciones corregidas: %d' % r['acciones'])
        print('  pots corregidos    : %d' % r['pots'])
        print('  respaldo           : %s' % r['respaldo'])
    if args.aplicar:
        r = aplicar_normalizacion(manos, detalle, args.ruta)
        print()
        print('NORMALIZACION aplicada a %d manos' % r['manos'])
        print('  acciones corregidas: %d' % r['acciones'])
        print('  pots corregidos    : %d' % r['pots'])
        print('  respaldo           : %s' % r['respaldo'])
    if args.doc:
        r = escribir_documento(manos, detalle, args.doc)
        print()
        print('DOCUMENTO: %s' % r['ruta'])
        print('  STACK: %d   NADA: %d   ACCION_AMBIGUA: %d'
              % (r['stack'], r['nada'], r['ambiguas']))
    print()
    print('  detalle: %s' % args.salida)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()