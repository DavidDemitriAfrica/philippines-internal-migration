"""Provincial populations for ALL censuses 1990-2015 — including the
mid-decade 1995 POPCEN and 2007 census that exist nowhere reachable at
municipal level — from Philippine Statistical Yearbook Table 1.1.

The 1995 and 2007 censuses split the 1990-2000 and 2000-2010 decades into
four shorter windows (1990-95, 1995-2000, 2000-07, 2007-10) at province
resolution. Rendered as a static four-panel figure for the site; values are
verified against our municipal-panel folds on the overlapping censuses
(2000/2010/2015).

Outputs: data/interim/psy_prov_pops.csv, figures/growth_windows_prov.png
(+ docs/assets copy)
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import normalize_name, strip_parens, CITY_HOST_PROVINCE  # noqa: E402
import figstyle  # noqa: E402

figstyle.apply()

ROOT = Path(__file__).resolve().parent.parent
RAW, INTERIM, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "interim", ROOT / "data" / "clean"
SRC = RAW / "census" / "psy_table1.1_1990_2015.xlsx"

YEAR_COLS = {2015: 1, 2010: 3, 2007: 5, 2000: 7, 1995: 9, 1990: 10}
# census reference dates -> interval lengths in years
INTERVALS = [("w9095", 1990, 1995, 5.34), ("w9500", 1995, 2000, 4.66),
             ("w0007", 2000, 2007, 7.25), ("w0710", 2007, 2010, 2.75)]
PANEL_LABELS = {"w9095": "1990 – 1995", "w9500": "1995 – 2000",
                "w0007": "2000 – 2007", "w0710": "2007 – 2010"}
# national totals as printed in the same table (Philippines row); using the
# publication's own totals keeps the anchor consistent with its footnotes
NATIONAL = {1990: 60_703_206, 1995: 68_616_536, 2000: 76_504_077,
            2007: 88_548_366, 2010: 92_335_113, 2015: 100_979_303}
NIR = {"06045": "18045", "07046": "18046", "07061": "18061"}


def parse_psy() -> pd.DataFrame:
    """Names wrap across physical rows in both directions (values sometimes on
    the first physical row, sometimes on the continuation). Group rows by
    parenthesis balance: a name-unit is complete when its parens close; take
    whichever row in the unit carries the values."""
    df = pd.read_excel(SRC, sheet_name=0, header=None)
    rows = []
    parts, unit_vals, depth = [], None, 0

    def flush():
        nonlocal parts, unit_vals, depth
        if parts and unit_vals is not None:
            rows.append({"name_src": " ".join(parts), **unit_vals})
        parts, unit_vals, depth = [], None, 0

    for _, r in df.iterrows():
        name = r[0]
        if not isinstance(name, str) or not name.strip():
            flush()
            continue
        name = name.strip().rstrip("*")
        if name.upper().startswith(("TABLE", "CENSUS", "REGION AND", "PHILIPPINES",
                                    "NOTE", "SOURCE", "A1", "A2", "A3", "B1", "B2",
                                    "B3", "C ", "FOR ", "DETAILS")):
            flush()
            continue
        vals = {}
        for yr, ci in YEAR_COLS.items():
            v = r[ci]
            vals[yr] = int(v) if isinstance(v, (int, float)) and not pd.isna(v) and v > 1000 else None
        ok = sum(v is not None for v in vals.values()) >= 4
        if depth == 0 and not name.startswith("("):
            flush()
        parts.append(name)
        depth += name.count("(") - name.count(")")
        if ok and unit_vals is None:
            unit_vals = vals
        if depth <= 0 and unit_vals is not None:
            flush()
    flush()
    return pd.DataFrame(rows)


def main() -> None:
    psy = parse_psy()
    import re as _re
    def keyof(s):
        s = str(s).replace("\n", " ")
        s = s.split("(")[0]                 # drop "(excluding …" even if unbalanced
        s = _re.sub(r"[)\d]", " ", s)       # stray ')' and footnote digits anywhere
        return normalize_name(strip_parens(s))
    psy["key"] = psy.name_src.map(keyof)
    psy = psy[psy.key != ""]

    # classify: region rows (drop except NCR), city rows (fold to host province)
    is_region = psy.name_src.str.contains(
        r"Region|CAR\b|Cordillera|ARMM|Mindanao \(|CARAGA|Caraga|MIMAROPA|National Capital",
        regex=True) | psy.name_src.str.match(r"^\s*[IVX]+(-[AB])?\s*[–-]")
    ncr = psy[psy.key.str.contains("national capital")]
    body = psy[~is_region].copy()

    city = body.key.str.contains("city")
    body.loc[city, "key"] = body.loc[city, "key"].map(
        lambda k: CITY_HOST_PROVINCE.get(k, k))
    # NCR cities fold into the NCR unit
    body.loc[body.key.isin([  # any remaining "x city" keys inside NCR list
        k for k in body.key.unique() if k.endswith("city") or "pateros" in k]),
        "key"] = "__ncr__"
    ncr_row = {"key": "national capital region"}
    for yr in YEAR_COLS:
        ncr_row[yr] = int(ncr.iloc[0][yr]) if len(ncr) else \
            int(body.loc[body.key == "__ncr__", yr].sum())
    body = body[body.key != "__ncr__"]
    # NaN must propagate: a province+city sum with a missing year is missing,
    # not understated
    prov = (body.groupby("key")[list(YEAR_COLS)]
            .apply(lambda g: g.sum(skipna=False)).reset_index())
    prov = pd.concat([prov, pd.DataFrame([ncr_row])], ignore_index=True)

    # verification vs municipal-panel folds on 2000/2010/2015
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    def geo_prov(row):
        nm = normalize_name(str(row["name"]))
        host = CITY_HOST_PROVINCE.get(nm)
        if host:
            return host
        p = normalize_name(strip_parens(str(row.province)))
        if "national capital region" in p:
            return "national capital region"
        if p in ("maguindanao del norte", "maguindanao del sur"):
            return "maguindanao"
        if "bangsamoro" in p:
            return "cotabato"
        return p
    cp["geo"] = cp.apply(geo_prov, axis=1)
    fold = cp.groupby("geo")[["pop2000", "pop2010", "pop2015"]].sum(min_count=1)
    j = prov.set_index("key").join(fold, how="inner")
    for yr, col in ((2000, "pop2000"), (2010, "pop2010"), (2015, "pop2015")):
        d = (j[yr] - j[col]).abs()
        bad = d[d > max(500, 0)].sort_values(ascending=False)
        print(f"{yr}: {len(j) - len(bad)}/{len(j)} provinces match panel folds "
              f"(tolerance 500); worst: {dict(bad.head(3).astype(int))}")
    print("unmatched PSY keys:", sorted(set(prov.key) - set(fold.index))[:8])

    # relative-growth windows
    for w, a, b, yrs in INTERVALS:
        gm = ((prov[b] / prov[a]) ** (1 / yrs) - 1) * 100
        gn = ((NATIONAL[b] / NATIONAL[a]) ** (1 / yrs) - 1) * 100
        prov[w] = (gm - gn).round(2)
    INTERIM.mkdir(exist_ok=True)
    prov.to_csv(INTERIM / "psy_prov_pops.csv", index=False)

    # province polygons (dissolved; NCR one unit), attach windows
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/provdists-region-*.json"))
             or glob.glob(str(ROOT / "data/raw/boundaries/provdists-region-*.json"))]
    if not parts:
        parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/*.json"))
                 if "provdists-region" in f]
    g = pd.concat(parts, ignore_index=True)
    g["prov5"] = g["adm2_psgc"].astype(str).str.zfill(10).str[:5].replace(
        {**NIR, "09901": "19007", "19099": "12047"})
    g.loc[g.prov5.str.startswith("13"), "prov5"] = "13NCR"
    g = g.dissolve(by="prov5", as_index=False)
    provs_reg = pd.read_csv(INTERIM / "psgc_provinces.csv", dtype=str)
    name_by5 = dict(zip(provs_reg.prov_code, provs_reg.province))
    def poly_key(p5, adm2en):
        if p5 == "13NCR":
            return "national capital region"
        nm = name_by5.get(p5, adm2en)
        k = normalize_name(strip_parens(str(nm)))
        return {"maguindanao del norte": "maguindanao", "maguindanao del sur": "maguindanao",
                "davao de oro": "compostela valley",
                # created 2013 from Davao del Sur — PSY 1990-2015 vintage keeps them together
                "davao occidental": "davao del sur"}.get(k, k)
    g["key"] = [poly_key(p, e) for p, e in zip(g.prov5, g.adm2_en)]
    # PSY-era names: Davao de Oro appears as Compostela Valley
    prov["key"] = prov.key.replace({"davao de oro": "compostela valley"})
    gg = g.merge(prov[["key"] + [w for w, *_ in INTERVALS]], on="key", how="left")
    gg = gg.dissolve(by="key", as_index=False, aggfunc="first")  # merge split provs
    gg["name"] = gg.key.str.title()
    keep = gg[["name", "geometry"] + [w for w, *_ in INTERVALS]]
    simp = keep.geometry.simplify(0.004, preserve_topology=True)
    bad = simp.is_empty | simp.isna()
    simp[bad] = keep.geometry[bad]
    keep = gpd.GeoDataFrame(keep.set_geometry(simp), crs="EPSG:4326")
    missing = keep[keep.w9095.isna()]
    if len(missing):
        print("polygons without PSY values:", list(missing.name)[:8])

    # four-panel figure, same palette and bins as the site's time-lapse
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    RED_ARM = ["#6b1414", "#a11d1d", "#e04234", "#f79b8e"]
    NEUTRAL = "#f0efec"
    BLUE_ARM = ["#74b3f7", "#2a7ff0", "#0f5ec4", "#093a80"]
    BINS = [-np.inf, -3, -1.5, -0.5, -0.15, 0.15, 0.5, 1.5, 3, np.inf]
    LABELS = ["< −3", "−3 to −1.5", "−1.5 to −0.5", "−0.5 to −0.15", "≈ national",
              "0.15 to 0.5", "0.5 to 1.5", "1.5 to 3", "> 3"]
    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)

    fig, axes = plt.subplots(1, 4, figsize=(13.6, 5.6))
    fig.patch.set_facecolor(figstyle.SURFACE)
    for ax, (w, a, b, _) in zip(axes, INTERVALS):
        ax.set_facecolor(figstyle.SURFACE); ax.set_axis_off()
        keep.plot(ax=ax, column=w, cmap=cmap, norm=norm,
                  edgecolor="#ffffff", linewidth=0.5,
                  missing_kwds={"color": "#e5e4e0", "edgecolor": "#ffffff",
                                "linewidth": 0.5})
        ax.set_title(PANEL_LABELS[w], fontsize=13, color=figstyle.INK, family="serif")
    handles = [Patch(facecolor=c, edgecolor="#d8d7d3", linewidth=0.4, label=l)
               for c, l in zip(RED_ARM + [NEUTRAL] + BLUE_ARM, LABELS)]
    handles.append(Patch(facecolor="#e5e4e0", label="no data"))
    fig.legend(handles=handles, loc="lower center", ncol=10, fontsize=8,
               frameon=False, labelcolor=figstyle.INK2,
               title="province growth minus national growth, percentage points per year",
               title_fontsize=9)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.12, wspace=0.02)
    out = ROOT / "figures" / "growth_windows_prov.png"
    fig.savefig(out, dpi=150, facecolor=figstyle.SURFACE)
    plt.close(fig)
    import shutil
    (ROOT / "docs" / "assets").mkdir(exist_ok=True)
    shutil.copy(out, ROOT / "docs" / "assets" / "growth_windows_prov.png")
    print("wrote", out, f"({out.stat().st_size // 1024} KB, {len(keep)} provinces)")


if __name__ == "__main__":
    main()
