from .capacity_rules import WEIGHTS, STATUS_POINTS


def score(metrics):
    relevant = [m for m in metrics if m["status"] != "NOT_APPLICABLE"]
    known = [m for m in relevant if m["status"] != "UNKNOWN"]
    denominator = sum(WEIGHTS[m["id"]] for m in known)
    earned = sum(WEIGHTS[m["id"]] * STATUS_POINTS[m["status"]] for m in known)
    possible = sum(WEIGHTS[m["id"]] for m in relevant)
    return {
        "score": round(100 * earned / denominator) if denominator else None,
        "confidence": round(100 * denominator / possible) if possible else 100,
        "evaluated_weight": denominator,
        "applicable_weight": possible,
    }

