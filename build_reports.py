"""
build_reports.py

Author: Aritra Roy
Email: contact@aritraroy.live
Website: https://aritraroy.live
GitHub: aritraroy24

Builds the two submission PDFs (project description and workflow summary) from the analysis outputs.
"""
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).parent
ANALYSIS = HERE / "analysis" / "output"
SUBMISSION = HERE / "submission"
TITLE_TEXT = "Exploring Heterometallic Co–Ni–Cu Benzenedicarboxylate Coordination Polymers via Automated Ternary Gradient Synthesis"

pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic")

ACCENT = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#DDE7F2")
GRID = colors.HexColor("#9AA5B1")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Arial", fontSize=9.5, leading=13)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Arial-Bold", fontSize=13.5, leading=17, textColor=ACCENT, spaceBefore=6, spaceAfter=5, keepWithNext=1)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Arial-Bold", fontSize=16, leading=20, textColor=ACCENT, alignment=TA_CENTER)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#444444"))


def P(text, style=BODY):
    return Paragraph(text, style)


def steps(items):
    return ListFlowable([ListItem(P(t), leftIndent=14, value=i) for i, t in enumerate(items, 1)],
                        bulletType="1", leftIndent=14, bulletFontName="Arial-Bold", bulletFontSize=9.5)


def bullets(items):
    return ListFlowable([ListItem(P(t), leftIndent=12) for t in items], bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8)


