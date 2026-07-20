"""Bar charts from the provincial residual series for the site.

figures/region_bars.png    — net migration rate by region, one panel per
                             census window, shared region order
figures/ncr_dumbbell.png   — Metro Manila city by city, 2015-2020 vs
                             2020-2024 (Makati and Taguig combined: the EMBO
                             barangays moved between them in 2023)

Aggregation notes: where the file carries both individual Makati/Taguig rows
and the EMBO-consistent combined row, the combined row is used (the individual
rows are flagged as inconsistent across the period). The Cotabato unit that
spans Region XII and the BARMM special area is counted with Soccsksargen,
where most of its population lives.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"
figstyle.apply()
SURFACE, INK, INK2, LINE = figstyle.SURFACE, figstyle.INK, figstyle.INK2, figstyle.GRID
BLUE, RED = "#2a7ff0", "#e04234"           # diverging pair (validated)
EARLY, LATE = figstyle.CORAL, figstyle.NAVY  # dumbbell pair, chart voice
GRAY = "#b5b3ac"                           # de-emphasis: BARMM artifact
YRS = {"2015-2020": 4.75, "2020-2024": 4.17}

SHORT = {
    "National Capital Region (NCR)": "Metro Manila (NCR)",
    "Region IV-A (CALABARZON)": "Calabarzon",
    "Region III (Central Luzon)": "Central Luzon",
    "MIMAROPA Region": "Mimaropa",
    "Region VII (Central Visayas)": "Central Visayas",
    "Region XIII (Caraga)": "Caraga",
    "Region VI (Western Visayas)": "Western Visayas",
    "Region II (Cagayan Valley)": "Cagayan Valley",
    "Region XII (SOCCSKSARGEN)": "Soccsksargen",
    "Region XI (Davao Region)": "Davao Region",
    "Negros Island Region (NIR)": "Negros Island",
    "Region IX (Zamboanga Peninsula)": "Zamboanga Peninsula",
    "Region I (Ilocos Region)": "Ilocos Region",
    "Region X (Northern Mindanao)": "Northern Mindanao",
    "Cordillera Administrative Region (CAR)": "Cordillera (CAR)",
    "Region VIII (Eastern Visayas)": "Eastern Visayas",
    "Region V (Bicol Region)": "Bicol",
    "Bangsamoro Autonomous Region In Muslim Mindanao (BARMM)": "BARMM †",
}


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2, labelsize=8.5)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)


def load() -> pd.DataFrame:
    p = pd.read_csv(CLEAN / "net_migration_province.csv")
    p = p[p.net_migration.notna()].copy()
    # combined MKT+TAG row supersedes the flagged individual rows
    p = p[~p.flag.fillna("").str.contains("use combined MKT\\+TAG")]
    p["region"] = p.region.replace({
        "Bangsamoro Autonomous Region In Muslim Mindanao (BARMM);Region XII (SOCCSKSARGEN)":
        "Region XII (SOCCSKSARGEN)"})
    return p


def region_bars(p: pd.DataFrame) -> None:
    rates = {}
    for per, yrs in YRS.items():
        d = p[p.period == per]
        g = d.groupby("region").agg(net=("net_migration", "sum"),
                                    p0=("pop_start", "sum"), p1=("pop_end", "sum"))
        rates[per] = g.net / ((g.p0 + g.p1) / 2) / yrs * 1000
    t = pd.DataFrame(rates).dropna()
    t.index = t.index.map(SHORT)
    t = t.sort_values("2020-2024")
    print(t.round(1).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 6.2), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    ypos = range(len(t))
    for ax, per in zip(axes, YRS):
        style_axes(ax)
        vals = t[per]
        colors = [GRAY if n.endswith("†") else (BLUE if v > 0 else RED)
                  for n, v in vals.items()]
        ax.barh(list(ypos), vals, height=0.62, color=colors)
        ax.axvline(0, color=INK, linewidth=0.8)
        ax.set_title(per.replace("-", "–"), fontsize=12, color=INK,
                     family="serif", loc="left")
        ax.set_xlim(-13, 34.5)
        # direct labels: the story rows only (NCR + the extremes)
        lab = {t.index[0], t.index[-1], "Metro Manila (NCR)", "BARMM †", "Calabarzon"}
        for i, (n, v) in enumerate(vals.items()):
            if n in lab:
                ax.text(v + (0.7 if v >= 0 else -0.7), i, f"{v:+.1f}",
                        va="center", ha="left" if v >= 0 else "right",
                        fontsize=8, color=INK2)
    axes[0].set_yticks(list(ypos), t.index)
    fig.suptitle("Net migration by region", x=0.005, ha="left", fontsize=15,
                 color=INK, family="serif", fontweight=600)
    fig.text(0.005, 0.925, "people gained or lost per 1,000 residents per year, residual method",
             fontsize=9, color=INK2)
    fig.text(0.005, 0.012,
             "† BARMM: mostly a birth-registration artifact, not migration (see limitations). "
             "The Cotabato unit spanning Region XII and the BARMM special area is counted with Soccsksargen.\n"
             "Summed nationally the estimates come to +2.8M (2015–2020) and +0.5M (2020–2024) rather than zero "
             "(international migration plus counting error), so compare bars within a panel.",
             fontsize=7.5, color=INK2)
    fig.subplots_adjust(left=0.155, right=0.985, top=0.86, bottom=0.115, wspace=0.06)
    out = FIG / "region_bars.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", out)


def ncr_dumbbell(p: pd.DataFrame) -> None:
    ncr = p[p.region.fillna("").str.contains("NCR")].copy()
    rows = {}
    for per, yrs in YRS.items():
        d = ncr[ncr.period == per].set_index("unit_name")
        # combine Makati and Taguig in 2015-2020 to match the 2020-2024 unit
        if "City of Makati" in d.index:
            mt = d.loc[["City of Makati", "City of Taguig"]].sum()
            d = d.drop(["City of Makati", "City of Taguig"])
            d.loc["Makati + Taguig (EMBO-consistent)"] = mt
        rows[per] = d.net_migration / ((d.pop_start + d.pop_end) / 2) / yrs * 1000
    t = pd.DataFrame(rows).dropna()
    t.index = (t.index.str.replace("City of ", "", regex=False)
                      .str.replace(" (EMBO-consistent)", "", regex=False)
                      .str.replace("Pasay City", "Pasay"))
    t = t.sort_values("2020-2024")
    print(t.round(1).to_string())

    fig, ax = plt.subplots(figsize=(10.8, 6.4))
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    ypos = range(len(t))
    ax.axvline(0, color=INK, linewidth=0.8)
    for i, (name, r) in enumerate(t.iterrows()):
        a, b = r["2015-2020"], r["2020-2024"]
        ax.plot([a, b], [i, i], color=LINE, linewidth=2, zorder=1)
        ax.plot(a, i, "o", ms=9, color=EARLY, mec=SURFACE, mew=2, zorder=2)
        ax.plot(b, i, "o", ms=9, color=LATE, mec=SURFACE, mew=2, zorder=3)
    ax.set_yticks(list(ypos), t.index)
    # direct labels on the two most extreme movers
    for name in (t["2020-2024"].idxmax(), (t["2015-2020"] - t["2020-2024"]).abs().idxmax()):
        i = list(t.index).index(name)
        a, b = t.loc[name, "2015-2020"], t.loc[name, "2020-2024"]
        ax.text(b + (1 if b >= a else -1), i, f"{b:+.1f}", va="center",
                ha="left" if b >= a else "right", fontsize=8, color=INK2)
    ax.legend(handles=[
        plt.Line2D([], [], marker="o", ls="", ms=9, color=EARLY, mec=SURFACE, mew=2, label="2015–2020"),
        plt.Line2D([], [], marker="o", ls="", ms=9, color=LATE, mec=SURFACE, mew=2, label="2020–2024")],
        loc="upper left", frameon=True, framealpha=1, edgecolor="#d9d9d9",
        facecolor=SURFACE, fontsize=9.5, labelcolor=INK, borderpad=0.8)
    ax.set_title("Metro Manila, city by city", fontsize=15, color=INK,
                 family="serif", loc="left", pad=26)
    ax.text(0, 1.045, "net migration per 1,000 residents per year",
            transform=ax.transAxes, fontsize=9, color=INK2)
    fig.text(0.005, 0.012,
             "Makati and Taguig are shown combined: ten barangays moved between them in 2023.",
             fontsize=7.5, color=INK2)
    fig.subplots_adjust(left=0.18, right=0.97, top=0.885, bottom=0.09)
    out = FIG / "ncr_dumbbell.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", out)


def main() -> None:
    p = load()
    region_bars(p)
    ncr_dumbbell(p)
    import shutil
    for f in ("region_bars.png", "ncr_dumbbell.png"):
        shutil.copy(FIG / f, ROOT / "docs" / "assets" / f)


if __name__ == "__main__":
    main()
