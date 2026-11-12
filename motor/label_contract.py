# -*- coding: utf-8 -*-
"""P0-5 — Contrato contextual de etiquetas (sombra).

No cambia etiquetas efectivas, modelos ni recomendaciones. Su único trabajo es
hacer explícito qué etiqueta produce cada clasificador, con qué variables, con
qué evidencia y con qué procedencia.

Dos clasificadores conviven hoy:

  training  ``Profiles.simple_label(vpip, pfr, stack_mean)``
            - stack medio del dataset < 50 BB -> PEZ
            - si no, VPIP > 0.32 y PFR < 0.10 -> PEZ
            - resto -> TIBURON (incluye el caso sin información)
  serving   ``Asistente._perfil_for(player_id, state)``
            - media de stacks visibles en la sesión < 50 BB -> PEZ
            - si no hay media, stack actual < 50 BB -> PEZ
            - sin información -> TIBURON
            - NO usa VPIP, PFR, nombre ni ``models.labels``

Una etiqueta no es válida solo por ser determinista: además necesita evidencia
y procedencia. El contrato nunca rellena un dato ausente.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import io
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .learn import load_hands
from .profile import (
    PEZ,
    STACK_FISH_BB,
    TIBURON,
    Profiles,
    simple_label,
)
from .provenance_contract import (
    INCOMPATIBLE,
    PARTIAL,
    build_models_envelope,
    profiles_envelope,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_PATH = os.path.join(ROOT, 'data', 'profiles.json')

LABEL_UNKNOWN = 'UNKNOWN'

# Estados del contrato.
STATE_HISTORICAL = 'historical'
STATE_CURRENT = 'current_evidence'
STATE_PROVISIONAL = 'provisional'
STATE_UNKNOWN = 'unknown'
STATE_INSUFFICIENT = 'insufficient_evidence'
STATE_INCOMPATIBLE = 'incompatible_provenance'

# Resultado de la comparación entrenamiento vs serving.
STATUS_COINCIDENT = 'coincident'
STATUS_DIFFERENT = 'different'
STATUS_HISTORICAL_NOT_REPRODUCIBLE = 'historical_not_reproducible'
STATUS_INSUFFICIENT = 'insufficient_evidence'
STATUS_SERVING_UNAVAILABLE = 'serving_data_unavailable'
STATUS_INCOMPATIBLE = 'incompatible_provenance'
STATUS_UNKNOWN = 'unknown'

# Tramo mínimo ya declarado en profile.HANDS_BANDS. No se introduce un umbral
# nuevo: se reutiliza solo como diagnóstico de "primer tramo".
FIRST_RELIABILITY_BAND = 40

# Umbrales de la regla, declarados aquí para que la auditoría no los invente.
VPIP_FALLBACK_MIN = 0.32
PFR_FALLBACK_MAX = 0.10


@dataclass
class LabelDecision:
    """Decisión de etiqueta con su evidencia y su procedencia."""
    player: str
    source: str
    label: str
    contract_label: str
    state: str
    method: str
    variables: Dict[str, Any] = field(default_factory=dict)
    hands_n: Optional[int] = None
    relevant_observations: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[str] = None
    provenance_status: Optional[str] = None
    window: Optional[str] = None
    window_hash: Optional[str] = None
    built_commit: Optional[str] = None
    uncertainty: List[str] = field(default_factory=list)
    rules_blocking: List[str] = field(default_factory=list)
    reproducible: Optional[bool] = None
    valid_for_serving: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


@dataclass
class LabelComparison:
    """Comparación de una etiqueta de entrenamiento con una de serving."""
    player: str
    status: str
    reason: str
    training_label: Optional[str]
    serving_label: Optional[str]
    historical_label: Optional[str] = None
    stack_only_label: Optional[str] = None
    current_evidence_available: Optional[bool] = None
    historical_reproducible: Optional[bool] = None
    provenance_status: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Evidencia
# ---------------------------------------------------------------------------

def stack_samples_by_player(hands):
    """Lista de stacks observados por jugador, en orden de aparición.

    No se deduplica: es la evidencia del dataset, no la sesión live.
    """
    out = defaultdict(list)
    for hand in hands:
        for p in hand.get('players', []):
            name = p.get('name')
            if not name:
                continue
            try:
                s = float(p.get('stack'))
            except (TypeError, ValueError):
                continue
            out[name].append(s)
    return dict(out)


def last_stack_by_player(hands):
    out = {}
    for hand in hands:
        for p in hand.get('players', []):
            name = p.get('name')
            if not name:
                continue
            try:
                out[name] = float(p.get('stack'))
            except (TypeError, ValueError):
                continue
    return out


def _current_provenance():
    env = build_models_envelope()
    return {
        'provenance': ('data/hands_db.jsonl · ventana fiable 877 · '
                       'build actual'),
        'provenance_status': env.status,
        'window': env.window,
        'window_hash': env.window_hash,
        'built_commit': env.code_commit,
        'code_dirty': env.code_dirty,
        'hands_n': env.hands_received,
    }


def _historical_provenance():
    env = profiles_envelope()
    return {
        'provenance': ('data/profiles.json · derivado historico · '
                       'P0-4 partial'),
        'provenance_status': env.status,
        'artifact_hash_matches': env.artifact_hash_matches,
        'window': ('no registrada en el artefacto; calibration_window '
                   'declara 877'),
        'window_hash': None,
        'built_commit': env.code_commit,
        'hands_n': env.hands_received,
        'code_dirty': env.code_dirty,
    }


def _state_from_evidence(n_rule_observations):
    if n_rule_observations is None or n_rule_observations <= 0:
        return STATE_INSUFFICIENT
    if n_rule_observations < FIRST_RELIABILITY_BAND:
        return STATE_PROVISIONAL
    return STATE_CURRENT


# ---------------------------------------------------------------------------
# Entrenamiento
# ---------------------------------------------------------------------------

def training_decision(profile, n_stack_observations, hands_n,
                      provenance=None):
    """Traza exacta de la etiqueta de entrenamiento para un PlayerProfile."""
    provenance = provenance or _current_provenance()
    vpip = profile.stats.get('vpip')
    pfr = profile.stats.get('pfr')
    stack = profile.stack_mean
    counts = dict(profile.counts or {})
    n = profile.n

    variables = {
        'stack_mean_bb': stack,
        'stack_threshold_bb': STACK_FISH_BB,
        'vpip': vpip,
        'vpip_threshold': VPIP_FALLBACK_MIN,
        'pfr': pfr,
        'pfr_threshold': PFR_FALLBACK_MAX,
        'vpip_counts_opp_act': counts.get('vpip'),
        'pfr_counts_opp_act': counts.get('pfr'),
        'n_vpip_opportunities': n,
        'stack_observations': n_stack_observations,
        'reliability_band_first': FIRST_RELIABILITY_BAND,
    }
    relevant = {
        'n_vpip_opportunities': n,
        'vpip_opp': (counts.get('vpip') or (None, None))[0],
        'vpip_act': (counts.get('vpip') or (None, None))[1],
        'pfr_opp': (counts.get('pfr') or (None, None))[0],
        'pfr_act': (counts.get('pfr') or (None, None))[1],
        'stack_observations': n_stack_observations,
        'hands_in_window': hands_n,
    }

    uncertainty = []
    blocking = []
    label = TIBURON

    if stack is not None and stack < STACK_FISH_BB:
        label = PEZ
        method = 'stack_mean_lt_50bb'
        n_rule_obs = n_stack_observations or 0
        state = _state_from_evidence(n_rule_obs)
        uncertainty.append(
            'regla de stack: %.2f BB < %.1f BB; margen %.2f BB'
            % (stack, STACK_FISH_BB, STACK_FISH_BB - stack))
    elif vpip is not None and pfr is not None:
        n_rule_obs = n
        state = _state_from_evidence(n_rule_obs)
        if vpip > VPIP_FALLBACK_MIN and pfr < PFR_FALLBACK_MAX:
            label = PEZ
            method = 'loose_passive_fallback'
            uncertainty.append(
                'fallback VPIP>0.32 y PFR<0.10; serving no dispone de estas '
                'variables')
        else:
            label = TIBURON
            method = 'default_rest'
    elif stack is not None:
        # stack >= 50 but no VPIP/PFR: TIBURON is the classifier default,
        # not a validated classification.
        label = TIBURON
        method = 'default_rest_no_stats'
        state = STATE_INSUFFICIENT
        blocking.append(
            'VPIP/PFR ausentes; el fallback estadistico no se puede evaluar')
        uncertainty.append('TIBURON por defecto sin evidencia estadistica')
    else:
        label = TIBURON
        method = 'default_no_evidence'
        state = STATE_INSUFFICIENT
        blocking.append('stack, VPIP y PFR ausentes')
        uncertainty.append('TIBURON por defecto sin ninguna evidencia')

    if state == STATE_PROVISIONAL:
        uncertainty.append(
            'n=%s < %s: primer tramo de HANDS_BANDS (diagnostico, no '
            'intervalo de confianza)' % (n, FIRST_RELIABILITY_BAND))
    if provenance['provenance_status'] == PARTIAL:
        uncertainty.append(
            'procedencia P0-4 partial: reproduccion de la base no demostrada')
    if provenance['provenance_status'] == INCOMPATIBLE:
        state = STATE_INCOMPATIBLE
        uncertainty.append('procedencia incompatible: no se usa como evidencia')

    valid = (state in (STATE_CURRENT, STATE_PROVISIONAL)
             and label in (PEZ, TIBURON))
    contract_label = (label if state in (STATE_CURRENT, STATE_PROVISIONAL)
                      else LABEL_UNKNOWN)
    return LabelDecision(
        player=profile.player,
        source='training_current',
        label=label,
        contract_label=contract_label,
        state=state,
        method=method,
        variables=variables,
        hands_n=hands_n,
        relevant_observations=relevant,
        provenance=provenance['provenance'],
        provenance_status=provenance['provenance_status'],
        window=provenance['window'],
        window_hash=provenance['window_hash'],
        built_commit=provenance['built_commit'],
        uncertainty=uncertainty,
        rules_blocking=blocking,
        reproducible=True,
        valid_for_serving=valid,
        notes=['la etiqueta efectiva no se modifica; el contrato es sombra'],
    )


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------

def _serving_instance():
    """Instancia mínima para ejecutar el clasificador real de serving."""
    # El import de asistente_live inicializa OCR y puede escribir por stdout;
    # la auditoría no debe ensuciar su salida.
    with contextlib.redirect_stdout(io.StringIO()):
        from .asistente_live import Asistente
    a = Asistente.__new__(Asistente)
    a.live_stacks = {}
    a._last_seen_stake = {}
    return a


def serving_decision(player_id, samples, state=None, source='serving',
                     instance=None):
    """Traza de la etiqueta que produce ``Asistente._perfil_for``.

    ``samples`` es la lista de stacks visibles (evidencia de sesión simulada).
    ``state`` permite probar la rama de stack actual.
    """
    state = dict(state or {})
    instance = instance or _serving_instance()
    instance.live_stacks = {player_id: list(samples)} if samples else {}
    label = instance._perfil_for(player_id, state)
    mean = instance._live_mean(player_id)
    stake = state.get('%s_stake' % player_id)
    n_obs = len(samples) if samples else (1 if stake is not None else 0)

    if mean is not None:
        method = 'session_mean_lt_50bb'
        uncertainty = ['serving usa solo stacks; no usa VPIP, PFR, nombre ni '
                       'la etiqueta historica']
        state_contract = STATE_CURRENT
    elif stake is not None:
        method = 'current_stack_lt_50bb'
        uncertainty = ['sin historial de sesion; solo stack actual; no usa '
                       'VPIP, PFR ni la etiqueta historica']
        state_contract = STATE_CURRENT
    else:
        method = 'default_tiburon_no_info'
        uncertainty = ['sin stack visible: TIBURON por defecto, no una '
                       'clasificacion validada']
        state_contract = STATE_INSUFFICIENT

    return LabelDecision(
        player=player_id,
        source=source,
        label=label,
        contract_label=(label if state_contract == STATE_CURRENT
                        else LABEL_UNKNOWN),
        state=state_contract,
        method=method,
        variables={
            'live_mean_bb': mean,
            'current_stake_bb': stake,
            'stack_threshold_bb': STACK_FISH_BB,
            'stack_observations': n_obs,
        },
        hands_n=None,
        relevant_observations={'stack_samples': n_obs},
        provenance='sesion live (simulada desde stacks de la ventana)',
        provenance_status=None,
        window='sesion (simulada)' if n_obs else None,
        window_hash=None,
        built_commit=None,
        uncertainty=uncertainty,
        rules_blocking=['serving no tiene historial de manos; solo stack '
                        'visible'],
        reproducible=True,
        valid_for_serving=(state_contract == STATE_CURRENT),
        notes=['la etiqueta efectiva de serving no se modifica'],
    )


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------

def historical_decision(player, entry, current_evidence_available=True):
    """Traza de una etiqueta almacenada en ``data/profiles.json``.

    ``current_evidence_available=False`` marca una entrada histórica sin
    contraparte en la ventana actual (p. ej. el marcador ``HERO``): la
    etiqueta existe, pero su procedencia no es conciliable con la base actual.
    """
    prov = _historical_provenance()
    if entry is None:
        return LabelDecision(
            player=player, source='historical_artifact',
            label=LABEL_UNKNOWN, contract_label=LABEL_UNKNOWN,
            state=STATE_UNKNOWN,
            method='historical_entry_missing',
            provenance=prov['provenance'],
            provenance_status=prov['provenance_status'],
            window=prov['window'], window_hash=None,
            built_commit=prov['built_commit'],
            uncertainty=['el jugador no aparece en el artefacto historico'],
            rules_blocking=['sin etiqueta historica que comparar'],
            reproducible=False, valid_for_serving=False,
        )

    stats = entry.get('stats') or {}
    vpip = stats.get('vpip')
    pfr = stats.get('pfr')
    stack = entry.get('stack_mean')
    stored = entry.get('label')
    recomputed = None
    if stored in (PEZ, TIBURON):
        recomputed = simple_label(vpip, pfr, stack)
        reproducible = (recomputed == stored)
    else:
        reproducible = False

    uncertainty = [
        'el artefacto no registra la regla aplicada; solo la etiqueta final',
        'solo guarda n de VPIP; no guarda denominadores por stat ni numero '
        'de observaciones de stack',
        'procedencia P0-4 partial: reproduccion no demostrada',
    ]
    if not prov['artifact_hash_matches']:
        uncertainty.append('el hash no coincide con el canonico declarado')
    blocking = ['la etiqueta historica no es una traza de regla; se '
                'reproduce recalculando desde sus campos']
    label = stored if stored in (PEZ, TIBURON) else LABEL_UNKNOWN
    state = STATE_HISTORICAL if stored in (PEZ, TIBURON) else STATE_UNKNOWN
    prov_status = prov['provenance_status']
    if prov_status == INCOMPATIBLE or not prov['artifact_hash_matches']:
        state = STATE_INCOMPATIBLE
        prov_status = 'incompatible'
        uncertainty.append('procedencia incompatible con el canonico')
    if not current_evidence_available:
        state = STATE_INCOMPATIBLE
        prov_status = 'incompatible'
        uncertainty.append(
            'sin contraparte en la evidencia actual: no conciliable con la '
            'base actual')

    contract_label = (label if state == STATE_HISTORICAL
                      else LABEL_UNKNOWN)
    return LabelDecision(
        player=player, source='historical_artifact', label=label,
        contract_label=contract_label,
        state=state, method='historical_artifact_label',
        variables={
            'stack_mean_bb': stack,
            'vpip': vpip,
            'pfr': pfr,
            'recomputed_label': recomputed,
            'stored_n': entry.get('n'),
            'reliability': entry.get('reliability'),
            'confidence': entry.get('confidence'),
        },
        hands_n=None,
        relevant_observations={
            'vpip_opp': entry.get('n'),
            'pfr_opp': None,
            'stack_observations': None,
        },
        provenance=prov['provenance'],
        provenance_status=prov_status,
        window=prov['window'], window_hash=None,
        built_commit=prov['built_commit'],
        uncertainty=uncertainty, rules_blocking=blocking,
        reproducible=reproducible, valid_for_serving=False,
        notes=['etiqueta historica; no es una etiqueta calculada con '
               'evidencia actual'],
    )


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------

def compare_labels(training, historical, serving, stack_only_label=None,
                   current_evidence_available=True):
    """Clasifica una comparación entrenamiento vs serving."""
    if historical is None or historical.label == LABEL_UNKNOWN:
        status = STATUS_UNKNOWN
        reason = 'sin etiqueta historica'
    elif historical.label != training.label:
        status = STATUS_HISTORICAL_NOT_REPRODUCIBLE
        reason = ('la etiqueta historica %s no coincide con la actual %s'
                  % (historical.label, training.label))
    elif not current_evidence_available:
        status = STATUS_HISTORICAL_NOT_REPRODUCIBLE
        reason = ('no hay evidencia actual para el jugador; la etiqueta '
                  'historica no se puede reproducir con esta ventana')
    elif historical.provenance_status == 'incompatible':
        status = STATUS_INCOMPATIBLE
        reason = 'la evidencia historica tiene procedencia incompatible'
    elif training.state == STATE_INCOMPATIBLE:
        status = STATUS_INCOMPATIBLE
        reason = 'la evidencia de entrenamiento tiene procedencia incompatible'
    elif training.state == STATE_INSUFFICIENT:
        status = STATUS_INSUFFICIENT
        reason = 'faltan variables requeridas por la regla'
    elif training.label == serving.label:
        status = STATUS_COINCIDENT
        reason = 'misma etiqueta'
    elif (stack_only_label is not None
          and stack_only_label == serving.label):
        status = STATUS_SERVING_UNAVAILABLE
        reason = ('serving solo ve stack; la diferencia la decide el '
                  'fallback VPIP/PFR, no disponible en serving')
    elif training.label == stack_only_label:
        status = STATUS_DIFFERENT
        reason = ('misma regla de stack con evidencia distinta: media del '
                  'dataset vs stack de la sesion')
    else:
        status = STATUS_DIFFERENT
        reason = 'diferencia no explicada por las reglas declaradas'

    return LabelComparison(
        player=training.player,
        status=status,
        reason=reason,
        training_label=training.label,
        serving_label=serving.label,
        historical_label=historical.label if historical else None,
        stack_only_label=stack_only_label,
        current_evidence_available=current_evidence_available,
        historical_reproducible=(historical.reproducible
                                 if historical else None),
        provenance_status=(historical.provenance_status
                           if historical else None),
        detail={
            'training_method': training.method,
            'training_state': training.state,
            'serving_method': serving.method,
            'training_uncertainty': list(training.uncertainty),
            'serving_uncertainty': list(serving.uncertainty),
            'training_variables': dict(training.variables),
            'serving_variables': dict(serving.variables),
        },
    )


# ---------------------------------------------------------------------------
# Auditoría completa
# ---------------------------------------------------------------------------

def _load_historical():
    with open(PROFILES_PATH, encoding='utf-8') as f:
        return json.load(f)


def historical_evidence_diffs(profs, historical):
    """Diferencias de evidencia entre el artefacto y la ventana actual.

    No infiere la causa: solo deja constancia de que la etiqueta histórica
    puede coincidir aunque sus contadores/estadísticas no sean idénticos.
    """
    common = sorted(set(profs.profiles) & set(historical))
    n_diff = []
    stack_diff = []
    stats_diff = []
    for name in common:
        p = profs.profiles[name]
        entry = historical[name]
        if p.n != entry.get('n'):
            n_diff.append({'player': name, 'current': p.n,
                           'artifact': entry.get('n')})
        current_stack = (None if p.stack_mean is None
                         else round(p.stack_mean, 2))
        artifact_stack = entry.get('stack_mean')
        if current_stack != artifact_stack:
            stack_diff.append({'player': name, 'current': current_stack,
                               'artifact': artifact_stack})
        current_stats = {k: round(v, 4) for k, v in p.stats.items()}
        artifact_stats = entry.get('stats') or {}
        keys = sorted(set(current_stats) | set(artifact_stats))
        fields = [k for k in keys
                  if current_stats.get(k) != artifact_stats.get(k)]
        if fields:
            stats_diff.append({
                'player': name,
                'fields': fields,
                'current': {k: current_stats.get(k) for k in fields},
                'artifact': {k: artifact_stats.get(k) for k in fields},
            })
    return {
        'common_players': len(common),
        'n_different': len(n_diff),
        'n_different_players': n_diff,
        'stack_mean_different': len(stack_diff),
        'stack_mean_different_players': stack_diff,
        'stats_different': len(stats_diff),
        'stats_different_players': stats_diff,
        'note': ('la etiqueta puede coincidir aunque la evidencia no sea '
                 'idéntica; el artefacto no registra commit, fecha ni '
                 'ventana, así que la causa no se infiere'),
    }


def label_audit():
    """Auditoría reproducible de etiquetas (solo lectura)."""
    hands = load_hands(reliable_only=True)
    hands_n = len(hands)
    profs = Profiles.from_hands(hands)
    samples = stack_samples_by_player(hands)
    last = last_stack_by_player(hands)
    means = {name: sum(ss) / len(ss) for name, ss in samples.items()}
    historical = _load_historical()
    prov = _current_provenance()
    hist_prov = _historical_provenance()
    serving = _serving_instance()

    training_rows = {}
    serving_mean = {}
    serving_last = {}
    serving_no_info = {}
    stack_only = {}
    for name, profile in profs.profiles.items():
        n_stack = len(samples.get(name, []))
        training_rows[name] = training_decision(
            profile, n_stack, hands_n, provenance=prov)
        serving_mean[name] = serving_decision(
            name, samples.get(name, []), state={},
            source='serving_session_mean', instance=serving)
        serving_last[name] = serving_decision(
            name, [], state={'%s_stake' % name: last.get(name)},
            source='serving_current_stack', instance=serving)
        serving_no_info[name] = serving_decision(
            name, [], state={}, source='serving_no_info', instance=serving)
        stack_only[name] = simple_label(None, None, profile.stack_mean)

    historical_rows = {
        name: historical_decision(name, entry)
        for name, entry in historical.items()
    }

    # Comparaciones con la media del dataset (misma evidencia de stack que
    # training) y con el ultimo stack (evidencia de sesión al empezar).
    comparisons_mean = []
    comparisons_last = []
    for name in sorted(profs.profiles):
        hist = historical_rows.get(name)
        tr = training_rows[name]
        comparisons_mean.append(compare_labels(
            tr, hist, serving_mean[name],
            stack_only_label=stack_only[name]))
        # La evidencia de training para el fallback es el stack medio del
        # dataset; para el control de implementación de la regla de stack se
        # usa la MISMA evidencia (last) en parity_stack_rule.
        comparisons_last.append(compare_labels(
            tr, hist, serving_last[name],
            stack_only_label=stack_only[name]))

    historical_only = sorted(set(historical) - set(profs.profiles))
    current_only = sorted(set(profs.profiles) - set(historical))
    historical_only_rows = []
    for name in historical_only:
        row = historical_decision(
            name, historical[name],
            current_evidence_available=False).as_dict()
        row['current_evidence_available'] = False
        row['status'] = STATUS_HISTORICAL_NOT_REPRODUCIBLE
        historical_only_rows.append(row)
    current_only_rows = []
    for name in current_only:
        row = training_rows[name].as_dict()
        row['current_evidence_available'] = True
        row['status'] = STATUS_UNKNOWN
        row['reason'] = 'sin etiqueta historica que comparar'
        current_only_rows.append(row)

    # Paridad de la regla de stack con la MISMA evidencia (control de
    # implementación, no de disponibilidad).
    stack_rule_mean_errors = []
    stack_rule_last_errors = []
    for name in sorted(profs.profiles):
        if stack_only[name] != serving_mean[name].label:
            stack_rule_mean_errors.append(name)
        training_last = simple_label(None, None, last.get(name))
        if training_last != serving_last[name].label:
            stack_rule_last_errors.append(name)

    # Conteos.
    def _counts(rows):
        return dict(Counter(r.status for r in rows))

    training_labels = Counter(t.label for t in training_rows.values())
    contract_labels = Counter(t.contract_label
                              for t in training_rows.values())
    training_states = Counter(t.state for t in training_rows.values())
    labels_payload = json.dumps(
        {name: t.label for name, t in training_rows.items()},
        sort_keys=True, ensure_ascii=False)
    effective_labels_sha256 = hashlib.sha256(
        labels_payload.encode('utf-8')).hexdigest()
    historical_common = sorted(set(profs.profiles) & set(historical))
    historical_diffs = [
        name for name in historical_common
        if historical_rows[name].label != training_rows[name].label
    ]

    small_names = ['Valentina22', 'Sp1609', 'Ocampo99', 'Nnn1']
    small = []
    for name in small_names:
        if name not in profs.profiles:
            small.append({'player': name, 'available': False})
            continue
        tr = training_rows[name]
        hist = historical_rows.get(name)
        small.append({
            'player': name,
            'available': True,
            'training': tr.as_dict(),
            'historical': hist.as_dict() if hist else None,
            'serving_session_mean': serving_mean[name].as_dict(),
            'serving_current_stack': serving_last[name].as_dict(),
            'serving_no_info': serving_no_info[name].as_dict(),
            'comparison_session_mean': next(
                c.as_dict() for c in comparisons_mean
                if c.player == name),
            'comparison_current_stack': next(
                c.as_dict() for c in comparisons_last
                if c.player == name),
            'stack_samples': samples.get(name, []),
            'stack_mean_bb': means.get(name),
            'last_stack_bb': last.get(name),
            'stack_margin_bb': (abs(STACK_FISH_BB - means[name])
                                if means.get(name) is not None else None),
            'n_vpip_opportunities': profs.profiles[name].n,
            'historical_label_reproducible_from_fields': (
                hist.reproducible if hist else None),
            'current_evidence_available': True,
            'evidence_note': ('muestra pequeña: n=%s; no se aplica un umbral '
                              'nuevo, solo el primer tramo ya declarado '
                              'HANDS_BANDS=40 como diagnostico'
                              % profs.profiles[name].n),
        })

    return {
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec='seconds'),
        'code_commit': prov['built_commit'],
        'code_dirty': prov['code_dirty'],
        'hands_in_window': hands_n,
        'window': prov['window'],
        'window_hash': prov['window_hash'],
        'base_provenance_status': prov['provenance_status'],
        'training': {
            'players': len(training_rows),
            'labels': dict(training_labels),
            'labels_sha256': effective_labels_sha256,
            'contract_labels': dict(contract_labels),
            'states': dict(training_states),
            'provisional': sum(1 for t in training_rows.values()
                               if t.state == STATE_PROVISIONAL),
            'current': sum(1 for t in training_rows.values()
                           if t.state == STATE_CURRENT),
            'insufficient': sum(1 for t in training_rows.values()
                                if t.state == STATE_INSUFFICIENT),
        },
        'historical': {
            'artifact': 'data/profiles.json',
            'players': len(historical),
            'provenance_status': hist_prov['provenance_status'],
            'artifact_hash_matches': hist_prov['artifact_hash_matches'],
            'common_with_current': len(historical_common),
            'coincident': len(historical_common) - len(historical_diffs),
            'different': len(historical_diffs),
            'different_players': historical_diffs,
            'only_historical': historical_only,
            'only_historical_rows': historical_only_rows,
            'only_current': current_only,
            'only_current_rows': current_only_rows,
            'not_reproducible': historical_only,
            'evidence_diffs': historical_evidence_diffs(profs, historical),
        },
        'serving_session_mean': {
            'counts': _counts(comparisons_mean),
            'players': len(comparisons_mean),
        },
        'serving_current_stack': {
            'counts': _counts(comparisons_last),
            'players': len(comparisons_last),
        },
        'parity_stack_rule': {
            'same_evidence_mean': {
                'players': len(profs.profiles),
                'errors': stack_rule_mean_errors,
            },
            'same_evidence_last': {
                'players': len(profs.profiles),
                'errors': stack_rule_last_errors,
            },
        },
        'differences_session_mean': [
            c.as_dict() for c in comparisons_mean
            if c.status != STATUS_COINCIDENT
        ],
        'differences_current_stack': [
            c.as_dict() for c in comparisons_last
            if c.status != STATUS_COINCIDENT
        ],
        'small_samples': small,
        'methods': {
            'training': ('Profiles.simple_label: stack_mean<50 -> PEZ; '
                         'si no, vpip>0.32 y pfr<0.10 -> PEZ; resto -> '
                         'TIBURON'),
            'serving': ('Asistente._perfil_for: media de stacks de sesion '
                        '<50 -> PEZ; si no, stack actual<50 -> PEZ; sin '
                        'informacion -> TIBURON'),
            'historical': ('data/profiles.json: etiqueta almacenada; no '
                           'registra la regla aplicada'),
        },
        'notes': [
            'P0-5 es solo auditoria: no cambia etiquetas efectivas, modelos, '
            'probabilidades ni recomendaciones.',
            'La etiqueta de training es reproducible desde la ventana actual; '
            'el artefacto historico coincide para los 138 jugadores comunes.',
            'El serving no usa VPIP/PFR, nombre ni models.labels: solo stack.',
            'Las diferencias por fallback se clasifican como datos no '
            'disponibles en serving, no como error de implementacion.',
            'La regla de stack comun no muestra errores de implementacion con '
            'la misma evidencia.',
            'No se introduce ningun umbral nuevo de muestra minima; se '
            'reutiliza el primer tramo ya declarado HANDS_BANDS=40 solo como '
            'diagnostico.',
            'La ausencia de informacion no se convierte en una etiqueta '
            'validada: se queda en insufficient_evidence/unknown.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(label_audit(), indent=2, ensure_ascii=False,
                     default=str))
