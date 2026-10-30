"""
analyse_uvvis.py

Author: Aritra Roy
Email: contact@aritraroy.live
Website: https://aritraroy.live
GitHub: aritraroy24

Analyses the 96-well Co-Ni-Cu BDC UV-Vis screen and writes per-well metrics, tidy spectra and figures to analysis/output.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy.optimize import nnls
from scipy.signal import savgol_filter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "uvvis_raw_tecan.xlsx"
DESIGN = ROOT / "plate_design_96wells.csv"
OUT = ROOT / "analysis" / "output"

METALS = ["Co", "Ni", "Cu"]
SG_WINDOW, SG_POLY = 9, 3
D2_SCALE = 1e4
D2_RANGE = (420, 800)
SCATTER_RANGE = (860, 900)
BANDS = {"420": (420, 435), "460": (445, 475), "590": (570, 610), "700": (660, 750)}
PNR_THRESHOLD = 3.0

SURFACE, INK, INK_2, MUTED, GRID = "#ffffff", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
FAMILY_COLOURS = {"Co-Ni": "#2a78d6", "Co-Cu": "#eb6834", "Ni-Cu": "#1baf7a", "Co-Ni-Cu": "#a3a29c"}
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
CRITICAL = "#d03b3b"

plt.rcParams.update({
    "font.family": "Arial", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK_2, "xtick.color": INK_2,
    "ytick.color": INK_2, "axes.titlecolor": INK, "axes.titlesize": 11, "axes.titleweight": "bold", "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def load_spectra(path):
    """Read the Tecan absorbance scans from every sheet of the plate-reader export.

    Args:
        path (Path, required): Tecan i-control Excel export, one sheet per measured plate.

    Returns:
        pd.DataFrame: Absorbance with sample IDs (A1-H12) as rows and wavelengths (nm) as columns.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    spectra, wavelengths = {}, None
    for ws in wb:
        rows = list(ws.iter_rows(values_only=True))
        header = next(r for r in rows if r[0] == "Wavel.")
        wavelengths = [float(v) for v in header[1:] if v is not None]
        for r in rows:
            if isinstance(r[0], str) and r[0][:1] in "ABCDEFGH" and r[0][1:].isdigit():
                spectra[r[0]] = [float(v) for v in r[1:len(wavelengths) + 1]]
    return pd.DataFrame(spectra, index=wavelengths).T


def load_design(path):
    """Read the plate design and add mole fractions, metal family and a composition label.

    Args:
        path (Path, required): plate_design_96wells.csv written by generate_plate.py.

    Returns:
        pd.DataFrame: One row per sample ID with ratios, mole fractions (x_Co, x_Ni, x_Cu), Family and Comp.
    """
    d = pd.read_csv(path).set_index("Well")
    total = d[[f"{m}_Ratio" for m in METALS]].sum(axis=1)
    for m in METALS:
        d[f"x_{m}"] = d[f"{m}_Ratio"] / total
    d["Family"] = d.apply(lambda r: "-".join(m for m in METALS if r[f"{m}_Ratio"] > 0), axis=1)
    d["Comp"] = d.Co_Ratio.astype(str) + ":" + d.Ni_Ratio.astype(str) + ":" + d.Cu_Ratio.astype(str)
    return d


def second_derivative(spectra):
    """Savitzky-Golay second derivative, sign-flipped so absorption bands are positive and smooth scattering is suppressed.

    Args:
        spectra (pd.DataFrame, required): Absorbance, samples x wavelengths at 5 nm spacing.

    Returns:
        pd.DataFrame: -d2A/dlambda2 in 1e-4 AU nm^-2, same shape as the input.
    """
    step = np.diff(spectra.columns.values).mean()
    d2 = -savgol_filter(spectra.values, SG_WINDOW, SG_POLY, deriv=2, delta=step, axis=1) * D2_SCALE
    return pd.DataFrame(d2, index=spectra.index, columns=spectra.columns)


