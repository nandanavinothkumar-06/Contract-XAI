"""
Client-facing PDF Report Generator for Task 034 Final Lawyer-Reviewed Reports.

Features:
- Two-pass NumberedCanvas with running header and "Page X of Y" footer.
- Clear distinction between AI observations, lawyer decisions, corrections, and rejections.
- Rejected AI findings are explicitly marked as rejected by the lawyer, never presented as accepted conclusions.
- Preserves Indian statutory citations and retrieval disclaimers.
- Embeds mandatory legal disclaimers and SHA-256 integrity hash.
- Strictly excludes internal lawyer notes, tokens, or confidential comments.
- Handles Unicode characters safely.
"""

import os
import io
import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#0f172a")
DARK_BLUE = colors.HexColor("#1e293b")
ACCENT_BLUE = colors.HexColor("#2563eb")
ACCENT_CYAN = colors.HexColor("#0284c7")
EMERALD = colors.HexColor("#059669")
EMERALD_BG = colors.HexColor("#ecfdf5")
AMBER = colors.HexColor("#d97706")
AMBER_BG = colors.HexColor("#fffbeb")
ROSE = colors.HexColor("#dc2626")
ROSE_BG = colors.HexColor("#fef2f2")
GREY_TEXT = colors.HexColor("#475569")
LIGHT_BG = colors.HexColor("#f8fafc")
BORDER_GREY = colors.HexColor("#cbd5e1")
WHITE = colors.HexColor("#ffffff")

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 40.0
PRINTABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN


class ClientReportNumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for running header and page numbering ('Page X of Y').
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
        self.setFont("Helvetica", 8)
        self.setFillColor(GREY_TEXT)

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(MARGIN, PAGE_HEIGHT - 28, "ContractRisk-XAI — Final Lawyer-Reviewed Report")
            page_info = f"Page {self._pageNumber} of {total_pages}"
            self.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 28, page_info)
            self.setStrokeColor(BORDER_GREY)
            self.setLineWidth(0.5)
            self.line(MARGIN, PAGE_HEIGHT - 32, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32)

        # Running Footer (all pages)
        self.setStrokeColor(BORDER_GREY)
        self.setLineWidth(0.5)
        self.line(MARGIN, 32, PAGE_WIDTH - MARGIN, 32)

        disclaimer_note = "AI-ASSISTED LEGAL DECISION SUPPORT — NOT A CERTIFICATE OF STATUTORY COMPLIANCE"
        self.drawString(MARGIN, 22, disclaimer_note)
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(PAGE_WIDTH - MARGIN, 22, page_str)

        self.restoreState()


