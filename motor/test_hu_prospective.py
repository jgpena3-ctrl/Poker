import json
import math
import os
import tempfile

import pytest

from motor.hu_prospective import (
    HUPrediction, HUOutcome, ProspectiveHURegistry, _safe_storage_path)


def test_register_prediction(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    pred = HUPrediction(prediction_id="p1", emitted_at="2026-01-01T10:00:00",
                        hero_position="BTN", canonical_status="resolved",
                        pot=10.0, to_call=2.0, hero_stack=10.0)
    event = reg.register_prediction(pred)
    assert event["event_type"] == "HU_PREDICTION"
    assert event["event_id"] == "p1"
    assert path.exists()
    assert len(reg.read_events()) == 1


def test_register_outcome(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    out = HUOutcome(outcome_id="o1", prediction_id="p1",
                    observed_at="2026-01-01T10:05:00",
                    observed_action="call")
    event = reg.register_outcome(out)
    assert event["event_type"] == "HU_OUTCOME"
    assert len(reg.read_events()) == 2


def test_register_na_outcome_when_prediction_was_not_applicable(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(
        prediction_id="p1", emitted_at="2026-01-01T10:00:00",
        hero_position="BTN", canonical_status="unresolved"))

    event = reg.register_outcome(HUOutcome(
        outcome_id="o1", prediction_id="p1",
        observed_at="2026-01-01T10:05:00", observed_action="n/a"))

    assert event["payload"]["observed_action"] == "n/a"


def test_outcome_requires_prediction(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_outcome(HUOutcome(outcome_id="o1", prediction_id="missing",
                                      observed_at="2026-01-01T10:05:00"))


def test_duplicate_event_id(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(prediction_id="p1",
                                             emitted_at="2026-01-01T10:01:00",
                                             hero_position="BTN",
                                             canonical_status="resolved"))


def test_prediction_not_overwritten(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    before = path.read_bytes()
    reg.register_outcome(HUOutcome(outcome_id="o1", prediction_id="p1",
                                  observed_at="2026-01-01T10:05:00"))
    after = path.read_bytes()
    assert before in after
    pred = reg.get_prediction("p1")
    assert "observed_action" not in pred["payload"]


def test_future_timestamp_in_prediction_rejected(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="not-a-timestamp",
            hero_position="BTN", canonical_status="resolved"))


def test_missing_fields_allowed(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    event = reg.register_prediction(HUPrediction(
        prediction_id="p1", emitted_at="2026-01-01T10:00:00",
        hero_position="BTN", canonical_status="unresolved"))
    assert event["payload"]["pot"] is None
    assert event["payload"]["equity"] is None


def test_unknown_values_not_converted(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    event = reg.register_prediction(HUPrediction(
        prediction_id="p1", emitted_at="2026-01-01T10:00:00",
        hero_position="BTN", canonical_status="unresolved",
        coverage_state="unknown", equity=None))
    assert event["payload"]["coverage_state"] == "unknown"
    assert event["payload"]["equity"] is None


def test_invalid_probability(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="2026-01-01T10:00:00",
            hero_position="BTN", canonical_status="resolved",
            response_distribution={"fold": 0.5, "call": 0.4}))


def test_incoherent_economics(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="2026-01-01T10:00:00",
            hero_position="BTN", canonical_status="resolved",
            pot=-1.0))


def test_malformed_event(tmp_path):
    path = tmp_path / "pilot.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.read_events()


def test_write_failure_no_partial(tmp_path, monkeypatch):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)

    def fail_write(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(type(path), "open", fail_write)
    with pytest.raises(OSError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="2026-01-01T10:00:00",
            hero_position="BTN", canonical_status="resolved"))
    assert not path.exists() or path.read_text(encoding="utf-8") == ""


def test_previous_events_intact(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    first_bytes = path.read_bytes()
    reg.register_prediction(HUPrediction(prediction_id="p2",
                                         emitted_at="2026-01-01T10:01:00",
                                         hero_position="BB",
                                         canonical_status="resolved"))
    assert path.read_bytes().startswith(first_bytes)


def test_reject_protected_path():
    with pytest.raises(ValueError):
        ProspectiveHURegistry("data/hands_db.jsonl")
    with pytest.raises(ValueError):
        ProspectiveHURegistry("data")


def test_reproduce_without_modifying_bytes(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    before = path.read_bytes()
    _ = reg.read_events()
    assert path.read_bytes() == before


def test_no_future_data_in_prediction(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="2026-01-01T10:00:00",
            hero_position="BTN", canonical_status="resolved",
            metadata={"final_pot": 100.0}))


def test_outcome_timestamp_order(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    with pytest.raises(ValueError):
        reg.register_outcome(HUOutcome(outcome_id="o1", prediction_id="p1",
                                      observed_at="2026-01-01T09:59:00"))


def test_canonical_hash_present(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    event = reg.register_prediction(HUPrediction(prediction_id="p1",
                                                 emitted_at="2026-01-01T10:00:00",
                                                 hero_position="BTN",
                                                 canonical_status="resolved"))
    assert "canonical_hash" in event
    assert len(event["canonical_hash"]) == 64

def test_nested_future_data_rejected(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    with pytest.raises(ValueError):
        reg.register_prediction(HUPrediction(
            prediction_id="p1", emitted_at="2026-01-01T10:00:00",
            hero_position="BTN", canonical_status="resolved",
            metadata={"nested": {"final_pot": 100.0}}))


def test_symlink_to_protected_data_rejected(tmp_path):
    link = tmp_path / "alias.jsonl"
    target = (tmp_path / ".." / "data" / "hands_db.jsonl").resolve()
    if not target.exists():
        pytest.skip("protected target unavailable")
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        ProspectiveHURegistry(link)

def test_verify_integrity_ok(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    res = reg.verify_integrity()
    assert res.ok is True
    assert res.event_count == 1
    assert res.issues == ()


def test_verify_detects_hash_tampering(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    # Tamper with bytes without updating hash.
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["payload"]["pot"] = 999.0
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    res = reg.verify_integrity()
    assert res.ok is False
    assert any("hash incorrecto" in issue for issue in res.issues)


def test_verify_detects_truncated_event(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    data = path.read_bytes()
    path.write_bytes(data[:-5])
    res = reg.verify_integrity()
    assert res.ok is False
    assert res.truncated is True


def test_second_writer_rejected(tmp_path):
    path = tmp_path / "pilot.jsonl"
    reg1 = ProspectiveHURegistry(path)
    reg2 = ProspectiveHURegistry(path)
    reg1.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    # Simulate an active lock.
    reg1.lock_path.write_text(str(os.getpid()), encoding="utf-8")
    with pytest.raises(RuntimeError):
        reg2.register_prediction(HUPrediction(prediction_id="p2",
                                             emitted_at="2026-01-01T10:01:00",
                                             hero_position="BB",
                                             canonical_status="resolved"))
    reg1.lock_path.unlink(missing_ok=True)


def test_backup_and_restore(tmp_path):
    path = tmp_path / "pilot.jsonl"
    backup = tmp_path / "backup.jsonl"
    restored = tmp_path / "restored.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    original_hash = reg.verify_integrity().event_count
    result = reg.create_backup(backup)
    assert backup.exists()
    assert (backup.with_name(backup.name + ".sha256")).exists()
    assert result.event_count == 1
    reg.restore_backup(backup, destination=restored, overwrite=False)
    restored_reg = ProspectiveHURegistry(restored)
    assert restored_reg.verify_integrity().ok is True
    assert restored_reg.read_events() == reg.read_events()


def test_restore_rejects_existing_destination(tmp_path):
    path = tmp_path / "pilot.jsonl"
    backup = tmp_path / "backup.jsonl"
    restored = tmp_path / "restored.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    reg.create_backup(backup)
    restored.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        reg.restore_backup(backup, destination=restored, overwrite=False)


def test_backup_corrupt_rejected(tmp_path):
    path = tmp_path / "pilot.jsonl"
    backup = tmp_path / "backup.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved"))
    reg.create_backup(backup)
    # Corrupt backup.
    backup.write_text("{bad json}\n", encoding="utf-8")
    result = reg.verify_backup(backup)
    assert result.ok is False


def test_full_synthetic_cycle(tmp_path):
    path = tmp_path / "pilot.jsonl"
    backup = tmp_path / "backup.jsonl"
    restored = tmp_path / "restored.jsonl"
    reg = ProspectiveHURegistry(path)
    reg.register_prediction(HUPrediction(prediction_id="p1",
                                         emitted_at="2026-01-01T10:00:00",
                                         hero_position="BTN",
                                         canonical_status="resolved",
                                         pot=10.0))
    assert reg.verify_integrity().ok
    reg.register_outcome(HUOutcome(outcome_id="o1", prediction_id="p1",
                                  observed_at="2026-01-01T10:05:00",
                                  observed_action="call"))
    assert reg.verify_integrity().ok
    reg.create_backup(backup)
    reg.restore_backup(backup, destination=restored, overwrite=False)
    restored_reg = ProspectiveHURegistry(restored)
    assert restored_reg.verify_integrity().ok
    assert restored_reg.read_events() == reg.read_events()
    assert reg.get_prediction("p1")["payload"]["pot"] == 10.0
