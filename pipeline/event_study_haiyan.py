"""Demonstration application: a thin event study of Typhoon Haiyan (Nov 2013)
on municipal population growth.

Design: difference-in-differences on annualized census growth rates.
    treated  = municipalities of Leyte, Eastern Samar, Samar, Biliran,
               Southern Leyte + Tacloban City (landfall corridor provinces)
    control  = all other municipalities of the Visayas (Regions VI, VII, VIII
               remainder is none — so VI and VII + NIR provinces)
    outcome  = g(2010-2015) - g(2000-2010)   (within-municipality change in
               annualized growth, %/yr; the 2010-15 window contains Haiyan)
    placebo  = g(2015-2020) - g(2010-2015)   (recovery/return window)

Inference: cluster-bootstrap by province (999 draws). This is deliberately
simple — the dataset is the contribution; the event study demonstrates use.

Output: data/clean/atlas/event_study_haiyan.csv + printed estimates.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"

TREAT_PROVS = ["Leyte", "Eastern Samar", "Samar", "Biliran", "Southern Leyte"]
CONTROL_REGIONS = ["Region VI (Western Visayas)", "Region VII (Central Visayas)",
                   "Negros Island Region (NIR)"]


def ann_growth(p1, p0, years):
    return ((p1 / p0) ** (1 / years) - 1) * 100


def cluster_boot(df, col, n=999, seed=13):
    rng = np.random.default_rng(seed)
    provs = df.province.unique()
    stats = []
    for _ in range(n):
        take = rng.choice(provs, size=len(provs), replace=True)
        sub = pd.concat([df[df.province == p] for p in take])
        t = sub[sub.treated][col].mean() - sub[~sub.treated][col].mean()
        stats.append(t)
    return np.percentile(stats, [2.5, 97.5])


def main() -> None:
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    cp = cp.dropna(subset=["pop2000", "pop2010", "pop2015", "pop2020"])
    treated = cp.province.isin(TREAT_PROVS) | cp.name.str.contains("Tacloban", na=False)
    control = cp.region.isin(CONTROL_REGIONS) | cp.region.str.contains("Eastern Visayas", na=False)
    df = cp[treated | control].copy()
    df["treated"] = treated[df.index]
    # Eastern Visayas non-landfall provinces (none besides the treated five +
    # Tacloban) — the region is fully treated, so controls are VI/VII/NIR.
    df["g0010"] = ann_growth(df.pop2010, df.pop2000, 10.0)
    df["g1015"] = ann_growth(df.pop2015, df.pop2010, 5.25)
    df["g1520"] = ann_growth(df.pop2020, df.pop2015, 4.75)
    df["d_event"] = df.g1015 - df.g0010
    df["d_recovery"] = df.g1520 - df.g1015

    for col, label in (("d_event", "Haiyan window (Δg 2010-15 vs 2000-10)"),
                       ("d_recovery", "recovery window (Δg 2015-20 vs 2010-15)")):
        t = df[df.treated][col].mean()
        c = df[~df.treated][col].mean()
        lo, hi = cluster_boot(df, col)
        print(f"{label}: treated {t:+.3f}, control {c:+.3f}, "
              f"DiD {t - c:+.3f} pp/yr  [95% cluster-bootstrap CI {lo:+.3f}, {hi:+.3f}]  "
              f"(n_treated={df.treated.sum()}, n_control={(~df.treated).sum()})")

    out = df[["psgc10", "name", "province", "region", "treated",
              "g0010", "g1015", "g1520", "d_event", "d_recovery"]].round(3)
    out.to_csv(CLEAN / "atlas" / "event_study_haiyan.csv", index=False)
    print("wrote", CLEAN / "atlas" / "event_study_haiyan.csv")


if __name__ == "__main__":
    main()