class ClientPDFReportBuilder:
    """
    Builds a professional, client-ready lawyer review report PDF.
    """
    def __init__(self, report_payload: Dict[str, Any], output_path: Optional[str] = None):
        self.payload = report_payload
        self.output_path = output_path
        self.styles = self._setup_styles()
        self.story = []

    def _setup_styles(self) -> Dict[str, ParagraphStyle]:
        base_styles = getSampleStyleSheet()
        custom = {}

        custom["Title"] = ParagraphStyle(
            "ReportTitle",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=NAVY,
            alignment=0,
            spaceAfter=4,
        )

        custom["Subtitle"] = ParagraphStyle(
            "ReportSubtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=ACCENT_BLUE,
            spaceAfter=12,
        )

        custom["DraftBanner"] = ParagraphStyle(
            "DraftBanner",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=ROSE,
            alignment=1,
            spaceAfter=10,
        )

        custom["H1"] = ParagraphStyle(
            "Heading1",
            parent=base_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )

        custom["H2"] = ParagraphStyle(
            "Heading2",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=DARK_BLUE,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        )

        custom["Body"] = ParagraphStyle(
            "Body",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
            spaceAfter=6,
        )

        custom["BodyMuted"] = ParagraphStyle(
            "BodyMuted",
            parent=custom["Body"],
            textColor=GREY_TEXT,
        )

        custom["BodySmall"] = ParagraphStyle(
            "BodySmall",
            parent=custom["Body"],
            fontSize=8,
            leading=11,
            textColor=GREY_TEXT,
        )

        custom["MetaLabel"] = ParagraphStyle(
            "MetaLabel",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=DARK_BLUE,
        )

        custom["MetaVal"] = ParagraphStyle(
            "MetaVal",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=NAVY,
        )

        custom["ClauseText"] = ParagraphStyle(
            "ClauseText",
            parent=base_styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=DARK_BLUE,
        )

        custom["BadgeAccepted"] = ParagraphStyle(
            "BadgeAccepted",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=EMERALD,
        )

        custom["BadgeRejected"] = ParagraphStyle(
            "BadgeRejected",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=ROSE,
        )

        custom["BadgeModified"] = ParagraphStyle(
            "BadgeModified",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=AMBER,
        )

        custom["Disclaimer"] = ParagraphStyle(
            "Disclaimer",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10.5,
            textColor=GREY_TEXT,
            spaceAfter=4,
        )

        return custom

    def _clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        # Safe XML escaping for ReportLab Paragraphs
        cleaned = (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
        return cleaned

    def build(self) -> bytes:
        """Compiles the document story and returns bytes (or writes to output_path)."""
        buffer = io.BytesIO()
        target = self.output_path if self.output_path else buffer

        doc = SimpleDocTemplate(
            target,
            pagesize=letter,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=42,
            bottomMargin=42
        )

        meta = self.payload.get("metadata", {})
        exec_sum = self.payload.get("executive_summary", {})
        findings = self.payload.get("findings", [])
        is_final = meta.get("is_final", True)

        # 1. Header Banner & Status
        if not is_final:
            self.story.append(Paragraph("&#9888; DRAFT — PRELIMINARY ASSESSMENT — NOT A FINAL LAWYER REPORT &#9888;", self.styles["DraftBanner"]))

        self.story.append(Paragraph("LEGAL RISK ASSESSMENT &amp; LAWYER REVIEW REPORT", self.styles["Title"]))
        
        status_text = "FINAL LAWYER-REVIEWED REPORT" if is_final else "DRAFT PREVIEW"
        sub_text = f"Report Ref: <b>{self._clean_text(meta.get('report_number'))}</b> | Version {meta.get('report_version', 1)} | Status: <b>{status_text}</b>"
        self.story.append(Paragraph(sub_text, self.styles["Subtitle"]))
        self.story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_BLUE, spaceAfter=8))

        # 2. Metadata Grid Table
        meta_data = [
            [
                Paragraph("<b>Document Name:</b>", self.styles["MetaLabel"]),
                Paragraph(self._clean_text(meta.get("original_filename")), self.styles["MetaVal"]),
                Paragraph("<b>Doc Version:</b>", self.styles["MetaLabel"]),
                Paragraph(str(meta.get("document_version", 1)), self.styles["MetaVal"]),
            ],
            [
                Paragraph("<b>Reviewing Advocate:</b>", self.styles["MetaLabel"]),
                Paragraph(self._clean_text(meta.get("assigned_lawyer_name")), self.styles["MetaVal"]),
                Paragraph("<b>Bar Enrolment:</b>", self.styles["MetaLabel"]),
                Paragraph(self._clean_text(meta.get("bar_enrolment_id") or "Not recorded"), self.styles["MetaVal"]),
            ],
            [
                Paragraph("<b>Review Completed:</b>", self.styles["MetaLabel"]),
                Paragraph(self._clean_text(meta.get("review_completed_at") or meta.get("generated_at")), self.styles["MetaVal"]),
                Paragraph("<b>Report Generated:</b>", self.styles["MetaLabel"]),
                Paragraph(self._clean_text(meta.get("generated_at")), self.styles["MetaVal"]),
            ],
            [
                Paragraph("<b>File Integrity SHA-256:</b>", self.styles["MetaLabel"]),
                Paragraph(f"<font size=7>{self._clean_text(meta.get('file_sha256')[:24])}...</font>", self.styles["MetaVal"]),
                Paragraph("<b>Report SHA-256:</b>", self.styles["MetaLabel"]),
                Paragraph(f"<font size=7>{self._clean_text(meta.get('content_sha256')[:24])}...</font>", self.styles["MetaVal"]),
            ],
        ]

        t_meta = Table(meta_data, colWidths=[110, 155, 100, 165])
        t_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.story.append(t_meta)
        self.story.append(Spacer(1, 10))

        # 3. Executive Summary
        self.story.append(Paragraph("1. Executive Summary &amp; Scope of Review", self.styles["H1"]))
        
        exec_text = exec_sum.get("key_findings_summary") or "Comprehensive lawyer review conducted."
        self.story.append(Paragraph(f"<b>Review Summary:</b> {self._clean_text(exec_text)}", self.styles["Body"]))

        scope_text = exec_sum.get("scope_of_review") or "Standard contractual risk and legal compliance assessment."
        self.story.append(Paragraph(f"<b>Scope:</b> {self._clean_text(scope_text)}", self.styles["Body"]))

        # Counts Table
        counts_data = [
            [
                Paragraph("<b>Total Findings</b>", self.styles["MetaLabel"]),
                Paragraph("<b>Accepted AI</b>", self.styles["MetaLabel"]),
                Paragraph("<b>Corrected</b>", self.styles["MetaLabel"]),
                Paragraph("<b>Rejected AI</b>", self.styles["MetaLabel"]),
                Paragraph("<b>Lawyer Authored</b>", self.styles["MetaLabel"]),
            ],
            [
                Paragraph(str(exec_sum.get("total_findings_count", len(findings))), self.styles["MetaVal"]),
                Paragraph(str(exec_sum.get("accepted_ai_findings_count", 0)), self.styles["MetaVal"]),
                Paragraph(str(exec_sum.get("corrected_findings_count", 0)), self.styles["MetaVal"]),
                Paragraph(str(exec_sum.get("rejected_ai_findings_count", 0)), self.styles["MetaVal"]),
                Paragraph(str(exec_sum.get("lawyer_authored_findings_count", 0)), self.styles["MetaVal"]),
            ]
        ]
        t_counts = Table(counts_data, colWidths=[106, 106, 106, 106, 106])
        t_counts.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        self.story.append(t_counts)
        self.story.append(Spacer(1, 8))

        if exec_sum.get("outstanding_limitations"):
            self.story.append(Paragraph(f"<b>Outstanding Limitations:</b> {self._clean_text(exec_sum.get('outstanding_limitations'))}", self.styles["Body"]))
        if exec_sum.get("unresolved_questions"):
            self.story.append(Paragraph(f"<b>Unresolved Questions / Clarifications:</b> {self._clean_text(exec_sum.get('unresolved_questions'))}", self.styles["Body"]))

        self.story.append(Spacer(1, 8))

        # 4. Detailed Reviewed Findings
        self.story.append(Paragraph("2. Detailed Findings &amp; Lawyer Determinations", self.styles["H1"]))
        self.story.append(Paragraph(
            "Each finding below reflects human advocate evaluation. AI observations are strictly segregated from "
            "lawyer conclusions, and any AI observation rejected by the advocate is explicitly identified.",
            self.styles["BodyMuted"]
        ))
        self.story.append(Spacer(1, 6))

        if not findings:
            self.story.append(Paragraph("<i>No specific clause findings were released for this review.</i>", self.styles["BodyMuted"]))
        else:
            for idx, f in enumerate(findings, 1):
                f_flowables = []
                clause_hdr = f.get("clause_heading") or f"Clause Segment {f.get('segment_id', 'N/A')}"
                origin = f.get("finding_origin", "AI_GENERATED")
                decision = f.get("lawyer_decision", "UNREVIEWED")
                is_rejected = f.get("is_ai_observation_rejected", False) or decision == "REJECT_AI_OBSERVATION"

                # Decision badge
                if is_rejected:
                    badge_style = self.styles["BadgeRejected"]
                    badge_bg = ROSE_BG
                    decision_display = f"&#10006; REJECTED BY ADVOCATE ({decision})"
                elif decision in ("ACCEPT", "ACCEPTED", "ACCEPT_AI_OBSERVATION"):
                    badge_style = self.styles["BadgeAccepted"]
                    badge_bg = EMERALD_BG
                    decision_display = f"&#10004; ACCEPTED BY ADVOCATE ({decision})"
                else:
                    badge_style = self.styles["BadgeModified"]
                    badge_bg = AMBER_BG
                    decision_display = f"&#9998; {decision}"

                f_flowables.append(Paragraph(f"<b>Finding {idx}: {self._clean_text(clause_hdr)}</b>", self.styles["H2"]))

                # Clause text box
                excerpt = f.get("clause_text_excerpt") or ""
                clause_p = Paragraph(f"<b>Clause Excerpt:</b> <i>&ldquo;{self._clean_text(excerpt)}&rdquo;</i>", self.styles["ClauseText"])
                
                # Finding details table
                rows = [
                    [Paragraph("<b>Origin:</b>", self.styles["MetaLabel"]), Paragraph(self._clean_text(origin), self.styles["MetaVal"])],
                    [Paragraph("<b>Evidence Quality:</b>", self.styles["MetaLabel"]), Paragraph(self._clean_text(f.get("evidence_quality_status", "NO_MATCHING_EVIDENCE")), self.styles["MetaVal"])],
                ]

                if f.get("ai_observation"):
                    rows.append([
                        Paragraph("<b>AI Observation:</b>", self.styles["MetaLabel"]),
                        Paragraph(self._clean_text(f.get("ai_observation")), self.styles["MetaVal"])
                    ])

                if f.get("ai_metadata") and isinstance(f["ai_metadata"], dict):
                    ai_meta = f["ai_metadata"]
                    m_name = ai_meta.get("model_name", "legalbert-base-uncased")
                    m_ver = ai_meta.get("model_version", "1.0.0")
                    rows.append([
                        Paragraph("<b>Model Identity:</b>", self.styles["MetaLabel"]),
                        Paragraph(f"{self._clean_text(m_name)} (v{self._clean_text(m_ver)}) &mdash; Statistical observation, not a legal opinion", self.styles["BodySmall"])
                    ])

                if f.get("model_attribution") and isinstance(f["model_attribution"], dict):
                    attrib = f["model_attribution"]
                    spans = attrib.get("attributed_spans") or attrib.get("evidence_spans") or []
                    spans_text = ", ".join([f'"{s.get("text", "")}" ({round(float(s.get("raw_score", 0.0)), 3)})' for s in spans[:3]]) if spans else "Unavailable"
                    rows.append([
                        Paragraph("<b>Model Explanation:</b>", self.styles["MetaLabel"]),
                        Paragraph(f"Method: {self._clean_text(attrib.get('method', 'GradientXInput'))} &bull; Attributed spans: {self._clean_text(spans_text)}", self.styles["BodySmall"])
                    ])

                rows.append([
                    Paragraph("<b>Advocate Decision:</b>", self.styles["MetaLabel"]),
                    Paragraph(f"<font color='{badge_style.textColor.hexval()}'><b>{decision_display}</b></font>", badge_style)
                ])

                rows.append([
                    Paragraph("<b>Advocate Rationale:</b>", self.styles["MetaLabel"]),
                    Paragraph(self._clean_text(f.get("lawyer_rationale") or "No rationale recorded."), self.styles["MetaVal"])
                ])

                # Statutory references
                stat_refs = f.get("statutory_references", [])
                if stat_refs:
                    stat_paras = []
                    for s in stat_refs:
                        chk_str = f" | SHA-256: {self._clean_text(s.get('source_checksum', '')[:10])}..." if s.get("source_checksum") else ""
                        stat_text = (
                            f"<b>{self._clean_text(s.get('act_name'))}</b>, Section {self._clean_text(s.get('section'))}: "
                            f"{self._clean_text(s.get('excerpt'))[:140]}... "
                            f"<font size=7 color='#64748b'>[Curated Extract v{self._clean_text(s.get('snapshot_version', '1.0'))}{chk_str}]</font>"
                        )
                        stat_paras.append(Paragraph(stat_text, self.styles["BodySmall"]))
                    rows.append([
                        Paragraph("<b>Statutory Grounding:</b>", self.styles["MetaLabel"]),
                        stat_paras
                    ])

                t_finding = Table(rows, colWidths=[130, 400])
                t_finding.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]))

                f_flowables.append(clause_p)
                f_flowables.append(Spacer(1, 3))
                f_flowables.append(t_finding)
                f_flowables.append(Spacer(1, 8))

                self.story.append(KeepTogether(f_flowables))

        # 5. Statutory Corpus Notice & Retrieval Caveats
        self.story.append(Spacer(1, 8))
        self.story.append(Paragraph("3. Statutory Corpus Limitations &amp; Score Semantics", self.styles["H1"]))
        
        stat_notice = self.payload.get("statutory_corpus_notice", "")
        self.story.append(Paragraph(self._clean_text(stat_notice), self.styles["Disclaimer"]))

        score_notice = (
            "BM25 and lexical retrieval relevance metrics are computational relevance indicators only. "
            "They do not indicate legal certainty, statutory bindingness, or court interpretation."
        )
        self.story.append(Paragraph(self._clean_text(score_notice), self.styles["Disclaimer"]))

        # 6. Mandatory Disclaimers & Legal Liability Notice
        self.story.append(Spacer(1, 8))
        self.story.append(Paragraph("4. Mandatory Legal Disclaimers &amp; Terms of Use", self.styles["H1"]))
        
        legal_disclaimer = self.payload.get("disclaimer_and_limitations", "")
        self.story.append(Paragraph(self._clean_text(legal_disclaimer), self.styles["Disclaimer"]))

        # Build Document
        doc.build(self.story, canvasmaker=ClientReportNumberedCanvas)

        if self.output_path:
            with open(self.output_path, "rb") as f:
                return f.read()
        else:
            buffer.seek(0)
            return buffer.getvalue()
