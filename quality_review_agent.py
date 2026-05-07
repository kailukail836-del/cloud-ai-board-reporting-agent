"""Quality review agent for final Cloud.AI board reporting outputs."""

from __future__ import annotations

from typing import Any


def _summary(metrics: dict[str, Any], key: str) -> Any:
    """Return one extracted summary metric."""

    return metrics.get("summary_metrics", {}).get(key)


def _has_metric_tied_text(items: list[str], metric_tokens: list[str]) -> bool:
    """Check whether any text item includes a metric reference token."""

    text = " ".join(items).lower()
    return any(token.lower() in text for token in metric_tokens)


def _collect_recommendations(finance_analysis: dict[str, Any]) -> list[str]:
    """Collect recommendation text from all finance reasoning sections."""

    recommendations: list[str] = []
    for value in finance_analysis.values():
        if isinstance(value, dict):
            recommendations.extend(str(item) for item in value.get("Recommendations", []))
        elif isinstance(value, list):
            recommendations.extend(str(item) for item in value)
    return recommendations


def review_output_quality(
    metrics: dict[str, Any],
    finance_analysis: dict[str, Any],
    devils_advocate: dict[str, Any],
    markdown_report: str,
) -> dict[str, Any]:
    """Review final V2 outputs before stakeholder use."""

    score = 100
    checklist: list[dict[str, Any]] = []
    final_review_notes: list[str] = []

    recommendations = _collect_recommendations(finance_analysis)
    report_lower = markdown_report.lower()

    checks = [
        {
            "item": "Recommendations are tied to actual metrics",
            "passed": _has_metric_tied_text(
                recommendations,
                ["funding", "cash", "nrr", "cac", "pipeline", "retention", "opex"],
            ),
            "failure_note": "Recommendations should explicitly reference extracted KPIs or operating metrics.",
        },
        {
            "item": "Assumptions are clearly flagged",
            "passed": bool(devils_advocate.get("weak_assumptions")),
            "failure_note": "Add a clear weak-assumptions section before stakeholder use.",
        },
        {
            "item": "Unsupported claims are limited",
            "passed": "n/a" not in report_lower or bool(metrics.get("summary_metrics")),
            "failure_note": "Report includes unresolved n/a values or claims without supporting metrics.",
        },
        {
            "item": "Liquidity risk is clearly communicated",
            "passed": (
                _summary(metrics, "ending_cash") is not None
                and ("cash" in report_lower or "liquidity" in report_lower)
                and ("funding" in report_lower or "runway" in report_lower)
            ),
            "failure_note": "Liquidity, ending cash, runway, and funding need must be explicit.",
        },
        {
            "item": "Board decisions are specific",
            "passed": _has_metric_tied_text(recommendations, ["approve", "begin", "define", "assign", "use"]),
            "failure_note": "Board recommendations should include concrete decision verbs.",
        },
    ]

    for check in checks:
        checklist.append({"item": check["item"], "passed": check["passed"]})
        if not check["passed"]:
            score -= 12
            final_review_notes.append(check["failure_note"])

    if _summary(metrics, "ending_cash") is not None and float(_summary(metrics, "ending_cash")) < 0:
        final_review_notes.append("Liquidity risk is material and should remain prominent in the board narrative.")

    if _summary(metrics, "funding_need") is not None and float(_summary(metrics, "funding_need")) > 0:
        final_review_notes.append("Funding recommendation is supported by extracted funding-need metrics.")

    if not final_review_notes:
        final_review_notes.append("Outputs are internally consistent and ready for stakeholder review.")

    score = max(0, min(100, score))
    status = "Ready for Stakeholders" if score >= 85 else "Needs Review" if score >= 65 else "Not Ready"

    return {
        "quality_score": score,
        "status": status,
        "checklist": checklist,
        "final_review_notes": final_review_notes,
    }
