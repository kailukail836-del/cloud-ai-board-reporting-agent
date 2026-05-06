"""Generate a board-ready Markdown report from extracted SaaS FP&A metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def money(value: Any) -> str:
    """Format a number as board-report currency."""

    if value is None:
        return "n/a"
    value = float(value)
    formatted = f"${abs(value):,.0f}"
    return f"({formatted})" if value < 0 else formatted


def number(value: Any, decimals: int = 1) -> str:
    """Format a plain number with a controlled decimal count."""

    if value is None:
        return "n/a"
    return f"{float(value):,.{decimals}f}"


def percent(value: Any) -> str:
    """Format decimal percentages from spreadsheet metrics."""

    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def safe_text(value: Any) -> str:
    """Return clean text for Markdown output."""

    if value is None:
        return ""
    return str(value).strip()


def metric(metrics: dict[str, Any], key: str) -> Any:
    """Get one compact summary metric."""

    return metrics.get("summary_metrics", {}).get(key)


def board_section(metrics: dict[str, Any], section_name: str) -> list[dict[str, str]]:
    """Return Board Analysis rows for an optional narrative section."""

    board = metrics.get("sheets", {}).get("Board Analysis", {}).get("sections", {})
    return board.get(section_name, [])


def scenario_records(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return parsed scenario records."""

    return metrics.get("sheets", {}).get("Scenario Analysis", {}).get("scenarios", [])


def dashboard_takeaways(metrics: dict[str, Any]) -> list[dict[str, str]]:
    """Return parsed dashboard takeaways."""

    return metrics.get("sheets", {}).get("SaaS KPI Dashboard", {}).get("takeaways", [])


def risk_level(metrics: dict[str, Any]) -> str:
    """Classify liquidity risk using ending cash, runway, and funding need."""

    ending_cash = metric(metrics, "ending_cash")
    funding_need = metric(metrics, "funding_need")
    runway_months = metric(metrics, "ending_runway_months")
    if ending_cash is not None and float(ending_cash) < 0:
        return "High"
    if funding_need is not None and float(funding_need) > 0:
        return "Elevated"
    if runway_months is not None and float(runway_months) < 6:
        return "Watch"
    return "Moderate"


def generate_executive_summary(metrics: dict[str, Any]) -> str:
    """Build the top-level executive summary paragraph."""

    return (
        f"Cloud.AI scales to {money(metric(metrics, 'ending_arr'))} of ending ARR and "
        f"{money(metric(metrics, 'ending_mrr'))} of ending MRR, with "
        f"{number(metric(metrics, 'ending_customers'))} ending customers. The model shows attractive "
        f"SaaS economics, including {percent(metric(metrics, 'gross_margin'))} gross margin and "
        f"{number(metric(metrics, 'ltv_cac'))}x LTV:CAC, but liquidity is the board-level constraint: "
        f"ending cash is {money(metric(metrics, 'ending_cash'))} and modeled funding need is "
        f"{money(metric(metrics, 'funding_need'))}."
    )


def generate_kpi_summary(metrics: dict[str, Any]) -> str:
    """Build a compact KPI table."""

    rows = [
        ("Ending ARR", money(metric(metrics, "ending_arr"))),
        ("Ending MRR", money(metric(metrics, "ending_mrr"))),
        ("Ending Customers", number(metric(metrics, "ending_customers"))),
        ("Gross Margin", percent(metric(metrics, "gross_margin"))),
        ("EBITDA Margin", percent(metric(metrics, "ebitda_margin"))),
        ("LTV:CAC", f"{number(metric(metrics, 'ltv_cac'))}x"),
        ("Funding Need", money(metric(metrics, "funding_need"))),
    ]
    lines = ["| KPI | Value |", "| --- | ---: |"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)


def generate_runway_analysis(metrics: dict[str, Any]) -> str:
    """Summarize cash runway and funding timing."""

    below_min = metric(metrics, "first_below_minimum_cash_month") or "not reached"
    negative = metric(metrics, "first_negative_cash_month") or "not reached"
    return (
        f"Cash starts at {money(metric(metrics, 'starting_cash'))} and ends at "
        f"{money(metric(metrics, 'ending_cash'))}. Peak monthly net burn is "
        f"{money(metric(metrics, 'peak_net_burn'))}. Cash first falls below the minimum buffer in "
        f"{below_min}, and first turns negative in {negative}. The board should treat financing "
        f"timing as the primary decision because the model requires {money(metric(metrics, 'funding_need'))} "
        f"to preserve the minimum cash balance."
    )