def band_metrics(d2):
    """Strength of each band as the mean second-derivative signal inside its window (robust to single-point noise), plus the peak position.

    Args:
        d2 (pd.DataFrame, required): Output of second_derivative.

    Returns:
        pd.DataFrame: Columns B<band> (mean signal, 1e-4 AU nm^-2) and B<band>_nm (position) for every band in BANDS.
    """
    wl = d2.columns.values
    out = {}
    for name, (lo, hi) in BANDS.items():
        sub = d2.loc[:, (wl >= lo) & (wl <= hi)]
        out[f"B{name}"] = sub.mean(axis=1)
        out[f"B{name}_nm"] = sub.idxmax(axis=1)
    return pd.DataFrame(out)


def binary_span_residuals(d2, design):
    """Rebuild every spectrum from the best non-negative combination of the binary spectra at the same metal:ligand ratio.

    A ternary feature that no mixture of binary spectra can reproduce is left in the residual. Each binary well is rebuilt from the other eight binaries, which gives the null distribution for wells that cannot contain a three-metal feature.

    Args:
        d2 (pd.DataFrame, required): Second-derivative spectra restricted to the analysis range.
        design (pd.DataFrame, required): Output of load_design, indexed like d2.

    Returns:
        pd.DataFrame: Observed minus reconstructed, same shape as d2.
    """
    resid = pd.DataFrame(index=d2.index, columns=d2.columns, dtype=float)
    offset = np.ones((d2.shape[1], 1))
    for _, grp in design.groupby("Ligand_Ratio"):
        binaries = grp.index[grp.Composition_Type == "Binary"]
        for w in grp.index:
            basis = d2.loc[[b for b in binaries if b != w]].values.T
            a = np.hstack([basis, offset, -offset])
            coef, _ = nnls(a, d2.loc[w].values)
            resid.loc[w] = d2.loc[w].values - a @ coef
    return resid


def replicate_noise(d2, design):
    """Pooled standard deviation of the 1:1:1 triplicates at every wavelength (one triplicate per metal:ligand ratio).

    Args:
        d2 (pd.DataFrame, required): Second-derivative spectra.
        design (pd.DataFrame, required): Output of load_design.

    Returns:
        pd.Series: Pooled replicate SD per wavelength, in the units of d2.
    """
    reps = design.index[design.Comp == "1:1:1"]
    groups = design.loc[reps, "Ligand_Ratio"]
    var = d2.loc[reps].groupby(groups).var(ddof=1)
    return np.sqrt(var.mean())


def to_xy(x_co, x_ni, x_cu):
    """Barycentric to Cartesian coordinates with Co bottom-left, Ni bottom-right and Cu at the top.

    Args:
        x_co (array-like, required): Co mole fraction.
        x_ni (array-like, required): Ni mole fraction.
        x_cu (array-like, required): Cu mole fraction.

    Returns:
        tuple: (x, y) arrays for plotting.
    """
    return np.asarray(x_ni) + 0.5 * np.asarray(x_cu), np.sqrt(3) / 2 * np.asarray(x_cu)


def ternary_axes(ax, title):
    """Draw an empty composition triangle with corner labels.

    Args:
        ax (matplotlib.axes.Axes, required): Target axes.
        title (str, required): Panel title.
    """
    ax.plot([0, 1, 0.5, 0], [0, 0, np.sqrt(3) / 2, 0], color=MUTED, lw=1)
    for f in (1 / 3, 2 / 3):
        for a, b in [((f, 1 - f, 0), (f, 0, 1 - f)), ((0, f, 1 - f), (1 - f, f, 0)), ((1 - f, 0, f), (0, 1 - f, f))]:
            xa, ya = to_xy(*a)
            xb, yb = to_xy(*b)
            ax.plot([xa, xb], [ya, yb], color=GRID, lw=0.6, zorder=0)
    ax.text(-0.04, -0.05, "Co", ha="right", va="top", fontweight="bold", color=INK)
    ax.text(1.04, -0.05, "Ni", ha="left", va="top", fontweight="bold", color=INK)
    ax.text(0.5, np.sqrt(3) / 2 + 0.05, "Cu", ha="center", va="bottom", fontweight="bold", color=INK)
    ax.set_title(title, pad=12)
    ax.set_xlim(-0.12, 1.12)
    ax.set_ylim(-0.12, 1.0)
    ax.set_aspect("equal")
    ax.axis("off")