def table(rows, widths):
    """Grid table with a shaded header row and zebra striping.

    Args:
        rows (list[list[str]], required): Header row followed by data rows; strings may hold reportlab markup.
        widths (list[float], required): Column widths in points.

    Returns:
        Table: Styled table flowable.
    """
    data = [[Paragraph(c, ParagraphStyle("c", parent=BODY, fontSize=8.5, leading=10.5, fontName="Arial-Bold" if r == 0 else "Arial"))
             for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    style += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F6F8FA")) for r in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def figure(name, width_mm, caption):
    """Scaled analysis figure with a caption underneath.

    Args:
        name (str, required): PNG file name in analysis/output.
        width_mm (float, required): Display width in millimetres.
        caption (str, required): Caption text.

    Returns:
        KeepTogether: Image and caption kept on one page.
    """
    img = Image(str(ANALYSIS / name))
    img.drawHeight = img.drawHeight * width_mm * mm / img.drawWidth
    img.drawWidth = width_mm * mm
    return KeepTogether([img, Spacer(1, 1.5 * mm), P(caption, SMALL), Spacer(1, 3 * mm)])


def header(subtitle):
    return [P(TITLE_TEXT, TITLE), Spacer(1, 2 * mm), P(f"{subtitle}  |  SDL Hackathon, UZH HTEL, 26–30 October 2026", SUB),
            P("Team MOFKeKing (project M3-MOF): Aritra Roy, Piyush Ranjan Maharana, Tarak Nath Das", SUB), Spacer(1, 5 * mm)]


def build(story, path, label):
    """Write a story to an A4 PDF with a footer naming the document.

    Args:
        story (list, required): reportlab flowables.
        path (Path, required): Output PDF path.
        label (str, required): Document name shown in the footer.
    """
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Arial", 7.5)
        canvas.setFillColorRGB(0.4, 0.4, 0.4)
        canvas.drawString(20 * mm, 10 * mm, f"MOFKeKing  |  M3-MOF  |  {label}")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=13 * mm, bottomMargin=15 * mm,
                            title=f"{TITLE_TEXT}: {label}", author="Aritra Roy")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


REFERENCES = [
    "Panda, J. P.; Singha, D.; Panda, P. K.; Tripathy, B. C.; Rana, M. K. Experimental and DFT Study of Transition Metal Doping in a Zn-BDC MOF to Improve "
    "Electrical and Visible Light Absorption Properties. <i>J. Phys. Chem. C</i> <b>2022</b>, 126 (30), 12348–12360.",
    "Thorarinsdottir, A. E.; Harris, T. D. Metal–Organic Framework Magnets. <i>Chem. Rev.</i> <b>2020</b>, 120 (16), 8716–8789.",
    "Mohamedien, H. A.; Enaiet Allah, A.; Kamal, S. M.; Mohamed, F. Two-Dimensional Fe-MOF and Bimetallic NiFe-MOFs with Different Ni : Fe Ratios for "
    "Superior Electrochemical Performance in Supercapacitor Applications. <i>Nanoscale Adv.</i> <b>2026</b>, 8 (3), 896–911.",
    "Saad, M.; Elhamad, A.; Deeb, M.; Alrakkad, H. From Plastic Bottle Waste to Functional Adsorbent: A Nanostructured Bimetallic Al/Cd-BDC MOF for Enhanced "
    "Methylene Blue Removal. <i>Sci. Rep.</i> <b>2026</b> (just accepted).",
    "Kurisingal, J. F.; Babu, R.; Kim, S.-H.; Li, Y. X.; Chang, J.-S.; Cho, S. J.; Park, D.-W. Microwave-Induced Synthesis of a Bimetallic Charge-Transfer "
    "Metal Organic Framework: A Promising Host for the Chemical Fixation of CO<sub>2</sub>. <i>Catal. Sci. Technol.</i> <b>2018</b>, 8 (2), 591–600.",
    "Katugampalage, T. R.; Waribam, P.; Ratanatawanate, C.; Shahid, M.; Opaprakasit, P.; Chooaksorn, W.; Sreearunothai, P. Rapid Microwave-Assisted Synthesis "
    "of Fe/Co Bimetallic Metal-Organic Frameworks and Evaluating the Role of Coordinatively Unsaturated Sites for Selective CO<sub>2</sub> Capture. "
    "<i>Trends Sci.</i> <b>2025</b>, 22 (10), 10552.",
]


def side_by_side(left, right, widths):
    """Two flowables in one borderless row, e.g. text beside a figure.

    Args:
        left (Flowable | list, required): Left cell content.
        right (Flowable | list, required): Right cell content.
        widths (list[float], required): Column widths in points.

    Returns:
        Table: Borderless two-column table.
    """
    t = Table([[left, right]], colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def image(name, width_mm):
    img = Image(str(ANALYSIS / name))
    img.drawHeight = img.drawHeight * width_mm * mm / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def description(t):
    """Project description: aim, design, what was and was not executed, analysis, results, next steps and references.

    Args:
        t (pd.DataFrame, required): well_metrics.csv indexed by sample.

    Returns:
        list: reportlab flowables.
    """
    tern, binr = t[t.Composition_Type == "Ternary"], t[t.Composition_Type == "Binary"]
    fam = t.groupby(["Family", "Ligand_Ratio"])[["A_scatter", "B420", "B590", "B700"]].mean()
    null_cut = float(binr.PNR.quantile(0.95))
    reps = t[t.Comp == "1:1:1"].groupby("Ligand_Ratio").A_scatter
    cv = (100 * reps.std() / reps.mean()).round(0).astype(int)

    def rng(family, col):
        v = fam.loc[family, col]
        return f"{v.min():.2f} to {v.max():.2f}"

    s = header("Project description")
    s += [P("1. Background and aim", H1),
          P("Benzenedicarboxylate (BDC) metal–organic frameworks are studied for their tunable electronic<super>1</super> and magnetic<super>2</super> properties, "
            "and bimetallic BDC frameworks are well established<super>3,4</super>. The ternary Co–Ni–Cu–BDC system, however, has not been explored across a wide "
            "composition range. We asked whether a self-driving-lab workflow (automated dispensing plus fast UV–Vis screening) can map this space and flag "
            "compositions whose spectra cannot be explained by simpler mixes, as leads for HPLC–MS and PXRD.")]

    design_text = [P("2. Experimental design", H1),
                   P("24 Co:Ni:Cu compositions, all with at least two metals: the 1:1, 2:1 and 1:2 mixes on each binary edge (9) and 15 ternaries (1:1:1 in "
                     "triplicate to measure noise, plus 2:1:1, 2:2:1 and 3:2:1 permutations). Each composition runs at metal : ligand 1:1, 1:2, 1:3 and 1:4, giving "
                     "96 reactions with 5.4 µmol total metal (18 mM) in 300 µL DMF."),
                   Spacer(1, 2 * mm),
                   P("Metal acetates (450 mM) and BDC (180 mM) stocks are diluted to 90 mM and dispensed by the OT-2, BDC last so all reactions start together. "
                     "Microwave-assisted synthesis, which gives bimetallic BDC frameworks rapidly<super>5,6</super>, was our preferred heating method, but no high-throughput microwave reactor was available, so the capped vials were heated in a conventional oven for 13 h at 120 °C instead.")]
    s += [side_by_side(design_text, image("fig0_design.png", 55), [113 * mm, 57 * mm])]

    s += [P("3. What was executed and what was not", H1),
          table([["Step", "Status", "Notes"],
                 ["Design and stock calculations", "Done", "Python scripts and an Excel calculator."],
                 ["Stock and working solutions", "Done (HTEL staff)", "Prepared by hand following the submitted procedure."],
                 ["OT-2 dispensing into 96 × 2 mL GC vials", "Done (HTEL staff)", "DMF, Co, Ni, Cu, then BDC last; 420 transfers."],
                 ["Reaction: 120 °C oven", "Done (HTEL staff)", "Oven instead of microwave (no high-throughput microwave reactor available); 13 h instead of the planned 3 h."],
                 ["UV–Vis, 400–900 nm, all 96 reactions", "Done", "50 µL aliquots in DMF-safe glass inserts instead of the planned 200 µL; no DMF blank."],
                 ["HPLC–MS", "Not yet available", "Pending at the time of writing."],
                 ["PXRD of the solids", "Not done", "Planned follow-up on the leads."]],
                [55 * mm, 30 * mm, 85 * mm])]

    s += [P("4. Analysis approach", H1),
          bullets(["<b>Solid formation.</b> Suspended solid scatters light and raises the whole spectrum, so the median absorbance from 860 to 900 nm "
                   "(A<sub>scatter</sub>) is used as a measure of how much solid formed.",
                   "<b>Bands.</b> A Savitzky–Golay second derivative (40 nm window) removes the smooth scattering background and turns absorption bands into peaks. "
                   "Band strength is the mean signal in windows at ~420, ~460, ~590 and ~700 nm.",
                   f"<b>Noise.</b> The 1:1:1 triplicates give the measurement noise at each wavelength (CV of A<sub>scatter</sub> {cv[1]}–{cv[4]}% across the four ratios).",
                   "<b>Three-metal test.</b> Each ternary spectrum is rebuilt from the best non-negative mix of the nine binary spectra at the same ratio. The leftover "
                   "is scored as PNR (peak-to-noise ratio: biggest leftover signal divided by the noise). As a null, each binary is rebuilt from the other eight."])]

    s += [KeepTogether([P("5. Key results", H1),
          bullets([f"<b>Copper drives solid formation.</b> Co–Ni mixes scatter least (A<sub>scatter</sub> {rng('Co-Ni', 'A_scatter')}); Co–Cu "
                   f"({rng('Co-Cu', 'A_scatter')}) and Ni–Cu ({rng('Ni-Cu', 'A_scatter')}) scatter strongly. More BDC gives more solid.",
                   "<b>A ~700 nm band (Cu(II) d–d)</b> appears in every Cu-containing mix and is absent without Cu.",
                   f"<b>A ~590 nm band needs Co and Cu together</b> ({rng('Co-Cu', 'B590')} in Co–Cu, {rng('Co-Ni', 'B590')} in Co–Ni with the same Co content), "
                   "strongest at Co:Cu 1:1 and 2:1.",
                   f"<b>A ~420 nm band needs Ni and Cu together</b> ({rng('Ni-Cu', 'B420')} in Ni–Cu, absent elsewhere), strongest at Ni:Cu 1:1, 2:1 and 1:2 "
                   "with little BDC. These two bands are <b>bimetallic signatures</b>.",
                   f"<b>No three-metal feature.</b> All 60 ternaries are rebuilt from binaries to within PNR {tern.PNR.max():.1f}, against a binary null of "
                   f"{null_cut:.1f} (95th percentile). {int((tern.PNR > 3).sum())}/60 ternaries exceed PNR = 3, but so do {int((binr.PNR > 3).sum())}/36 binaries."])])]
    s += [figure("fig5_bands_by_pair.png", 125,
                 "Band strength by metal pair: ~420 nm needs Ni + Cu, ~590 nm needs Co + Cu, and the ~700 nm Cu band is absent without Cu.")]

    s += [P("6. Success criteria", H1),
          table([["Criterion (application)", "Outcome"],
                 ["1. UV–Vis spectra for all 96 reactions", "<b>Met.</b> 96/96 spectra, 400–900 nm."],
                 ["2. A UV–Vis feature absent from simpler compositions (PNR > 3)", "<b>Partly met.</b> Two bimetallic bands; no ternary-only feature."],
                 ["3. LRMS ion consistent with a mixed-metal stoichiometry", "<b>Pending.</b> HPLC–MS results not yet available."],
                 ["4. Ternary composition map with compositions of interest", "<b>Met</b> for UV–Vis (scattering and band maps at all four ratios)."]],
                [85 * mm, 85 * mm])]

    s += [P("7. Next steps", H1),
          bullets(["<b>HPLC–MS and PXRD on the leads</b> (Co:Cu 1:1 and 2:1; Ni:Cu 1:1, 2:1 and 1:2; 1:1:1, 3:2:1 and 2:1:3 ternaries at high BDC) to look for "
                   "mixed-metal ions and to tell a new phase from a physical mixture."])]

    s += [P("References", H1),
          ListFlowable([ListItem(P(r, SMALL), leftIndent=12, value=i) for i, r in enumerate(REFERENCES, 1)],
                       bulletType="1", leftIndent=12, bulletFontName="Arial", bulletFontSize=8)]
    return s


def flow_diagram(stages, width):
    """Horizontal chain of rounded boxes joined by arrows.

    Args:
        stages (list[tuple[str, str]], required): (title, detail) for each box.
        width (float, required): Total drawing width in points.

    Returns:
        Drawing: The flow diagram.
    """
    n, gap, h = len(stages), 9, 18 * mm
    bw = (width - gap * (n - 1)) / n
    d = Drawing(width, h)
    for i, (title, detail) in enumerate(stages):
        x = i * (bw + gap)
        d.add(Rect(x, 0, bw, h, rx=5, ry=5, fillColor=LIGHT, strokeColor=None))
        d.add(String(x + bw / 2, h - 13, title, fontName="Arial-Bold", fontSize=9, fillColor=ACCENT, textAnchor="middle"))
        for k, line in enumerate(detail.split("\n")):
            d.add(String(x + bw / 2, h - 28 - 10 * k, line, fontName="Arial", fontSize=7.5, fillColor=colors.HexColor("#333333"), textAnchor="middle"))
        if i < n - 1:
            ax = x + bw + 1.5
            d.add(Polygon([ax, h / 2 + 3.5, ax + gap - 3, h / 2, ax, h / 2 - 3.5], fillColor=ACCENT, strokeColor=None))
    return d


def workflow(t):
    """One-page workflow summary: a flow diagram and one line per step.

    Args:
        t (pd.DataFrame, required): well_metrics.csv indexed by sample (unused, kept for a common signature).

    Returns:
        list: reportlab flowables.
    """
    s = header("Workflow summary")
    s += [flow_diagram([("Design", "24 compositions\n× 4 ratios"), ("Prepare", "Stocks diluted\nto 90 mM"), ("Dispense", "OT-2, 96 vials\nBDC last"),
                        ("React", "Oven\n13 h, 120 °C"), ("Measure", "UV–Vis\n400–900 nm"), ("Analyse", "Python\nbands, maps"),
                        ("Confirm", "HPLC–MS\n+ PXRD")], 170 * mm), Spacer(1, 6 * mm)]
    s += [table([["Step", "What happens", "Who / what"],
                 ["1. Design", "Choose 24 Co:Ni:Cu mixes and four metal : ligand ratios; calculate volumes and stock masses.", "Python, Excel"],
                 ["2. Prepare", "Weigh the metal acetates and BDC, make stocks in DMF and dilute them to 90 mM.", "HTEL staff, by hand"],
                 ["3. Dispense", "Add DMF, Co, Ni and Cu to 96 GC vials, then BDC last so all reactions start together.", "Opentrons OT-2"],
                 ["4. React", "Cap the vials and heat for 13 h at 120 °C (oven, as no high-throughput microwave was available).", "Oven, by hand"],
                 ["5. Measure", "Take a 50 µL sample of each vial and record a UV–Vis spectrum.", "Tecan plate reader"],
                 ["6. Analyse", "Separate bands from scattering, map them on the composition triangle, test for three-metal features.", "Python"],
                 ["7. Confirm", "Run HPLC–MS and PXRD on the most promising compositions.", "Pending"]],
                [25 * mm, 110 * mm, 35 * mm]),
          Spacer(1, 6 * mm),
          P("<b>Status:</b> steps 1–6 are done; step 7 is pending. Code, data and figures are in the M3-MOF repository, and "
            "<i>python analysis/analyse_uvvis.py</i> reproduces every figure from the raw plate-reader export.")]
    return s


def main():
    t = pd.read_csv(ANALYSIS / "well_metrics.csv", index_col=0)
    SUBMISSION.mkdir(exist_ok=True)
    build(description(t), SUBMISSION / "M3-MOF_Project_Description.pdf", "Project description")
    build(workflow(t), SUBMISSION / "M3-MOF_Workflow_Summary.pdf", "Workflow summary")


if __name__ == "__main__":
    main()
