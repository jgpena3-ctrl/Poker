# -*- coding: utf-8 -*-
"""El escaner de frases retiradas, en UN solo sitio.

POR QUE ESTO ES UN MODULO Y NO UNA FUNCION DE UN TEST

Habia dos copias, en `test_retraccion_y_auc.py` y en
`test_cuarta_correccion.py`, y divergieron. Una miraba linea a linea y
encontraba «78» dentro de «378»; la otra normalizaba los espacios por
documento entero y se comia las citas. Y las dos tenian su propia lista de
frases retiradas, que es exactamente lo que no puede tener dos sitios.

La copia dentro de un test no es un problema de estilo: es que cuando la
regla cambie, cambiara en un sitio y el otro seguira con la regla vieja
diciendo que el documento esta mal. O peor: las dos pasan, y la regla ya no
existe en ningun sitio.

QUE HACE, Y LAS TRES COSAS QUE TIENE QUE HACER BIEN

1. DISTINGUIR AFIRMAR DE CITAR. Una retraccion tiene que citar lo que
   retira. Sin la cita no se ve que se corrigio, y parece que siempre se
   dijo lo nuevo. Lo que no puede es AFIRMARLO. Y la diferencia no es el
   vocabulario: una cita va en bloque `>`.

2. MIRAR EL TEXTO UNIDO, NO LA LINEA. Un documento esta hard-wrapped, y
   `no esta\\nimplementada` es `no esta implementada`. Una frase partida
   entre dos lineas no es una frase que nadie escribio asi.

3. ENTENDER LA NEGACION. «No «de una sola clase»: ninguna» CONTIENE la
   frase retirada y la NIEGA. Un escaner que solo busca la palabra senala
   justo la frase que hace la correccion. Y eso es peor que no mirar: hace
   que la gente deje de mirar.

Y un cuarto, que resulto del primer fallo real:

4. LOS NUMEROS SON TOKENS, NO SUBCADENDRAS. Buscar `78` encuentra `378`, y
   `378` es un numero legitimo y distinto: es el total de cortes con accion
   jugada bajo el corte en la primera. Un escaner que no distingue eso
   senala una linea correcta y obliga a corregir un numero que esta bien.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'DOCS')

# Los tres documentos que llevan las cifras de la poblacion B.
LOS_TRES = ('LIMITACION_PREFLOP_AUC.md', 'REPRESENTATIVIDAD_23.md',
            'FASE_D_BLOQUEADA.md')


def leer(nombre):
    with io.open(os.path.join(DOCS, nombre), encoding='utf-8') as f:
        return f.read()


def cita(linea):
    """¿Esta linea es una cita? Lo unico que lo marca es el `>` inicial."""
    return linea.lstrip().startswith('>')


# ------------------------------------------------------- los dos alcances
# POLARIDAD: de la ORACION. Un «no» de una oracion no negate las otras tres
# de la linea, asi que se aplica solo a la oracion que envuelve a la frase.
POLARIDAD = ('no ', 'nunca', 'tampoco', 'tampien', 'tampién', 'ningun',
             'ninguna', 'ninguno', 'ni con', 'ya no')

# MARCA DE RETRACCION: del PARRAFO. Una retraccion escribe lo que retira en
# el parrafo entero, y a veces en el que sigue —«Decía:» queda en la
# oracion anterior— y a veces en el mismo, con dos puntos dentro de la frase
# retirada: «la población «no está vacía: está bloqueada»».
#
# Y NO es la palabra suelta. «Retirada» aparece en prosa corriente —«la
# cifra retirada»— sin anunciar ninguna retraccion, y con ella en la lista
# un documento que describe una cifra vieja se tomaba por un parrafo de
# retraccion y la frase dejaba de contar. Son formas de ANUNCIO: alguien
# esta retirando algo.
MARCAS_RETRACCION = ('se retira', 'se retiro', 'se ha retirado',
                     'retirada entera', 'retirado entero', 'retira la',
                     'retira el', 'retiran', 'decía', 'decia', 'dije',
                     'antes decía', 'antes decía', 'se escribió',
                     'se escribio', 'tabla rehecha', 'tabla nueva',
                     'cuarta corrección', 'cuarta correccion',
                     'antes afirmaba', 'dice así', 'dice as',
                     'antes ponía', 'antes ponia')

VEREDICTOS_NEGATIVOS = ('\u2717', 'x', 'X', 'NO', 'No')


def Polaridad(texto):
    """¿Este trozo de texto va en negativo? (polaridad, no retraccion)

    Tres formas, y las tres estan en los documentos:

      - una negacion: «no es de una sola clase: ninguna»
      - una tabla con veredicto negativo: `| una sola clase | \u2717 | ... |`
      - una retraccion en linea: «se retiró», «decía», «antes»

    Recibe una ORACION cuando quien la llama es `afirmada_sin_negar`, y una
    LINEA cuando quien la llama es un test. Las dos cosas funcionan, y no hay
    recorte de longitud a proposito: el recorte es lo que hacia fallar. Lo
    que delimita el alcance es quien llama.
    """
    b = texto.lower().lstrip('> ')
    for neg in POLARIDAD:
        if neg in b:
            return True
    for marca in MARCAS_RETRACCION:
        if marca in b:
            return True
    if texto.lstrip().startswith('|'):
        celdas = [c.strip() for c in texto.strip().strip('|').split('|')]
        # el veredicto es la segunda celda en las tablas de este proyecto
        for c in (celdas[1:2] or celdas[:1]):
            if c in VEREDICTOS_NEGATIVOS:
                return True
    return False


# Alias, y con este nombre para que un test que lo lea sepa que es lo que
# pense todo el mundo.
niega = Polaridad


def parrafo_que_rodea(lineas, num):
    """El parrafo —bloque separado por lineas en blanco— que contiene `num`."""
    ini = num - 1
    while ini > 0 and lineas[ini - 1].strip():
        ini -= 1
    fin = num - 1
    while fin < len(lineas) - 1 and lineas[fin].strip():
        fin += 1
    return '\n'.join(lineas[ini:fin + 1])


def en_retiracion(texto, num):
    """¿La linea `num` esta dentro de un parrafo que RETIRA algo?

    Es lo que permite citar lo retirado en linea, dentro del parrafo que lo
    retira, sin que el detector lo tome por una afirmacion.
    """
    p = parrafo_que_rodea(texto.split('\n'), num).lower()
    for marca in MARCAS_RETRACCION:
        if marca in p:
            return True
    return False


# ----------------------------------------------- afirmar, con numero de linea
def afirmadas(texto):
    """[(numero_de_linea, texto_normalizado)] de lo que NO es cita."""
    return [(i, re.sub(r'\s+', ' ', l).strip().lower())
            for i, l in enumerate(texto.split('\n'), 1) if not cita(l)]


def _unido(pares):
    """`(texto_unido, [(offset_de_cada_linea, numero_de_linea)])`."""
    trozos, offsets, cursor = [], [], 0
    for _i, t in pares:
        trozos.append(t)
        offsets.append((cursor, _i))
        cursor += len(t) + 1
    return ' '.join(trozos), offsets


def citada(texto, frase):
    """¿La frase aparece CITADA, o sea en una linea que empieza por `>`?

    Una retraccion tiene que citar lo que retira. Sin la cita no se ve que se
    corrigio, y parece que siempre se dijo lo nuevo.
    """
    baja = frase.lower()
    return any(cita(l) and baja in l.lower() for l in texto.split('\n'))


def _oracion_que_rodea(unido, pos):
    """La oracion del texto que contiene la posicion `pos`.

    Delimitadores: punto, punto y coma, dos puntos, exclamacion,
    interrogacion y salto de linea.

    Y el motivo de mirar la oracion y no la linea:

        Y **no es un arreglo**, y esto hay que decirlo. Lo que B1 hace es
        **sustituir una poblacion por otra**.

    La oracion de «sustituye» no esta negada. La LINEA empieza con «no es»,
    y si se mira la linea el detector dice que el documento esta mal cuando
    esta bien. Una linea de Markdown puede tener cuatro oraciones, y la
    polaridad de una no es la de las otras tres.
    """
    corte = max(unido.rfind(c, 0, pos) for c in ('.', ';', ':', '!', '?', '\n'))
    fin = pos
    while (fin < len(unido)
           and unido[fin] not in ('.', ';', ':', '!', '?', '\n')):
        fin += 1
    return unido[corte + 1:fin]


def _coincidencias(texto, frase):
    """[(numero_de_linea, oracion_que_la_rodea)] de cada vez que `frase`
    aparece AFIRMADA en `texto`.

    Es el emparejamiento, y no el juicio: ni mira la polaridad ni la
    retraccion. Solo hace las dos cosas que hay que hacer bien una vez:

      - **los numeros son tokens.** Buscar `78` encuentra `378`, y `378` es
        un numero legitimo y distinto. Con limites de palabra, no.
      - **el texto se mira UNIDO**, no linea a linea. Un documento esta
        hard-wrapped, y `no esta\nimplementada` es `no esta implementada`.
        Una frase partida entre dos lineas no es una frase que nadie
        escribio asi.

    Las lineas de cita se APARTAN antes de unir. Unir primero y filtrar
    despues no vale: al unir, la cita y la afirmacion se vuelven una sola
    linea, y el detector deja de distinguir las dos cosas —que es el error
    entero de este escaner—.
    """
    pares = afirmadas(texto)
    if not pares:
        return []
    unido, offsets = _unido(pares)
    if re.fullmatch(r'[\d.,% ]+', frase.strip()):
        patron = r'(?<![\d.,])%s(?![\d.,])' % re.escape(frase.strip())
    else:
        patron = re.escape(frase.lower())

    salida = []
    for m in re.finditer(patron, unido):
        pos = m.start()
        linea = offsets[0][1]
        for off, num in offsets:
            if off <= pos:
                linea = num
            else:
                break
        salida.append((linea, _oracion_que_rodea(unido, pos)))
    return salida


def afirmada(texto, frase):
    """Lineas donde `frase` se AFIRMA, o sea no se cita. Vacio si no.

    Para los numeros, `frase` se busca como TOKEN: con limites de palabra,
    para que `78` no encuentre `378`. Para el resto, como subcadena, que es
    lo que se quiere para frases.
    """
    return sorted({n for n, _oracion in _coincidencias(texto, frase)})


# Si la frase buscada CONTIENE polaridad, no se le aplica el filtro de
# polaridad, porque la frase ya la lleva:
#
#     «no suficiente»  es una afirmacion sobre una cosa que NO basta
#     «no implementada» es una afirmacion sobre una cosa que NO se hace
#
# Y el filtro las descartaba por el «no» —que es justo lo que las hace ser las
# frases que se buscan—. Con eso, un detector que exige «no está
# implementada» en un documento no lo encuentra nunca, y parece un fallo del
# documento cuando el documento esta bien.
#
# Lo que sigue vigilando a esas frases es `en_retiracion()`, que es lo que
# tiene que vigilarlas: una frase retirada puede aparecer en linea dentro
# del parrafo que la retira, y con dos puntos dentro de si misma.
def lleva_polaridad(frase):
    b = frase.lower()
    return any(neg in b for neg in POLARIDAD)


def afirmada_sin_negar(texto, frase):
    """Como `afirmada()`, pero saltandose las que NIEGAN o están RETIRADAS.

    Para las frases retiradas. «No «de una sola clase»: ninguna» contiene la
    frase y la niega, y hay que poder decir que el documento la ha correcto.

    Dos alcances, y son distintos a proposito:

      - la **polaridad** es de la ORACION. Un «no» de una oracion no negate
        las otras tres de la linea, asi que se aplica solo a la oracion que
        envuelve a la frase.

      - una **marca de retraccion** es del PARRAFO. Una retraccion escribe
        lo que retira en el parrafo entero, y a veces dentro de la frase
        retirada hay dos puntos: «la poblacion «no esta vacia: esta
        bloqueada»». Con el corte por oracion, la segunda mitad se queda sin
        la negacion y parece una afirmacion.

    Y si la frase buscada CONTIENE polaridad —«no suficiente», «no
    implementada»— no se filtra por polaridad, porque la frase ya la lleva.
    Ver `lleva_polaridad()`. Lo que la vigila entonces es la retraccion del
    parrafo, que es lo que tiene que vigilarla.
    """
    # Las DOS preguntas se hacen siempre. Una version anterior hacia un atajo
    # —«si la frase lleva polaridad, saltate el filtro»— y con eso se
    # perdia `en_retiracion()`, que es lo unico que vigila las frases
    # retiradas que llevan polaridad dentro: «no esta vacia: esta
    # bloqueada». El atajo arreglaba una cosa rompiendo la otra.
    con_polaridad = lleva_polaridad(frase)
    fuera = set()
    for linea, oracion in _coincidencias(texto, frase):
        if not oracion.strip():
            continue
        # 1. POLARIDAD, de la oracion —salvo que la frase la traiga ella
        if not con_polaridad and Polaridad(oracion):
            continue
        # 2. RETRACCION, del parrafo: siempre
        if en_retiracion(texto, linea):
            continue
        fuera.add(linea)
    return sorted(fuera)


# ------------------------------------------------------ el fichero entero
def frases_retiradas(nombre):
    """(frases_retiradas_afirmadas, frases_retiradas_citadas) de un
    documento. Vacio en la primera si el documento esta bien."""
    texto = leer(nombre)
    malas, citadas = [], []
    for frase, _ctx in RETIRADAS:
        for i in afirmada_sin_negar(texto, frase):
            linea = texto.split('\n')[i - 1]
            # una cifra suelta es ruido; lo que importa es que se afirme
            # como una poblacion
            if re.fullmatch(r'[\d.,% ]+', frase.strip()):
                if not re.search(r'(poblaci|observacion|observaciones'
                                 r'|etiqueta|victori|derrota|total|corte)',
                                 linea, re.IGNORECASE):
                    continue
            malas.append((i, frase, linea.strip()[:64]))
        if citada(texto, frase):
            citadas.append(frase)
    return malas, citadas


# Las frases y cifras que la cuarta correccion retira. El segundo elemento es
# el contexto: por que se retiraba. Se escribe para que el mensaje de fallo
# diga algo util si alguien anade una frase nueva sin entenderla.
RETIRADAS = (
    ('78', 'positivas preflop: son 0'),
    ('270', 'observaciones del corte en la primera: son 67'),
    ('216', 'victorias del corte en la primera: son 20'),
    ('236', 'cortes postflop: son 48 observaciones'),
    ('131', 'total con la replica: son 48'),
    ('103', 'positivas globales con la replica: son 20'),
    ('arreglar el 1', 'la separacion en dos problemas: es uno'),
    ('sesgo de la selección', 'la separacion en dos problemas: es uno'),
    ('una sola clase', 'la poblacion no es de una clase: es vacia'),
    ('dos problemas', 'es UN problema, y su enunciado cabe en una frase'),
    ('orden de filtros', 'el orden de filtros no es la causa: a el no llega'
                         ' ninguna de las 83'),
    ('quedan separados', 'es UN problema'),
    ('que no son uno', 'es UN problema'),
    ('cero derrotas', 'no hay observaciones, ni positivas ni negativas'),
    ('están bloqueada', 'no esta bloqueada: no tiene etiquetas'),
    ('no está vacía: está bloqueada', 'no esta bloqueada'),
    ('población no está vacía', 'la poblacion esta vacia'),
)


if __name__ == '__main__':
    print('=' * 78)
    print('FICHAS RETIRADAS AFIRMADAS FUERA DE CITA')
    print('=' * 78)
    vacio = True
    for n in LOS_TRES:
        malas, citadas = frases_retiradas(n)
        print()
        print('--- %s' % n)
        if not malas:
            print('    ninguna  (citadas: %d de %d)'
                  % (len(citadas), len(RETIRADAS)))
            continue
        vacio = False
        for i, f, l in malas:
            print('    %4d  [%s]  %s' % (i, f, l))
    print()
    print('RESULTADO:', 'limpio' if vacio else 'HAY AFIRMACIONES RETIRADAS')