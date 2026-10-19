# -*- coding: utf-8 -*-
"""`lista_saneamiento.py`: que los lotes sean fiables y que no escriba.

Que hay que probar, y por que
-----------------------------
Un instrumento de saneamiento tiene dos formas de mentir:

  1. Dice que no hay nada que arreglar. Un detector que no se contrasta con
     una respuesta conocida no es un instrumento, es una opinion. Y aqui el
     coste de creerselo es alto: se cierra la revision y el defecto se queda.

  2. Escribe en la base. Este script SOLO propone. Si el saneamiento lo
     automatizara, la decision del mantenedor habria desaparecido, y el
     guard de `test_canal_manual.py` —que obliga a declarar el hash— dejaria
     de ser el unico sitio por el que puede pasar una escritura.

Las dos se comprueban aqui, y la segunda se comprueba PLANTANDO la
violacion: si el check solo se ejecuta contra el fichero real, solo se le ve
pasar, y no hay forma de saber si funciona o si esta muerto.
"""
import io
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn  # noqa: E402
from tools import auditar_rango as AR  # noqa: E402
from tools import lista_saneamiento as LS  # noqa: E402


# --- (1) los lotes cubren cada clase, y solo una vez -----------------------

def test_cada_clase_esta_en_exactamente_un_lote():
    """Dos lotes con la misma clase duplican el trabajo y rompen el recuento.

    No es hipotetico: la primera version de este fichero dejo las siete
    clases que dan 0 fuera de todo lote, y `--validar` lo encontro. Lo
    encontro porque se comprueba, no porque se lea.
    """
    visto = {}
    for lote in LS.LOTES:
        for c in lote.clases:
            assert c not in visto, (
                'la clase %s esta en los lotes %s y %s' % (c, visto[c], lote.clave))
            visto[c] = lote.clave

    auditadas = {c for c, _e, _f, _n in AR.CLASES}
    sin_lote = auditadas - set(visto)
    assert not sin_lote, (
        'clases de `auditar_rango.py` sin lote: %s\n\n'
        'Una clase sin lote NO es una clase limpia: es una clase que nadie '
        'mira. Si da 0, se pone en un lote con 0. Un lote vacio se ve; una '
        'clase sin lote, no.' % ', '.join(sorted(sin_lote)))


def test_las_cifras_de_los_lotes_cuadran_con_los_detectores():
    """El recuento del lote es el del detector. Si no, el lote mente.

    Agregado, y luego mano a mano en el test siguiente. El agregado avisa
    pronto; el desglosado dice WHICH lote se ha desviado.
    """
    manos = LS.cargar()
    hall, _m = AR.auditar(list(manos.values()))
    total_lotes = sum(len(hall.get(c, ())) for lote in LS.LOTES
                      for c in lote.clases)
    total_detectores = sum(len(v) for v in hall.values())
    assert total_lotes == total_detectores, (
        'los lotes suman %d casos y los detectores %d. O hay una clase en dos '
        'lotes, o hay una clase que no esta en ninguno.'
        % (total_lotes, total_detectores))


def test_el_lote_tiene_las_manos_que_dice_tener():
    """Cada lote, contra el detector, mano a mano. Sin Energia agregada."""
    manos = LS.cargar()
    lotes, _mult, _res = LS.construir(manos, None)
    hall, _m = AR.auditar(list(manos.values()))
    por_id = {l['clave']: l for l in lotes}
    for lote in LS.LOTES:
        esperado = sorted(
            (hid for c in lote.clases for hid, _d in hall.get(c, ())),
            key=lambda h: AR.num(h) or 0)
        got = [c['hand_id'] for c in por_id[lote.clave]['manos']]
        assert got == esperado, (
            'el lote %s no lleva las mismas manos que el detector.\n'
            '  detector: %s\n  lote    : %s'
            % (lote.clave, esperado[:10], got[:10]))


def test_la_autocomprobacion_del_script_pasa():
    """`--validar` tiene que dar 0 en el estado real, y no en un estado ideal."""
    assert LS.validar() == 0


# --- (2) el chequeo de no-escritura PUEDE fallar ----------------------------

