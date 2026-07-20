"""Animated time-lapse: municipal population growth relative to the national
rate, per intercensal window 1960→2024.

Metric per window: annualized municipal growth minus annualized national
growth (pp/yr). Positive (blue) = gaining population share — in-migration
flavored; negative (red) = losing share. One diverging scale across all eight
windows makes eras comparable; 2020–2024 uses the verified 2024 counts.

Output: figures/growth_timelapse.gif (+ docs/assets copy)
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"
figstyle.apply()
SURFACE, TEXT, TEXT2 = figstyle.SURFACE, figstyle.INK, figstyle.INK2
RED_ARM = ["#6b1414", "#a11d1d", "#e04234", "#f79b8e"]
NEUTRAL = "#f0efec"
BLUE_ARM = ["#74b3f7", "#2a7ff0", "#0f5ec4", "#093a80"]
BINS = [-np.inf, -3, -1.5, -0.5, -0.15, 0.15, 0.5, 1.5, 3, np.inf]
LABELS = ["< −3", "−3 to −1.5", "−1.5 to −0.5", "−0.5 to −0.15", "≈ national",
          "0.15 to 0.5", "0.5 to 1.5", "1.5 to 3", "> 3"]
NIR = {"06045": "18045", "07046": "18046", "07061": "18061"}

# PSA national census counts — the anchor for "growth vs national". Panel
# column sums would misstate it where early censuses are missing rows for
# municipalities that did not yet exist.
NATIONAL = {1960: 27_087_685, 1970: 36_684_486, 1980: 48_098_460,
            1990: 60_703_206, 2000: 76_506_928, 2010: 92_337_852,
            2015: 100_981_437, 2020: 109_035_343, 2024: 112_729_484}

WINDOWS = [  # (start, end, years, label)
    (1960, 1970, 10.19, "1960 → 1970"), (1970, 1980, 9.99, "1970 → 1980"),
    (1980, 1990, 10.0, "1980 → 1990"), (1990, 2000, 10.0, "1990 → 2000"),
    (2000, 2010, 10.0, "2000 → 2010"), (2010, 2015, 5.25, "2010 → 2015"),
    (2015, 2020, 4.75, "2015 → 2020"), (2020, 2024, 4.17, "2020 → 2024"),
]


def load_geo() -> gpd.GeoDataFrame:
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/municities/*.json"))]
    g = pd.concat(parts, ignore_index=True)
    g["psgc10"] = g["adm3_psgc"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    pref = g.psgc10.str[:5].map(NIR)
    g.loc[pref.notna(), "psgc10"] = pref[pref.notna()] + g.loc[pref.notna(), "psgc10"].str[5:]
    # fill the five empty hires geometries from the medres patch files, and
    # drop Kalayaan (Spratlys): 400 km west, it would shrink every frame
    empty = g.geometry.isna() | g.geometry.is_empty
    if empty.any():
        patch = pd.concat([gpd.read_file(f) for f in
                           glob.glob(str(ROOT / "data/raw/boundaries/municities_medres_patch/*.json"))],
                          ignore_index=True)
        patch["psgc10"] = (patch["adm3_psgc"].astype(str)
                           .str.replace(r"\.0$", "", regex=True).str.zfill(10))
        g.loc[empty, "geometry"] = g.loc[empty, "psgc10"].map(patch.set_index("psgc10").geometry)
    g = g[g.geometry.notna() & ~g.geometry.is_empty & (g.psgc10 != "1705321000")]
    gg = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326")
    simp = gg.geometry.simplify(0.004, preserve_topology=True)
    bad = simp.is_empty | simp.isna()
    simp[bad] = gg.geometry[bad]
    return gg.set_geometry(simp)[["psgc10", "geometry"]]


def main() -> None:
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    r24 = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    cp = cp.merge(r24[["psgc10", "pop2024"]], on="psgc10", how="left")
    geo = load_geo().merge(cp, on="psgc10", how="left")

    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)

    frames = []
    for a, b, yrs, label in WINDOWS:
        pa, pb = geo[f"pop{a}"], geo[f"pop{b}"]
        with np.errstate(all="ignore"):
            g_mun = ((pb / pa) ** (1 / yrs) - 1) * 100
        nat = ((NATIONAL[b] / NATIONAL[a]) ** (1 / yrs) - 1) * 100
        rel = g_mun - nat
        fig, ax = plt.subplots(figsize=(7.4, 9.6))
        fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE); ax.set_axis_off()
        plot_df = geo.assign(rel=rel)
        plot_df.plot(ax=ax, column="rel", cmap=cmap, norm=norm,
                     edgecolor="#ffffff", linewidth=0.3,
                     missing_kwds={"color": "#e5e4e0", "edgecolor": "#ffffff",
                                   "linewidth": 0.3})
        ax.set_title(f"Gaining and losing population share\n{label}",
                     fontsize=16, color=TEXT, loc="left", family="serif")
        handles = [Patch(facecolor=c, edgecolor="#d8d7d3", linewidth=0.4, label=l)
                   for c, l in zip(RED_ARM + [NEUTRAL] + BLUE_ARM, LABELS)]
        handles.append(Patch(facecolor="#e5e4e0", label="no data"))
        ax.legend(handles=handles, loc="lower left", fontsize=7.5, frameon=False,
                  labelcolor=TEXT2, title="growth vs national (pp/yr)", title_fontsize=8.5)
        fig.text(0.03, 0.015,
                 "Municipal growth minus national growth, per census window. PSA censuses.",
                 fontsize=7.5, color=TEXT2)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        frames.append(Image.fromarray(buf))
        plt.close(fig)
        print(label, "national %/yr:", round(nat, 2))

    out = FIG / "growth_timelapse.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=[1400] * (len(frames) - 1) + [2600], loop=0, optimize=True)
    print("wrote", out, f"({out.stat().st_size // 1024} KB)")
    (ROOT / "docs" / "assets").mkdir(exist_ok=True)
    import shutil
    shutil.copy(out, ROOT / "docs" / "assets" / "growth_timelapse.gif")


if __name__ == "__main__":
    main()
