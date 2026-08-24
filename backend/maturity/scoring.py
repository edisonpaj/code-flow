from .rules import DIMENSION_WEIGHTS


def confidence(coverage):
    if coverage is None: return "NOT_AVAILABLE"
    if coverage >= 80: return "HIGH"
    if coverage >= 60: return "MEDIUM"
    return "LOW"


def dimension_score(results):
    scored_results = [r for r in results if r.get("score_enabled", True)]
    evaluated = [r for r in scored_results if r["processing_status"] == "EVALUATED" and r["result"] != "NOT_APPLICABLE"]
    not_applicable = sum(r["result"] == "NOT_APPLICABLE" for r in scored_results)
    applicable = len(scored_results) - not_applicable
    groups = {}
    for result in scored_results:
        groups.setdefault(result.get("subdimension", "__dimension__"), []).append(result)
    subdimension_scores = []
    for group in groups.values():
        group_applicable = [r for r in group if r["result"] != "NOT_APPLICABLE"]
        if group_applicable:
            subdimension_scores.append(sum((r["score"] or 0) for r in group_applicable) * 100 / len(group_applicable))
    score = round(sum(subdimension_scores) / len(subdimension_scores)) if subdimension_scores else None
    coverage = round(len(evaluated) * 100 / applicable) if applicable else None
    return score, coverage, confidence(coverage), len(evaluated), applicable


def consolidate_dimensions(results):
    scored = [r for r in results if r.get("score") is not None]
    weight_sum = sum(DIMENSION_WEIGHTS[r["dimension_id"]] for r in scored)
    score = round(sum(r["score"] * DIMENSION_WEIGHTS[r["dimension_id"]] for r in scored) / weight_sum) if weight_sum else None
    evaluated = sum(r["summary"]["evaluated_applicable"] for r in results)
    applicable = sum(r["summary"]["applicable"] for r in results)
    coverage = round(evaluated * 100 / applicable) if applicable else None
    return score, coverage, confidence(coverage), evaluated, applicable
