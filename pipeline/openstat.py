"""PSA OpenSTAT (PxWeb) client with provenance logging.

OpenSTAT is a PxWeb instance at https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB.
Every fetched artifact is written under data/raw/openstat/ and logged to
data/provenance.jsonl with URL, query, timestamp, and sha256.

Usage:
    python pipeline/openstat.py ls 1A/VS/BI           # list a folder
    python pipeline/openstat.py meta 1A/VS/BI/0011A1ABIB8.px
    python pipeline/openstat.py fetch 1A/VS/BI/0011A1ABIB8.px --out births_muni_2024 \
        --select 'Place=1' --select 'Sex=0'
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "openstat"
PROVENANCE = ROOT / "data" / "provenance.jsonl"

UA = "migration-dataset-pipeline/0.1 (open research; contact via repo)"


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post(url: str, payload: dict, timeout: int = 300) -> bytes:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def log_provenance(path: Path, source_url: str, note: str, query: dict | None = None) -> None:
    PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "file": str(path.relative_to(ROOT)),
        "source_url": source_url,
        "query": query,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    }
    with PROVENANCE.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ls(folder: str) -> list[dict]:
    return json.loads(_get(f"{API}/{folder}"))


def meta(table: str) -> dict:
    return json.loads(_get(f"{API}/{table}"))


def fetch(table: str, out: str, selects: list[str], fmt: str = "csv", note: str = "") -> Path:
    """Fetch a table. Variables not mentioned in selects are returned in full."""
    query = []
    for s in selects:
        code, values = s.split("=", 1)
        query.append({"code": code, "selection": {"filter": "item", "values": values.split(",")}})
    payload = {"query": query, "response": {"format": fmt}}
    url = f"{API}/{table}"
    data = _post(url, payload)
    RAW.mkdir(parents=True, exist_ok=True)
    ext = "csv" if fmt.startswith("csv") else fmt
    path = RAW / f"{out}.{ext}"
    path.write_bytes(data)
    # PxWeb CSV is often Windows-1252; keep raw bytes, decode downstream.
    meta_path = RAW / f"{out}.meta.json"
    meta_path.write_bytes(_get(url))
    log_provenance(path, url, note or f"PxWeb POST {payload['query']}", payload)
    log_provenance(meta_path, url, "PxWeb table metadata (GET)")
    time.sleep(1.0)  # be polite
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ls = sub.add_parser("ls"); p_ls.add_argument("folder")
    p_meta = sub.add_parser("meta"); p_meta.add_argument("table")
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("table")
    p_fetch.add_argument("--out", required=True)
    p_fetch.add_argument("--select", action="append", default=[])
    p_fetch.add_argument("--format", default="csv")
    p_fetch.add_argument("--note", default="")
    args = ap.parse_args()

    if args.cmd == "ls":
        for t in ls(args.folder):
            print(t.get("id"), "|", t.get("type"), "|", t.get("text"))
    elif args.cmd == "meta":
        m = meta(args.table)
        print(m["title"])
        for v in m["variables"]:
            vals = v.get("valueTexts", [])
            print(f"  {v['code']}: {len(vals)} values", vals[:5], "..." if len(vals) > 5 else "")
    elif args.cmd == "fetch":
        p = fetch(args.table, args.out, args.select, args.format, args.note)
        print("wrote", p)


if __name__ == "__main__":
    main()
