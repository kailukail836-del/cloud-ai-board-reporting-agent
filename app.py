import json
from pathlib import Path
from io import BytesIO

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from pptx import Presentation
from pptx.util import Inches, Pt

from extract_metrics import extract_metrics
from generate_summary import generate_markdown_report
from export_charts import export_charts


st.set_page_config(
    page_title="Cloud.AI Board Reporting Agent",
    layout="wide"
)


def money(value):
    if value is None:
        return "n/a"
    value = float(value)
    text = f"${abs(value):,.0f}"
    return f"({text})" if value < 0 else text


def percent(value):
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def number(value):
    if value is None:
        return "n/a"
    return f"{float(value):,.1f}"


def create_pdf(metrics, report_text):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    summary = metrics.get("summary_metrics", {})

    story.append(Paragraph("Cloud.AI Board Reporting Pack", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive KPI Summary", styles["Heading2"]))

    data = [
        ["KPI", "Value"],
        ["Ending ARR", money(summary.get("ending_arr"))],
        ["Ending MRR", money(summary.get("ending_mrr"))],
        ["Ending Customers", number(summary.get("ending_customers"))],
        ["Gross Margin", percent(summary.get("gross_margin"))],
        ["EBITDA Margin", percent(summary.get("ebitda_margin"))],
        ["LTV:CAC", f"{number(summary.get('ltv_cac'))}x"],
        ["Funding Need", money(summary.get("funding_need"))],
    ]

    table = Table(data, colWidths=[220, 180])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FB")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Board Report", styles["Heading2"]))

    for line in report_text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("#"):
            story.append(Paragraph(line.replace("#", "").strip(), styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["BodyText"]))
        elif "|" not in line:
            story.append(Paragraph(line, styles["BodyText"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


def create_ppt(metrics):
    prs = Presentation()
    summary = metrics.get("summary_metrics", {})

    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Cloud.AI Board Reporting Pack"
    slide.placeholders[1].text = "AI-assisted SaaS FP&A reporting workflow"

    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Executive KPI Summary"

    rows = [
        ("Ending ARR", money(summary.get("ending_arr"))),
        ("Ending MRR", money(summary.get("ending_mrr"))),
        ("Ending Customers", number(summary.get("ending_customers"))),
        ("Gross Margin", percent(summary.get("gross_margin"))),
        ("EBITDA Margin", percent(summary.get("ebitda_margin"))),
        ("LTV:CAC", f"{number(summary.get('ltv_cac'))}x"),
        ("Funding Need", money(summary.get("funding_need"))),
    ]

    left = Inches(0.8)
    top = Inches(1.5)
    width = Inches(8.5)
    height = Inches(4.5)

    table = slide.shapes.add_table(len(rows) + 1, 2, left, top, width, height).table
    table.cell(0, 0).text = "KPI"
    table.cell(0, 1).text = "Value"

    for i, (kpi, value) in enumerate(rows, start=1):
        table.cell(i, 0).text = kpi
        table.cell(i, 1).text = value

    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Board Decision Summary"
    slide.placeholders[1].text = (
        f"Cloud.AI scales to {money(summary.get('ending_arr'))} ending ARR, "
        f"but ending cash falls to {money(summary.get('ending_cash'))}. "
        f"The board should align on financing timing, opex guardrails, and retention improvement."
    )

    output = BytesIO()
    prs.save(output)
    output.seek(0)
    return output


st.title("Cloud.AI Board Reporting Agent")
st.caption("Excel model → KPI extraction → board analysis → charts → PDF/PPT outputs")

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

    with st.spinner("Generating board reporting outputs..."):
        metrics = extract_metrics(workbook_path)
        report = generate_markdown_report(metrics)
        chart_paths = export_charts(metrics, charts_dir)

    summary = metrics.get("summary_metrics", {})

    st.success("Board reporting workflow completed successfully.")

    st.subheader("Executive KPI Snapshot")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ending ARR", money(summary.get("ending_arr")))
    col2.metric("Ending MRR", money(summary.get("ending_mrr")))
    col3.metric("Ending Customers", number(summary.get("ending_customers")))
    col4.metric("Funding Need", money(summary.get("funding_need")))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Gross Margin", percent(summary.get("gross_margin")))
    col6.metric("EBITDA Margin", percent(summary.get("ebitda_margin")))
    col7.metric("LTV:CAC", f"{number(summary.get('ltv_cac'))}x")
    col8.metric("Ending Cash", money(summary.get("ending_cash")))

    st.divider()

    st.subheader("Generated Charts")
    for chart in chart_paths:
        st.image(str(chart), caption=chart.name, use_container_width=True)

    st.divider()

    st.subheader("Clean Board Report")

    st.info(
        "This report is generated from the uploaded SaaS financial model. "
        "Use the PDF or PPT download for stakeholder sharing."
    )

    board_sections = metrics.get("sheets", {}).get("Board Analysis", {}).get("sections", {})

    for section, rows in board_sections.items():
        st.markdown(f"### {section}")
        for row in rows:
            topic = row.get("topic", "")
            message = row.get("message", "")
            st.markdown(f"**{topic}:** {message}")

    pdf_file = create_pdf(metrics, report)
    ppt_file = create_ppt(metrics)

    st.divider()

    st.subheader("Download Outputs")

    st.download_button(
        "Download Board Report PDF",
        data=pdf_file,
        file_name="cloud_ai_board_report.pdf",
        mime="application/pdf"
    )

    st.download_button(
        "Download Board Summary PPT",
        data=ppt_file,
        file_name="cloud_ai_board_summary.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

    st.download_button(
        "Download Metrics JSON",
        data=json.dumps(metrics, indent=2),
        file_name="cloud_ai_metrics.json",
        mime="application/json"
    )

else:
    st.info("Upload the SaaS financial model workbook to generate board reporting outputs.")
