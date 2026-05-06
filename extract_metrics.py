"""Extract reusable FP&A metrics from a SaaS financial model workbook.

The extractor is intentionally label-driven. It looks for familiar headers
such as "Line Item", "Month", "Scenario", and "Slide No" instead of relying on
fixed cell addresses, which makes it more tolerant of future SaaS models with a
similar reporting structure.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import openpyxl
import pandas as pd


TARGET_SHEETS = [
    "SaaS KPI Dashboard",
    "P&L",
    "Cash Runway",
    "Scenario Analysis",
    "Board Analysis",
    "Board Deck Input",
]


@dataclass(frozen=True)
class WorkbookSource:
    """Resolved input workbook and core sheet metadata."""

    path: Path
    sheet_names: list[str]


def find_workbook(input_dir: Path) -> Path:
    """Return the first Excel workbook found in the input folder."""

    candidates = sorted(
        p
        for p in input_dir.glob("*.xls*")
        if not p.name.startswith("~$") and p.suffix.lower() in {".xlsx", ".xlsm", ".xls"}
    )
    if not candidates:
        raise FileNotFoundError(f"No Excel workbook found in {input_dir}")
    return candidates[0]


def load_source(workbook_path: Path) -> WorkbookSource:
    """Load workbook metadata without modifying the file."""

    wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
    return WorkbookSource(path=workbook_path, sheet_names=list(wb.sheetnames))


def clean_value(value: Any) -> Any:
    """Convert spreadsheet / pandas values into JSON-friendly values."""

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    return str(value).strip() if isinstance(value, str) else value


def normalize_key(label: Any) -> str:
    """Convert a row label into a stable snake_case key."""

    text = str(label or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def read_sheet(workbook_path: Path, sheet_name: str) -> pd.DataFrame:
    """Read one sheet as a headerless DataFrame preserving blank cells."""

    return pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, engine="openpyxl")


def non_empty(value: Any) -> bool:
    """Return True when a cell value is meaningfully present."""

    return clean_value(value) not in (None, "")


def row_values(df: pd.DataFrame, row_idx: int) -> list[Any]:
    """Return a cleaned list of row values."""

    return [clean_value(v) for v in df.iloc[row_idx].tolist()]


def find_row_containing(df: pd.DataFrame, labels: Iterable[str]) -> int | None:
    """Find the first row containing any of the provided labels."""

    wanted = {label.lower() for label in labels}
    for idx in range(len(df.index)):
        values = [str(v).strip().lower() for v in row_values(df, idx) if non_empty(v)]
        if any(value in wanted for value in values):
            return idx
    return None


def trim_record(record: dict[str, Any]) -> dict[str, Any]:
    """Remove empty columns from a parsed table record."""

    return {k: v for k, v in record.items() if k and v not in (None, "")}


def dataframe_from_header(df: pd.DataFrame, header_label: str) -> pd.DataFrame:
    """Build a clean table from the row containing a specific header label."""

    header_row = find_row_containing(df, [header_label])
    if header_row is None:
        return pd.DataFrame()

    headers = row_values(df, header_row)
    used_cols = [idx for idx, header in enumerate(headers) if non_empty(header)]
    if not used_cols:
        return pd.DataFrame()

    first_col, last_col = min(used_cols), max(used_cols)
    headers = [clean_value(v) for v in headers[first_col : last_col + 1]]
    data = df.iloc[header_row + 1 :, first_col : last_col + 1].copy()
    data.columns = headers
    data = data.dropna(how="all")
    data = data.loc[:, [col for col in data.columns if non_empty(col)]]
    data = data.where(pd.notnull(data), None)
    return data


def records_from_table(df: pd.DataFrame, header_label: str) -> list[dict[str, Any]]:
    """Return row records from a header-driven table."""

    table = dataframe_from_header(df, header_label)
    if table.empty:
        return []
    return [trim_record({str(k): clean_value(v) for k, v in row.items()}) for _, row in table.iterrows()]


def monthly_table_from_line_item(df: pd.DataFrame) -> dict[str, Any]:
    """Parse a model table whose first column is "Line Item" and remaining columns are months."""

    table = dataframe_from_header(df, "Line Item")
    if table.empty:
        return {"months": [], "rows": {}, "sections": []}

    months = [clean_value(col) for col in table.columns[1:] if non_empty(col)]
    rows: dict[str, dict[str, Any]] = {}
    sections: list[str] = []

    for _, raw_row in table.iterrows():
        label = clean_value(raw_row.iloc[0])
        if not non_empty(label):
            continue

        values = [clean_value(v) for v in raw_row.iloc[1 : len(months) + 1].tolist()]
        if not any(non_empty(v) for v in values):
            sections.append(str(label))
            continue

        rows[normalize_key(label)] = {
            "label": str(label),
            "values": dict(zip(months, values)),
            "start": values[0] if values else None,
            "end": values[-1] if values else None,
        }

    return {"months": months, "rows": rows, "sections": sections}


def table_from_month_header(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Parse a trend table whose first header is "Month"."""

    records = records_from_table(df, "Month")
    cleaned = []
    for record in records:
        if record.get("Month"):
            cleaned.append(record)
    return cleaned


