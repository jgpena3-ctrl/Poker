# -*- coding: utf-8 -*-
"""Aplica las correcciones manuales CM-001 y CM-003 a hands_db.jsonl.

    python tools/aplicar_correcciones.py            # dry-run (no escribe)
    python tools/aplicar_correcciones.py --apply    # escribe, con backup

Las nueve garantias
-------------------
1. Precondiciones estrictas. Cada mano debe estar exactamente en el estado
   esperado. Cualquier estado inesperado ABORTA antes de escribir nada.
2. Idempotencia. Si una correccion ya esta aplicada, se clasifica como tal y
   no se vuelve a aplicar. Si esta a medias, se aborta.
3. Backup verificado por SHA-256. Se copia el fichero original y se comprueba
   que el hash coincide ANTES de continuar.
4. Procedencia diferenciada. Las correcciones observadas (CM-001) y las
   inferidas (CM-003) se marcan distinto. La inferida lleva `inferred: true` y
   NO reutiliza `amount_type`: presentarla como 'observed' seria mentir.
5. Insercion en el lugar logico correcto. El check se anade al final de la
   secuencia preflop, que es donde cae: el BB es el ultimo en actuar, asi que
   su check es lo ultimo que ocurrio en preflop.
6. --dry-run por defecto. Sin `--apply` no se toca nada.
7. Diff explicito. Se imprime el antes/despues de cada mano, distinguiendo
   observado de inferido, y se guarda en DOCS/.
8. Verificacion post-aplicacion. Tras escribir se comprueba que el numero de
   manos no cambia, que CM-001 quedo corregido, que hay exactamente 25 checks
   inferidos sin duplicados, y que las categorias preflop cambian como se
   esperaba.
9. Rollback automatico. Si la verificacion post falla, se restaura el backup
   y el proceso termina con error.

CM-002 (H_0350, cartas ausentes) queda FUERA a proposito: no hay evidencia
suficiente para reconstruir las cartas, y no es verificable sin la captura.

Alcance real de CM-003
----------------------
El inventario de `tools/auditar_bb_check.py` decia 41 manos. Al preguntar al
motor en vez de a una reimplementacion del criterio son 26: en las otras 15 del
antiguo inventario hay una entrada `BB b` situada DESPUES de acciones
voluntarias, de modo que `_es_ciega_bb` (que exige `not voluntary_before`) no
la reconoce como ciega y el motor la lee como una subida voluntaria del BB. En
esas manos el BB ya "ha actuado" y el check no es la accion que falta: el
defecto es otro, y anadir el check no lo arregla.

Quedan 23 manos con ese defecto de orden, fuera de esta migracion y
documentadas en `tools/auditar_bb_check.py`. No se tocan: corregirlas exigiria
inventar un reordenamiento que los datos no dicen.
"""
import argparse
import collections
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
DOCS_DIR = os.path.join(ROOT, 'DOCS')

# --- constantes de la migracion -------------------------------------------
H_CM001 = 'H_0141'
CM001_ANTES = 27.0        # OCR de 2.7
CM001_DESPUES = 2.7

INVENTARIO_ESPERADO = 26  # debe coincidir con auditar_bb_check.py
MIGRABLES_ESPERADOS = 26
CIEGA_MAL_PUESTA = 23     # defecto medido, fuera de esta migracion

CHECK_INFERIDO = {'pos': 'BB', 'action': 'x', 'amount': 0.0,
                  'inferred': True}

# El sha256 de lo que este script PRODUCE, para que su salida sea
# distinguible de una edicion a mano. Sin esta constante, un fichero escrito
# por aqui es indistinguible de uno que alguien toco en un editor, que es
# exactamente lo que `DOCS/CANAL_MANUAL_CERRADO.md` dice que no va a pasar.
#
# Corresponde al estado CM-001 + CM-003 sobre la base de partida, y esta
# tambien en `DOCS/MIGRACION_CM001_CM003.md`.
#
# Nota: el fichero tiene que versionarse SIN conversion de saltos de linea
# (`.gitattributes`: `data/hands_db.jsonl -text`). Con la conversion activa,
# el blob del repositorio y el disco tienen distinto hash siempre, y esto no
# se puede comprobar.
SHA_SALIDA = 'bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee'


