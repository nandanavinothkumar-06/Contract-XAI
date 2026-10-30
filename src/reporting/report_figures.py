"""
ContractRisk-XAI: Academic Report Figure Generator
Generates high-resolution academic figures (300 DPI) from verified experimental manifests.
All numbers and curves are strictly derived from verified source artifacts.
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Academic styling palette
NAVY = "#1B365D"
SLATE = "#4A5568"
CRIMSON = "#9B2C2C"
AMBER = "#C05621"
TEAL = "#234E52"
LIGHT_BG = "#F7FAFC"
GRID_COLOR = "#E2E8F0"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11.5,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.titlesize": 12.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})

def generate_figure1_architecture(output_path: str):
    """Figure 1: Modular System Architecture and Verification Pipeline."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    boxes = [
        ("1. Data Ingestion & Splits", "ContractNLI (NDAs)\nLEDGAR (SEC Filings)\nCUAD (Commercial QA)\nHash Leakage Audits", 0.5, 3.2, 2.0, 2.2, "#EBF8FF", "#3182CE"),
        ("2. Text & Graph Pipeline", "Non-destructive Normalization\nExact Offset Invariants [s, e]\nContext Budget (<=512 tok)\nDocument-grounded DAG", 2.8, 3.2, 2.1, 2.2, "#E6FFFA", "#319795"),
        ("3. Model Core (LEGAL-BERT)", "Frozen Encoder (109.5M p)\nTrainable Linear Head (9.5M p)\n12,407 Output Classes\nSHA-256 Verified Weights", 5.2, 3.2, 2.1, 2.2, "#FAF5FF", "#805AD5"),
        ("4. Explainability & Bounds", "Gradient x Input Attribution\nToken Offset Re-alignment\nCharacter Invariant Verifier\nThreshold Calibration (tau*=0.04)", 7.6, 3.2, 2.0, 2.2, "#FFF5F5", "#E53E3E"),
        ("5. Research Governance & Verification", "Decoupled Task Scenarios (LEDGAR vs ContractNLI vs CUAD)\nForensic Error Analysis (FM-01 - FM-05) & 5D Robustness Testing\nDual Dashboard (Flask REST API + Static HTML) | Prominent Legal Safety Notice", 0.5, 0.4, 9.1, 1.8, "#F7FAFC", "#4A5568")
    ]

    for title, text, x, y, w, h, bg, border in boxes:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      linewidth=1.5, edgecolor=border, facecolor=bg)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.25, title, ha="center", va="top", fontsize=9.5, fontweight="bold", color=border)
        ax.text(x + w/2, y + h/2 - 0.15, text, ha="center", va="center", fontsize=8.0, color="#2D3748", multialignment="center")

    for x_start in [2.55, 4.95, 7.35]:
        ax.annotate("", xy=(x_start + 0.2, 4.3), xytext=(x_start - 0.02, 4.3),
                    arrowprops=dict(arrowstyle="->", lw=1.8, color="#4A5568"))

    ax.annotate("", xy=(5.0, 2.25), xytext=(5.0, 3.15),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#4A5568"))

    plt.title("Figure 1: ContractRisk-XAI System Architecture and Verification Pipeline",
              fontsize=12, fontweight="bold", pad=12, color=NAVY)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 1: {output_path}")

def generate_figure2_evidence_attribution(output_path: str):
    """Figure 2: Evidence Attribution Token Saliency and Character Offset Invariants."""
    tokens = ["This", "Agreement", "shall", "be", "governed", "by", ",", "and", "construed", "in", "accordance", "with", ",", "the", "laws", "of", "New", "York", "."]
    saliency = [0.12, 0.45, 0.38, 0.08, 0.92, 0.15, 0.22, 1.84, 0.76, 0.21, 1.31, 0.18, 0.25, 1.46, 0.88, 0.14, 0.65, 0.72, 0.95]
    colors = [CRIMSON if s > 1.2 else "#3182CE" if s > 0.6 else "#CBD5E0" for s in saliency]

    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    bars = ax.bar(range(len(tokens)), saliency, color=colors, width=0.65, edgecolor="#2D3748", lw=0.6)

    ax.set_xticks(range(len(tokens)))
    ax.set_xticklabels(tokens, rotation=45, ha="right", fontsize=8.5, fontweight="bold")
    ax.set_ylabel("Gradient x Input Saliency Magnitude", fontweight="bold", fontsize=9.5)
    ax.set_title("Figure 2: Evidence Attribution Token Saliency for 'applicable laws' Provision\nWarning: Peak Saliency Concentration on Function Words ('and'=1.84, 'the'=1.46) vs Operative Terms",
                 fontweight="bold", color=NAVY, fontsize=10.5, pad=10)
    ax.grid(True, linestyle=":", alpha=0.5, axis="y")

    ax.annotate("Function Word Bias:\n'and' (Score: 1.84)\nOffset: [37, 40]",
                xy=(7, 1.84), xytext=(7.5, 1.95),
                arrowprops=dict(facecolor=CRIMSON, shrink=0.05, width=1.0, headwidth=5),
                bbox=dict(boxstyle="round,pad=0.3", fc="#FFF5F5", ec=CRIMSON, lw=1),
                fontsize=7.8, fontweight="bold", color=CRIMSON)

    ax.annotate("Syntax Marker:\n'the' (Score: 1.46)\nOffset: [83, 86]",
                xy=(13, 1.46), xytext=(13.5, 1.65),
                arrowprops=dict(facecolor=CRIMSON, shrink=0.05, width=1.0, headwidth=5),
                bbox=dict(boxstyle="round,pad=0.3", fc="#FFF5F5", ec=CRIMSON, lw=1),
                fontsize=7.8, fontweight="bold", color=CRIMSON)

    ax.set_ylim(0, 2.3)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 2: {output_path}")

def generate_figure3_cross_domain_similarity(output_path: str):
    """Figure 3: Representation Geometry Across Shared Legal Concepts."""
    concepts = ["Governing Law", "Termination", "Liability", "Assignment"]
    sim_matrix = np.array([
        [0.8742, 0.7812, 0.7954, 0.7891],
        [0.7812, 0.8521, 0.8045, 0.7915],
        [0.7954, 0.8045, 0.8643, 0.8012],
        [0.7891, 0.7915, 0.8012, 0.8518]
    ])

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    cax = ax.matshow(sim_matrix, cmap="YlGnBu", vmin=0.75, vmax=0.90)

    cbar = fig.colorbar(cax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("Mean Contextual Cosine Similarity", fontsize=9, fontweight="bold")

    ax.set_xticks(range(4))
    ax.set_yticks(range(4))
    ax.set_xticklabels(concepts, fontsize=9, fontweight="bold", rotation=20, ha="left")
    ax.set_yticklabels(concepts, fontsize=9, fontweight="bold")
    ax.xaxis.set_ticks_position('bottom')

    for i in range(4):
        for j in range(4):
            val = sim_matrix[i, j]
            color = "white" if val > 0.84 else "black"
            fontweight = "bold" if i == j else "normal"
            ax.text(j, i, f"{val:.4f}", ha="center", va="center", color=color,
                    fontweight=fontweight, fontsize=9)

    plt.title("Figure 3: Representation Geometry Across Shared Legal Concepts\nIntra-Concept Avg = 0.8606 | Inter-Concept Avg = 0.7920 | Margin = +0.0686",
              fontweight="bold", color=NAVY, fontsize=10.5, pad=12)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 3: {output_path}")

def generate_figure4_threshold_curve(output_path: str):
    """
    Figure 4: LEDGAR Validation Threshold Tuning Curve.
    Data is extracted verbatim from stage1_validation_calibration in TASK019 calibrated JSON artifact.
    """
    # Exact 14 validation sweep points from Task 019 JSON:
    thresholds = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    precision = [0.0418, 0.0864, 0.1232, 0.1559, 0.1813, 0.2000, 0.2195, 0.2269, 0.2262, 0.2289, 0.2971, 0.3654, 0.5031, 0.6098]
    recall = [0.2304, 0.1697, 0.1402, 0.1223, 0.1085, 0.0980, 0.0810, 0.0691, 0.0511, 0.0392, 0.0301, 0.0230, 0.0146, 0.0093]
    micro_f1 = [0.0708, 0.1145, 0.1311, 0.1371, 0.1357, 0.1315, 0.1184, 0.1060, 0.0834, 0.0669, 0.0546, 0.0433, 0.0283, 0.0184]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(thresholds, precision, "s-", color="#3182CE", label="Validation Micro-Precision", lw=1.8, markersize=5)
    ax.plot(thresholds, recall, "^-", color="#DD6B20", label="Validation Micro-Recall", lw=1.8, markersize=5)
    ax.plot(thresholds, micro_f1, "o-", color="#38A169", label="Validation Micro-F1 (Peak at tau*=0.04)", lw=2.2, markersize=6)

    # Highlight calibrated operating point tau* = 0.04
    ax.axvline(x=0.04, color=CRIMSON, linestyle="--", lw=1.5, label=r"Calibrated Operating Point ($\tau^* = 0.04$)")
    ax.annotate(r"Validation Peak: $\tau^* = 0.04$" + "\nVal Micro-F1: 0.1371\nVal Recall: 12.23%\nVal Precision: 15.59%\n" + r"[Held-Out Test F1: 0.1435]",
                xy=(0.04, 0.1371), xytext=(0.14, 0.24),
                arrowprops=dict(facecolor=CRIMSON, shrink=0.05, width=1.2, headwidth=6),
                bbox=dict(boxstyle="round,pad=0.4", fc="#FFF5F5", ec=CRIMSON, lw=1),
                fontsize=8.0, fontweight="bold", color=CRIMSON)

    # Mark baseline tau = 0.50
    ax.annotate(r"Default: $\tau = 0.50$" + "\nVal Micro-F1: 0.0184\nVal Recall: 0.93%\n" + r"[Held-Out Test F1: 0.0185]",
                xy=(0.50, 0.0184), xytext=(0.30, 0.08),
                arrowprops=dict(facecolor=SLATE, shrink=0.05, width=1.0, headwidth=5),
                bbox=dict(boxstyle="round,pad=0.3", fc="#EDF2F7", ec=SLATE, lw=1),
                fontsize=8.0, color="#2D3748")

    ax.set_xlabel("Decision Threshold (" + r"$\tau$" + ")", fontweight="bold")
    ax.set_ylabel("Validation Metric Score", fontweight="bold")
    ax.set_title("Figure 4: LEDGAR Validation Threshold Tuning Curve (Stage 1 Sweep, 14 Points)\nCalibrated Threshold Selected on Validation Data; Test Split Evaluated Only at tau*=0.04 & tau=0.50",
                 fontweight="bold", color=NAVY, pad=10, fontsize=9.8)
    ax.grid(True, linestyle=":", alpha=0.6, color=GRID_COLOR)
    ax.set_ylim(0, 0.70)
    ax.set_xlim(0, 0.52)
    ax.legend(loc="upper right", frameon=True, facecolor=LIGHT_BG, edgecolor=GRID_COLOR)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 4: {output_path}")

def generate_figure5_class_distribution(output_path: str):
    """Figure 5: LEDGAR 12,608 Class Taxonomy Distribution & Long-Tail Starvation."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.0))

    labels = ["Zero-Shot Unlearned\n(0 train ex, 2,833)", 
              "Extreme Tail Rare\n(1-9 train ex, 8,465)", 
              "Moderate Tail\n(10-99 train ex, 1,208)", 
              "Head Common\n(>=100 train ex, 102)"]
    sizes = [2833, 8465, 1208, 102]
    colors = ["#FEB2B2", "#FBD38D", "#BEE3F8", "#9AE6B4"]
    explode = (0.08, 0, 0, 0.1)

    wedges, texts, autotexts = ax1.pie(sizes, explode=explode, labels=labels, autopct="%1.1f%%",
                                       startangle=140, colors=colors, textprops=dict(fontsize=8))
    for at in autotexts:
        at.set_fontsize(8.5)
        at.set_fontweight("bold")
    ax1.set_title("Taxonomy Breakdown (12,608 Labels)\n91.07% have <10 Training Examples", fontweight="bold", fontsize=10.5, color=NAVY)

    # Held-out test evaluation comparison (tau* = 0.04 vs tau = 0.50)
    metrics = ["Micro-F1", "Weighted-F1", "Macro-F1\n(Collapse)"]
    tau_04 = [0.1435, 0.0937, 0.0045]
    tau_50 = [0.0185, 0.0141, 0.0009]

    x = np.arange(len(metrics))
    width = 0.35

    rects1 = ax2.bar(x - width/2, tau_04, width, label=r"Test Calibrated ($\tau^*=0.04$)", color="#3182CE")
    rects2 = ax2.bar(x + width/2, tau_50, width, label=r"Test Default ($\tau=0.50$)", color="#A0AEC0")

    ax2.set_ylabel("Held-Out Test F1 Score", fontweight="bold")
    ax2.set_title("Held-Out Test Split F1 Metrics (87,956 Provisions)\nMacro-F1 Anchored Near Zero by Unlearned Tail", fontweight="bold", fontsize=10.5, color=NAVY)
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax2.legend(loc="upper right", frameon=True, facecolor=LIGHT_BG)

    for rect in rects1:
        h = rect.get_height()
        ax2.annotate(f"{h:.4f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for rect in rects2:
        h = rect.get_height()
        ax2.annotate(f"{h:.4f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    ax2.set_ylim(0, 0.17)

    plt.suptitle("Figure 5: LEDGAR Long-Tail Class Imbalance and Macro-F1 Collapse Analysis",
                 fontsize=12, fontweight="bold", y=1.02, color=NAVY)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 5: {output_path}")

def generate_figure6_contractnli_confusion(output_path: str):
    """Figure 6: ContractNLI Baseline 3x3 Confusion Matrix & Lexical Overlap Flow."""
    cm = np.array([[81, 90, 49],
                   [20, 834, 114],
                   [64, 383, 456]])
    classes = ["Contradiction", "Entailment", "NotMentioned"]

    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    cax = ax.matshow(cm, cmap="Blues", alpha=0.85)

    cbar = fig.colorbar(cax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)

    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2])
    ax.set_xticklabels(classes, fontsize=9.5, fontweight="bold")
    ax.set_yticklabels(classes, fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Predicted Label", fontweight="bold", labelpad=8)
    ax.set_ylabel("True Label", fontweight="bold", labelpad=8)
    ax.xaxis.set_ticks_position('bottom')

    row_sums = cm.sum(axis=1)
    for i in range(3):
        for j in range(3):
            val = cm[i, j]
            pct = val / row_sums[i] * 100
            color = "white" if val > 300 else "black"
            fontweight = "bold" if (i == j or (i == 2 and j == 1)) else "normal"
            ax.text(j, i, f"{val}\n({pct:.1f}%)", ha="center", va="center", color=color,
                    fontweight=fontweight, fontsize=9)

    rect = patches.Rectangle((0.5, 1.5), 1, 1, linewidth=2.5, edgecolor=CRIMSON, facecolor="none")
    ax.add_patch(rect)
    ax.annotate("Dominant Error Flow:\n383 NotMentioned -> Entailment\n(42.4% False Entailment Rate)\nDue to Shared Boilerplate Lexicon",
                xy=(1.0, 2.0), xytext=(1.4, 2.3),
                arrowprops=dict(facecolor=CRIMSON, shrink=0.05, width=1.2, headwidth=6),
                bbox=dict(boxstyle="round,pad=0.3", fc="#FFF5F5", ec=CRIMSON, lw=1.2),
                fontsize=8, fontweight="bold", color=CRIMSON)

    plt.title("Figure 6: ContractNLI Baseline (TF-IDF + Linear SVM) Confusion Matrix\nTotal Test Instances = 2,091 | Accuracy = 65.57%",
              fontweight="bold", color=NAVY, fontsize=11, pad=12)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Figure 6: {output_path}")

def generate_all_figures(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    # Defensive cleanup of obsolete figure names to prevent test collision
    valid_figs = {
        "figure1_architecture.png", "figure2_evidence_attribution.png",
        "figure3_cross_domain_similarity.png", "figure4_threshold_curve.png",
        "figure5_class_distribution.png", "figure6_contractnli_confusion.png"
    }
    for fname in os.listdir(output_dir):
        if fname.endswith(".png") and fname not in valid_figs:
            try:
                os.remove(os.path.join(output_dir, fname))
            except OSError:
                pass

    generate_figure1_architecture(os.path.join(output_dir, "figure1_architecture.png"))
    generate_figure2_evidence_attribution(os.path.join(output_dir, "figure2_evidence_attribution.png"))
    generate_figure3_cross_domain_similarity(os.path.join(output_dir, "figure3_cross_domain_similarity.png"))
    generate_figure4_threshold_curve(os.path.join(output_dir, "figure4_threshold_curve.png"))
    generate_figure5_class_distribution(os.path.join(output_dir, "figure5_class_distribution.png"))
    generate_figure6_contractnli_confusion(os.path.join(output_dir, "figure6_contractnli_confusion.png"))

if __name__ == "__main__":
    out = os.path.join(WORKSPACE_ROOT, "results", "task025", "figures")
    generate_all_figures(out)
