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

import ejecutar_pytest as ep
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


def test_el_exit_code_4_significa_que_no_se_ha_ejecutado_nada():
    """La precondicion de todo lo demas: que se sepa lo que se esta
    mirando.

    Y se mira de verdad, no de memoria: se ejecuta pytest con un selector
    mal puesto y se comprueba que da 4 y dice «no tests ran»."""
    FICH = os.path.join(ROOT, 'tools', 'test_causa_no_validez.py')
    # Y por `ep.crudo`, no por `ep.correr`: este test COMPRUEBA que el 4
    # significa «no se ha ejecutado nada», y `correr` corta ese codigo a
    # proposito porque es el que hace pasar en verde a un `!= 0`. El test
    # que verifica la regla no puede usar la regla.
    #
    # Y que aqui aparezca `crudo` y no en ningun otro sitio es lo que hace
    # que la excepcion sea visible en vez de estar repartida.
    codigo, salida = ep.crudo(FICH, 'no_existe_este_test', cwd=ROOT)
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
    codigo, salida = ep.correr(FICH, 'test_la_prueba_causal_sigue_en_pie',
                               cwd=ROOT)
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

# Y el comentario iba DUPLICADO dos veces. Lo puso un parche que no
# comprobo que no estuviera ya, que es el mismo fallo del ancla que se
# cumplia. Un comentario repetido no rompe nada, y por eso nadie lo ve.
def test_ningun_subproceso_de_este_repositorio_acepta_el_codigo_cuatro():
    """Una mutacion REAL da codigo 1, y no 4.

    Y esto que era una comprobacion PROPIA —`ep.correr()`, `codigo == 1` y un
    `1 failed` en la salida— ahora es `ep.afirmar_caida()`. Que es lo que R2,
    punto 3, pedia, y la razon es de mantenimiento y no de estilo:

        dos comprobaciones del mismo hecho, una mas fuerte que la otra, y la
        debil en el sitio donde se acaba de decidir que la debilidad importa

    `afirmar_caida` exige ademas la linea `FAILED fichero::test`, que esta
    comprobacion no exigia. Y por eso la debil era peor que no tenerla: son
    dos sitios que pueden divergir, y divergen. En un bloque cuyo objetivo es
    que un error de importacion no se haga pasar por una mutacion detectada,
    tener la comprobacion debil DUPLICADA es contraproducente.

    Y sin esto, «el codigo no es 4» seria una promesa."""
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
        ep.escribir_documento(ruta, roto, que='la tesis afirmada')
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        ep.afirmar_caida(
            os.path.join(ROOT, 'tools', 'test_causa_no_validez.py'),
            'test_la_tesis_de_no_validez_se_afirma_como_no_demostrada',
            env=env, cwd=ROOT,
            cuando='una mutacion real deberia dar codigo 1, y no lo da. Si '
                    'fuera un 4 —«no se ha ejecutado nada»— el selector no '
                    'esta funcionando, y un `!= 0` pasaria sin hacer nada. Y '
                    'si fuera un 1 sin linea `FAILED fichero::test`, el fallo '
                    'no es de este test sino de la coleccion, que da el '
                    'mismo codigo.')
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

    def _con(que_texto, transformacion, etiqueta):
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
        # Y por `escribir_documento`, que la MARCA como escrita y sin probar.
        #
        # Y este fichero es el que hace la matriz de cuatro celdas —la que
        # dice que el contenido y la huella son dos mecanismos— y escribia un
        # DOCS mutado CUATRO veces sin marcar ninguna. O sea que la
        # comprobacion que mas importa de este fichero era la unica que
        # ningun invariante vigilaba.
        #
        # Y no es teorico: en el bloque anterior `test_tareas_r1.py` escribio
        # una mutacion y la sobrescribio sin ejecutar nada, y dio `8 passed`.
        # Si eso hubiera pasado aqui, esta matriz habria dado cuatro celdas
        # —cuatro codigos de salida— sin haber mirado un solo documento.
        ep.escribir_documento(ruta, nuevo,
                              que='«%s» %s' % (que_texto, etiqueta))
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        return tmp, env

    def _resultado(env, test, debe_caer, etiqueta):
        """El RESULTADO COMPLETO de una celda, no solo su codigo.

        Y R2, punto 2, lo dice bien: «no afirmo que las cuatro celdas
        actuales sean falsas; senalo que su fuerza probatoria depende de otra
        funcion». Dependia de que `correr()` cortara el 4, y eso es una
        propiedad de otra pieza, en otro fichero.

        Y la consecuencia: si `correr()` dejara pasar un 4 —o si alguien lo
        cambiara sin querer— esta matriz daria cuatro celdas y no se
        enteraria. Una comprobacion que depende de otra tiene que decirlo, o
        fallara cuando la otra cambie sin que nadie mire.

        Asi que cada celda usa la puerta que le toca:

            debe caer -> `afirmar_caida`, que exige codigo 1 Y que la salida
                         nombre ESE test como FAILED
            no debe   -> `afirmar_verde`, que exige codigo 0 Y el RECUENTO
                         de los que han pasado

        Y eso no es solo mas fuerte: es MENOS codigo. Las cuatro aserciones
        sobre `== 1` y `== 0` desaparecen, porque las hace la puerta comun,
        que ya dice QUE fallo y no solo CUANTO."""
        ruta_contratos = os.path.join(ROOT, 'tools',
                                      'test_contratos_firmados.py')
        if debe_caer:
            ep.afirmar_caida(
                ruta_contratos, test, env=env, cwd=ROOT,
                cuando='«%s» deberia CAER con la rotura «%s» y no cae. O '
                        'sea que este mecanismo no detecta la rotura, y la '
                        'matriz que dice que el contenido y la huella son '
                        'dos mecanismos esta midiendo una sola cosa.'
                        % (test, etiqueta))
            return 1
        ep.afirmar_verde(ruta_contratos, test, env=env, cwd=ROOT)
        return 0

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

    # (b) rotura COSMETICA: el texto cambia, el sentido no.
    #
    # Y con LIMITES DE PALABRA, como la de `test_tareas_r1.py`. MEDIDO: el
    # primer `el` de este contrato esta en el indice 237 y ES una palabra
    # completa, o sea que `find('el')` hoy es cosmetico de verdad y la
    # matriz es correcta. No hay cifra que mover.
    #
    # Lo que se cambia es la CASUALIDAD. Y con `find`, si el primer `el`
    # cayera dentro de una palabra —cambiar «ello» por «Ello», que rompe el
    # documento— la mutacion dejaria de ser cosmetica, el contenido caeria,
    # y las cuatro celdas darian cuatro unos: una matriz que demuestra lo
    # contrario de lo que afirma. Un fallo SILENCIOSO y en la direccion
    # contraria, que es la peor forma de tener un detector roto.
    #
    # Y que la de `test_tareas_r1.py` se corrigiera y esta no, es el mismo
    # descuido dos veces: arreglar un sitio y dejar el otro gemelo.
    def rompe_cosmetica(t):
        m = re.search(r'\bel\b', t)
        assert m, (
            'CONTRATO_L_SEC.md tiene que contener la palabra «el» completa, '
            'y no la tiene. Si el documento ha cambiado, esta mutacion hay '
            'que rehacerla, y es justo lo que comprueba')
        nuevo = t[:m.start()] + 'EL' + t[m.end():]
        # Y que la sustitucion no haya pegado una palabra: es la comprobacion
        # que `find` no hacia y que hacia que no fuera cosmetica.
        assert not re.search(r'\wEL\b', nuevo), (
            'la sustitucion ha producido una palabra pegada: %r. O sea que '
            '«el» no estaba como palabra, y cambiarla no es cosmetico'
            % nuevo[max(0, m.start() - 8):m.start() + 12])
        return nuevo

    for etiqueta, transformacion in (('afirmacion', rompe_afirmacion),
                                    ('cosmetica', rompe_cosmetica)):
        tmp, env = _con(NOMBRE, transformacion, etiqueta)
        try:
            # Y la huella tiene que caer SIEMPRE —ve cualquier cambio de
            # texto— mientras que el contenido solo cae con la afirmacion.
            resultados[(etiqueta, 'contenido')] = _resultado(
                env, CONTENIDO, etiqueta == 'afirmacion', etiqueta)
            resultados[(etiqueta, 'huella')] = _resultado(
                env, HUELLA, True, etiqueta)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # Y lo escrito, probado. Las cuatro celdas son cuatro DOCS mutados, y
    # los cuatro tienen que haber llegado a un test. Si alguno no ha
    # llegado, su celda no dice nada —el codigo habria salido de un 4, o de
    # nada— y entonces la matriz no es una matriz: son cuatro numeros.
    pendientes = ep.sin_probar()
    assert not pendientes, (
        'la matriz ha escrito %d documento(s) mutado(s) y estos no han '
        'llegado a ningun test:\n%s\n\nUna celda sin ejecucion no es una '
        'medida: es un codigo de salida.'
        % (len(pendientes),
           chr(10).join('   - %s' % que for que, _ in pendientes)))
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
    # Y las CUATRO celdas se leen, que es distinto de comprobarse. Lo que las
    # hace caer o pasar lo hace la puerta comun, que ademas mira la salida; y
    # una matriz que no lee sus propios numeros no dice nada, aunque los
    # numeros se hayan comprobado bien.
    #
    # Comprobacion y lectura son cosas distintas, y una sin la otra no vale.
    ESPERADO = {('afirmacion', 'contenido'): 1,
                ('afirmacion', 'huella'): 1,
                ('cosmetica', 'contenido'): 0,
                ('cosmetica', 'huella'): 1}
    for celda, esperado in sorted(ESPERADO.items()):
        assert resultados[celda] == esperado, (
            'la celda %s deberia dar %d y da %d.\n\nY no con el codigo: con '
            'la SALIDA, que es lo que distingue un test caido de un error de '
            'coleccion. La matriz entera dice %r'
            % (celda, esperado, resultados[celda], resultados))
    assert len(set(resultados.values())) == 2, (
        'las cuatro celdas tienen que ser DOS valores distintos, no uno. '
        'resultados: %r' % resultados)


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