def generate_profitability_analysis(metrics: dict[str, Any]) -> str:
    """Summarize revenue, EBITDA, and opex movement."""

    return (
        f"Revenue increases from {money(metric(metrics, 'starting_revenue'))} to "
        f"{money(metric(metrics, 'ending_revenue'))}. EBITDA improves from "
        f"{money(metric(metrics, 'starting_ebitda'))} to {money(metric(metrics, 'ending_ebitda'))}, "
        f"with ending EBITDA margin of {percent(metric(metrics, 'ebitda_margin'))}. Total opex grows "
        f"from {money(metric(metrics, 'starting_opex'))} to {money(metric(metrics, 'ending_opex'))}, "
        "so spend gates should stay tied to pipeline quality, retention progress, and cash trough timing."
    )


def generate_scenario_comparison(metrics: dict[str, Any]) -> str:
    """Create a Markdown table for scenario analysis."""

    scenarios = scenario_records(metrics)
    if not scenarios:
        return "No scenario table was found."

    lines = [
        "| Scenario | New Customer Growth | Monthly Churn | Ending ARR | Ending Cash | Funding Need | Comment |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in scenarios:
        lines.append(
            "| {scenario} | {growth} | {churn} | {arr} | {cash} | {need} | {comment} |".format(
                scenario=safe_text(record.get("Scenario")),
                growth=percent(record.get("New Customer Growth")),
                churn=percent(record.get("Monthly Churn")),
                arr=money(record.get("Ending ARR")),
                cash=money(record.get("Ending Cash")),
                need=money(record.get("Funding Need")),
                comment=safe_text(record.get("Comment")),
            )
        )
    return "\n".join(lines)


def generate_risk_summary(metrics: dict[str, Any]) -> str:
    """Generate a practical risk summary tied to extracted model outputs."""

    risks = [
        f"Liquidity risk is {risk_level(metrics).lower()}: ending cash is {money(metric(metrics, 'ending_cash'))}.",
        f"Funding buffer risk: modeled funding need is {money(metric(metrics, 'funding_need'))}, before any execution cushion.",
        f"Operating leverage risk: opex expands to {money(metric(metrics, 'ending_opex'))} before the model is sustainably cash positive.",
    ]

    # Reuse model-authored board risks when available, but keep the report concise.
    existing_risks = board_section(metrics, "Risk Summary") or board_section(metrics, "Key Risks")
    for item in existing_risks[:3]:
        risks.append(f"{safe_text(item.get('topic'))}: {safe_text(item.get('message'))}")

    return "\n".join(f"- {risk}" for risk in risks)


def generate_board_recommendations(metrics: dict[str, Any]) -> str:
    """Generate action-oriented recommendations for the next board cycle."""

    recommendations = [
        f"Start financing preparation before {metric(metrics, 'first_below_minimum_cash_month') or 'the minimum-cash trigger'} and size the raise above {money(metric(metrics, 'funding_need'))}.",
        "Approve spend gates for hiring and GTM programs that depend on CAC payback, retention progress, and pipeline coverage.",
        "Set an explicit retention and expansion plan aimed at moving NRR above 100%.",
        "Use base case for operating targets, but finance against the conservative case to protect execution flexibility.",
    ]
    return "\n".join(f"- {recommendation}" for recommendation in recommendations)


def generate_markdown_report(metrics: dict[str, Any]) -> str:
    """Create the full board report Markdown document."""

    workbook_name = metrics.get("workbook", {}).get("file_name", "SaaS financial model")
    takeaways = dashboard_takeaways(metrics)
    takeaway_lines = "\n".join(
        f"- {safe_text(item.get('topic'))}: {safe_text(item.get('message'))}" for item in takeaways
    )

    return f"""# Cloud.AI Board Reporting Pack

Source workbook: `{workbook_name}`

## Executive Summary
{generate_executive_summary(metrics)}

## KPI Summary
{generate_kpi_summary(metrics)}

## Dashboard Takeaways
{takeaway_lines or "- No dashboard takeaways were found."}

## Runway Analysis
{generate_runway_analysis(metrics)}

## Profitability Analysis
{generate_profitability_analysis(metrics)}

## Scenario Comparison
{generate_scenario_comparison(metrics)}

## Risk Summary
{generate_risk_summary(metrics)}

## Board Recommendations
{generate_board_recommendations(metrics)}
"""


def load_metrics(metrics_path: Path) -> dict[str, Any]:
    """Read metrics JSON from disk."""

    return json.loads(metrics_path.read_text(encoding="utf-8"))


def save_report(markdown: str, report_path: Path) -> None:
    """Write the Markdown report to disk."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    metrics_file = project_root / "output" / "cloud_ai_metrics.json"
    report = generate_markdown_report(load_metrics(metrics_file))
    save_report(report, project_root / "reports" / "cloud_ai_board_report.md")
    print(f"Saved report to {project_root / 'reports' / 'cloud_ai_board_report.md'}")
