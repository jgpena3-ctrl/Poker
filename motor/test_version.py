"""La versión registrada no puede ser nula ni inventarse."""
import os
import subprocess

from motor.version import ENV_VAR, motor_version


def test_motor_version_nunca_es_nula_ni_vacia(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    version = motor_version()
    assert isinstance(version, str)
    assert version.strip()


def test_override_explicito_gana(monkeypatch):
    monkeypatch.setenv(ENV_VAR, 'replay-test')
    assert motor_version() == 'replay-test'


def test_version_corresponde_al_commit_o_lo_marca_dirty(monkeypatch):
    """Un árbol limpio es el commit; uno sucio no puede afirmar serlo."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))),
            text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    version = motor_version()
    if not commit:
        assert version == 'unversioned'
        return
    assert version in (commit, f'{commit}-dirty')
