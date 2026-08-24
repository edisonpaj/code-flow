from backend.analyzer.capacity.workload_calculator import workload, classify_headroom
from backend.analyzer.capacity.score_calculator import score
from backend.analyzer.capacity.config_scanner import scan


def test_workload_2000_tps_100_ms():
    value = workload(2000, 100, 6, 10)
    assert value["estimated_concurrency"] == 200
    assert value["concurrency_per_pod"] == 33.33
    assert value["concurrency_per_pod_at_max_scale"] == 20


def test_headroom_thresholds():
    assert classify_headroom(2) == "HEALTHY"
    assert classify_headroom(1.5) == "ADEQUATE"
    assert classify_headroom(1) == "ATTENTION"
    assert classify_headroom(.99) == "INSUFFICIENT"


def test_project_tps_and_concurrency_with_30_percent_headroom():
    value = workload(2000, 50, headroom_percent=30)
    assert value["estimated_concurrency"] == 100
    assert value["design_tps"] == 2600
    assert value["headroom_percent"] == 30


def test_missing_values_yaml_has_actionable_recommendation(tmp_path):
    result = scan(str(tmp_path))
    values = next(item for item in result["configuration_files"] if item["name"] == "values.yaml")
    assert values["status"] == "NOT_DETECTED"
    combined = values["recommendation"] + values["example"]
    for expected in ("requests", "limits", "cpu", "memory", "minReplicas", "maxReplicas"):
        assert expected in combined


def test_unknown_reduces_confidence_and_na_is_removed():
    metrics=[{"id":"threads","status":"HEALTHY"},{"id":"database_pool","status":"UNKNOWN"},{"id":"http_pool","status":"NOT_APPLICABLE"}]
    result=score(metrics)
    assert result["score"] == 100
    assert result["confidence"] == 50
