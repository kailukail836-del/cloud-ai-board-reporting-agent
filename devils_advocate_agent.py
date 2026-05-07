"""Devil's advocate review agent for SaaS board reporting."""

from __future__ import annotations

from typing import Any

from generate_summary import money, number, percent


def _summary(metrics: dict[str, Any], key: str) -> Any:
    """Return one summary metric from extracted metrics."""

    return metrics.get("summary_metrics", {}).get(key)


def _scenario_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return parsed scenario rows."""

    return metrics.get("sheets", {}).get("Scenario Analysis", {}).get("scenarios", [])


def generate_devils_advocate_review(metrics: dict[str, Any], finance_analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stress-test the model and board narrative like an investor or board member."""

    scenarios = _scenario_rows(metrics)
    conservative = next((row for row in scenarios if str(row.get("Scenario", "")).lower().startswith("conservative")), {})
    optimistic = next((row for row in scenarios if str(row.get("Scenario", "")).lower().startswith("optimistic")), {})

    investor_objections = [
        (
            f"The plan shows ending cash of {money(_summary(metrics, 'ending_cash'))}; why should the board approve "
            "growth spend before the financing plan is locked?"
        ),
        (
            f"LTV:CAC is {number(_summary(metrics, 'ltv_cac'))}x. Is CAC fully loaded with sales salaries, marketing, "
            "onboarding, sales ops, and implementation support?"
        ),
        "If NRR is below 100%, why is the narrative emphasizing growth quality without a sharper retention plan?",
        (
            f"Peak monthly burn is {money(_summary(metrics, 'peak_net_burn'))}. What specific actions reduce burn if "
            "pipeline or collections underperform?"
        ),
    ]

    weak_assumptions = [
        "CAC may be understated if it excludes headcount, onboarding, or sales support costs.",
        "NRR below 100% means expansion is not yet offsetting churn; the plan may be too dependent on new logos.",
        "Churned customers can rise as the customer base scales, increasing the gross-add burden.",
        "Opex appears to scale before cash safety is secured.",
    ]

    if conservative and optimistic:
        weak_assumptions.append(
            "Scenario sensitivity is material: conservative ending cash is "
            f"{money(conservative.get('Ending Cash'))} versus optimistic ending cash of {money(optimistic.get('Ending Cash'))}."
        )

    data_gaps = [
        "Fully loaded CAC definition and CAC payback detail.",
        "Logo churn, gross revenue retention, and net revenue retention bridge.",
        "Pipeline coverage, conversion rate, sales capacity, and quota productivity assumptions.",
        "Collections timing, minimum cash policy, and financing contingency plan.",
        "Opex commitments split between fixed, variable, and deferrable spend.",
    ]

    questions = [
        "What exact costs are included in CAC, and how does CAC payback change if sales hiring is included?",
        "What operational changes move NRR above 100%, by when, and who owns them?",
        f"Why is {money(_summary(metrics, 'funding_need'))} the right funding reference if it excludes execution buffer?",
        "Which assumptions create the largest difference between conservative and base case cash?",
        "What evidence supports the modeled customer growth rate over the full forecast period?",
        "Which hires or opex programs can be delayed if cash falls below the minimum threshold?",
    ]

    return {
        "investor_objections": investor_objections,
        "weak_assumptions": weak_assumptions,
        "data_gaps": data_gaps,
        "questions_management_must_answer": questions,
        "review_context": {
            "ending_cash": _summary(metrics, "ending_cash"),
            "funding_need": _summary(metrics, "funding_need"),
            "ltv_cac": _summary(metrics, "ltv_cac"),
            "gross_margin": _summary(metrics, "gross_margin"),
            "ebitda_margin": _summary(metrics, "ebitda_margin"),
            "scenario_count": len(scenarios),
        },
    }