@pytest.mark.parametrize('codigo,por_que', [
    ("open(DB_PATH, 'w')", 'abre la base en escritura'),
    ('open(DB_PATH)', 'abre la base'),
    ("open('data/hands_db.jsonl', 'w')", 'la nombra literal'),
    ('os.replace(tmp, DB_PATH)', 'escritura atomica'),
    ('shutil.move(a, b)', 'mover'),
    ('shutil.copyfile(a, b)', 'copiar'),
    ('os.rename(a, b)', 'renombrar'),
])
def test_el_chequeo_de_escritura_detecta_lo_que_tiene_que_detectar(codigo, por_que):
    """Se planta la violacion y se exige que salte.

    Sin esto, el chequeo se veria pasar una vez y nadie sabria si mira algo.
    Es la diferencia entre un guard y una decoracion: un guard se prueba
    fallando.
    """
    assert LS.violaciones_de_escritura(codigo), (
        'el chequeo NO detecta %r (%s). Si el chequeo no puede fallar, no '
        'esta mirando nada.' % (codigo, por_que))


def test_el_chequeo_no_dispara_con_lo_que_este_fichero_hace_de_verdad():
    """El otro lado: no puede que avise de lo legitimo.

    Este fichero ESCRIBE en disco, para el volcado `--json`. Si el chequeo
    protestara por eso, dejaria de avisar de lo que importa. Un guard que
    grita siempre es un guard apagado.
    """
    propio = io.open(os.path.join(ROOT, 'tools', 'lista_saneamiento.py'),
                     encoding='utf-8').read()
    assert LS.violaciones_de_escritura(propio) == []


def test_volcar_json_no_toca_la_base(tmp_path):
    """El volcado escribe un fichero y NO cambia el sha de la base.

    Se mide antes y despues. No se comprueba que el codigo «parezca» de
    solo lectura: se comprueba que la base tiene el mismo sha cuando el
    script termina.
    """
    antes = LS.sha_de()
    destino = tmp_path / 'salida.json'
    assert LS.main(['--json', str(destino)]) == 0
    assert LS.sha_de() == antes, 'el volcado cambio la base'
    assert os.path.exists(destino)
    with io.open(str(destino), encoding='utf-8') as f:
        datos = json.load(f)
    assert datos['resumen']['db_sha256'] == antes
    assert 'lotes' in datos and datos['lotes'], 'el volcado salio vacio'


def test_correr_la_lista_no_toca_la_base():
    """Lo mismo, sin el volcado: el informe de consola tambien es de lectura."""
    antes = LS.sha_de()
    assert LS.main([]) == 0
    assert LS.sha_de() == antes


def test_la_lista_avisa_si_el_disco_no_es_el_declarado(monkeypatch, capsys):
    """Si el sha del disco no es el del manifiesto, lo dice en grande.

    Es el caso real: alguien edita la base con el editor y el manifiesto se
    queda viejo. Un informe que no lo menciona se lee como si valiera igual,
    y se decide sobre una base que no es la que se cree.
    """
    antes = LS.sha_de()
    monkeypatch.setattr(learn, 'HANDS_DB_SHA256', '0' * 64)
    assert LS.main([]) == 0
    out = capsys.readouterr().out
    assert 'NO es el declarado' in out, out
    assert LS.sha_de() == antes


# --- (3) el alcance, que es donde estaba el agujero ------------------------

def test_por_defecto_cubre_toda_la_base():
    """Todo el alcance, no `H_1014`.

    La revision manual llego a `H_1282` y el rango auditado se quedo en
    `H_1014`: 267 manos se corrigieron sin que ningun detector las mirase, y
    por ahi se colaron 4 defectos (H_1203, H_1063, H_1241, H_1196). Un
    instrumento con el rango viejo no puede encontrar lo que hay fuera del
    rango viejo.
    """
    manos = LS.cargar()
    _lotes, _mult, resumen = LS.construir(manos, None)
    assert resumen['manos'] == len(manos) == 1258


