"""Parse PSA municipal vital statistics (registered births & deaths) into a
tidy panel resolved to PSGC codes.

Sources (see data/provenance.jsonl):
    2017        vital_events_2017.xlsx           births+deaths (one sheet)
    2018        deaths_2018_stat_tables.xlsx     deaths only (births municipal
                                                 table not published as XLSX;
                                                 Q1 births exist — see notes)
    2019        vitalstats_2019_stat_tables.xlsx births+deaths (PRELIMINARY)
    2020-2022   births/deaths_20XX_stat_tables.xlsx
    2023-2024   OpenSTAT CSVs (births_muni_*, deaths_muni_*)

Concepts: births = registered live births by USUAL RESIDENCE of mother, both
sexes; deaths = registered total deaths by USUAL RESIDENCE. Registered ≠
occurred: under/late registration is real, varies by area, and is NOT adjusted
here (documented in the codebook; PSA publishes no municipal completeness
estimates).

Output: data/interim/vitals_muni.csv
    year, name_src, province_src, psgc10, match_method, births, deaths,
    births_flag, deaths_flag, source
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import resolve, strip_parens, normalize_name  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"

REGION_PAT = re.compile(
    r"(REGION\b|NATIONAL CAPITAL|CORDILLERA|BANGSAMORO|AUTONOMOUS REGION|CARAGA|MIMAROPA|"
    r"NEGROS ISLAND|PHILIPPINES|TOTAL$)", re.I)
DISTRICT_PAT = re.compile(r"DISTRICT$", re.I)
CITY_PAT = re.compile(r"(^CITY OF |\bCITY$)", re.I)
SKIP_PAT = re.compile(r"(not stated|foreign countr|unknown)", re.I)


def is_caps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(c.upper() == c for c in letters)


def walk_indented(rows, name_value_pairs):
    """Generic walker for PSA hierarchy tables.

    rows: iterable of (name, {col: value}) where name retains indentation.
    Yields dicts with name_src, province_src and the value columns.
    Context rules: ALL-CAPS row = region (matches REGION_PAT) or province;
    NCR districts are skipped as context (province stays the region); rows
    matching SKIP_PAT are emitted flagged so residuals can account for
    unallocated events.
    """
    region = None
    province = None
    for raw_name, vals in rows:
        name = raw_name.strip()
        if not name:
            continue
        if SKIP_PAT.search(name):
            yield {"name_src": name, "province_src": province or region,
                   "unallocated": True, **vals}
            continue
        if re.match(r"^region\b", strip_parens(name), re.I) and not is_caps(name):
            # e.g. "REGION XIII (Caraga)" written mixed-case; a bare mixed-case
            # "Caraga" is the municipality in Davao Oriental, not the region
            region, province = name, None
            continue
        if is_caps(name):
            core = strip_parens(name)
            if CITY_PAT.search(core):
                # HUCs/ICCs are listed in caps as their own group but carry
                # their data on the same row: emit, keep surrounding context.
                yield {"name_src": name, "province_src": province or region,
                       "unallocated": False, **vals}
            elif REGION_PAT.search(core):
                region = name
                province = name if "CAPITAL" in name.upper() else None
            elif DISTRICT_PAT.search(core):
                pass  # NCR district grouping; keep current province (= NCR)
            else:
                province = name
            continue
        yield {"name_src": name, "province_src": province or region,
               "unallocated": False, **vals}


def sheet_rows(path, sheet, name_col, cols: dict, skiprows=0):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[sheet]
    out = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i < skiprows:
            continue
        name = r[name_col]
        if not isinstance(name, str) or not name.strip():
            continue
        vals = {}
        ok = False
        for label, ci in cols.items():
            v = r[ci]
            if isinstance(v, (int, float)):
                vals[label] = int(v)
                ok = True
            else:
                vals[label] = None
        if ok:
            out.append((name, vals))
    wb.close()
    return out


def openstat_rows(path, value_col, encoding="cp1252"):
    """OpenSTAT CSV hierarchy uses leading dots; some exports substitute a
    cp1252 ellipsis ('…' = 3 dots). Municipal rows are the deepest level."""
    df = pd.read_csv(path, encoding=encoding)
    ncol = df.columns[0]
    parsed = []
    for _, r in df.iterrows():
        raw = str(r[ncol]).replace("…", "...")
        depth = len(raw) - len(raw.lstrip("."))
        name = raw.lstrip(".").strip()
        if not name:
            continue
        v = r[value_col]
        try:
            v = int(str(v).replace(",", ""))
        except (ValueError, TypeError):
            v = None
        parsed.append((depth, name, v))
    max_depth = max(d for d, _, _ in parsed)
    out = []
    for depth, name, v in parsed:
        # munis (deepest level) keep original case; shallower rows are context
        out.append((name if depth >= max_depth else name.upper(), {"value": v}))
    return out


def collect() -> pd.DataFrame:
    V = RAW / "vitalstats"
    O = RAW / "openstat"
    frames = []

    def emit(rows, year, kind, source, flag=""):
        recs = list(walk_indented(rows, None))
        df = pd.DataFrame(recs)
        df["year"], df["kind"], df["source"], df["flag"] = year, kind, source, flag
        frames.append(df)

    # --- 2017: one sheet, births col1 (both sexes, by residence), deaths col4
    rows = sheet_rows(V / "vital_events_2017.xlsx", "2017 Counts", 0, {"value": 1}, skiprows=6)
    emit(rows, 2017, "births", "vital_events_2017.xlsx")
    rows = sheet_rows(V / "vital_events_2017.xlsx", "2017 Counts", 0, {"value": 4}, skiprows=6)
    emit(rows, 2017, "deaths", "vital_events_2017.xlsx")

    # --- 2018: deaths only (Table1: col1 = total deaths by usual residence)
    rows = sheet_rows(V / "deaths_2018_stat_tables.xlsx", "Table1", 0, {"value": 1}, skiprows=2)
    emit(rows, 2018, "deaths", "deaths_2018_stat_tables.xlsx")

    # --- 2019 (PRELIMINARY): births col1, deaths col4
    rows = sheet_rows(V / "vitalstats_2019_stat_tables.xlsx", "2019", 0, {"value": 1}, skiprows=3)
    emit(rows, 2019, "births", "vitalstats_2019_stat_tables.xlsx", flag="preliminary")
    rows = sheet_rows(V / "vitalstats_2019_stat_tables.xlsx", "2019", 0, {"value": 4}, skiprows=3)
    emit(rows, 2019, "deaths", "vitalstats_2019_stat_tables.xlsx", flag="preliminary")

    # --- 2020-2022 births: Tab 1, name col1, usual residence both sexes col5
    for yr in (2020, 2021, 2022):
        f = V / f"births_{yr}_stat_tables.xlsx"
        rows = sheet_rows(f, "Tab 1", 1, {"value": 5}, skiprows=7)
        emit(rows, yr, "births", f.name)

    # --- 2020-2022 deaths: T1, name col0, total deaths usual residence col1
    for yr in (2020, 2021, 2022):
        f = V / f"deaths_{yr}_stat_tables.xlsx"
        rows = sheet_rows(f, "T1", 0, {"value": 1}, skiprows=5)
        emit(rows, yr, "deaths", f.name)

    # --- 2023-2024 from OpenSTAT
    for yr in (2023, 2024):
        rows = openstat_rows(O / f"births_muni_{yr}.csv", "Usual Residence Both Sexes")
        emit(rows, yr, "births", f"openstat births_muni_{yr}.csv")
        rows = openstat_rows(O / f"deaths_muni_{yr}.csv", "Total Deaths Place of Usual Residence")
        emit(rows, yr, "deaths", f"openstat deaths_muni_{yr}.csv")

    return pd.concat(frames, ignore_index=True)


def main() -> None:
    df = collect()
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype={"psgc10": str})
    # resolve allocated rows only; keep unallocated rows with empty psgc
    alloc = df[~df.unallocated].copy()
    unalloc = df[df.unallocated].copy()
    res = resolve(alloc, munis)
    # HUCs/ICCs can appear twice (caps group header + mixed-case row, same
    # value, e.g. CITY OF ISABELA / City of Isabela in 2017): dedupe.
    resolved_mask = res.match_method != "UNRESOLVED"
    res = pd.concat([
        res[resolved_mask].drop_duplicates(subset=["year", "kind", "psgc10"], keep="first"),
        res[~resolved_mask],
    ], ignore_index=True)
    unalloc["psgc10"], unalloc["match_method"] = "", "unallocated"
    out = pd.concat([res, unalloc], ignore_index=True)

    # pivot births/deaths into columns
    key = ["year", "psgc10", "name_src", "province_src", "match_method"]
    piv = out.pivot_table(index=key, columns="kind", values="value",
                          aggfunc="first").reset_index()
    flags = out.groupby(key[:2])["flag"].agg(lambda s: ";".join(sorted({x for x in s if x}))).reset_index()
    piv = piv.merge(flags, on=["year", "psgc10"], how="left")
    src = out.groupby(key[:2])["source"].agg(lambda s: ";".join(sorted(set(s)))).reset_index()
    piv = piv.merge(src, on=["year", "psgc10"], how="left")

    INTERIM.mkdir(parents=True, exist_ok=True)
    piv.to_csv(INTERIM / "vitals_muni.csv", index=False)

    n_un = (out.match_method == "UNRESOLVED").sum()
    print(f"rows: {len(out)}  unresolved: {n_un}")
    if n_un:
        bad = out[out.match_method == "UNRESOLVED"]
        print(bad.groupby(["name_src", "province_src"]).size().to_string())
    # sanity: national totals by year/kind (allocated munis only)
    chk = res[res.match_method != "UNRESOLVED"].groupby(["year", "kind"])["value"].sum()
    print(chk.to_string())


if __name__ == "__main__":
    main()
