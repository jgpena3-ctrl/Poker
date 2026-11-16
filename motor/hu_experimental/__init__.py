"""Asistente HU experimental aislado (Fase 10).

Este paquete no importa ``motor.asistente_live`` ni ``recommend_loop``. Su
objetivo es observar una mesa HU, interpretar el estado disponible y producir
una prediccion experimental trazable. No ejecuta acciones ni escribe en el
dataset historico.
"""
from .assistant import (  # noqa: F401
    EXPERIMENTAL_VERSION,
    ExperimentalAnalysis,
    HUExperimentalAssistant,
    PredictionRegistration,
)
from .capture import CaptureError, CapturedFrame, HUCaptureAdapter  # noqa: F401
from .config import ExperimentalConfig  # noqa: F401
from .state import HUState, StateInterpretationError, interpret_state  # noqa: F401

__all__ = [
    'EXPERIMENTAL_VERSION',
    'CaptureError',
    'CapturedFrame',
    'ExperimentalAnalysis',
    'ExperimentalConfig',
    'HUCaptureAdapter',
    'HUExperimentalAssistant',
    'HUState',
    'PredictionRegistration',
    'StateInterpretationError',
    'interpret_state',
]
