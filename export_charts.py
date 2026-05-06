"""Export board-reporting chart images from extracted SaaS FP&A metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


BRAND_COLORS = {
    "blue": "#2563EB",
    "teal": "#0F766E",
    "amber": "#D97706",
    "red": "#DC2626",
    "gray": "#475569",
}


def money_axis(value: float, _position: int) -> str:
    """Format chart axes as compact currency."""

    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def load_metrics(metrics_path: Path) -> dict[str, Any]:
    """Read metrics JSON from disk."""

    return json.loads(metrics_path.read_text(encoding="utf-8"))


def trend_dataframe(metrics: dict[str, Any]) -> pd.DataFrame:
    """Return KPI dashboard trend records as a DataFrame."""

    records = metrics.get("sheets", {}).get("SaaS KPI Dashboard", {}).get("trend", [])
    return pd.DataFrame(records)


def monthly_rows(metrics: dict[str, Any], sheet_name: str) -> dict[str, Any]:
    """Return parsed monthly row metrics for a sheet."""

    return metrics.get("sheets", {}).get(sheet_name, {}).get("monthly_table", {}).get("rows", {})


def series_from_row(row: dict[str, Any], name: str) -> pd.Series:
    """Convert a monthly row dictionary into a chartable pandas Series."""

    values = row.get("values", {})
    return pd.Series(values, name=name, dtype="float64")


def style_axes(ax, title: str, ylabel: str = "USD") -> None:
    """Apply consistent board-report chart styling."""

    ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.tick_params(axis="x", rotation=45)


def save_figure(fig, path: Path) -> None:
    """Save a Matplotlib figure and close it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def export_arr_mrr_chart(metrics: dict[str, Any], charts_dir: Path) -> Path | None:
    """Export ARR and MRR growth chart from the KPI dashboard trend table."""

    df = trend_dataframe(metrics)
    required = {"Month", "ARR", "MRR"}
    if df.empty or not required.issubset(df.columns):
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["Month"], df["ARR"], color=BRAND_COLORS["blue"], linewidth=2.5, label="ARR")
    ax.plot(df["Month"], df["MRR"], color=BRAND_COLORS["teal"], linewidth=2.5, label="MRR")
    ax.yaxis.set_major_formatter(money_axis)
    style_axes(ax, "ARR and MRR Growth")
    ax.legend(frameon=False)

    path = charts_dir / "arr_mrr_growth.png"
    save_figure(fig, path)
    return path


def export_revenue_expense_chart(metrics: dict[str, Any], charts_dir: Path) -> Path | None:
    """Export revenue versus expense trend chart."""

    pnl_rows = monthly_rows(metrics, "P&L")
    revenue = series_from_row(pnl_rows.get("total_revenue", {}), "Revenue")
    expenses = series_from_row(pnl_rows.get("total_opex", {}), "Total Opex")
    if revenue.empty or expenses.empty:
        return None

    df = pd.concat([revenue, expenses], axis=1)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df["Revenue"], color=BRAND_COLORS["teal"], linewidth=2.5, label="Revenue")
    ax.plot(df.index, df["Total Opex"], color=BRAND_COLORS["amber"], linewidth=2.5, label="Total Opex")
    ax.yaxis.set_major_formatter(money_axis)
    style_axes(ax, "Revenue vs. Operating Expense")
    ax.legend(frameon=False)

    path = charts_dir / "revenue_vs_opex.png"
    save_figure(fig, path)
    return path


def export_cash_runway_chart(metrics: dict[str, Any], charts_dir: Path) -> Path | None:
    """Export ending cash trend with a zero-cash reference line."""

    runway_rows = monthly_rows(metrics, "Cash Runway")
    ending_cash = series_from_row(runway_rows.get("ending_cash", {}), "Ending Cash")
    if ending_cash.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(ending_cash.index, ending_cash.values, color=BRAND_COLORS["red"], linewidth=2.5, label="Ending Cash")
    ax.axhline(0, color="#111827", linewidth=1, linestyle="--")
    ax.yaxis.set_major_formatter(money_axis)
    style_axes(ax, "Cash Runway")
    ax.legend(frameon=False)

    path = charts_dir / "cash_runway.png"
    save_figure(fig, path)
    return path


def export_scenario_chart(metrics: dict[str, Any], charts_dir: Path) -> Path | None:
    """Export scenario comparison for ending ARR, cash, and funding need."""

    scenarios = metrics.get("sheets", {}).get("Scenario Analysis", {}).get("scenarios", [])
    df = pd.DataFrame(scenarios)
    if df.empty or "Scenario" not in df.columns:
        return None

    cols = [col for col in ["Ending ARR", "Ending Cash", "Funding Need"] if col in df.columns]
    if not cols:
        return None

    plot_df = df.set_index("Scenario")[cols].astype(float)
    fig, ax = plt.subplots(figsize=(10, 5))
    plot_df.plot(kind="bar", ax=ax, color=[BRAND_COLORS["blue"], BRAND_COLORS["teal"], BRAND_COLORS["amber"]])
    ax.yaxis.set_major_formatter(money_axis)
    style_axes(ax, "Scenario Comparison")
    ax.set_xlabel("")
    ax.legend(frameon=False)

    path = charts_dir / "scenario_comparison.png"
    save_figure(fig, path)
    return path


def export_charts(metrics: dict[str, Any], charts_dir: Path) -> list[Path]:
    """Export all configured chart images and return paths that were created."""

    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_paths = [
        export_arr_mrr_chart(metrics, charts_dir),
        export_revenue_expense_chart(metrics, charts_dir),
        export_cash_runway_chart(metrics, charts_dir),
        export_scenario_chart(metrics, charts_dir),
    ]
    return [path for path in chart_paths if path is not None]


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    metrics_file = project_root / "output" / "cloud_ai_metrics.json"
    created = export_charts(load_metrics(metrics_file), project_root / "charts")
    print(f"Saved {len(created)} charts")