def test_las_manos_fuera_del_rango_auditado_tienen_defectos():
    """El agujero era real, y esto lo demuestra en vez de recordarlo.

    Se mide contra `dfef471`, el commit ANTERIOR al saneamiento, y no contra
    la base de hoy. La razon: `H_1063` y `H_1203` ya estan corregidas, asi que
    si el test mirara la base actual solo veria una de las cuatro yaria bien.

    Medir contra el pasado tiene una ventaja que medir contra el presente no
    tiene: el defecto no puede desaparecer. `dfef471` esta en git, y dentro
    de el los cuatro existen siempre. Si alguien recorta el alcance otra vez,
    este test sigue viendo lo mismo y sigue fallando.

    Y las cuatro importan por lo mismo: estan en las 267 manos que la revision
    toco sin que ningun detector las mirase.
    """
    import subprocess
    crudo = subprocess.run(
        ['git', 'show', 'dfef471:data/hands_db.jsonl'],
        cwd=ROOT, capture_output=True).stdout.decode('utf-8')
    manos = {json.loads(l)['hand_id']: json.loads(l)
             for l in crudo.splitlines() if l.strip()}
    hall, _m = AR.auditar(list(manos.values()))

    fuera = {hid for hid in manos
             if (AR.num(hid) or 0) > (AR.num('H_1014') or 0)}
    esperadas = {
        'H_1203': 'INACTIVO_QUE_ACTUA',
        'H_1063': 'AUSENCIA_RESPUESTA_BB',
        'H_1241': 'AUSENCIA_RESPUESTA_BB',
        'H_1196': 'CM-004',
    }
    for hid, clase in sorted(esperadas.items()):
        h = manos[hid]
        detector = {'INACTIVO_QUE_ACTUA': AR.inactivo_que_actua,
                    'AUSENCIA_RESPUESTA_BB': AR.ausencia_respuesta_bb,
                    'CM-004': AR.cm_004}[clase]
        assert detector(h), (
            '%s estaba fuera de H_1014 y en dfef471 no daba %s. Si eso '
            'cambio, dfef471 cambio y este test esta obsoleto.'
            % (hid, clase))
        assert hid in fuera


def test_el_detector_nuevo_encuentra_lo_que_ninguno_miraba():
    """`INACTIVO_QUE_ACTUA` existe porque un agujero se escondio como silencio.

    La historia, que es el motivo de que el detector sea permanente: el
    defecto real de `H_1203` era un BB con `active: false` jugando cuatro
    calles. `accion_fantasma` lo rozaba, pero de rebote y por el motivo
    equivocado —confundia `active` con «esta en la mesa»—. Al corregir ese
    detector, el defecto de `H_1203` desaparecio del informe sin haberse
    corregido. Un agujero que no se ve no se arregla nunca.

    Por eso el test mira el commit viejo: `dfef471` tiene el defecto, y lo
    tiene para siempre.
    """
    import subprocess
    crudo = subprocess.run(
        ['git', 'show', 'dfef471:data/hands_db.jsonl'],
        cwd=ROOT, capture_output=True).stdout.decode('utf-8')
    antes = {json.loads(l)['hand_id']: json.loads(l)
             for l in crudo.splitlines() if l.strip()}
    assert AR.inactivo_que_actua(antes['H_1203']) == ['BB(Jarduan)']

    # y hoy ya no, porque se corrigio
    assert not AR.inactivo_que_actua(LS.cargar()['H_1203'])


def test_el_rango_por_defecto_sigue_siendo_toda_la_base():
    """Que el alcance no se haya recortado al corregir las que se corregian.

    Es el modo de fallo natural de un saneamiento: corriges lo que sale, y el
    alcance se queda en lo que ya conocias. Aqui se comprueba que `H_1282`,
    la ultima mano, sigue dentro.
    """
    manos = LS.cargar()
    _lotes, _mult, resumen = LS.construir(manos, None)
    assert resumen['manos'] == 1258
    assert 'H_1282' in manos


