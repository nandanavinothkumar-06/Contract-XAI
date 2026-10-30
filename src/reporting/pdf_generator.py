"""
ContractRisk-XAI: Academic PDF Report Generator
Compiles a publication-quality multi-page PDF report with running headers,
two-pass page numbering ("Page X of Y"), styled tables, and embedded high-DPI figures.
"""

import os
import json
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Color Palette
NAVY = colors.HexColor("#1B365D")
SLATE = colors.HexColor("#4A5568")
CHARCOAL = colors.HexColor("#2D3748")
LIGHT_GREY = colors.HexColor("#F7FAFC")
BORDER_GREY = colors.HexColor("#E2E8F0")
CRIMSON = colors.HexColor("#9B2C2C")
CRIMSON_BG = colors.HexColor("#FFF5F5")
HEADER_BG = colors.HexColor("#EDF2F7")
TEAL = colors.HexColor("#234E52")

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 45.0
PRINTABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to compute total page count and render running headers and footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(CHARCOAL)

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(MARGIN, PAGE_HEIGHT - 32, "ContractRisk-XAI: Academic Research Report & Forensic Evaluation")
            self.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32, "CRXAI-ACAD-2026-T025")
            self.setStrokeColor(BORDER_GREY)
            self.setLineWidth(0.6)
            self.line(MARGIN, PAGE_HEIGHT - 36, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 36)

        # Running Footer (all pages)
        self.setStrokeColor(BORDER_GREY)
        self.setLineWidth(0.6)
        self.line(MARGIN, 36, PAGE_WIDTH - MARGIN, 36)

        footer_notice = "NOT A VALIDATED LEGAL DECISION-MAKER — CS Research Benchmark Only"
        self.drawString(MARGIN, 25, footer_notice)
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(PAGE_WIDTH - MARGIN, 25, page_str)

        self.restoreState()


