"""The drifting center of gravity: population-weighted mean location of the
Philippine population, 1960-2020, from the municipal census panel.

Weighted per census year over every municipality enumerated that year
(Report 2A Table 1 keeps mother municipalities' as-enumerated totals, so each
year covers 92-94% of the official total without double counting). National
path over the country outline plus a zoomed inset. Headline: south toward the
Mindanao frontier 1960-1990, then back toward Manila 1990-2020.

Output: figures/centroid_drift.png
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"
SURFACE, TEXT, TEXT2, BLUE, LINE = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#d8d7d3"
YEARS = [1960, 1970, 1980, 1990, 2000, 2010, 2015, 2020]
NIR = {"06045": "18045", "07046": "18046", "07061": "18061"}


def main() -> None:
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/municities/*.json"))]
    g = pd.concat(parts, ignore_index=True)
    g["psgc10"] = g["adm3_psgc"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    pref = g.psgc10.str[:5].map(NIR)
    g.loc[pref.notna(), "psgc10"] = pref[pref.notna()] + g.loc[pref.notna(), "psgc10"].str[5:]
    gg = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326").to_crs(3857)
    cent = gg.geometry.centroid.to_crs(4326)
    cen = pd.DataFrame({"psgc10": gg.psgc10, "lon": cent.x, "lat": cent.y})

    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    m = cp.merge(cen, on="psgc10", how="inner").dropna(subset=["lon", "lat"])
    # per-year weighting over every municipality enumerated that year: Table 1
    # records mother municipalities' as-enumerated totals, so each census year
    # covers (nearly) the whole population without double counting
    path = []
    for y in YEARS:
        sub = m[m[f"pop{y}"].notna()]
        w = sub[f"pop{y}"]
        cov = w.sum() / {1960: 27087685, 1970: 36684486, 1980: 48098460, 1990: 60703810,
                         2000: 76506928, 2010: 92337852, 2015: 100981437, 2020: 109035343}[y]
        path.append((y, np.average(sub.lon, weights=w), np.average(sub.lat, weights=w), cov))
        print(f"{y}: {len(sub)} munis, {cov*100:.1f}% of official total")
    path = pd.DataFrame(path, columns=["year", "lon", "lat", "coverage"])
    print(path[["year", "lon", "lat"]].to_string(index=False))
    n_note = f"{len(m)} municipalities; per-census coverage {path.coverage.min()*100:.0f}–{path.coverage.max()*100:.0f}% of official totals"

    outline = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326").dissolve()

    fig, (ax, axz) = plt.subplots(1, 2, figsize=(11.5, 7.5),
                                  gridspec_kw={"width_ratios": [1, 1.15]})
    fig.patch.set_facecolor(SURFACE)
    for a in (ax, axz):
        a.set_facecolor(SURFACE)
        a.set_axis_off()
    outline.plot(ax=ax, color="#eceae5", edgecolor="#d8d7d3", linewidth=0.4)
    ax.plot(path.lon, path.lat, "-", color=BLUE, lw=2, zorder=3)
    ax.scatter(path.lon, path.lat, s=26, color=BLUE, zorder=4, edgecolor=SURFACE, lw=1)
    ax.add_patch(plt.Rectangle((path.lon.min() - .25, path.lat.min() - .25),
                               path.lon.max() - path.lon.min() + .5,
                               path.lat.max() - path.lat.min() + .5,
                               fill=False, edgecolor=TEXT2, lw=0.9))
    ax.set_title("Where the average Filipino lives", fontsize=12, color=TEXT, loc="left")

    axz.plot(path.lon, path.lat, "-", color=BLUE, lw=2.5, zorder=3)
    axz.scatter(path.lon, path.lat, s=64, color=BLUE, zorder=4, edgecolor=SURFACE, lw=1.5)
    for _, r in path.iterrows():
        dx, dy = (8, -3)
        if r.year == 2015: dx, dy = (2, -16)
        if r.year == 2020: dx, dy = (-34, -3)
        axz.annotate(int(r.year), (r.lon, r.lat), textcoords="offset points",
                     xytext=(dx, dy), fontsize=10, color=TEXT)
    axz.set_title("Zoom: the 1960–2020 drift (~%d km south-…)"
                  % 0, fontsize=12, color=TEXT, loc="left")
    axz.set_aspect(1 / np.cos(np.radians(path.lat.mean())))
    axz.margins(0.25)

    # distance annotation
    from math import radians, sin, cos, asin, sqrt
    def hav(lo1, la1, lo2, la2):
        lo1, la1, lo2, la2 = map(radians, (lo1, la1, lo2, la2))
        return 2 * 6371 * asin(sqrt(sin((la2 - la1) / 2) ** 2
                               + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2))
    seg = sum(hav(path.lon.iloc[i], path.lat.iloc[i], path.lon.iloc[i+1], path.lat.iloc[i+1])
              for i in range(len(path) - 1))
    axz.set_title("Zoom: south toward the Mindanao frontier (1960–90),\n"
                  f"then back toward Manila (1990–2020) — ≈{seg:.0f} km of drift",
                  fontsize=12, color=TEXT, loc="left")

    fig.suptitle("The Philippines' demographic center of gravity, 1960–2020",
                 fontsize=15, color=TEXT, x=0.02, ha="left")
    fig.text(0.02, 0.03,
             f"Population-weighted mean of municipal centroids, weighted per census year ({n_note}). "
             "Sources: PSA censuses (2020 CPH Report 2A Table 1 / Table B).",
             fontsize=8.5, color=TEXT2)
    plt.tight_layout(rect=[0, 0.05, 1, 0.94])
    fig.savefig(FIG / "centroid_drift.png", dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print("wrote", FIG / "centroid_drift.png")


if __name__ == "__main__":
    main()
