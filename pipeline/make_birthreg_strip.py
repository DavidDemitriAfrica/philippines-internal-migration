"""Birth-registration visibility strip: registered births per 1,000 people,
by geographic province and year (2013-2024).

This is a *visibility* chart, not a fertility chart: where rows run pale,
births are going unregistered (true birth rates do not fall to 8/1,000 in
provinces with the country's youngest populations). BARMM rows sit at the
bottom and are labeled — this is the on-figure version of the dataset's
biggest caveat.

Denominator: nearest census population (2015 for 2013-17, 2020 for 2018-22,
2024 for 2023-24), stated on the figure. Outputs:
figures/birth_registration_strip.png (all provinces × years, for the paper)
figures/birthreg_lines.png (emphasis line chart for the site: every province
in gray, BARMM provinces highlighted, national rate for reference)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_prov_vs_panel import parse_deaths_2006_2015  # noqa: F401  (module import path)
from psgc import normalize_name, strip_parens  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"
SURFACE, TEXT, TEXT2, WARM = "#ffffff", "#1b1b1b", "#555555", "#b4552d"
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
BINS = [0, 8, 12, 16, 20, 24, 28, 60]
YEARS = list(range(2013, 2025))

BARMM = {"basilan", "sulu", "tawi tawi", "lanao del sur", "maguindanao (undivided)",
         "cotabato (incl sga)"}  # cotabato is XII but hosts SGA — not flagged


def main() -> None:
    plt.rcParams["font.family"] = "serif"
    vs = pd.read_csv(CLEAN / "vital_statistics_provincial.csv")
    vs = vs[vs.year.isin(YEARS) & vs.births.notna()]

    # nearest-census province denominators from the unit table geography
    prov = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    # reuse the site fold: build geographic-province pops from the municipal panel
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    r24 = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    cp = cp.merge(r24[["psgc10", "pop2024"]], on="psgc10", how="left")
    from psgc import CITY_HOST_PROVINCE
    def geo_prov(row):
        nm = normalize_name(str(row["name"]))
        host = CITY_HOST_PROVINCE.get(nm)
        if host:
            return host
        p = normalize_name(strip_parens(str(row.province)))
        if "national capital region" in p:
            return "national capital region"
        if p in ("maguindanao del norte", "maguindanao del sur"):
            return "maguindanao (undivided)"
        if p == "cotabato":
            return "cotabato (incl sga)"
        if "bangsamoro" in p:
            return "cotabato (incl sga)"  # SGA munis
        return p
    cp["geo"] = cp.apply(geo_prov, axis=1)
    pops = cp.groupby("geo")[["pop2015", "pop2020", "pop2024"]].sum(min_count=1)

    vs["geo_n"] = vs.geo.map(lambda s: normalize_name(strip_parens(str(s))))
    vs.loc[vs.geo_n == "maguindanao", "geo_n"] = "maguindanao (undivided)"
    vs.loc[vs.geo_n == "cotabato (incl. sga)", "geo_n"] = "cotabato (incl sga)"

    def denom(geo, yr):
        col = "pop2015" if yr <= 2017 else ("pop2020" if yr <= 2022 else "pop2024")
        try:
            return pops.loc[geo, col]
        except KeyError:
            return np.nan
    vs["rate"] = [b / denom(g, y) * 1000 for b, g, y in zip(vs.births, vs.geo_n, vs.year)]
    mat = vs.pivot_table(index="geo_n", columns="year", values="rate", aggfunc="first")
    mat = mat.dropna(how="all")
    order = mat.mean(axis=1).sort_values(ascending=False).index
    mat = mat.loc[order]

    cmap = ListedColormap(RAMP)
    norm = BoundaryNorm(BINS, cmap.N)
    fig, ax = plt.subplots(figsize=(8.2, 12.5))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    ax.pcolormesh(np.arange(len(YEARS) + 1), np.arange(len(mat) + 1),
                  mat[YEARS].values, cmap=cmap, norm=norm, edgecolors=SURFACE, linewidth=0.6)
    ax.set_xticks(np.arange(len(YEARS)) + 0.5)
    ax.set_xticklabels(YEARS, fontsize=8, color=TEXT2)
    ax.set_yticks(np.arange(len(mat)) + 0.5)
    labels = []
    for gname in mat.index:
        pretty = gname.replace(" (undivided)", "").replace(" (incl sga)", " (incl. SGA)").title()
        labels.append(pretty)
    ax.set_yticklabels(labels, fontsize=6.6,
                       color=TEXT2)
    for i, gname in enumerate(mat.index):
        if gname in BARMM:
            ax.get_yticklabels()[i].set_color(WARM)
            ax.get_yticklabels()[i].set_fontweight("bold")
    ax.invert_yaxis()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Registered births per 1,000 people — where births go uncounted\n"
                 "provinces sorted by average rate; BARMM provinces in orange",
                 fontsize=12.5, color=TEXT, loc="left", pad=12)
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                      orientation="horizontal", fraction=0.025, pad=0.03, aspect=45)
    cb.set_label("registered births per 1,000 people (nearest-census denominator)",
                 fontsize=8.5, color=TEXT2)
    cb.ax.tick_params(labelsize=8, colors=TEXT2)
    cb.outline.set_visible(False)
    fig.text(0.01, 0.005,
             "Pale rows mean births going unregistered, not low fertility: the palest provinces have "
             "the country's youngest populations. Maguindanao's dark row is the flip side — "
             "registration catch-up campaigns after 2016. Sources: PSA civil registration + censuses.",
             fontsize=8, color=TEXT2)
    plt.tight_layout()
    out = FIG / "birth_registration_strip.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    shutil.copy(out, ROOT / "docs" / "assets" / "birth_registration_strip.png")
    print("wrote", out)
    print(mat.tail(8).round(1).to_string())

    # site version: emphasis lines instead of the 80-row heatmap
    WHITE, INKC, INK2C, GRID = "#ffffff", "#1b1b1b", "#555555", "#e9e9e9"
    NAVY, CORAL = "#24435c", "#e8794f"
    plt.rcParams["font.family"] = "serif"
    natl = vs.groupby("year").births.sum()
    nat_pop = {y: (pops.pop2015.sum() if y <= 2017 else
                   pops.pop2020.sum() if y <= 2022 else pops.pop2024.sum())
               for y in YEARS}
    nat_rate = [natl.get(y, np.nan) / nat_pop[y] * 1000 for y in YEARS]

    fig, ax = plt.subplots(figsize=(11.4, 5.8))
    fig.patch.set_facecolor(WHITE); ax.set_facecolor(WHITE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2C, labelsize=10.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)
    for gname in mat.index:  # context: every non-BARMM province, thin gray
        if gname not in BARMM:
            ax.plot(YEARS, mat.loc[gname, YEARS], color="#d4d4d4",
                    linewidth=0.9, zorder=1)
    ends = []
    for gname in mat.index:  # the story: BARMM provinces
        if gname in BARMM:
            vals = mat.loc[gname, YEARS]
            ax.plot(YEARS, vals, color=CORAL, linewidth=2.2,
                    solid_capstyle="round", solid_joinstyle="round", zorder=3)
            pretty = (gname.replace(" (undivided)", "")
                           .replace("tawi tawi", "tawi-tawi").title())
            last = vals.dropna()
            ends.append([last.index[-1] + 0.15, last.iloc[-1], pretty])
    ends.sort(key=lambda e: e[1])  # spread colliding end labels
    for i in range(1, len(ends)):
        if ends[i][1] - ends[i - 1][1] < 1.5:
            ends[i][1] = ends[i - 1][1] + 1.5
    for x, y, pretty in ends:
        ax.text(x, y, pretty, fontsize=9.5, color=CORAL, va="center")
    ax.plot(YEARS, nat_rate, color=NAVY, linewidth=2.6, zorder=4,
            solid_capstyle="round", solid_joinstyle="round")
    ax.text(YEARS[-1] + 0.15, nat_rate[-1], "Philippines", fontsize=10,
            color=NAVY, va="center", fontweight="bold")
    ax.set_xlim(2013, 2027.4)
    ax.set_xticks(range(2013, 2025, 2))
    ax.set_ylim(0, 42)
    ax.set_ylabel("Registered Births per 1,000 People", fontsize=11.5, color=INKC)
    ax.set_xlabel("Year", fontsize=11.5, color=INKC)
    leg = ax.legend(handles=[
        plt.Line2D([], [], color=CORAL, lw=2.2, label="BARMM provinces"),
        plt.Line2D([], [], color=NAVY, lw=2.6, label="Philippines"),
        plt.Line2D([], [], color="#d4d4d4", lw=1, label="Every other province")],
        loc="upper left", fontsize=10, labelcolor=INKC, frameon=True,
        framealpha=1, edgecolor="#d9d9d9", facecolor=WHITE, borderpad=0.8,
        handlelength=1.6)
    leg.get_frame().set_linewidth(0.8)
    ax.set_title("Births go unregistered in BARMM, and the estimates absorb that",
                 fontsize=14.5, color=INKC, loc="left", pad=14)
    fig.text(0.005, 0.012,
             "Registered, not occurred: PSA's 2020 census found 77% of BARMM's population had a registered birth\n"
             "vs 96.6% nationally. Maguindanao's spike after 2016 is backlog registration, not a birth wave. "
             "Denominators: nearest census.",
             fontsize=8, color=INK2C, family="serif")
    fig.subplots_adjust(left=0.07, right=0.985, top=0.905, bottom=0.185)
    out2 = FIG / "birthreg_lines.png"
    fig.savefig(out2, dpi=150, facecolor=WHITE)
    plt.close(fig)
    shutil.copy(out2, ROOT / "docs" / "assets" / "birthreg_lines.png")
    print("wrote", out2)


if __name__ == "__main__":
    main()
