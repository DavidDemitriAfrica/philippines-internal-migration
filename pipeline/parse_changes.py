"""Parse the PSGC Summary of Changes (1977-2000 and 2001-present sheets) into
a tidy event log documenting every municipality creation, cityhood conversion,
rename, transfer, merger, and abolition — the documentation backbone of the
cross-census harmonization.

Output: data/clean/psgc_changes.csv
    period, name, change_type, new_code9, mother_or_old_name, old_code9,
    legal_basis, remarks, level
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "psgc" / "PSGC-1Q-2025-Summary-of-Changes.xlsx"
OUT = ROOT / "data" / "clean" / "psgc_changes.csv"

PERIOD_PAT = re.compile(r"(update|updates)\s*$", re.I)
HEADER_PAT = re.compile(r"region/province", re.I)


def classify_level(code) -> str:
    c = str(code) if code is not None else ""
    c = re.sub(r"\.0$", "", c).strip()
    if not c.isdigit():
        return ""
    c = c.zfill(9)
    if c[5:] == "0000000"[:4]:  # never true for 9-digit; keep simple below
        return ""
    if c.endswith("000"):
        return "province" if c[5:7] == "00" else "city_muni"
    return "barangay"


def parse_sheet(sheet: str) -> list[dict]:
    df = pd.read_excel(SRC, sheet_name=sheet, header=None, dtype=str)
    rows = []
    period = None
    for _, r in df.iterrows():
        c0 = (r[0] or "").strip() if isinstance(r[0], str) else ""
        if not c0 and not any(isinstance(v, str) and v.strip() for v in r[1:]):
            continue
        if c0 and PERIOD_PAT.search(c0):
            period = c0.replace("Updates", "").replace("Update", "").strip()
            continue
        if c0 and HEADER_PAT.search(c0):
            continue
        if not isinstance(r[1], str) or not r[1].strip():
            continue  # not an event row (title/footnote lines)
        rows.append({
            "period": period,
            "name": c0,
            "change_type": r[1].strip(),
            "new_code9": (r[2] or "").strip() if isinstance(r[2], str) else r[2],
            "mother_or_old_name": (r[3] or "").strip() if isinstance(r[3], str) else r[3],
            "old_code9": (r[4] or "").strip() if isinstance(r[4], str) else r[4],
            "legal_basis": (r[5] or "").strip() if isinstance(r[5], str) else r[5],
            "remarks": (r[6] or "").strip() if isinstance(r[6], str) and len(r) > 6 else None,
            "sheet": sheet,
        })
    return rows


def main() -> None:
    rows = parse_sheet("2001-present") + parse_sheet("1977-2000")
    df = pd.DataFrame(rows)
    df["level"] = df["new_code9"].map(classify_level)
    df.loc[df.level == "", "level"] = df["old_code9"].map(classify_level)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print("events:", len(df))
    print(df[df.level == "city_muni"].change_type.value_counts().head(15).to_string())


if __name__ == "__main__":
    main()
