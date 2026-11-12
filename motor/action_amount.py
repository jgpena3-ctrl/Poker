# -*- coding: utf-8 -*-
"""Representación común del importe de una acción.

No completa datos ausentes. El valor medido y su procedencia son dimensiones
separadas: `amount=None` no es cero; un importe numérico sin `amount_type` no
se convierte por inferencia en observado/canónico.
"""
from dataclasses import asdict, dataclass
import math
from typing import Any, Optional


KNOWN_ZERO = 'known_zero'
KNOWN_POSITIVE = 'known_positive'
ABSENT = 'absent'
INVALID = 'invalid'

ORIGIN_CANONICAL = 'canonical_observed'
ORIGIN_DERIVED = 'derived'
ORIGIN_NON_CANONICAL = 'non_canonical'
ORIGIN_UNKNOWN = 'unknown'

_MISSING = object()
_DERIVED_TYPES = frozenset({
    'derived', 'delta', 'stack_delta', 'reconstructed', 'inferred',
})


@dataclass(frozen=True)
class AmountEvidence:
    value: Optional[float]
    value_status: str
    origin_status: str
    raw_value: Any = None
    amount_type: Optional[str] = None
    amount_type_present: bool = False
    action_inferred: bool = False

    def as_dict(self):
        return asdict(self)


def classify_amount(action) -> AmountEvidence:
    """Clasifica importe y origen sin sustituir una ausencia por cero."""
    if isinstance(action, dict):
        raw = action.get('amount', _MISSING)
        amount_type_present = 'amount_type' in action
        amount_type = action.get('amount_type')
        inferred = bool(action.get('inferred'))
    else:
        raw = action if action is not _MISSING else _MISSING
        amount_type_present = False
        amount_type = None
        inferred = False

    if raw is _MISSING or raw is None or raw == '':
        value, value_status = None, ABSENT
    elif isinstance(raw, bool) or not isinstance(raw, (int, float)):
        value, value_status = None, INVALID
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError):
            value, value_status = None, INVALID
        else:
            if not math.isfinite(value) or value < 0:
                value, value_status = None, INVALID
            elif value == 0:
                value_status = KNOWN_ZERO
            else:
                value_status = KNOWN_POSITIVE

    if not amount_type_present:
        origin_status = ORIGIN_UNKNOWN
    elif amount_type == 'observed':
        origin_status = ORIGIN_CANONICAL
    elif str(amount_type).strip().lower() in _DERIVED_TYPES:
        origin_status = ORIGIN_DERIVED
    else:
        origin_status = ORIGIN_NON_CANONICAL

    raw_value = None if raw is _MISSING else raw
    return AmountEvidence(
        value=value,
        value_status=value_status,
        origin_status=origin_status,
        raw_value=raw_value,
        amount_type=amount_type,
        amount_type_present=amount_type_present,
        action_inferred=inferred,
    )