class AcademicPDFReportBuilder:
    """
    Constructs the flowable document story and builds the academic PDF.
    """
    def __init__(self, output_pdf_path: str, figures_dir: str):
        self.output_pdf_path = output_pdf_path
        self.figures_dir = figures_dir
        self.doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=48,
            bottomMargin=46
        )
        self.styles = self._setup_styles()
        self.story = []

    def _setup_styles(self) -> Dict[str, ParagraphStyle]:
        styles = getSampleStyleSheet()

        custom_styles = {
            "DocTitle": ParagraphStyle(
                "DocTitle", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=18, leading=22,
                textColor=NAVY, spaceAfter=4
            ),
            "DocSubtitle": ParagraphStyle(
                "DocSubtitle", parent=styles["Normal"],
                fontName="Helvetica", fontSize=10.5, leading=14,
                textColor=SLATE, spaceAfter=6
            ),
            "DocMeta": ParagraphStyle(
                "DocMeta", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.5, leading=10.5,
                textColor=SLATE, spaceAfter=8
            ),
            "DisclaimerTitle": ParagraphStyle(
                "DisclaimerTitle", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=8, leading=10,
                textColor=CRIMSON, spaceAfter=2
            ),
            "DisclaimerText": ParagraphStyle(
                "DisclaimerText", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.2, leading=9.5,
                textColor=CHARCOAL
            ),
            "Heading1": ParagraphStyle(
                "Heading1", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=11.5, leading=14.5,
                textColor=NAVY, spaceBefore=10, spaceAfter=4,
                keepWithNext=True
            ),
            "Heading2": ParagraphStyle(
                "Heading2", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=9.0, leading=11.5,
                textColor=CHARCOAL, spaceBefore=7, spaceAfter=3,
                keepWithNext=True
            ),
            "Heading3": ParagraphStyle(
                "Heading3", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=8.0, leading=10.0,
                textColor=SLATE, spaceBefore=5, spaceAfter=2,
                keepWithNext=True
            ),
            "Body": ParagraphStyle(
                "Body", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.6, leading=10.2,
                textColor=CHARCOAL, spaceAfter=3.5
            ),
            "Bullet": ParagraphStyle(
                "Bullet", parent=styles["Normal"],
                fontName="Helvetica", fontSize=7.6, leading=10.2,
                textColor=CHARCOAL, leftIndent=10, spaceAfter=2
            ),
            "Caption": ParagraphStyle(
                "Caption", parent=styles["Normal"],
                fontName="Helvetica-Oblique", fontSize=7.0, leading=9.0,
                textColor=SLATE, alignment=1, spaceBefore=2, spaceAfter=5
            ),
            "TableHead": ParagraphStyle(
                "TableHead", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=6.8, leading=8.5,
                textColor=NAVY
            ),
            "TableCell": ParagraphStyle(
                "TableCell", parent=styles["Normal"],
                fontName="Helvetica", fontSize=6.6, leading=8.2,
                textColor=CHARCOAL
            ),
            "TableCellBold": ParagraphStyle(
                "TableCellBold", parent=styles["Normal"],
                fontName="Helvetica-Bold", fontSize=6.6, leading=8.2,
                textColor=CHARCOAL
            ),
            "TableCellCode": ParagraphStyle(
                "TableCellCode", parent=styles["Normal"],
                fontName="Courier", fontSize=6.0, leading=7.5,
                textColor=CHARCOAL
            )
        }
        return custom_styles

    def add_p(self, text: str, style_name: str = "Body"):
        self.story.append(Paragraph(text, self.styles[style_name]))

    def add_bullet(self, text: str):
        self.story.append(Paragraph(f"• {text}", self.styles["Bullet"]))

    def add_spacer(self, height: float):
        self.story.append(Spacer(1, height))

    def add_disclaimer_box(self):
        title = Paragraph("MANDATORY LEGAL SAFETY & ETHICAL NOTICE — CS RESEARCH BENCHMARK ONLY", self.styles["DisclaimerTitle"])
        body = Paragraph(
            "<b>NOT A VALIDATED LEGAL DECISION-MAKER.</b> The models, algorithms, attribution rationales, and evaluation metrics "
            "documented in this academic report were developed strictly for computer science research in natural language processing and applied "
            "model explainability. Gradient-based token saliency and span-level attributions reflect the mathematical sensitivity of deep neural networks "
            "to input representations; <b>they do not constitute formal legal advice, statutory interpretation, or binding contract risk assessments</b>. "
            "Machine learning classifications are susceptible to severe false-positive inflation, long-tail class starvation, and lexical overlap artifacts. "
            "Autonomous legal decision-making based on these systems is expressly cautioned against.",
            self.styles["DisclaimerText"]
        )
        table = Table([[title], [body]], colWidths=[PRINTABLE_WIDTH])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CRIMSON_BG),
            ("BOX", (0, 0), (-1, -1), 1.0, CRIMSON),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.story.append(table)
        self.add_spacer(5)

    def add_figure(self, filename: str, caption_text: str, width: float = 480.0, height: float = 230.0):
        img_path = os.path.join(self.figures_dir, filename)
        if os.path.exists(img_path):
            img = Image(img_path, width=width, height=height)
            caption = Paragraph(caption_text, self.styles["Caption"])
            self.story.append(KeepTogether([img, caption]))
        else:
            self.add_p(f"<i>[Figure {filename} missing from {img_path}]</i>", "Caption")
        self.add_spacer(4)

    def add_table(self, data: List[List[Any]], col_widths: List[float], is_header: bool = True):
        formatted_data = []
        for row_idx, row in enumerate(data):
            formatted_row = []
            for col_idx, cell in enumerate(row):
                if isinstance(cell, str):
                    if row_idx == 0 and is_header:
                        p = Paragraph(cell, self.styles["TableHead"])
                    else:
                        p = Paragraph(cell, self.styles["TableCell"])
                    formatted_row.append(p)
                else:
                    formatted_row.append(cell)
            formatted_data.append(formatted_row)

        table = Table(formatted_data, colWidths=col_widths)
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for r in range(1, len(data)):
            if r % 2 == 1:
                t_style.append(("BACKGROUND", (0, r), (-1, r), colors.white))
            else:
                t_style.append(("BACKGROUND", (0, r), (-1, r), LIGHT_GREY))

        table.setStyle(TableStyle(t_style))
        self.story.append(table)
        self.add_spacer(4)

    def build_report_content(self):
        # Cover / Header
        self.add_p("ContractRisk-XAI: An Evidence-Grounded Legal Language Modeling & Explainability Benchmark for Commercial Contracts", "DocTitle")
        self.add_p("Comprehensive Research Findings, Ablation Studies, Robustness Audits, and Forensic Error Analysis", "DocSubtitle")
        self.add_p(
            "<b>Authors:</b> ContractRisk-XAI Research Consortium &nbsp;|&nbsp; <b>Date:</b> October 14, 2026 &nbsp;|&nbsp; "
            "<b>Doc ID:</b> CRXAI-ACAD-2026-T025-V1.0<br/>"
            "<b>Physical Weights SHA-256:</b> <font face='Courier' size='6'>7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f</font>",
            "DocMeta"
        )
        self.add_disclaimer_box()

        # Table of Contents Summary Box
        toc_text = (
            "<b>Report Structure & Table of Contents:</b> "
            "<b>1.</b> Abstract & Summary &nbsp;|&nbsp; <b>2.</b> Problem & Objectives &nbsp;|&nbsp; "
            "<b>3.</b> Methodology & Safeguards &nbsp;|&nbsp; <b>4.</b> Architecture & Pipelines &nbsp;|&nbsp; "
            "<b>5.</b> Dataset Provenance &nbsp;|&nbsp; <b>6.</b> Preprocessing & Segmentation &nbsp;|&nbsp; "
            "<b>7.</b> Model Architecture & Ingestion &nbsp;|&nbsp; <b>8.</b> Evidence Extraction & Invariants &nbsp;|&nbsp; "
            "<b>9.</b> Cross-Domain Geometry &nbsp;|&nbsp; <b>10.</b> Ablation Studies &nbsp;|&nbsp; "
            "<b>11.</b> Robustness Testing &nbsp;|&nbsp; <b>12.</b> Error Analysis & Taxonomy &nbsp;|&nbsp; "
            "<b>13.</b> Dashboard & Governance &nbsp;|&nbsp; <b>14.</b> Synthesis & Discussion &nbsp;|&nbsp; "
            "<b>15.</b> Threats to Validity &nbsp;|&nbsp; <b>16.</b> Conclusions & Roadmap &nbsp;|&nbsp; "
            "<b>17.</b> References &nbsp;|&nbsp; <b>18.</b> Provenance & Audit Ledger"
        )
        toc_table = Table([[Paragraph(toc_text, self.styles["TableCell"])]], colWidths=[PRINTABLE_WIDTH])
        toc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.story.append(toc_table)
        self.add_spacer(6)

        # Section 1
        self.add_p("1. Abstract & Executive Summary", "Heading1")
        self.add_p(
            "Automated contract analysis demands high accuracy, structural robustness, and verifiable explainability. "
            "However, real-world deployment of NLP systems in legal domains is frequently obstructed by three critical challenges: "
            "(i) extreme long-tail label taxonomies, (ii) task incompatibilities across datasets, and (iii) attribution artifacts "
            "where model saliency highlights grammatical syntax rather than legally operative language."
        )
        self.add_p(
            "This report presents the consolidated academic findings of the <b>ContractRisk-XAI</b> benchmark project (Tasks 001–025). "
            "We evaluated a frozen-encoder <b>LEGAL-BERT</b> model (<code>nlpaueb/legal-bert-base-uncased</code>, 109.5M frozen parameters) "
            "paired with a trainable linear classification head (9.5M parameters) spanning 12,407 provision categories trained on a deterministic "
            "10% contract subset of the LEDGAR corpus. We independently audited model performance against traditional baseline classifiers "
            "(TF-IDF + Linear SVM) on ContractNLI, and investigated cross-domain representations with the CUAD dataset."
        )
        self.add_bullet("<b>Decision Threshold Dilemma:</b> On held-out LEDGAR test data (87,956 provisions; 105,283 ground-truth labels), default tau=0.50 misses 99.06% of true labels (Recall 0.94%, TP=989, FN=104,294, Micro-F1 0.0185, Macro-F1 0.0009, Weighted-F1 0.0141). Calibrated tau*=0.04 recovers 12.83x recall (12,699 TP; Micro-F1 0.1435, +675.7% relative gain), but inflates FP by 134.6x (58,947 FP), capping precision at 17.72%.")
        self.add_bullet("<b>Macro-F1 Collapse Mechanism:</b> While Micro-F1 reaches 0.1435 and Weighted-F1 reaches 0.0937, Macro-F1 collapses to 0.0045 because 91.07% of the taxonomy (11,298 classes) has <10 training examples, including 2,833 unlearned zero-shot classes with 0.0% recall.")
        self.add_bullet("<b>ContractNLI Lexical Fallacy:</b> TF-IDF Linear SVM reaches 65.57% accuracy (0.6557) and 0.5844 Macro-F1, but misclassifies 42.41% of NotMentioned clauses (383/903) as Entailment due to shared NDA boilerplate.")
        self.add_bullet("<b>Cross-Domain Decoupling:</b> Direct transfer between ContractNLI, LEDGAR, and CUAD is INVALID due to task formulation mismatch. However, representation geometry shows a +0.0686 intra- vs inter-concept separation margin (0.8606 vs 0.7920).")
        self.add_bullet("<b>Attribution Offset Invariants:</b> Gradient x Input attributions guarantee 100% UTF-8 character-offset preservation, but exhibit heavy bias toward function words ('and', 'the'). Saliency must not be conflated with legal validity.")

        # Section 2
        self.add_p("2. Problem Statement, Research Questions & Objectives", "Heading1")
        self.add_p(
            "Commercial contract review requires identifying latent financial liabilities, indemnification exposures, unilateral amendment rights, "
            "and regulatory non-compliance. While deep learning models offer substantial promise, standard NLP practices fail in legal contexts:"
        )
        self.add_bullet("<b>RQ1 (Calibration):</b> Can validation-calibrated decision thresholds recover provision recall in extreme multi-label taxonomies without producing intolerable false alarm rates?")
        self.add_bullet("<b>RQ2 (Cross-Domain Validity):</b> Do transfer-learning assumptions hold across specialized legal corpora (SEC filings, NDAs, procurement specifications), or do divergent annotation schemes create artificial performance metrics?")
        self.add_bullet("<b>RQ3 (Explainability Invariants):</b> Does neural gradient attribution produce reliable, human-interpretable legal rationales, or does it merely highlight structural syntactic glue?")
        self.add_bullet("<b>RQ4 (Architectural Ablation & Robustness):</b> How do cross-clause context budgeting, relationship graph topologies, and textual perturbations affect classification stability?")

        # Section 3
        self.add_p("3. Research Methodology & Verification Safeguards", "Heading1")
        self.add_p(
            "To prevent p-hacking, data leakage, and ungrounded legal assertions, ContractRisk-XAI enforces seven mandatory research integrity safeguards:"
        )
        self.add_bullet("<b>Frozen Checkpoint Invariant:</b> Model weights are cryptographically locked (SHA-256: <code>7cd08d2c...</code>). Zero retraining or test-set tuning permitted.")
        self.add_bullet("<b>Threshold Calibration Boundary:</b> tau*=0.04 derived exclusively on validation split (84,250 provisions); test split (87,956 provisions) used strictly for reporting.")
        self.add_bullet("<b>Leakage Auditing:</b> Document-level hash comparisons (MD5, SHA-256) enforce zero cross-partition clause overlap.")
        self.add_bullet("<b>Task Decoupling Policy:</b> Supervised metrics from distinct problem formulations are never averaged into a composite score.")
        self.add_bullet("<b>Character Coordinate Invariants:</b> All attributed tokens must map bijectively back to UTF-8 character coordinates in source text.")
        self.add_bullet("<b>Dispassionate Long-Tail Accounting:</b> Tail-class collapse is formally documented using frequency tiers rather than obscured by micro-averages.")
        self.add_bullet("<b>Legal Governance Disclaimer:</b> Prominent notice displayed across all interfaces confirming models are not legal counsel.")

        # Section 4
        self.add_p("4. System Architecture & Engineering Pipelines", "Heading1")
        self.add_p(
            "The ContractRisk-XAI architecture comprises five modular, decoupled subsystems engineered to operate under strict computational constraints:"
        )
        self.add_figure("figure1_architecture.png", "Figure 1: ContractRisk-XAI Modular System Architecture and Verification Pipeline", 480, 225)

        # Section 5
        self.add_p("5. Dataset Descriptions, Legal Provenance & Split Invariants", "Heading1")
        self.add_p(
            "The benchmark utilizes three primary corpora and tracks two domain-restricted secondary sources:"
        )
        ds_data = [
            ["Dataset", "Origin Domain", "Registry Verification", "Local Availability", "Preprocessing Status", "Completed Supervised Exp", "Reproduction Status"],
            ["LEDGAR", "SEC EDGAR Filings", "VERIFIED (P002)", "Available (Local disk)", "Implemented (UTF-8, offsets)", "YES: LEGAL-BERT + Linear Head (12,407 classes, tau*=0.04)", "Independently audited & verified (Task 019/021)"],
            ["ContractNLI", "Commercial NDAs", "VERIFIED (P003)", "Available (Local disk)", "Implemented (NLI pair format)", "YES: Baseline TF-IDF + Linear SVM (3 classes, 2,091 test pairs)", "Independently audited & verified (Task 018/023)"],
            ["CUAD", "Commercial Contracts", "VERIFIED (Hendrycks)", "Available (Local disk)", "Implemented (Embedding extract)", "NO: Representation geometry only; supervised transfer is INVALID", "Concept margin verified (+0.0686, Task 020)"],
            ["CLAUDETTE", "Consumer ToS", "VERIFIED (P004)", "Downloadable (Research)", "Not implemented (Tracked)", "NO: Secondary reference domain; no supervised training executed", "Unexecuted in this benchmark (Literature reference)"],
            ["Construction", "Engineering Specs", "VERIFIED (P005-P007)", "Restricted (Proprietary)", "Not implemented (Tracked)", "NO: Access unresolved; no supervised training executed", "Unexecuted in this benchmark (Literature reference)"]
        ]
        self.add_table(ds_data, [48, 62, 60, 68, 68, 106, 110])
        self.add_p("<i>Empirical Status Distinction: Only LEDGAR and ContractNLI were utilized in completed supervised experiments in this benchmark. CUAD was evaluated exclusively for unsupervised cross-domain representation geometry. CLAUDETTE and Construction Specifications are tracked bibliographic reference domains without supervised pipelines.</i>", "Caption")

        # Section 6
        self.add_p("6. Non-Destructive Preprocessing & Hierarchical Clause Segmentation", "Heading1")
        self.add_p(
            "Standard text processing frequently mutilates contract numbering (e.g. <i>Section 4.1(a)(ii)</i>) and destroys character offsets. "
            "ContractRisk-XAI enforces a non-destructive pipeline maintaining exact UTF-8 character coordinates. Documents are parsed into a "
            "nested structural hierarchy: <i>Document -> Article -> Section -> Clause -> Sub-clause</i>. Contextual expansion operates under a strict "
            "512-token budget where the target clause is guaranteed protection against truncation."
        )

        # Section 7
        self.add_p("7. Model Architecture, Parameter Isolation & Training Ingestion", "Heading1")
        self.add_p(
            "The primary classification model utilizes parameter isolation: a frozen LEGAL-BERT encoder (109.5M params) and a trainable linear head "
            "(9.5M params) projecting 768-dimensional [CLS] embeddings to 12,407 output logits via BCEWithLogitsLoss. "
            "Training was completed over 3 epochs on the 10% LEDGAR subset (67,776 provisions, seed 42). Weights were archived in "
            "<code>model.safetensors</code> (476,116,436 bytes) with verified SHA-256 hash <code>7cd08d2c...</code>."
        )

        # Section 8
        self.add_p("8. Evidence Extraction, Saliency Attribution & Offset Invariants", "Heading1")
        self.add_p(
            "Token-level evidence extraction computes Gradient x Input saliency. Subword WordPiece tokens are re-aligned to original document character spans. "
            "Contiguous tokens are aggregated into clause phrases. Across all evaluated clauses, 100% of attribution spans satisfied the character-offset invariant: "
            "<code>doc_text[start_char : end_char] == attributed_substring</code>."
        )
        self.add_figure("figure2_evidence_attribution.png", "Figure 2: Evidence Attribution Token Saliency & Character Offset Invariants", 480, 205)

        # Section 9
        self.add_p("9. Cross-Domain Compatibility & Representation Geometry (Task 020)", "Heading1")
        self.add_p(
            "Task 020 formally audited cross-domain compatibility. Supervised transfer between ContractNLI (3-class NLI), LEDGAR (12,407-class classification), "
            "and CUAD (extractive QA) was classified as <b>INVALID / TASK_MISMATCH</b>. Zero cross-partition data leakage was detected. "
            "However, representation geometry across four shared legal concepts (Governing Law, Termination, Liability, Assignment) demonstrated an "
            "intra-concept cosine similarity of 0.8606 vs inter-concept similarity of 0.7920, yielding a concept separation margin of +0.0686."
        )
        self.add_figure("figure3_cross_domain_similarity.png", "Figure 3: Representation Geometry Across Shared Legal Concepts", 360, 215)

        # Section 10
        self.add_p("10. Component Ablation Studies (Task 021)", "Heading1")
        self.add_p(
            "Controlled ablations independently evaluated four architectural components:"
        )
        self.add_p("<b>Part A: Decision Threshold Evaluation & Calibration (Task 019 / 021)</b>", "Heading2")
        self.add_p(
            "<b>Table 10.1: Measured Full-Test Evaluation on Held-Out Test Set (87,956 Provisions; 105,283 Ground-Truth Labels)</b><br/>"
            "<i>Strict Provenance Boundary: Only tau*=0.04 and tau=0.50 were evaluated on the held-out test split. No intermediate test sweeps were performed.</i>"
        )
        test_th_data = [
            ["Threshold (tau)", "Evaluation Scope & Provenance", "Micro-P", "Micro-R", "Micro-F1", "Macro-F1", "Weighted-F1", "True Pos (TP)", "False Pos (FP)", "False Neg (FN)"],
            ["0.04 (tau*)", "Measured Full-Test (Calibrated Optimum)", "0.1772", "0.1206", "0.1435", "0.0045", "0.0937", "12,699", "58,947", "92,584"],
            ["0.50", "Measured Full-Test (Default Baseline)", "0.6931", "0.0094", "0.0185", "0.0009", "0.0141", "989", "438", "104,294"]
        ]
        self.add_table(test_th_data, [55, 147, 38, 38, 40, 40, 44, 40, 40, 40])

        self.add_p(
            "<b>Table 10.2: Stage 1 Validation Split Threshold Sweep Curve (84,250 Provisions — Calibration Dataset)</b><br/>"
            "<i>Validation Sweep: 14 candidate thresholds evaluated to select tau*=0.04 based on argmax(Validation Micro-F1).</i>"
        )
        val_th_data = [
            ["Threshold (tau)", "Validation Purpose", "Val Micro-P", "Val Micro-R", "Val Micro-F1", "Val Macro-F1", "Val TP", "Val FP", "Val FN"],
            ["0.01", "Validation Sweep Point", "0.0418", "0.2304", "0.0708", "0.0038", "23,071", "528,309", "77,058"],
            ["0.02", "Validation Sweep Point", "0.0864", "0.1697", "0.1145", "0.0044", "16,989", "179,698", "83,140"],
            ["0.03", "Validation Sweep Point", "0.1232", "0.1402", "0.1311", "0.0045", "14,036", "99,913", "86,093"],
            ["0.04 (tau*)", "Validation Optimum (Selected)", "0.1559", "0.1223", "0.1371", "0.0044", "12,246", "66,305", "87,883"],
            ["0.05", "Validation Sweep Point", "0.1813", "0.1085", "0.1357", "0.0043", "10,859", "49,052", "89,270"],
            ["0.06", "Validation Sweep Point", "0.2000", "0.0980", "0.1315", "0.0042", "9,813", "39,251", "90,316"],
            ["0.08", "Validation Sweep Point", "0.2195", "0.0810", "0.1184", "0.0039", "8,114", "28,854", "92,015"],
            ["0.10", "Validation Sweep Point", "0.2269", "0.0691", "0.1060", "0.0035", "6,921", "23,576", "93,208"],
            ["0.20", "Validation Sweep Point", "0.2289", "0.0392", "0.0669", "0.0025", "3,922", "13,213", "96,207"],
            ["0.50", "Validation Default Baseline", "0.6098", "0.0093", "0.0184", "0.0009", "936", "599", "99,193"]
        ]
        self.add_table(val_th_data, [60, 110, 48, 48, 48, 48, 50, 55, 55])
        self.add_figure("figure4_threshold_curve.png", "Figure 4: LEDGAR Validation Threshold Tuning Curve (84,250 provisions)", 440, 190)

        self.add_p(
            "<b>Parts B, C, D Summary:</b> Context strategy PARENT_CHILD yielded the highest structural stability (cosine 0.8720) with 100% budget compliance. "
            "Relationship graph ablation proved that cross-reference edges are required for multi-clause reachability (100% vs 9.52% for hierarchy alone). "
            "Span aggregation produced human-interpretable phrases with 100% character-offset integrity."
        )

        # Section 11
        self.add_p("11. Empirical Robustness & Boundary Stress Testing (Task 022)", "Heading1")
        self.add_p(
            "Robustness audits evaluated model stability and failure behavior across five critical dimensions:"
        )
        self.add_bullet("<b>Input Perturbations:</b> High representation stability: Uppercase (cosine 0.978), Whitespace (0.985), Typos (0.931), Entity substitution (0.946).")
        self.add_bullet("<b>Context Stress:</b> 100% target preservation under >1,000 token context overflow; 100% rejection of cross-document segment injections.")
        self.add_bullet("<b>Evidence Attribution Sparsity:</b> Confirmed authentic token-level gradient sparsity (Gini 0.3962 - 0.5633), resolving the Task 021 artifact caveat.")
        self.add_bullet("<b>Graph Topology & Cyclicity:</b> Mutual circular cross-references handled non-recursively; dangling references safely flagged UNRESOLVED.")
        self.add_bullet("<b>Pathological Edge Cases:</b> Empty inputs, single-word provisions, and symbolic noise handled with zero unhandled exceptions.")

        # Section 12
        self.add_p("12. Forensic Error Analysis & Systemic Failure Mode Taxonomy (Task 023)", "Heading1")
        self.add_p(
            "Forensic error analysis dissected failure patterns across the full held-out test sets of LEDGAR and ContractNLI."
        )
        self.add_p("<b>The Macro-F1 Collapse Mechanism:</b>", "Heading2")
        self.add_p(
            "Macro-F1 is an unweighted arithmetic mean across all 12,407 evaluated classes. Because 2,833 classes (22.5%) have zero positive training examples "
            "in the 10% subset and 8,465 classes (67.1%) have under 10 examples, over 91.07% of classes have near-zero recall and F1=0, mathematically dragging "
            "the macro average down to 0.0045 despite solid head-class performance."
        )
        tier_data = [
            ["Taxonomy Tier", "Training Support", "Class Count", "Pct of Taxonomy", "Empirical Status & Explanation"],
            ["Zero-Shot Unlearned", "0 instances", "2,833", "22.47%", "0.0% theoretical recall; linear head received 0 updates; F1 = 0.0"],
            ["Extreme Tail Rare", "1 - 9 instances", "8,465", "67.14%", "Severely sparse supervision under BCE loss; unreliable boundaries"],
            ["Moderate Tail", "10 - 99 instances", "1,208", "9.58%", "Basic feature association learned, but constrained by frozen encoder"],
            ["Head Common", ">= 100 instances", "102", "0.81%", "Frequent clauses (Governing Law, Termination) driving Micro-F1 (0.1435)"]
        ]
        self.add_table(tier_data, [95, 75, 55, 65, 232])
        self.add_figure("figure5_class_distribution.png", "Figure 5: LEDGAR Long-Tail Class Imbalance and Macro-F1 Collapse Analysis", 480, 185)

        self.add_p("<b>ContractNLI Baseline Lexical Fallacy:</b>", "Heading2")
        self.add_p(
            "On ContractNLI (2,091 test pairs), the TF-IDF Linear SVM baseline achieved 65.57% accuracy (0.6557) and 0.5844 Macro-F1. "
            "However, 42.41% of NotMentioned instances (383 / 903) were misclassified as Entailment due to shared boilerplate vocabulary."
        )
        cm_data = [
            ["True Class", "Support", "Pred: Contradiction", "Pred: Entailment", "Pred: NotMentioned", "Dominant Confusion Flow", "Rate (%)"],
            ["Contradiction", "220", "81 (36.8%)", "90 (40.9%)", "49 (22.3%)", "Contradiction -> Entailment", "40.91%"],
            ["Entailment", "968", "20 (2.1%)", "834 (86.2%)", "114 (11.8%)", "Entailment -> NotMentioned", "11.78%"],
            ["NotMentioned", "903", "64 (7.1%)", "383 (42.4%)", "456 (50.5%)", "NotMentioned -> Entailment (Boilerplate)", "42.41%"]
        ]
        self.add_table(cm_data, [65, 42, 75, 75, 75, 140, 50])
        self.add_figure("figure6_contractnli_confusion.png", "Figure 6: ContractNLI Baseline Confusion Matrix & Lexical Overlap Flow", 390, 200)

        self.add_p("<b>Verified Concrete Error Cases (Forensic Audit):</b>", "Heading2")
        cases_data = [
            ["Case ID & Category", "Input Provision Snippet / Context", "Ground Truth vs Predicted", "Forensic Root Cause Analysis"],
            ["ERR_CASE_01<br/>Taxonomy Collision", "Agreement governed by laws of State of Delaware...", "GT: applicable laws, governing law<br/>Pred: governing laws", "Near-synonym variant in 12,407 schema penalized as 1 FP + 2 FNs."],
            ["ERR_CASE_02<br/>Subthreshold False Neg", "Either party may terminate without cause...", "GT: terminations, termination<br/>Pred: None (prob = 0.0092)", "Probability 0.0092 < tau*=0.04 threshold; target suppressed."],
            ["ERR_CASE_03<br/>Boilerplate False Entail", "Receiving party agrees to maintain confidentiality...", "GT: NotMentioned<br/>Pred: Entailment", "Common NDA vocabulary triggered false Entailment for missing public carveout."],
            ["ERR_CASE_04<br/>Function Word Saliency", "Agreement governed by laws of State of New York.", "Target: applicable laws<br/>Top: 'and' (1.84), 'the' (1.46)", "Gradient x Input highlighted grammar words rather than legal terms."]
        ]
        self.add_table(cases_data, [95, 145, 122, 160])

        self.add_p("<b>Systemic Failure Mode Taxonomy (FM-01 through FM-05):</b>", "Heading2")
        fm_data = [
            ["ID", "Taxonomy Level", "Failure Mode Name", "Description & Empirical Manifestation"],
            ["FM-01", "Data & Taxonomy", "Extreme Long-Tail Starvation", "2,833 zero-shot classes and 8,465 sparse classes (<10 ex) cause total Macro-F1 collapse (0.0045)."],
            ["FM-02", "Calibration", "Threshold Dilemma", "tau*=0.04 recovers 12.83x recall (12,699 TP) but inflates FP by 134.6x (58,947 FP), capping precision at 17.72%."],
            ["FM-03", "Architecture", "Linear Probe Bottleneck", "Frozen encoder features cannot adapt to multi-label legal risk boundaries, squashing prediction probabilities."],
            ["FM-04", "Baseline", "Lexical Overlap Artifact", "TF-IDF models misclassify 42.41% of absent provisions as Entailment due to shared boilerplate."],
            ["FM-05", "Explainability", "Function Word Saliency Bias", "Gradient x Input assigns peak attribution to syntax tokens ('and', 'the') rather than substantive terms."]
        ]
        self.add_table(fm_data, [45, 75, 120, 282])

        # Section 13
        self.add_p("13. Interactive Dashboard & Algorithmic Governance (Task 024)", "Heading1")
        self.add_p(
            "Task 024 delivered a dual-architecture governance interface providing auditability without modifying underlying models: "
            "(i) A live REST service built with Flask 3.1.0 (<code>src/dashboard/app.py</code>) exposing authenticated REST endpoints "
            "(<code>/api/provenance</code>, <code>/api/ledgar</code>, <code>/api/contractnli</code>, <code>/api/cross_domain</code>, "
            "<code>/api/robustness</code>, <code>/api/cases</code>, <code>/api/health</code>), and (ii) a standalone pre-compiled static dashboard "
            "(<code>results/task024/index.html</code>, 33.9 KB) viewable offline in any modern browser. "
            "A mandatory governance notice ('NOT A VALIDATED LEGAL DECISION-MAKER') is permanently embedded across all views."
        )

        # Section 14
        self.add_p("14. Comprehensive Results Synthesis & Comparative Discussion", "Heading1")
        self.add_p(
            "Synthesizing findings across Tasks 018 through 024 yields three fundamental conclusions for NLP in legal contracts:"
        )
        self.add_bullet("<b>Threshold Tuning is Imperative:</b> Standard 0.50 boundaries are catastrophic in extreme multi-label NLP, missing >99% of targets. Calibration is mandatory, but human oversight must manage the resulting false alarm inflation.")
        self.add_bullet("<b>Boilerplate Defeats Bag-of-Words:</b> Contract boilerplate invalidates lexical overlap baselines. Document NLI requires deep semantic understanding of conditions, exceptions, and scope negations.")
        self.add_bullet("<b>Attribution Saliency is Not Legal Justification:</b> Mathematical gradient attributions successfully locate sensitivity areas but frequently highlight grammatical syntax. Explanations must be treated as diagnostic aids, not legal proofs.")

        # Section 15
        self.add_p("15. Threats to Validity & Research Limitations", "Heading1")
        self.add_bullet("<b>Subsampling Bias:</b> Training on a 10% contract subset induced zero-shot starvation across 2,833 classes.")
        self.add_bullet("<b>Frozen Representation Bottleneck:</b> Freezing the 109.5M encoder constrained representation learning.")
        self.add_bullet("<b>Corpus Specialization:</b> LEDGAR is restricted to SEC filings; ContractNLI to NDAs; CUAD to procurement.")
        self.add_bullet("<b>Saliency Non-Axiomatic Nature:</b> Gradient x Input does not satisfy completeness axioms and exhibits syntax bias.")

        # Section 16
        self.add_p("16. Conclusions & Roadmap for Future Work", "Heading1")
        self.add_p(
            "The ContractRisk-XAI benchmark project has established a rigorous, evidence-grounded foundation for legal NLP research. "
            "Recommended future directions include: (1) unfreezing the upper transformer layers for end-to-end domain adaptation, "
            "(2) mapping the 12,407-label taxonomy into a hierarchical ontology (e.g. 50 macro concepts) to eliminate zero-shot collapse, "
            "(3) integrating axiomatic attribution methods (Integrated Gradients) to suppress function-word artifacts, and "
            "(4) conducting formal human-in-the-loop user studies with legal practitioners."
        )

        # Section 17
        self.add_p("17. Complete Verified References & Bibliography", "Heading1")
        refs_data = [
            ["Key", "Verified Citation & Bibliographic Metadata", "Venue / DOI / Source", "Registry Verification Status"],
            ["P001", "Chalkidis et al. (2020). LEGAL-BERT: The Muppets straight out of Law School.", "Findings of EMNLP 2020 | DOI: 10.18653/v1/2020.findings-emnlp.261", "VERIFIED (ACL Anthology; verified_papers.csv)"],
            ["P002", "Tuggener et al. (2020). LEDGAR: A Large-Scale Multi-label Corpus for Text Classification.", "LREC 2020 | https://aclanthology.org/2020.lrec-1.55/", "VERIFIED (ACL Anthology; verified_papers.csv)"],
            ["P003", "Koreeda & Manning (2021). ContractNLI: Dataset for Document-level NLI for Contracts.", "Findings of EMNLP 2021 | https://aclanthology.org/2021.findings-emnlp.164/", "VERIFIED (ACL Anthology; verified_papers.csv)"],
            ["CUAD", "Hendrycks et al. (2021). CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review.", "arXiv:2103.06268 | The Atticus Project (CC BY 4.0)", "VERIFIED (Atticus Project; verified_datasets.csv)"],
            ["P004", "Ruggeri et al. (2022). Detecting and Explaining Unfairness in Consumer Contracts (CLAUDETTE).", "Artificial Intelligence and Law, 30(2) | DOI: 10.1007/s10506-021-09288-2", "VERIFIED (Springer; verified_papers.csv)"],
            ["P005", "Moon et al. (2022). Automated Detection of Contractual Risk Clauses from Construction Specs.", "Automation in Construction, 140 | DOI: 10.1016/j.autcon.2022.104465", "VERIFIED (ScienceDirect; verified_papers.csv)"],
            ["P006", "Shuai (2023). A Rationale-Augmented NLP Framework to Identify Unilateral Change Risk.", "Computers in Industry, 151 | DOI: 10.1016/j.compind.2023.103940", "VERIFIED (ScienceDirect; verified_papers.csv)"],
            ["P007", "Zhou et al. (2023). Intelligent detection on construction project contract missing clauses.", "Eng. Const. & Arch. Mgmt, 32(3) | DOI: 10.1108/ECAM-02-2023-0172", "VERIFIED (Emerald Insight; verified_papers.csv)"],
            ["P008", "Singh et al. (2025). A Survey of Classification Tasks and Approaches for Legal Contracts.", "Artificial Intelligence Review, 58(2) | DOI: 10.1007/s10462-025-11359-8", "VERIFIED (Springer; verified_papers.csv)"],
            ["P009", "Liu et al. (2025). ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification.", "NLLP Workshop 2025 | https://aclanthology.org/2025.nllp-1.19/", "VERIFIED (ACL Anthology; verified_papers.csv)"],
            ["XAI", "Sundararajan et al. (2017). Axiomatic Attribution for Deep Networks (Integrated Gradients).", "ICML 2017 | PMLR 70:3319-3328", "METHODOLOGY (External ML reference; not in legal paper registry)"]
        ]
        self.add_table(refs_data, [35, 195, 152, 140])
        self.add_p(
            "<i>Note on Reference Verification: Papers P001-P009 and CUAD are verified against the authoritative legal research registries (verified_papers.csv and verified_datasets.csv). Sundararajan et al. (2017) is an external computer science methodology reference for Integrated Gradients and is flagged as an external methodological reference outside the legal corpus registry.</i>",
            "Caption"
        )

        # Section 18
        self.add_p("18. Artifact Provenance, Cryptographic Checksums & Audit Ledger", "Heading1")
        prov_data = [
            ["Component", "Source Artifact Relative Path", "Bytes", "SHA-256 Checksum", "Status"],
            ["Model Weights", "results/models/.../final_model/model.safetensors", "476,116,436", "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f", "VERIFIED"],
            ["Model Archive", "task019_fresh_colab_results_WITH_MODEL.zip", "441,575,824", "aca7529b79d8d7fd88155b14654ba425686775cb72e9982cb5e5e528b74c166a", "VERIFIED"],
            ["LEDGAR Eval", "results/.../calibrated/TASK019_..._CALIBRATED.json", "6,786", "fbd05ced725508b3c9d6d5eb9f5991d8bdc601d23578ec3067bcc0362d607b27", "VERIFIED"],
            ["ContractNLI", "results/baseline/contractnli/..._TFIDF_SVM.json", "2,119", "0e6eb4db9f406f1f13ae648d5902889562f81cffafbcb87e137f1c6261dc1b01", "VERIFIED"],
            ["Task 020 Manifest", "results/task020/task020_cross_domain_manifest.json", "16,370", "77faa3e6fc066d9db4683b337c11aa2e9c6584a7c5ded7c5f03b9ad7469db197", "VERIFIED"],
            ["Task 021 Manifest", "results/task021/task021_ablation_manifest.json", "10,081", "730b5b500ed827b042df01b09270865188d6486d75af50900d385e147e22be1f", "VERIFIED"],
            ["Task 022 Manifest", "results/task022/task022_robustness_manifest.json", "13,982", "a9f75b8e86428202df4667e943e205e6db47b8f5fd49a3aceca7f036c7445cf5", "VERIFIED"],
            ["Task 023 Manifest", "results/task023/task023_error_analysis_manifest.json", "9,388", "1df0170fccb731c48e0a10ce0cfd7e3f74bfb6bd138d6c425110bf2649302fd6", "VERIFIED"],
            ["Task 024 Manifest", "results/task024/task024_dashboard_manifest.json", "2,031", "66805ba5be8b071114da06aa1dd14bebf73369f5f23f118a67c357a882cc9d6a", "VERIFIED"]
        ]
        self.add_table(prov_data, [75, 175, 42, 175, 55])
        self.add_p(
            "<i>Forensic Resolution of Checksum Discrepancy: The hash prefix e3b0c44298fc1c149afbf4c8996fb924... previously reported in early draft manifests corresponds to hashlib.sha256(b'').hexdigest() (empty string placeholder). Recomputing SHA-256 over physical file bytes on disk resolves to 0e6eb4db9f406f1f13ae648d5902889562f81cffafbcb87e137f1c6261dc1b01 (2,119 bytes). All artifact hashes have been cross-verified against actual disk bytes and marked VERIFIED.</i>",
            "Caption"
        )

    def generate(self) -> str:
        self.build_report_content()
        self.doc.build(self.story, canvasmaker=NumberedCanvas)
        return self.output_pdf_path

def build_pdf_report(output_pdf_path: str, figures_dir: str) -> str:
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    builder = AcademicPDFReportBuilder(output_pdf_path, figures_dir)
    return builder.generate()

if __name__ == "__main__":
    pdf_out = os.path.join(WORKSPACE_ROOT, "results", "task025", "CONTRACTRISK_XAI_ACADEMIC_REPORT.pdf")
    fig_dir = os.path.join(WORKSPACE_ROOT, "results", "task025", "figures")
    build_pdf_report(pdf_out, fig_dir)
    print(f"Academic PDF Report compiled successfully at: {pdf_out}")
