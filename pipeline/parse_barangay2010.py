"""Barangay-level 2010 census populations, all 17 regions, extracted from the
archived 2010 CPH regional press-release PDFs ("Total Population by Province,
City, Municipality and Barangay: as of May 1, 2010").

Text grammar mirrors the 2020 workbooks: PROVINCE rows caps, municipality rows
caps, barangay rows mixed case, one "Name Number" pair per line; names can
wrap across lines/pages (buffered). QA is strict: every municipality's
barangay sum is checked against its official 2010 count from the census panel;
mismatches are flagged per municipality.

Outputs: data/clean/population_barangay_2010.csv, and a pop2010 column merged
into data/clean/population_barangay_2020.csv (psgc10-matched rows).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import load_psgc, normalize_name, strip_parens, resolve  # noqa: E402
from parse_barangay2020 import is_caps, norm_bgy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "census" / "barangay2010"
CLEAN, INTERIM = ROOT / "data" / "clean", ROOT / "data" / "interim"

FILES = {
    "National_Capital_Region.pdf": "National Capital Region (NCR)",
    "Cordillera_Administrative_Region.pdf": "Cordillera Administrative Region (CAR)",
    "Ilocos.pdf": "Region I (Ilocos Region)",
    "Cagayan_Valley.pdf": "Region II (Cagayan Valley)",
    "Central_Luzon.pdf": "Region III (Central Luzon)",
    "CALABARZON.pdf": "Region IV-A (CALABARZON)",
    "MIMAROPA.pdf": "MIMAROPA Region",
    "Bicol.pdf": "Region V (Bicol Region)",
    "Western_Visayas.pdf": "Region VI (Western Visayas)",
    "Central_Visayas.pdf": "Region VII (Central Visayas)",
    "Eastern_Visayas.pdf": "Region VIII (Eastern Visayas)",
    "Zamboanga_Peninsula.pdf": "Region IX (Zamboanga Peninsula)",
    "Northern_Mindanao.pdf": "Region X (Northern Mindanao)",
    "Davao.pdf": "Region XI (Davao Region)",
    "SOCCSKSARGEN.pdf": "Region XII (SOCCSKSARGEN)",
    "Caraga.pdf": "Region XIII (Caraga)",
    "Autonomous_Region_in_Muslim_Mindanao.pdf":
        "Bangsamoro Autonomous Region In Muslim Mindanao (BARMM)",
}

HEADER_PAT = re.compile(
    r"^(2010 Census|Total Population by|as of May|Province, City|and Barangay|Page \d|National Statistics Office|Source:|\d+$)", re.I)
LINE_PAT = re.compile(r"^(.*?)[\s ]+([\d,]{2,})$")


def walk_pdf(path: Path, region: str) -> list[dict]:
    """Context comes from each page's running header ("2010 Census of
    Population and Housing <Province-or-City>"); caps rows inside a page are
    municipality headers (or the unit's own total row, skipped). Word-level
    row reconstruction pairs every numeric token with the words before it,
    handling one- and two-column pages alike; bold overprint is deduped."""
    rows = []
    province = None
    muni = None
    pending = ""
    NUM = re.compile(r"^[\d,]{2,}$")
    CTX = re.compile(r"2010 Census of Population and Housing\s+(.+)$", re.I)

    def emit(name, val, ctx_norm):
        nonlocal muni, pending
        name = (pending + " " + name).strip()
        pending = ""
        if not name or HEADER_PAT.match(name):
            return
        if is_caps(name):
            nn = normalize_name(strip_parens(name))
            if nn == ctx_norm or ctx_norm.startswith(nn):
                # the unit's own total row: on city pages the city IS the
                # municipality; on province pages skip the total
                if "city" in ctx_norm:
                    muni = name
                return
            muni = name
            return
        rows.append({"region": region, "province_src": province, "muni_src": muni,
                     "barangay_src": name, "pop2010": val})

    with pdfplumber.open(path) as pdf:
        prev_ctx = None
        for page in pdf.pages:
            words = page.dedupe_chars(tolerance=1).extract_words()
            words.sort(key=lambda w: w["top"])
            lines = []
            cur, cur_top = [], None
            for w in words:
                if cur_top is None or w["top"] - cur_top <= 2.5:
                    cur.append(w)
                    cur_top = w["top"] if cur_top is None else (cur_top + w["top"]) / 2
                else:
                    lines.append(sorted(cur, key=lambda x: x["x0"]))
                    cur, cur_top = [w], w["top"]
            if cur:
                lines.append(sorted(cur, key=lambda x: x["x0"]))
            # page context from the running header
            head = " ".join(w["text"] for w in lines[0]) if lines else ""
            mh = CTX.search(head)
            ctx = mh.group(1).strip() if mh else prev_ctx
            if ctx != prev_ctx:
                province = ctx
                if not (ctx and "city" in ctx.lower()):
                    muni = None
                prev_ctx = ctx
                pending = ""
            ctx_norm = normalize_name(strip_parens(ctx or ""))
            if ctx and "city" in ctx.lower() and muni is None:
                muni = ctx
            for ws in lines:
                buf = []
                for w in ws:
                    if NUM.match(w["text"]):
                        emit(" ".join(buf), int(w["text"].replace(",", "")), ctx_norm)
                        buf = []
                    else:
                        buf.append(w["text"])
                if buf:
                    line = " ".join(buf)
                    if HEADER_PAT.match(line) or CTX.search(line):
                        pending = ""
                    elif is_caps(line):
                        nn = normalize_name(strip_parens(line))
                        pending = ""
                        if nn != ctx_norm and not ctx_norm.startswith(nn):
                            muni = line
                    else:
                        pending = (pending + " " + line).strip()
    return rows


def main() -> None:
    allrows = []
    for f, region in FILES.items():
        rows = walk_pdf(SRC / f, region)
        allrows += rows
        print(f"{f}: {len(rows)} barangay rows")
    df = pd.DataFrame(allrows)

    # province context problem: consecutive caps rows make provinces and munis
    # ambiguous — resolve by treating a caps row as a PROVINCE header when it
    # matches the province register AND its value equals the province total
    # (already handled implicitly: the first caps row after a region header is
    # the province; municipalities follow). Cross-check now with the resolver.
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype=str)
    ctx = df[["muni_src", "province_src", "region"]].drop_duplicates().copy()
    ctx["name_src"] = ctx.muni_src
    ctx.loc[ctx.region.str.contains("NCR"), "province_src"] = "National Capital Region (NCR)"
    resolved = resolve(ctx.dropna(subset=["name_src"]), munis)
    muni_code = {(r.muni_src, r.province_src, r.region): r.psgc10
                 for r in resolved.itertuples() if r.match_method != "UNRESOLVED"}
    un = resolved[resolved.match_method == "UNRESOLVED"]
    if len(un):
        print("unresolved muni contexts:", len(un))
        print(un[["name_src", "province_src"]].head(12).to_string())

    psgc = load_psgc()
    submun = psgc[psgc.level == "SubMun"]
    bgy = psgc[psgc.level == "Bgy"].copy()
    bgy["mun7"] = bgy.psgc10.str[:7]
    bgy["key"] = bgy["name"].map(norm_bgy)
    bgy["key_stripped"] = bgy["name"].map(lambda s: norm_bgy(strip_parens(str(s))))
    ix, ixs, manila = {}, {}, {}
    for t in bgy.itertuples():
        ix.setdefault((t.mun7, t.key), []).append(t.psgc10)
        ixs.setdefault((t.mun7, t.key_stripped), []).append(t.psgc10)
        if t.psgc10.startswith("13806"):
            manila.setdefault(t.key, []).append(t.psgc10)

    out = []
    n_ok = 0
    for t in df.itertuples():
        prov_ctx = "National Capital Region (NCR)" if "NCR" in t.region else t.province_src
        mcode = muni_code.get((t.muni_src, prov_ctx, t.region))
        rec = {"region": t.region, "province": t.province_src, "municipality": t.muni_src,
               "muni_psgc10": mcode or "", "barangay_src": t.barangay_src,
               "pop2010": t.pop2010, "psgc10": "", "flag": ""}
        if mcode:
            k = norm_bgy(t.barangay_src)
            c = ix.get((mcode[:7], k), [])
            if len(c) != 1:
                c2 = ixs.get((mcode[:7], norm_bgy(strip_parens(t.barangay_src))), [])
                if len(c2) == 1:
                    c = c2
                    rec["flag"] = "matched after dropping parenthetical"
            if len(c) == 1:
                rec["psgc10"] = c[0]; n_ok += 1
            else:
                rec["flag"] = ("ambiguous barangay name within municipality" if len(c) > 1
                               else "barangay name not matched to PSGC")
        elif isinstance(t.muni_src, str) and "NCR" in t.region:
            c = manila.get(norm_bgy(t.barangay_src), [])
            if len(c) == 1:
                rec["psgc10"] = c[0]; rec["muni_psgc10"] = "1380600000"
                rec["flag"] = "Manila (SubMun context)"; n_ok += 1
            else:
                rec["flag"] = "Manila SubMun: barangay not uniquely matched"
        else:
            rec["flag"] = "municipality context unresolved"
        out.append(rec)
    res = pd.DataFrame(out)

    # STRICT QA: per-municipality sums vs official 2010 counts
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    sums = res[res.muni_psgc10 != ""].groupby("muni_psgc10").pop2010.sum()
    chk = cp[["psgc10", "name", "pop2010"]].merge(
        sums.rename("bgy_sum"), left_on="psgc10", right_index=True, how="inner")
    bad = chk[chk.pop2010 != chk.bgy_sum]
    print(f"municipality-sum check: {len(chk) - len(bad)}/{len(chk)} exact; "
          f"{len(bad)} mismatched")
    if len(bad):
        bad = bad.assign(diff=bad.bgy_sum - bad.pop2010)
        print(bad.nlargest(8, "diff", keep="all")[["name", "pop2010", "bgy_sum", "diff"]]
              .to_string())
    # per-municipality QA flag: does the barangay sum equal the official count?
    ok_munis = set(chk[chk.pop2010 == chk.bgy_sum].psgc10)
    bad_munis = set(chk[chk.pop2010 != chk.bgy_sum].psgc10)
    res.loc[res.muni_psgc10.isin(bad_munis), "flag"] = (
        res.loc[res.muni_psgc10.isin(bad_munis), "flag"].fillna("").astype(str)
        .radd("municipality sum does not reconcile with official 2010 count; ").str.rstrip("; "))
    res["muni_sum_verified"] = res.muni_psgc10.isin(ok_munis)
    res.to_csv(CLEAN / "population_barangay_2010.csv", index=False)
    print(f"rows: {len(res)} | psgc-matched: {n_ok} ({n_ok/len(res)*100:.1f}%) | "
          f"national sum: {res.pop2010.sum():,}")

    # merge pop2010 into the 2020 barangay file on psgc10
    b20 = pd.read_csv(CLEAN / "population_barangay_2020.csv", dtype={"psgc10": str})
    add = res[(res.psgc10 != "") & res.muni_sum_verified][["psgc10", "pop2010"]].drop_duplicates("psgc10")
    b20 = b20.drop(columns=[c for c in ("pop2010",) if c in b20.columns])
    b20 = b20.merge(add, on="psgc10", how="left")
    b20.to_csv(CLEAN / "population_barangay_2020.csv", index=False)
    both = b20.pop2010.notna() & b20.psgc10.ne("")
    print(f"barangays with both 2010 and 2020: {int(both.sum())}")


if __name__ == "__main__":
    main()
