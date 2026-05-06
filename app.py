import json
from pathlib import Path

import pandas as pd
import streamlit as st

from extract_metrics import extract_metrics
from generate_summary import generate_markdown_report
from export_charts import export_charts


st.set_page_config(
    page_title="Cloud.AI Board Reporting Agent",
    layout="wide"
)

st.title("Cloud.AI Board Reporting Agent")
st.caption("AI-assisted SaaS FP&A workflow: Excel model → KPI extraction → board report → charts → presentation inputs")

uploaded_file = st.file_uploader(
    "Upload SaaS financial model workbook",
    type=["xlsx", "xlsm"]
)

if uploaded_file:
    work_dir = Path("streamlit_outputs")
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    charts_dir = work_dir / "charts"
    reports_dir = work_dir / "reports"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    workbook_path = input_dir / uploaded_file.name
    workbook_path.write_bytes(uploaded_file.getbuffer())

    with st.spinner("Reading workbook and generating board reporting outputs..."):
        metrics = extract_metrics(workbook_path)

        metrics_path = output_dir / "cloud_ai_metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        report = generate_markdown_report(metrics)
        report_path = reports_dir / "cloud_ai_board_report.md"
        report_path.write_text(report, encoding="utf-8")

        chart_paths = export_charts(metrics, charts_dir)

    summary = metrics.get("summary_metrics", {})

    st.success("Board reporting workflow completed successfully.")

    st.subheader("Executive KPI Snapshot")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Ending ARR", f"${summary.get('ending_arr', 0):,.0f}")
    col2.metric("Ending MRR", f"${summary.get('ending_mrr', 0):,.0f}")
    col3.metric("Ending Customers", f"{summary.get('ending_customers', 0):,.1f}")
    col4.metric("Funding Need", f"${summary.get('funding_need', 0):,.0f}")

    st.subheader("Generated Charts")

    for chart in chart_paths:
        st.image(str(chart), caption=chart.name, use_container_width=True)

    st.subheader("Board Report")

    st.markdown(report)

    st.download_button(
        "Download Metrics JSON",
        data=metrics_path.read_text(encoding="utf-8"),
        file_name="cloud_ai_metrics.json",
        mime="application/json"
    )

    st.download_button(
        "Download Board Report",
        data=report,
        file_name="cloud_ai_board_report.md",
        mime="text/markdown"
    )

else:
    st.info("Upload the SaaS financial model workbook to generate the board reporting output.")