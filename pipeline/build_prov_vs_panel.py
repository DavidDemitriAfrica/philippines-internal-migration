"""Long provincial vital-statistics panel, 2006-2024, at GEOGRAPHIC-province
level (HUCs folded into host provinces; NCR one unit; Maguindanao undivided;
Cotabato incl. SGA territory) — the only geography consistent across all
sources:

    deaths 2006-2012  PSA deaths-by-cause file (provinces already fold HUCs;
                      NCR published as four districts, summed here)
    births/deaths 2013-2024  unit-level series folded via the HUC->host map

Overlap years 2013-2015 exist in both death sources; equality is checked and
reported (spot-verified exact: Benguet 2013 = Benguet+Baguio = 3,136).
Births before 2013 were never published at this level in reachable open
sources (eFOI TODO; UN Demographic Yearbook natality tables are a possible
alternative — unverified).

Output: data/clean/vital_statistics_provincial.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import normalize_name, strip_parens, CITY_HOST_PROVINCE  # noqa: E402
from build_dataset import (load_register, build_units, build_unit_vs,  # noqa: E402
                           COTABATO_CITY, ISABELA_CITY, SGA_UNIT)

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN, INTERIM = ROOT / "data" / "raw", ROOT / "data" / "clean", ROOT / "data" / "interim"
SRC = RAW / "vitalstats" / "deaths_by_cause_prov_2006_2015.xlsx"

YEARS_OLD = list(range(2006, 2016))  # col pairs starting at col 2


def parse_deaths_2006_2015() -> pd.DataFrame:
    df = pd.read_excel(SRC, sheet_name=0, header=None)
    geo = df[df[0].notna() & df[1].isna()]
    rows = []
    ncr = {yr: 0 for yr in YEARS_OLD}
    for _, r in geo.iterrows():
        name = str(r[0]).strip()
        if not name or name.upper().startswith(("TABLE", "CAUSE", "SOURCE", "NOTES",
                                                "PHILIPPINES", "FOREIGN")):
            continue
        vals = {}
        ok = True
        for i, yr in enumerate(YEARS_OLD):
            m, f = r[2 + 2 * i], r[3 + 2 * i]
            if pd.isna(m) or pd.isna(f):
                ok = False
                break
            vals[yr] = int(m) + int(f)
        if not ok:
            continue
        if name.upper().startswith("NCR"):
            for yr in YEARS_OLD:
                ncr[yr] += vals[yr]
            continue
        if re.search(r"(REGION\b|CORDILLERA|ARMM|AUTONOMOUS|CARAGA$|MIMAROPA|CAPITAL)",
                     strip_parens(name), re.I):
            continue
        rows.append({"prov_name_src": name, **vals})
    rows.append({"prov_name_src": "NATIONAL CAPITAL REGION", **ncr})
    return pd.DataFrame(rows)


def geo_key_for_unit(uid: str, name_by_id: dict, prov_name_by_code: dict) -> str | None:
    """Map a unit id to a geographic-province key (normalized name)."""
    if uid == "MKT+TAG" or (uid.startswith("13") and len(uid) == 10):
        return "national capital region"
    if uid in ("19087", "19088", "19087+19088", "19087+19088+CC", COTABATO_CITY):
        return "maguindanao (undivided)"
    if uid in ("12047", SGA_UNIT, "12047+19999"):
        return "cotabato (incl. sga)"
    if uid == ISABELA_CITY:
        return "basilan"
    if len(uid) == 5 and uid.isdigit():
        return normalize_name(strip_parens(prov_name_by_code.get(uid, "")))
    nm = normalize_name(name_by_id.get(uid, ""))
    host = CITY_HOST_PROVINCE.get(nm)
    return host


def main() -> None:
    m, provs = load_register()
    units = build_units(m, provs)
    vs = build_unit_vs(units, m)
    name_by_id = dict(zip(m.psgc10, m["name"]))
    prov_name_by_code = dict(zip(provs.prov_code, provs.province))

    vs["geo"] = vs.unit_id.map(lambda u: geo_key_for_unit(u, name_by_id, prov_name_by_code))
    # avoid double counting: combined units overlap their components
    vs = vs[~vs.unit_id.isin(["19087+19088+CC", "MKT+TAG", "12047+19999"])]
    new = (vs[vs.geo.notna()].groupby(["geo", "year"])[["births", "deaths"]]
           .sum(min_count=1).reset_index())
    new = new[new.year >= 2013]

    old = parse_deaths_2006_2015()
    old["geo"] = old.prov_name_src.map(lambda s: normalize_name(strip_parens(s)))
    old.loc[old.geo == "maguindanao", "geo"] = "maguindanao (undivided)"
    # this vintage's Cotabato province includes the future-SGA barangays
    old.loc[old.geo.isin(["cotabato", "north cotabato"]), "geo"] = "cotabato (incl. sga)"
    # renamed/re-spelled provinces; chartered cities listed separately in the
    # old source fold into their geographic province (matching the new fold)
    old.loc[old.geo == "compostela valley", "geo"] = "davao de oro"
    old.loc[old.geo == "davao (davao del norte)", "geo"] = "davao del norte"
    old.loc[old.geo == "dinagat island", "geo"] = "dinagat islands"
    old.loc[old.geo == "mt province", "geo"] = "mountain province"
    old.loc[old.geo == "isabela city", "geo"] = "basilan"
    old.loc[old.geo == "cotabato city", "geo"] = "maguindanao (undivided)"
    old = old.groupby("geo", as_index=False)[YEARS_OLD].sum()
    long_old = old.melt(id_vars=["geo"], value_vars=YEARS_OLD,
                        var_name="year", value_name="deaths_old")

    # overlap check 2013-2015
    chk = new.merge(long_old, on=["geo", "year"])
    diff = chk[chk.deaths.notna() & (chk.deaths != chk.deaths_old)]
    print(f"overlap 2013-2015: {len(chk)} cells, {len(diff)} disagree")
    if len(diff):
        print(diff.head(10).to_string())

    # assemble: 2006-2012 deaths from old; 2013+ from unit fold
    pre = long_old[long_old.year <= 2012].rename(columns={"deaths_old": "deaths"})
    pre["births"] = pd.NA
    pre["source"] = "PSA deaths-by-cause 2006-2015 (HUCs folded at source)"
    new["source"] = "unit series folded to geographic provinces"
    panel = pd.concat([pre[["geo", "year", "births", "deaths", "source"]],
                       new[["geo", "year", "births", "deaths", "source"]]],
                      ignore_index=True).sort_values(["geo", "year"])
    unmatched_old = set(long_old.geo) - set(new.geo)
    if unmatched_old:
        print("old-source provinces with no modern counterpart:", sorted(unmatched_old))
    panel["flag"] = ""
    panel.loc[panel.year <= 2012, "flag"] = "births not published at this level before 2013"
    CLEAN.mkdir(exist_ok=True)
    panel.to_csv(CLEAN / "vital_statistics_provincial.csv", index=False)
    n_prov = panel.geo.nunique()
    print(f"panel: {len(panel)} rows, {n_prov} geographic provinces, years "
          f"{panel.year.min()}-{panel.year.max()}")


if __name__ == "__main__":
    main()
