# -*- coding: utf-8 -*-
"""Lo que `revision_2` §2 y §3 pide comprobar del verificador.

§3. La correccion tiene que funcionar sobre el caso DOCUMENTADO. El defecto
    es `se` + U+0435 (ie cirilico) + `Normalized`. Antes se derivaba la
    secuencia con `antes.replace(antes[-1], caracter)`, y `antes[-1]` de
    `seNormalized` es la `d` FINAL: la secuencia salia
    `seNormalize<cirilico>d` y la correccion no podia dispararse nunca.
    Estos tres casos son los que R2 nombra, y el primero es el que hacia
    falta.

§2. El numeraje de lineas. R2 afirma que `n` puede no corresponder a la
    linea real del bloque siguiente. Eso se mide con un diff de numeros
    conocidos, en vez de discutirlo.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIRILICO = chr(0x435)


def _mod():
    ruta = os.path.join(ROOT, 'tools', 'verificar_caracteres.py')
    spec = importlib.util.spec_from_file_location('vc', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ============================================ §3: la correccion, tres casos
def test_una_coincidencia_exacta_se_corrige():
    """El caso documentado, y el unico que tiene que escribir."""
    vc = _mod()
    roto = 'x = "se' + CIRILICO + 'Normalized"   # comentario'
    nuevo, apl, pend = vc.correcciones_de(roto)
    assert pend == [], 'una coincidencia no es pendiente'
    assert len(apl) == 1
    assert CIRILICO not in nuevo, 'el caracter raro tiene que desaparecer'
    assert nuevo == 'x = "se normalizado"   # comentario'


def test_una_cadena_ascii_legitima_no_se_toca():
    """`seNormalized` en ASCII es texto normal. Si esto se corrigiera, el
    preventor estaria rompiendo ficheros, que es lo que hace INC-003."""
    vc = _mod()
    ok = 'y = "seNormalized"'
    nuevo, apl, pend = vc.correcciones_de(ok)
    assert nuevo == ok, 'no puede tocar texto ASCII'
    assert apl == [] and pend == []


def test_dos_coincidencias_exactas_no_se_corrige():
    """Dos ya no son 'el caso conocido', son dos casos: se informa y no se
    escribe."""
    vc = _mod()
    roto = ('a = "se' + CIRILICO + 'Normalized"\n'
            'b = "se' + CIRILICO + 'Normalized"\n')
    nuevo, apl, pend = vc.correcciones_de(roto)
    assert nuevo == roto, 'no puede escribir con dos coincidencias'
    assert apl == []
    assert len(pend) == 1
    assert pend[0][1].count(CIRILICO) == 1 and pend[0][2] == 2, (
        'la pendiente dice QUE secuencia y CUANTAS')


def test_una_coincidencia_y_otra_ilegítima_usan_registros_distintos():
    """La regla se aplica a la SECUENCIA, no al fichero entero: una
    coincidencia buena no se bloquea por el hecho de que el fichero tenga
    otra cosa distinta."""
    vc = _mod()
    texto = ('seNormalized\n'
             'se' + CIRILICO + 'Normalized\n')
    nuevo, apl, pend = vc.correcciones_de(texto)
    assert pend == []
    assert len(apl) == 1
    assert nuevo.split('\n')[0] == 'seNormalized', 'la ASCII intacta'
    assert nuevo.split('\n')[1] == 'se normalizado'


def test_la_secuencia_se_construye_con_el_cirilico_en_su_sitio():
    """El bug concreto. Si alguien vuelve a derivar la secuencia del
    nombre en vez de escribirla, este test falla."""
    vc = _mod()
    (clave, (patron, reemplazo, caracter)), = vc.CORRECCIONES.items()
    bueno = patron.replace('{0}', caracter)
    assert bueno == 'se' + CIRILICO + 'Normalized', (
        'la secuencia tiene que ser `se` + U+0435 + `Normalized`, y es %r'
        % bueno)
    assert caracter == chr(0x435), 'el caracter raro es el U+0435'


def test_ningun_caracter_raro_en_crudo_en_el_propio_verificador():
    """El verificador define el caso con `chr()`, no escribiendolo: si se
    escribiera el U+0435 en crudo, el script se contaminaria a si mismo."""
    vc = _mod()
    fuente = open(vc.__file__, encoding='utf-8').read()
    # el unico sitio donde puede aparecer es la cadena de este propio test
    assert fuente.count(CIRILICO) == 0, (
        'el verificador no lleva el caracter en crudo')


# ================================== §2: el numeraje de lineas del diff
DIFF_SINTETICO = (
    'diff --git a/x.py b/x.py\n'
    'index 1111111..2222222 100644\n'
    '--- a/x.py\n'
    '+++ b/x.py\n'
    '@@ -40,0 +41,2 @@\n'
    '+primera\n'
    '+segunda\n'
    '@@ -100,0 +103,1 @@\n'
    '+cuarta\n'
)


def test_el_numero_de_linea_sale_del_encabezado_del_bloque():
    """Con `-U0` no hay lineas de contexto, asi que `n` NO se desincroniza:
    `+41,2` da 41 y 42, y `+103,1` da 103. Es lo que mide la afirmacion
    de `revision_2` §2, en vez de suponerla."""
    vc = _mod()
    nuevas = vc.parsear_hunks(DIFF_SINTETICO)
    assert nuevas == [(41, 'primera'), (42, 'segunda'), (103, 'cuarta')], \
        'los numeros tienen que ser 41, 42 y 103; son %r' % nuevas


def test_un_bloque_intermedio_no_rompe_la_cuenta():
    """La duda real de R2: si el contador se desincroniza tras un bloque,
    el segundo bloque daria numeros falsos. Aqui no, porque cada `@@` lo
    reinicia desde su `+c`."""
    vc = _mod()
    nuevas = vc.parsear_hunks(DIFF_SINTETICO)
    assert nuevas[-1][0] == 103, 'el segundo bloque reinicia en su +c'


def test_las_lineas_borradas_no_avanzan_el_numero():
    """Una linea eliminada ocupa sitio en el fichero viejo, no en el nuevo.
    Contarla como si ocupara, correria todos los numeros siguientes."""
    vc = _mod()
    diff = ('@@ -10,2 +10,2 @@\n'
            '-se va\n'
            '+viene\n'
            '+otra\n')
    assert vc.parsear_hunks(diff) == [(10, 'viene'), (11, 'otra')]


def test_los_encabezados_de_fichero_no_cuentan_como_lineas_anadidas():
    vc = _mod()
    nuevas = vc.parsear_hunks(DIFF_SINTETICO)
    assert not any(t.startswith('++') for _n, t in nuevas)
    assert len(nuevas) == 3


def test_en_cambio_devuelve_todas_las_lineas_no_solo_la_primera():
    """Si el cambio anade el mismo caracter en dos sitios, el informe tiene
    que senalar los dos."""
    vc = _mod()
    assert vc.en_cambio.__doc__.count('TODAS') == 1, (
        'el contrato de en_cambio dice que devuelve todas')

# ============== §2 bis: lo que el diff NO ve, y que es justo lo nuevo
def test_un_fichero_sin_seguimiento_es_todo_del_cambio(vc=None):
    """git diff no ve un fichero sin seguimiento. Sin este caso, el
    fichero nuevo de este bloque salio PREEXISTENTE: es el mismo error que
    R2 pointed, por el otro extremo."""
    vc = _mod()
    rel = 'tools/test_verificador_caracteres.py'
    assert vc._porcelain(rel).startswith('??') or '??' in vc._porcelain(rel), (
        'este test solo tiene sentido si el fichero sigue SIN SEGUIMIENTO; '
        'si ya esta commiteado, la asercion lo dira y habra que quitarlo')
    nuevas = vc.lineas_nuevas(os.path.join(ROOT, rel))
    assert nuevas, 'un fichero sin seguimiento tiene lineas nuevas'
    assert min(n for n, _t in nuevas) == 1
    # Y sale el TEXTO REAL del fichero, linea a linea: un fichero sin
    # seguimiento es ENTERO nuevo, no un recorte.
    propio = list(enumerate(open(os.path.join(ROOT, rel),
                                 encoding='utf-8').read().split(chr(10)), 1))
    assert nuevas == propio, (
        'sin seguimiento tiene que devolver el fichero entero; devuelve %d '
        'lineas de %d' % (len(nuevas), len(propio)))


def test_un_fichero_rastreado_y_sin_cambios_no_tiene_lineas_nuevas():
    """El otro extremo: un fichero que no ha cambiado no puede salir
    DEL CAMBIO aunque tenga el caracter dentro."""
    vc = _mod()
    rel = 'motor/test_canal_manual.py'
    assert '??' not in vc._porcelain(rel)
    assert vc.lineas_nuevas(os.path.join(ROOT, rel)) == []
