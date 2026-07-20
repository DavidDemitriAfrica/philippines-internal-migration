"""Descriptive atlas tables: rate rankings, and the two event windows the
goal names (Haiyan 2013 / Eastern Visayas; Marawi 2017), described with
census population change and the residual estimates where available.
No modeling — descriptive tables for the paper's atlas section.

Outputs (data/clean/atlas/):
    rates_province_ranked.csv     both periods, all units, ranked
    rates_municipal_ranked.csv    2020-2024, all municipalities
    event_haiyan_eastern_visayas.csv
    event_marawi_lanao_del_sur.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
ATLAS = CLEAN / "atlas"

HAIYAN_PROVS = ["Leyte", "Southern Leyte", "Eastern Samar", "Samar", "Biliran",
                "Tacloban"]  # Tacloban is an HUC unit
MARAWI_PROVS = ["Lanao del Sur", "Lanao del Norte", "Iligan"]


def main() -> None:
    ATLAS.mkdir(parents=True, exist_ok=True)

    prov = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    prov = prov.sort_values(["period", "netmig_rate_per_1000_yr"])
    prov.to_csv(ATLAS / "rates_province_ranked.csv", index=False)

    muni = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    muni.sort_values("netmig_rate_per_1000_yr").to_csv(
        ATLAS / "rates_municipal_ranked.csv", index=False)

    # --- Haiyan: census population change by municipality, Eastern Visayas core
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    ev = cp[cp.province.isin(HAIYAN_PROVS) | cp.name.str.contains("Tacloban", na=False)].copy()
    for a, b, tag in ((2000, 2010, "g_2000_2010"), (2010, 2015, "g_2010_2015"),
                      (2015, 2020, "g_2015_2020")):
        yrs = {2000: 10.0, 2010: 5.25, 2015: 4.75}[a]
        ev[tag] = ((ev[f"pop{b}"] / ev[f"pop{a}"]) ** (1 / yrs) - 1) * 100
    ev = ev.merge(muni[["psgc10", "netmig_rate_per_1000_yr"]].rename(
        columns={"netmig_rate_per_1000_yr": "residual_rate_2020_2024"}), on="psgc10", how="left")
    cols = ["psgc10", "name", "province", "pop2000", "pop2010", "pop2015", "pop2020",
            "g_2000_2010", "g_2010_2015", "g_2015_2020", "residual_rate_2020_2024"]
    ev[cols].round(2).to_csv(ATLAS / "event_haiyan_eastern_visayas.csv", index=False)
    # headline: growth-rate dip 2010-2015 vs baseline in hardest-hit areas
    tac = ev[ev.name.str.contains("Tacloban", na=False)]
    if len(tac):
        t = tac.iloc[0]
        print(f"Tacloban annualized growth %: 2000-10 {t.g_2000_2010:.2f} | "
              f"2010-15 {t.g_2010_2015:.2f} | 2015-20 {t.g_2015_2020:.2f}")
    reg = ev[["g_2000_2010", "g_2010_2015", "g_2015_2020"]].median()
    print("Eastern Visayas core municipalities, median annualized growth %:",
          reg.round(2).to_dict())

    # --- Marawi: same structure
    mw = cp[cp.province.isin(MARAWI_PROVS) | cp.name.str.contains("Marawi|Iligan", na=False)].copy()
    for a, b, tag in ((2000, 2010, "g_2000_2010"), (2010, 2015, "g_2010_2015"),
                      (2015, 2020, "g_2015_2020")):
        yrs = {2000: 10.0, 2010: 5.25, 2015: 4.75}[a]
        mw[tag] = ((mw[f"pop{b}"] / mw[f"pop{a}"]) ** (1 / yrs) - 1) * 100
    mw = mw.merge(muni[["psgc10", "netmig_rate_per_1000_yr"]].rename(
        columns={"netmig_rate_per_1000_yr": "residual_rate_2020_2024"}), on="psgc10", how="left")
    mw[cols].round(2).to_csv(ATLAS / "event_marawi_lanao_del_sur.csv", index=False)
    mar = mw[mw.name.str.contains("Marawi", na=False)]
    if len(mar):
        t = mar.iloc[0]
        print(f"Marawi City pops 2010/2015/2020: {t.pop2010}/{t.pop2015}/{t.pop2020} | "
              f"growth 2015-20 {t.g_2015_2020:.2f}%/yr (siege May-Oct 2017)")
    print("wrote atlas tables to", ATLAS)


if __name__ == "__main__":
    main()
