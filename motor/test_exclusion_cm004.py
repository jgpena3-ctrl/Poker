# -*- coding: utf-8 -*-
"""Las 23 manos de CM-004 fuera de la ventana de calibracion.

revision_1 Tarea 2 y revision_2 punto 4: la exclusion no depende de la
decision de regrabar o migrar. El defecto esta identificado y su efecto
sobre el perfil del BB no esta cuantificado; mantenerlas dentro seria usar
unas cifras que el propio proyecto ya sabe que no son fiables.

Lo que estos tests protegen:

  - la ventana cuenta 877, no 900, y se sabe por que
  - H_0031 no esta, y las otras 22 tampoco
  - las manos NO se borran: siguen en el fichero y en `reliable_only=False`
  - el motivo es consultable, no esta escrito en piedra
"""
from motor import learn


CM004 = learn.manos_excluidas()


def test_h_0031_no_esta_en_la_ventana_fiable():
    """El caso que nombra revision_1, literalmente."""
    ids = {h['hand_id'] for h in learn.load_hands(reliable_only=True)}
    assert 'H_0031' not in ids


def test_ninguna_de_las_23_esta_en_la_ventana_fiable():
    ids = {h['hand_id'] for h in learn.load_hands(reliable_only=True)}
    assert len(CM004) == 23
    assert not (CM004 & ids), sorted(CM004 & ids)


def test_la_ventana_fiable_cuenta_877():
    """900 lineas de corte menos 23 exclusiones. La cifra se puede razonar."""
    ventana = learn.load_hands(reliable_only=True)
    assert len(ventana) == 877
    assert len(ventana) == learn.RELIABLE_HANDS - len(CM004)


def test_las_23_no_se_borran_del_fichero():
    """Se EXCLUYEN, no se eliminan. La evidencia se preserva."""
    ids = {h['hand_id'] for h in learn.load_hands(reliable_only=False)}
    assert CM004 <= ids, 'alguien borro manos del historico'


def test_la_exclusion_es_declarada_y_consultable():
    """`EXCLUSIONES_VENTANA_FABLE` es la fuente; el motivo se puede leer."""
    claves = {c for c, _m, _i in learn.EXCLUSIONES_VENTANA_FABLE}
    assert claves == {'CM-004'}
    motivo = learn.motivos_exclusion('H_0031')
    assert motivo and 'CM-004' in motivo and 'ciega' in motivo
    assert learn.motivos_exclusion('H_0001') is None


def test_excluir_no_arrastra_a_manos_sanas():
    """Las manos que NO son de CM-004 siguen dentro, incluidas las que lo
    fueron de otros defectos ya migrados (CM-001, CM-003)."""
    ids = {h['hand_id'] for h in learn.load_hands(reliable_only=True)}
    for sana in ('H_0001', 'H_0100', 'H_0500', 'H_0900'):
        assert sana in ids, '%s no deberia estar excluida' % sana


def test_la_exclusion_es_reversible_con_un_solo_conmutador():
    """Si aparece el original, se quita la lista y la ventana vuelve a 900.

    Se comprueba que, sin el filtro de exclusion, el mismo corte de 900 lineas
    que haria `reliable_only=False` con `max_hands=900`.
    """
    todas = learn.load_hands(max_hands=learn.RELIABLE_HANDS)
    ventana = learn.load_hands(reliable_only=True)
    assert len(todas) == 900
    assert len(ventana) == len(todas) - 23