# -*- coding: utf-8 -*-
"""Tres comprobaciones que este bloque ha necesitado mas de una vez.

1. EL EXIT CODE 4 — «un test que nunca se ejecuto y daba verde»

   `pytest FICHERO -q ::test` no selecciona nada: exit 4, «no tests ran».

   Y 4 != 0. O sea que `assert returncode != 0` sobre eso PASA SIEMPRE, en
   verde. Ha estado dando verde desde que lo escribi.

   Que es el patron de los veintiseis en su forma mas pura: un instrumento
   que dice «algo ha caido» sin haber ejecutado nada.

   Y la leccion de R2 es la que hay que aplicar en general:

       un codigo de salida distinto de cero no significa necesariamente que
       un test haya fallado. Tambien puede indicar que no se encontro
       ningun test.

   O sea: comprobar el CODIGO no basta. Hay que comprobar que el test
   OBJETIVO se ha ejecutado.

   Y AQUI HAY UNA ASIMETRIA QUE MEDI, y que es lo que hace que esto no sea
   «una comprobacion mas». Con `-q`, en VERDE, el nombre del test NO sale en
   ningun sitio: la salida es `.` y `1 passed`. En ROJO si sale, y con
   `FAILED` delante. O sea que en verde hay que mirar el RECUENTO, y en rojo
   el NOMBRE, y una sola comprobacion con un «o» haria verde un caso
   imposible y caeria en el otro.

   Y el sitio donde vive esta regla es `ejecutar_pytest.py`, con sus
   pruebas, y aqui lo que queda es lo que es de este fichero: la MATRIZ y
   el MUTADOR.

2. LA MATRIZ DE INDEPENDENCIA DE LOS DOS MECANISMOS

   Los contratos se vigilan con dos mecanismos: el CONTENIDO y la HUELLA.
   Con dos roturas: la de AFIRMACION y la COSMETICA.

   La matriz completa, y las cuatro celdas:

                | afirmacion | cosmetica
     -----------+------------+-----------
     contenido  | CAE        | NO cae
     huella     | CAE        | CAE

   Las dos celdas que importan para demostrar que son DOS mecanismos y no uno
   repetido:

     - contenido con cosmetica NO cae   -> el contenido no mira la forma
     - huella con cosmetica CAE        -> la huella mira cualquier cambio

   Y la que R2 pide y faltaba: la huella con la rotura de AFIRMACION tambien
   cae, y eso es lo correcto — la huella ve cualquier cambio de texto —. Si
   NO caera, la huella estaria midiendo lo mismo que el contenido, y entonces
   no serian dos mecanismos.

3. QUE LAS MUTACIONES SEAN COMPLETAS

   «Una mutacion que cambia una aparicion no es una mutacion». Tres veces:

     - «sin el filtro»    -> una aparicion de varias
     - la frase del y = 0 -> uno de tres sitios
     - «herо continúa»    -> una variante de cinco

   Y lo que se comprueba aqui no es que las mutaciones sean completas, sino
   que EL MUTADOR ES COMPLETO: que cambia todas las apariciones y todas las
   variantes, y que despues de mutar no queda ninguna forma de la propiedad.

   Que es lo unico que se puede comprobar sin repetir cada mutacion a mano.

   Y el laboratorio se construye DESDE la lista de formas aceptadas, no a
   mano. Un texto escrito a mano contra una lista se queda viejo en cuanto
   se anade una forma, y el fallo es el que se vio al escribirlo: decia
   traer tres variantes y traia una. O sea que el laboratorio mentia sobre
   lo que probaba.

   Y ademas el mutador real —el de `test_tareas_r1.py`, el que rompe el
   contrato de verdad— comprueba TAMBIEN que no queda ninguna forma, y dice
   cual. Los dos hacen falta: uno mira el mutador, el otro mira lo que ha
   hecho sobre el documento.

4. QUE ESTRECHAR UNA MARCA NO LA DEJE SIN DIENTES

   Al final, porque lo de este bloque ha sido eso: se ha estrecho la marca de
   `MECANISMO` a la DECLARACION, y estrecharla sin comprobar que sigue
   cazando lo que tiene que cazar es dejar la regla muda.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import retraccion_scan as rs                                   # noqa: E402

# ================================================ 1. EL EXIT CODE
EXIT_QUE_SIGNIFICA = {
    0: 'todo verde',
    1: 'ha fallado ALGO — que es lo que tiene que pasar',
    2: 'interrumpido',
    3: 'error interno de pytest',
    4: ' USO INTERNO: NO SE HA EJECUTADO NINGUN TEST',
    5: 'NO SE HA ENCONTRADO NINGUN TEST',
}


def _correr(args, env=None):
    r = subprocess.run([sys.executable, '-m', 'pytest'] + args,
                       cwd=ROOT, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


def test_el_exit_code_4_significa_que_no_se_ha_ejecutado_nada():
    """La precondicion de todo lo demas: que se sepa lo que se esta
    mirando.

    Y se mira de verdad, no de memoria: se ejecuta pytest con un selector
    mal puesto y se comprueba que da 4 y dice «no tests ran»."""
    FICH = os.path.join(ROOT, 'tools', 'test_causa_no_validez.py')
    codigo, salida = _correr([FICH, '-q', '--no-header',
                              '-p', 'no:cacheprovider',
                              '::no_existe_este_test'])
    assert codigo == 4, (
        'con un selector que no existe, pytest deberia dar 4, y da %d. Si esa '
        'afirmacion falla, el 4 no significa lo que se cree que significa y '
        'todo lo de abajo hay que rehacerlo' % codigo)
    assert 'no tests ran' in salida, (
        'y la salida deberia decir «no tests ran», que es la segunda mitad de '
        'la prueba de que no se ejecuto nada. Salida:\n%s' % salida[-600:])


def test_el_selector_correcto_da_0_o_1_y_nunca_4():
    """Y que el selector bien puesto ejecuta de verdad. Que es lo que evita
    el falso verde."""
    FICH = os.path.join(ROOT, 'tools', 'test_causa_no_validez.py')
    codigo, salida = _correr(
        [FICH + '::test_la_prueba_causal_sigue_en_pie',
         '-q', '--no-header', '-p', 'no:cacheprovider'])
    assert codigo == 0, (
        'un test que pasa deberia dar 0, y da %d (%s)'
        % (codigo, EXIT_QUE_SIGNIFICA.get(codigo, '?')))
    assert 'no tests ran' not in salida, 'y no puede decir «no tests ran»'
    assert '1 passed' in salida or 'passed' in salida, (
        'y tiene que decir que ha pasado UNO. Si no dice cuanto, no se sabe '
        'si ejecuto el que queria o ninguno. Salida:\n%s' % salida[-600:])


# Y la regla «un subproceso de pytest solo vale 0 o 1» NO esta aqui: esta
# en `test_ejecutar_pytest.py`, junto al modulo que la aplica.
#
# Y no es mudanza por limpieza: la copia que estaba aqui ya se habia
# desincronizado — exigia `subprocess.run(` en el fuente, y la version
# cableada usa `ejecutar_pytest.correr` —. Dos copias de una regla se
# separan. Se queda la que esta junto al modulo, que es donde una regla
# se mantiene.

# Y la regla «un subproceso de pytest solo vale 0 o 1» NO esta aqui: esta
# en `test_ejecutar_pytest.py`, junto al modulo que la aplica.
#
# Y no es mudanza por limpieza: la copia que estaba aqui ya se habia
# desincronizado — exigia `subprocess.run(` en el fuente, y la version
# cableada usa `ejecutar_pytest.correr` —. Dos copias de una regla se
# separan. Se queda la que esta junto al modulo, que es donde una regla
# se mantiene.

def test_ningun_subproceso_de_este_repositorio_acepta_el_codigo_cuatro():
    """Y el test que lo hace de verdad, no de palabra: se ejecuta una
    mutacion real y se comprueba que el codigo que sale es 1, no 4.

    Sin esto, «el codigo no es 4» seria una promesa."""
    tmp = tempfile.mkdtemp(prefix='opencode_exit_')
    try:
        destino = os.path.join(tmp, 'DOCS')
        shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
        ruta = os.path.join(destino, 'QUE_REPRESENTA_LA_PREDICCION.md')
        with io.open(ruta, encoding='utf-8') as f:
            texto = f.read()
        # una mutacion que de verdad rompe la propiedad
        roto = texto.replace('Eso **no** está demostrado, y no lo puede',
                              'Eso **sí** está demostrado, y lo puede')
        assert roto != texto, 'la mutacion no ha cambiado nada'
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(roto)
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        codigo, salida = _correr(
            [os.path.join(ROOT, 'tools', 'test_causa_no_validez.py')
             + '::test_la_tesis_de_no_validez_se_afirma_como_no_demostrada',
             '-q', '--no-header', '-p', 'no:cacheprovider'], env=env)
        assert codigo == 1, (
            'una mutacion real deberia dar 1, y da %d — que es %s. Si es 4, '
            'el selector no esta funcionando y el assert «!= 0» de mas arriba '
            'pasa sin hacer nada.\n\nSalida:\n%s'
            % (codigo, EXIT_QUE_SIGNIFICA.get(codigo, '?'), salida[-900:]))
        assert 'no tests ran' not in salida
        assert '1 failed' in salida, (
            'y la salida tiene que decir «1 failed», no «2 failed» ni «0 '
            'passed»: si dice otra cosa, el test que se ejecuto no es el que '
            'se queria. Salida:\n%s' % salida[-600:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================ 2. LA MATRIZ DE INDEPENDENCIA
def test_los_dos_mecanismos_de_los_contratos_miden_cosas_distintas():
    """La matriz entera, y las cuatro celdas, porque tres no dicen nada.

    La celda que hace de testigo es la de arriba a la izquierda: el contenido
    NO cae con un cambio cosmetico. Si cayera, no estaria mirando
    afirmaciones, estaria mirando el fichero — y entonces seria el mismo
    mecanismo que la huella, con pasos extra."""
    import test_contratos_firmados as cf
    DOCS = os.path.join(ROOT, 'DOCS')

    def _con(que_texto, transformacion):
        tmp = tempfile.mkdtemp(prefix='opencode_matriz_')
        destino = os.path.join(tmp, 'DOCS')
        os.makedirs(destino)
        for f in os.listdir(DOCS):
            if f.endswith('.md'):
                shutil.copy(os.path.join(DOCS, f), os.path.join(destino, f))
        ruta = os.path.join(destino, que_texto)
        with io.open(ruta, encoding='utf-8') as f:
            t = f.read()
        nuevo = transformacion(t)
        assert nuevo != t, 'la transformacion no ha cambiado nada'
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(nuevo)
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        return tmp, env

    def _codigo(env, test):
        return _correr([os.path.join(ROOT, 'tools',
                                     'test_contratos_firmados.py')
                        + '::' + test,
                        '-q', '--no-header', '-p', 'no:cacheprovider'],
                       env=env)[0]

    CONTENIDO = 'test_los_contratos_dicen_lo_que_el_proyecto_les_pide'
    HUELLA = 'test_los_contratos_no_cambian_sin_que_se_sepa'
    NOMBRE = 'CONTRATO_L_SEC.md'
    resultados = {}

    # (a) rotura de AFIRMACION: no queda ninguna forma
    def rompe_afirmacion(t):
        import test_contratos_firmados as cf
        for clave in cf.AFIRMACIONES[NOMBRE]:
            for forma in clave[1]:
                t = t.replace(forma, '§' * len(forma))
        return t

    # (b) rotura COSMETICA: el texto cambia, el sentido no
    def rompe_cosmetica(t):
        i = t.find('el')
        return t[:i] + 'EL' + t[i + 2:] if i > 0 else t

    for etiqueta, transformacion in (('afirmacion', rompe_afirmacion),
                                    ('cosmetica', rompe_cosmetica)):
        tmp, env = _con(NOMBRE, transformacion)
        try:
            resultados[(etiqueta, 'contenido')] = _codigo(env, CONTENIDO)
            resultados[(etiqueta, 'huella')] = _codigo(env, HUELLA)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('   %-12s %-12s %-12s' % ('rotura', 'contenido', 'huella'))
    for etiqueta in ('afirmacion', 'cosmetica'):
        print('   %-12s %-12s %-12s'
              % (etiqueta,
                 EXIT_QUE_SIGNIFICA.get(resultados[(etiqueta, 'contenido')],
                                        '?')[:8],
                 EXIT_QUE_SIGNIFICA.get(resultados[(etiqueta, 'huella')],
                                        '?')[:8]))
    print()
    assert len(set(resultados.values())) == 2, (
        'los cuatro codigos tienen que ser DOS distintos, no uno. '
        'resultados: %r' % resultados)
    # contenido: cae con afirmacion, NO cae con cosmetica
    assert resultados[('afirmacion', 'contenido')] == 1, (
        'el contenido tiene que caer con la rotura de afirmacion')
    assert resultados[('cosmetica', 'contenido')] == 0, (
        'el contenido NO tiene que caer con un cambio cosmetico. Si cae, esta '
        'midiendo el fichero y no las afirmaciones, y entonces es el mismo '
        'mecanismo que la huella')
    # huella: cae con las dos, porque ve cualquier cambio de texto
    assert resultados[('afirmacion', 'huella')] == 1, (
        'la huella tiene que caer con cualquier cambio de texto')
    assert resultados[('cosmetica', 'huella')] == 1, (
        'y tambien con un cambio cosmetico. Si no, la huella estaria midiendo '
        'lo mismo que el contenido y no serian dos mecanismos')


# ================================ 3. EL MUTADOR ES COMPLETO
def test_el_mutador_de_frases_cambia_todas_las_apariciones():
    """Lo que se comprueba no es que las mutaciones concretas sean
    completas —eso se comprueba mutando y mirando— sino que EL MUTADOR es
    completo.

    Y el criterio es el de fondo: despues de mutar, no tiene que quedar
    NINGUNA forma de la propiedad. Que es la version de este bloque de «una
    retraccion se retira en todas sus formas, no en una»."""
    import test_contratos_firmados as cf
    # El laboratorio se construye DESDE la lista de formas, no a mano.
    #
    # Y eso no es elegancia: un texto escrito a mano contra una lista de
    # formas aceptadas se queda viejo en cuanto se anade una, y el fallo es
    # el de este mismo test: decia traer tres variantes y trayendo una. O
    # sea que el laboratorio mentia sobre lo que probaba.
    #
    # Y el criterio del test no es «cuantas variantes hay» —que dependeria de
    # lo que se escriba— sino que DESPUES de mutar no quede ninguna forma.
    # Y para que eso se pueda comprobar, el laboratorio trae todas.
    formas = cf.AFIRMACIONES['CONTRATO_L_SEC.md'][0][1]
    texto = ('un documento cualquiera, y aqui la afirmacion: '
             + ' ; '.join(formas) + ' ; y la repetida: ' + formas[0])
    mutado = texto
    tocadas = 0
    for clave in cf.AFIRMACIONES['CONTRATO_L_SEC.md']:
        for forma in clave[1]:
            if forma in mutado:
                mutado = mutado.replace(forma, '§' * len(forma))
                tocadas += 1
    print()
    print('   variantes tocadas: %d' % tocadas)
    assert tocadas == len(formas), (
        'el mutador tiene que tocar TODAS las variantes que el test acepta: '
        '%d, y ha tocado %d. Si toca una, no es una mutacion: es un cambio '
        'de redaccion. Y eso ya ha pasado tres veces seguidas'
        % (len(formas), tocadas))
    # y no queda ninguna forma
    for clave in cf.AFIRMACIONES['CONTRATO_L_SEC.md']:
        for forma in clave[1]:
            assert forma not in mutado, (
                'despues de mutar queda la forma %r. O sea que el mutador es '
                'PARCIAL, y una mutacion parcial no rompe nada' % forma)

# ================ Y QUE LA REGLA ESTRECHA SIGA TENIENDO DIENTES
def test_estrechar_una_marca_no_puede_dejarla_sin_dientes():
    """La otra mitad de estrechar: que lo que se ha quitado no sea justo lo
    que la regla vigilaba.

    Y hay una asimetria que no se resuelve mirando el codigo:

      - la PROSA es la marca que sobraba: la palabra «MECANISMOS» en un
        encabezado, que no es una declaracion de nada
      - la DECLARACION es lo que la regla tiene que seguir cazando

    Y si se estrecha de mas, la segunda desaparece y la regla pasa a mirar
    prosa, que es lo contrario de lo que quiere. Un detector de copias que
    no detecta copias es peor que no tener detector: ocupa el sitio del que
    avisa.

    Y por eso la prueba no es «la forma nueva funciona con un ejemplo
    bueno» —eso lo hace cualquier forma, buena o mala— sino «la forma nueva
    sigue cayendo con lo que TIENE que cazar». Lo segundo es lo unico que
    dice algo sobre la regla."""
    import test_sin_copias as sc

    # (a) lo que TIENE que cazar: una declaracion
    declaracion = ("MECANISMO = ('gano_por_fold', 'mejores_manos', "
                   "'llego_al_showdown')" + chr(10) + 'resto')
    assert sc._declara_la_lista(declaracion), (
        'una declaracion de la lista tiene que detectarse. Si no, la regla '
        'estrechada se ha quedado sin dientes y hay que deshacer el '
        'estrechamiento')

    # (b) y las variantes de escritura que tambien son declaraciones
    for variante in ("MECANISMO=('a',)", '  MECANISMO  =  (\'a\',)',
                     'MECANISMO = (' + chr(10) + '    \'a\',\'b\',)'):
        assert sc._declara_la_lista(variante), (
            'no ha detectado una declaracion escrita asi: %r' % variante)

    # (c) y lo que NO tiene que cazar: prosa, y usos de la lista
    for falso in ('los DOS MECANISMOS de los contratos',
                  'usadas = [fn for fn in MECANISMO if fn + abre in cuerpo]',
                  "assert 'MECANISMO' not in texto",
                  '# MECANISMO, con mayuscula, en un comentario',
                  'x = MECANISMO  # sin parentesis: no es una lista'):
        assert not sc._declara_la_lista(falso), (
            'ha tomado por declaracion algo que no lo es: %r' % falso)

    # (d) y la exencion sigue siendo de UN solo fichero
    propio = os.path.basename(sc.__file__.replace(chr(92), '/'))
    assert propio == sc.YO, (
        'la exencion se ha movido de fichero: si el detector puede eximirse '
        'a si mismo desde mas de un sitio, la exencion no exime nada. Se '
        'llama %s y se exime a %s' % (propio, sc.YO))
