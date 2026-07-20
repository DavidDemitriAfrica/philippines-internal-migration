"""Parse 2020 CPH Report 2A Table 1 — "Population Enumerated in Various
Census by City/Municipality: 1960-2020" — extending the municipal census
panel back to 1960 (censuses: 1960, 1970, 1980, 1990, 2000, 2010, 2015, 2020;
2020 municipal universe, populations as enumerated).

Row-type disambiguation: region rows match the region pattern; a row whose
name matches the province register is treated as a PROVINCE header only if
its 2020 value equals the official province total (computed from our Table B
panel) — this resolves municipalities named like provinces (Biliran,
Siquijor) and like OTHER provinces (Quirino in Isabela, Aurora in Zamboanga
del Sur, ...).

Verification: for every resolved municipality, the 2000/2010/2015/2020 values
must equal the Table B panel exactly; mismatches are reported and flagged.

Output: data/interim/census_hist_muni.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import resolve, normalize_name, strip_parens  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, INTERIM = ROOT / "data" / "raw", ROOT / "data" / "interim"
SRC = RAW / "census" / "2020cph_report2A_population.xlsx"

# NB: no bare CARAGA here — T1 writes the region as "REGION XIII (CARAGA)"
# while "CARAGA" alone is the municipality in Davao Oriental.
REGION_PAT = re.compile(
    r"(REGION\b|NATIONAL CAPITAL|CORDILLERA|BANGSAMORO|AUTONOMOUS REGION|MIMAROPA|"
    r"NEGROS ISLAND|^PHILIPPINES)", re.I)

YEAR_COLS = {1960: 1, 1970: 2, 1980: 3, 1990: 4, 2000: 6, 2010: 8, 2015: 10, 2020: 12}


def main() -> None:
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype=str)
    cp = pd.read_csv(INTERIM / "census_pop_muni.csv", dtype={"psgc10": str})
    cp = cp.merge(munis[["psgc10", "prov_code"]], on="psgc10", how="left")
    prov_totals_2020 = cp.groupby("prov_code")["pop2020"].sum().to_dict()
    provs = pd.read_csv(INTERIM / "psgc_provinces.csv", dtype=str)
    prov_by_norm = {normalize_name(strip_parens(p.province)): p.prov_code
                    for _, p in provs.iterrows()}
    # Table A restated province totals (T1's vintage restates the SGA transfer:
    # Cotabato and its six mother municipalities carry post-transfer values)
    from build_dataset import parse_table_a
    ta = parse_table_a()
    prov_totals_restated = {}
    for _, r in ta.iterrows():
        pc = prov_by_norm.get(r.name_norm)
        if pc and pd.notna(r.pop2020_a):
            prov_totals_restated[pc] = r.pop2020_a

    wb = openpyxl.load_workbook(SRC, read_only=True)
    ws = wb["T1"]
    rows = []
    province = None
    for r in ws.iter_rows(min_row=9, values_only=True):
        name = r[0]
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.upper().startswith(("TABLE", "CITY/MUNICIPALITY", "CENSUS", "NOTE", "SOURCE",
                                    "A ", "B ", "C ", "D ")):
            continue
        if REGION_PAT.search(strip_parens(name)):
            province = name if "CAPITAL" in name.upper() else None
            continue
        low = normalize_name(strip_parens(name))
        if low.startswith("maguindanao"):
            # undivided "MAGUINDANAO (including CITY OF COTABATO)" header
            province = "MAGUINDANAO"
            continue
        if low.startswith("interim province"):
            province = "SPECIAL GEOGRAPHIC AREA"
            continue
        v2020 = r[YEAR_COLS[2020]]
        nn = normalize_name(strip_parens(name))
        pcode = prov_by_norm.get(nn)
        if pcode is not None and isinstance(v2020, (int, float)):
            official = prov_totals_2020.get(pcode)
            restated = prov_totals_restated.get(pcode)
            if (official is not None and abs(v2020 - official) <= 2) or \
               (restated is not None and abs(v2020 - restated) <= 2):
                province = name
                continue
        vals = {}
        any_num = False
        for yr, ci in YEAR_COLS.items():
            v = r[ci]
            # T1 prints 0 for censuses predating an LGU's existence — that is
            # a nonexistence marker, not an enumerated count of zero.
            if isinstance(v, (int, float)) and v > 0:
                vals[f"pop{yr}"] = int(v)
                any_num = True
            else:
                vals[f"pop{yr}"] = None
        if not any_num:
            continue
        rows.append({"name_src": name, "province_src": province, **vals})

    df = pd.DataFrame(rows)
    res = resolve(df, munis)
    # LGUs dissolved before 2020 appear with historical values and a zero/blank
    # 2020 cell (e.g. Bacon, Sorsogon — merged into Sorsogon City in 2000):
    # keep them, flagged, with no PSGC code.
    dissolved = (res.match_method == "UNRESOLVED") & (res.pop2020.fillna(0) == 0)
    res.loc[dissolved, "match_method"] = "dissolved_pre2020"
    n_un = (res.match_method == "UNRESOLVED").sum()
    print(f"rows: {len(res)}  unresolved: {n_un}  dissolved: {int(dissolved.sum())}")
    if n_un:
        print(res[res.match_method == "UNRESOLVED"][["name_src", "province_src"]].to_string())
    dup = res[res.psgc10.ne("") & res.psgc10.duplicated(keep=False)]
    if len(dup):
        print("DUPLICATES:\n", dup[["name_src", "province_src", "psgc10"]].to_string())

    # element-wise verification vs Table B; disagreements (all explained
    # boundary restatements/disputes: SGA mothers, Burdeos/Panukulan,
    # Dumalneg/Adams) become per-row flags
    chk = res.merge(cp[["psgc10", "pop2000", "pop2010", "pop2015", "pop2020"]],
                    on="psgc10", suffixes=("", "_tb"))
    bad = 0
    flag_years: dict[str, list[int]] = {}
    for yr in (2000, 2010, 2015, 2020):
        m = chk[f"pop{yr}"].notna() & chk[f"pop{yr}_tb"].notna() & \
            (chk[f"pop{yr}"] != chk[f"pop{yr}_tb"])
        if m.any():
            bad += int(m.sum())
            for p in chk[m].psgc10:
                flag_years.setdefault(p, []).append(yr)
    res["hist_flag"] = res.psgc10.map(
        lambda p: (f"Report 2A restates {flag_years[p]} vs Table B "
                   "(boundary change/dispute — see codebook)") if p in flag_years else "")
    res.loc[res.match_method == "dissolved_pre2020", "hist_flag"] = \
        "LGU dissolved/absorbed before 2020; historical values only"
    print(f"verification vs Table B: {bad} mismatching cells "
          f"across {4 * len(chk)} overlapping cells; {len(flag_years)} LGUs flagged")
    for yr in YEAR_COLS:
        print(yr, int(res[f"pop{yr}"].sum(skipna=True)), f"(n={res[f'pop{yr}'].notna().sum()})")
    res.to_csv(INTERIM / "census_hist_muni.csv", index=False)


if __name__ == "__main__":
    main()
