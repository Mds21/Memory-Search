"""Deep extraction from office files: slide notes, tables, charts, headers, sheet columns become searchable."""
import io
import tempfile
from pathlib import Path

import pytest

from app.pipelines.extractors import extract

from .conftest import API, wait_ready


def _no_ocr(*_):
    return ""


@pytest.fixture(scope="module")
def office_files():
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches

    d = Path(tempfile.mkdtemp(prefix="smriti_office_"))

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[5])
    s1.shapes.title.text = "Quarterly Roadmap"
    tbl = s1.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    tbl.cell(0, 0).text, tbl.cell(0, 1).text = "Milestone", "Owner"
    tbl.cell(1, 0).text, tbl.cell(1, 1).text = "Launch beta", "Priya"
    s1.notes_slide.notes_text_frame.text = "Remember to mention the flamingo partnership"
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Revenue by region"
    cd = CategoryChartData()
    cd.categories = ["North", "South"]
    cd.add_series("Turnover", (10, 20))
    s2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(5), Inches(3), cd)
    prs.save(d / "roadmap_deck.pptx")

    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Confidential: Orchard Holdings"
    doc.add_heading("Tenancy terms", 1)
    doc.add_paragraph("The tenant shall water the bonsai garden every week.")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Item", "Deposit"
    t.cell(1, 0).text, t.cell(1, 1).text = "Flat 4B", "45000"
    doc.save(d / "tenancy.docx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Expenses"
    ws.append(["Month", "Category", "Amount"])
    ws.append(["March", "Groceries", 5400])
    ws.append(["April", "Telescope", 18000])
    wb.save(d / "budget.xlsx")
    return d


def test_pptx_extracts_titles_tables_notes_charts(office_files):
    ex = extract(office_files / "roadmap_deck.pptx", ".pptx", _no_ocr)
    text = "\n".join(ex.pages)
    assert ex.pages[0].startswith("Slide 1: Quarterly Roadmap")
    assert "Launch beta | Priya" in text and "flamingo partnership" in text
    assert "Chart:" in text and "North" in text and "Turnover" in text
    keys = {d["key"]: d["value"] for d in ex.details}
    assert keys["slides"] == "2" and "Revenue by region" in keys["outline"] and keys["charts"] == "1"


def test_docx_extracts_headings_tables_headers(office_files):
    ex = extract(office_files / "tenancy.docx", ".docx", _no_ocr)
    text = "\n".join(ex.pages)
    assert "Flat 4B | 45000" in text and "Orchard Holdings" in text
    assert ex.outline == ["Tenancy terms"]


def test_xlsx_rows_carry_column_names(office_files):
    ex = extract(office_files / "budget.xlsx", ".xlsx", _no_ocr)
    assert "Columns: Month, Category, Amount" in ex.pages[0]
    assert "Month: April; Category: Telescope; Amount: 18000" in ex.pages[0]


def test_markup_is_stripped(tmp_path):
    p = tmp_path / "page.html"
    p.write_text("<html><title>Trip plan</title><style>.x{}</style><body><p>Ferry to Havelock &amp; back</p></body></html>")
    ex = extract(p, ".html", _no_ocr)
    assert "Ferry to Havelock & back" in ex.pages[0] and "<p>" not in ex.pages[0]


def test_office_files_are_searchable(client, alice, office_files):
    ups = [("files", (p.name, p.read_bytes())) for p in sorted(office_files.iterdir())]
    assert client.post(f"{API}/assets", headers=alice, files=ups).status_code == 201
    assets = wait_ready(client, alice)
    deck = next(a for a in assets if a["title"] == "roadmap_deck.pptx")
    assert deck["status"] == "ready"
    for q, want in [("flamingo partnership", "roadmap_deck.pptx"), ("bonsai garden", "tenancy.docx"),
                    ("telescope expense", "budget.xlsx")]:
        res = client.post(f"{API}/search", headers=alice, json={"query": q}).json()["results"]
        assert res and res[0]["title"] == want, (q, [r["title"] for r in res[:3]])