def extract_dashboard_tiles(df: pd.DataFrame) -> dict[str, Any]:
    """Extract KPI dashboard tiles where label, value, and description stack vertically."""

    tiles: dict[str, Any] = {}
    max_rows = min(len(df.index), 12)
    max_cols = min(len(df.columns), 16)

    for row in range(max_rows - 2):
        for col in range(max_cols):
            label = clean_value(df.iat[row, col])
            value = clean_value(df.iat[row + 1, col])
            description = clean_value(df.iat[row + 2, col])
            if not (non_empty(label) and non_empty(value) and non_empty(description)):
                continue
            if isinstance(value, str):
                continue
            key = normalize_key(label)
            tiles[key] = {"label": label, "value": value, "description": description}

    return tiles


def extract_dashboard_takeaways(df: pd.DataFrame) -> list[dict[str, str]]:
    """Extract plain-English dashboard takeaways beneath their heading."""

    start = find_row_containing(df, ["Plain-English Takeaways"])
    if start is None:
        return []

    takeaways = []
    for idx in range(start + 1, len(df.index)):
        first = clean_value(df.iat[idx, 0])
        second = clean_value(df.iat[idx, 1]) if len(df.columns) > 1 else None
        if first == "Month":
            break
        if non_empty(first) and non_empty(second):
            takeaways.append({"topic": str(first), "message": str(second)})
    return takeaways


def extract_board_analysis(df: pd.DataFrame) -> dict[str, Any]:
    """Parse Board Analysis into sections with topic/message rows."""

    sections: dict[str, list[dict[str, str]]] = {}
    current_section = "Overview"

    for idx in range(len(df.index)):
        first = clean_value(df.iat[idx, 0])
        second = clean_value(df.iat[idx, 1]) if len(df.columns) > 1 else None
        if not non_empty(first):
            continue

        text = str(first)
        if re.match(r"^\d+\.\s+", text):
            current_section = re.sub(r"^\d+\.\s+", "", text).strip()
            sections.setdefault(current_section, [])
            continue
        if non_empty(second):
            sections.setdefault(current_section, []).append({"topic": text, "message": str(second)})

    return {"sections": sections}


