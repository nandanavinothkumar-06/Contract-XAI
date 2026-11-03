"""
Generate high-fidelity PowerPoint presentation for CONTRACTRISK-XAI Final Project Evaluation.
Outputs: CONTRACTRISK_XAI_Final_Presentation.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_TICK_MARK, XL_LABEL_POSITION

def create_deck(output_path="CONTRACTRISK_XAI_Final_Presentation.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Theme Colors
    NAVY = RGBColor(26, 54, 93)       # #1A365D Primary dark
    SLATE_DARK = RGBColor(15, 23, 42)  # #0F172A Body header
    BLUE_ACCENT = RGBColor(14, 116, 144) # #0E7490 Teal / Accent Blue
    CYAN_ACCENT = RGBColor(2, 132, 199) # #0284C7 Bright blue
    MUTED = RGBColor(100, 116, 139)    # #64748B Secondary text
    LIGHT_BG = RGBColor(248, 250, 252) # #F8FAFC Slide background
    CARD_BG = RGBColor(255, 255, 255)  # White card
    CARD_BORDER = RGBColor(226, 232, 240) # Card outline
    BAR_BG = RGBColor(241, 245, 249)   # Sub-banner fill
    GREEN_ACCEPT = RGBColor(22, 163, 74)
    RED_WITHHOLD = RGBColor(220, 38, 38)
    WHITE = RGBColor(255, 255, 255)

    def set_slide_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = LIGHT_BG
        bg.line.fill.background() # No line
        return bg

    def add_header(slide, section_tag, main_title, subtitle=None):
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.3))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p0 = tf.paragraphs[0]
        p0.text = section_tag.upper()
        p0.font.name = "Calibri"
        p0.font.size = Pt(11)
        p0.font.bold = True
        p0.font.color.rgb = BLUE_ACCENT
        p0.space_after = Pt(2)

        p1 = tf.add_paragraph()
        p1.text = main_title
        p1.font.name = "Calibri"
        p1.font.size = Pt(24)
        p1.font.bold = True
        p1.font.color.rgb = SLATE_DARK
        p1.space_after = Pt(3)

        if subtitle:
            p2 = tf.add_paragraph()
            p2.text = subtitle
            p2.font.name = "Calibri"
            p2.font.size = Pt(13)
            p2.font.color.rgb = MUTED

    def add_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1)
        else:
            card.line.fill.background()
        return card

    # ==========================================
    # SLIDE 1: Title Slide
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    # Decorative top bar
    top_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = NAVY
    top_bar.line.fill.background()

    # Evaluation Tag
    eval_box = s1.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(11.3), Inches(0.4))
    tf1 = eval_box.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "FINAL PROJECT EVALUATION · 2026"
    p.font.name = "Calibri"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT

    # Main Title & Subtitle
    title_box = s1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(1.5))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_t = tf_title.paragraphs[0]
    p_t.text = "CONTRACTRISK-XAI"
    p_t.font.name = "Calibri"
    p_t.font.size = Pt(44)
    p_t.font.bold = True
    p_t.font.color.rgb = NAVY

    p_sub = tf_title.add_paragraph()
    p_sub.text = "An evidence-aware explainable NLP framework for commercial contract risk analysis"
    p_sub.font.name = "Calibri"
    p_sub.font.size = Pt(18)
    p_sub.font.color.rgb = MUTED
    p_sub.space_before = Pt(6)

    # Authors Card (Left)
    add_card(s1, Inches(1.0), Inches(2.9), Inches(5.4), Inches(2.3))
    auth_box = s1.shapes.add_textbox(Inches(1.2), Inches(3.05), Inches(5.0), Inches(2.0))
    tf_auth = auth_box.text_frame
    tf_auth.word_wrap = True
    p = tf_auth.paragraphs[0]
    p.text = "PROJECT TEAM"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_after = Pt(8)

    members = [
        "SRI LATHIKA .V.S  –  23MID0213",
        "OVIYA .B  –  23MID0244",
        "NANDANA .V  –  23MID0251"
    ]
    for m in members:
        pm = tf_auth.add_paragraph()
        pm.text = m
        pm.font.name = "Calibri"
        pm.font.size = Pt(14)
        pm.font.bold = True
        pm.font.color.rgb = SLATE_DARK
        pm.space_after = Pt(4)

    # Guide & Institution Card (Right)
    add_card(s1, Inches(6.7), Inches(2.9), Inches(5.6), Inches(2.3))
    guide_box = s1.shapes.add_textbox(Inches(6.9), Inches(3.05), Inches(5.2), Inches(2.0))
    tf_g = guide_box.text_frame
    tf_g.word_wrap = True
    p = tf_g.paragraphs[0]
    p.text = "PROJECT GUIDE & AFFILIATION"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_after = Pt(8)

    pg = tf_g.add_paragraph()
    pg.text = "PROJECT GUIDE: ARIVOLI A"
    pg.font.name = "Calibri"
    pg.font.size = Pt(15)
    pg.font.bold = True
    pg.font.color.rgb = SLATE_DARK
    pg.space_after = Pt(6)

    p_dept = tf_g.add_paragraph()
    p_dept.text = "SCHOOL OF COMPUTER SCIENCE AND ENGINEERING\nVELLORE INSTITUTE OF TECHNOLOGY (VIT)"
    p_dept.font.name = "Calibri"
    p_dept.font.size = Pt(12)
    p_dept.font.color.rgb = MUTED

    # Bottom Prototype Banner
    add_card(s1, Inches(1.0), Inches(5.4), Inches(11.3), Inches(1.3), bg_color=CARD_BG, border_color=CYAN_ACCENT)
    proto_box = s1.shapes.add_textbox(Inches(1.2), Inches(5.5), Inches(10.9), Inches(1.1))
    tf_proto = proto_box.text_frame
    tf_proto.word_wrap = True
    p = tf_proto.paragraphs[0]
    p.text = "DECISION-SUPPORT PROTOTYPE · XAI"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_ACCENT
    p.space_after = Pt(3)

    p_desc = tf_proto.add_paragraph()
    p_desc.text = "Analyse contract clauses, identify potential risks, retrieve supporting statutory passages, and withhold findings when evidence is insufficient."
    p_desc.font.name = "Calibri"
    p_desc.font.size = Pt(13)
    p_desc.font.color.rgb = SLATE_DARK

    p_ft = tf_proto.add_paragraph()
    p_ft.text = "ACADEMIC YEAR · 2026"
    p_ft.font.name = "Calibri"
    p_ft.font.size = Pt(10)
    p_ft.font.bold = True
    p_ft.font.color.rgb = MUTED
    p_ft.space_before = Pt(4)

    # ==========================================
    # SLIDE 2: The Problem
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "THE PROBLEM", "Confidence is not evidence.", "6 core challenges · Contract review needs evidence, not confidence alone")

    cards_s2 = [
        ("Why review is hard",
         "Commercial contracts contain obligations, liabilities, confidentiality requirements, and legal conditions. Manual review is time-consuming."),
        ("Where systems fail",
         "Extreme multi-label imbalance, clause identification, limited interpretability, unsupported statutory references, version inconsistency, and over-reliance on confidence."),
        ("Research question",
         "Can evidence sufficiency, source verification, and document-version consistency reduce unsupported findings versus confidence-only screening?"),
        ("Objectives",
         "LegalBERT classification, Gradient × Input attribution, BM25 retrieval, evidence-quality evaluation, abstention, and lawyer-supervised review.")
    ]

    coords_s2 = [
        (Inches(0.8), Inches(1.9)),
        (Inches(6.8), Inches(1.9)),
        (Inches(0.8), Inches(4.5)),
        (Inches(6.8), Inches(4.5))
    ]

    for (title, text), (l, t) in zip(cards_s2, coords_s2):
        add_card(s2, l, t, Inches(5.7), Inches(2.4))
        tb = s2.shapes.add_textbox(l + Inches(0.3), t + Inches(0.25), Inches(5.1), Inches(1.9))
        tf = tb.text_frame
        tf.word_wrap = True
        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.name = "Calibri"
        p_t.font.size = Pt(17)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY
        p_t.space_after = Pt(8)

        p_b = tf.add_paragraph()
        p_b.text = text
        p_b.font.name = "Calibri"
        p_b.font.size = Pt(13)
        p_b.font.color.rgb = MUTED

    # ==========================================
    # SLIDE 3: Novelty
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "NOVELTY", "The novelty is a traceable evidence-aware decision workflow",
               "Integrates evidence sufficiency, statutory grounding, source-verification status, document-version consistency, and abstention into one traceable decision-support workflow. The classifier is an existing LegalBERT model; no new transformer architecture is claimed.")

    workflow_steps = [
        "01 Contract Upload",
        "02 Validation & Hashing",
        "03 Text Extraction",
        "04 Clause Segmentation",
        "05 LegalBERT Inference",
        "06 Taxonomy Mapping",
        "07 BM25 Retrieval",
        "08 Gradient × Input",
        "09 Evidence Abstention",
        "10 Lawyer Review"
    ]

    step_w = Inches(2.2)
    step_h = Inches(1.0)
    for i, step in enumerate(workflow_steps):
        row = i // 5
        col = i % 5
        x = Inches(0.8) + col * Inches(2.38)
        y = Inches(2.1) + row * Inches(1.2)
        add_card(s3, x, y, step_w, step_h)
        tb = s3.shapes.add_textbox(x + Inches(0.1), y + Inches(0.15), step_w - Inches(0.2), step_h - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        parts = step.split(" ", 1)
        p.text = parts[0]
        p.font.name = "Calibri"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = BLUE_ACCENT
        p.space_after = Pt(2)

        p2 = tf.add_paragraph()
        p2.text = parts[1]
        p2.font.name = "Calibri"
        p2.font.size = Pt(12)
        p2.font.bold = True
        p2.font.color.rgb = SLATE_DARK

    # Outcome Decision Boxes (ACCEPT vs WITHHOLD)
    # ACCEPT
    add_card(s3, Inches(0.8), Inches(4.8), Inches(5.7), Inches(1.9), bg_color=CARD_BG, border_color=GREEN_ACCEPT)
    tb_acc = s3.shapes.add_textbox(Inches(1.1), Inches(4.95), Inches(5.1), Inches(1.6))
    tf_acc = tb_acc.text_frame
    tf_acc.word_wrap = True
    p = tf_acc.paragraphs[0]
    p.text = "ACCEPT"
    p.font.name = "Calibri"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = GREEN_ACCEPT
    p.space_after = Pt(4)

    p_acc_body = tf_acc.add_paragraph()
    p_acc_body.text = "Required checks pass → Routed directly to verified Advocate Review Workbench with full token attribution and verified statutory grounding."
    p_acc_body.font.name = "Calibri"
    p_acc_body.font.size = Pt(13)
    p_acc_body.font.color.rgb = SLATE_DARK

    # WITHHOLD
    add_card(s3, Inches(6.8), Inches(4.8), Inches(5.7), Inches(1.9), bg_color=CARD_BG, border_color=RED_WITHHOLD)
    tb_wth = s3.shapes.add_textbox(Inches(7.1), Inches(4.95), Inches(5.1), Inches(1.6))
    tf_wth = tb_wth.text_frame
    tf_wth.word_wrap = True
    p = tf_wth.paragraphs[0]
    p.text = "WITHHOLD"
    p.font.name = "Calibri"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = RED_WITHHOLD
    p.space_after = Pt(4)

    p_wth_body = tf_wth.add_paragraph()
    p_wth_body.text = "Insufficient evidence, sub-threshold confidence, or failed validation → Finding withheld as NO_ACTIONABLE_RISK; attribution cleanly suppressed."
    p_wth_body.font.name = "Calibri"
    p_wth_body.font.size = Pt(13)
    p_wth_body.font.color.rgb = SLATE_DARK

    # ==========================================
    # SLIDE 4: Experimental Backbone
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, "EXPERIMENTAL BACKBONE", "LegalBERT provides the experimental classification backbone",
               "Multi-label linear probe configuration over a frozen transformer encoder trained with binary cross-entropy.")

    # 5-step model sequence
    model_seq = [
        ("01 Clause", "Contract clause"),
        ("02 Tokens", "WordPiece Tokenizer"),
        ("03 Encoder", "LegalBERT (Frozen)"),
        ("04 Head", "Linear Probe Head"),
        ("05 Scores", "Multi-Label Sigmoid")
    ]
    for i, (step_t, step_d) in enumerate(model_seq):
        x = Inches(0.8) + i * Inches(2.38)
        y = Inches(1.8)
        add_card(s4, x, y, Inches(2.2), Inches(1.1))
        tb = s4.shapes.add_textbox(x + Inches(0.1), y + Inches(0.15), Inches(2.0), Inches(0.8))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = step_t
        p1.font.name = "Calibri"
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = BLUE_ACCENT

        p2 = tf.add_paragraph()
        p2.text = step_d
        p2.font.name = "Calibri"
        p2.font.size = Pt(11)
        p2.font.color.rgb = SLATE_DARK

    # 3 Large Callouts
    stat_callouts = [
        ("12,407", "LEDGAR OUTPUT LABELS", "Extensive legal taxonomy covering multi-label commercial provisions"),
        ("0.04", "OPERATING THRESHOLD", "Empirically calibrated to maximize validation F1 and prevent omission"),
        ("SEVERE", "LONG-TAIL IMBALANCE", "91.1% of taxonomy classes have fewer than 10 training examples")
    ]
    for i, (val, lbl, note) in enumerate(stat_callouts):
        x = Inches(0.8) + i * Inches(3.98)
        y = Inches(3.2)
        add_card(s4, x, y, Inches(3.8), Inches(1.8))
        tb = s4.shapes.add_textbox(x + Inches(0.2), y + Inches(0.2), Inches(3.4), Inches(1.4))
        tf = tb.text_frame
        tf.word_wrap = True
        p_val = tf.paragraphs[0]
        p_val.text = val
        p_val.font.name = "Calibri"
        p_val.font.size = Pt(28)
        p_val.font.bold = True
        p_val.font.color.rgb = CYAN_ACCENT

        p_lbl = tf.add_paragraph()
        p_lbl.text = lbl
        p_lbl.font.name = "Calibri"
        p_lbl.font.size = Pt(12)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = NAVY
        p_lbl.space_after = Pt(2)

        p_note = tf.add_paragraph()
        p_note.text = note
        p_note.font.name = "Calibri"
        p_note.font.size = Pt(11)
        p_note.font.color.rgb = MUTED

    # Tech Stack & Boundary Banners
    add_card(s4, Inches(0.8), Inches(5.3), Inches(11.733), Inches(0.7), bg_color=BAR_BG, border_color=None)
    tb_stk = s4.shapes.add_textbox(Inches(1.0), Inches(5.35), Inches(11.3), Inches(0.6))
    tf_stk = tb_stk.text_frame
    tf_stk.word_wrap = True
    p = tf_stk.paragraphs[0]
    p.text = "STACK: Python · PyTorch 2.6.0 · Hugging Face Transformers · LegalBERT · scikit-learn · Flask 3.1.0 · SQLAlchemy · Okapi BM25 · Pytest"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = SLATE_DARK

    add_card(s4, Inches(0.8), Inches(6.15), Inches(11.733), Inches(0.95))
    tb_bnd = s4.shapes.add_textbox(Inches(1.0), Inches(6.25), Inches(11.3), Inches(0.8))
    tf_bnd = tb_bnd.text_frame
    tf_bnd.word_wrap = True
    p = tf_bnd.paragraphs[0]
    p.text = "EXPERIMENTAL BOUNDARY & DISCLAIMER:"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_after = Pt(2)

    p2 = tf_bnd.add_paragraph()
    p2.text = "LEDGAR reports 12,407 output labels. Threshold selection affects precision and recall; extreme label imbalance affects performance. This prototype is an academic benchmark and is not a validated Indian legal risk detector."
    p2.font.name = "Calibri"
    p2.font.size = Pt(11)
    p2.font.color.rgb = MUTED

    # ==========================================
    # SLIDE 5: Inspectability
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, "INSPECTABILITY", "Explanations and statutory retrieval make findings inspectable",
               "First-order input sensitivity coupled with lexical statutory retrieval.")

    # Formula Box
    add_card(s5, Inches(0.8), Inches(1.8), Inches(11.733), Inches(1.6))
    tb_fm = s5.shapes.add_textbox(Inches(1.1), Inches(1.95), Inches(11.1), Inches(1.3))
    tf_fm = tb_fm.text_frame
    tf_fm.word_wrap = True
    p_fm = tf_fm.paragraphs[0]
    p_fm.text = "Saliency(wt) = | ∇e_t z_c(x) · e_t |"
    p_fm.font.name = "Consolas"
    p_fm.font.size = Pt(20)
    p_fm.font.bold = True
    p_fm.font.color.rgb = CYAN_ACCENT
    p_fm.space_after = Pt(4)

    p_fm_desc = tf_fm.add_paragraph()
    p_fm_desc.text = "Gradient × Input produces token-level attribution aligned through tokenizer offsets to the original clause, with special-token handling. Attribution is strictly suppressed when a finding is withheld."
    p_fm_desc.font.name = "Calibri"
    p_fm_desc.font.size = Pt(12)
    p_fm_desc.font.color.rgb = SLATE_DARK

    p_fm_warn = tf_fm.add_paragraph()
    p_fm_warn.text = "ATTRIBUTION HELPS INSPECT MODEL BEHAVIOUR BUT DOES NOT ESTABLISH CAUSAL EXPLANATION."
    p_fm_warn.font.name = "Calibri"
    p_fm_warn.font.size = Pt(10)
    p_fm_warn.font.bold = True
    p_fm_warn.font.color.rgb = MUTED
    p_fm_warn.space_before = Pt(3)

    # 3 Pillar Cards
    pillars = [
        ("Gradient × Input", "Maps model sensitivity back to clause tokens with 100% bijective character slicing: source[start:end] == span.text."),
        ("BM25 Retrieval", "Scores a clause query against curated statutory passages using exact lexical matching, avoiding dense semantic drift."),
        ("Passage Evidence", "Retrieves and surfaces indexed passages for human assessment across 40 curated sections from 6 Indian commercial statutes.")
    ]
    for i, (p_t, p_d) in enumerate(pillars):
        x = Inches(0.8) + i * Inches(3.98)
        y = Inches(3.6)
        add_card(s5, x, y, Inches(3.8), Inches(2.4))
        tb = s5.shapes.add_textbox(x + Inches(0.25), y + Inches(0.25), Inches(3.3), Inches(2.0))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = p_t
        p1.font.name = "Calibri"
        p1.font.size = Pt(16)
        p1.font.bold = True
        p1.font.color.rgb = NAVY
        p1.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = p_d
        p2.font.name = "Calibri"
        p2.font.size = Pt(12)
        p2.font.color.rgb = MUTED

    # Bottom notice
    add_card(s5, Inches(0.8), Inches(6.2), Inches(11.733), Inches(0.8), bg_color=BAR_BG, border_color=None)
    tb_nt = s5.shapes.add_textbox(Inches(1.0), Inches(6.3), Inches(11.3), Inches(0.6))
    tf_nt = tb_nt.text_frame
    tf_nt.word_wrap = True
    p = tf_nt.paragraphs[0]
    p.text = "STATUTORY CORPUS: 40 curated sections across 6 Indian central Acts (Contract Act 1872, Specific Relief Act 1963, Arbitration Act 1996, IT Act 2000, Sale of Goods 1930, Companies Act 2013). CURRENTNESS AND APPLICABILITY REQUIRE INDEPENDENT VERIFICATION."
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = SLATE_DARK

    # ==========================================
    # SLIDE 6: Abstention Policy
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(s6, "ABSTENTION POLICY", "Five checks determine whether the system abstains",
               "Sequential hierarchical gates prioritizing document integrity and legal grounding over raw model confidence.")

    tiers = [
        ("01 Version Integrity", "Checks document-version consistency and suppresses findings on stale drafts via SHA-256 digests."),
        ("02 Partition & Provenance", "Ensures data isolation and strict prevention of cross-partition or unverified contract evaluation."),
        ("03 Statutory Grounding", "Evaluates whether retrieved statutory evidence suits the finding and is currently in force."),
        ("04 Confidence Threshold", "Checks the model prediction against empirical operating threshold tau* = 0.04."),
        ("05 Final Disposition", "Routes verified findings to lawyer review or withholds sub-threshold predictions as NO_ACTIONABLE_RISK.")
    ]

    tier_w = Inches(11.733)
    tier_h = Inches(0.7)
    for i, (t_title, t_desc) in enumerate(tiers):
        y = Inches(1.8) + i * Inches(0.82)
        add_card(s6, Inches(0.8), y, tier_w, tier_h)
        tb = s6.shapes.add_textbox(Inches(1.0), y + Inches(0.12), tier_w - Inches(0.4), tier_h - Inches(0.2))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = t_title
        p.font.name = "Calibri"
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = BLUE_ACCENT

        p_desc = tf.add_paragraph()
        p_desc.text = t_desc
        p_desc.font.name = "Calibri"
        p_desc.font.size = Pt(11)
        p_desc.font.color.rgb = MUTED

    # Bottom Core Principle Card
    add_card(s6, Inches(0.8), Inches(6.05), Inches(11.733), Inches(0.95), bg_color=CARD_BG, border_color=CYAN_ACCENT)
    tb_pr = s6.shapes.add_textbox(Inches(1.0), Inches(6.15), Inches(11.3), Inches(0.75))
    tf_pr = tb_pr.text_frame
    tf_pr.word_wrap = True
    p = tf_pr.paragraphs[0]
    p.text = "CORE LEGAL SAFETY PRINCIPLE:"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_ACCENT
    p.space_after = Pt(2)

    p2 = tf_pr.add_paragraph()
    p2.text = "In high-stakes legal work, a confident but unsupported finding can mislead a client. The system withholds rather than forces a speculative prediction."
    p2.font.name = "Calibri"
    p2.font.size = Pt(12)
    p2.font.bold = True
    p2.font.color.rgb = SLATE_DARK

    # ==========================================
    # SLIDE 7: Implemented Workflow
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header(s7, "IMPLEMENTED WORKFLOW", "The implemented workflow preserves evidence and auditability",
               "Full decoupled pipeline from raw file ingestion to advocate review workbench.")

    workflow_cards = [
        ("01 Upload", "Contract ingestion", "PDF / DOCX / TXT"),
        ("02 Extract", "Preprocess document", "Non-destructive normalization"),
        ("03 Segment", "Deterministic clauses", "Character-coordinate slices"),
        ("04 Analyse", "LegalBERT inference", "12,407-label sigmoid logits"),
        ("05 Retrieve", "Evidence & attribution", "Okapi BM25 + Gradient × Input"),
        ("06 Abstain", "Apply policy cascade", "5-tier fail-closed evaluation"),
        ("07 Review", "Lawyer workbench", "Human-in-the-loop sign-off"),
        ("08 Persist", "Audit & database", "Tamper-evident SHA-256 logs")
    ]

    card_w = Inches(2.75)
    card_h = Inches(1.8)
    for i, (step_num, step_name, step_detail) in enumerate(workflow_cards):
        row = i // 4
        col = i % 4
        x = Inches(0.8) + col * Inches(2.98)
        y = Inches(1.9) + row * Inches(2.05)
        add_card(s7, x, y, card_w, card_h)
        tb = s7.shapes.add_textbox(x + Inches(0.18), y + Inches(0.18), card_w - Inches(0.36), card_h - Inches(0.36))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = step_num
        p1.font.name = "Calibri"
        p1.font.size = Pt(13)
        p1.font.bold = True
        p1.font.color.rgb = BLUE_ACCENT
        p1.space_after = Pt(2)

        p2 = tf.add_paragraph()
        p2.text = step_name
        p2.font.name = "Calibri"
        p2.font.size = Pt(14)
        p2.font.bold = True
        p2.font.color.rgb = NAVY
        p2.space_after = Pt(4)

        p3 = tf.add_paragraph()
        p3.text = step_detail
        p3.font.name = "Calibri"
        p3.font.size = Pt(11)
        p3.font.color.rgb = MUTED

    # Bottom Stack Banner
    add_card(s7, Inches(0.8), Inches(6.2), Inches(11.733), Inches(0.8), bg_color=BAR_BG, border_color=None)
    tb_wf_b = s7.shapes.add_textbox(Inches(1.0), Inches(6.3), Inches(11.3), Inches(0.6))
    tf_wf_b = tb_wf_b.text_frame
    tf_wf_b.word_wrap = True
    p = tf_wf_b.paragraphs[0]
    p.text = "FLASK · PDF/DOCX/TXT INGESTION · NLP INFERENCE · STATUTORY RETRIEVAL · PERSISTENCE AND REVIEW WORKFLOW · SHA-256 INTEGRITY CHECKS · AUDIT MECHANISMS · PYTEST AUTOMATION"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = SLATE_DARK

    # ==========================================
    # SLIDE 8: Evaluation Design
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header(s8, "EVALUATION DESIGN", "LEDGAR and ContractNLI measure different behaviours",
               "Evaluating multi-label calibration against extreme class imbalance vs. traditional NLI baselines.")

    # Left: Metric Visual Bars for LEDGAR
    add_card(s8, Inches(0.8), Inches(1.8), Inches(5.7), Inches(4.3))
    tb_m = s8.shapes.add_textbox(Inches(1.0), Inches(1.95), Inches(5.3), Inches(4.0))
    tf_m = tb_m.text_frame
    tf_m.word_wrap = True
    p = tf_m.paragraphs[0]
    p.text = "LEDGAR (LegalBERT @ Operating Threshold 0.04)"
    p.font.name = "Calibri"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p.space_after = Pt(10)

    metrics_data = [
        ("Micro-Precision", "0.18", 0.18, CYAN_ACCENT),
        ("Micro-Recall", "0.12", 0.12, CYAN_ACCENT),
        ("Micro-F1", "0.14", 0.14, CYAN_ACCENT),
        ("Macro-F1", "0.00 (0.0045)", 0.02, MUTED),
        ("Weighted-F1", "0.09", 0.09, BLUE_ACCENT)
    ]
    for lbl, val_str, norm_val, col in metrics_data:
        p_lbl = tf_m.add_paragraph()
        p_lbl.text = f"{lbl}:  {val_str}"
        p_lbl.font.name = "Calibri"
        p_lbl.font.size = Pt(12)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = SLATE_DARK
        p_lbl.space_after = Pt(2)

    # Right: ContractNLI Baseline Card
    add_card(s8, Inches(6.8), Inches(1.8), Inches(5.7), Inches(4.3))
    tb_nli = s8.shapes.add_textbox(Inches(7.0), Inches(1.95), Inches(5.3), Inches(4.0))
    tf_nli = tb_nli.text_frame
    tf_nli.word_wrap = True
    p = tf_nli.paragraphs[0]
    p.text = "ContractNLI (TF-IDF + Linear SVM Baseline)"
    p.font.name = "Calibri"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p.space_after = Pt(10)

    nli_metrics = [
        ("Test Accuracy", "0.6557 (65.57%)"),
        ("Macro-F1", "0.5844"),
        ("Weighted-F1", "0.6385"),
        ("Feature Space", "118,497 unigrams & bigrams"),
        ("Held-Out Test Set", "2,091 instances across 123 NDAs")
    ]
    for lbl, val_str in nli_metrics:
        p_item = tf_nli.add_paragraph()
        p_item.text = f"{lbl}:  {val_str}"
        p_item.font.name = "Calibri"
        p_item.font.size = Pt(12)
        p_item.font.bold = True
        p_item.font.color.rgb = SLATE_DARK
        p_item.space_after = Pt(4)

    # Bottom Callout
    add_card(s8, Inches(0.8), Inches(6.2), Inches(11.733), Inches(0.95))
    tb_ev_c = s8.shapes.add_textbox(Inches(1.0), Inches(6.25), Inches(11.3), Inches(0.85))
    tf_ev_c = tb_ev_c.text_frame
    tf_ev_c.word_wrap = True
    p = tf_ev_c.paragraphs[0]
    p.text = "CRITICAL FORENSIC INSIGHT:"
    p.font.name = "Calibri"
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_after = Pt(2)

    p2 = tf_ev_c.add_paragraph()
    p2.text = "LEDGAR has severe long-tail label imbalance. Micro metrics pool every label decision, so frequent labels dominate; Macro-F1 weights each label equally and exposes weak rare-label performance (0.0045). ContractNLI is a separate document-level NLI task and is not directly comparable."
    p2.font.name = "Calibri"
    p2.font.size = Pt(11)
    p2.font.color.rgb = MUTED

    # ==========================================
    # SLIDE 9: 30-Seed Synthetic Evaluation
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header(s9, "30-SEED SYNTHETIC EVALUATION – MATCHED-COVERAGE ANALYSIS",
               "Abstention reduced unsupported findings across matched synthetic seeds",
               "Across 28 matched seeds, the full evidence-aware policy lowered the unsupported-finding rate relative to confidence-only screening. These are synthetic results.")

    stat_grid = [
        ("28", "MATCHED SEEDS", "Seeds with exact coverage match (|ΔUFC| <= 0.02)"),
        ("23.24 PP", "MEAN REDUCTION (0.2324)", "Average decrease in unsupported findings"),
        ("19.05–27.44 PP", "95% CONFIDENCE INTERVAL", "Statistically robust reduction across seeds"),
        ("7.45 × 10⁻⁹", "WILCOXON P-VALUE", "Highly significant difference (p < 0.001)")
    ]

    card_w9 = Inches(2.75)
    card_h9 = Inches(2.3)
    for i, (val, lbl, note) in enumerate(stat_grid):
        x = Inches(0.8) + i * Inches(2.98)
        y = Inches(2.1)
        add_card(s9, x, y, card_w9, card_h9)
        tb = s9.shapes.add_textbox(x + Inches(0.18), y + Inches(0.2), card_w9 - Inches(0.36), card_h9 - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        p_v = tf.paragraphs[0]
        p_v.text = val
        p_v.font.name = "Calibri"
        p_v.font.size = Pt(24)
        p_v.font.bold = True
        p_v.font.color.rgb = CYAN_ACCENT
        p_v.space_after = Pt(4)

        p_l = tf.add_paragraph()
        p_l.text = lbl
        p_l.font.name = "Calibri"
        p_l.font.size = Pt(11)
        p_l.font.bold = True
        p_l.font.color.rgb = NAVY
        p_l.space_after = Pt(4)

        p_n = tf.add_paragraph()
        p_n.text = note
        p_n.font.name = "Calibri"
        p_n.font.size = Pt(10)
        p_n.font.color.rgb = MUTED

    # Bottom Explanatory Banner
    add_card(s9, Inches(0.8), Inches(4.7), Inches(11.733), Inches(1.3))
    tb_s9_b = s9.shapes.add_textbox(Inches(1.0), Inches(4.85), Inches(11.3), Inches(1.0))
    tf_s9_b = tb_s9_b.text_frame
    tf_s9_b.word_wrap = True
    p = tf_s9_b.paragraphs[0]
    p.text = "METHODOLOGICAL RIGOR & GOVERNANCE NOTES:"
    p.font.name = "Calibri"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_after = Pt(2)

    p2 = tf_s9_b.add_paragraph()
    p2.text = "PP = PERCENTAGE POINTS. 28 SEEDS WERE INCLUDED, RATHER THAN 30, BECAUSE OF DISCRETE CANDIDATE-COUNT CONSTRAINTS. VERSION-AWARE, STATUTORY-GROUNDING, AND RULE-BASED BASELINES ARE PRESERVED IN AUDIT LEDGERS. FORCED THRESHOLD INTERPOLATION ACROSS DISCONTINUOUS POINTS IS STRICTLY PROHIBITED PER RDR-002."
    p2.font.name = "Calibri"
    p2.font.size = Pt(10)
    p2.font.color.rgb = MUTED

    # ==========================================
    # SLIDE 10: Limitations, Safeguards & Conclusion
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header(s10, "LIMITATIONS, SAFEGUARDS & CONCLUSION", "Trustworthy contract AI must know when to abstain",
               "Balancing empirical capabilities with strict academic integrity and responsible AI safeguards.")

    # Left: Limitations Card
    add_card(s10, Inches(0.8), Inches(1.8), Inches(5.7), Inches(3.3))
    tb_lim = s10.shapes.add_textbox(Inches(1.0), Inches(1.95), Inches(5.3), Inches(3.0))
    tf_lim = tb_lim.text_frame
    tf_lim.word_wrap = True
    p = tf_lim.paragraphs[0]
    p.text = "LIMITATIONS"
    p.font.name = "Calibri"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = RED_WITHHOLD
    p.space_after = Pt(6)

    lims = [
        "No validated real Indian commercial contract test set",
        "Severe long-tail label imbalance (91.1% rare classes)",
        "Curated statutory collection limited to 40 sections",
        "Attribution does not establish causal legal faithfulness",
        "Synthetic evaluation does not establish real-world legal performance",
        "Mandatory advocate review remains essential"
    ]
    for lim in lims:
        p_l = tf_lim.add_paragraph()
        p_l.text = f"• {lim}"
        p_l.font.name = "Calibri"
        p_l.font.size = Pt(11)
        p_l.font.color.rgb = SLATE_DARK
        p_l.space_after = Pt(2)

    # Right: Safeguards & Future Work Card
    add_card(s10, Inches(6.8), Inches(1.8), Inches(5.7), Inches(3.3))
    tb_saf = s10.shapes.add_textbox(Inches(7.0), Inches(1.95), Inches(5.3), Inches(3.0))
    tf_saf = tb_saf.text_frame
    tf_saf.word_wrap = True
    p = tf_saf.paragraphs[0]
    p.text = "SAFEGUARDS & FUTURE WORK"
    p.font.name = "Calibri"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = GREEN_ACCEPT
    p.space_after = Pt(6)

    safs = [
        "Decision-support prototype only; zero autonomous legal advice",
        "Uncertain or sub-threshold findings are strictly withheld",
        "Client Disclosure Isolation: is_disclosed_to_client = False",
        "Demonstrated: LegalBERT, BM25, Gradient × Input, 5-Tier Abstention",
        "Future Work: Authorised lawyer-annotated contracts & LoRA fine-tuning",
        "Future Work: Expanded judicial precedent coverage & active learning"
    ]
    for saf in safs:
        p_s = tf_saf.add_paragraph()
        p_s.text = f"• {saf}"
        p_s.font.name = "Calibri"
        p_s.font.size = Pt(11)
        p_s.font.color.rgb = SLATE_DARK
        p_s.space_after = Pt(2)

    # Bottom Quote & Thank You Banner
    add_card(s10, Inches(0.8), Inches(5.25), Inches(11.733), Inches(1.8), bg_color=CARD_BG, border_color=CYAN_ACCENT)
    tb_end = s10.shapes.add_textbox(Inches(1.0), Inches(5.35), Inches(11.3), Inches(1.6))
    tf_end = tb_end.text_frame
    tf_end.word_wrap = True
    p = tf_end.paragraphs[0]
    p.text = "“Trustworthy AI in high-stakes domains requires traceable evidence, transparent limitations and the ability to abstain when sufficient support is unavailable.”"
    p.font.name = "Calibri"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p.alignment = PP_ALIGN.CENTER
    p.space_after = Pt(8)

    p_ty = tf_end.add_paragraph()
    p_ty.text = "THANK YOU"
    p_ty.font.name = "Calibri"
    p_ty.font.size = Pt(20)
    p_ty.font.bold = True
    p_ty.font.color.rgb = BLUE_ACCENT
    p_ty.alignment = PP_ALIGN.CENTER
    p_ty.space_after = Pt(2)

    p_names = tf_end.add_paragraph()
    p_names.text = "SRI LATHIKA .V.S  |  OVIYA .B  |  NANDANA .V"
    p_names.font.name = "Calibri"
    p_names.font.size = Pt(12)
    p_names.font.bold = True
    p_names.font.color.rgb = SLATE_DARK
    p_names.alignment = PP_ALIGN.CENTER

    prs.save(output_path)
    print(f"Successfully generated presentation at {output_path}")

if __name__ == "__main__":
    create_deck("CONTRACTRISK_XAI_Final_Presentation.pptx")