def ternary_panel_grid(metrics, design, columns, row_labels, cbar_labels, path, vmin_zero=True):
    """Small multiples of composition triangles: one row per metric, one column per metal:ligand ratio, shared colour scale per row.

    Args:
        metrics (pd.DataFrame, required): Per-well values.
        design (pd.DataFrame, required): Output of load_design.
        columns (list[str], required): Metric columns, one per row of panels.
        row_labels (list[str], required): Row titles.
        cbar_labels (list[str], required): Colour-bar labels.
        path (Path, required): Output PNG path.
        vmin_zero (bool, optional): Anchor every colour scale at zero. Defaults to True.
    """
    ratios = sorted(design.Ligand_Ratio.unique())
    fig = plt.figure(figsize=(3.1 * len(ratios), 3.2 * len(columns)))
    rows = np.atleast_1d(fig.subfigures(len(columns), 1))
    for row, col, label, clab in zip(rows, columns, row_labels, cbar_labels):
        merged = design.join(metrics[[col]]).groupby(["Ligand_Ratio", "Comp"]).agg(
            v=(col, "mean"), x_Co=("x_Co", "first"), x_Ni=("x_Ni", "first"), x_Cu=("x_Cu", "first")).reset_index()
        vmax = merged.v.max()
        vmin = 0 if vmin_zero else merged.v.min()
        axes = row.subplots(1, len(ratios))
        row.subplots_adjust(top=0.80, bottom=0.03, left=0.02, right=0.98, wspace=0.3)
        for ax, L in zip(axes, ratios):
            ternary_axes(ax, f"M:L 1:{L}")
            sub = merged[merged.Ligand_Ratio == L]
            x, y = to_xy(sub.x_Co, sub.x_Ni, sub.x_Cu)
            sc = ax.scatter(x, y, c=sub.v, cmap=SEQ, vmin=vmin, vmax=vmax, s=70, edgecolors=SURFACE, linewidths=1.2, zorder=3)
        cb = row.colorbar(sc, ax=axes.tolist(), shrink=0.8, pad=0.02)
        cb.set_label(clab, color=INK_2)
        cb.outline.set_visible(False)
        centre = (axes[0].get_position().x0 + axes[-1].get_position().x1) / 2
        row.suptitle(label, x=centre, y=0.97, fontweight="bold", fontsize=12, color=INK)
    fig.savefig(path)
    plt.close(fig)


