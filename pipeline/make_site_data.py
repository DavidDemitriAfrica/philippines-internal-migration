"""Build docs/municipal.geojson — the single data file behind both site maps.

Per municipality: the 2020-2024 residual net-migration estimate (rate, net
moves, populations, caveat flag) and, for the time-lapse, relative growth for
each census window 1960-2024 (annualized municipal growth minus annualized
national growth, pp/yr).

The national growth rate is computed from PSA's published national census
counts, not from panel column sums: early censuses are missing rows for
municipalities that did not yet exist, and a sum over available rows would
misstate the national rate those municipalities are compared against
(1960-70 comes out 3.6%/yr instead of the true 3.0).
"""
from __future__ import annotations

import glob
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
NIR = {"06045": "18045", "07046": "18046", "07061": "18061"}

# PSA national census counts (persons), census reference dates
NATIONAL = {1960: 27_087_685, 1970: 36_684_486, 1980: 48_098_460,
            1990: 60_703_206, 2000: 76_506_928, 2010: 92_337_852,
            2015: 100_981_437, 2020: 109_035_343, 2024: 112_729_484}
WINDOWS = [(1960, 1970, 10.19), (1970, 1980, 9.99), (1980, 1990, 10.0),
           (1990, 2000, 10.0), (2000, 2010, 10.0), (2010, 2015, 5.25),
           (2015, 2020, 4.75), (2020, 2024, 4.17)]


def main() -> None:
    parts = [gpd.read_file(f) for f in glob.glob(str(ROOT / "data/raw/boundaries/municities/*.json"))]
    g = pd.concat(parts, ignore_index=True)
    g["psgc10"] = g["adm3_psgc"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    pref = g.psgc10.str[:5].map(NIR)
    g.loc[pref.notna(), "psgc10"] = pref[pref.notna()] + g.loc[pref.notna(), "psgc10"].str[5:]
    # five municipalities have empty geometry in the hires boundary files
    # (San Pedro, Kalayaan-Palawan, Pikit, Limasawa, Jala-Jala); fill them
    # from the medres patch files (logged in provenance.jsonl)
    empty = g.geometry.isna() | g.geometry.is_empty
    if empty.any():
        patch = pd.concat(
            [gpd.read_file(f) for f in
             glob.glob(str(ROOT / "data/raw/boundaries/municities_medres_patch/*.json"))],
            ignore_index=True)
        patch["psgc10"] = (patch["adm3_psgc"].astype(str)
                           .str.replace(r"\.0$", "", regex=True).str.zfill(10))
        fixes = patch.set_index("psgc10").geometry
        g.loc[empty, "geometry"] = g.loc[empty, "psgc10"].map(fixes)
        still = g.geometry.isna() | g.geometry.is_empty
        print(f"patched {int(empty.sum() - still.sum())} empty geometries; "
              f"dropping {int(still.sum())} still-empty rows")
        g = g[~still]
    gg = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326")
    simp = gg.geometry.simplify(0.002, preserve_topology=True)
    bad = simp.is_empty | simp.isna()
    simp[bad] = gg.geometry[bad]
    gg = gg.set_geometry(simp)

    r = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    cp = cp.merge(r[["psgc10", "pop2024"]], on="psgc10", how="left", suffixes=("", "_r"))

    for a, b, yrs in WINDOWS:
        with np.errstate(all="ignore"):
            gm = ((cp[f"pop{b}"] / cp[f"pop{a}"]) ** (1 / yrs) - 1) * 100
        nat = ((NATIONAL[b] / NATIONAL[a]) ** (1 / yrs) - 1) * 100
        cp[f"w{a}"] = (gm - nat).round(2)

    m = gg[["psgc10", "adm3_en", "geometry"]].merge(
        r[["psgc10", "name", "province", "netmig_rate_per_1000_yr",
           "net_migration", "pop2020", "pop2024", "flag"]], on="psgc10", how="left")
    m = m.merge(cp[["psgc10"] + [f"w{a}" for a, _, _ in WINDOWS]], on="psgc10", how="left")
    m["name"] = m["name"].fillna(m["adm3_en"])
    m = m.drop(columns=["adm3_en"]).rename(columns={"netmig_rate_per_1000_yr": "rate"})

    out = ROOT / "docs" / "municipal.geojson"
    m.to_file(out, driver="GeoJSON", COORDINATE_PRECISION=4)
    print("wrote", out, f"({out.stat().st_size // 1024} KB, {len(m)} features)")

    # dissolved metro outlines for the map's jump-to feature: the outline
    # follows the actual member municipalities, not a bounding box
    cent = m.geometry.representative_point()
    prov = m.province.fillna("")
    metros = {
        "Metro Manila": m[prov.str.contains("National Capital")],
        "Metro Cebu": m[(prov == "Cebu") & cent.x.between(123.55, 124.15)
                        & cent.y.between(10.10, 10.70)],
        "Metro Davao": m[prov.str.startswith("Davao") & cent.x.between(125.10, 125.80)
                         & cent.y.between(6.80, 7.50)],
    }
    feats = gpd.GeoDataFrame(
        {"name": list(metros)},
        geometry=[v.geometry.union_all().buffer(0) for v in metros.values()],
        crs="EPSG:4326")
    mout = ROOT / "docs" / "metros.geojson"
    feats.to_file(mout, driver="GeoJSON", COORDINATE_PRECISION=4)
    print("wrote", mout, f"({mout.stat().st_size // 1024} KB)",
          {k: len(v) for k, v in metros.items()})
    for a, b, yrs in WINDOWS:
        nat = ((NATIONAL[b] / NATIONAL[a]) ** (1 / yrs) - 1) * 100
        print(f"  {a}-{b}: national {nat:.2f}%/yr, "
              f"{m[f'w{a}'].notna().sum()} municipalities with values")

    # per-window thumbnails: the small-multiple buttons that drive the
    # history map, same bins and palette as the map itself
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    RED_ARM = ["#6b1414", "#a11d1d", "#e04234", "#f79b8e"]
    NEUTRAL = "#f0efec"
    BLUE_ARM = ["#74b3f7", "#2a7ff0", "#0f5ec4", "#093a80"]
    BINS = [-np.inf, -3, -1.5, -0.5, -0.15, 0.15, 0.5, 1.5, 3, np.inf]
    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)
    tdir = ROOT / "docs" / "assets" / "thumbs"
    tdir.mkdir(parents=True, exist_ok=True)
    # frame on the main archipelago: Kalayaan (Spratlys) sits 400 km west and
    # would shrink every thumbnail if included in the limits
    b = m[m.psgc10 != "1705321000"].total_bounds
    for a, _, _ in WINDOWS:
        fig, ax = plt.subplots(figsize=(1.05, 1.7), dpi=120)
        ax.set_axis_off()
        m.plot(ax=ax, column=f"w{a}", cmap=cmap, norm=norm, linewidth=0,
               missing_kwds={"color": "#e5e4e0", "linewidth": 0})
        ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        fig.savefig(tdir / f"w{a}.png", transparent=True)
        plt.close(fig)
    print("wrote", tdir, f"({len(WINDOWS)} thumbnails)")


if __name__ == "__main__":
    main()
