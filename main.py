"""Run the reusable SaaS FP&A board-reporting automation workflow.

Workflow:
1. Find the Excel workbook in /input.
2. Extract structured metrics from the required model tabs.
3. Generate a Markdown board report.
4. Export chart images for board reporting.
5. Save all outputs to /output, /reports, and /charts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from export_charts import export_charts
from extract_metrics import extract_metrics, find_workbook, save_metrics
from generate_summary import generate_markdown_report, save_report


def project_root() -> Path:
    """Return the repository/project root based on this script location."""

    return Path(__file__).resolve().parents[1]


def run_pipeline(
    workbook_path: Path | None = None,
    output_dir: Path | None = None,
    reports_dir: Path | None = None,
    charts_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the end-to-end FP&A automation pipeline."""

    root = project_root()
    workbook = workbook_path or find_workbook(root / "input")
    output = output_dir or root / "output"
    reports = reports_dir or root / "reports"
    charts = charts_dir or root / "charts"

    output.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)

    metrics = extract_metrics(workbook)

    metrics_path = output / "cloud_ai_metrics.json"
    report_path = reports / "cloud_ai_board_report.md"

    save_metrics(metrics, metrics_path)
    save_report(generate_markdown_report(metrics), report_path)
    chart_paths = export_charts(metrics, charts)

    return {
        "workbook": workbook,
        "metrics_path": metrics_path,
        "report_path": report_path,
        "chart_paths": chart_paths,
        "missing_sheets": metrics.get("workbook", {}).get("sheets_missing", []),
    }


def parse_args() -> argparse.Namespace:
    """Parse optional CLI arguments for future model reuse."""

    parser = argparse.ArgumentParser(description="Automate SaaS FP&A board-reporting outputs.")
    parser.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to a workbook. Defaults to the first Excel file in /input.",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for JSON metrics.")
    parser.add_argument("--reports-dir", type=Path, default=None, help="Directory for Markdown reports.")
    parser.add_argument("--charts-dir", type=Path, default=None, help="Directory for chart PNGs.")
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    result = run_pipeline(
        workbook_path=args.workbook,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        charts_dir=args.charts_dir,
    )

    print("FP&A automation complete")
    print(f"Workbook: {result['workbook']}")
    print(f"Metrics JSON: {result['metrics_path']}")
    print(f"Markdown report: {result['report_path']}")
    print(f"Charts: {len(result['chart_paths'])} files")
    if result["missing_sheets"]:
        print(f"Missing sheets: {', '.join(result['missing_sheets'])}")


if __name__ == "__main__":
    main()