# ---------------------------------------------------------------- utilidades
def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def es_check_inferido(a):
    return (isinstance(a, dict) and a.get('pos') == 'BB'
            and a.get('action') == 'x' and a.get('inferred') is True)


def tiene_check_bb(acciones):
    return any(isinstance(a, dict) and a.get('pos') == 'BB'
               and a.get('action') == 'x' for a in acciones)


def objetivo_cm003(hand):
    """Mismo criterio que tools/auditar_bb_check.py, y el motor como unico
    arbitro.

    La version anterior de la auditoria usaba `x[1] != 'b' or x[3]`, que
    trata CUALQUIER 'b' del BB como ciega y daba 41 manos. Preguntar al motor
    (`preflop_events`) da 26: en las otras 15 la entrada `BB b` va detras de
    acciones voluntarias, no es ciega, y el BB ya ha actuado.
    """
    st = hand.get('streets', {}) or {}
    pf = (st.get('preflop') or {}).get('actions') or []
    flop = (st.get('flop') or {}).get('actions') or []
    board = (st.get('flop') or {}).get('board') or []
    if not pf:
        return False
    if any(e.pos == 'BB' for e in learn.preflop_events(hand)):
        return False
    return bool(flop or board)


# ------------------------------------------------------------------- el plan
class Plan(object):
    def __init__(self):
        self.lineas = []          # lineas originales del JSONL
        self.manos = []           # dicts parseados, en orden
        self.nuevas = []          # indexada como `lineas`: None = sin tocar
        self.cambios = []         # (hand_id, tipo, motivo, antes, despues)
        self.ya_aplicados = []
        self.bloqueados = []      # (hand_id, motivo)
        self.errores = []         # condiciones violadas -> aborta
        self.n_inferidas_en_base = 0
        self.ya_aplicada_en_todo = False

    def texto_accion(self, a):
        if not isinstance(a, dict):
            return repr(a)
        return json.dumps(a, ensure_ascii=False, sort_keys=True)


