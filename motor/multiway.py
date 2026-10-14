# -*- coding: utf-8 -*-
import collections
"""`motor/multiway.py` — quien esta en el bote y quien PUEDE RESPONDER.

Vive en `motor/` y no en `tools/` porque lo usa el motor (revision_1
Tarea 3). Una regla que decide no puede vivir en un script de auditoria:
la copia se queda vieja y el motor acaba usando la otra.

EL CONTRATO ESTA EN `DOCS/CONTRATO_F72A.md`. Este modulo es su
implementacion; si las dos se separan, el contrato miente.

Las tres funciones que exporta este modulo son:

  - `posiciones_allin(hand)`       el dato `allin` unido a su posicion
  - `no_puede_actuar(hand, s)`     POR CALLE   -> set | None
  - `no_puede_actuar_en_instante(hand, s, i)`  POR INSTANTE -> set | None

Por que hay dos y no una
------------------------
Un all-in en la calle S NO significa "no puede actuar desde el principio de
S". Un jugador puede actuar antes de que otro se vaya all-in en esa misma
calle. Para clasificar UNA decision concreta hay que mirar el ORDEN de las
acciones, no la calle entera. Por calle es la aproximacion que se uso para
el 169; por instante es la que se firma.

El orden SÍ se puede reconstruir: `streets[k].actions` es una lista, y las
calles van en orden. Se recorre como una secuencia global con clave
`(indice_de_calle, indice_de_accion)`.
"""

# Orden con el que el recorder rellena `players[]`. El mapeo de `allin`
# (que guarda ids internos) a posicion depende de ESTE orden, asi que
# `test_contrato_orden_players` lo verifica contra el codigo del recorder.
PLAYER_IDS = ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')

ORDEN = ('preflop', 'flop', 'turn', 'river')
POSTFLOP = ('flop', 'turn', 'river')


# ---------------------------------------------------------------------------
# El dato: `allin` unido a su posicion
# ---------------------------------------------------------------------------
def contrato_orden_ok(hand):
    """True si `players[]` tiene el tamano que hace valido el mapeo.

    NO demuestra el orden: eso lo demuestra `test_contrato_orden_players`,
    que lee el codigo del recorder. Aqui solo se comprueba el tamano, que
    es lo que hace falta para que el indice no se salga.
    """
    return len(hand.get('players') or []) == len(PLAYER_IDS)


def posicion_de_id(hand, pid):
    """Id interno (`p1`...) -> `pos`. None si el mapeo no es valido."""
    if not contrato_orden_ok(hand):
        return None
    return (hand['players'][PLAYER_IDS.index(pid)] or {}).get('pos') or None


def posiciones_allin(hand):
    """Posiciones que se fueron all-in en la mano. `None` = sin evidencia.

    Los tres casos que devuelven `None`, y solo esos:

      1. el campo `allin` no esta (manos anteriores al recorder que lo
         escribia, H_0001..H_0073);
      2. `players[]` no mide lo que el mapeo necesita;
      3. el orden de `players[]` no es el de `PLAYER_IDS`.

    `None` NO es "nadie esta all-in". `allin: []` es lo que significa eso.
    """
    if not contrato_orden_ok(hand):
        return None
    if 'allin' not in hand:
        return None
    out = set()
    for pid in (hand.get('allin') or []):
        pos = posicion_de_id(hand, pid)
        if pos is None:
            return None
        out.add(pos)
    return out


# ---------------------------------------------------------------------------
# El orden de las acciones
# ---------------------------------------------------------------------------
def acciones(hand, street):
    return ((hand.get('streets') or {}).get(street) or {}).get('actions') or []


def secuencia(hand):
    """Lista de `(clave, pos, accion)` en orden cronologico.

    La clave `(indice_de_calle, indice_de_accion)` ordena las acciones de
    toda la mano sin ambiguedad, y es lo que permite comparar el instante
    de una decision con el instante de un all-in.
    """
    out = []
    for k, st in enumerate(ORDEN):
        for i, a in enumerate(acciones(hand, st)):
            if isinstance(a, dict) and a.get('pos'):
                out.append(((k, i), a.get('pos'), a.get('action')))
    return out