def plot_design(design, path):
    """The 21 distinct Co:Ni:Cu compositions on the composition triangle, coloured by metal pair, as run at every metal:ligand ratio.

    Args:
        design (pd.DataFrame, required): Output of load_design.
        path (Path, required): Output PNG path.
    """
    comps = design[design.Ligand_Ratio == 1].drop_duplicates("Comp")
    fig, ax = plt.subplots(figsize=(4.6, 4.3))
    ternary_axes(ax, "")
    for fam, colour in FAMILY_COLOURS.items():
        sub = comps[comps.Family == fam]
        x, y = to_xy(sub.x_Co, sub.x_Ni, sub.x_Cu)
        ax.scatter(x, y, s=95, color=colour, edgecolors=SURFACE, linewidths=1.5, zorder=3,
                   label=f"{fam} ({len(design[(design.Ligand_Ratio == 1) & (design.Family == fam)])} wells)")
    x, y = to_xy(1 / 3, 1 / 3, 1 / 3)
    ax.annotate("1:1:1 in triplicate", (x, y), xytext=(x + 0.2, y + 0.33), fontsize=9, color=INK_2,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.legend(loc="upper left", bbox_to_anchor=(-0.08, 1.02), fontsize=8.5, handletextpad=0.3)
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_spectra(spectra, design, path):
    """Raw spectra in one panel per metal:ligand ratio, coloured by which metals the well contains.

    Args:
        spectra (pd.DataFrame, required): Absorbance spectra.
        design (pd.DataFrame, required): Output of load_design.
        path (Path, required): Output PNG path.
    """
    wl = spectra.columns.values
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharex=True)
    for ax, L in zip(axes.flat, sorted(design.Ligand_Ratio.unique())):
        for fam in ["Co-Ni-Cu", "Co-Ni", "Co-Cu", "Ni-Cu"]:
            wells = design.index[(design.Ligand_Ratio == L) & (design.Family == fam)]
            for k, w in enumerate(wells):
                ax.plot(wl, spectra.loc[w], color=FAMILY_COLOURS[fam], lw=1.4 if fam != "Co-Ni-Cu" else 1.0,
                        label=fam if k == 0 else None, zorder=1 if fam == "Co-Ni-Cu" else 2)
        ax.set_title(f"Metal : ligand 1:{L}")
        ax.set_ylabel("Absorbance")
    for ax in axes[1]:
        ax.set_xlabel("Wavelength (nm)")
    axes[0, 0].legend(title="Metals in well", loc="upper right", fontsize=9, title_fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_band_examples(spectra, d2, design, wells, path):
    """Absorbance and second-derivative spectra of representative wells with the band windows shaded.

    Args:
        spectra (pd.DataFrame, required): Absorbance spectra.
        d2 (pd.DataFrame, required): Second-derivative spectra.
        design (pd.DataFrame, required): Output of load_design.
        wells (list[str], required): Sample IDs to show.
        path (Path, required): Output PNG path.
    """
    wl = spectra.columns.values
    m = (wl >= D2_RANGE[0]) & (wl <= D2_RANGE[1])
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for w in wells:
        r = design.loc[w]
        lab = f"Co:Ni:Cu {r.Comp}, M:L 1:{r.Ligand_Ratio}"
        axes[0].plot(wl, spectra.loc[w], lw=1.8, color=FAMILY_COLOURS[r.Family], label=lab)
        axes[1].plot(wl[m], d2.loc[w].values[m], lw=1.8, color=FAMILY_COLOURS[r.Family])
    for ax in axes:
        for name, (lo, hi) in BANDS.items():
            ax.axvspan(lo, hi, color=GRID, alpha=0.6, lw=0, zorder=0)
    for name, (lo, hi) in BANDS.items():
        axes[1].text((lo + hi) / 2, axes[1].get_ylim()[1], f"{name} nm", ha="center", va="bottom", color=INK_2, fontsize=9)
    axes[0].set_ylabel("Absorbance")
    axes[1].set_ylabel(r"$-d^2A/d\lambda^2$ (10$^{-4}$ AU nm$^{-2}$)")
    axes[1].set_xlabel("Wavelength (nm)")
    axes[1].axhline(0, color=MUTED, lw=0.8)
    axes[0].legend(fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_replicates(spectra, design, metrics, path):
    """The 1:1:1 triplicate spectra for each metal:ligand ratio with the coefficient of variation of the scattering level.

    Args:
        spectra (pd.DataFrame, required): Absorbance spectra.
        design (pd.DataFrame, required): Output of load_design.
        metrics (pd.DataFrame, required): Per-well metrics including A_scatter.
        path (Path, required): Output PNG path.
    """
    wl = spectra.columns.values
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4), sharey=True)
    for ax, L in zip(axes, sorted(design.Ligand_Ratio.unique())):
        reps = design.index[(design.Comp == "1:1:1") & (design.Ligand_Ratio == L)]
        for w in reps:
            ax.plot(wl, spectra.loc[w], color=FAMILY_COLOURS["Co-Ni"], lw=1.4)
        a = metrics.loc[reps, "A_scatter"]
        ax.set_title(f"M:L 1:{L}   CV(A$_{{scatter}}$) = {100 * a.std() / a.mean():.0f}%")
        ax.set_xlabel("Wavelength (nm)")
    axes[0].set_ylabel("Absorbance")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_band_by_family(metrics, design, path):
    """Band strengths grouped by which metals the well contains, one panel per band, to show which pair each band needs.

    Args:
        metrics (pd.DataFrame, required): Per-well metrics including B420, B590 and B700.
        design (pd.DataFrame, required): Output of load_design.
        path (Path, required): Output PNG path.
    """
    families = ["Co-Ni", "Co-Cu", "Ni-Cu", "Co-Ni-Cu"]
    titles = {"B420": "Band ~420 nm", "B590": "Band ~590 nm", "B700": "Band ~700 nm (Cu d-d)"}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    rng = np.random.default_rng(0)
    for ax, col in zip(axes, titles):
        for i, fam in enumerate(families):
            for k, L in enumerate(sorted(design.Ligand_Ratio.unique())):
                v = metrics.loc[design.index[(design.Family == fam) & (design.Ligand_Ratio == L)], col]
                x = i + (k - 1.5) * 0.17 + rng.uniform(-0.03, 0.03, len(v))
                ax.scatter(x, v, s=26, color=FAMILY_COLOURS[fam], edgecolors=SURFACE, linewidths=0.8, zorder=3)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_xticks(range(len(families)), families)
        ax.set_title(titles[col])
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel(r"Band strength, $-d^2A/d\lambda^2$ (10$^{-4}$ AU nm$^{-2}$)")
    fig.text(0.5, -0.02, "Within each group, the four clusters are metal : ligand 1:1, 1:2, 1:3, 1:4 (left to right).",
             ha="center", color=INK_2, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_binary_span(metrics, design, null_cut, path):
    """Peak-to-noise of the residual after rebuilding each well from binary spectra: binaries (leave-one-out null) against ternaries.

    Args:
        metrics (pd.DataFrame, required): Per-well metrics including PNR.
        design (pd.DataFrame, required): Output of load_design.
        null_cut (float, required): 95th percentile of the binary null distribution.
        path (Path, required): Output PNG path.
    """
    fig, ax = plt.subplots(figsize=(10, 4.4))
    rng = np.random.default_rng(1)
    for k, L in enumerate(sorted(design.Ligand_Ratio.unique())):
        for j, (kind, colour) in enumerate([("Binary", MUTED), ("Ternary", FAMILY_COLOURS["Co-Ni"])]):
            v = metrics.loc[design.index[(design.Ligand_Ratio == L) & (design.Composition_Type == kind)], "PNR"]
            x = k * 3 + j + rng.uniform(-0.18, 0.18, len(v))
            ax.scatter(x, v, s=34, color=colour, edgecolors=SURFACE, linewidths=0.8, zorder=3,
                       label=("Binary, rebuilt from the other 8 binaries (null)" if kind == "Binary" else
                              "Ternary, rebuilt from the 9 binaries") if k == 0 else None)
    ax.axhline(PNR_THRESHOLD, color=INK, lw=1, ls="--", label="PNR = 3 (criterion in the application)")
    ax.axhline(null_cut, color=CRITICAL, lw=1, ls=":", label=f"95th percentile of the binary null ({null_cut:.1f})")
    ax.set_xticks([k * 3 + 0.5 for k in range(4)], [f"M:L 1:{L}" for L in sorted(design.Ligand_Ratio.unique())])
    ax.set_xlim(-0.8, 11.8)
    ax.set_ylim(0, metrics.PNR.max() * 1.45)
    ax.set_ylabel("Peak-to-noise of residual\n(max over 420-800 nm)")
    ax.set_title("Can each spectrum be rebuilt from binary spectra at the same metal : ligand ratio?", loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=9, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spectra = load_spectra(RAW)
    design = load_design(DESIGN)
    spectra = spectra.loc[design.index]
    wl = spectra.columns.values
    d2 = second_derivative(spectra)
    m = (wl >= D2_RANGE[0]) & (wl <= D2_RANGE[1])

    metrics = band_metrics(d2)
    metrics["A_scatter"] = spectra.loc[:, (wl >= SCATTER_RANGE[0]) & (wl <= SCATTER_RANGE[1])].median(axis=1)

    noise = replicate_noise(d2, design)
    resid = binary_span_residuals(d2.loc[:, m], design)
    pnr = resid.abs() / noise[m]
    metrics["PNR"] = pnr.max(axis=1)
    metrics["PNR_nm"] = pnr.idxmax(axis=1)
    null_cut = float(np.percentile(metrics.loc[design.Composition_Type == "Binary", "PNR"], 95))
    ternary = design.Composition_Type == "Ternary"
    metrics["Flag_PNR_gt_3"] = ternary & (metrics.PNR > PNR_THRESHOLD)
    metrics["Flag_beyond_binary_null"] = ternary & (metrics.PNR > null_cut)

    table = design[["Composition_ID", "Composition_Type", "Family", "Comp", "Co_Ratio", "Ni_Ratio", "Cu_Ratio", "Ligand_Ratio",
                    "x_Co", "x_Ni", "x_Cu", "Notes"]].join(metrics)
    table.round(4).to_csv(OUT / "well_metrics.csv", index_label="Sample")
    table.groupby(["Ligand_Ratio", "Family"])[["A_scatter", "B420", "B590", "B700", "PNR"]].agg(["mean", "std", "count"]).round(3).to_csv(
        OUT / "summary_by_family.csv")
    spectra.rename_axis(index="Sample", columns="Wavelength_nm").stack().rename("Absorbance").reset_index().to_csv(
        OUT / "uvvis_spectra_long.csv", index=False)
    d2.loc[:, m].round(4).to_csv(OUT / "uvvis_second_derivative.csv", index_label="Sample")
    pd.DataFrame({"Wavelength_nm": wl[m], "Replicate_SD": noise[m].values}).round(5).to_csv(OUT / "replicate_noise.csv", index=False)

    plot_design(design, OUT / "fig0_design.png")
    plot_spectra(spectra, design, OUT / "fig1_spectra_by_ratio.png")
    plot_band_examples(spectra, d2, design, ["A1", "A4", "A7", "B3"], OUT / "fig2_band_examples.png")
    ternary_panel_grid(metrics, design, ["A_scatter"], ["Scattering (solid formation)"], ["A (860-900 nm)"],
                       OUT / "fig3_ternary_scattering.png")
    ternary_panel_grid(metrics, design, ["B420", "B590", "B700"], ["Band ~420 nm", "Band ~590 nm", "Band ~700 nm (Cu d-d)"],
                       [r"$-d^2A/d\lambda^2$"] * 3, OUT / "fig4_ternary_bands.png")
    plot_band_by_family(metrics, design, OUT / "fig5_bands_by_pair.png")
    plot_replicates(spectra, design, metrics, OUT / "fig6_replicates.png")
    plot_binary_span(metrics, design, null_cut, OUT / "fig7_binary_span_test.png")

    reps = table[table.Comp == "1:1:1"].groupby("Ligand_Ratio").A_scatter
    print(f"Replicate CV of A_scatter by M:L: {(100 * reps.std() / reps.mean()).round(1).to_dict()}")
    print(f"Binary null PNR 95th percentile: {null_cut:.2f}; ternary PNR max: {table[ternary].PNR.max():.2f}")
    print(f"Ternary wells with PNR > {PNR_THRESHOLD:g}: {int(table.Flag_PNR_gt_3.sum())}/60; beyond binary null: {int(table.Flag_beyond_binary_null.sum())}/60")
    print(table.groupby(["Ligand_Ratio", "Family"])[["A_scatter", "B420", "B590", "B700"]].mean().round(2).to_string())


if __name__ == "__main__":
    main()