def test_la_violacion_de_cm004_es_cero_y_el_cierre_esta_escrito():
    """La mano abierta ya no esta abierta, y el cierre esta DECIDIDO.

    Antes este test fijaba `H_1196` por identidad, para que no se perdiera de
    vista mientras no se decidia. Ahora la decision esta tomada —la primera
    de las dos ramas: el registro de la mano estaba mal, y se corrige en el
    fichero— y el defecto es CERO en toda la base.

    Y las dos mitades, porque cada una sola no dice nada:

      1. que la violation sea cero, que es la MEDICION;
      2. que el cierre este ESCRITO, que es lo que distingue «se corrigió» de
         «se corrigió y nadie lo dejó escrito».

    Y la segunda es la que importa: un defecto que desaparece sin que nadie
    lo decida se ha decidido por olvido, y un olvido no se parece a una
    decision solo en el resultado: se parece tambien en que no se puede
    revertir ni explicar.
    """
    manos = LS.cargar()
    hall, _m = AR.auditar(list(manos.values()))
    cm004 = sorted(h for h, _d in hall['CM-004'])
    assert cm004 == [], (
        'la violation de CM-004 es cero en toda la base, y sale %r. Si vuelve '
        'a aparecer, la correccion de `H_1196` no era la unica.' % cm004)

    doc = io.open(os.path.join(ROOT, 'DOCS', 'INC-004_H_1196.md'),
                  encoding='utf-8').read()
    declaracion = [l for l in doc.split('\n') if 'ESTADO:' in l.upper()]
    assert len(declaracion) == 1, (
        'tiene que haber UNA declaracion de estado, y no %d' % len(declaracion))
    assert 'CERRADO' in declaracion[0].upper(), (
        'y tiene que decir CERRADO: %r' % declaracion[0])


# --- (4) el reparto de trabajo, que es la razon de este fichero ------------

def test_cada_tiene_un_tipo_y_todos_los_tipos_existen():
    """La clasificacion por coste de decision es lo que aporta el fichero.

    Sin ella seria un `auditar_rango.py` con otro nombre. Con ella, quien
    mantiene puede ver que hay 73 manos que son UNA decision y 3 que son
    tres, y empezar por donde el trabajo rinde.
    """
    for lote in LS.LOTES:
        assert lote.tipo in (LS.MECANICO, LS.LECTURA_DOBLE, LS.LOTE, LS.LIMPIO), \
            '%s tiene un tipo que no existe: %s' % (lote.clave, lote.tipo)
        assert lote.titulo, '%s no explica que es' % lote.clave
        assert lote.decision, '%s no dice que hay que decidir' % lote.clave


def test_sin_allin_es_un_lote_y_no_73_problemas():
    """El motivo por el que este fichero existe, medido.

    `SIN_ALLIN` da 73 casos y son las manos `H_0001`..`H_0073`, contiguas.
    Presentarlos como «73 problemas» hace que seplane un trabajo de 73
    decisiones lo que es UNO de esquema. Este test falla si el lote deja de
    declarar que es un lote, que es lo que pasaria si alguien lo convirtiera
    en 73 tareas al añadirle una correccion automatica.
    """
    lote = next(l for l in LS.LOTES if 'SIN_ALLIN' in l.clases)
    assert lote.tipo == LS.LOTE
    manos = LS.cargar()
    hall, _m = AR.auditar(list(manos.values()))
    ids = sorted((h for h, _d in hall['SIN_ALLIN']), key=lambda h: AR.num(h) or 0)
    assert len(ids) == 73, ids[:5]
    numeros = [AR.num(h) for h in ids]
    assert numeros == list(range(1, 74)), (
        'las manos sin `allin` ya no son H_0001..H_0073. Si el tramo se '
        'corrigio, este test esta obsoleto y hay que actualizarlo; si cambio '
        'la forma, el lote ya no es un lote.')


def test_el_instrumento_no_se_registra_como_escritor_de_la_base():
    """Que `quien_escribe.py` no lo cuente como alguien que escribe.

    El inventario de escritores es lo que sostiene la promesa de que la base
    solo se edita a mano. Un instrumento de lectura que se colara en esa lista
    haria que la promesa no significara nada.
    """
    salida = subprocess.run(
        [sys.executable, os.path.join(ROOT, 'tools', 'quien_escribe.py')],
        capture_output=True, cwd=ROOT)
    texto = salida.stdout.decode('utf-8', 'replace')
    assert 'lista_saneamiento.py' not in texto, (
        'quien_escribe.py cuenta lista_saneamiento.py. No lo hace, o ha '
        'cambiado. Ver tools/quien_escribe.py --autocomprobacion.')