def ultima_accion(hand, pos):
    """Clave de la ultima accion de `pos`, o None si no tiene ninguna.

    Un jugador que se commitmenta no vuelve a actuar, asi que su ultima
    accion ES la del all-in. Es la deduccion que convierte el hecho de
    fin-de-mano que guarda `allin` en algo utilizable calle a calle.
    """
    clave = None
    for c, p, _ in secuencia(hand):
        if p == pos:
            clave = c
    return clave


def folds_hasta(hand, street):
    """Posiciones que han foldeado en alguna calle hasta `street` (incluida)."""
    corte = ORDEN.index(street)
    return {pos for clave, pos, acc in secuencia(hand)
            if acc == 'f' and clave[0] <= corte}


def hero_pos(hand):
    """Posicion del hero: el primer jugador con cartas conocidas.

    NO hay marca de hero en el JSON (`{active, cards, name, pos, stack}`).
    El proyecto lo reconoce por tener cartas, no por el nombre.
    """
    for p in (hand.get('players') or []):
        if (p.get('cards') or '').strip():
            return p.get('pos')
    return None


def heroes(hand):
    return [p.get('pos') for p in (hand.get('players') or [])
            if (p.get('cards') or '').strip()]


def instantes_decision(hand, street):
    """Indices de TODAS las acciones del hero en `street`, en orden.

    No solo la primera. Si el hero apuesta y despues tiene que decidir
    otra vez ante una resubida, esa segunda vez es OTRA decision, con otra
    situacion: entre una y otra puede haberse incorporated un rival al bote
    o haberse retirado otro. Contarlas como un solo punto escondia
    justamente los puntos donde mas rivales pueden responder.

    Medido: 110 calles de la ventana fiable tienen 2 o 3 acciones del hero.
    """
    hp = hero_pos(hand)
    if hp is None:
        return []
    return [i for i, a in enumerate(acciones(hand, street))
            if isinstance(a, dict) and a.get('pos') == hp]


def instante_decision(hand, street):
    """Indice de la PRIMERA accion del hero en `street`, o None.

    Atajo de `instantes_decision(...)[0]`. Se conserva porque describe el
    INICIO de la calle, que es lo que quiere el corte por calle. Para
    enumerar puntos de decision hay que usar `instantes_decision`.

    None = en esa calle el hero no tiene ninguna accion registrada: no hay
    decision que tomar. Ojo: si lo que tiene es un 'f', SI es una decision
    (decidir folding), y este indice lo devuelve igual.
    """
    inst = instantes_decision(hand, street)
    return inst[0] if inst else None


def contradiccion_allin_fold(hand):
    """Posiciones con evidencia CONTRADICTORIA: en `allin` y ademas con fold.

    Un jugador que se compromete no puede foldear despues. Si el registro
    dice las dos cosas, el campo `allin` y las acciones son incompatibles y
    NO se puede deducir el instante del compromiso: la ultima accion del
    jugador es justamente el fold, que no es el all-in.

    Es el caso de `H_0851`, y la causa de INC-002. MEDIDO: 1 de 138
    entradas de `allin` en la ventana fiable (0,7 %).

    Quien encuentre esto NO debe forzar una clasificacion: es
    `DESCONOCIDO` por la misma via que las manos sin campo.
    """
    ai = posiciones_allin(hand)
    if not ai:
        return set()
    folds = {pos for _clave, pos, acc in secuencia(hand) if acc == 'f'}
    return ai & folds


def en_bote(hand, street):
    """Jugadores que siguen en la mesa al terminar `street` (incluye hero)."""
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active')}
    return activos - folds_hasta(hand, street)


def en_bote_en_instante(hand, street, indice):
    """Jugadores en la mesa en el instante de la decision, hero incluido.

    Mismo criterio que `en_bote` pero CORTE en `(street, indice)`: un fold
    de esta misma calle posterior a la decision no cuenta. Hace falta
    porque si no, un hero que apuesta, ve una resubida y foldea aparece
    como "ya fuera" en su propia decision.

    NO descuenta los all-in: eso lo hace `no_puede_actuar_en_instante`, con
    el mismo corte. Las dos funciones son ortogonales a proposito, fold y
    commitment son hechos distintos y pueden pasar en el mismo instante.
    """
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active')}
    clave = (ORDEN.index(street), indice)
    fuera = {pos for c, pos, acc in secuencia(hand)
             if acc == 'f' and c < clave}
    return activos - fuera


