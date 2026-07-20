"""Assemble clean dataset files and compute residual net migration.

Units follow PSA statistical convention ("province or HUC"): 82 provinces
(HUCs excluded), HUCs and NCR cities/municipality as own units, plus the two
chartered cities outside any province (City of Isabela, City of Cotabato) and
the BARMM Special Geographic Area.

Residual method:
    NetMig(t0->t1) = [P(t1) - P(t0)] - [B(t0..t1) - D(t0..t1)]
Births/deaths between census reference dates are estimated from annual
REGISTERED counts with uniform within-year allocation (documented limitation;
monthly tables exist for future refinement):
    2015-08-01 -> 2020-05-01 and 2020-05-01 -> 2024-07-01.

Vital statistics assembly per unit-year:
    2017-2024: aggregated from the municipal panel (complete, incl. City of
               Cotabato); 2018 births hole filled from provincial tables.
    2013-2016: OpenSTAT provincial tables (no City of Cotabato row -> its
               2015-2020 residual is flagged not-computable).

Boundary handling (documented in data/clean/psgc_changes.csv):
  * 2015-2020 uses ORIGINAL-boundary census pops (2020 CPH Table B aggregated)
    with original-coding VS. Maguindanao computed only as the undivided
    combined unit (VS never split).
  * 2020-2024 uses Table A 2024 RESTATED pops (2024 boundaries). Units whose
    VS coding breaks mid-period get synthetic combined rows:
    Makati+Taguig (EMBO transfer, 2023), Cotabato+SGA (63 barangays moved to
    BARMM SGA), Maguindanao del Norte+del Sur (+ never-split VS).
  * BARMM units flagged: civil-registration coverage there is far below
    the national rate (PSA 2020 CPH: 77% vs 96.6% with registered births),
    so the residual mostly measures the registration gap.

Outputs (data/clean/): municipalities.csv, population_census_municipal.csv,
vital_statistics_municipal.csv, net_migration_province.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import normalize_name, strip_parens  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, INTERIM, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "interim", ROOT / "data" / "clean"

CENSUS_DATES = {2015: "2015-08-01", 2020: "2020-05-01", 2024: "2024-07-01"}

ISABELA_CITY = "0990101000"
COTABATO_CITY = "1908703000"
SGA_PREFIX = "19999"
SGA_UNIT = "19999"

BARMM_FLAG = ("BARMM: civil registration coverage is far below national (2020 "
              "census: 77% of persons had a registered birth vs 96.6% "
              "nationally, PSA); unregistered births read as in-migration, so "
              "do not interpret this residual as migration")


def year_fractions(start: str, end: str) -> dict[int, float]:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = {}
    for yr in range(s.year, e.year + 1):
        y0, y1 = pd.Timestamp(f"{yr}-01-01"), pd.Timestamp(f"{yr + 1}-01-01")
        lo, hi = max(s, y0), min(e, y1)
        if hi > lo:
            out[yr] = (hi - lo).days / (y1 - y0).days
    return out


def load_register():
    m = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype=str)
    provs = pd.read_csv(INTERIM / "psgc_provinces.csv", dtype=str)
    m["is_own_unit"] = ((m.city_class == "HUC")
                        | (m.region == "National Capital Region (NCR)")
                        | (m.psgc10.isin([ISABELA_CITY, COTABATO_CITY])))
    m["unit_id"] = m.apply(
        lambda r: (SGA_UNIT if r.psgc10.startswith(SGA_PREFIX)
                   else r.psgc10 if r.is_own_unit else r.prov_code), axis=1)
    return m, provs


def build_units(m: pd.DataFrame, provs: pd.DataFrame) -> pd.DataFrame:
    rows = [{"unit_id": r.psgc10, "unit_name": r["name"], "unit_type": "city",
             "region": r.region, "name_norm": normalize_name(strip_parens(r["name"]))}
            for _, r in m[m.is_own_unit].iterrows()]
    reg_by_prov = m.groupby("prov_code")["region"].first().to_dict()
    for _, r in provs.iterrows():
        rows.append({"unit_id": r.prov_code, "unit_name": r.province, "unit_type": "province",
                     "region": reg_by_prov.get(r.prov_code, ""),
                     "name_norm": normalize_name(strip_parens(r.province))})
    rows.append({"unit_id": SGA_UNIT, "unit_name": "Special Geographic Area (BARMM)",
                 "unit_type": "SGA",
                 "region": "Bangsamoro Autonomous Region In Muslim Mindanao (BARMM)",
                 "name_norm": "special geographic area"})
    return pd.DataFrame(rows)


def parse_table_a() -> pd.DataFrame:
    df = pd.read_excel(RAW / "census" / "2024popcen_tableA_prov_huc.xlsx", header=None, skiprows=6)
    rows = []
    for _, r in df.iterrows():
        name = r[0]
        if not isinstance(name, str) or not name.strip():
            continue
        nm = strip_parens(re.sub(r"\*+", " ", name)).strip()
        if re.search(r"(PHILIPPINES|REGION\b|CORDILLERA|BANGSAMORO|MIMAROPA|CARAGA$|"
                     r"NEGROS ISLAND|CAPITAL)", nm, re.I) and "CITY" not in nm.upper() \
                and "GEOGRAPHIC" not in nm.upper():
            continue
        vals = {}
        for label, ci in {"pop2010_a": 2, "pop2015_a": 4, "pop2020_a": 6, "pop2024_a": 8}.items():
            v = r[ci]
            if isinstance(v, str):
                v = v.replace(",", "").strip()
                v = int(v) if v.isdigit() else None
            elif isinstance(v, (int, float)) and not pd.isna(v):
                v = int(v)
            else:
                v = None
            vals[label] = v
        if any(v is not None for v in vals.values()):
            rows.append({"name_a": name.strip(), "name_norm": normalize_name(nm), **vals})
    return pd.DataFrame(rows)


def build_unit_vs(units: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """Unit x year births/deaths panel, 2013-2024."""
    # municipal aggregation, 2017-2024
    v = pd.read_csv(INTERIM / "vitals_muni.csv", dtype={"psgc10": str})
    v = v[v.psgc10.notna() & (v.psgc10 != "")]
    v = v.merge(m[["psgc10", "unit_id"]], on="psgc10", how="left")
    agg = (v[v.year >= 2017].groupby(["unit_id", "year"])[["births", "deaths"]]
           .sum(min_count=1).reset_index())

    # provincial tables 2013-2023 (fills 2013-2016 and the 2018 births hole)
    frames = []
    for kind, f in (("births", "births_prov_2013_2023.csv"),
                    ("deaths", "deaths_prov_2013_2023.csv")):
        df = pd.read_csv(RAW / "openstat" / f, encoding="cp1252")
        ncol = df.columns[0]
        val_cols = {int(c.split()[0]): c for c in df.columns
                    if re.match(r"^\d{4} Both Sexes", c.strip())}
        name_to_unit = dict(zip(units.name_norm, units.unit_id))
        for _, r in df.iterrows():
            raw = str(r[ncol]).replace("…", "...")
            name = raw.lstrip(".").strip()
            depth = len(raw) - len(raw.lstrip("."))
            if not name or re.search(r"(PHILIPPINES|FOREIGN)", name, re.I):
                continue
            if depth in (0, 2) and "CITY" not in name.upper():
                continue
            nn = normalize_name(strip_parens(name))
            # undivided Maguindanao: PSA never split the VS series
            uid = "19087+19088" if nn == "maguindanao" else name_to_unit.get(nn)
            if uid is None:
                print("  [prov VS] no unit for:", name)
                continue
            for yr, c in val_cols.items():
                try:
                    val = int(str(r[c]).replace(",", ""))
                except (ValueError, TypeError):
                    continue
                frames.append({"unit_id": uid, "year": yr, "kind": kind, "value": val})
    pv = pd.DataFrame(frames)
    pvw = pv.pivot_table(index=["unit_id", "year"], columns="kind", values="value",
                         aggfunc="first").reset_index()

    # combine: muni agg preferred for >=2017; prov rows for 2013-2016; fill holes
    base = pd.concat([pvw[pvw.year <= 2016], agg], ignore_index=True)
    base = base.set_index(["unit_id", "year"])
    fill = pvw[pvw.year >= 2017].set_index(["unit_id", "year"])
    for col in ("births", "deaths"):
        base[col] = base[col].fillna(fill[col])
    base = base.reset_index()

    # synthetic combined units (sum of components).
    #  - "19087+19088": undivided Maguindanao EXCL Cotabato City (matches the
    #    provincial VS row and original-boundary Table B pops; 2015-2020 unit)
    #  - "19087+19088+CC": undivided Maguindanao INCL Cotabato City (matches
    #    Table A 2024 restated pops, where CC sits inside Mag. del Norte)
    #  - "12047+19999": Cotabato + SGA. SGA vital events remain registered
    #    under the North Cotabato mother municipalities (verified: provincial
    #    row == municipal sum), so VS = Cotabato's own series.
    combos = {
        "19087+19088": ["19087", "19088"],
        "19087+19088+CC": ["19087", "19088", COTABATO_CITY],
        "12047+19999": ["12047"],
        "MKT+TAG": ["1380300000", "1381500000"],
    }
    add = []
    for cid, parts in combos.items():
        sub = base[base.unit_id.isin(parts)]
        g = sub.groupby("year")[["births", "deaths"]].sum(min_count=len(parts)).reset_index()
        g["unit_id"] = cid
        add.append(g)
    direct = base[base.unit_id == "19087+19088"]  # pre-2017 undivided provincial rows
    out = pd.concat([base[~base.unit_id.isin(combos)], direct] + add, ignore_index=True)
    out = out.drop_duplicates(subset=["unit_id", "year"], keep="first")
    # fill remaining holes (e.g. undivided Maguindanao 2018 births) from the
    # provincial tables, which cover 2013-2023 without the 2018 gap
    out = out.set_index(["unit_id", "year"])
    fill2 = pvw.set_index(["unit_id", "year"])
    for col in ("births", "deaths"):
        out[col] = out[col].fillna(fill2[col])
    return out.reset_index().sort_values(["unit_id", "year"])


def residual(pop: pd.DataFrame, vs: pd.DataFrame, start_year: int, end_year: int,
             pop_cols: tuple[str, str], flags: dict[str, str],
             skip_units: set[str] = frozenset()) -> pd.DataFrame:
    fr = year_fractions(CENSUS_DATES[start_year], CENSUS_DATES[end_year])
    years = sorted(fr)
    dt_years = ((pd.Timestamp(CENSUS_DATES[end_year])
                 - pd.Timestamp(CENSUS_DATES[start_year])).days / 365.25)
    vs_ix = vs.set_index(["unit_id", "year"])
    rows = []
    for _, r in pop.iterrows():
        if r.unit_id in skip_units:
            continue
        p0, p1 = r[pop_cols[0]], r[pop_cols[1]]
        rec = {"unit_id": r.unit_id, "unit_name": r.unit_name,
               "region": r.get("region", ""), "period": f"{start_year}-{end_year}"}
        if pd.isna(p0) or pd.isna(p1):
            rec["flag"] = "missing census population"
            rows.append(rec)
            continue
        b = d = 0.0
        missing = []
        for yr in years:
            key = (r.unit_id, yr)
            if key in vs_ix.index:
                row = vs_ix.loc[key]
                if pd.notna(row["births"]) and pd.notna(row["deaths"]):
                    b += fr[yr] * row["births"]
                    d += fr[yr] * row["deaths"]
                    continue
            missing.append(yr)
        if missing:
            rec["flag"] = f"not computable: missing VS years {missing}"
            rows.append(rec)
            continue
        nm = (p1 - p0) - (b - d)
        avg_pop = (p0 + p1) / 2
        rec.update({
            "pop_start": int(p0), "pop_end": int(p1),
            "births_est": round(b, 1), "deaths_est": round(d, 1),
            "natural_increase": round(b - d, 1), "net_migration": round(nm, 1),
            "netmig_rate_per_1000_yr": round(nm / avg_pop / dt_years * 1000, 2),
            "flag": flags.get(r.unit_id, ""),
        })
        rows.append(rec)
    return pd.DataFrame(rows)


def muni_residual_2020_2024(tb24: Path, m: pd.DataFrame) -> None:
    """Municipal residual once 2024 POPCEN Table B is available. Expects the
    same layout as the 2020 CPH Table B (region sheets, =SUM province rows);
    VERIFY on first run. Populations are PSA-restated to 2024 boundaries;
    municipal VS 2020-2024 comes from the municipal panel (complete)."""
    from parse_census import parse_sheet  # same sheet grammar
    import openpyxl
    from psgc import resolve as _resolve
    wb = openpyxl.load_workbook(tb24, read_only=True)
    rows = []
    for s in wb.sheetnames:
        rows += parse_sheet(wb[s], s)
    df = pd.DataFrame(rows)
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype={"psgc10": str})
    res = _resolve(df, munis)
    print("2024 Table B: rows", len(res), "unresolved", (res.match_method == "UNRESOLVED").sum())

    v = pd.read_csv(INTERIM / "vitals_muni.csv", dtype={"psgc10": str})
    v = v[v.psgc10.notna() & (v.psgc10 != "")]
    fr = year_fractions(CENSUS_DATES[2020], CENSUS_DATES[2024])
    dt_years = ((pd.Timestamp(CENSUS_DATES[2024]) - pd.Timestamp(CENSUS_DATES[2020])).days / 365.25)
    vx = v.pivot_table(index="psgc10", columns="year", values=["births", "deaths"], aggfunc="first")
    out = []
    pop_cols = [c for c in res.columns if c.startswith("pop")]
    p0c = "pop2020" if "pop2020" in pop_cols else None
    p1c = "pop2024" if "pop2024" in pop_cols else None
    for _, r in res.iterrows():
        if not r.psgc10 or p0c is None or p1c is None:
            continue
        p0, p1 = r.get(p0c), r.get(p1c)
        if pd.isna(p0) or pd.isna(p1):
            continue
        try:
            b = sum(fr[y] * vx.loc[r.psgc10, ("births", y)] for y in fr)
            d = sum(fr[y] * vx.loc[r.psgc10, ("deaths", y)] for y in fr)
        except KeyError:
            continue
        if pd.isna(b) or pd.isna(d):
            continue
        nm = (p1 - p0) - (b - d)
        out.append({"psgc10": r.psgc10, "name": r.name_src, "pop2020": int(p0), "pop2024": int(p1),
                    "births_est": round(b, 1), "deaths_est": round(d, 1),
                    "net_migration": round(nm, 1),
                    "netmig_rate_per_1000_yr": round(nm / ((p0 + p1) / 2) / dt_years * 1000, 2)})
    pd.DataFrame(out).to_csv(CLEAN / "net_migration_municipal_2020_2024.csv", index=False)
    print("municipal residual rows:", len(out))


# Municipalities whose 2020->2024 comparison crosses a boundary change:
# EMBO barangays (Makati -> Taguig, in force in 2024 statistics) and the 63
# barangays that left six North Cotabato municipalities for the BARMM SGA.
# The 8 SGA municipalities have no 2020-boundary census base at all.
BOUNDARY_BREAK_2020_2024 = {
    "1380300000": "EMBO barangays transferred to Taguig (2020 base not comparable)",
    "1381500000": "EMBO barangays received from Makati (2020 base not comparable)",
}
SGA_MOTHER_NAMES = ["Aleosan", "Carmen", "Kabacan", "Midsayap", "Pigkawayan", "Pikit"]


def muni_residual_2020_2024_verified(wiki24: Path, m: pd.DataFrame, up: pd.DataFrame) -> None:
    """Municipal residual using the Wikipedia transcription of 2024 POPCEN
    Table B, accepted only where municipal sums reconcile with PSA's official
    Table A unit totals (see parse_pop2024_wiki.py docstring)."""
    w = pd.read_csv(wiki24, dtype={"psgc10": str})
    w = w[w.psgc10.notna() & (w.psgc10 != "")]
    w = w.merge(m[["psgc10", "unit_id", "name", "province", "region"]], on="psgc10", how="left")

    # --- verification against Table A (official)
    agg = w.groupby("unit_id")["pop2024"].sum().rename("pop2024_wiki")
    ta = up.set_index("unit_id")["pop2024_a"]
    # Table A folds Cotabato City into Maguindanao del Norte
    cc = w.loc[w.psgc10 == COTABATO_CITY, "pop2024"].sum()
    agg = agg.add(pd.Series({"19087": cc}), fill_value=0).rename("pop2024_wiki")
    agg = agg.drop(index=[COTABATO_CITY], errors="ignore")
    cmp = pd.concat([agg, ta], axis=1).dropna()
    cmp["diff"] = cmp.pop2024_wiki - cmp.pop2024_a
    bad_units = set(cmp[cmp["diff"] != 0].index)
    n_exact = (cmp["diff"] == 0).sum()
    print(f"\n2024 transcription check vs Table A: {n_exact}/{len(cmp)} units exact")
    if bad_units:
        print(cmp[cmp['diff'] != 0].to_string())

    # --- boundary exclusions
    mothers = set(m[(m.prov_code == "12047") & (m.name.isin(SGA_MOTHER_NAMES))].psgc10)
    excl = dict(BOUNDARY_BREAK_2020_2024)
    for p in mothers:
        excl[p] = "barangays transferred to BARMM SGA (2020 base not comparable)"
    for p in m[m.psgc10.str.startswith(SGA_PREFIX)].psgc10:
        excl[p] = "SGA municipality created after 2020 census (no 2020 base)"

    # --- assemble residual
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    v = pd.read_csv(INTERIM / "vitals_muni.csv", dtype={"psgc10": str})
    v = v[v.psgc10.notna() & (v.psgc10 != "")]
    fr = year_fractions(CENSUS_DATES[2020], CENSUS_DATES[2024])
    dt_years = ((pd.Timestamp(CENSUS_DATES[2024]) - pd.Timestamp(CENSUS_DATES[2020])).days / 365.25)
    vx = v.pivot_table(index="psgc10", columns="year", values=["births", "deaths"], aggfunc="first")
    barmm_units = set(m[m.region.astype(str).str.contains("Bangsamoro|BARMM", na=False)].psgc10)

    out = []
    j = w.merge(cp[["psgc10", "pop2020"]], on="psgc10", how="left")
    for _, r in j.iterrows():
        rec = {"psgc10": r.psgc10, "name": r["name"], "province": r.province,
               "region": r.region, "pop2024_src": "wikipedia-transcription (verified vs Table A)"}
        flags = []
        if r.psgc10 in excl:
            rec["flag"] = "EXCLUDED: " + excl[r.psgc10]
            out.append(rec)
            continue
        if r.unit_id in bad_units:
            flags.append("unit total does not reconcile with Table A — transcription unverified")
        if pd.isna(r.pop2020):
            rec["flag"] = "EXCLUDED: no 2020 census base"
            out.append(rec)
            continue
        try:
            b = sum(fr[y] * vx.loc[r.psgc10, ("births", y)] for y in fr)
            d = sum(fr[y] * vx.loc[r.psgc10, ("deaths", y)] for y in fr)
        except KeyError:
            b = d = float("nan")
        if pd.isna(b) or pd.isna(d):
            rec["flag"] = "EXCLUDED: missing municipal VS years in 2020-2024"
            out.append(rec)
            continue
        if r.psgc10 in barmm_units:
            flags.append(BARMM_FLAG)
        nm = (r.pop2024 - r.pop2020) - (b - d)
        rate = nm / ((r.pop2020 + r.pop2024) / 2) / dt_years * 1000
        if abs(rate) > 50:
            flags.append("extreme rate — small-area counts, inspect before use")
        rec.update({"pop2020": int(r.pop2020), "pop2024": int(r.pop2024),
                    "births_est": round(b, 1), "deaths_est": round(d, 1),
                    "natural_increase": round(b - d, 1), "net_migration": round(nm, 1),
                    "netmig_rate_per_1000_yr": round(nm / ((r.pop2020 + r.pop2024) / 2) / dt_years * 1000, 2),
                    "flag": "; ".join(flags)})
        out.append(rec)
    res = pd.DataFrame(out)
    res.to_csv(CLEAN / "net_migration_municipal_2020_2024.csv", index=False)
    ok = res[res.net_migration.notna()]
    print(f"municipal residual 2020-2024: {len(ok)} computed, {len(res) - len(ok)} excluded/flagged")
    s = ok[~ok.flag.str.contains("BARMM", na=False)].sort_values("netmig_rate_per_1000_yr")
    cols = ["name", "province", "net_migration", "netmig_rate_per_1000_yr"]
    print("top out (non-BARMM):\n", s[cols].head(5).to_string())
    print("top in (non-BARMM):\n", s[cols].tail(5).to_string())


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    m, provs = load_register()
    units = build_units(m, provs)

    # ---- clean municipal files
    reg = m[["psgc10", "psgc9", "name", "level", "city_class", "income_class",
             "province", "region", "old_names"]]
    reg.to_csv(CLEAN / "municipalities.csv", index=False)

    cp = pd.read_csv(INTERIM / "census_pop_muni.csv", dtype={"psgc10": str})
    cp = cp.merge(m[["psgc10", "name", "province", "region", "unit_id"]], on="psgc10", how="left")
    out_cols = ["psgc10", "name", "province", "region", "pop2000", "pop2010", "pop2015",
                "pop2020", "name_src", "province_src", "match_method"]
    hist_path = INTERIM / "census_hist_muni.csv"
    if hist_path.exists():
        hist = pd.read_csv(hist_path, dtype={"psgc10": str})
        keep = hist[hist.psgc10.notna() & (hist.psgc10 != "")]
        cp = cp.merge(keep[["psgc10", "pop1960", "pop1970", "pop1980", "pop1990", "hist_flag"]],
                      on="psgc10", how="left")
        # SGA municipalities are absent from Table B (their territory was
        # enumerated under N. Cotabato in 2020) but Report 2A T1 provides
        # their full restated series incl. 2000-2020 — append those rows.
        sga = keep[~keep.psgc10.isin(cp.psgc10)].copy()
        if len(sga):
            sga = sga.merge(m[["psgc10", "name", "province", "region", "unit_id"]],
                            on="psgc10", how="left")
            sga["match_method"] = sga["match_method"].fillna("report2A_only")
            sga["hist_flag"] = ("Report 2A only (restated boundaries); no Table B row — "
                                + sga["hist_flag"].fillna(""))
            cp = pd.concat([cp, sga], ignore_index=True)
        out_cols = (["psgc10", "name", "province", "region",
                     "pop1960", "pop1970", "pop1980", "pop1990",
                     "pop2000", "pop2010", "pop2015", "pop2020",
                     "name_src", "province_src", "match_method", "hist_flag"])
    cp[out_cols].to_csv(CLEAN / "population_census_municipal.csv", index=False)

    v = pd.read_csv(INTERIM / "vitals_muni.csv", dtype={"psgc10": str})
    v = v[v.psgc10.notna() & (v.psgc10 != "")]
    v = v.merge(m[["psgc10", "name", "province"]], on="psgc10", how="left")
    v[["psgc10", "name", "province", "year", "births", "deaths", "flag", "source"]].sort_values(
        ["psgc10", "year"]).to_csv(CLEAN / "vital_statistics_municipal.csv", index=False)

    # ---- unit population table
    ta = parse_table_a()
    up = units.merge(ta.drop(columns=["name_a"]), on="name_norm", how="left")
    # original-boundary pops (Table B aggregation)
    orig = cp.groupby("unit_id")[["pop2015", "pop2020"]].sum(min_count=1).reset_index()
    up = up.merge(orig, on="unit_id", how="left")

    # synthetic combined units
    def combo_row(cid, name, parts):
        sub = up[up.unit_id.isin(parts)]
        rec = {"unit_id": cid, "unit_name": name, "unit_type": "combined",
               "region": ";".join(sorted(set(sub.region.dropna())))}
        for c in ("pop2010_a", "pop2015_a", "pop2020_a", "pop2024_a", "pop2015", "pop2020"):
            rec[c] = sub[c].sum(min_count=len(parts))
        return rec
    combos = pd.DataFrame([
        combo_row("19087+19088", "Maguindanao (undivided, excl. Cotabato City)", ["19087", "19088"]),
        combo_row("19087+19088+CC", "Maguindanao (undivided, incl. Cotabato City)",
                  ["19087", "19088", COTABATO_CITY]),
        combo_row("12047+19999", "Cotabato incl. Special Geographic Area", ["12047", SGA_UNIT]),
        combo_row("MKT+TAG", "Makati + Taguig (EMBO-consistent)", ["1380300000", "1381500000"]),
    ])
    # Table A's Mag. del Norte already contains Cotabato City: the incl-CC
    # combo's restated pops are just MdN+MdS; the excl-CC combo has no valid
    # restated pops (prevent misuse).
    mdn_mds = up[up.unit_id.isin(["19087", "19088"])][["pop2015_a", "pop2020_a", "pop2024_a"]].sum(min_count=2)
    for c in ("pop2015_a", "pop2020_a", "pop2024_a"):
        combos.loc[combos.unit_id == "19087+19088+CC", c] = mdn_mds[c]
        combos.loc[combos.unit_id == "19087+19088", c] = float("nan")
    up = pd.concat([up, combos], ignore_index=True)

    vs = build_unit_vs(units, m)

    barmm = set(up[up.region.astype(str).str.contains("BARMM|Bangsamoro", case=False, na=False)].unit_id)
    flags_1520 = {u: BARMM_FLAG for u in barmm}
    flags_2024 = dict(flags_1520)
    for _, r in up.iterrows():
        note = []
        if pd.notna(r.pop2020) and pd.notna(r.pop2020_a) and abs(r.pop2020 - r.pop2020_a) > 500:
            note.append("2020 pop restated to 2024 boundaries")
        if r.unit_id in ("1380300000", "1381500000"):
            note.append("EMBO barangays moved Makati->Taguig during period; VS coding "
                        "switches mid-period — use combined MKT+TAG row for a consistent estimate")
        if r.unit_id in ("12047", SGA_UNIT):
            note.append("63 barangays moved N. Cotabato -> BARMM SGA during period; use "
                        "combined 12047+19999 row for a consistent estimate")
        if note:
            flags_2024[r.unit_id] = "; ".join([flags_2024.get(r.unit_id, "")] + note).strip("; ")

    # 2015-2020: original boundaries. Maguindanao only as undivided (excl CC);
    # combined units for later boundary events don't apply to this period.
    skip_1520 = {"19087", "19088", SGA_UNIT, "MKT+TAG", "12047+19999", "19087+19088+CC"}
    r1520 = residual(up, vs, 2015, 2020, ("pop2015", "pop2020"), flags_1520, skip_1520)
    # (City of Cotabato has no provincial-table VS 2015/2016 -> flagged not computable)
    # 2020-2024: restated boundaries; Maguindanao only as undivided incl CC.
    skip_2024 = {"19087", "19088", SGA_UNIT, COTABATO_CITY, "19087+19088"}
    r2024 = residual(up, vs, 2020, 2024, ("pop2020_a", "pop2024_a"), flags_2024, skip_2024)

    allr = pd.concat([r1520, r2024], ignore_index=True)
    allr.to_csv(CLEAN / "net_migration_province.csv", index=False)

    # ---- municipal residual 2020-2024: requires the 2024 POPCEN municipal
    # counts (Table B), not yet obtainable from this machine (psa.gov.ph
    # blocks direct access; file not yet in the Internet Archive). Drop the
    # file at data/raw/census/2024popcen_tableB_muni.xlsx and re-run.
    tb24 = RAW / "census" / "2024popcen_tableB_muni.xlsx"
    wiki24 = INTERIM / "pop2024_muni.csv"
    if tb24.exists():
        muni_residual_2020_2024(tb24, m)
    elif wiki24.exists():
        muni_residual_2020_2024_verified(wiki24, m, up)
    else:
        print("\n[skip] municipal residual 2020-2024: place 2024 POPCEN Table B at", tb24)

    for name, r in (("2015-2020", r1520), ("2020-2024", r2024)):
        ok = r[r.net_migration.notna()]
        nc = r[r.net_migration.isna()]
        print(f"\n=== provincial residual {name}: {len(ok)} computed, {len(nc)} flagged ===")
        if len(nc):
            print("  not computed:", list(nc.unit_name)[:8])
        if len(ok):
            print("  national net migration (sum):", int(ok[~ok.unit_id.str.contains('[+]', regex=True)].net_migration.sum()))
            s = ok.sort_values("netmig_rate_per_1000_yr")
            cols = ["unit_name", "net_migration", "netmig_rate_per_1000_yr"]
            print("  top out:\n", s[cols].head(6).to_string())
            print("  top in:\n", s[cols].tail(6).to_string())


if __name__ == "__main__":
    main()
