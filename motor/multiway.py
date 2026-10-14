# -*- coding: utf-8 -*-
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


def instante_decision(hand, street):
    """Indice de la PRIMERA accion del hero en `street`, o None.

    None = en esa calle el hero no tiene ninguna accion registrada: no hay
    decision que tomar. Ojo: si lo que tiene es un 'f', SI es una decision
    (decidir folding), y este indice lo devuelve igual.
    """
    hp = hero_pos(hand)
    if hp is None:
        return None
    for i, a in enumerate(acciones(hand, street)):
        if isinstance(a, dict) and a.get('pos') == hp:
            return i
    return None


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
    fuera = set()
    for pos in ai:
        c = ultima_accion(hand, pos)
        if c is None:
            return None
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
    clave = (ORDEN.index(street), indice)
    fuera = set()
    for pos in ai:
        c = ultima_accion(hand, pos)
        if c is None:
            return None
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


def clasificar_decision(hand, street):
    """Clasifica UN punto de decision del hero. dict, no tupla.

    Devuelve: `clase`, `instante`, `en_bote`, `pueden`, `sin_evidencia`.

    `clase` solo puede ser HU, MULTIWAY, DESCONOCIDO o SIN_DECISION. Un
    punto donde el hero no decide (ya foldeo, o la calle no tiene su
    accion) NO es un punto de decision: se dice explicitamente en vez de
    contarlo como un HU cualquiera.
    """
    hp = hero_pos(hand)
    if hp is None:
        return {'clase': SIN_DECISION, 'instante': None, 'en_bote': 0,
                'pueden': 0, 'sin_evidencia': True}
    i = instante_decision(hand, street)
    if i is None:
        return {'clase': SIN_DECISION, 'instante': None, 'en_bote': 0,
                'pueden': 0, 'sin_evidencia': False}
    # El hero se cuenta a si mismo hasta que su accion se ejecute: si lo
    # que hace es foldear, sigue estando en la mesa cuando decide.
    bote = en_bote_en_instante(hand, street, i) | {hp}
    pueden = puede_responder(hand, street, i)
    if pueden is None:
        return {'clase': DESCONOCIDO, 'instante': i, 'en_bote': len(bote),
                'pueden': None, 'sin_evidencia': True}
    n = len(pueden)
    if n == 0:
        return {'clase': SIN_DECISION, 'instante': i, 'en_bote': len(bote),
                'pueden': 0, 'sin_evidencia': False}
    return {'clase': HU if n == 1 else MULTIWAY, 'instante': i,
            'en_bote': len(bote), 'pueden': n, 'sin_evidencia': False}