# ---------------------------------------------------------------------------
# EL CONTRATO: no puede actuar
# ---------------------------------------------------------------------------
def _allin_usable(hand, ai):
    """`ai` si se puede deducir la calle de cada all-in; None si no.

    None cuando hay una contradiccion `allin` + fold posterior: la ultima
    accion de ese jugador es el fold, no el compromiso, asi que cualquier
    instante deducido de ella seria falso. Es el caso de `H_0851`, y es
    `DESCONOCIDO` por la misma via que las 73 manos sin campo.
    """
    if contradiccion_allin_fold(hand):
        return None
    for pos in ai:
        if ultima_accion(hand, pos) is None:
            return None
    return ai


def no_puede_actuar(hand, street):
    """Rivales en el bote que ya no pueden actuar. POR CALLE. set | None.

    Contrato completo en `DOCS/CONTRATO_F72A.md`.

    Aproximacion declarada: un all-in en `street` se considera incapacity
    desde el principio de `street`. Es mas grueso que la realidad — un
    rival puede actuar antes de que otro se vaya all-in en esa misma calle
    — y por eso existe `no_puede_actuar_en_instante`. Lo que se firma es
    el de INSTANTE; este se conserva para poder comparar.
    """
    ai = posiciones_allin(hand)
    if ai is None:
        return None
    ai = _allin_usable(hand, ai)
    if ai is None:
        return None
    fuera = set()
    for pos in ai:
        c = ultima_accion(hand, pos)
        if c[0] <= ORDEN.index(street):
            fuera.add(pos)
    return fuera


def no_puede_actuar_en_instante(hand, street, indice):
    """Lo mismo, pero en el instante `indice` de la decision de `street`.

    Un rival solo queda fuera si su all-in es ANTERIOR o IGUAL al instante
    de la decision. Si se commitmenta despues, todavia puede responder a
    lo que el hero acaba de apostar: es el caso que la regla por calle
    clasificaba mal.
    """
    ai = posiciones_allin(hand)
    if ai is None:
        return None
    ai = _allin_usable(hand, ai)
    if ai is None:
        return None
    clave = (ORDEN.index(street), indice)
    fuera = set()
    for pos in ai:
        c = ultima_accion(hand, pos)
        if c <= clave:
            fuera.add(pos)
    return fuera


def puede_responder(hand, street, indice):
    """Rivales que en ese instante siguen CAPACES de responder. set | None.

    `None` es lo que significa "no hay evidencia para clasificar". Quien
    lo reciba NO debe forzar HU ni MULTIWAY: sale del numerador y se cuenta
    aparte. Ver la seccion de politica del contrato.
    """
    hp = hero_pos(hand)
    if hp is None:
        return None
    fuera = no_puede_actuar_en_instante(hand, street, indice)
    if fuera is None:
        return None
    return (en_bote_en_instante(hand, street, indice) - fuera) - {hp}


# ---------------------------------------------------------------------------
# La decision completa
# ---------------------------------------------------------------------------
# Los tres estados que el contrato obliga a distinguir. `DESCONOCIDO` no es
# un valor por defecto: es la unica respuesta cuando falta la evidencia, y
# no se colapsa nunca en HU ni en MULTIWAY.
DESCONOCIDO = 'DESCONOCIDO'
HU = 'HU'
MULTIWAY = 'MULTIWAY'
SIN_DECISION = 'SIN_DECISION'


def clasificar_instante(hand, street, indice):
    """Clasifica UN punto de decision, en un instante concreto. dict.

    `clase` solo puede ser HU, MULTIWAY, DESCONOCIDO o SIN_DECISION.
    Un punto donde no se puede clasificar NO se convierte en un HU:
    se dice explicitamente.
    """
    hp = hero_pos(hand)
    if hp is None:
        return _dict(SIN_DECISION, None, 0, 0, True)
    # El hero se cuenta a si mismo hasta que su accion se ejecute: si lo
    # que hace es foldear, sigue estando en la mesa cuando decide.
    bote = en_bote_en_instante(hand, street, indice) | {hp}
    pueden = puede_responder(hand, street, indice)
    if pueden is None:
        return _dict(DESCONOCIDO, indice, len(bote), None, True)
    n = len(pueden)
    if n == 0:
        return _dict(SIN_DECISION, indice, len(bote), 0, False)
    return _dict(HU if n == 1 else MULTIWAY, indice, len(bote), n, False)


