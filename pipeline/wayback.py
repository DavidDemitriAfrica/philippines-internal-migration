"""Download psa.gov.ph (and other Cloudflare-blocked) files via the Wayback Machine.

psa.gov.ph returns 403 to this machine's IP range; the Internet Archive holds
snapshots of both pages and attached files. Provenance records BOTH the original
URL and the archive URL + snapshot timestamp, so every number remains traceable
to the named PSA source file.

Usage:
    python pipeline/wayback.py get "https://psa.gov.ph/system/files/scd/PSGC-1Q-2026-Publication-Datafile.xlsx" \
        --out data/raw/psgc/PSGC-1Q-2026-Publication-Datafile.xlsx --note "PSGC 1Q2026 datafile"
    python pipeline/wayback.py page "https://psa.gov.ph/classification/psgc"   # print archived page links
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ROOT / "data" / "provenance.jsonl"
UA = "migration-dataset-pipeline/0.1 (open research)"


def _get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def find_snapshot(original_url: str, timestamp: str | None = None) -> dict | None:
    """Return closest snapshot info from the Wayback availability API."""
    q = f"http://archive.org/wayback/available?url={urllib.parse.quote(original_url, safe='')}"
    if timestamp:
        q += f"&timestamp={timestamp}"
    data = json.loads(_get(q))
    snap = data.get("archived_snapshots", {}).get("closest")
    return snap if snap and snap.get("available") else None


def get_file(original_url: str, out: Path, note: str = "", timestamp: str | None = None) -> Path:
    snap = find_snapshot(original_url, timestamp)
    if not snap:
        raise SystemExit(f"NO SNAPSHOT: {original_url}")
    # 'id_' suffix serves the original bytes without archive rewriting.
    ts = snap["timestamp"]
    archive_url = f"http://web.archive.org/web/{ts}id_/{original_url}"
    data = _get(archive_url)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    rec = {
        "file": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out),
        "source_url": original_url,
        "archive_url": archive_url,
        "snapshot_timestamp": ts,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "note": note or "retrieved via Wayback Machine (psa.gov.ph blocks direct access)",
    }
    PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    with PROVENANCE.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    time.sleep(1.0)
    return out


def page_links(original_url: str, pattern: str = r"\.(xlsx|xls|csv|zip)", timestamp: str | None = None) -> list[str]:
    snap = find_snapshot(original_url, timestamp)
    if not snap:
        raise SystemExit(f"NO SNAPSHOT: {original_url}")
    html = _get(snap["url"]).decode("utf-8", errors="replace")
    links = set()
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if re.search(pattern, href, re.I):
            # strip wayback prefix to recover the original URL
            mm = re.search(r"https?://psa\.gov\.ph\S*", href)
            if mm:
                links.add(mm.group(0))
    return sorted(links)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("url"); g.add_argument("--out", required=True)
    g.add_argument("--note", default=""); g.add_argument("--timestamp", default=None)
    p = sub.add_parser("page")
    p.add_argument("url"); p.add_argument("--pattern", default=r"\.(xlsx|xls|csv|zip)")
    p.add_argument("--timestamp", default=None)
    args = ap.parse_args()
    if args.cmd == "get":
        out = get_file(args.url, Path(args.out), args.note, args.timestamp)
        print("wrote", out)
    else:
        for link in page_links(args.url, args.pattern, args.timestamp):
            print(link)


if __name__ == "__main__":
    main()
