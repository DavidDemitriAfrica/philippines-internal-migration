"""Event-study suite: difference-in-differences on municipal demographic
outcomes around major shocks, exploiting the 1960-2020 census panel and the
2020-2024 municipal residual.

Design per event (kept deliberately thin — the dataset is the contribution):
    outcome  = change in annualized census growth between the event window and
               the preceding window (pp/yr), or the 2020-2024 residual net
               migration rate for the one post-2020 event
    treated  = municipalities of the named impact provinces
    control  = municipalities of the named comparison provinces/regions,
               excluding other events' impact zones
    estimate = DiD (treated mean − control mean), 95% CI from a cluster
               bootstrap by province (999 draws)

Events:
    Pinatubo 1991    Zambales/Pampanga/Tarlac; Δg(1990-2000 vs 1980-1990)
    Bohol quake 2013 Bohol; Δg(2010-2015 vs 2000-2010); controls exclude
                     Cebu/Leyte (Haiyan/quake contamination)
    Haiyan 2013      landfall corridor; Δg(2010-15 vs 2000-10) and the
                     delayed window Δg(2015-20 vs 2010-15)
    Marawi 2017      Lanao del Sur; Δg(2015-2020 vs 2010-2015); note BARMM
                     census-quality caveats
    Odette 2021      SE Visayas/Siargao landfalls; outcome = residual net
                     migration rate 2020-2024 (level difference vs controls)

Outputs: data/clean/atlas/event_studies_summary.csv,
         figures/event_studies_forest.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN, FIG = ROOT / "data" / "clean", ROOT / "figures"

figstyle.apply()
SURFACE, TEXT, TEXT2 = figstyle.SURFACE, figstyle.INK, figstyle.INK2
BLUE, LINE = figstyle.NAVY, "#d9d9d9"

WINDOW_YEARS = {(1980, 1990): 10.0, (1990, 2000): 10.0, (2000, 2010): 10.0,
                (2010, 2015): 5.25, (2015, 2020): 4.75}

HAIYAN = ["Leyte", "Southern Leyte", "Eastern Samar", "Samar", "Biliran"]

EVENTS = [
    dict(key="pinatubo", label="Mt. Pinatubo eruption (Jun 1991)",
         outcome=("g", (1990, 2000), (1980, 1990)),
         treated_provs=["Zambales", "Pampanga", "Tarlac"],
         control_provs=["Pangasinan", "Nueva Ecija", "Bulacan", "Bataan", "Aurora",
                        "La Union", "Ilocos Sur", "Ilocos Norte", "Nueva Vizcaya"],
         note="ashfall/lahar provinces vs rest of Central/North Luzon"),
    dict(key="bohol_quake", label="Bohol earthquake (Oct 2013)",
         outcome=("g", (2010, 2015), (2000, 2010)),
         treated_provs=["Bohol"],
         control_provs=["Negros Oriental", "Siquijor", "Iloilo", "Capiz", "Aklan",
                        "Antique", "Guimaras", "Negros Occidental"],
         note="controls exclude Cebu and the Haiyan corridor"),
    dict(key="haiyan_immediate", label="Typhoon Haiyan — census window (2010–15)",
         outcome=("g", (2010, 2015), (2000, 2010)),
         treated_provs=HAIYAN,
         control_provs=["Iloilo", "Capiz", "Aklan", "Antique", "Guimaras",
                        "Negros Occidental", "Negros Oriental", "Siquijor", "Bohol"],
         note="landfall corridor; census came 21 months after landfall"),
    dict(key="haiyan_delayed", label="Typhoon Haiyan — delayed window (2015–20)",
         outcome=("g", (2015, 2020), (2010, 2015)),
         treated_provs=HAIYAN,
         control_provs=["Iloilo", "Capiz", "Aklan", "Antique", "Guimaras",
                        "Negros Occidental", "Negros Oriental", "Siquijor", "Bohol"],
         note="the demographic cost arrives after the immediate recovery"),
    dict(key="marawi", label="Marawi siege (May–Oct 2017) †",
         outcome=("g", (2015, 2020), (2010, 2015)),
         treated_provs=["Lanao del Sur"],
         control_provs=["Lanao del Norte", "Misamis Occidental", "Misamis Oriental",
                        "Bukidnon", "Zamboanga del Sur", "Zamboanga del Norte"],
         note="BARMM census-quality caveats apply to treated counts"),
    dict(key="odette", label="Typhoon Odette (Dec 2021)",
         outcome=("resid", None, None),
         treated_provs=["Surigao del Norte", "Dinagat Islands", "Southern Leyte", "Bohol"],
         control_provs=["Agusan del Norte", "Agusan del Sur", "Surigao del Sur",
                        "Misamis Oriental", "Camiguin", "Iloilo", "Capiz", "Aklan",
                        "Antique", "Negros Occidental", "Negros Oriental", "Siquijor"],
         note="outcome = residual net migration rate 2020–24 (level, not change)"),
]


def ann_growth(p1, p0, years):
    with np.errstate(all="ignore"):
        return ((p1 / p0) ** (1 / years) - 1) * 100


def cluster_boot_diff(df, col, n=999, seed=13):
    rng = np.random.default_rng(seed)
    provs = df.province.unique()
    stats = []
    for _ in range(n):
        take = rng.choice(provs, size=len(provs), replace=True)
        sub = pd.concat([df[df.province == p] for p in take])
        t, c = sub[sub.treated][col], sub[~sub.treated][col]
        if t.notna().sum() and c.notna().sum():
            stats.append(t.mean() - c.mean())
    return np.percentile(stats, [2.5, 97.5])


def main() -> None:
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    resid = pd.read_csv(CLEAN / "net_migration_municipal_2020_2024.csv", dtype={"psgc10": str})
    cp = cp.merge(resid[["psgc10", "netmig_rate_per_1000_yr"]], on="psgc10", how="left")

    rows = []
    for ev in EVENTS:
        kind, w1, w0 = ev["outcome"]
        df = cp[cp.province.isin(ev["treated_provs"] + ev["control_provs"])].copy()
        df["treated"] = df.province.isin(ev["treated_provs"])
        if kind == "g":
            a0, b0 = w0
            a1, b1 = w1
            g0 = ann_growth(df[f"pop{b0}"], df[f"pop{a0}"], WINDOW_YEARS[w0])
            g1 = ann_growth(df[f"pop{b1}"], df[f"pop{a1}"], WINDOW_YEARS[w1])
            df["y"] = g1 - g0
            unit = "pp/yr (Δ annualized growth)"
        else:
            df["y"] = df["netmig_rate_per_1000_yr"]
            unit = "per 1,000/yr (residual net migration rate)"
        df = df[df.y.notna() & np.isfinite(df.y)]
        t, c = df[df.treated], df[~df.treated]
        did = t.y.mean() - c.y.mean()
        lo, hi = cluster_boot_diff(df, "y")
        rows.append({"event": ev["label"], "key": ev["key"], "unit": unit,
                     "treated_mean": round(t.y.mean(), 3), "control_mean": round(c.y.mean(), 3),
                     "did": round(did, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
                     "n_treated": len(t), "n_control": len(c), "note": ev["note"]})
        print(f"{ev['label']}: DiD {did:+.3f} [{lo:+.3f}, {hi:+.3f}] "
              f"({unit}; n={len(t)}/{len(c)})")

    out = pd.DataFrame(rows)
    (CLEAN / "atlas").mkdir(exist_ok=True)
    out.to_csv(CLEAN / "atlas" / "event_studies_summary.csv", index=False)

    # forest plot (growth-outcome events share an axis; Odette annotated separately)
    g_rows = out[out.unit.str.startswith("pp/yr")].iloc[::-1]
    o_row = out[out.key == "odette"].iloc[0]
    fig, ax = plt.subplots(figsize=(11.4, 5.6))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    ax.axvline(0, color=LINE, lw=1.2)
    ypos = np.arange(len(g_rows))
    ax.hlines(ypos, g_rows.ci_lo, g_rows.ci_hi, color=BLUE, lw=2.4, zorder=2)
    ax.scatter(g_rows.did, ypos, s=72, color=BLUE, edgecolor=SURFACE, lw=1.4, zorder=3)
    for y, (_, r) in zip(ypos, g_rows.iterrows()):
        ax.annotate(f"{r.did:+.2f}", (r.did, y), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=9, color=TEXT2)
    ax.set_yticks(ypos)
    ax.set_yticklabels(g_rows.event, fontsize=10, color=TEXT)
    ax.set_xlabel("Difference-in-differences: Δ annualized municipal growth, treated − control (pp/yr)",
                  fontsize=9.5, color=TEXT2)
    ax.set_title("Demographic event studies from the census panel\n"
                 "point = DiD estimate; line = 95% cluster-bootstrap CI (by province)",
                 fontsize=12, color=TEXT, loc="left")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=TEXT2)
    ax.grid(True, axis="x", color=figstyle.GRID, lw=0.9, zorder=0)
    fig.text(0.995, 0.045,
             f"Odette 2021 (different outcome — residual net migration 2020–24): "
             f"{o_row.did:+.1f} per 1,000/yr [{o_row.ci_lo:+.1f}, {o_row.ci_hi:+.1f}]",
             ha="right", fontsize=8.5, color=TEXT2)
    fig.text(0.995, 0.005,
             "† positive 'growth' in Lanao del Sur is best read against the BARMM "
             "census-quality caveats (see codebook), not as in-migration to a siege zone",
             ha="right", fontsize=8.5, color=TEXT2)
    plt.tight_layout(rect=[0, 0.08, 1, 0.96])
    fig.savefig(FIG / "event_studies_forest.png", dpi=150, facecolor=SURFACE,
                bbox_inches="tight")
    import shutil
    shutil.copy(FIG / "event_studies_forest.png", ROOT / "docs" / "assets" / "event_studies_forest.png")
    print("wrote", FIG / "event_studies_forest.png")


if __name__ == "__main__":
    main()
