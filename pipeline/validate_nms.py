"""Validation: residual net migration (2015-2020, province/HUC aggregated to
regions) vs the 2018 National Migration Survey's inter-regional net period
migration (Table 4 of the NMS results release; persons who moved in the five
years before the 2018 survey, in thousands).

Periods differ (2013-2018 vs 2015-2020) and the NMS is a sample survey —
this is a directional/rank consistency check, not a levels test. Output:
data/clean/validation_region_nms.csv, figures/validation_nms_scatter.png,
correlations printed and written into the CSV header comment.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG, RAWV = ROOT / "data" / "clean", ROOT / "figures", ROOT / "data" / "raw" / "validation"

figstyle.apply()
SURFACE, TEXT, TEXT2, BLUE = figstyle.SURFACE, figstyle.INK, figstyle.INK2, figstyle.NAVY

# keyword -> canonical region key (2018 boundaries)
REGION_KEYS = [
    ("national capital", "NCR"), ("cordillera", "CAR"), ("ilocos", "R01"),
    ("cagayan valley", "R02"), ("central luzon", "R03"), ("calabarzon", "R4A"),
    ("mimaropa", "MIM"), ("bicol", "R05"), ("western visayas", "R06"),
    ("central visayas", "R07"), ("eastern visayas", "R08"), ("zamboanga", "R09"),
    ("northern mindanao", "R10"), ("davao", "R11"), ("soccsksargen", "R12"),
    ("caraga", "R13"), ("armm", "BARMM"), ("bangsamoro", "BARMM"),
    ("negros island", "NIR"),
]


def region_key(name: str) -> str | None:
    s = str(name).lower()
    for kw, key in REGION_KEYS:
        if kw in s:
            return key
    return None


def load_nms() -> pd.DataFrame:
    df = pd.read_excel(RAWV / "nms2018_migrant_destinations.xlsx", sheet_name="PR3_Table 4", header=None)
    rows = []
    for _, r in df.iterrows():
        key = region_key(r[0])
        if key and pd.notna(r[4]):
            # source table mislabels Eastern Visayas as "VII"; keyword match handles it
            rows.append({"region_key": key, "nms_net_2013_2018": float(r[4]) * 1000})
    return pd.DataFrame(rows)


def load_residual_regional() -> pd.DataFrame:
    r = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    r = r[(r.period == "2015-2020") & r.net_migration.notna()].copy()
    r["region_key"] = r.region.map(region_key)
    # NIR provinces back to 2018 regions: Neg. Occidental & Bacolod -> R06,
    # Neg. Oriental & Siquijor -> R07
    to_r06 = r.unit_name.str.contains("Negros Occidental|Bacolod", case=False, na=False)
    to_r07 = r.unit_name.str.contains("Negros Oriental|Siquijor", case=False, na=False)
    r.loc[to_r06, "region_key"] = "R06"
    r.loc[to_r07, "region_key"] = "R07"
    g = r.groupby("region_key")["net_migration"].sum().rename("residual_net_2015_2020")
    return g.reset_index()


def load_census_inmovers() -> pd.DataFrame:
    """2020 CPH SR Table B: per-region household population 5+ whose residence
    in 2015 was a DIFFERENT PROVINCE (gross in-movers, 2015-2020)."""
    df = pd.read_excel(ROOT / "data/raw/census/2020cph_migration_sr_tables.xlsx",
                       sheet_name="Table B", header=None)
    rows = []
    for _, r in df.iterrows():
        key = region_key(r[0])
        if key and pd.notna(r[4]) and str(r[0]).strip().upper() != "PHILIPPINES":
            rows.append({"region_key": key, "census_inmovers_diffprov": float(r[4]),
                         "census_hhpop5plus": float(r[1])})
    return pd.DataFrame(rows)


def main() -> None:
    nms = load_nms()
    res = load_residual_regional()
    j = nms.merge(res, on="region_key", how="inner")
    j = j.merge(load_census_inmovers(), on="region_key", how="left")
    # de-mean the residual: its national sum absorbs closure error (intl
    # migration + registration incompleteness); NMS nets sum to ~0 by design
    j["residual_net_demeaned"] = j.residual_net_2015_2020 - j.residual_net_2015_2020.mean()
    pear = np.corrcoef(j.nms_net_2013_2018, j.residual_net_2015_2020)[0, 1]
    pear_dm = np.corrcoef(j.nms_net_2013_2018, j.residual_net_demeaned)[0, 1]
    rho = pd.Series(j.nms_net_2013_2018).rank().corr(pd.Series(j.residual_net_2015_2020).rank())
    print(f"n={len(j)} regions; NMS net vs residual net: Pearson r={pear:.3f} "
          f"(demeaned {pear_dm:.3f}); Spearman rho={rho:.3f}")
    print(f"NMS net sum = {j.nms_net_2013_2018.sum():,.0f} (internal nets should sum to ~0 — "
          "origin-based surveys under-capture out-migrants; see paper §4)")
    # complementary check: census gross in-mover RATE vs residual net rate
    sub = j.dropna(subset=["census_inmovers_diffprov"])
    in_rate = sub.census_inmovers_diffprov / sub.census_hhpop5plus
    # residual rate needs region pops; counts suffice for rank comparison
    rho_in = in_rate.rank().corr(sub.residual_net_demeaned.rank())
    r_in = np.corrcoef(in_rate, sub.residual_net_demeaned)[0, 1]
    print(f"census in-mover share vs residual net (rank): rho={rho_in:.3f}, r={r_in:.3f}")
    j.to_csv(CLEAN / "validation_region_nms.csv", index=False)

    # reliability: cross-period persistence of unit rates (structural flows
    # like suburbanization should persist between 2015-2020 and 2020-2024)
    r_all = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    piv = r_all.pivot_table(index="unit_id", columns="period",
                            values="netmig_rate_per_1000_yr", aggfunc="first").dropna()
    pers = np.corrcoef(piv["2015-2020"], piv["2020-2024"])[0, 1]
    pers_rho = piv["2015-2020"].rank().corr(piv["2020-2024"].rank())
    print(f"cross-period persistence of unit rates (n={len(piv)}): r={pers:.3f}, rho={pers_rho:.3f}")

    # proxy test on the SAME window: mayoral-vote growth 2022->2025 vs
    # municipal residual rate 2020-2024
    try:
        vm = pd.read_csv(CLEAN / "proxy_mayor_votes_municipal.csv", dtype={"psgc10": str})
        mm = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
        z = vm.merge(mm[["psgc10", "netmig_rate_per_1000_yr"]], on="psgc10").dropna(
            subset=["mayor_votes_2022", "mayor_votes_2025", "netmig_rate_per_1000_yr"])
        gv = np.log(z.mayor_votes_2025.clip(lower=1) / z.mayor_votes_2022.clip(lower=1))
        rr = np.corrcoef(gv, z.netmig_rate_per_1000_yr)[0, 1]
        print(f"proxy same-window test: d(log mayor votes 22->25) vs municipal residual rate "
              f"20-24: r={rr:.3f} (n={len(z)})")
    except FileNotFoundError:
        pass

    fig, ax = plt.subplots(figsize=(10.2, 6.4))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    lim = max(abs(j.nms_net_2013_2018).max(), abs(j.residual_net_demeaned).max()) * 1.15
    ax.axhline(0, color="#d8d7d3", lw=1, zorder=1)
    ax.axvline(0, color="#d8d7d3", lw=1, zorder=1)
    ax.plot([-lim, lim], [-lim, lim], color="#d8d7d3", lw=1, ls="--", zorder=1)
    ax.scatter(j.nms_net_2013_2018, j.residual_net_demeaned, s=64, color=BLUE,
               edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for _, row in j.iterrows():
        if abs(row.nms_net_2013_2018) > 60000 or abs(row.residual_net_demeaned) > 150000:
            ax.annotate(row.region_key, (row.nms_net_2013_2018, row.residual_net_demeaned),
                        textcoords="offset points", xytext=(7, 4), fontsize=9, color=TEXT2)
    ax.set_xlabel("NMS 2018: net inter-regional migrants, 2013–2018 (persons)", color=TEXT2)
    ax.set_ylabel("Residual net migration 2015–2020, demeaned (persons)", color=TEXT2)
    ax.set_title("Residual estimates vs. 2018 National Migration Survey\n"
                 f"17 regions — Pearson r = {pear_dm:.2f}, Spearman ρ = {rho:.2f}",
                 color=TEXT, fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#d8d7d3")
    ax.tick_params(colors=TEXT2)
    ax.grid(True, color="#efeeea", lw=0.7, zorder=0)
    fig.text(0.5, 0.015, "Different windows (2013–2018 vs 2015–2020) and instruments (survey recall vs census+registration residual).",
             ha="center", fontsize=8, color=TEXT2)
    fig.savefig(FIG / "validation_nms_scatter.png", dpi=150, facecolor=SURFACE, bbox_inches="tight")
    import shutil
    shutil.copy(FIG / "validation_nms_scatter.png", ROOT / "docs" / "assets" / "validation_nms_scatter.png")
    print("wrote", FIG / "validation_nms_scatter.png")


if __name__ == "__main__":
    main()
