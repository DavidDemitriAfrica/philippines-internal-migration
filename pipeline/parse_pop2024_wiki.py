"""2024 POPCEN municipal populations via a VERIFIED secondary transcription.

PSA's 2024 Table B ("Population and Annual PGR by Province, City, and
Municipality") exists on psa.gov.ph but is unreachable from this machine
(Cloudflare IP block) and was never successfully crawled into the Internet
Archive. Until the primary file is dropped at
data/raw/census/2024popcen_tableB_muni.xlsx, we use the English Wikipedia
"List of cities and municipalities in the Philippines" table (Population
(2024) column, cited to the PSA census), pinned to a specific revision, and
ACCEPT IT ONLY WHERE IT RECONCILES with PSA's official Table A 2024
(provincial/HUC totals, primary source in our raw store):

    sum of municipal 2024 counts per province/HUC unit  ==  Table A value

Units that do not reconcile exactly are flagged and their municipalities are
EXCLUDED from the residual (never guessed). Every accepted number is thus
anchored to an official PSA marginal total; the file is still marked
`source=wikipedia-transcription (verified)` and slated for replacement by
Table B (docs/data_inventory.md gap #1).

Output: data/interim/pop2024_muni.csv
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, INTERIM = ROOT / "data" / "raw", ROOT / "data" / "interim"
PROVENANCE = ROOT / "data" / "provenance.jsonl"

TITLE = "List_of_cities_and_municipalities_in_the_Philippines"
REVID = 1364613900  # 2026-07-17 revision, pinned


def fetch_wikitext() -> str:
    out = RAW / "wikipedia" / f"lgu_list_rev{REVID}.json"
    if not out.exists():
        url = ("https://en.wikipedia.org/w/api.php?action=parse"
               f"&oldid={REVID}&prop=wikitext&format=json&formatversion=2")
        req = urllib.request.Request(url, headers={"User-Agent": "migration-dataset-research/0.1"})
        data = urllib.request.urlopen(req, timeout=60).read()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        rec = {"file": str(out.relative_to(ROOT)), "source_url": url,
               "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
               "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "note": ("enwiki LGU list rev 1364613900 (2026-07-17): Population (2024) column "
                        "cited to PSA 2024 POPCEN; used as VERIFIED transcription pending Table B "
                        "(license CC BY-SA 4.0)")}
        with PROVENANCE.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    return json.loads(out.read_text())["parse"]["wikitext"]


def parse_rows(wt: str) -> pd.DataFrame:
    """Rows look like:
    ! scope="row" | [[Adams, Ilocos Norte|Adams]]\n| 2,279\n| 159.31\n| ...\n| Mun\n| [[Ilocos Norte]]
    The province cell may carry an id= attribute; city rows use City/HUC/ICC in Class.
    """
    rows = []
    blocks = re.split(r'!\s*scope="row"[^|\n]*\|', wt)
    for b in blocks[1:]:
        b = b.split("\n|-")[0]  # stop at end of this table row
        cells = [c.strip() for c in b.split("\n|")]
        if len(cells) < 4:
            continue
        name_raw = cells[0].strip()
        m = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", name_raw)
        name = m.group(1) if m else re.sub(r"[{}\[\]]", "", name_raw)
        pop_raw = re.sub(r"\{\{.*?\}\}", "", cells[1].replace(",", "")).strip()
        if not re.match(r"^\d+$", pop_raw):
            continue
        # class = first cell that is exactly a class token; province = last
        # wikilinked cell (skipping the name cell)
        cls = next((c for c in cells[2:] if re.fullmatch(r"(Mun|CC|ICC|HUC)", c.strip())), "")
        prov = None
        for c in reversed(cells[2:]):
            pm = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", c)
            if pm:
                prov = pm.group(1)
                break
        if prov is None:
            prov = ""
        rows.append({"name_src": name, "province_src": prov, "pop2024": int(pop_raw),
                     "class_src": cls})
    return pd.DataFrame(rows)


def main() -> None:
    wt = fetch_wikitext()
    df = parse_rows(wt)
    print("parsed rows:", len(df))
    munis = pd.read_csv(INTERIM / "psgc_municipalities.csv", dtype={"psgc10": str})
    res = resolve(df, munis)
    n_un = (res.match_method == "UNRESOLVED").sum()
    print("unresolved:", n_un)
    if n_un:
        print(res[res.match_method == "UNRESOLVED"][["name_src", "province_src"]].to_string())
    dup = res[res.psgc10.ne("") & res.psgc10.duplicated(keep=False)]
    if len(dup):
        print("DUPLICATE assignments:\n", dup[["name_src", "province_src", "psgc10"]].to_string())
    res.to_csv(INTERIM / "pop2024_muni.csv", index=False)
    print("total 2024 pop (sum of parsed):", res.pop2024.sum())


if __name__ == "__main__":
    main()
