# -*- coding: utf-8 -*-
"""P0-4 — Contrato de procedencia y compatibilidad de modelos.

Este módulo no cambia modelos, priors, tablas ni recomendaciones. Define un
envelope común para describir la procedencia de cada componente y permite
auditar mezclas silenciosas entre artefactos históricos y modelos
reconstruidos desde la base actual.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ._procedencia import code_commit, arbol_sucio, RUTAS_RELEVANTES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')


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


# Estados de procedencia (sin inferencias).
VERIFIED = 'verified'
PARTIAL = 'partial'
UNKNOWN = 'unknown'
INCOMPATIBLE = 'incompatible'
HISTORICAL = 'historical'
REBUILT = 'rebuilt'

# Origenes.
ORIGIN_REBUILT = 'rebuilt_from_current_base'
ORIGIN_HISTORICAL = 'historical_derivative'
ORIGIN_STATIC = 'static_table'
ORIGIN_UNKNOWN = 'unknown'


@dataclass
class ProvenanceEnvelope:
    """Envelope común para un componente o artefacto."""
    component: str
    kind: str
    source_path: Optional[str] = None
    database_path: Optional[str] = 'data/hands_db.jsonl'
    database_hash: Optional[str] = None
    hands_received: Optional[int] = None
    window: Optional[str] = None
    window_hash: Optional[str] = None
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
    required_fields: List[str] = field(default_factory=list)
    present_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def as_dict(self):
        return asdict(self)

    def is_verified(self):
        return self.status == VERIFIED


# Versión mínima del contrato de clasificación y política. Se declara aquí
# para que las auditorías puedan compararla sin inferir por fecha.
CLASSIFICATION_CONTRACT_VERSION = 'P0-1 shadow (dd80689)'
ELIGIBILITY_POLICY_VERSION = 'P0-2 shadow (717d2ea)'


def _hand_hash():
    return _sha256_file(os.path.join(ROOT, 'data', 'hands_db.jsonl'))


def _reliable_hands():
    from .learn import RELIABLE_HANDS, manos_excluidas
    return RELIABLE_HANDS - len(manos_excluidas())


def _base_meta(path):
    data = _json(path)
    if not isinstance(data, dict):
        return None
    return data.get('meta')


def _envelope_from_meta(component, kind, path, meta, origin, status=None):
    env = ProvenanceEnvelope(component=component, kind=kind,
                             source_path=path, origin=origin)
    if meta is not None:
        env.database_path = meta.get('origen') and 'data/hands_db.jsonl' \
            or env.database_path
        env.hands_received = meta.get('hands_input')
        env.window = meta.get('hands_window')
        env.code_commit = meta.get('code_commit')
        env.code_dirty = meta.get('arbol_sucio')
        env.built_at = meta.get('built_at')
        env.prior_provenance = 'Oracle built from same input hands' \
            if 'Oracle' in (meta.get('origen') or '') else None
        env.present_fields = sorted(k for k in meta.keys())
    else:
        env.present_fields = []
    env.database_hash = _hand_hash()
    env.required_fields = ['hands_input', 'hands_window', 'code_commit',
                          'built_at']
    env.missing_fields = [f for f in env.required_fields
                          if f not in env.present_fields]
    if status is None:
        if meta is None:
            status = UNKNOWN
        elif env.missing_fields:
            status = PARTIAL
        else:
            status = VERIFIED
    env.status = status
    return env


def build_models_envelope():
    """Envelope del build actual, sin construir modelos."""
    env = ProvenanceEnvelope(
        component='build_models', kind='runtime_builder',
        source_path='motor/asistente_live.py::build_models',
        origin=ORIGIN_REBUILT)
    env.database_path = 'data/hands_db.jsonl'
    env.database_hash = _hand_hash()
    env.hands_received = _reliable_hands()
    env.window = 'reliable_only'
    env.code_commit = code_commit()
    env.code_dirty = arbol_sucio()
    env.classification_contract_version = CLASSIFICATION_CONTRACT_VERSION
    env.eligibility_policy_version = ELIGIBILITY_POLICY_VERSION
    env.prior_provenance = 'Oracle built from input hands'
    env.range_provenance = 'ProfileRangeModel.from_hands'
    env.built_at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec='seconds')
    env.present_fields = ['hands_received', 'window', 'code_commit',
                          'code_dirty', 'classification_contract_version',
                          'eligibility_policy_version', 'built_at']
    env.required_fields = ['hands_received', 'window', 'code_commit',
                           'code_dirty', 'classification_contract_version',
                           'eligibility_policy_version', 'built_at']
    env.missing_fields = [f for f in env.required_fields
                          if f not in env.present_fields]
    env.status = VERIFIED if not env.missing_fields else PARTIAL
    return env


def profile_ranges_envelope(path='data/profile_ranges.json'):
    full = os.path.join(ROOT, path)
    meta = _base_meta(full)
    env = _envelope_from_meta('profile_ranges', 'model_artifact', path, meta,
                              ORIGIN_HISTORICAL if meta else ORIGIN_UNKNOWN)
    env.classification_contract_version = None
    env.eligibility_policy_version = None
    env.prior_provenance = 'ProfileRangeModel omega + matrices preflop'
    env.range_provenance = 'ProfileRangeModel.from_hands'
    # Histórico: no se puede verificar compatibilidad con la base actual.
    if meta is not None:
        if meta.get('hands_input') != _reliable_hands():
            env.status = INCOMPATIBLE
            env.notes.append(
                'hands_input %s != ventana fiable actual %s'
                % (meta.get('hands_input'), _reliable_hands()))
        if meta.get('code_commit') != code_commit():
            env.notes.append(
                'code_commit %s != actual %s'
                % (meta.get('code_commit'), code_commit()))
        if meta.get('arbol_sucio'):
            env.notes.append('artefacto construido con arbol sucio')
    else:
        env.status = UNKNOWN
        env.notes.append('sin meta: procedencia desconocida')
    env.required_fields = ['hands_input', 'hands_window', 'code_commit',
                          'built_at', 'classification_contract_version',
                          'eligibility_policy_version']
    env.missing_fields = [f for f in env.required_fields
                          if f not in (env.present_fields or [])]
    if env.missing_fields and env.status == VERIFIED:
        env.status = PARTIAL
    return env


def postflop_ranges_envelope(path='data/postflop_ranges.json'):
    full = os.path.join(ROOT, path)
    meta = _base_meta(full)
    env = _envelope_from_meta('postflop_ranges', 'model_artifact', path, meta,
                              ORIGIN_HISTORICAL if meta else ORIGIN_UNKNOWN)
    env.prior_provenance = 'Oracle.p_action (mismo build)'
    env.range_provenance = 'PostflopRangeModel.from_hands'
    if meta is not None:
        if meta.get('hands_input') != _reliable_hands():
            env.status = INCOMPATIBLE
            env.notes.append(
                'hands_input %s != ventana fiable actual %s'
                % (meta.get('hands_input'), _reliable_hands()))
        if meta.get('code_commit') != code_commit():
            env.notes.append(
                'code_commit %s != actual %s'
                % (meta.get('code_commit'), code_commit()))
    else:
        env.status = UNKNOWN
        env.notes.append('sin meta: procedencia desconocida')
    env.required_fields = ['hands_input', 'hands_window', 'code_commit',
                          'built_at', 'classification_contract_version',
                          'eligibility_policy_version']
    env.missing_fields = [f for f in env.required_fields
                          if f not in (env.present_fields or [])]
    if env.missing_fields and env.status == VERIFIED:
        env.status = PARTIAL
    return env


def behavior_envelope(path='data/behavior.json'):
    data = _json(os.path.join(ROOT, path))
    env = ProvenanceEnvelope(component='behavior', kind='behavior_table',
                             source_path=path, origin=ORIGIN_HISTORICAL
                             if data is not None else ORIGIN_UNKNOWN)
    if isinstance(data, dict):
        env.hands_received = data.get('hands')
        env.present_fields = sorted(data.keys())
    else:
        env.present_fields = []
    env.database_hash = _hand_hash()
    env.required_fields = ['meta', 'hands', 'code_commit', 'built_at']
    env.missing_fields = [f for f in env.required_fields
                          if f not in (env.present_fields or [])]
    env.status = UNKNOWN if not data else PARTIAL
    env.notes.append('sin sello de procedencia: no se puede verificar '
                     'compatibilidad con la base actual')
    return env


def profile_stats_envelope(path='data/player_stats.json'):
    data = _json(os.path.join(ROOT, path))
    env = ProvenanceEnvelope(component='player_stats', kind='stats_artifact',
                             source_path=path, origin=ORIGIN_HISTORICAL
                             if data is not None else ORIGIN_UNKNOWN)
    env.present_fields = ['players'] if data is not None else []
    env.database_hash = _hand_hash()
    env.required_fields = ['meta', 'hands', 'code_commit', 'built_at']
    env.missing_fields = list(env.required_fields)
    env.status = UNKNOWN if not data else PARTIAL
    env.notes.append('sin sello de procedencia')
    return env


def preflop_matrices_envelope(path='data/preflop_matrices.json'):
    data = _json(os.path.join(ROOT, path))
    env = ProvenanceEnvelope(component='preflop_matrices', kind='static_table',
                             source_path=path, origin=ORIGIN_STATIC
                             if data is not None else ORIGIN_UNKNOWN)
    if isinstance(data, dict):
        env.present_fields = sorted(data.keys())
        env.hands_received = None
    else:
        env.present_fields = []
    env.database_hash = None
    env.required_fields = ['meta', 'hands_input', 'hands_window', 'code_commit',
                          'built_at', 'source', 'coverage']
    env.missing_fields = list(env.required_fields)
    env.status = UNKNOWN
    env.notes.append('sin meta, sin hash de base, sin commit, sin fecha')
    env.notes.append('no se sabe si pertenece a 877, a 1344 o a otra ventana')
    env.notes.append('no declarar compatible con la base actual')
    return env


def diagnosticar_56_154_envelope():
    env = ProvenanceEnvelope(component='diagnosticar_56_154',
                            kind='auxiliary_tool',
                            source_path='tools/diagnosticar_56_154.py',
                            origin=ORIGIN_HISTORICAL)
    env.database_hash = _hand_hash()
    env.required_fields = ['mode_historical', 'mode_current', 'separation']
    env.missing_fields = list(env.required_fields)
    env.classification = 'historical_only'
    env.status = HISTORICAL
    env.notes.append('lee data/_snapshot_pre_rebuild_1b14c18/profile_ranges.json '
                     'y data/_snapshot_pre_rebuild_1b14c18/postflop_ranges.json')
    env.notes.append('compara contra data/profile_ranges.json y '
                     'data/postflop_ranges.json actuales')
    env.notes.append('no construye modelos desde la base actual ni recomienda')
    env.notes.append('no existe separacion de modos: es un comparador historico')
    return env


def range_lab_gui_envelope():
    env = ProvenanceEnvelope(component='range_lab_gui', kind='auxiliary_tool',
                             source_path='tools/range_lab_gui.py',
                             origin=ORIGIN_UNKNOWN)
    env.database_hash = _hand_hash()
    env.required_fields = ['mode_historical', 'mode_current', 'separation']
    env.missing_fields = list(env.required_fields)
    env.classification = 'not_suitable'
    env.status = INCOMPATIBLE
    env.notes.append('load_models() intenta ProfileRangeModel.load() y '
                     'PostflopRangeModel.load() primero; si existen artefactos '
                     'historicos, los usa sin verificar procedencia')
    env.notes.append('si falta el artefacto, reconstruye desde la base actual')
    env.notes.append('reinyecta Oracle desde la base actual cuando load() lo '
                     'perdio, mezclando Oracle actual con tablas historicas')
    env.notes.append('la interfaz no comunica que modelo/fuente se esta usando')
    env.notes.append('no existe separacion real de fuentes ni comprobacion de '
                     'compatibilidad')
    return env


def cache_inventory():
    """Inventario de cachés y sus claves de identidad actuales."""
    return [
        {'cache': '_TABLES (preflop.py)',
         'scope': 'process', 'key': 'None (singleton)', 'depends_on':
         ['data/preflop_matrices.json', 'matrix_to_probs'],
         'invalidation_needed': 'path + mtime/hash de matrices + code_commit'},
        {'cache': '_tables_cache (player_ranges.py)',
         'scope': 'process', 'key': 'None (singleton)', 'depends_on':
         ['data/preflop_matrices.json'],
         'invalidation_needed': 'path + mtime/hash de matrices + code_commit'},
        {'cache': '_scores_cache (PostflopRangeModel)',
         'scope': 'instance', 'key': 'board_ids bytes', 'depends_on':
         ['board', 'n_buckets', 'evaluate_batch'],
         'invalidation_needed': 'board + n_buckets + code_commit'},
        {'cache': '_poblacion/_label_level (Oracle)',
         'scope': 'instance', 'key': 'street', 'depends_on':
         ['facing table', 'min_n', 'labels'],
         'invalidation_needed': 'inputs del build + code_commit'},
        {'cache': '_omega (ProfileRangeModel)',
         'scope': 'instance', 'key': 'player+spot', 'depends_on':
         ['profiles', 'SPOT_STAT'],
         'invalidation_needed': 'profiles + code_commit'},
        {'cache': '_base_rates (Profiles)',
         'scope': 'instance', 'key': 'matrices_path', 'depends_on':
         ['data/preflop_matrices.json'],
         'invalidation_needed': 'path + mtime/hash + code_commit'},
    ]


def all_envelopes():
    return [
        build_models_envelope(),
        profile_ranges_envelope(),
        postflop_ranges_envelope(),
        behavior_envelope(),
        profile_stats_envelope(),
        preflop_matrices_envelope(),
        diagnosticar_56_154_envelope(),
        range_lab_gui_envelope(),
    ]


def compatibility_matrix():
    """Matriz de compatibilidad entre componentes (solo diagnóstico)."""
    rows = []
    envs = {e.component: e for e in all_envelopes()}
    # build actual vs artefactos históricos
    bm = envs['build_models']
    for name in ('profile_ranges', 'postflop_ranges'):
        e = envs[name]
        rows.append({
            'left': 'build_models', 'right': name,
            'compatible': False,
            'reason': ('procedencia %s vs %s; no mezclar artefacto historico '
                       'con modelo reconstruido' % (bm.status, e.status)),
        })
    rows.append({
        'left': 'profile_ranges', 'right': 'postflop_ranges',
        'compatible': 'unknown',
        'reason': 'ambos historicos (0fcceed) pero sin verificacion de base',
    })
    rows.append({
        'left': 'preflop_matrices', 'right': 'build_models',
        'compatible': 'unknown',
        'reason': 'matrices sin meta; no se sabe si son de 877/1344',
    })
    rows.append({
        'left': 'behavior', 'right': 'build_models',
        'compatible': 'unknown',
        'reason': 'behavior.json sin sello de procedencia',
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
        'envelopes': [e.as_dict() for e in all_envelopes()],
        'compatibility': compatibility_matrix(),
        'caches': cache_inventory(),
        'notes': [
            'P0-4 en modo auditoria/sombra: no cambia modelos ni recomendaciones.',
            'Los siete derivados historicos permanecen intactos.',
            'preflop_matrices.json se conserva sin modificar; procedencia desconocida.',
            'No se reancla ni regenera ningun derivado.',
        ],
    }


if __name__ == '__main__':
    import json as _json
    print(_json.dumps(audit_provenance(), indent=2, ensure_ascii=False,
                      default=str))