"""Guardia de instancia y deteccion conservadora de captura compartida."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


class ConcurrencyError(RuntimeError):
    """La captura/registro ya esta ocupado por otra sesion compatible."""


def detect_original_assistants() -> Optional[list]:
    """Lista procesos originales si puede inspeccionarlos; None = desconocido.

    Se prefiere psutil. En Windows se usa una consulta de solo lectura a CIM.
    La deteccion de GUI/proceso no existe en todas las plataformas; el caso
    desconocido se informa al operador y nunca se presenta como exclusividad
    verificada.
    """
    try:
        import psutil  # type: ignore
        found = []
        for proc in psutil.process_iter(('pid', 'name', 'cmdline')):
            try:
                if proc.info.get('pid') == os.getpid():
                    continue
                name = (proc.info.get('name') or '').lower()
                command = ' '.join(proc.info.get('cmdline') or [])
                if 'python' in name and 'asistente_live' in command.lower():
                    found.append({'pid': proc.info.get('pid'),
                                  'command': command})
            except (OSError, psutil.Error):
                continue
        return found
    except ImportError:
        pass

    if os.name != 'nt':
        return None
    current_pid = os.getpid()
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -ne %d -and $_.Name -match 'python' -and "
        "$_.CommandLine -match 'asistente_live(_gui)?(\\.py)?' } | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        % current_pid)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, timeout=3, check=False)
        if result.returncode != 0:
            return None
        text = result.stdout.strip()
        if not text:
            return []
        value = json.loads(text)
        return value if isinstance(value, list) else [value]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _pid_alive(pid: int) -> Optional[bool]:
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                capture_output=True, text=True, timeout=2, check=False)
            if result.returncode != 0:
                return None
            return any(str(pid) in line.split()
                       for line in result.stdout.splitlines())
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


class CaptureSessionGuard:
    """Lock atomico por proceso experimental y comprobacion best-effort live."""

    def __init__(self, lock_path, *,
                 process_probe: Optional[Callable[[], Optional[list]]] = None,
                 pid_alive: Optional[Callable[[int], Optional[bool]]] = None,
                 require_process_detection: bool = True,
                 recheck_interval_s: float = 5.0):
        self.path = Path(lock_path).expanduser().resolve()
        self.process_probe = process_probe or detect_original_assistants
        self.pid_alive = pid_alive or _pid_alive
        self.require_process_detection = bool(require_process_detection)
        self.recheck_interval_s = max(0.0, float(recheck_interval_s))
        self._token = uuid.uuid4().hex
        self._held = False
        self.warning: Optional[str] = None
        self._last_process_check = 0.0

    @property
    def held(self) -> bool:
        return self._held

    def acquire(self) -> Optional[str]:
        if self._held:
            if (time.monotonic() - self._last_process_check
                    >= self.recheck_interval_s):
                processes = self._check_original_processes()
                self.warning = None if processes == [] else (
                    'no se pudo verificar asistente_live; cierrelo manualmente '
                    'antes de compartir captura')
            return self.warning
        processes = self._check_original_processes()
        if processes:
            raise ConcurrencyError(
                'recurso de captura ocupado: asistente_live detectado; '
                'cierrelo manualmente antes de iniciar paridad')
        if processes is None and self.require_process_detection:
            raise ConcurrencyError(
                'no se pudo verificar si asistente_live usa la captura; '
                'inicio abortado por seguridad')
        self.warning = None if processes == [] else (
            'no se pudo verificar asistente_live; cierrelo manualmente antes '
            'de compartir captura')

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'pid': os.getpid(),
            'host': socket.gethostname(),
            'token': self._token,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        for attempt in range(2):
            try:
                descriptor = os.open(
                    str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    json.dump(payload, stream, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._held = True
                return self.warning
            except FileExistsError:
                if attempt == 0 and self._remove_stale_lock():
                    continue
                raise ConcurrencyError(
                    'recurso de captura ocupado por otra sesion experimental '
                    '(%s); no se iniciara polling' % self.path)
        raise ConcurrencyError('no se pudo adquirir el lock de captura')

    def _check_original_processes(self):
        try:
            processes = self.process_probe()
        except Exception:
            processes = None
        self._last_process_check = time.monotonic()
        if processes:
            raise ConcurrencyError(
                'recurso de captura ocupado: asistente_live detectado; '
                'cierrelo manualmente antes de iniciar paridad')
        if processes is None and self.require_process_detection:
            raise ConcurrencyError(
                'no se pudo verificar si asistente_live usa la captura; '
                'inicio abortado por seguridad')
        return processes

    def _remove_stale_lock(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
            if payload.get('host') != socket.gethostname():
                return False
            pid = int(payload.get('pid'))
        except (OSError, ValueError, TypeError):
            # Archivo corrupto/host desconocido: tratarlo como ocupado.
            return False
        alive = self.pid_alive(pid)
        if alive is not False:
            return False
        try:
            self.path.unlink()
            return True
        except OSError:
            return False

    def release(self) -> None:
        if not self._held:
            return
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
            if payload.get('token') == self._token:
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
        self._held = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
