from pathlib import Path


SCRIPT = (Path(__file__).parents[1] / "frontend" / "maturity.js").read_text(encoding="utf-8")


def test_highlights_are_derived_from_evaluation_results():
    assert "deriveHighlights(dimensionResults)" in SCRIPT
    assert "item.result.dimension" in SCRIPT
    assert "Melhor resultado entre as dimensões avaliadas." not in SCRIPT
    assert "Dimensão com maior oportunidade de evolução." not in SCRIPT


def test_recommendations_are_derived_from_criterion_findings():
    assert "deriveRecommendations(dimensionResults)" in SCRIPT
    assert "result.criteria" in SCRIPT
    assert "item.subdimension" in SCRIPT
    assert "item.dimensionId" in SCRIPT

