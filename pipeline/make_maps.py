"""Choropleth maps: provincial residual net migration rates, 2015-2020 and
2020-2024.

Display units are GEOGRAPHIC provinces: HUC values are folded into their host
province (components' net_migration and populations summed, rate recomputed),
NCR is dissolved to a single unit, Cotabato City into Maguindanao del Norte,
Isabela City into Basilan, SGA into Cotabato (its polygon lies within North
Cotabato in the 2023 boundaries). This is a *visualization* aggregation only —
the published CSV keeps PSA's province/HUC units.

Colors: diverging blue (net in-migration) / red (net out-migration) with a
neutral gray midpoint, arms lightness-matched in OKLab and validated with the
dataviz palette validator (ordinal mode, light surface). Boundaries:
faeldon/philippines-json-maps 2023 (PSA/NAMRIA-derived), lowres.
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
from psgc import CITY_HOST_PROVINCE  # noqa: E402  (single source of truth)

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"

# validated bin colors (see module docstring)
RED_ARM = ["#762221", "#9e3432", "#d75853", "#ea9a93"]   # most-negative -> slightly-negative
NEUTRAL = "#f0efec"
BLUE_ARM = ["#86b6ef", "#3987e5", "#1c5cab", "#104281"]  # slightly-positive -> most-positive
BINS = [-np.inf, -10, -5, -2, -0.5, 0.5, 2, 5, 10, np.inf]
LABELS = ["< −10", "−10 to −5", "−5 to −2", "−2 to −0.5", "−0.5 to 0.5",
          "0.5 to 2", "2 to 5", "5 to 10", "> 10"]
SURFACE = "#fcfcfb"
TEXT, TEXT2 = "#0b0b0b", "#52514e"


def load_geo() -> gpd.GeoDataFrame:
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/provdists-region-*.json"))]
    g = pd.concat(parts, ignore_index=True)
    g["prov5"] = g["adm2_psgc"].astype(str).str.zfill(10).str[:5]
    g["reg2"] = g["adm2_psgc"].astype(str).str.zfill(10).str[:2]
    # 2023-boundary codes -> 1Q-2025 PSGC (Negros Island Region renumbering),
    # and fold special polygons into their display units (Isabela City ->
    # Basilan; SGA polygon -> Cotabato incl. SGA)
    g["prov5"] = g["prov5"].replace({"06045": "18045", "07046": "18046", "07061": "18061",
                                     "09901": "19007", "19099": "12047"})
    # dissolve NCR districts into one display unit
    g.loc[g.reg2 == "13", "prov5"] = "13NCR"
    g = g.dissolve(by="prov5", as_index=False)[["prov5", "adm2_en", "geometry"]]
    return g


def display_values(period: str) -> pd.DataFrame:
    r = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    r = r[(r.period == period) & r.net_migration.notna()].copy()
    m = pd.read_csv(CLEAN / "municipalities.csv", dtype=str)
    name_by_id = dict(zip(m.psgc10, m.name))
    prov_norm_to5 = {}
    mm = pd.read_csv(ROOT / "data/interim/psgc_municipalities.csv", dtype=str)
    from psgc import normalize_name
    provs = pd.read_csv(ROOT / "data/interim/psgc_provinces.csv", dtype=str)
    for _, p in provs.iterrows():
        prov_norm_to5[normalize_name(p.province)] = p.prov_code

    def display_key(row):
        uid = row.unit_id
        if len(uid) == 5 and uid.isdigit():
            return uid                       # province
        if uid.startswith("13"):
            return "13NCR"                   # NCR city
        nm = normalize_name(name_by_id.get(uid, ""))
        host = CITY_HOST_PROVINCE.get(nm)
        if host:
            return prov_norm_to5.get(host, None)
        if uid == "19087+19088+CC":
            return None                      # split into MdN/MdS below
        if uid == "12047+19999":
            return "12047"
        return None

    # use combined rows where they are canonical; drop their components
    drop = {"1380300000", "1381500000"}      # Makati/Taguig individual (combined row exists 2020-2024)
    if period == "2015-2020":
        drop = set()
    r = r[~((r.period == "2020-2024") & r.unit_id.isin(drop - drop))]  # keep; MKT+TAG both map to NCR anyway
    r["disp"] = r.apply(display_key, axis=1)
    # Maguindanao combined -> assign the same rate to both successor polygons
    extra = []
    for _, row in r[r.unit_id.isin(["19087+19088", "19087+19088+CC"])].iterrows():
        for p5 in ("19087", "19088"):
            e = row.copy(); e["disp"] = p5
            extra.append(e)
    r = pd.concat([r[r.disp.notna()], pd.DataFrame(extra)], ignore_index=True)
    # avoid double counting: within a display unit, drop combined rows whose
    # components are already present
    if period == "2020-2024":
        r = r[r.unit_id != "MKT+TAG"]        # components present (flagged), both in NCR
        r = r[r.unit_id != "12047"]          # combined 12047+19999 is canonical
    g = r.groupby("disp").agg(net_migration=("net_migration", "sum"),
                              pop_start=("pop_start", "sum"), pop_end=("pop_end", "sum")).reset_index()
    dt = 4.75 if period == "2015-2020" else 4.17
    g["rate"] = g.net_migration / ((g.pop_start + g.pop_end) / 2) / dt * 1000
    return g[["disp", "rate", "net_migration"]]


def main() -> None:
    FIG.mkdir(exist_ok=True)
    geo = load_geo()
    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)

    fig, axes = plt.subplots(1, 2, figsize=(13, 9))
    fig.patch.set_facecolor(SURFACE)
    for ax, period in zip(axes, ("2015-2020", "2020-2024")):
        vals = display_values(period)
        gg = geo.merge(vals, left_on="prov5", right_on="disp", how="left")
        gg.plot(ax=ax, column="rate", cmap=cmap, norm=norm,
                edgecolor="#ffffff", linewidth=0.4,
                missing_kwds={"color": "#e5e4e0", "hatch": "///", "edgecolor": "#ffffff"})
        ax.set_title(f"{period.replace('-', '–')}", fontsize=13, color=TEXT, pad=8)
        ax.set_axis_off()
        ax.set_facecolor(SURFACE)
    handles = [Patch(facecolor=c, edgecolor="#d8d7d3", linewidth=0.5, label=l)
               for c, l in zip(RED_ARM + [NEUTRAL] + BLUE_ARM, LABELS)]
    handles.append(Patch(facecolor="#e5e4e0", hatch="///", edgecolor="#ffffff", label="no estimate"))
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False,
               fontsize=9, labelcolor=TEXT2,
               title="Residual net internal migration rate (per 1,000 population per year)",
               title_fontsize=10)
    fig.suptitle("Net migration by province, residual method — Philippines", fontsize=15,
                 color=TEXT, y=0.97)
    fig.text(0.5, 0.085,
             "Provinces incl. their highly urbanized cities; NCR shown as one unit. "
             "BARMM rates mostly reflect the civil-registration gap (2020 census: 77% registered births vs 96.6% national) — see codebook.",
             ha="center", fontsize=8.5, color=TEXT2)
    plt.tight_layout(rect=[0, 0.11, 1, 0.95])
    out = FIG / "net_migration_province_maps.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
