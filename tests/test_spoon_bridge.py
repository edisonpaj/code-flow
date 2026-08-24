from pathlib import Path

import backend.spoon_bridge as bridge


def test_spoon_disabled_is_safe(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERT_CODE_FLOW_SPOON", "off")
    result = bridge.analyze_with_spoon(str(tmp_path))
    assert result["state"] == "disabled"
    assert result["authoritative"] is False


def test_spoon_unavailable_is_safe(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERT_CODE_FLOW_SPOON", "shadow")
    monkeypatch.setattr(bridge, "SPOON_JAR", tmp_path / "missing.jar")
    result = bridge.analyze_with_spoon(str(tmp_path))
    assert result["state"] == "unavailable"
    assert result["authoritative"] is False


def test_engine_status_reports_selectable_mode(monkeypatch):
    monkeypatch.setenv("EXPERT_CODE_FLOW_SPOON", "selectable")
    status = bridge.engine_status()
    assert status["id"] == "spoon"
    assert status["mode"] == "selectable"
    assert status["enabled"] is True
