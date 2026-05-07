"""Board-level FP&A reasoning agent for extracted SaaS metrics."""

from __future__ import annotations

from typing import Any

from generate_summary import money, number, percent


def _summary(metrics: dict[str, Any], key: str) -> Any:
    """Return one extracted summary metric."""

    return metrics.get("summary_metrics", {}).get(key)


def _row(metrics: dict[str, Any], sheet: str, key: str) -> dict[str, Any]:
    """Return one parsed monthly table row."""

    return (
        metrics.get("sheets", {})
        .get(sheet, {})
        .get("monthly_table", {})
        .get("rows", {})
        .get(key, {})
    )


def _scenario_table(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return scenario rows."""

    return metrics.get("sheets", {}).get("Scenario Analysis", {}).get("scenarios", [])


def _trend_first_last(metrics: dict[str, Any], key: str) -> tuple[Any, Any]:
    """Return first and last values from the KPI dashboard trend table."""

    trend = metrics.get("sheets", {}).get("SaaS KPI Dashboard", {}).get("trend", [])
    values = [row.get(key) for row in trend if row.get(key) is not None]
    if not values:
        return None, None
    return values[0], values[-1]


def _first_last(row: dict[str, Any]) -> tuple[Any, Any]:
    """Return first and last values from a monthly metric row."""

    values = list(row.get("values", {}).values())
    if not values:
        return None, None
    return values[0], values[-1]


def _section(facts: list[str], interpretation: list[str], recommendations: list[str]) -> dict[str, list[str]]:
    """Create a standardized reasoning section."""

    return {
        "Facts": facts,
        "Interpretation": interpretation,
        "Recommendations": recommendations,
    }


def generate_finance_reasoning(metrics: dict[str, Any]) -> dict[str, Any]:
    """Generate board-level FP&A analysis separated into facts, interpretation, and recommendations."""

    customer_start, customer_end = _trend_first_last(metrics, "Ending Customers")
    mrr_start, mrr_end = _trend_first_last(metrics, "MRR")
    arr_start, arr_end = _trend_first_last(metrics, "ARR")
    scenarios = _scenario_table(metrics)

    if arr_start is None:
        arr_start = _summary(metrics, "starting_arr")
    if arr_end is None:
        arr_end = _summary(metrics, "ending_arr")
    if mrr_end is None:
        mrr_end = _summary(metrics, "ending_mrr")

    conservative = next((row for row in scenarios if str(row.get("Scenario", "")).lower().startswith("conservative")), {})
    base = next((row for row in scenarios if str(row.get("Scenario", "")).lower().startswith("base")), {})
    optimistic = next((row for row in scenarios if str(row.get("Scenario", "")).lower().startswith("optimistic")), {})

    return {
        "executive_summary": _section(
            facts=[
                f"Ending ARR is {money(_summary(metrics, 'ending_arr'))}.",
                f"Ending MRR is {money(_summary(metrics, 'ending_mrr'))}.",
                f"Ending cash is {money(_summary(metrics, 'ending_cash'))}.",
                f"Modeled funding need is {money(_summary(metrics, 'funding_need'))}.",
            ],
            interpretation=[
                "The model shows a growth story with a clear liquidity constraint.",
                "Board attention should focus on financing timing, spend gates, and retention quality.",
            ],
            recommendations=[
                f"Begin financing work before {_summary(metrics, 'first_below_minimum_cash_month') or 'the first minimum-cash breach'}.",
                "Use the next board cycle to align on cash guardrails and operating trigger points.",
            ],
        ),
        "growth_analysis": _section(
            facts=[
                f"ARR moves from {money(arr_start)} to {money(arr_end)}.",
                f"MRR ends at {money(mrr_end)}.",
                f"Customers move from {number(customer_start)} to {number(customer_end)} where customer trend data is available.",
            ],
            interpretation=[
                "Recurring revenue growth appears strong, but the plan depends on sustained customer acquisition.",
                "If churn rises with the customer base, gross adds must keep accelerating just to maintain the growth curve.",
            ],
            recommendations=[
                "Tie the growth plan to sales capacity, pipeline conversion, and CAC payback proof points.",
                "Review churn and expansion ownership at the same cadence as new-logo growth.",
            ],
        ),
        "profitability_analysis": _section(
            facts=[
                f"Revenue grows from {money(_summary(metrics, 'starting_revenue'))} to {money(_summary(metrics, 'ending_revenue'))}.",
                f"EBITDA moves from {money(_summary(metrics, 'starting_ebitda'))} to {money(_summary(metrics, 'ending_ebitda'))}.",
                f"Ending EBITDA margin is {percent(_summary(metrics, 'ebitda_margin'))}.",
                f"Total opex grows from {money(_summary(metrics, 'starting_opex'))} to {money(_summary(metrics, 'ending_opex'))}.",
            ],
            interpretation=[
                "The business moves toward profitability, but opex commitments arrive before cash safety is restored.",
                "Revenue scale is doing the heavy lifting; cost timing needs explicit board-level governance.",
            ],
            recommendations=[
                "Approve incremental opex only against pipeline, retention, and cash milestones.",
                "Separate one-time costs from structural burn in board materials.",
            ],
        ),
        "cash_runway_analysis": _section(
            facts=[
                f"Cash starts at {money(_summary(metrics, 'starting_cash'))}.",
                f"Cash ends at {money(_summary(metrics, 'ending_cash'))}.",
                f"Peak monthly net burn is {money(_summary(metrics, 'peak_net_burn'))}.",
                f"Cash first falls below the minimum buffer in {_summary(metrics, 'first_below_minimum_cash_month') or 'n/a'}.",
                f"Cash first turns negative in {_summary(metrics, 'first_negative_cash_month') or 'n/a'}.",
            ],
            interpretation=[
                "Liquidity is the clearest board decision because the plan consumes cash before reaching a safer operating state.",
                "The funding need should be treated as a minimum, not as a recommended raise size.",
            ],
            recommendations=[
                f"Plan a raise above {money(_summary(metrics, 'funding_need'))} to include execution buffer.",
                "Create a fallback spend plan if bookings, churn, or collections underperform.",
            ],
        ),
        "saas_kpi_analysis": _section(
            facts=[
                f"Gross margin is {percent(_summary(metrics, 'gross_margin'))}.",
                f"LTV:CAC is {number(_summary(metrics, 'ltv_cac'))}x.",
                f"Ending customers are {number(_summary(metrics, 'ending_customers'))}.",
            ],
            interpretation=[
                "Unit economics look attractive, but the LTV:CAC result should be pressure-tested for fully loaded CAC and churn sensitivity.",
                "A strong SaaS story requires retention and expansion to support the acquisition plan.",
            ],
            recommendations=[
                "Confirm whether CAC includes all sales, marketing, onboarding, and sales support costs.",
                "Add a retention/expansion target that moves NRR above 100%.",
            ],
        ),
        "scenario_analysis": _section(
            facts=[
                f"Conservative ending ARR / cash: {money(conservative.get('Ending ARR'))} / {money(conservative.get('Ending Cash'))}.",
                f"Base ending ARR / cash: {money(base.get('Ending ARR'))} / {money(base.get('Ending Cash'))}.",
                f"Optimistic ending ARR / cash: {money(optimistic.get('Ending ARR'))} / {money(optimistic.get('Ending Cash'))}.",
            ],
            interpretation=[
                "The scenario table shows liquidity is highly sensitive to acquisition and churn.",
                "A board should not finance only to the base case when the conservative case creates a materially larger funding gap.",
            ],
            recommendations=[
                "Use base case for operating accountability and conservative case for financing buffer.",
                "Add a bridge showing which assumptions create the largest swing in cash and ARR.",
            ],
        ),
        "recommended_actions": [
            "Approve financing timing and minimum raise buffer.",
            "Define opex gates tied to cash runway and growth quality.",
            "Assign an owner for NRR, churn reduction, and expansion motion.",
            "Require scenario refreshes before each board meeting until cash risk is resolved.",
        ],
    }