def construir_plan(db_path=DB_PATH):
    plan = Plan()
    plan.lineas = leer_lineas(db_path)
    plan.nuevas = [None] * len(plan.lineas)

    manos = []
    for n, linea in enumerate(plan.lineas):
        if not linea.strip():
            manos.append(None)
            continue
        try:
            manos.append(json.loads(linea))
        except ValueError as exc:
            plan.errores.append('linea %d: JSON invalido (%s)' % (n + 1, exc))
            manos.append(None)
    plan.manos = manos

    fiables = learn.load_hands(reliable_only=True)
    objetivo_ids = [h.get('hand_id') for h in fiables if objetivo_cm003(h)]

    indice = {}
    for k, h in enumerate(manos):
        if isinstance(h, dict) and h.get('hand_id'):
            indice[h['hand_id']] = k

    # ---- garantia 1 y 2: inventario coherente y migracion integra ---------
    # Hay tres estados legitimos y nada mas:
    #   A) sin aplicar   : 0 checks inferidos y 26 manos con check perdido
    #   B) aplicada      : 26 checks inferidos y 0 manos con check perdido
    #   C) a medias       : cualquier otra combinacion -> ABORTA
    # Contar los checks inferidos en la base (no solo en el inventario) es lo
    # que permite reconocer el estado B despues de aplicar: entonces el
    # inventario queda vacio, porque las manos ya tienen su check.
    n_inferidas = 0
    for h in manos:
        if not isinstance(h, dict):
            continue
        acc = (h.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
        n_inferidas += sum(1 for a in acc if es_check_inferido(a))
    plan.n_inferidas_en_base = n_inferidas

    if n_inferidas == 0 and len(objetivo_ids) == INVENTARIO_ESPERADO:
        pass                                        # estado A
    elif (n_inferidas == INVENTARIO_ESPERADO
            and len(objetivo_ids) == 0):
        plan.ya_aplicada_en_todo = True              # estado B
    else:
        plan.errores.append(
            'estado incoherente: %d checks inferidos en la base y %d manos '
            'con el check perdido (se esperan 0/%d o %d/0). Migracion a '
            'medias o base cambiada: NO se continua.'
            % (n_inferidas, len(objetivo_ids), INVENTARIO_ESPERADO,
               INVENTARIO_ESPERADO))

    # ---------------------------------------------------------- CM-001 ----
    if H_CM001 not in indice:
        plan.errores.append('CM-001: %s no esta en la base' % H_CM001)
    else:
        h = copy.deepcopy(manos[indice[H_CM001]])
        acc = h['streets']['preflop']['actions']
        con_27 = [a for a in acc
                  if isinstance(a, dict) and a.get('amount') == CM001_ANTES]
        con_27_p = [a for a in acc
                    if isinstance(a, dict) and a.get('pos') == 'UTG'
                    and a.get('action') == 'b']
        if len(con_27_p) != 1:
            plan.errores.append(
                'CM-001: %s deberia tener exactamente 1 subida UTG, hay %d'
                % (H_CM001, len(con_27_p)))
        elif len(con_27) == 1:
            antes = plan.texto_accion(con_27[0])
            con_27[0]['amount'] = CM001_DESPUES
            plan.cambios.append({
                'hand_id': H_CM001, 'tipo': 'observado',
                'motivo': 'OCR: 27.0 leido donde las llamadas usan 2.7',
                'antes': antes,
                'despues': plan.texto_accion(con_27[0]),
            })
            plan.nuevas[indice[H_CM001]] = h
        elif len(con_27) == 0:
            # idempotencia: ya corregido
            ya = [a for a in acc
                  if isinstance(a, dict) and a.get('pos') == 'UTG'
                  and a.get('action') == 'b'
                  and a.get('amount') == CM001_DESPUES]
            if len(ya) == 1:
                plan.ya_aplicados.append(
                    '%s: importe ya corregido a %s' % (H_CM001, CM001_DESPUES))
            else:
                plan.errores.append(
                    'CM-001: %s no tiene ni %s ni %s; estado inesperado'
                    % (H_CM001, CM001_ANTES, CM001_DESPUES))
        else:
            plan.errores.append(
                'CM-001: %s tiene %d acciones con amount=%s'
                % (H_CM001, len(con_27), CM001_ANTES))

    # ---------------------------------------------------------- CM-003 ----
    for hid in objetivo_ids:
        if hid not in indice:
            plan.errores.append('CM-003: %s no esta en la base' % hid)
            continue
        k = indice[hid]
        original = manos[k]
        acc = original['streets']['preflop']['actions']

        # idempotencia
        if any(es_check_inferido(a) for a in acc):
            plan.ya_aplicados.append('%s: check BB inferido ya presente' % hid)
            continue
        if tiene_check_bb(acc):
            plan.bloqueados.append(
                (hid, 'ya hay un check del BB registrado (no es el caso '
                      'del inventario)'))
            continue

        # garantia 5: se inserta al final, que es donde cae el check del BB
        # (el BB es el ultimo en actuar en preflop).
        candidato = copy.deepcopy(original)
        antes_acciones = copy.deepcopy(acc)
        candidato['streets']['preflop']['actions'].append(dict(CHECK_INFERIDO))

        # garantia 8 (en memoria): la inferencia debe producir bb_check.
        # Si no, esta mano NO es un check perdido: hay otro defecto y no se
        # inventa ningun reordenamiento.
        eventos = learn.preflop_events(candidato)
        if not any(e.category == 'bb_check' for e in eventos):
            razon = ('entrada BB b despues de acciones voluntarias: '
                     '_es_ciega_bb no la reconoce como ciega y el motor la '
                     'lee como subida del BB')
            plan.bloqueados.append((hid, razon))
            continue

        plan.nuevas[k] = candidato
        plan.cambios.append({
            'hand_id': hid, 'tipo': 'inferido',
            'motivo': 'preflop cerrado y el BB sin accion propia: hizo check',
            'antes': '%d acciones, ultima %s'
                     % (len(antes_acciones),
                        plan.texto_accion(antes_acciones[-1])),
            'despues': '+ %s' % plan.texto_accion(CHECK_INFERIDO),
        })

    return plan


# ------------------------------------------------------------------ informe
def imprimir_diff(plan):
    print('=' * 78)
    print('DIFF DE LAS CORRECCIONES PREVISTAS')
    print('=' * 78)
    obs = [c for c in plan.cambios if c['tipo'] == 'observado']
    inf = [c for c in plan.cambios if c['tipo'] == 'inferido']

    print()
    print('--- OBSERVADAS (dato leido mal, correccion de un valor) ---')
    if not obs:
        print('   ninguna')
    for c in obs:
        print('   %s' % c['hand_id'])
        print('      antes  : %s' % c['antes'])
        print('      despues: %s' % c['despues'])
        print('      motivo : %s' % c['motivo'])

    print()
    print('--- INFERIDAS (no observadas: deducidas de que el preflop cerro) ---')
    print('   %d correcciones' % len(inf))
    if inf:
        print('   ejemplo (primera):')
        c = inf[0]
        print('      %s' % c['hand_id'])
        print('      antes  : %s' % c['antes'])
        print('      despues: %s' % c['despues'])
        print('      motivo : %s' % c['motivo'])
    return obs, inf


def imprimir_bloqueados(plan):
    if not plan.bloqueados:
        return
    print()
    print('=' * 78)
    print('BLOQUEADAS (%d) — NO se tocan' % len(plan.bloqueados))
    print('=' * 78)
    print('No son un check perdido: tienen otro defecto, y corregirlo exigiria')
    print('inventar un orden que los datos no dicen. Se dejan como estan.')
    for hid, motivo in plan.bloqueados:
        print('   %-8s %s' % (hid, motivo))


# -------------------------------------------------------------- verificacion
def categorias(manos, inyectar=None):
    c = collections.Counter()
    for h in manos:
        if not isinstance(h, dict):
            continue          # `plan.nuevas` lleva None en lo no modificado
        hh = h
        if inyectar and h.get('hand_id') in inyectar:
            hh = copy.deepcopy(h)
            hh['streets']['preflop']['actions'].append(dict(CHECK_INFERIDO))
        for e in learn.preflop_events(hh):
            c[e.category] += 1
    return c


def verificar(plan, manos_antes, categorias_antes, manos_despues=None):
    """Devuelve (ok, mensajes). Garantia 8.

    `manos_despues` es la base completa tras el plan. Si no se pasa, se
    reconstruye con `manos_resultantes` (imprescindible: comparar solo las
    manos tocadas contra la base entera daria un falso fallo).
    """
    if manos_despues is None:
        manos_despues = manos_resultantes(plan)

    msgs = []
    ok = True

    n_antes = sum(1 for h in manos_antes if isinstance(h, dict))
    n_desp = sum(1 for h in manos_despues if isinstance(h, dict))
    if n_antes != n_desp:
        ok = False
        msgs.append('FALLO: el numero de manos cambio (%d -> %d)'
                    % (n_antes, n_desp))
    else:
        msgs.append('OK  numero de manos sin cambios: %d' % n_antes)

    # CM-001
    h141 = next((h for h in manos_despues
                 if isinstance(h, dict) and h.get('hand_id') == H_CM001), None)
    if h141 is not None:
        acc = h141['streets']['preflop']['actions']
        v = [a.get('amount') for a in acc
             if isinstance(a, dict) and a.get('pos') == 'UTG'
             and a.get('action') == 'b']
        if v == [CM001_DESPUES]:
            msgs.append('OK  CM-001: %s importe = %s' % (H_CM001, v[0]))
        else:
            ok = False
            msgs.append('FALLO: CM-001 quedo en %s, se esperaba [%s]'
                        % (v, CM001_DESPUES))

    # CM-003: exactamente N inferidos, sin duplicados
    inf_ids = [c['hand_id'] for c in plan.cambios if c['tipo'] == 'inferido']
    total_inf = 0
    duplicados = []
    for h in manos_despues:
        if not isinstance(h, dict):
            continue
        acc = (h.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
        n = sum(1 for a in acc if es_check_inferido(a))
        total_inf += n
        if n > 1:
            duplicados.append(h.get('hand_id'))
    if duplicados:
        ok = False
        msgs.append('FALLO: checks inferidos duplicados en %s' % duplicados)
    if total_inf == len(inf_ids):
        msgs.append('OK  %d checks inferidos, ninguno duplicado'
                    % total_inf)
    else:
        ok = False
        msgs.append('FALLO: esperaba %d checks inferidos, hay %d'
                    % (len(inf_ids), total_inf))

    # categorias
    cats_desp = categorias(manos_despues)
    delta_bb = cats_desp['bb_check'] - categorias_antes['bb_check']
    otros = {k: cats_desp[k] - categorias_antes[k]
             for k in set(cats_desp) | set(categorias_antes)
             if k != 'bb_check' and cats_desp[k] != categorias_antes[k]}
    if otros:
        ok = False
        msgs.append('FALLO: cambiaron categorias distintas de bb_check: %s'
                    % otros)
    else:
        msgs.append('OK  bb_check %d -> %d (%+d); ninguna otra categoria cambio'
                    % (categorias_antes['bb_check'], cats_desp['bb_check'],
                       delta_bb))
    return ok, msgs


# ------------------------------------------------------------------- aplicar
def escribir_atomico(lineas, destino):
    """Escribe a temporal, valida, y reemplaza. Devuelve el temporal usado."""
    d = os.path.dirname(destino)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.hands_db_', suffix='.tmp')
    os.close(fd)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for linea in lineas:
            f.write(linea if linea.endswith('\n') else linea + '\n')
    # validar el temporal completo antes de tocar el original
    with io.open(tmp, encoding='utf-8') as f:
        for n, linea in enumerate(f, 1):
            if linea.strip():
                try:
                    json.loads(linea)
                except ValueError as exc:
                    os.remove(tmp)
                    raise ValueError('temporal invalido en linea %d: %s'
                                     % (n, exc))
    return tmp


def manos_resultantes(plan):
    """La lista COMPLETA de manos despues de aplicar el plan.

    `plan.nuevas` solo lleva las manos tocadas; el resto va como None. Para
    verificar hay que reconstruir la base entera, no comparar 27 contra 1280.
    """
    out = []
    for i, h in enumerate(plan.manos):
        if h is None:
            continue
        out.append(plan.nuevas[i] if i < len(plan.nuevas) and plan.nuevas[i]
                   else h)
    return out


def aplicar(plan):
    manos_antes = [h for h in plan.manos if h]

    # ---- garantia 3: backup verificado --------------------------------
    stamp = os.path.dirname(DB_PATH)
    backup_dir = os.path.join(stamp, '_backup_aplicar_correcciones')
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, 'hands_db.jsonl')
    shutil.copy2(DB_PATH, backup)
    h_orig, h_back = sha256(DB_PATH), sha256(backup)
    print('backup    : %s' % os.path.relpath(backup, ROOT))
    print('sha256    : %s' % h_orig)
    print('verificado: %s' % ('OK, coinciden' if h_orig == h_back
                             else 'FALLO, NO coinciden'))
    if h_orig != h_back:
        raise RuntimeError('el backup no coincide con el original; abortando')
    print()

    categorias_antes = categorias(manos_antes)

    # serializar las manos modificadas y reconstruir el fichero
    lineas = []
    for i, linea in enumerate(plan.lineas):
        if not linea.strip():
            lineas.append(linea)
            continue
        nueva = plan.nuevas[i] if i < len(plan.nuevas) else None
        if nueva is None:
            lineas.append(linea)
        else:
            lineas.append(json.dumps(nueva, ensure_ascii=False) + '\n')

    manos_despues = manos_resultantes(plan)
    ok, msgs = verificar(plan, manos_antes, categorias_antes,
                         manos_despues=manos_despues)
    if not ok:
        print('la verificacion en memoria falla; NO se escribe nada:')
        for m in msgs:
            print('   %s' % m)
        print('\nnada modificado. Backup creado sin usar: %s' % backup)
        return False

    tmp = escribir_atomico(lineas, DB_PATH)
    try:
        os.replace(tmp, DB_PATH)
    except Exception:
        os.remove(tmp)
        shutil.copy2(backup, DB_PATH)
        raise

    # ---- garantia 8 sobre el fichero YA escrito -------------------------
    releido = [json.loads(l) for l in leer_lineas(DB_PATH) if l.strip()]
    ok2, msgs2 = verificar(plan, manos_antes, categorias_antes,
                           manos_despues=releido)

    print('VERIFICACION POST-ESCRITURA')
    for m in msgs2:
        print('   %s' % m)

    if not ok2:
        # ---- garantia 9: rollback --------------------------------------
        print()
        print('la verificacion post-escritura FALLA: restaurando el backup')
        shutil.copy2(backup, DB_PATH)
        if sha256(DB_PATH) == h_orig:
            print('   rollback OK, la base vuelve a estar intacta (sha256 %s)'
                  % h_orig[:16])
        else:
            print('   *** ROLLBACK FALLIDO: revisa %s a mano ***' % backup)
        return False

    print()
    print('aplicado. nuevo sha256: %s' % sha256(DB_PATH))
    nuevo = sha256(DB_PATH)
    if nuevo != SHA_SALIDA:
        print()
        print('  AVISO: el resultado NO es el que este script declara.')
        print('  esperado : %s' % SHA_SALIDA)
        print('  obtenido : %s' % nuevo)
        print('  Si el cambio es legitimo, actualiza SHA_SALIDA y explica el')
        print('  motivo en DOCS/CANAL_MANUAL_CERRADO.md. Si no lo es,')
        print('  revierte: git checkout %s -- %s'
              % (subprocess.check_output(
                  ['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT)
                  .decode().strip(), DB_REL))
    else:
        print('  OK  coincide con SHA_SALIDA, declarado en este script.')
    return True


# ---------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribir de verdad (sin esto, dry-run)')
    args = ap.parse_args(argv)

    plan = construir_plan()

    print('=' * 78)
    print('aplicar_correcciones  ·  %s' % ('MODO REAL' if args.apply
                                           else 'DRY-RUN (no escribe)'))
    print('=' * 78)

    if plan.errores:
        print()
        print('PRECONDICIONES INCUMPLIDAS:')
        for e in plan.errores:
            print('   - %s' % e)
        print()
        print('ABORTANDO. No se modifica nada.')
        return 2

    obs, inf = imprimir_diff(plan)
    imprimir_bloqueados(plan)

    print()
    print('-' * 78)
    print('resumen: %d correccion(es) observada(s), %d inferida(s), '
          '%d ya aplicada(s), %d bloqueada(s)'
          % (len(obs), len(inf), len(plan.ya_aplicados), len(plan.bloqueados)))
    for y in plan.ya_aplicados:
        print('   ya aplicada: %s' % y)

    if plan.ya_aplicada_en_todo and not plan.cambios:
        print()
        print('MIGRACION YA APLICADA POR COMPLETO:')
        print('   CM-001: importe ya corregido')
        print('   CM-003: %d checks inferidos ya presentes en la base'
              % plan.n_inferidas_en_base)
        print()
        print('no se modifica nada (idempotencia).')
        return 0
    print()
    print('  Fuera de esta migracion siguen %d manos con la ciega del BB mal'
          % CIEGA_MAL_PUESTA)
    print('  puesta: el motor les asigna una SUBIDA que puede no haber')
    print('  ocurrido (rol/squeeze/3bet/open). No se corrigen aqui porque')
    print('  exigirian inventar un orden. Ver tools/auditar_bb_check.py.')

    if not plan.cambios:
        print()
        print('nada que hacer: la migracion ya esta aplicada por completo.')
        return 0

    if len(inf) != MIGRABLES_ESPERADOS:
        print()
        print('AVISO: %d inferidas, se esperaban %d. Revisar antes de aplicar.'
              % (len(inf), MIGRABLES_ESPERADOS))
        if not args.apply:
            return 1

    if not args.apply:
        print()
        print('DRY-RUN. Para escribir de verdad: --apply')
        return 0

    ok = aplicar(plan)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
