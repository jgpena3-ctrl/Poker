# -*- coding: utf-8 -*-
"""P0-4 — Contrato de procedencia y compatibilidad de modelos (sombra).

Este módulo no cambia modelos, priors, tablas ni recomendaciones. Define un
envelope común para describir la procedencia de cada componente y permite
auditar mezclas silenciosas entre artefactos históricos y modelos
reconstruidos desde la base actual.

Reglas de honestidad:

  - Un campo que no está en el artefacto queda en ``None``. No se rellena por
    inferencia.
  - Un artefacto histórico identificado por hash no se convierte en
    "compatible con la base actual": sigue siendo histórico y su reproducción
    está declarada como no verificada por B1.
  - La ventana de 877 se identifica con el hash de líneas seleccionadas que
    declara ``data/calibration_window.json``; si la base o el corte no
    coinciden, el hash de ventana queda en ``None``.
  - Modo sombra: se registra qué se habría bloqueado, pero no se bloquea.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from ._procedencia import arbol_sucio, code_commit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
CALIBRATION_WINDOW_PATH = 'data/calibration_window.json'

# ---------------------------------------------------------------------------
# Estados y orígenes
# ---------------------------------------------------------------------------

VERIFIED = 'verified'
PARTIAL = 'partial'
UNKNOWN = 'unknown'
INCOMPATIBLE = 'incompatible'
HISTORICAL = 'historical'
REBUILT = 'rebuilt'

ORIGIN_REBUILT = 'rebuilt_from_current_base'
ORIGIN_HISTORICAL = 'historical_derivative'
ORIGIN_STATIC = 'static_table'
ORIGIN_UNKNOWN = 'unknown'

# Estados de clasificación exigidos para herramientas auxiliares.
CLASS_HISTORICAL_ONLY = 'historical_only'
CLASS_CURRENT_ONLY = 'current_only'
CLASS_EXPLICIT_MODES = 'explicit_modes'
CLASS_NOT_SUITABLE = 'not_suitable'
CLASS_UNKNOWN = 'unknown'

# Versiones de contrato. No se deducen por fecha: se declaran aquí y los
# artefactos históricos quedan como ``None`` porque son anteriores a P0-1/P0-2.
CLASSIFICATION_CONTRACT_VERSION = 'P0-1 shadow (dd80689)'
ELIGIBILITY_POLICY_VERSION = 'P0-2 shadow (717d2ea)'


# ---------------------------------------------------------------------------
# Utilidades de solo lectura
# ---------------------------------------------------------------------------

def _git(*args):
    try:
        return subprocess.check_output(
            ['git'] + list(args), cwd=ROOT,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def _sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _hand_hash():
    return _sha256_file(os.path.join(ROOT, 'data', 'hands_db.jsonl'))


def _reliable_hands():
    from .learn import RELIABLE_HANDS, manos_excluidas
    return RELIABLE_HANDS - len(manos_excluidas())


def _window_facts():
    """Hechos declarados en ``data/calibration_window.json`` (sin inferir)."""
    cw = _json(os.path.join(ROOT, CALIBRATION_WINDOW_PATH))
    if not isinstance(cw, dict):
        return {
            'present': False,
            'calibration_window_status': None,
            'calibration_provenance_status': None,
            'declared_base_sha256': None,
            'declared_lines_total': None,
            'selected_count': None,
            'selected_lines_sha256': None,
            'excluded_count': None,
            'window_rule': None,
            'canonical_hashes': {},
            'derivatives_status': None,
        }
    base = cw.get('base') or {}
    win = cw.get('window') or {}
    der = cw.get('derivatives') or {}
    return {
        'present': True,
        'calibration_window_status': cw.get('status'),
        'calibration_provenance_status': cw.get('provenance_status'),
        'declared_base_sha256': base.get('sha256'),
        'declared_lines_total': base.get('lines_total'),
        'selected_count': win.get('selected_count'),
        'selected_lines_sha256': win.get('selected_lines_sha256'),
        'excluded_count': win.get('excluded_count'),
        'physical_lines_considered': win.get('physical_lines_considered'),
        'window_rule': win.get('rule'),
        'canonical_hashes': der.get('canonical_sha256') or {},
        'derivatives_status': der.get('status'),
    }


def _current_window():
    """Devuelve la identificación de ventana SOLO si la base y el corte casan."""
    facts = _window_facts()
    db_hash = _hand_hash()
    reliable = _reliable_hands()
    verified = (
        facts['present']
        and db_hash is not None
        and facts['declared_base_sha256'] == db_hash
        and facts['selected_count'] == reliable
        and facts['selected_lines_sha256'] is not None
    )
    if verified:
        return {
            'window': 'reliable_only',
            'window_id': 'reliable_only/first-%s-minus-%s=%s' % (
                facts['physical_lines_considered'] or '?',
                facts['excluded_count'], facts['selected_count']),
            'window_hash': facts['selected_lines_sha256'],
            'window_hash_source': CALIBRATION_WINDOW_PATH,
            'window_verified': True,
        }
    return {
        'window': 'reliable_only',
        'window_id': None,
        'window_hash': None,
        'window_hash_source': None,
        'window_verified': False,
    }


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceEnvelope:
    """Envelope común para un componente o artefacto."""
    component: str
    kind: str
    source_path: Optional[str] = None
    database_path: Optional[str] = 'data/hands_db.jsonl'
    database_hash: Optional[str] = None
    hands_received: Optional[int] = None
    hands_used: Optional[int] = None
    observations: Optional[int] = None
    window: Optional[str] = None
    window_id: Optional[str] = None
    window_hash: Optional[str] = None
    window_hash_source: Optional[str] = None
    code_commit: Optional[str] = None
    code_dirty: Optional[bool] = None
    classification_contract_version: Optional[str] = None
    eligibility_policy_version: Optional[str] = None
    prior_provenance: Optional[str] = None
    range_provenance: Optional[str] = None
    built_at: Optional[str] = None
    origin: str = ORIGIN_UNKNOWN
    status: str = UNKNOWN
    classification: Optional[str] = None
    artifact_hash: Optional[str] = None
    expected_artifact_hash: Optional[str] = None
    artifact_hash_matches: Optional[bool] = None
    required_fields: List[str] = field(default_factory=list)
    present_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def as_dict(self):
        return asdict(self)

    def is_verified(self):
        return self.status == VERIFIED


def _set_window(env, hands_received, window_name):
    """Rellena la ventana solo si coincide con el corte verificado."""
    current = _current_window()
    env.window = window_name
    if (current['window_verified']
            and hands_received == _reliable_hands()
            and window_name in (None, 'reliable_only')):
        env.window_id = current['window_id']
        env.window_hash = current['window_hash']
        env.window_hash_source = current['window_hash_source']


def _complete(env, required):
    env.required_fields = list(required)
    env.missing_fields = [f for f in env.required_fields
                          if getattr(env, f, None) is None]
    return env


# ---------------------------------------------------------------------------
# Reconstruido desde la base actual
# ---------------------------------------------------------------------------

def build_models_envelope():
    """Envelope del build actual, sin construir modelos."""
    env = ProvenanceEnvelope(
        component='build_models', kind='runtime_builder',
        source_path='motor/asistente_live.py::build_models',
        origin=ORIGIN_REBUILT)
    env.database_path = 'data/hands_db.jsonl'
    env.database_hash = _hand_hash()
    env.hands_received = _reliable_hands()
    _set_window(env, env.hands_received, 'reliable_only')
    env.code_commit = code_commit()
    env.code_dirty = arbol_sucio()
    env.classification_contract_version = CLASSIFICATION_CONTRACT_VERSION
    env.eligibility_policy_version = ELIGIBILITY_POLICY_VERSION
    env.prior_provenance = (
        'Oracle.build(hands, labels) desde las mismas manos de entrada')
    env.range_provenance = (
        'ProfileRangeModel.from_hands + PostflopRangeModel.from_hands')
    env.built_at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec='seconds')
    env.present_fields = ['database_hash', 'hands_received', 'window',
                          'window_hash', 'code_commit', 'code_dirty',
                          'classification_contract_version',
                          'eligibility_policy_version', 'prior_provenance',
                          'range_provenance', 'built_at']
    facts = _window_facts()
    env.notes.append(
        'ventana de 877 identificada por hash de lineas seleccionadas')
    env.notes.append(
        'B1 declara la reproduccion de la base como no demostrada y el '
        'snapshot de calibracion como provisional; por eso el estado es '
        'partial, no verified')
    if facts['calibration_provenance_status']:
        env.notes.append('calibration_window.provenance_status: %s'
                         % facts['calibration_provenance_status'])
    if env.code_dirty:
        env.notes.append('arbol de trabajo sucio en el momento de la auditoria')
    _complete(env, ['database_hash', 'hands_received', 'window',
                    'window_hash', 'code_commit',
                    'classification_contract_version',
                    'eligibility_policy_version', 'prior_provenance',
                    'range_provenance'])
    # La base no está reproducida de forma exacta: partial, nunca verified.
    env.status = PARTIAL
    return env


def oracle_priors_envelope():
    """Priors Oracle construidos en el build actual."""
    env = ProvenanceEnvelope(
        component='oracle_priors', kind='prior_source',
        source_path='motor/behavior.py::build + motor/behavior.py::Oracle',
        origin=ORIGIN_REBUILT)
    env.database_path = 'data/hands_db.jsonl'
    env.database_hash = _hand_hash()
    env.hands_received = _reliable_hands()
    _set_window(env, env.hands_received, 'reliable_only')
    env.code_commit = code_commit()
    env.code_dirty = arbol_sucio()
    env.prior_provenance = (
        'tablas granular/por_facing/label/poblacion derivadas de las manos '
        'de entrada y de las etiquetas PEZ/TIBURON')
    env.range_provenance = None
    env.present_fields = ['database_hash', 'hands_received', 'window',
                          'window_hash', 'code_commit', 'prior_provenance']
    env.notes.append('el Oracle del build se comparte con PostflopRangeModel')
    env.notes.append(
        'PostflopRangeModel.load() NO restaura _oracle: al cargar un artefacto '
        'la procedencia del prior se pierde y se usa el fallback plano 0.2 '
        'para celdas con n>0; esto NO se corrige en P0-4')
    _complete(env, ['database_hash', 'hands_received', 'window',
                    'window_hash', 'code_commit', 'prior_provenance'])
    env.status = PARTIAL
    return env


def ranges_envelope():
    """Rangos reconstruidos en el build actual."""
    env = ProvenanceEnvelope(
        component='ranges', kind='range_source',
        source_path=('motor/player_ranges.py::ProfileRangeModel.from_hands + '
                     'motor/postflop_ranges.py::PostflopRangeModel.from_hands'),
        origin=ORIGIN_REBUILT)
    env.database_path = 'data/hands_db.jsonl'
    env.database_hash = _hand_hash()
    env.hands_received = _reliable_hands()
    _set_window(env, env.hands_received, 'reliable_only')
    env.code_commit = code_commit()
    env.code_dirty = arbol_sucio()
    env.prior_provenance = (
        'ProfileRangeModel usa data/preflop_matrices.json como prior por '
        'posicion; procedencia de esa tabla desconocida')
    env.range_provenance = (
        'P(A|H) desde las manos de entrada; PostflopRangeModel usa Oracle '
        'como prior cuando está inyectado')
    env.present_fields = ['database_hash', 'hands_received', 'window',
                          'window_hash', 'code_commit', 'prior_provenance',
                          'range_provenance']
    env.notes.append(
        'el rango preflop depende de una tabla estatica sin procedencia '
        'verificable: no puede declararse verified')
    _complete(env, ['database_hash', 'hands_received', 'window',
                    'window_hash', 'code_commit', 'prior_provenance',
                    'range_provenance'])
    env.status = PARTIAL
    return env


# ---------------------------------------------------------------------------
# Artefactos históricos
# ---------------------------------------------------------------------------

# Los siete derivados históricos declarados por
# tools/reconstruir_derivados.py y data/calibration_window.json.
HISTORICAL_DERIVATIVES = (
    ('profile_ranges', 'data/profile_ranges.json', 'model_artifact'),
    ('postflop_ranges', 'data/postflop_ranges.json', 'model_artifact'),
    ('preflop_stats', 'data/preflop_stats.json', 'stats_artifact'),
    ('player_stats', 'data/player_stats.json', 'stats_artifact'),
    ('profiles', 'data/profiles.json', 'labels_and_profiles_artifact'),
    ('behavior', 'data/behavior.json', 'behavior_table'),
    ('observations', 'data/observations.json', 'observations_artifact'),
)


def _historical_envelope(component, path, kind):
    full = os.path.join(ROOT, path)
    data = _json(full)
    facts = _window_facts()
    env = ProvenanceEnvelope(
        component=component, kind=kind, source_path=path,
        origin=ORIGIN_HISTORICAL if data is not None else ORIGIN_UNKNOWN)
    # El artefacto no registra el hash de la base con la que se construyo.
    # Heredar el hash actual seria una inferencia: se deja en None.
    env.database_path = None
    env.database_hash = None
    env.notes.append(
        'el artefacto no registra hash de base; no se hereda el hash actual')
    env.artifact_hash = _sha256_file(full)
    env.expected_artifact_hash = facts['canonical_hashes'].get(
        os.path.basename(path))
    if env.expected_artifact_hash is not None:
        env.artifact_hash_matches = (
            env.artifact_hash == env.expected_artifact_hash)

    meta = data.get('meta') if isinstance(data, dict) else None
    if isinstance(meta, dict):
        if meta.get('origen'):
            origin = meta['origen']
            env.database_path = ('data/hands_db.jsonl'
                                 if origin == 'hands_db.jsonl' else origin)
            env.notes.append('origen declarado en meta: %r' % origin)
        env.hands_received = meta.get('hands_input')
        env.hands_used = meta.get('hands_used')
        env.window = meta.get('hands_window')
        env.window_id = None
        env.window_hash = None
        env.window_hash_source = None
        if env.hands_received is not None:
            _set_window(env, env.hands_received, meta.get('hands_window'))
        env.code_commit = meta.get('code_commit')
        env.code_dirty = meta.get('arbol_sucio')
        env.built_at = meta.get('built_at')
        env.present_fields = sorted(meta.keys())
        if env.code_commit and env.code_commit != code_commit():
            env.notes.append('code_commit %s != actual %s'
                             % (env.code_commit, code_commit()))
        if env.code_dirty:
            env.notes.append('artefacto construido con arbol sucio')
        if env.hands_used is not None:
            env.notes.append(
                'hands_used=%s es el sello legacy del artefacto; no es un '
                'conteo de contribuyentes postflop' % env.hands_used)
    elif isinstance(data, dict):
        # Sin meta. Solo se registran hechos declarados por el propio fichero.
        env.database_path = None
        if isinstance(data.get('hands'), int):
            env.hands_received = data['hands']
            # Declara un conteo de manos, no una ventana. No se identifica ese
            # conteo con la ventana fiable: seria inferir de mas.
            env.notes.append(
                'declara %s manos, pero no declara ventana ni hash; no se '
                'identifica con la ventana fiable' % data['hands'])
        if isinstance(data.get('observaciones'), int):
            env.observations = data['observaciones']
        env.present_fields = sorted(data.keys())
        env.notes.append('sin bloque meta: no hay commit ni fecha de build')
    elif isinstance(data, list):
        env.observations = len(data)
        env.present_fields = ['list']
        env.notes.append('sin bloque meta: no hay commit ni fecha de build')
    else:
        env.present_fields = []
        env.notes.append('artefacto ausente o ilegible')

    if env.artifact_hash_matches is True:
        env.notes.append(
            'hash del artefacto coincide con canonical_sha256 declarado en '
            'data/calibration_window.json')
    elif env.artifact_hash_matches is False:
        env.notes.append(
            'hash del artefacto NO coincide con el canonico declarado')
    elif data is not None:
        env.notes.append('sin hash canonico declarado: no verificable')
    if facts['calibration_provenance_status']:
        env.notes.append(
            'procedencia de la ventana declarada por B1: %s'
            % facts['calibration_provenance_status'])
    if facts['derivatives_status']:
        env.notes.append('estado de derivados declarado: %s'
                         % facts['derivatives_status'])

    _complete(env, ['artifact_hash', 'code_commit', 'built_at',
                    'classification_contract_version',
                    'eligibility_policy_version'])
    if data is None:
        env.status = UNKNOWN
    elif env.artifact_hash_matches is False:
        env.status = INCOMPATIBLE
    else:
        # Identificado por hash, pero su build no está reproducido ni
        # adoptado: parcial, nunca compatible con la base actual.
        env.status = PARTIAL
    return env


def profile_ranges_envelope(path='data/profile_ranges.json'):
    env = _historical_envelope('profile_ranges', path, 'model_artifact')
    env.classification_contract_version = None
    env.eligibility_policy_version = None
    env.prior_provenance = 'ProfileRangeModel omega + preflop_matrices preflop'
    env.range_provenance = 'ProfileRangeModel.from_hands (historico)'
    env.notes.append(
        'artefacto historico: no se declara compatible con la base actual')
    return env


def postflop_ranges_envelope(path='data/postflop_ranges.json'):
    env = _historical_envelope('postflop_ranges', path, 'model_artifact')
    env.classification_contract_version = None
    env.eligibility_policy_version = None
    env.prior_provenance = 'Oracle.p_action del mismo build historico'
    env.range_provenance = 'PostflopRangeModel.from_hands (historico)'
    env.notes.append(
        'artefacto historico: no se declara compatible con la base actual')
    return env


def preflop_stats_envelope(path='data/preflop_stats.json'):
    env = _historical_envelope('preflop_stats', path, 'stats_artifact')
    env.notes.append('tabla de transiciones preflop historica')
    return env


def profile_stats_envelope(path='data/player_stats.json'):
    env = _historical_envelope('player_stats', path, 'stats_artifact')
    env.notes.append('estadisticas por jugador historicas')
    return env


def profiles_envelope(path='data/profiles.json'):
    env = _historical_envelope('profiles', path,
                               'labels_and_profiles_artifact')
    env.notes.append(
        'provee etiquetas PEZ/TIBURON y perfiles; las etiquetas live se '
        'recalculan desde la base actual en build_models')
    return env


def behavior_envelope(path='data/behavior.json'):
    env = _historical_envelope('behavior', path, 'behavior_table')
    env.notes.append(
        'tabla de comportamiento por etiqueta/calle/textura/facing; sin meta')
    return env


def observations_envelope(path='data/observations.json'):
    env = _historical_envelope('observations', path, 'observations_artifact')
    env.notes.append(
        'observaciones historicas; su numero no es el de contribuyentes '
        'postflop de P0-3')
    return env


def preflop_matrices_envelope(path='data/preflop_matrices.json'):
    data = _json(os.path.join(ROOT, path))
    env = ProvenanceEnvelope(
        component='preflop_matrices', kind='static_table',
        source_path=path,
        origin=ORIGIN_STATIC if data is not None else ORIGIN_UNKNOWN)
    env.artifact_hash = _sha256_file(os.path.join(ROOT, path))
    env.database_path = None
    env.database_hash = None
    env.present_fields = sorted(data.keys()) if isinstance(data, dict) else []
    env.notes.append('sin meta, sin hash de base, sin commit, sin fecha')
    env.notes.append(
        'no se sabe si pertenece a la ventana de 877, a la base de 1344 o a '
        'otra fuente')
    env.notes.append('no declarar compatible con la base actual')
    env.notes.append(
        'es fuente de preflop.py, profile.py y player_ranges._prior_grid')
    _complete(env, ['artifact_hash', 'database_hash', 'hands_received',
                    'window', 'window_hash', 'code_commit', 'built_at',
                    'classification_contract_version',
                    'eligibility_policy_version', 'prior_provenance',
                    'range_provenance'])
    env.status = UNKNOWN
    return env


# ---------------------------------------------------------------------------
# Herramientas auxiliares
# ---------------------------------------------------------------------------

def diagnosticar_56_154_envelope():
    env = ProvenanceEnvelope(component='diagnosticar_56_154',
                             kind='auxiliary_tool',
                             source_path='tools/diagnosticar_56_154.py',
                             origin=ORIGIN_HISTORICAL)
    env.database_hash = _hand_hash()
    env.classification = CLASS_HISTORICAL_ONLY
    env.status = HISTORICAL
    env.notes.append(
        'lee data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json y '
        'data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json')
    env.notes.append(
        'compara contra data/profile_ranges.json y '
        'data/postflop_ranges.json actuales')
    env.notes.append('no construye modelos desde la base actual ni recomienda')
    env.notes.append(
        'no existe separacion de modos: es un comparador historico; su salida '
        'no es un diagnostico de los modelos live actuales')
    _complete(env, ['database_hash'])
    return env


def range_lab_gui_envelope():
    env = ProvenanceEnvelope(component='range_lab_gui',
                             kind='auxiliary_tool',
                             source_path='tools/range_lab_gui.py',
                             origin=ORIGIN_UNKNOWN)
    env.database_hash = _hand_hash()
    env.classification = CLASS_NOT_SUITABLE
    env.status = INCOMPATIBLE
    env.notes.append(
        'load_models() intenta ProfileRangeModel.load() y '
        'PostflopRangeModel.load() primero; si existen artefactos historicos, '
        'los usa sin verificar procedencia')
    env.notes.append(
        'si falta el artefacto, reconstruye desde la base actual')
    env.notes.append(
        'reinyecta Oracle desde la base actual cuando load() lo perdio, '
        'mezclando Oracle actual con tablas historicas')
    env.notes.append(
        'la interfaz no comunica que modelo/fuente se esta usando')
    env.notes.append(
        'no existe separacion real de fuentes ni comprobacion de '
        'compatibilidad')
    _complete(env, ['database_hash'])
    return env


# ---------------------------------------------------------------------------
# Inventarios
# ---------------------------------------------------------------------------

def artifact_readers_inventory():
    """Lectores de artefactos históricos y si comprueban procedencia."""
    return [
        {'reader': 'PostflopRangeModel.load',
         'source': 'motor/postflop_ranges.py',
         'artifact': 'data/postflop_ranges.json',
         'checks_provenance': False,
         'checks_artifact_hash': False,
         'drops_oracle': True,
         'classification': CLASS_NOT_SUITABLE,
         'note': ('acepta cualquier JSON con meta/labels/opp/cnt; no compara '
                  'hash ni commit; deja _oracle=None y cae al fallback 0.2')},
        {'reader': 'ProfileRangeModel.load',
         'source': 'motor/player_ranges.py',
         'artifact': 'data/profile_ranges.json',
         'checks_provenance': False,
         'checks_artifact_hash': False,
         'drops_oracle': False,
         'classification': CLASS_NOT_SUITABLE,
         'note': ('acepta cualquier JSON con meta/perfil/opp/cnt; no compara '
                  'hash ni commit')},
        {'reader': 'PostflopRangeModel.save',
         'source': 'motor/postflop_ranges.py',
         'artifact': 'data/postflop_ranges.json',
         'checks_provenance': False,
         'checks_artifact_hash': False,
         'drops_oracle': False,
         'classification': 'writer',
         'note': 'escribe meta de procedencia; no firma hash de la base'},
        {'reader': 'ProfileRangeModel.save',
         'source': 'motor/player_ranges.py',
         'artifact': 'data/profile_ranges.json',
         'checks_provenance': False,
         'checks_artifact_hash': False,
         'drops_oracle': False,
         'classification': 'writer',
         'note': 'escribe meta de procedencia; no firma hash de la base'},
    ]


def cache_inventory():
    """Inventario de cachés y las dependencias que deberían invalidarlas."""
    return [
        {'cache': '_TABLES (preflop.py)', 'scope': 'process',
         'key': 'None (singleton)',
         'depends_on': ['data/preflop_matrices.json', 'matrix_to_probs',
                        'code_commit'],
         'invalidation_needed': 'path + mtime/hash de matrices + code_commit',
         'survives_base_change': True,
         'survives_labels_change': True,
         'survives_contract_change': True},
        {'cache': '_tables_cache (player_ranges.py)', 'scope': 'process',
         'key': 'None (singleton)',
         'depends_on': ['data/preflop_matrices.json', 'code_commit'],
         'invalidation_needed': 'path + mtime/hash de matrices + code_commit',
         'survives_base_change': True,
         'survives_labels_change': True,
         'survives_contract_change': True},
        {'cache': '_scores_cache (PostflopRangeModel)', 'scope': 'instance',
         'key': 'bytes del board',
         'depends_on': ['board', 'n_buckets', 'evaluate_batch',
                        'code_commit'],
         'invalidation_needed': 'board + n_buckets + code_commit',
         'survives_base_change': True,
         'survives_labels_change': True,
         'survives_contract_change': True},
        {'cache': '_poblacion (Oracle)', 'scope': 'instance',
         'key': 'street',
         'depends_on': ['tabla por_facing', 'min_n', 'labels',
                        'manos de entrada'],
         'invalidation_needed': 'inputs del build + code_commit',
         'survives_base_change': False,
         'survives_labels_change': False,
         'survives_contract_change': True},
        {'cache': '_by_label/_norm (Oracle)', 'scope': 'instance',
         'key': 'sin cache persistente; recalcula por llamada',
         'depends_on': ['tabla por_facing', 'ACTIONS'],
         'invalidation_needed': 'inputs del build + code_commit',
         'survives_base_change': False,
         'survives_labels_change': False,
         'survives_contract_change': True},
        {'cache': '_omega (ProfileRangeModel)', 'scope': 'instance',
         'key': 'player+spot',
         'depends_on': ['profiles', 'SPOT_STAT', 'code_commit'],
         'invalidation_needed': 'profiles + code_commit',
         'survives_base_change': False,
         'survives_labels_change': False,
         'survives_contract_change': True},
        {'cache': '_prior_grid (ProfileRangeModel)', 'scope': 'instance',
         'key': 'action+pos+vs',
         'depends_on': ['data/preflop_matrices.json', 'CAT_TABLE',
                        'code_commit'],
         'invalidation_needed': 'matrices hash + code_commit',
         'survives_base_change': True,
         'survives_labels_change': True,
         'survives_contract_change': True},
        {'cache': '_base_rates (Profiles)', 'scope': 'instance',
         'key': 'matrices_path',
         'depends_on': ['data/preflop_matrices.json', 'code_commit'],
         'invalidation_needed': 'path + mtime/hash + code_commit',
         'survives_base_change': True,
         'survives_labels_change': True,
         'survives_contract_change': True},
        {'cache': '_board_buckets/_cell_hand_ids (PostflopRangeModel)',
         'scope': 'instance',
         'key': 'board / celda',
         'depends_on': ['board', 'evidencia P0-3', 'code_commit'],
         'invalidation_needed': 'board + evidencia + code_commit',
         'survives_base_change': False,
         'survives_labels_change': False,
         'survives_contract_change': True},
    ]


def auxiliary_tool_flows():
    """Flujo efectivo de las dos herramientas auxiliares (auditoría P0-4)."""
    return [
        {
            'tool': 'diagnosticar_56_154',
            'source_path': 'tools/diagnosticar_56_154.py',
            'files_read': [
                'data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json',
                'data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json',
                'data/profile_ranges.json',
                'data/postflop_ranges.json',
            ],
            'models_built': [],
            'historical_sources': [
                'data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json',
                'data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json',
            ],
            'current_sources': [
                'data/profile_ranges.json (artefacto historico en disco)',
                'data/postflop_ranges.json (artefacto historico en disco)',
            ],
            'priors_used': [],
            'ranges_used': [],
            'combinations': [
                'snapshot historico vs artefacto historico en disco',
            ],
            'caches': [],
            'outputs': [
                'comparativa de jugadores, claves y totales opp/cnt',
                'explicacion del salto 56 -> 154 jugadores',
            ],
            'classification': CLASS_HISTORICAL_ONLY,
            'evidence': [
                'SNAP = data/_snapshot_pre_rebuild_1b14c18 en la linea 16',
                '_load() abre SNAP/<name> y data/<name> en la linea 20-23',
                'no importa motor, no llama build_models ni Oracle',
            ],
            'incompatibilities': [
                'no hay modo actual: la salida no describe los modelos live',
            ],
            'limitations': [
                'depende de un snapshot historico que debe conservarse',
                'el artefacto "actual" que compara tambien es historico',
            ],
        },
        {
            'tool': 'range_lab_gui',
            'source_path': 'tools/range_lab_gui.py',
            'files_read': [
                'data/profile_ranges.json (si existe)',
                'data/postflop_ranges.json (si existe)',
                'data/hands_db.jsonl (fallback y reinyeccion de Oracle)',
                'data/preflop_matrices.json (via player_ranges)',
            ],
            'models_built': [
                'ProfileRangeModel.load() o ProfileRangeModel.from_hands()',
                'PostflopRangeModel.load() o PostflopRangeModel.from_hands()',
                'Oracle(build(hands, labels)) si _oracle is None',
            ],
            'historical_sources': [
                'data/profile_ranges.json (si load tiene exito)',
                'data/postflop_ranges.json (si load tiene exito)',
            ],
            'current_sources': [
                'data/hands_db.jsonl via load_hands(reliable_only=True)',
            ],
            'priors_used': [
                'Oracle actual reconstruido desde hands_db',
                'preflop_matrices.json via ProfileRangeModel._prior_grid',
                'fallback plano 0.2 si el Oracle falta (n>0)',
            ],
            'ranges_used': [
                'ProfileRangeModel.prob_vec / opening_range',
                'PostflopRangeModel.prob_vec',
            ],
            'combinations': [
                'perfil historico + Oracle actual (reinyectado)',
                'postflop historico + Oracle actual (reinyectado)',
                'preflop historico + matrices de procedencia desconocida',
                'artefacto ausente -> modelo reconstruido desde base actual',
            ],
            'caches': [
                '_TABLES', '_tables_cache', '_scores_cache', '_poblacion',
                '_omega', '_prior_grid', '_board_buckets',
            ],
            'outputs': [
                'tabla de pasos con equity, masa, ms_update, ms_equity, '
                'n_cell y prior',
                'top combos del rango rival',
                'timings de carga y pipeline',
            ],
            'classification': CLASS_NOT_SUITABLE,
            'evidence': [
                'load_models() lineas 47-79: json si existe, DB si falla',
                'lineas 70-76: reinyecta Oracle desde la base actual',
                'la cabecera solo muestra ms de carga, no la fuente',
                'no compara hashes ni commit de los artefactos cargados',
            ],
            'incompatibilities': [
                'tablas postflop historicas + Oracle actual',
                'perfil preflop historico + matrices sin procedencia',
            ],
            'limitations': [
                'no separa modo historico y modo actual',
                'no comunica que modelo esta usando',
                'no se corrige en P0-4: solo se documenta y prueba',
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Inventario y compatibilidad
# ---------------------------------------------------------------------------

def all_envelopes():
    return [
        build_models_envelope(),
        oracle_priors_envelope(),
        ranges_envelope(),
        profile_ranges_envelope(),
        postflop_ranges_envelope(),
        preflop_stats_envelope(),
        profile_stats_envelope(),
        profiles_envelope(),
        behavior_envelope(),
        observations_envelope(),
        preflop_matrices_envelope(),
        diagnosticar_56_154_envelope(),
        range_lab_gui_envelope(),
    ]


_COMPAT_PAIRS = (
    ('build_models', 'profile_ranges'),
    ('build_models', 'postflop_ranges'),
    ('build_models', 'preflop_stats'),
    ('build_models', 'player_stats'),
    ('build_models', 'profiles'),
    ('build_models', 'behavior'),
    ('build_models', 'observations'),
    ('build_models', 'preflop_matrices'),
    ('build_models', 'oracle_priors'),
    ('build_models', 'ranges'),
    ('profile_ranges', 'postflop_ranges'),
    ('profile_ranges', 'preflop_stats'),
    ('profiles', 'player_stats'),
    ('postflop_ranges', 'oracle_priors'),
    ('postflop_ranges', 'ranges'),
    ('ranges', 'preflop_matrices'),
    ('ranges', 'oracle_priors'),
)


def _compat_pair(a: ProvenanceEnvelope, b: ProvenanceEnvelope) -> Dict:
    if a.status in (UNKNOWN, HISTORICAL) or b.status in (UNKNOWN, HISTORICAL):
        unknown = [x.component for x in (a, b)
                   if x.status in (UNKNOWN, HISTORICAL)]
        return {'compatible': None, 'verdict': 'unknown',
                'scope': 'unknown',
                'reason': 'procedencia desconocida o solo historica en %s'
                          % ', '.join(unknown)}
    if a.status == INCOMPATIBLE or b.status == INCOMPATIBLE:
        return {'compatible': False, 'verdict': 'incompatible',
                'scope': 'declared',
                'reason': 'alguno es incompatible con su procedencia declarada'}
    if a.origin == ORIGIN_UNKNOWN or b.origin == ORIGIN_UNKNOWN:
        return {'compatible': None, 'verdict': 'unknown', 'scope': 'unknown',
                'reason': 'origen desconocido'}
    if a.database_hash and b.database_hash \
            and a.database_hash != b.database_hash:
        return {'compatible': False, 'verdict': 'incompatible',
                'scope': 'base', 'reason': 'hashes de base distintos'}
    if a.origin == ORIGIN_REBUILT and b.origin == ORIGIN_HISTORICAL:
        return {'compatible': False, 'verdict': 'incompatible',
                'scope': 'current_vs_historical',
                'reason': 'modelo reconstruido vs artefacto historico; no se '
                          'presentan como un modelo coherente'}
    if b.origin == ORIGIN_REBUILT and a.origin == ORIGIN_HISTORICAL:
        return {'compatible': False, 'verdict': 'incompatible',
                'scope': 'current_vs_historical',
                'reason': 'artefacto historico vs modelo reconstruido; no se '
                          'presentan como un modelo coherente'}
    if a.origin == ORIGIN_REBUILT and b.origin == ORIGIN_REBUILT:
        if a.window_hash and b.window_hash \
                and a.window_hash != b.window_hash:
            return {'compatible': False, 'verdict': 'incompatible',
                    'scope': 'window', 'reason': 'ventanas distintas'}
        if a.database_hash is None or b.database_hash is None:
            return {'compatible': None, 'verdict': 'unknown',
                    'scope': 'base', 'reason': 'sin hash de base'}
        if a.code_commit and b.code_commit and a.code_commit != b.code_commit:
            return {'compatible': None, 'verdict': 'unknown',
                    'scope': 'code', 'reason': 'commits distintos sin '
                    'verificacion de equivalencia'}
        return {'compatible': True, 'verdict': 'compatible',
                'scope': 'current',
                'reason': 'misma base y ventana, mismo commit'}
    if a.origin == ORIGIN_HISTORICAL and b.origin == ORIGIN_HISTORICAL:
        if a.code_commit and b.code_commit and a.code_commit != b.code_commit:
            return {'compatible': None, 'verdict': 'unknown',
                    'scope': 'historical',
                    'reason': 'commits historicos distintos'}
        if a.artifact_hash_matches and b.artifact_hash_matches:
            return {'compatible': True, 'verdict': 'compatible',
                    'scope': 'historical_only',
                    'reason': 'ambos coinciden con los hashes canonicos '
                              'declarados en calibration_window.json'}
        return {'compatible': None, 'verdict': 'unknown',
                'scope': 'historical',
                'reason': 'sin hashes canonicos verificables'}
    if a.origin == ORIGIN_STATIC or b.origin == ORIGIN_STATIC:
        return {'compatible': None, 'verdict': 'unknown', 'scope': 'static',
                'reason': 'tabla estatica sin procedencia verificable'}
    return {'compatible': None, 'verdict': 'unknown', 'scope': 'unknown',
            'reason': 'sin regla de compatibilidad aplicable'}


def compatibility_matrix():
    """Matriz de compatibilidad calculada a partir de los envelopes."""
    envs = {e.component: e for e in all_envelopes()}
    rows = []
    for left, right in _COMPAT_PAIRS:
        pair = _compat_pair(envs[left], envs[right])
        rows.append({'left': left, 'right': right, **pair})
    return rows


def detect_mixture(components):
    """Diagnóstico de una combinación concreta (sombra, no bloquea)."""
    envs = {e.component: e for e in all_envelopes()}
    missing = [c for c in components if c not in envs]
    if missing:
        return {'components': list(components), 'verdict': 'unknown',
                'would_block': False, 'would_warn': True,
                'pairs': [], 'error': 'componentes no inventariados: %s'
                % ', '.join(missing)}
    pairs = []
    for left, right in combinations(components, 2):
        pair = _compat_pair(envs[left], envs[right])
        pairs.append({'left': left, 'right': right, **pair})
    would_block = any(p['compatible'] is False for p in pairs)
    would_warn = any(p['compatible'] is None for p in pairs)
    return {'components': list(components),
            'verdict': ('incompatible' if would_block
                        else 'unknown' if would_warn else 'compatible'),
            'would_block': would_block,
            'would_warn': would_warn,
            'pairs': pairs}


def mixture_cases():
    """Casos reproducibles de mezcla incompatible o desconocida."""
    cases = [
        ('reconstruido_vs_perfil_historico',
         ['build_models', 'profile_ranges']),
        ('reconstruido_vs_postflop_historico',
         ['build_models', 'postflop_ranges']),
        ('reconstruido_vs_behavior_historico',
         ['build_models', 'behavior']),
        ('reconstruido_vs_matrices_sin_procedencia',
         ['build_models', 'preflop_matrices']),
        ('rangos_vs_matrices_sin_procedencia',
         ['ranges', 'preflop_matrices']),
        ('postflop_historico_vs_oracle_actual',
         ['postflop_ranges', 'oracle_priors']),
        ('historico_vs_historico_mismo_snapshot',
         ['profile_ranges', 'postflop_ranges']),
    ]
    out = []
    for name, components in cases:
        result = detect_mixture(components)
        out.append({'case': name, **result})
    return out


def auxiliary_tool_matrix():
    """Clasificación y mezclas de las herramientas auxiliares."""
    envs = {e.component: e for e in all_envelopes()}
    rows = []
    for tool, sources in (
            ('diagnosticar_56_154', ['profile_ranges', 'postflop_ranges']),
            ('range_lab_gui',
             ['profile_ranges', 'postflop_ranges', 'oracle_priors',
              'preflop_matrices'])):
        env = envs[tool]
        rows.append({
            'tool': tool,
            'classification': env.classification,
            'status': env.status,
            'sources': sources,
            'separation_of_modes': (
                env.classification == CLASS_EXPLICIT_MODES),
            'suitable_for_current_analysis': (
                env.classification in (CLASS_CURRENT_ONLY,
                                       CLASS_EXPLICIT_MODES)),
            'notes': list(env.notes),
        })
    return rows


def audit_provenance():
    return {
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec='seconds'),
        'code_commit': code_commit(),
        'code_dirty': arbol_sucio(),
        'database_hash': _hand_hash(),
        'reliable_hands': _reliable_hands(),
        'window': _current_window(),
        'calibration_window': _window_facts(),
        'envelopes': [e.as_dict() for e in all_envelopes()],
        'compatibility': compatibility_matrix(),
        'mixture_cases': mixture_cases(),
        'auxiliary_tools': auxiliary_tool_matrix(),
        'auxiliary_flows': auxiliary_tool_flows(),
        'readers': artifact_readers_inventory(),
        'caches': cache_inventory(),
        'notes': [
            'P0-4 en modo auditoria/sombra: no cambia modelos ni '
            'recomendaciones.',
            'Los siete derivados historicos permanecen intactos y coinciden '
            'con los hashes canonicos declarados.',
            'La reproduccion de la base y de los derivados no esta '
            'demostrada (B1); no se declaran compatibles con la base actual.',
            'preflop_matrices.json se conserva sin modificar; procedencia '
            'desconocida.',
            'No se reancla ni regenera ningun derivado.',
            'No se bloquean consultas live: solo se registra que se habria '
            'bloqueado.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(audit_provenance(), indent=2, ensure_ascii=False,
                     default=str))
