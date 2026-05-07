"""Controller for the V2 agent-style Cloud.AI FP&A workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devils_advocate_agent import generate_devils_advocate_review
from export_charts import export_charts
from extract_metrics import clean_value, extract_metrics, save_metrics
from finance_reasoning_agent import generate_finance_reasoning
from generate_summary import generate_markdown_report, save_report
from model_audit_agent import audit_financial_model
from quality_review_agent import review_output_quality
from readiness_agent import inspect_workbook_readiness


def _json_safe(value: Any) -> Any:
    """Recursively convert Paths and spreadsheet values into JSON-safe values."""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return clean_value(value)


def run_agent_workflow(
    workbook_path: Path,
    output_dir: Path,
    reports_dir: Path,
    charts_dir: Path,
) -> dict[str, Any]:
    """Run the full V2 workflow and return a single agent_results dictionary."""

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    readiness = inspect_workbook_readiness(workbook_path)
    metrics = extract_metrics(workbook_path)
    model_audit = audit_financial_model(workbook_path, metrics)
    finance_reasoning = generate_finance_reasoning(metrics)
    devils_advocate = generate_devils_advocate_review(metrics, finance_reasoning)

    markdown_report = generate_markdown_report(metrics)
    chart_paths = export_charts(metrics, charts_dir)

    metrics_path = output_dir / "cloud_ai_metrics.json"
    report_path = reports_dir / "cloud_ai_board_report.md"
    save_metrics(metrics, metrics_path)
    save_report(markdown_report, report_path)

    quality_review = review_output_quality(metrics, finance_reasoning, devils_advocate, markdown_report)

    agent_results = {
        "workflow_version": "V2 Agent FP&A Analysis",
        "workbook": {
            "file_name": workbook_path.name,
            "path": str(workbook_path),
        },
        "readiness": readiness,
        "metrics": metrics,
        "model_audit": model_audit,
        "finance_reasoning": finance_reasoning,
        "devils_advocate": devils_advocate,
        "quality_review": quality_review,
        "charts": [str(path) for path in chart_paths],
        "reports": {
            "metrics_json": str(metrics_path),
            "markdown_report": str(report_path),
        },
    }

    return _json_safe(agent_results)
