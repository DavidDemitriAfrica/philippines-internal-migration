"""Municipal choropleth: residual net migration rate 2020-2024.

Same validated diverging scale as the province maps. Excluded municipalities
(boundary breaks, SGA, missing VS) are hatched. 2023-vintage polygon PSGC
codes are translated to 1Q-2025 where they differ (NIR renumbering at the
municipal level shares the province prefix fix).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_maps import BINS, BLUE_ARM, LABELS, NEUTRAL, RED_ARM, SURFACE, TEXT, TEXT2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"

NIR_PREFIX = {"06045": "18045", "07046": "18046", "07061": "18061"}


def load_geo() -> gpd.GeoDataFrame:
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/municities/*.json"))]
    g = pd.concat(parts, ignore_index=True)
    g["psgc10"] = (g["adm3_psgc"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10))
    pref = g.psgc10.str[:5].map(NIR_PREFIX)
    g.loc[pref.notna(), "psgc10"] = pref[pref.notna()] + g.loc[pref.notna(), "psgc10"].str[5:]
    return g[["psgc10", "adm3_en", "geometry"]]


def main() -> None:
    FIG.mkdir(exist_ok=True)
    geo = load_geo()
    r = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    gg = geo.merge(r[["psgc10", "netmig_rate_per_1000_yr", "flag"]], on="psgc10", how="left")
    unmatched = gg[gg.netmig_rate_per_1000_yr.isna() & ~gg.flag.notna()]
    print("polygons without any record:", len(unmatched))
    if len(unmatched):
        print(unmatched[["psgc10", "adm3_en"]].head(12).to_string())

    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)
    fig, ax = plt.subplots(figsize=(8.5, 11))
    fig.patch.set_facecolor(SURFACE)
    gg.plot(ax=ax, column="netmig_rate_per_1000_yr", cmap=cmap, norm=norm,
            edgecolor="#ffffff", linewidth=0.15,
            missing_kwds={"color": "#e5e4e0", "hatch": "///", "edgecolor": "#ffffff",
                          "linewidth": 0.15})
    ax.set_axis_off()
    handles = [Patch(facecolor=c, edgecolor="#d8d7d3", linewidth=0.5, label=l)
               for c, l in zip(RED_ARM + [NEUTRAL] + BLUE_ARM, LABELS)]
    handles.append(Patch(facecolor="#e5e4e0", hatch="///", edgecolor="#ffffff",
                         label="excluded / no estimate"))
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=False,
              labelcolor=TEXT2, title="rate per 1,000 per year", title_fontsize=9)
    ax.set_title("Net internal migration by city/municipality, residual method\n"
                 "Philippines, 2020–2024", fontsize=14, color=TEXT, pad=10)
    fig.text(0.5, 0.045,
             "Residual = population change (2020 CPH → 2024 POPCEN) − registered natural increase. "
             "Hatched: boundary changes (Makati/Taguig,\nN. Cotabato→SGA), SGA municipalities, or missing inputs. "
             "BARMM rates inflated by birth under-registration — see codebook.",
             ha="center", fontsize=8, color=TEXT2)
    out = FIG / "net_migration_municipal_2020_2024.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print("wrote", out)


if __name__ == "__main__":
    main()
