"""One-file version of the dataset: data/clean/municipal_master.csv.

One row per city/municipality (1,642), joining the pieces most users want
without having to merge anything themselves: identity (PSGC code, names,
province, region, class), the eight census populations 1960-2020, the 2024
count, registered births and deaths per year 2017-2024, and the 2020-2024
residual net-migration estimate with its caveat flag.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"


def main() -> None:
    mun = pd.read_csv(CLEAN / "municipalities.csv", dtype={"psgc10": str})
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    nm = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    vs = pd.read_csv(CLEAN / "vital_statistics_municipal.csv", dtype={"psgc10": str})

    pops = [c for c in cp.columns if c.startswith("pop")]
    wide = vs.pivot_table(index="psgc10", columns="year",
                          values=["births", "deaths"], aggfunc="first")
    wide.columns = [f"{v}_{y}" for v, y in wide.columns]

    m = (mun[["psgc10", "name", "level", "city_class", "income_class",
              "province", "region"]]
         .merge(cp[["psgc10"] + pops], on="psgc10", how="left")
         .merge(nm[["psgc10", "pop2024", "net_migration",
                    "netmig_rate_per_1000_yr", "flag"]], on="psgc10", how="left")
         .merge(wide, on="psgc10", how="left"))

    out = CLEAN / "municipal_master.csv"
    m.to_csv(out, index=False)
    print(f"wrote {out} ({len(m)} rows, {len(m.columns)} columns)")
    print("estimates:", m.netmig_rate_per_1000_yr.notna().sum(),
          "| 1960 pops:", m.pop1960.notna().sum(),
          "| 2017-2024 births cols:", sum(c.startswith('births') for c in m.columns))


if __name__ == "__main__":
    main()