def extract_board_deck_input(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Extract board deck input rows for report appendix and recommendation context."""

    return records_from_table(df, "Slide No")


def metric_row(table: dict[str, Any], key: str) -> dict[str, Any]:
    """Safely return one metric row from a parsed monthly table."""

    return table.get("rows", {}).get(key, {})


def first_non_empty(values: Iterable[Any]) -> Any:
    """Return the first meaningful value from an iterable."""

    for value in values:
        if non_empty(value):
            return value
    return None


def first_month_where(row: dict[str, Any], predicate) -> str | None:
    """Find the first month where a monthly metric matches a condition."""

    for month, value in row.get("values", {}).items():
        try:
            if value is not None and predicate(float(value)):
                return str(month)
        except (TypeError, ValueError):
            continue
    return None


def max_numeric(row: dict[str, Any]) -> float | None:
    """Return the maximum numeric value in a monthly row."""

    nums = []
    for value in row.get("values", {}).values():
        try:
            if value is not None:
                nums.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(nums) if nums else None


def min_numeric(row: dict[str, Any]) -> float | None:
    """Return the minimum numeric value in a monthly row."""

    nums = []
    for value in row.get("values", {}).values():
        try:
            if value is not None:
                nums.append(float(value))
        except (TypeError, ValueError):
            continue
    return min(nums) if nums else None


def build_summary_metrics(extracted: dict[str, Any]) -> dict[str, Any]:
    """Create a compact board-ready metrics layer from extracted sheet data."""

    kpi = extracted.get("sheets", {}).get("SaaS KPI Dashboard", {})
    pnl = extracted.get("sheets", {}).get("P&L", {}).get("monthly_table", {})
    runway = extracted.get("sheets", {}).get("Cash Runway", {}).get("monthly_table", {})
    scenarios = extracted.get("sheets", {}).get("Scenario Analysis", {}).get("scenarios", [])

    revenue = metric_row(pnl, "total_revenue")
    gross_margin = metric_row(pnl, "gross_margin")
    ebitda = metric_row(pnl, "ebitda")
    ebitda_margin = metric_row(pnl, "ebitda_margin")
    total_opex = metric_row(pnl, "total_opex")
    ending_cash = metric_row(runway, "ending_cash")
    net_burn = metric_row(runway, "net_burn")
    funding_need = metric_row(runway, "funding_need_to_minimum_cash")
    runway_months = metric_row(runway, "runway_months")

    return {
        "ending_arr": kpi.get("tiles", {}).get("ending_arr", {}).get("value"),
        "ending_mrr": kpi.get("tiles", {}).get("ending_mrr", {}).get("value"),
        "ending_customers": kpi.get("tiles", {}).get("ending_customers", {}).get("value"),
        "gross_margin": kpi.get("tiles", {}).get("gross_margin", {}).get("value") or gross_margin.get("end"),
        "ebitda_margin": kpi.get("tiles", {}).get("ebitda_margin", {}).get("value") or ebitda_margin.get("end"),
        "ltv_cac": kpi.get("tiles", {}).get("ltv_cac", {}).get("value"),
        "funding_need": kpi.get("tiles", {}).get("funding_need", {}).get("value") or max_numeric(funding_need),
        "starting_revenue": revenue.get("start"),
        "ending_revenue": revenue.get("end"),
        "starting_ebitda": ebitda.get("start"),
        "ending_ebitda": ebitda.get("end"),
        "starting_cash": metric_row(runway, "opening_cash").get("start"),
        "ending_cash": ending_cash.get("end"),
        "minimum_cash": min_numeric(ending_cash),
        "peak_net_burn": max_numeric(net_burn),
        "ending_runway_months": runway_months.get("end"),
        "first_below_minimum_cash_month": first_month_where(funding_need, lambda value: value > 0),
        "first_negative_cash_month": first_month_where(ending_cash, lambda value: value < 0),
        "starting_opex": total_opex.get("start"),
        "ending_opex": total_opex.get("end"),
        "scenario_count": len(scenarios),
    }


def extract_metrics(workbook_path: Path) -> dict[str, Any]:
    """Extract all required sheets into a structured metrics dictionary."""

    source = load_source(workbook_path)
    extracted: dict[str, Any] = {
        "workbook": {
            "file_name": source.path.name,
            "path": str(source.path),
            "sheets_available": source.sheet_names,
            "sheets_requested": TARGET_SHEETS,
            "sheets_missing": [sheet for sheet in TARGET_SHEETS if sheet not in source.sheet_names],
        },
        "sheets": {},
    }

    for sheet_name in TARGET_SHEETS:
        if sheet_name not in source.sheet_names:
            continue

        df = read_sheet(workbook_path, sheet_name)
        if sheet_name == "SaaS KPI Dashboard":
            extracted["sheets"][sheet_name] = {
                "tiles": extract_dashboard_tiles(df),
                "takeaways": extract_dashboard_takeaways(df),
                "trend": table_from_month_header(df),
            }
        elif sheet_name in {"P&L", "Cash Runway"}:
            extracted["sheets"][sheet_name] = {"monthly_table": monthly_table_from_line_item(df)}
        elif sheet_name == "Scenario Analysis":
            extracted["sheets"][sheet_name] = {"scenarios": records_from_table(df, "Scenario")}
        elif sheet_name == "Board Analysis":
            extracted["sheets"][sheet_name] = extract_board_analysis(df)
        elif sheet_name == "Board Deck Input":
            extracted["sheets"][sheet_name] = {"slides": extract_board_deck_input(df)}

    extracted["summary_metrics"] = build_summary_metrics(extracted)
    return extracted


def save_metrics(metrics: dict[str, Any], output_path: Path) -> None:
    """Write structured JSON metrics to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, indent=2, default=clean_value), encoding="utf-8")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    workbook = find_workbook(project_root / "input")
    metrics_data = extract_metrics(workbook)
    save_metrics(metrics_data, project_root / "output" / "cloud_ai_metrics.json")
    print(f"Extracted metrics from {workbook}")