# ---------------------------------------------------------------------------
# LA METRICA DE F7.2
# ---------------------------------------------------------------------------
CLASES = ('HU', 'MULTIWAY', 'DESCONOCIDO', 'SIN_DECISION')

# Las dos clases que gobiernan la politica multiway. Las otras dos quedan
# fuera del numerador por contrato: no se sabe (DESCONOCIDO) o no hay con
# quien jugar (SIN_DECISION).
CLASES_POLITICA = ('HU', 'MULTIWAY')


def metrica_politica(hands):
    """La metrica de F7.2, medida sobre una lista de manos.

    Devuelve la TABLA CRUZADA (fold x clase) y, sobre ella, el
    denominador de politica y el numerador de MULTIWAY.

    El denominador EXCLUYE los folds del hero. Un fold es una decision
    real, pero no consulta equity: no hay nada que repartir entre HU y
    MULTIWAY para una politica multiway. Meterlo en el denominador
    inflaria el numerador con puntos que nunca producen una recomendacion.

    Vive aqui y no en el script de auditoria para que el script y los tests
    midan LO MISMO. Una copia en cada sitio es como vuelve el bug de la
    regla del raise.
    """
    tabla = collections.Counter()
    techo = 0
    for hand in hands:
        hp = hero_pos(hand)
        for r in puntos_decision_mano(hand):
            st, i = r['calle'], r['instante']
            fold = acciones(hand, st)[i]['action'] == 'f'
            tabla[('fold' if fold else 'no fold', r['clase'])] += 1
            if fold or r['clase'] != 'DESCONOCIDO':
                continue
            if posiciones_allin(hand) is not None:
                continue
            bote = en_bote_en_instante(hand, st, i) | ({hp} if hp else set())
            if len(bote) - 1 > 1:
                techo += 1

    numerador = tabla[('no fold', 'MULTIWAY')]
    denominador = sum(tabla[('no fold', c)] for c in CLASES_POLITICA)
    return {
        'tabla': tabla,
        'total': sum(tabla.values()),
        'denominador': denominador,
        'numerador': numerador,
        'porcentaje': (numerador / denominador * 100) if denominador else 0.0,
        'techo_desconocidos': techo,
        'techo': numerador + techo,
    }


def _dict(clase, instante, en_bote, pueden, sin_evidencia):
    return {'clase': clase, 'instante': instante, 'en_bote': en_bote,
            'pueden': pueden, 'sin_evidencia': sin_evidencia}


def clasificar_decision(hand, street):
    """PRIMERA decision del hero en la calle. Atajo de `puntos_decision`.

    Se conserva por comodidad. Para el denominador hay que usar
    `puntos_decision(hand)`, que devuelve una entrada por CADA accion del
    hero: una calle con dos acciones suyas son dos decisiones.
    """
    inst = instantes_decision(hand, street)
    if not inst:
        return _dict(SIN_DECISION, None, 0, 0, hero_pos(hand) is None)
    return clasificar_instante(hand, street, inst[0])


def puntos_decision(hand, street):
    """TODOS los puntos de decision del hero en una calle.

    Una lista de dict, uno por accion del hero. Vacia si el hero no
    aparece en esa calle.
    """
    return [clasificar_instante(hand, street, i)
            for i in instantes_decision(hand, street)]


def puntos_decision_mano(hand, calles=None):
    """TODOS los puntos de decision del hero en la mano.

    Este es el enumerado que usan el inventario y el auditor: el punto
    de decision es la ACCION del hero, no la calle.
    """
    out = []
    for st in (calles or POSTFLOP):
        for r in puntos_decision(hand, st):
            r = dict(r, calle=st)
            out.append(r)
    return out
