"""Contratos puros de rango/equity para el desarrollo HU (HU-P2).

Este módulo NO activa la ruta live ni escribe datos. Fija las fronteras que
faltaban entre:

- observación exacta (`ObservedRange`), que nunca se convierte en distribución;
- estadística con denominador explícito (`ActionStatistics`);
- prior con procedencia y cobertura (`GenericPrior`);
- rango estimado con reach declarado y estado vacío visible (`EstimatedRange`);
- fuerza actual y equity a showdown como resultados distintos.

Regla central: un rango vacío, una celda sin tabla o una incertidumbre no se
sustituyen por 0.0 ni por un prior plano silencioso. El resultado queda como
`empty`/`unknown` con una razón inspeccionable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

from .cards import card_id, cards_to_bits
from .hand_evaluator import equity_preflop_rango, legal_hands
from .ranges import HAND_MASKS, N_COMBOS, RangeError, RangeState
from .situation import equity_vs_range

CONTRACT = 'hu_range_contract_v1'
COVERAGE_STATES = ('exact', 'alias', 'coverage_gap', 'impossible', 'unknown')
PRIOR_SOURCES = ('flat', 'preflop_table', 'profile_template', 'alias',
                 'fallback', 'manual')


def _tuple_of_cards(value: Sequence[str], name: str,
                    allowed_lengths: Tuple[int, ...]) -> Tuple[str, ...]:
    out = tuple(value or ())
    if len(out) not in allowed_lengths:
        raise ValueError(
            f'{name} debe tener longitud {allowed_lengths}, tiene {len(out)}')
    ids = [card_id(c) for c in out]
    if len(set(ids)) != len(ids):
        raise ValueError(f'{name} repite una carta')
    return out


_STREET_BOARD_LENGTHS = {
    'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5,
}


def _validate_street_board(board: Sequence[str], street: str,
                           name: str = 'board') -> Tuple[str, ...]:
    out = tuple(board or ())
    expected = _STREET_BOARD_LENGTHS.get(street)
    if expected is None:
        raise ValueError('street inválido')
    if len(out) != expected:
        raise ValueError(
            f'{name} de {street} debe tener {expected} cartas, tiene {len(out)}')
    ids = [card_id(c) for c in out]
    if len(set(ids)) != len(ids):
        raise ValueError(f'{name} repite una carta')
    return out


def _readonly_vector(value, name: str, *, positive: bool = False) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64).copy()
    if arr.shape != (N_COMBOS,):
        raise ValueError(f'{name} debe tener forma ({N_COMBOS},), {arr.shape}')
    if not np.all(np.isfinite(arr)):
        raise ValueError(f'{name} contiene NaN o infinito')
    if np.any(arr < 0):
        raise ValueError(f'{name} contiene valores negativos')
    if positive and float(arr.sum()) <= 0:
        raise ValueError(f'{name} debe tener masa positiva')
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True)
class KnownCards:
    """Cartas conocidas con validación de duplicados entre grupos."""
    hero_hand: Tuple[str, ...] = ()
    board: Tuple[str, ...] = ()
    dead_cards: Tuple[str, ...] = ()
    known_opponent_cards: Tuple[str, ...] = ()

    def __post_init__(self):
        hero = _tuple_of_cards(self.hero_hand, 'hero_hand', (0, 2))
        board = _tuple_of_cards(self.board, 'board', (0, 3, 4, 5))
        dead = _tuple_of_cards(self.dead_cards, 'dead_cards', tuple(range(0, 6)))
        opp = _tuple_of_cards(
            self.known_opponent_cards, 'known_opponent_cards', (0, 2))
        all_cards = hero + board + dead + opp
        ids = [card_id(c) for c in all_cards]
        if len(set(ids)) != len(ids):
            raise ValueError('las cartas conocidas se solapan entre grupos')
        object.__setattr__(self, 'hero_hand', hero)
        object.__setattr__(self, 'board', board)
        object.__setattr__(self, 'dead_cards', dead)
        object.__setattr__(self, 'known_opponent_cards', opp)

    @property
    def all_cards(self) -> Tuple[str, ...]:
        return self.hero_hand + self.board + self.dead_cards + \
            self.known_opponent_cards

    @property
    def known_mask(self) -> int:
        return cards_to_bits(list(self.all_cards))

    @property
    def legal_mask(self) -> np.ndarray:
        return (HAND_MASKS & self.known_mask) == 0

    def as_dict(self) -> dict:
        return {
            'hero_hand': list(self.hero_hand),
            'board': list(self.board),
            'dead_cards': list(self.dead_cards),
            'known_opponent_cards': list(self.known_opponent_cards),
        }


@dataclass(frozen=True)
class ObservedCombo:
    """Mano observada exactamente. No es una distribución ni un prior."""
    hand_id: str
    exact_combo: Tuple[str, str]
    reveal_source: str
    reveal_event: str
    data_snapshot_hash: str

    def __post_init__(self):
        combo = tuple(self.exact_combo or ())
        if len(combo) != 2 or combo[0] == combo[1]:
            raise ValueError('exact_combo debe tener 2 cartas distintas')
        card_id(combo[0])
        card_id(combo[1])
        for name in ('hand_id', 'reveal_source', 'reveal_event',
                     'data_snapshot_hash'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} no puede estar vacío')
        object.__setattr__(self, 'exact_combo', combo)

    def as_dict(self) -> dict:
        return {
            'hand_id': self.hand_id,
            'exact_combo': list(self.exact_combo),
            'reveal_source': self.reveal_source,
            'reveal_event': self.reveal_event,
            'data_snapshot_hash': self.data_snapshot_hash,
        }


@dataclass(frozen=True)
class ObservedRange:
    """Conjunto de manos mostradas/observadas, sin normalización."""
    player: str
    street: str
    board: Tuple[str, ...]
    observations: Tuple[ObservedCombo, ...]
    source_window: str
    data_snapshot_hash: str

    def __post_init__(self):
        if self.street not in ('preflop', 'flop', 'turn', 'river'):
            raise ValueError('street inválido')
        board = _validate_street_board(self.board, self.street)
        board_ids = {card_id(c) for c in board}
        observations = tuple(self.observations or ())
        if any(not isinstance(o, ObservedCombo) for o in observations):
            raise TypeError('observations debe contener ObservedCombo')
        for observation in observations:
            if any(card_id(c) in board_ids for c in observation.exact_combo):
                raise ValueError(
                    'un combo observado contiene una carta del board')
        for name in ('player', 'source_window', 'data_snapshot_hash'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} no puede estar vacío')
        object.__setattr__(self, 'board', board)
        object.__setattr__(self, 'observations', observations)

    @property
    def n_observations(self) -> int:
        return len(self.observations)

    @property
    def is_distribution(self) -> bool:
        return False

    def as_dict(self) -> dict:
        return {
            'player': self.player,
            'street': self.street,
            'board': list(self.board),
            'n_observations': self.n_observations,
            'observations': [o.as_dict() for o in self.observations],
            'source_window': self.source_window,
            'data_snapshot_hash': self.data_snapshot_hash,
            'is_distribution': False,
        }


@dataclass(frozen=True)
class ActionStatistics:
    """Frecuencia con denominador y, si existe, intervalo declarado."""
    scope: str
    spot: str
    action: str
    numerator: int
    denominator: int
    frequency: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    ci_method: Optional[str] = None
    source_window: Optional[str] = None
    data_snapshot_hash: Optional[str] = None
    filters: Optional[Mapping[str, Any]] = None

    def __post_init__(self):
        for name in ('numerator', 'denominator'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f'{name} debe ser entero')
            if value < 0:
                raise ValueError(f'{name} no puede ser negativo')
        if self.numerator > self.denominator:
            raise ValueError('numerator no puede superar denominator')
        if not self.scope or not self.spot or not self.action:
            raise ValueError('scope, spot y action son obligatorios')

        expected = (self.numerator / self.denominator
                    if self.denominator else None)
        if self.frequency is None and expected is not None:
            object.__setattr__(self, 'frequency', expected)
        if self.frequency is not None:
            if expected is None:
                raise ValueError('sin denominador no hay frecuencia')
            if not np.isfinite(self.frequency) or not 0.0 <= self.frequency <= 1.0:
                raise ValueError('frequency debe estar en [0,1]')
            if abs(float(self.frequency) - expected) > 1e-12:
                raise ValueError('frequency no coincide con numerator/denominator')

        if (self.ci_low is None) != (self.ci_high is None):
            raise ValueError('ci_low y ci_high deben venir juntos')
        if self.ci_low is not None:
            if self.denominator <= 0 or self.frequency is None:
                raise ValueError(
                    'un intervalo exige denominador y frecuencia calculable')
            if not self.ci_method:
                raise ValueError('un intervalo exige ci_method')
            if not (0.0 <= self.ci_low <= self.ci_high <= 1.0):
                raise ValueError('intervalo de confianza inválido')
            if not (self.ci_low - 1e-12 <= self.frequency
                    <= self.ci_high + 1e-12):
                raise ValueError('frequency fuera de su intervalo declarado')
        elif self.ci_method is not None:
            raise ValueError('ci_method sin intervalo no es verificable')

    def as_dict(self) -> dict:
        return {
            'scope': self.scope,
            'spot': self.spot,
            'action': self.action,
            'numerator': self.numerator,
            'denominator': self.denominator,
            'frequency': self.frequency,
            'ci_low': self.ci_low,
            'ci_high': self.ci_high,
            'ci_method': self.ci_method,
            'source_window': self.source_window,
            'data_snapshot_hash': self.data_snapshot_hash,
            'filters': dict(self.filters or {}),
        }


@dataclass(frozen=True)
class GenericPrior:
    """Prior operativo con vector, procedencia y cobertura explícitas."""
    key: str
    vector: np.ndarray
    source: str
    coverage: str
    alias_of: Optional[str] = None
    source_key: Optional[str] = None
    fallback_key: Optional[str] = None
    fallback_reason: Optional[str] = None
    provenance: Optional[Mapping[str, Any]] = None
    version: str = CONTRACT
    data_snapshot_hash: Optional[str] = None

    def __post_init__(self):
        if not self.key:
            raise ValueError('key no puede estar vacío')
        if self.source not in PRIOR_SOURCES:
            raise ValueError('source de prior inválido')
        if self.coverage not in COVERAGE_STATES:
            raise ValueError('coverage de prior inválido')
        arr = _readonly_vector(self.vector, 'vector', positive=True)
        object.__setattr__(self, 'vector', arr)
        if self.source == 'flat' and self.coverage in ('exact', 'alias'):
            raise ValueError('flat no puede presentarse como exacto ni alias')
        if self.coverage == 'alias':
            if not self.alias_of or not self.source_key:
                raise ValueError('coverage alias exige alias_of y source_key')
            if self.source_key != self.alias_of:
                raise ValueError('source_key debe coincidir con alias_of')
        elif self.alias_of is not None:
            raise ValueError('alias_of solo aplica a coverage alias')
        if self.source == 'alias' and self.coverage != 'alias':
            raise ValueError('source alias exige coverage alias')
        if self.source == 'fallback':
            if not self.fallback_key or not self.fallback_reason:
                raise ValueError(
                    'source fallback exige fallback_key y fallback_reason')
        if self.fallback_key is not None and self.coverage != 'coverage_gap':
            raise ValueError('fallback_key solo aplica a coverage_gap')
        if self.fallback_reason is not None and self.coverage != 'coverage_gap':
            raise ValueError('fallback_reason solo aplica a coverage_gap')
        if (self.coverage == 'coverage_gap'
                and (self.fallback_key is None) !=
                (self.fallback_reason is None)):
            raise ValueError('fallback_key y fallback_reason deben venir juntos')
        if (self.source in ('preflop_table', 'profile_template')
                and not self.provenance):
            raise ValueError('la fuente historica exige provenance no vacia')

    @classmethod
    def flat(cls, key: str = 'flat', *, value: float = 1.0,
             coverage: str = 'unknown', source: str = 'flat') -> 'GenericPrior':
        if value <= 0:
            raise ValueError('value debe ser positivo')
        return cls(key=key, vector=np.full(N_COMBOS, value, dtype=np.float64),
                   source=source, coverage=coverage)

    @property
    def mass(self) -> float:
        return float(self.vector.sum())

    def as_dict(self) -> dict:
        return {
            'key': self.key,
            'source': self.source,
            'coverage': self.coverage,
            'alias_of': self.alias_of,
            'source_key': self.source_key,
            'fallback_key': self.fallback_key,
            'fallback_reason': self.fallback_reason,
            'mass': self.mass,
            'version': self.version,
            'data_snapshot_hash': self.data_snapshot_hash,
            'provenance': dict(self.provenance or {}),
        }


@dataclass(frozen=True)
class EstimatedRange:
    """Posterior y reach separados, con estado vacío no silencioso."""
    player: str
    street: str
    board: Tuple[str, ...]
    prior_key: str
    prior_source: str
    coverage: str
    likelihood_model: str
    unnormalized_weights: np.ndarray
    posterior: Optional[np.ndarray]
    reach: Optional[np.ndarray]
    reach_role: str
    n_obs: int
    n_opp: int
    n_eff: Optional[float]
    empty_status: str
    empty_reason: Optional[str]
    data_snapshot_hash: Optional[str] = None
    version: str = CONTRACT

    def __post_init__(self):
        if self.street not in ('preflop', 'flop', 'turn', 'river'):
            raise ValueError('street inválido')
        board = _validate_street_board(self.board, self.street)
        if self.coverage not in COVERAGE_STATES:
            raise ValueError('coverage inválido')
        if self.empty_status not in ('usable', 'empty', 'unknown',
                                     'unsupported'):
            raise ValueError('empty_status inválido')
        if self.reach_role not in ('none', 'likelihood_component',
                                   'diagnostic_only', 'independent_factor'):
            raise ValueError('reach_role inválido')
        unnormalized = _readonly_vector(
            self.unnormalized_weights, 'unnormalized_weights')
        object.__setattr__(self, 'unnormalized_weights', unnormalized)
        if self.posterior is not None:
            post = _readonly_vector(self.posterior, 'posterior')
            total = float(post.sum())
            if abs(total - 1.0) > 1e-9:
                raise ValueError('posterior debe sumar 1')
            object.__setattr__(self, 'posterior', post)
        if self.reach is not None:
            reach = _readonly_vector(self.reach, 'reach')
            object.__setattr__(self, 'reach', reach)
        if self.reach is None and self.reach_role != 'none':
            raise ValueError('sin reach, reach_role debe ser none')
        if self.reach is not None and self.reach_role == 'none':
            raise ValueError('reach presente exige reach_role')
        if self.empty_status == 'usable':
            if self.posterior is None:
                raise ValueError('usable exige posterior')
            if self.empty_reason is not None:
                raise ValueError('usable no lleva empty_reason')
        else:
            if self.posterior is not None:
                raise ValueError('estado no usable no produce posterior')
            if not self.empty_reason:
                raise ValueError('estado no usable exige empty_reason')
        for name in ('n_obs', 'n_opp'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f'{name} debe ser entero')
            if value < 0:
                raise ValueError(f'{name} no puede ser negativo')
        if self.n_obs > self.n_opp:
            raise ValueError('n_obs no puede superar n_opp')
        if self.n_eff is not None:
            if not np.isfinite(self.n_eff) or self.n_eff < 0:
                raise ValueError('n_eff debe ser finito y no negativo')
        object.__setattr__(self, 'board', board)

    @property
    def usable(self) -> bool:
        return self.empty_status == 'usable'

    def as_dict(self) -> dict:
        return {
            'player': self.player,
            'street': self.street,
            'board': list(self.board),
            'prior_key': self.prior_key,
            'prior_source': self.prior_source,
            'coverage': self.coverage,
            'likelihood_model': self.likelihood_model,
            'posterior_mass': (float(self.posterior.sum())
                               if self.posterior is not None else None),
            'reach_role': self.reach_role,
            'n_obs': self.n_obs,
            'n_opp': self.n_opp,
            'n_eff': self.n_eff,
            'empty_status': self.empty_status,
            'empty_reason': self.empty_reason,
            'version': self.version,
            'data_snapshot_hash': self.data_snapshot_hash,
        }


def _empty_reason(prior: GenericPrior, likelihood: np.ndarray,
                  reach: Optional[np.ndarray], legal: np.ndarray,
                  weights: np.ndarray) -> str:
    if not np.any(legal):
        return 'blocked_by_known_cards'
    if float((prior.vector * legal).sum()) <= 0:
        return 'prior_empty_after_blockers'
    if float((likelihood * legal).sum()) <= 0:
        return 'likelihood_zero_after_blockers'
    if reach is not None and float((reach * legal).sum()) <= 0:
        return 'reach_zero_after_blockers'
    if float((weights * legal).sum()) <= 0:
        return 'weights_zero'
    return 'empty_range'


def build_estimated_range(*, player: str, street: str, board: Sequence[str],
                          prior: GenericPrior, likelihood: Sequence[float],
                          known_cards: Optional[KnownCards] = None,
                          reach: Optional[Sequence[float]] = None,
                          reach_role: str = 'none',
                          likelihood_model: str = 'declared_likelihood',
                          n_obs: int = 0, n_opp: int = 0,
                          data_snapshot_hash: Optional[str] = None
                          ) -> EstimatedRange:
    """P(H | evidencia) = normalizar(prior · likelihood · reach aplicable).

    `reach_role='likelihood_component'` significa que el caller YA incluyó el
    reach dentro de `likelihood`: no se multiplica otra vez.
    `reach_role='independent_factor'` lo multiplica una sola vez.
    `reach_role='diagnostic_only'` lo conserva como diagnóstico, sin peso.
    """
    if not isinstance(prior, GenericPrior):
        raise TypeError('prior debe ser GenericPrior')
    board = _validate_street_board(board, street)
    if known_cards is not None:
        if not isinstance(known_cards, KnownCards):
            raise TypeError('known_cards debe ser KnownCards')
        if tuple(known_cards.board) != board:
            raise ValueError(
                'known_cards.board no coincide con el board del calculo')
    if reach_role not in ('none', 'likelihood_component', 'diagnostic_only',
                          'independent_factor'):
        raise ValueError('reach_role inválido')
    like = np.asarray(likelihood, dtype=np.float64)
    if like.shape != (N_COMBOS,):
        raise ValueError(f'likelihood debe tener forma ({N_COMBOS},)')
    if not np.all(np.isfinite(like)) or np.any(like < 0):
        raise ValueError('likelihood debe ser finito y no negativo')
    reach_arr = None
    if reach is not None:
        reach_arr = _readonly_vector(reach, 'reach')
    if reach_arr is None and reach_role != 'none':
        raise ValueError('reach_role distinto de none exige reach')
    if reach_arr is not None and reach_role == 'none':
        raise ValueError('reach presente exige reach_role')

    legal = (known_cards.legal_mask if known_cards is not None
             else np.ones(N_COMBOS, dtype=bool))
    weights = prior.vector * like
    if reach_arr is not None and reach_role == 'independent_factor':
        weights = weights * reach_arr
    weights = weights * legal

    total = float(weights.sum())
    unnormalized = weights.copy()
    unnormalized.setflags(write=False)
    if total <= 0:
        return EstimatedRange(
            player=player, street=street, board=board,
            prior_key=prior.key, prior_source=prior.source,
            coverage=prior.coverage, likelihood_model=likelihood_model,
            unnormalized_weights=unnormalized, posterior=None,
            reach=reach_arr, reach_role=reach_role, n_obs=n_obs, n_opp=n_opp,
            n_eff=None, empty_status='empty',
            empty_reason=_empty_reason(prior, like, reach_arr, legal, weights),
            data_snapshot_hash=(data_snapshot_hash
                                or prior.data_snapshot_hash),
        )

    posterior = weights / total
    posterior.setflags(write=False)
    n_eff = (total * total / float((weights * weights).sum())
             if float((weights * weights).sum()) > 0 else None)
    return EstimatedRange(
        player=player, street=street, board=board,
        prior_key=prior.key, prior_source=prior.source,
        coverage=prior.coverage, likelihood_model=likelihood_model,
        unnormalized_weights=unnormalized, posterior=posterior,
        reach=reach_arr, reach_role=reach_role, n_obs=n_obs, n_opp=n_opp,
        n_eff=n_eff, empty_status='usable', empty_reason=None,
        data_snapshot_hash=(data_snapshot_hash or prior.data_snapshot_hash),
    )


@dataclass(frozen=True)
class CurrentBoardStrength:
    """Fuerza contra el rango en el board actual, sin sortear runouts."""
    hero_hand: Tuple[str, str]
    board: Tuple[str, ...]
    value: Optional[float]
    method: str
    coverage: str
    n_combos: int
    result_definition: str = 'wins + 0.5 * ties'
    reason: Optional[str] = None
    evaluator_version: str = CONTRACT

    def __post_init__(self):
        hero = _tuple_of_cards(self.hero_hand, 'hero_hand', (2,))
        board = _tuple_of_cards(self.board, 'board', (3, 4, 5))
        object.__setattr__(self, 'hero_hand', hero)
        object.__setattr__(self, 'board', board)
        if self.coverage not in ('usable', 'unknown'):
            raise ValueError('coverage inválido')
        if self.coverage == 'usable':
            if self.value is None:
                raise ValueError('coverage usable exige value')
            if self.reason is not None:
                raise ValueError('coverage usable no lleva reason')
        else:
            if self.value is not None:
                raise ValueError('coverage unknown no produce value')
            if not self.reason:
                raise ValueError('coverage unknown exige reason')
        if self.value is not None:
            if not np.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
                raise ValueError('value debe estar en [0,1]')
        if self.n_combos < 0:
            raise ValueError('n_combos no puede ser negativo')

    def as_dict(self) -> dict:
        return {
            'hero_hand': list(self.hero_hand),
            'board': list(self.board),
            'value': self.value,
            'method': self.method,
            'coverage': self.coverage,
            'n_combos': self.n_combos,
            'result_definition': self.result_definition,
            'reason': self.reason,
            'evaluator_version': self.evaluator_version,
        }


def current_board_strength(hero_codes: Sequence[str],
                           board_codes: Sequence[str],
                           villain_reach=None,
                           villain_ids: Optional[Sequence[int]] = None
                           ) -> CurrentBoardStrength:
    """Equity actual (wins + 0.5 ties) contra el rango, sin runout."""
    hero = _tuple_of_cards(hero_codes, 'hero_codes', (2,))
    board = _tuple_of_cards(board_codes, 'board_codes', (3, 4, 5))
    known = KnownCards(hero_hand=hero, board=board)
    if villain_ids is None:
        ids = legal_hands(known.known_mask)
    else:
        ids = np.asarray(villain_ids, dtype=np.intp)
        if ids.ndim != 1 or ids.size == 0:
            return CurrentBoardStrength(
                hero_hand=hero, board=board, value=None,
                method='equity_vs_range_current_board', coverage='unknown',
                n_combos=0, reason='villain_ids_vacio_o_invalido')
        if len(set(int(i) for i in ids)) != int(ids.size):
            raise ValueError('villain_ids no puede contener duplicados')
    try:
        equity, _wins, _ties, _losses = equity_vs_range(
            hero, board, villain_reach=villain_reach, villain_ids=ids)
    except (RangeError, ValueError) as exc:
        return CurrentBoardStrength(
            hero_hand=hero, board=board, value=None,
            method='equity_vs_range_current_board', coverage='unknown',
            n_combos=int(len(ids)), reason=str(exc))
    return CurrentBoardStrength(
        hero_hand=hero, board=board, value=float(equity),
        method='equity_vs_range_current_board', coverage='usable',
        n_combos=int(len(ids)),
    )


@dataclass(frozen=True)
class EquityToShowdown:
    """Equity a showdown, separada de la fuerza actual."""
    hero_hand: Tuple[str, str]
    board: Tuple[str, ...]
    value: Optional[float]
    method: str
    n_runouts: int
    n_combos_sampled: int
    seed: int
    result_definition: str = 'expected_showdown_share'
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    uncertainty_reason: Optional[str] = None
    evaluator_version: str = CONTRACT

    def __post_init__(self):
        hero = _tuple_of_cards(self.hero_hand, 'hero_hand', (2,))
        board = _tuple_of_cards(self.board, 'board', (0, 3, 4, 5))
        object.__setattr__(self, 'hero_hand', hero)
        object.__setattr__(self, 'board', board)
        if self.value is None:
            if not self.uncertainty_reason:
                raise ValueError('sin valor se exige uncertainty_reason')
        elif not np.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError('value debe estar en [0,1]')
        if self.n_runouts < 0 or self.n_combos_sampled < 0:
            raise ValueError('conteos de muestreo no pueden ser negativos')
        if (self.ci_low is None) != (self.ci_high is None):
            raise ValueError('ci_low y ci_high deben venir juntos')
        if self.ci_low is not None or self.ci_high is not None:
            raise ValueError(
                'intervalos no soportados sin metodo estadistico definido')

    def as_dict(self) -> dict:
        return {
            'hero_hand': list(self.hero_hand),
            'board': list(self.board),
            'value': self.value,
            'method': self.method,
            'n_runouts': self.n_runouts,
            'n_combos_sampled': self.n_combos_sampled,
            'seed': self.seed,
            'result_definition': self.result_definition,
            'ci_low': self.ci_low,
            'ci_high': self.ci_high,
            'uncertainty_reason': self.uncertainty_reason,
            'evaluator_version': self.evaluator_version,
        }


def equity_to_showdown(hero_codes: Sequence[str],
                       board_codes: Sequence[str],
                       villain_reach=None,
                       n_runouts: int = 100,
                       n_combos: int = 200,
                       seed: int = 7) -> EquityToShowdown:
    """Equity a showdown; los intervalos no se inventan si no hay modelo."""
    hero = _tuple_of_cards(hero_codes, 'hero_codes', (2,))
    board = _tuple_of_cards(board_codes, 'board_codes', (0, 3, 4, 5))
    known = KnownCards(hero_hand=hero, board=board)
    n_legal = int(legal_hands(known.known_mask).size)
    try:
        if not board:
            value = float(equity_preflop_rango(
                hero, villain_reach, n_runouts=n_runouts, n_combos=n_combos,
                seed=seed))
            return EquityToShowdown(
                hero_hand=hero, board=board, value=value,
                method='preflop_combo_mc', n_runouts=0,
                n_combos_sampled=min(int(n_combos), n_legal), seed=seed,
                uncertainty_reason='combo_sampling_variance_not_quantified')
        from .decision import runout_equity
        value = float(runout_equity(
            hero, board, villain_reach=villain_reach, n_runouts=n_runouts,
            n_combos=n_combos, seed=seed))
        if len(board) == 5:
            return EquityToShowdown(
                hero_hand=hero, board=board, value=value,
                method='river_exact', n_runouts=0, n_combos_sampled=n_legal,
                seed=seed)
        # `runout_equity` evalua todos los combos legales; `n_combos` solo
        # interviene en el muestreo preflop. El metadato informa lo calculado.
        return EquityToShowdown(
            hero_hand=hero, board=board, value=value,
            method='runout_mc', n_runouts=int(n_runouts),
            n_combos_sampled=n_legal, seed=seed,
            uncertainty_reason='ci_not_available_without_variance_model')
    except (RangeError, ValueError) as exc:
        return EquityToShowdown(
            hero_hand=hero, board=board, value=None,
            method='unavailable', n_runouts=int(max(0, n_runouts)),
            n_combos_sampled=0, seed=seed, uncertainty_reason=str(exc))


def estimated_range_to_state(estimated: EstimatedRange) -> RangeState:
    """Adaptador explícito a `RangeState`; no normaliza un rango vacío."""
    if not isinstance(estimated, EstimatedRange):
        raise TypeError('estimated debe ser EstimatedRange')
    if not estimated.usable or estimated.posterior is None:
        raise RangeError('rango estimado vacío: %s'
                         % (estimated.empty_reason or 'sin motivo'))
    return RangeState(reach=estimated.posterior, source='hu_estimated_range')
