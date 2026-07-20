"""Build the electoral-turnout proxy panel from OpenHalalan vote counts.

Proxy: total MAYOR votes cast per city/municipality per cycle (2016, 2019,
2022, 2025). Mayoral races are contested in virtually every locality and every
cycle (including midterms), so their locality vote total ≈ ballots cast there
— a turnout-dependent but municipality-resolved, higher-frequency signal of
adult-population change between censuses. 2013 is excluded (88% coverage,
partial offices).

Output: data/interim/votes_proxy_muni.csv, then joined/PSGC-resolved into
data/clean/proxy_mayor_votes_municipal.csv by build_proxy().
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, INTERIM, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "interim", ROOT / "data" / "clean"
SRC = RAW / "openhalalan" / "NLE_Vote_Counts_2013-2025.csv.gz"


SRC_URL = ("https://raw.githubusercontent.com/RobertRLeung/OpenHalalan/main/"
           "data/output/NLE_Vote_Counts_2013-2025.csv.gz")


def ensure_source() -> None:
    """The compiled OpenHalalan dataset is not committed here (it is theirs to
    distribute); fetch from the canonical repo on first run."""
    if SRC.exists():
        return
    import urllib.request
    SRC.parent.mkdir(parents=True, exist_ok=True)
    print("downloading OpenHalalan vote counts from canonical repo…")
    urllib.request.urlretrieve(SRC_URL, SRC)


def main() -> None:
    ensure_source()
    df = pd.read_csv(SRC, usecols=["year", "region", "province", "city", "position",
                                   "votes", "is_geographic"])
    df = df[(df.year >= 2016) & df.is_geographic & (df.position == "MAYOR")]
    g = (df.groupby(["year", "region", "province", "city"])["votes"]
         .sum().reset_index().rename(columns={"votes": "mayor_votes"}))
    # resolve to PSGC: OpenHalalan names are canonical caps; province context works
    g = g.rename(columns={"city": "name_src", "province": "province_src"})
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype={"psgc10": str})
    res = resolve(g, munis)
    n_un = (res.match_method == "UNRESOLVED").sum()
    print(f"rows: {len(res)}  unresolved: {n_un}")
    if n_un:
        bad = res[res.match_method == "UNRESOLVED"]
        print(bad.groupby(["name_src", "province_src"]).size().sort_values(ascending=False).head(30).to_string())
    res.to_csv(INTERIM / "votes_proxy_muni.csv", index=False)

    ok = res[res.match_method != "UNRESOLVED"]
    piv = ok.pivot_table(index="psgc10", columns="year", values="mayor_votes", aggfunc="sum")
    piv.columns = [f"mayor_votes_{c}" for c in piv.columns]
    m = munis[["psgc10", "name", "province", "region"]]
    out = m.merge(piv.reset_index(), on="psgc10", how="inner")
    CLEAN.mkdir(parents=True, exist_ok=True)
    out.to_csv(CLEAN / "proxy_mayor_votes_municipal.csv", index=False)
    print("clean proxy rows:", len(out))

    # quick internal validation: cross-sectional correlation with census pops
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    j = out.merge(cp[["psgc10", "pop2015", "pop2020"]], on="psgc10")
    import numpy as np
    for vc, pc in [("mayor_votes_2016", "pop2015"), ("mayor_votes_2019", "pop2020"),
                   ("mayor_votes_2022", "pop2020")]:
        sub = j[[vc, pc]].dropna()
        r = np.corrcoef(np.log(sub[vc].clip(lower=1)), np.log(sub[pc]))[0, 1]
        print(f"log-log corr {vc} vs {pc}: {r:.3f}  (n={len(sub)})")
    # growth-on-growth (the real test): vote growth 2016->2022 vs pop growth 2015->2020
    sub = j[["mayor_votes_2016", "mayor_votes_2022", "pop2015", "pop2020"]].dropna()
    gv = np.log(sub.mayor_votes_2022 / sub.mayor_votes_2016)
    gp = np.log(sub.pop2020 / sub.pop2015)
    r = np.corrcoef(gv, gp)[0, 1]
    print(f"growth corr d(log votes 16->22) vs d(log pop 15->20): {r:.3f}  (n={len(sub)})")


if __name__ == "__main__":
    main()
