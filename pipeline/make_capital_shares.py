"""Time series: Metro Manila's and its suburban ring's share of the national
population across the eight censuses 1960-2020.

The census panel restates history to current municipalities, so "Rizal" is
today's Rizal throughout (the cities that left it for Metro Manila in 1975
carry their own series). Shares use PSA's published national census counts.

Output: figures/capital_shares.png (+ docs/assets copy)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SURFACE, INK, INK2, GRID = "#ffffff", "#1b1b1b", "#555555", "#e9e9e9"
NAVY, CORAL = "#24435c", "#e8794f"
RING = ["Cavite", "Laguna", "Rizal", "Bulacan"]
YEARS = [1960, 1970, 1980, 1990, 2000, 2010, 2015, 2020]
NATIONAL = {1960: 27_087_685, 1970: 36_684_486, 1980: 48_098_460,
            1990: 60_703_206, 2000: 76_506_928, 2010: 92_337_852,
            2015: 100_981_437, 2020: 109_035_343}


def main() -> None:
    plt.rcParams["font.family"] = "serif"
    cp = pd.read_csv(ROOT / "data/clean/population_census_municipal.csv",
                     dtype={"psgc10": str})
    ncr = cp[cp.province.fillna("").str.contains("National Capital")]
    ring = cp[cp.province.isin(RING)]
    ncr_share = [ncr[f"pop{y}"].sum() / NATIONAL[y] * 100 for y in YEARS]
    ring_share = [ring[f"pop{y}"].sum() / NATIONAL[y] * 100 for y in YEARS]
    print("NCR share:", [round(v, 1) for v in ncr_share])
    print("ring share:", [round(v, 1) for v in ring_share])

    fig, ax = plt.subplots(figsize=(11.4, 5.6))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2, labelsize=10.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)

    for vals, color, name in ((ncr_share, NAVY, "Metro Manila"),
                              (ring_share, CORAL, "Cavite + Laguna + Rizal + Bulacan")):
        ax.plot(YEARS, vals, color=color, linewidth=2.4, solid_capstyle="round",
                solid_joinstyle="round", marker="o", ms=5.5, mec=SURFACE,
                mew=1.4, label=name, clip_on=False)
        ax.annotate(f"{vals[-1]:.1f}%", (YEARS[-1], vals[-1]),
                    xytext=(9, 0), textcoords="offset points",
                    va="center", fontsize=10.5, color=color)
    ax.set_xlim(1958, 2022)
    ax.set_xticks(YEARS, [str(y) for y in YEARS])
    ax.set_yticks(range(0, 16, 3), [str(v) for v in range(0, 16, 3)])
    ax.set_ylim(0, 15.5)
    ax.set_ylabel("Share of National Population (%)", fontsize=11.5, color=INK)
    ax.set_xlabel("Census Year", fontsize=11.5, color=INK)
    leg = ax.legend(loc="upper left", fontsize=10.5, labelcolor=INK,
                    frameon=True, framealpha=1, edgecolor="#d9d9d9",
                    facecolor=SURFACE, borderpad=0.8, handlelength=1.6)
    leg.get_frame().set_linewidth(0.8)
    ax.set_title("Share of all Filipinos living in and around the capital",
                 fontsize=15, color=INK, loc="left", pad=14)
    fig.text(0.005, 0.012,
             "Provinces use today's boundaries throughout: the cities that left Rizal for "
             "Metro Manila in 1975 are counted with Metro Manila in every census.",
             fontsize=8, color=INK2, family="serif")
    fig.subplots_adjust(left=0.075, right=0.93, top=0.9, bottom=0.155)
    out = ROOT / "figures" / "capital_shares.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    import shutil
    shutil.copy(out, ROOT / "docs" / "assets" / "capital_shares.png")
    print("wrote", out)


if __name__ == "__main__":
    main()
